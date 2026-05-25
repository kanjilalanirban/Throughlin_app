# Integrations

Read this when working on Jira, GitHub, or HRIS adapters. The adapter pattern is the contract; concrete implementations vary by source.

## The Adapter Pattern

All ingestion adapters implement a single interface:

```python
class SourceAdapter(Protocol):
    source_name: str  # "jira" | "github" | "hris_csv" | ...

    async def authenticate(self, secrets: dict) -> AuthContext: ...
    async def discover_resources(self, ctx: AuthContext) -> list[Resource]: ...
    async def fetch_signals(
        self, ctx: AuthContext, since: datetime
    ) -> AsyncIterator[RawSignal]: ...
    async def map_to_internal(self, raw: RawSignal) -> Signal: ...
```

Adapters live in `backend/app/integrations/{source_name}/`. The Lambda entry point lives in `ingesters/{source_name}/handler.py` and is thin — it imports the adapter and runs the standard ingestion loop.

**Why this pattern matters:** Every future partner will have a different HRIS, possibly a different ticketing system, possibly a different code host. Coupling Phase 0 code to specific vendors is the wrong move. The internal schema is the contract; adapters are the variable.

## Jira (Atlassian Cloud Free)

### Setup
1. Sign up for Atlassian Cloud Free at https://www.atlassian.com/software/jira/free (up to 10 users, full API access).
2. Populate test data:
   - At least 1 epic representing a "transformation initiative."
   - 30–50 issues distributed across 3–5 sprints.
   - A small team of users (sock-puppet accounts or real teammates).
3. Register an OAuth 2.0 (3LO) integration at https://developer.atlassian.com/console.
4. Configure scopes: `read:jira-work`, `read:jira-user`, `read:project:jira`, `read:issue:jira`.
5. Store the OAuth client ID and secret in AWS Secrets Manager under `companybrain/phase0/jira/oauth`.

### Auth flow (OAuth 2.0 3LO)
- The user (the team during Phase 0) goes through an OAuth consent flow from the React UI.
- FastAPI handles the callback at `/api/integrations/jira/callback`.
- Access tokens have a short TTL; refresh tokens are stored encrypted in Secrets Manager.
- The `jira-ingester` Lambda fetches a fresh access token via the refresh token at the start of every run.

### What we ingest
- **Projects** → metadata cached in Postgres.
- **Epics** → strong candidates for initiative inference.
- **Issues** → primary signals. Title, description, status, assignee, transitions, comments.
- **Sprints** → useful for velocity signals.

### Rate limits
- Jira Cloud REST API: roughly 100 requests per 10 seconds per user.
- Implement client-side rate limiting in the adapter — don't rely on the API to push back.

### Quirks
- Use REST API **v3** (the JSON-document format for descriptions). v2 is deprecated.
- Issue descriptions arrive as ADF (Atlassian Document Format) JSON, not plain text. Use `atlassian-python-api` or write a small ADF-to-Markdown converter.

## GitHub (Free Org or Personal Account)

### Setup
1. Create a free GitHub org (or use a personal account with private repos).
2. Populate test data:
   - 2–3 repos with **realistic activity**: real commits, PRs, reviews, issues, contributors.
   - At least 2–3 distinct contributors (real teammates, not just commits attributed to one person).
3. Register a **GitHub App** (not an OAuth App) at https://github.com/settings/apps.
   - Permissions: **Read** on Contents, Metadata, Pull Requests, Issues, Members.
   - Subscribe to events: `push`, `pull_request`, `issues`, `member`.
4. Generate and download the App's private key. Store in Secrets Manager under `companybrain/phase0/github/app-key`.

### Why a GitHub App, not OAuth?
- Per-org isolation.
- Fine-grained, declarative permissions.
- App installations issue short-lived tokens (1 hour) automatically — better security posture.
- Webhook events are scoped to the app's installation.
- This is the right pattern for production SaaS, and switching from OAuth later is painful, so do it right now.

### What we ingest
- **Repositories**: metadata, languages, default branch, size.
- **Commits**: SHA, author (with email — primary join key to HRIS), co-authors, message, timestamp, files touched (just paths, not content in Phase 0).
- **Pull requests**: title, description, state, requested reviewers, actual reviewers, merge status, linked issues.
- **Reviews**: who approved/commented/requested-changes.
- **Issues**: title, body, labels, assignees.
- **Members**: org membership.

### Identity mapping
GitHub `email` (from `commit.author.email`) is the primary key joining to `people.email`. **But** many engineers commit with their `noreply` GitHub email rather than their work email. Handle this in `app/inference/identity.py`:
1. Try direct email match.
2. Fall back to matching `github_handle` on the people table if populated.
3. Fall back to fuzzy name match with a confidence threshold (mark these as `low_confidence_mapping` for manual review).

### Rate limits
- GitHub App installations get 5,000 requests/hour per installation.
- Use the GraphQL API where possible (single query can pull dozens of nested objects, saving REST round trips).

## HRIS (CSV via Generic Adapter)

### Why CSV in Phase 0?
- There is no high-quality free HRIS API equivalent to Jira Cloud Free.
- Every future partner will have a different HRIS. The CSV adapter is one concrete implementation; future adapters (BambooHR, Personio, Workday, Rippling, Merge.dev) are added as needed.
- The internal People schema is the contract; CSV is the easiest way to feed it.

### CSV schema (sample)
```
employee_id,name,email,role,manager_email,team,start_date,status,github_handle,jira_account_id
E0001,Priya Shah,priya.shah@example.com,Senior Engineer,carlos.ruiz@example.com,Payments,2022-04-11,active,priyashah,5f4b...
E0002,Carlos Ruiz,carlos.ruiz@example.com,Engineering Manager,ana.ng@example.com,Payments,2019-01-15,active,carlos-r,8a2e...
...
```

### Upload flow
1. Admin uploads CSV via React UI (`/admin/integrations/hris`).
2. FastAPI validates the file (column names, types, required fields, manager-email references resolve, no duplicates on `employee_id`).
3. Validated CSV lands in `s3://companybrain-phase0-raw/hris/{date}/{run_id}.csv`.
4. S3 trigger fires the `hris-csv-ingester` Lambda.
5. Lambda upserts rows into `people`. Departed employees are flagged `status='departed'` rather than deleted (audit trail).

### Future adapters
When we add BambooHR, the steps are:
1. Create `backend/app/integrations/bamboohr/` with the `SourceAdapter` Protocol.
2. Add `ingesters/bamboohr/handler.py`.
3. Add a new EventBridge schedule.
4. Update the admin UI to allow configuring it.

No changes to the schema, the See dashboard, or anything else. That's the point of the adapter pattern.

## Anthropic Claude

Not an "integration" in the ingestion sense, but listed here for completeness because it's an external dependency.

- Use the official `anthropic` Python SDK.
- API key in Secrets Manager (`companybrain/phase0/anthropic/api-key`).
- All calls through `app/inference/llm_client.py`. See `@docs/inference.md`.
- **No Bedrock in Phase 0.** Direct Anthropic API is simpler and one less integration to set up. Bedrock is on the Phase 1 list if a partner requires it.

## Webhooks (Phase 0 Posture)

Phase 0 uses **polling-only** for all sources. Webhooks add complexity (public endpoints, signature verification, replay handling) that doesn't earn its keep with 0 external users. Phase 1 adds webhooks as the primary path with polling as a backstop.

## Testing Integrations

- **Unit tests:** mock the source API at the HTTP boundary using `respx` (httpx mocking).
- **Integration tests:** the team's real Jira/GitHub workspaces. **No automated CI runs against real APIs** — those tests are manual checkpoints, not gated by PRs.
- **Fixtures:** save sanitized real responses to `tests/fixtures/{source}/` for repeatable replay.
