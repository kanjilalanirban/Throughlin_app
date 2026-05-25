# 0002. Phase 0 runs as a pure-ephemeral AWS stack

Date: 2026-05-25
Status: Accepted

## Context

Company Brain Phase 0 has no external users, no production traffic, and a 2-month head-down build window with the founding team. The original Phase 0 plan assumed an "always-on" stack at ~$210–$280/month: ECS Fargate always running, RDS always provisioned, NAT Gateway always live (~$32/mo on its own), ALB always present, CloudFront fronting the frontend.

This is wrong for our actual usage pattern. The founding team will work on the product in bursts — design sessions, demos, eval runs — not 24/7. Paying for an always-on stack between bursts is pure waste, and the "$210–$280/mo" target only holds if usage is roughly continuous.

We also do not have, and do not need, real users, real data, or a real domain in Phase 0. The seed data IS the data. There is nothing in the running stack that we would mourn losing.

## Decision

Phase 0 runs as a **pure-ephemeral AWS stack**, lifecycle-managed by the founding team:

1. **Bring up before working:** `cd Throughlin_TFE && make up` provisions the entire stack from zero. Bootstrap completes with migrations applied and seed data loaded, ready in ~10–15 minutes.
2. **Tear down immediately after:** `cd Throughlin_TFE && make down` destroys the entire stack. No idle resources, no surprise bills.
3. **Nothing in the running stack persists across teardowns.** Database state, ingested raw data, audit log, signals — all wiped. Every session starts from a known-good seeded state.

### What stays always-on (the floor)

A small permanent footprint exists to make `make up` possible at all:
- Terraform state bucket (`companybrain-tf-state`, S3, versioned)
- Terraform lock table (`companybrain-tf-locks`, DynamoDB)
- IAM Identity Center configuration and GitHub OIDC provider
- ECR repositories (so app container images survive across sessions and we don't rebuild from scratch on every `up`)

Idle cost target: **~$1–5/month.**

### What's ephemeral (everything else)

- VPC, subnets, NAT Gateway, security groups
- RDS PostgreSQL instance
- ECS Fargate service + ALB
- Lambda functions + EventBridge schedules
- Cognito user pool
- S3 raw-data bucket and frontend bucket
- CloudWatch log groups (logs are flushed on teardown; CloudTrail audit trail stays in a separately-managed S3 bucket)

Active cost target: **~$5–15 per working day.**

### What's not in Phase 0 at all (per this decision)

- No domain. No Route53 hosted zone. No ACM certs. No CloudFront. Frontend is served from the S3 bucket URL or from local Vite during development. Backend is reached via raw ALB DNS.
- No production-style CI/CD that auto-deploys on every push to main. App container images are built and pushed to ECR via CI; the running stack pulls `latest` when `make up` runs.

## Consequences

**Positive:**
- Idle cost goes from ~$210–$280/month to ~$1–5/month. Active cost is pay-per-use. Total monthly cost likely under $50 unless we're working in the stack daily.
- The team's mental model is simple: "is the stack up?" is a binary question with a single command to answer.
- Forcing every session to bring up from zero is a continuous test of our Terraform: if `make up` breaks, we notice immediately, not three months later during a real outage.
- Seeded-state-only means every demo and every eval run starts identically. No "it worked on Wednesday but not Friday because the data drifted."

**Negative:**
- ~10–15 minute wait before working. Mitigated by keeping bring-up fast (no CloudFront propagation; minimal RDS startup; ECR images pre-built).
- No persistent audit log across sessions. The `audit_log` table is wiped on teardown. **For Phase 0 this is acceptable** because audit-log requirements are partner-/compliance-driven and Phase 0 has neither. Phase 1 will move audit log to a long-lived store (DynamoDB or S3+Athena) as part of the multi-tenancy hardening checklist.
- Cannot leave a long-running ingestion job overnight; it dies on teardown. Acceptable in Phase 0 because ingestion runs are short (~minutes).
- No "permanent" demo URL we can hand to anyone. Acceptable because there's no one to hand it to in Phase 0.

**Trade-offs not taken:**
- We did not adopt a "snapshot + restore" model (snapshot RDS on teardown, restore on apply). It adds operational complexity and ~15 minutes to bring-up, and the seed data is good enough for Phase 0. Revisit in Phase 1 once design partners are sending real data we'd want to preserve.
- We did not adopt LocalStack or similar local-AWS simulation. Running against real AWS keeps the dev/prod gap honest (especially for Cognito, Secrets Manager, IAM role behavior) and the cost of doing so is now negligible.

## Supersedes / Related

- Extends ADR [0001 — bootstrap phase 0 scope](0001-bootstrap-phase-0-scope.md). 0001 set the budget target; 0002 changes the operating shape that achieves it.
- Phase 1 hardening (`docs/security.md`) will revisit always-on for partner-facing infrastructure. Until then, ephemeral is the rule.
