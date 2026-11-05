# CEO OS — 30-Day Build-to-Hire Roadmap

## Outcome
By day 30, the candidate should be able to demonstrate a production-minded CEO AI operating system and explain the business architecture, data flows, APIs, approval controls, failure handling and measurable value.

## Week 1 — Core system
- Run the FastAPI MVP locally.
- Understand every endpoint and data model.
- Extend priority scoring with one additional business rule.
- Learn REST basics by calling `/briefing` from Postman/curl.
- Learn Git fundamentals: branch, commit, pull request, tag.
- Add one unit test yourself.

**Proof:** explain the codebase without reading from notes and modify it live.

## Week 2 — Google workspace integration
- Configure a Google Cloud project.
- Implement OAuth with minimum required Gmail and Calendar scopes.
- Pull recent email metadata and calendar events into normalized WorkItem objects.
- Do not enable autonomous sending.
- Add token refresh, error handling and environment-based secrets.

**Proof:** live morning briefing built from authorized Gmail + Calendar data.

## Week 3 — Orchestration + CRM
- Run n8n locally or in a secured hosted environment.
- Schedule the morning briefing workflow.
- Add a CRM connector or mock CRM API.
- Detect stale high-value opportunities.
- Create AI-generated follow-up drafts behind approval.
- Persist proposals and decisions to PostgreSQL.

**Proof:** end-to-end workflow from source event to approved proposed action.

## Week 4 — Portfolio + executive demo
- Add WhatsApp Business integration pattern or sandbox where permitted.
- Add audit logs, retries, idempotency and basic monitoring.
- Record a 2–3 minute demo.
- Publish architecture diagram and case study.
- Prepare technical walkthrough and failure-mode answers.

**Proof:** demonstrate the system, then answer architecture questions without hiding behind no-code terminology.

## Interview bar
You are ready when you can answer all of these clearly:
1. Why use n8n instead of putting every integration in Python?
2. What belongs in the orchestration layer vs the decision layer?
3. How do OAuth refresh tokens work and where are they stored?
4. How do you prevent duplicate actions after retries?
5. Which actions require human approval and why?
6. How would you isolate one executive's data from another's?
7. How do you test a workflow before allowing writes to production systems?
8. How do you measure whether the AI system saves time or just creates noise?
9. What happens when the LLM is unavailable?
10. What happens when an API changes, rate-limits, or returns partial data?

## KPI targets for the pilot
These are targets, not claims until measured:
- 50%+ reduction in daily triage time
- 90%+ critical follow-ups surfaced within defined SLA
- 100% sensitive external actions logged
- 0 autonomous high-risk writes during pilot
- measurable reduction in opportunities without a next action
