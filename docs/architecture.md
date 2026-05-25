# Architecture

System architecture for Company Brain Phase 0. Read this when working on AWS services, deployment, or anything infrastructure-shaped.

> **Operating model:** Phase 0 runs as a pure-ephemeral AWS stack — `make up` to provision, `make down` to destroy. See ADR [0002 — ephemeral AWS stack](decisions/0002-ephemeral-aws-stack.md) and the [Throughlin_TFE](https://github.com/kanjilalanirban/Throughlin_TFE) repo for lifecycle mechanics. Everything below describes the stack **while it is up**.

## Component Diagram (Logical)

```
External sources                  AWS ca-central-1   (ephemeral — destroyed on teardown)
─────────────────                 ──────────────────────────────────────────
  Jira Cloud      ─┐
                   │              ┌─────────────────────────────────┐
  GitHub (App)    ─┼─► HTTPS ────►│  Ingestion Lambdas              │
                   │              │  (one per source, scheduled     │
  HRIS CSV upload ─┘              │   via EventBridge)              │
                                  └────────┬───────────┬────────────┘
                                           │ raw       │ normalized
                                           ▼           ▼
                                       ┌────────┐  ┌────────────────┐
                                       │   S3   │  │ RDS Postgres   │
                                       │  raw   │  │ (4 primitives  │
                                       │ bucket │  │  + pgvector)   │
                                       └────────┘  └──────┬─────────┘
                                                          │
                                  ┌───────────────────────┴────────┐
                                  │  FastAPI on ECS Fargate        │
                                  │  (1 task behind ALB, HTTP)     │
                                  │                                │
                                  │  ┌──────────────────────────┐  │
                                  │  │ /api/ask  /api/see       │  │
                                  │  │ /api/brief  /api/admin   │  │
                                  │  └──────────────────────────┘  │
                                  └──────┬─────────────────┬───────┘
                                         │                 │
                                         ▼                 ▼
Anthropic API ◄─────── HTTPS ──── Claude calls       Cognito (auth)
                                         ▲
                                         │
                       ┌─────────────────┴───────────┐
                       │ React frontend              │
                       │  - dev: localhost:5173      │
                       │  - deployed: S3 bucket URL  │
                       │    (no CloudFront, no       │
                       │     custom domain)          │
                       └─────────────────────────────┘

Always-on (bootstrap):  ECR (container images), Secrets Manager (containers + values),
                        IAM Identity Center, OIDC provider, TF state bucket + lock.
                        Referenced by the ephemeral stack at bring-up.

Supporting (ephemeral): CloudWatch Logs, X-Ray. Logs and traces die on teardown.
```

## AWS Services and Their Roles

`Lifecycle` column: **bootstrap** = always-on, never destroyed; **ephemeral** = exists only while the stack is up.

| Service | Role | Lifecycle | Phase 0 config |
|---------|------|-----------|----------------|
| **VPC** | Network isolation | ephemeral | 1 VPC, 2 AZs (subnets only — compute single-AZ), 1 NAT Gateway |
| **ECS Fargate** | Backend API hosting | ephemeral | 1 task, 0.5 vCPU / 1 GB, no auto-scaling |
| **ALB** | HTTP termination, routing to Fargate | ephemeral | Public subnet, **HTTP only** (no TLS in Phase 0 — no domain, no ACM cert) |
| **RDS PostgreSQL 16** | Primary data store | ephemeral | `db.t4g.micro`, 20 GB gp3, single-AZ, pgvector enabled. **DB is reseeded on every `make up`.** |
| **Lambda** | Ingestion + scheduled jobs | ephemeral | One function per source + normalization function |
| **EventBridge** | Schedules ingestion runs | ephemeral | Jira/GitHub every 30 min while stack is up; HRIS daily (rarely fires given short sessions) |
| **S3 (raw + frontend)** | Raw ingest data, frontend bundle | ephemeral | Wiped on teardown. Frontend bucket served via website endpoint (no CloudFront). |
| **Cognito** | User auth | ephemeral | User pool, username/password + MFA. **User accounts are recreated on every `make up`** (seeded with the team's accounts). |
| **CloudWatch** | Logs + metrics + alarms | ephemeral | INFO retention default; log groups deleted with the stack |
| **X-Ray** | Distributed traces | ephemeral | Via ADOT |
| **Secrets Manager** | Secret containers (Anthropic key, OAuth secrets, RDS creds) | **bootstrap** (containers) + ephemeral (values populated by `make up` where appropriate) | Values are populated out-of-band so they never live in Terraform state |
| **ECR** | Container images (backend + each ingester) | **bootstrap** | Images survive teardown; ephemeral Fargate pulls `latest` at bring-up |
| **IAM Identity Center** | Team access | **bootstrap** | MFA enforced, no IAM users for humans |
| **GitHub OIDC provider** | CI auth | **bootstrap** | One-time configured; CI roles trust it |
| **TF state bucket + lock table** | Terraform backend | **bootstrap** | `companybrain-tf-state` (S3 versioned) + `companybrain-tf-locks` (DynamoDB) |

### Not in Phase 0

- **Route 53** — no custom domain.
- **ACM** — no TLS certs needed without a domain.
- **CloudFront** — frontend served directly from S3 bucket URL.
- **CloudTrail dedicated audit trail** — the default account-level trail is sufficient for Phase 0 (no compliance audience). A dedicated multi-region trail is on the Phase 1 list.

## Deployment Topology

- **Single AWS account** for Phase 0, inside AWS Organizations so adding a separate `prod` account in Phase 1 is a config change.
- **One environment**: `phase0`. When Phase 1 begins, `phase0` becomes `dev` and `prod` is provisioned alongside it.
- **One region**: `ca-central-1`. With no CloudFront in Phase 0, there are no resources outside this region.
- **No persistent application URL.** Each `make up` produces a new ALB DNS name and a new frontend S3 URL. Both are published to SSM Parameter Store on bring-up and printed at the end of `make up`.

## Request Flow Examples

### "Ask" request
1. User opens the frontend (S3 URL or local Vite); React calls `POST /api/ask` against the current ALB DNS (read from SSM at app build time, or set as a Vite env var for local dev).
2. ALB forwards to FastAPI on Fargate over plain HTTP (Phase 0; TLS in Phase 1).
3. FastAPI validates the Cognito JWT, logs to `audit_log` table.
4. FastAPI calls `app/inference/retrieval.py` → pgvector search + structured filters → returns top-K signals.
5. FastAPI calls `app/inference/llm_client.py` with the retrieved context.
6. `llm_client.py` calls Claude via the official Anthropic SDK (model from config).
7. Response streamed back to the frontend.
8. OTel spans recorded for retrieval, LLM call (with tokens, cost), and total request latency. These spans die on teardown — export if you need them long-term.

### Jira ingestion run (while stack is up)
1. EventBridge triggers `jira-ingester` Lambda on its schedule.
2. Lambda fetches Jira OAuth token from Secrets Manager.
3. Lambda paginates through Jira REST API v3.
4. Raw JSON written to `s3://companybrain-phase0-raw-{stack-id}/jira/{date}/{run_id}.json`.
5. S3 PutObject event triggers the `normalizer` Lambda.
6. Normalizer maps raw JSON to the four-primitives schema, upserts into Postgres.
7. `ingestion_runs` row written.
8. Embedding pipeline updates pgvector embeddings.

**Note:** because the stack is ephemeral, the bucket name includes a per-stack suffix to avoid name collisions across rapid up/down cycles. The current name is published to SSM at `/companybrain/phase0/s3/raw_bucket`.

## Networking

- **VPC CIDR:** `10.20.0.0/16`.
- **Public subnets:** `10.20.0.0/24`, `10.20.1.0/24` (one per AZ; host ALB and NAT GW).
- **Private subnets:** `10.20.10.0/24`, `10.20.11.0/24` (one per AZ; host Fargate, Lambda, RDS).
- **Internet access:**
  - Inbound: only via ALB (port 80 → Fargate; HTTP in Phase 0).
  - Outbound: Lambda and Fargate go through NAT Gateway for external API calls (Anthropic, Jira, GitHub).
- **Security groups:** strict least-privilege. ALB → Fargate, Fargate → RDS, Lambda → external APIs. Document each SG in `infra/modules/vpc/security_groups.tf`.

## Cross-Repo Seam (recap)

This repo (the app) **never runs Terraform**. It reads infra-published outputs from SSM Parameter Store at deploy time, and secret values from AWS Secrets Manager at app startup. Standard parameter paths are listed in [Throughlin_TFE/docs/infrastructure.md](https://github.com/kanjilalanirban/Throughlin_TFE/blob/main/docs/infrastructure.md).

## What's Deferred (Don't Build in Phase 0)

These are anticipated by the architecture but not implemented:
- Custom domain, ACM, CloudFront, TLS on the API path
- KMS customer-managed keys
- WAF, GuardDuty, Security Hub, Config
- Multi-AZ RDS, read replicas
- VPC Flow Logs
- SSO/SAML via Cognito
- Cross-region snapshot replication
- Production/staging account separation
- Persistent audit log (current table is reseeded each session)

See `docs/security.md` for the full Phase 0 → Phase 1 hardening checklist.

## Cost Discipline

The single largest variable cost is **Anthropic API spend**. Track tokens-per-feature in OTel and review weekly.

In the ephemeral model, AWS infrastructure cost is **time-based**: NAT Gateway, RDS, and Fargate are billed by the hour the stack is up, not by the month. A working day with the stack live costs ~$1-3 in AWS infra; an idle week costs near zero. Total monthly target is ~$30-75 all-in (mostly Anthropic; AWS is a rounding error if we're disciplined about `make down`).

See [Throughlin_TFE/docs/infrastructure.md](https://github.com/kanjilalanirban/Throughlin_TFE/blob/main/docs/infrastructure.md) for the full cost-discipline section including the forgotten-stack alarm.
