# 0001. Bootstrap Phase 0 with a constrained scope and timeline

Date: 2026-05-25
Status: Accepted

## Context

Company Brain is a new product targeting tech executives (CTOs, CIOs, VPs of Technology). The founding team is 2–4 people, bootstrap-funded, with a 12-month plan to reach 3–5 design partners on a working internal alpha and a security-credible Phase 2.

The original instinct was to build "all four capabilities" (Initiative tracking, ad-hoc question answering, knowledge risk surfacing, exec briefings) plus "full security" plus "minimal cost" plus "partners from month 1" — a combination that does not coexist in any realistic plan.

## Decision

We commit to a three-phase build:

- **Phase 0 (Months 1–2):** internal alpha, founding team only, AWS region `ca-central-1`, monthly cost target $210–$280, lean security (no SOC 2 prep, no WAF, no GuardDuty), but architectural primitives in place (audit log, `org_id` on every org table, Secrets Manager, OIDC CI/CD, OpenTelemetry from day one).
- **Phase 1 (Months 3–6):** harden security, onboard first 1–2 design partners under a Design Partner Agreement (no payment, deep feedback).
- **Phase 2 (Months 7–12):** 3–5 design partners, SOC 2 Type 1 audit in progress, all four capabilities at partner-grade quality.

Within Phase 0, all four capabilities must show end-to-end (per founder requirement) but with rough edges accepted. The "AI infers structure from operational data" capability is treated as the highest-risk component and gets dedicated time in Weeks 5–6.

We also commit to:
- Single-tenant in Phase 0, but every org-scoped table carries `org_id` from day one.
- Per-seat SaaS pricing (decided in concept phase, not yet billed).
- Same product across company sizes (Series C through Fortune 500), positioned on use case rather than segment.

## Consequences

**Positive:**
- Cost ceiling holds; bootstrap runway preserved.
- Two months of head-down build without external user pressure.
- Architecture is partner-ready after Phase 1 hardening with no schema migrations.
- The audit log and `org_id` columns are "free" to add now and expensive to retrofit later.

**Negative:**
- No external validation until Month 3. Assumptions about partner needs are untested in Phase 0.
- Four-capability Phase 0 is ambitious for 2–4 people in 8 weeks; slippage into Weeks 9–10 is anticipated and acceptable.
- Anthropic API spend is the largest variable in the monthly bill; cost discipline is mandatory from Week 5 onward.

**Trade-offs not taken:**
- We did not take the "partners from month 1" path because the security work required to accept partner data would have pushed AWS spend to $700+/mo and we'd have spent Phase 0 fielding security questionnaires instead of building.
- We did not narrow to a single capability for Phase 0 because the founder's call was that all four are needed to make the product story coherent for design-partner conversations starting in Month 3.
