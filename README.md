# CEO OS — AI Executive Operating System MVP

A portfolio-grade MVP showing how an AI automation professional can turn fragmented executive work into a prioritized operating system.

## What this demonstrates

- Executive priority scoring across email, calendar, CRM, tasks, WhatsApp/news-style inputs
- AI-generated morning briefing with deterministic fallback
- Human-in-the-loop approval gate: server-controlled status, risk floors per action type, final decisions, execute-once
- Persistent actions + append-only audit log (SQLite locally, PostgreSQL in Docker)
- Idempotent proposals (`Idempotency-Key` header) so n8n retries never duplicate actions
- Mock CRM with stalled-deal detection and AI-drafted follow-ups behind approval
- Read-only Gmail + Google Calendar connector (OAuth, minimum scopes, token refresh)
- FastAPI service layer with importable n8n workflows
- Dockerized local stack with n8n + PostgreSQL

## Architecture

```text
Sources (Email / Calendar / CRM / WhatsApp / News)
          |
          v
       n8n orchestration
          |
          v
      FastAPI CEO OS
     /      |       \
Priority  LLM layer  Approval Gate
Engine               |
     \                v
      ----> PostgreSQL / Audit Log
                     |
                     v
               Approved Actions
```

## Run locally

```bash
cp .env.example .env
uv venv --python 3.12
uv pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload
```

Python 3.12 is pinned in `.python-version`; the pinned pydantic does not build on 3.14.

Run tests with `.venv/bin/pytest -q`.

Locally, actions and the audit log go to `ceoos.db` (SQLite). Set `DATABASE_URL` to a
`postgresql+psycopg://...` URL to use Postgres instead. Tables are created on first use.

Open:

- API docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`
- Demo briefing: `http://localhost:8000/demo/briefing`

### Docker option

```bash
cp .env.example .env
docker compose up --build
```

Then use:
- CEO OS API: `http://localhost:8000` (backed by Postgres; if 8000 is taken, start with `API_PORT=8010 docker compose up -d`)
- n8n: `http://localhost:5678`

Import the workflows into n8n:

```bash
docker compose exec n8n n8n import:workflow --separate --input=/workflows
```

See [n8n/README.md](n8n/README.md) for what each workflow does. To run one from the CLI while n8n is up:

```bash
docker compose exec -e N8N_RUNNERS_BROKER_PORT=5690 n8n n8n execute --id=ceoMorningBrief01
```

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/demo/briefing` | Briefing from sample data |
| POST | `/briefing` | Briefing from work items you supply |
| GET | `/briefing/google` | Live briefing from Gmail + Calendar (+ stalled CRM deals) |
| POST | `/actions/propose` | Propose an action (status is always `proposed`) |
| POST | `/actions/decide` | Approve or reject a proposed action (once) |
| POST | `/actions/{id}/execute` | Execute an approved action (once; dry-run by default) |
| GET | `/actions`, `/actions/{id}` | List / inspect actions (`?status=proposed`) |
| GET | `/audit` | Audit trail (`?action_id=`) |
| GET | `/crm/stale-opportunities` | Open, high-value deals with no recent activity |
| POST | `/crm/follow-ups` | Draft follow-ups for stalled deals (idempotent) |

### Action lifecycle

```text
proposed --approve--> approved --execute--> executing --> executed
    \                                           \
     --reject--> rejected                         --> failed (error recorded)
```

- Clients cannot set status; anything they send is ignored.
- Risk is raised to a per-type floor (`send_email` is always high, `crm_update`/`calendar_update` at least medium).
- Status changes are compare-and-set in the database, so two concurrent approvals or executions cannot both succeed.
- Execution is dry-run unless `ALLOW_EXTERNAL_ACTIONS=true` **and** a live executor is registered in `app/services/executors.py`. None are registered yet, so nothing leaves the system.
- Every transition is written to the audit log.

## Google Workspace (Gmail + Calendar)

Read-only, using the `gmail.metadata` (headers and labels, no message bodies) and `calendar.events.readonly` scopes.

1. In Google Cloud console: create a project and enable the Gmail API and Google Calendar API.
2. Configure the OAuth consent screen (External, Testing) and add your account as a test user.
3. Create an OAuth client of type **Desktop app**. Download the JSON to `secrets/google_client_secret.json`.
4. Install and authorize:

```bash
uv pip install -r requirements-google.txt
```

```bash
.venv/bin/python -m app.providers.google_workspace auth
```

5. Check it, then open `http://localhost:8000/briefing/google`:

```bash
.venv/bin/python -m app.providers.google_workspace check
```

The refresh token is stored in `secrets/google_token.json` with owner-only permissions; `secrets/` is gitignored and kept out of the Docker image (it is mounted at runtime instead).

## OpenAI configuration

Set `OPENAI_API_KEY` and `OPENAI_MODEL` in `.env`. The MVP intentionally does not hard-code a model name, so the deployment can use whichever approved model is available in the target account. If these values are absent, the system still runs using a deterministic executive-summary fallback.

## Safety / governance

Default operating principle: **read freely within authorized scopes; write externally only after approval**.

Examples requiring approval:
- sending email or WhatsApp messages
- changing calendar events
- updating CRM opportunity stages
- publishing social content
- placing financial/trading actions

## Portfolio demo flow

1. Open `/demo/briefing`.
2. Show how mixed executive inputs become ranked priorities.
3. `POST /crm/follow-ups` to show stalled deals turning into drafted follow-ups, then call it again to show nothing is duplicated.
4. Approve one with `/actions/decide`, execute it with `/actions/{id}/execute` (dry run), and show `/audit`.
5. Try to approve it again, or propose an action with `"status": "approved"`, to show the gate holding.
6. Explain that n8n is the orchestration layer and external connectors are intentionally isolated from decision logic.

## Roadmap status

| Roadmap item | Status |
|---|---|
| Extra priority rule (key-stakeholder boost) + tests | Done |
| Gmail + Calendar → WorkItems, OAuth, token refresh, env-based secrets | Built and unit-tested; needs your Google Cloud project to run live |
| n8n scheduled briefing workflow | Done (`n8n/workflows/`) |
| Mock CRM + stalled-deal detection + drafted follow-ups behind approval | Done |
| Proposals and decisions saved to PostgreSQL | Done |
| Audit log, retries, idempotency | Done |
| Briefing delivery channel (Slack/email/WhatsApp) | Not done: add a node in n8n with your own credentials |
| WhatsApp Business, real CRM, live executors, RBAC/auth on the API | Not done |
| Demo recording, case study, interview prep | Yours |

## Next production integrations

- Gmail API OAuth with minimum necessary scopes
- Google Calendar API
- HubSpot / Salesforce
- WhatsApp Business Platform
- Slack / Teams
- social analytics and publishing APIs
- Langfuse/Sentry or equivalent observability
- encrypted token storage, API authentication and RBAC (today any caller can approve; `approver` is self-reported)
- Alembic migrations once the schema starts changing

## Portfolio positioning

**Problem:** senior executives lose time switching between communication, meetings, CRM, reporting and follow-ups.

**Solution:** CEO OS creates a single decision layer that ranks what matters, drafts next actions, requests approval for sensitive actions and tracks execution.

**Business KPI targets:**
- reduce executive inbox triage time
- reduce missed follow-ups
- shorten decision-to-action cycle time
- improve CRM follow-up SLA
- increase percentage of meetings with prepared context/action capture

Do not claim quantified impact until measured in a live pilot.
