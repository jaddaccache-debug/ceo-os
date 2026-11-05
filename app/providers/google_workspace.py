"""Gmail + Google Calendar connector (read-only).

Scopes are the minimum needed for a briefing: message metadata (headers and labels, no
bodies) and read-only calendar events. Nothing here can send mail or change events.

One-time setup:
  1. Google Cloud console -> create a project, enable the Gmail API and Google Calendar API.
  2. OAuth consent screen (External, Testing) and add yourself as a test user.
  3. Create an OAuth client of type "Desktop app" and download the JSON to
     secrets/google_client_secret.json (or point GOOGLE_CLIENT_SECRETS at it).
  4. uv pip install -r requirements-google.txt
  5. .venv/bin/python -m app.providers.google_workspace auth
     This opens a browser for consent and stores a refresh token in secrets/google_token.json.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr
from pathlib import Path

from app.models import Source, WorkItem

SCOPES = [
    "https://www.googleapis.com/auth/gmail.metadata",
    "https://www.googleapis.com/auth/calendar.events.readonly",
]

NOISE_CATEGORIES = {"CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL", "CATEGORY_UPDATES", "CATEGORY_FORUMS"}


class GoogleNotConfigured(Exception):
    pass


def _client_secrets_path() -> Path:
    return Path(os.getenv("GOOGLE_CLIENT_SECRETS", "secrets/google_client_secret.json"))


def _token_path() -> Path:
    return Path(os.getenv("GOOGLE_TOKEN_PATH", "secrets/google_token.json"))


def _save_token(creds) -> None:
    path = _token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Owner-only permissions: the refresh token grants ongoing read access to the mailbox.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(creds.to_json())


def authorize() -> None:
    from google_auth_oauthlib.flow import InstalledAppFlow

    secrets = _client_secrets_path()
    if not secrets.exists():
        raise GoogleNotConfigured(f"OAuth client file not found at {secrets}")
    flow = InstalledAppFlow.from_client_secrets_file(str(secrets), SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    _save_token(creds)


def load_credentials():
    """Load stored credentials, refreshing the access token when it has expired.

    Access tokens last about an hour; the refresh token lets us mint new ones without
    another consent screen until the user revokes access.
    """
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except ImportError as exc:
        raise GoogleNotConfigured("Install requirements-google.txt to enable Google connectors") from exc

    path = _token_path()
    if not path.exists():
        raise GoogleNotConfigured("No Google token yet: run `python -m app.providers.google_workspace auth`")
    creds = Credentials.from_authorized_user_file(str(path), SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            _save_token(creds)
        else:
            raise GoogleNotConfigured("Stored Google token is invalid: re-run the auth command")
    return creds


# --- Normalization (pure functions, unit-tested without network) ---

def _headers(msg: dict) -> dict[str, str]:
    return {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}


def gmail_message_to_work_item(msg: dict) -> WorkItem:
    headers = _headers(msg)
    labels = set(msg.get("labelIds", []))
    name, address = parseaddr(headers.get("from", ""))
    is_noise = bool(labels & NOISE_CATEGORIES)

    if "STARRED" in labels:
        importance = 5
    elif "IMPORTANT" in labels:
        importance = 4
    elif is_noise:
        importance = 1
    else:
        importance = 3

    return WorkItem(
        id=f"gmail-{msg['id']}",
        source=Source.email,
        title=headers.get("subject") or "(no subject)",
        summary=f"From {name or address}",
        sender_or_owner=name or address or None,
        importance=importance,
        urgency=2 if is_noise else 3,
        requires_reply="UNREAD" in labels and "INBOX" in labels and not is_noise,
        metadata={"from_email": address.lower(), "thread_id": msg.get("threadId"), "labels": sorted(labels)},
    )


def _event_start(event: dict) -> datetime | None:
    start = event.get("start", {})
    if "dateTime" in start:
        return datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00"))
    return None  # all-day events carry no time pressure


def calendar_event_to_work_item(event: dict, now: datetime | None = None) -> WorkItem:
    now = now or datetime.now(timezone.utc)
    start = _event_start(event)
    attendees = event.get("attendees", [])
    me = next((a for a in attendees if a.get("self")), {})
    hours_away = (start - now).total_seconds() / 3600 if start else None

    return WorkItem(
        id=f"gcal-{event['id']}",
        source=Source.calendar,
        title=event.get("summary") or "(untitled event)",
        summary=f"{len(attendees)} attendees" + (f", organized by {event['organizer'].get('email')}" if event.get("organizer") else ""),
        sender_or_owner=event.get("organizer", {}).get("displayName") or event.get("organizer", {}).get("email"),
        due_at=start,
        importance=4 if len(attendees) >= 5 else 3,
        urgency=4 if hours_away is not None and hours_away <= 4 else 3,
        requires_reply=me.get("responseStatus") == "needsAction",
        metadata={"html_link": event.get("htmlLink"), "attendee_count": len(attendees)},
    )


# --- Fetching ---

def fetch_work_items(max_emails: int = 25, hours_ahead: int = 24) -> list[WorkItem]:
    from googleapiclient.discovery import build

    creds = load_credentials()
    gmail = build("gmail", "v1", credentials=creds, cache_discovery=False)
    calendar = build("calendar", "v3", credentials=creds, cache_discovery=False)

    items: list[WorkItem] = []
    # The metadata scope does not allow the `q` search parameter, so filter by label instead.
    listing = gmail.users().messages().list(userId="me", labelIds=["INBOX", "UNREAD"], maxResults=max_emails).execute()
    for ref in listing.get("messages", []):
        msg = gmail.users().messages().get(
            userId="me", id=ref["id"], format="metadata", metadataHeaders=["From", "Subject", "Date"]
        ).execute()
        items.append(gmail_message_to_work_item(msg))

    now = datetime.now(timezone.utc)
    events = calendar.events().list(
        calendarId="primary", timeMin=now.isoformat(), timeMax=(now + timedelta(hours=hours_ahead)).isoformat(),
        singleEvents=True, orderBy="startTime",
    ).execute()
    items.extend(calendar_event_to_work_item(e, now) for e in events.get("items", []) if e.get("status") != "cancelled")
    return items


if __name__ == "__main__":
    if sys.argv[1:] == ["auth"]:
        authorize()
        print(f"Saved token to {_token_path()}")
    elif sys.argv[1:] == ["check"]:
        for item in fetch_work_items():
            print(f"{item.source.value:8} {item.title}")
    else:
        print("usage: python -m app.providers.google_workspace [auth|check]")
