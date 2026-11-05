from datetime import datetime, timedelta, timezone

from app.providers.google_workspace import calendar_event_to_work_item, gmail_list_labels, gmail_message_to_work_item


def test_gmail_unread_important_needs_reply():
    msg = {
        'id': 'm1', 'threadId': 't1', 'labelIds': ['INBOX', 'UNREAD', 'IMPORTANT'],
        'payload': {'headers': [
            {'name': 'From', 'value': 'Jane Investor <jane@fund.example>'},
            {'name': 'Subject', 'value': 'Term sheet questions'},
        ]},
    }
    item = gmail_message_to_work_item(msg)
    assert item.id == 'gmail-m1'
    assert item.title == 'Term sheet questions'
    assert item.sender_or_owner == 'Jane Investor'
    assert item.importance == 4
    assert item.requires_reply
    assert item.metadata['from_email'] == 'jane@fund.example'


def test_gmail_promotions_are_low_priority_and_no_reply():
    msg = {'id': 'm2', 'labelIds': ['INBOX', 'UNREAD', 'CATEGORY_PROMOTIONS'],
           'payload': {'headers': [{'name': 'From', 'value': 'deals@shop.example'}]}}
    item = gmail_message_to_work_item(msg)
    assert item.importance == 1
    assert not item.requires_reply
    assert item.title == '(no subject)'


def test_calendar_event_soon_with_pending_rsvp():
    now = datetime(2026, 10, 5, 8, 0, tzinfo=timezone.utc)
    event = {
        'id': 'e1', 'summary': 'Board review',
        'start': {'dateTime': (now + timedelta(hours=2)).isoformat()},
        'organizer': {'email': 'chair@board.example'},
        'attendees': [{'email': f'p{i}@x.example'} for i in range(5)] + [{'email': 'me@x.example', 'self': True, 'responseStatus': 'needsAction'}],
    }
    item = calendar_event_to_work_item(event, now)
    assert item.source.value == 'calendar'
    assert item.urgency == 4
    assert item.importance == 4
    assert item.requires_reply
    assert item.due_at == now + timedelta(hours=2)


def test_all_day_event_has_no_due_time():
    event = {'id': 'e2', 'summary': 'Offsite', 'start': {'date': '2026-10-06'}}
    item = calendar_event_to_work_item(event)
    assert item.due_at is None
    assert item.urgency == 3


def test_newsletter_in_primary_is_noise_even_if_important():
    msg = {'id': 'm3', 'labelIds': ['INBOX', 'UNREAD', 'IMPORTANT', 'CATEGORY_PERSONAL'],
           'payload': {'headers': [{'name': 'From', 'value': 'news@media.example'},
                                   {'name': 'Subject', 'value': 'This week in AI'},
                                   {'name': 'List-Unsubscribe', 'value': '<mailto:unsub@media.example>'}]}}
    item = gmail_message_to_work_item(msg)
    assert item.importance == 1
    assert not item.requires_reply


def test_starred_bulk_mail_stays_top_importance():
    msg = {'id': 'm4', 'labelIds': ['INBOX', 'STARRED', 'CATEGORY_UPDATES'], 'payload': {'headers': []}}
    assert gmail_message_to_work_item(msg).importance == 5


def test_inbox_listing_defaults_to_primary_tab():
    assert gmail_list_labels() == ['INBOX', 'UNREAD', 'CATEGORY_PERSONAL']
    assert gmail_list_labels(primary_only=False) == ['INBOX', 'UNREAD']
