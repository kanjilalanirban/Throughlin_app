# Security

Read this when working on auth, secrets, audit logging, or anything tenant-isolation-shaped. Phase 0 has no external users, so the level is dialed down — but the **primitives are in the right place** so Phase 1 hardening is config, not redesign.

> **Operating model:** Phase 0 runs as a pure-ephemeral AWS stack (see ADR [0002](decisions/0002-ephemeral-aws-stack.md)). Several "security" controls that look weaker than usual — no TLS on the API path, audit log reset every session, no dedicated CloudTrail bucket — are direct consequences of the operating model and are explicitly justified below. Phase 1 reverses all of them.

## Phase 0 Security Posture (Lean but Correct)

### Identity & Access
- Root user secured with hardware MFA. Credentials sealed after initial setup.
- IAM Identity Center for team access. MFA enforced on every team account.
- **No long-lived IAM users for humans.** None.
- **No long-lived access keys anywhere.** GitHub Actions auths via OIDC.
- Service-to-service auth: IAM roles attached to ECS tasks and Lambda functions; no shared credentials.

### Data Protection
- **Encryption at rest**: RDS storage encryption enabled, S3 default encryption (SSE-S3). KMS customer-managed keys are deferred to Phase 1.
- **Encryption in transit**:
  - RDS forces SSL (Fargate → RDS over TLS).
  - Backend → external APIs (Anthropic, Jira, GitHub): TLS 1.2+ enforced.
  - **Client → API path is plain HTTP in Phase 0.** No domain, no ACM cert, no CloudFront. Acceptable because: (a) the only clients are the founding team's browsers/CLIs, (b) the only data is seeded test data, (c) the ALB DNS rotates every `make up` so there's no stable target to attack. Phase 1 adds a domain + ACM + HTTPS-only listener.
- **Secrets**: AWS Secrets Manager only. Never in env vars, Terraform state, code, or GitHub Secrets.

### Network
- RDS in private subnets, **never publicly accessible**.
- Fargate tasks in private subnets, outbound via NAT Gateway only.
- Security groups follow least-privilege: ALB → Fargate only, Fargate → RDS only, Lambda → external APIs only.

### Application
- **Audit log every read and write of organizational data.** No exceptions. Use the `audit_logged` decorator from `app/core/audit.py`. The `audit_log` table lives in RDS, so **it resets on every `make down`** — acceptable in Phase 0 because there is no compliance audience for the log; the discipline of writing it is what we're preserving, not the historical record. Phase 1 moves audit log to a long-lived store (DynamoDB or S3+Athena) as part of multi-tenancy hardening.
- Cognito JWT validation on every API request (except `/health`).
- All requests scoped by `org_id`. Use the `TenantScopedQuery` mixin in `app/core/tenant.py`. **Never write a raw SQL query that omits `org_id`.**
- Input validation via Pydantic v2 on every API boundary.
- No raw SQL string interpolation. Always parameterized queries via SQLAlchemy.

### Operational
- **CloudTrail**: account-default trail only in Phase 0. A dedicated multi-region trail with object-lock retention is on the Phase 1 list (relevant when there are partners and compliance evidence to preserve).
- CloudWatch alarms on unusual login patterns (failed Cognito auth bursts), IAM changes, security group modifications — meaningful only while the stack is up; auto-cleaned on teardown.
- Billing alarms at $50, $100, $200 (matched to the ephemeral cost shape).
- **Forgotten-stack alarm**: fires if ephemeral resources have existed for > 24 hours — most likely cause is someone forgot to `make down`, which is a cost issue, not strictly a security issue, but flagged in the same place.

## What's Deferred to Phase 1

These are anticipated by the architecture but **not** in Phase 0. Don't build them unless explicitly asked.

- Custom domain + ACM + CloudFront + HTTPS-only listener on the ALB.
- Dedicated CloudTrail multi-region trail with object-lock.
- KMS customer-managed keys (CMKs) for RDS and S3.
- AWS WAF on the ALB (and on CloudFront once it exists).
- GuardDuty, Security Hub, Config.
- VPC Flow Logs.
- Multi-AZ RDS, cross-region snapshot replication.
- SSO/SAML support in Cognito.
- Persistent audit log store (outside ephemeral RDS).
- Always-on stack — Phase 1 will need at least some "always-on" surface (a permanent ingestion path so partner data can flow continuously); the ephemeral model is Phase 0 only.
- Formal vendor risk paperwork (DPA, MSA templates, security questionnaire pre-answered).
- SOC 2 Type 1 audit preparation.

## Phase 0 → Phase 1 Hardening Checklist

Before any external user accesses the platform in Phase 1, the following must be in place:

- [ ] Provision a custom domain in Route53, ACM cert, CloudFront for the frontend, HTTPS-only ALB listener for the API.
- [ ] Move at least the data-bearing services (RDS, S3 raw, audit log store) out of the ephemeral lifecycle into an always-on layer.
- [ ] Migrate audit log to a long-lived store (DynamoDB or S3+Athena). Retain ≥ 1 year.
- [ ] Add a dedicated CloudTrail multi-region trail to a separate S3 bucket. Object-lock retention configured.
- [ ] Enable KMS customer-managed keys for RDS and S3 (raw + artifacts). Rotate annually.
- [ ] Add WAF managed rule groups to CloudFront and the ALB.
- [ ] Enable GuardDuty (account-wide), Security Hub (with AWS Foundational Security Best Practices), and Config.
- [ ] Enable VPC Flow Logs to CloudWatch (14-day retention).
- [ ] Switch RDS to Multi-AZ. Configure cross-region snapshot replication.
- [ ] Add SAML/OIDC SSO support to Cognito for partner organizations.
- [ ] Implement formal multi-tenancy: Postgres row-level security on `org_id`. Every API call scoped by `org_id` at the DB layer, not just the application layer.
- [ ] Draft and publish: DPA template, MSA template, sub-processor list, security questionnaire (SIG Lite or CAIQ pre-answered), incident response runbook.
- [ ] Engage a SOC 2 audit firm. Type 1 timeline: 3–6 months.

## Specific Coding Rules That Touch Security

### Never log sensitive content
- Audit log entries store **metadata** (who, what, when), never query content or response content.
- Application logs (`logger.info(...)`) must not contain prompts, completions, PII, or secrets.
- Use structured logging; mark fields that could contain sensitive data with explicit redaction.

### Audit the right things
The `audit_log` table captures:
- Every successful and failed API request to `/api/ask`, `/api/see/**`, `/api/brief/**`, `/api/admin/**`.
- Every ingestion run start/end (already covered by `ingestion_runs`, no double-log).
- Every change to a primitive (initiative confirmed, decision marked invalid, person mapping overridden).
- Every secret retrieval from Secrets Manager (built into AWS, no app work needed — read via CloudTrail).

What's **not** in the audit log: low-value events like static-asset fetches, health checks, or successful JWT validations on read-only endpoints (those generate noise, not signal).

### Tenant isolation in code
```python
# WRONG — missing org_id
result = await session.execute(select(Initiative).where(Initiative.id == initiative_id))

# RIGHT — always scope by current org
result = await session.execute(
    select(Initiative).where(
        Initiative.id == initiative_id,
        Initiative.org_id == current_org_id,
    )
)
```

In Phase 0 with a single tenant, this looks redundant. **Do it anyway.** Phase 1 multi-tenancy is built on the assumption that every query has this filter.

### Webhook signature verification
Phase 0 doesn't use webhooks, but when Phase 1 adds them:
- Always verify HMAC signatures using the per-source shared secret from Secrets Manager.
- Reject requests with missing or invalid signatures with 401, not 200 (don't leak that the endpoint exists).
- Implement replay protection via timestamp + nonce.

### Error messages
- **Never return raw exception messages to clients.** Wrap exceptions in `app/core/errors.py` and return generic messages with a correlation ID for support.
- Stack traces go to CloudWatch only, never to the response body.

## Anthropic API Key Handling

- Stored in Secrets Manager under `companybrain/phase0/anthropic/api-key`.
- Loaded once at app startup via `app/core/config.py`, never re-fetched per request.
- For local development only, may live in `backend/.env` (gitignored). **Never** committed.
- Rotation: manually rotated quarterly during Phase 0; automated rotation considered in Phase 1.

## Incident Response (Phase 0)

Phase 0 has minimal IR posture because there are no external users. **The simplest IR action available is `make down`** — the entire ephemeral surface vanishes. Use it liberally if anything looks wrong; the cost of an unscheduled teardown is ~zero.

The runbook (`docs/runbook.md`) covers:
- How to rotate Anthropic API keys if leaked (Secrets Manager value update; survives `make up`/`down`).
- How to revoke Jira/GitHub OAuth grants.
- How to invalidate Cognito sessions (or just `make down` to destroy the entire user pool — fastest in Phase 0).
- How to handle a suspected data issue: `make down`, investigate the orphaned RDS snapshot (if any), bring up fresh.
- Who to contact (the founding team — there's no on-call rotation in Phase 0).
