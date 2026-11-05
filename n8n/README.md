# n8n workflows

Importable workflows live in `workflows/`. With the Docker stack running:

```bash
docker compose exec n8n n8n import:workflow --separate --input=/workflows
```

They import inactive. Open each one in n8n, run it once by hand, then activate it.

| Workflow | Schedule | What it does |
|---|---|---|
| `morning_briefing.json` | Weekdays 07:00 | GET the briefing, format a short text message |
| `stale_deal_watcher.json` | Weekdays hourly, 08:00–18:00 | POST `/crm/follow-ups`, summarize drafts waiting for approval |

Both end at a formatted `text` field. Add a delivery node (Slack, Gmail, Telegram, etc.) after it with your own credentials.

The morning briefing calls `/briefing/google`, so authorize Google first (see the main README); until then that call returns 503. To run it without Google, change the URL to `http://api:8000/demo/briefing`.

## Planned workflows

1. Email follow-up detector -> create `draft_email` proposal -> require CEO approval.
2. Meeting prep -> pull attendees/context -> summarize -> propose action list.

## Rules

- All external write actions stay behind the approval gate until a workflow is deliberately promoted to trusted automation.
- Send an `Idempotency-Key` header when proposing actions from n8n, so retried executions never create duplicates.
- Do not add an n8n webhook that approves actions unless it is authenticated: anyone who can reach it could approve.
