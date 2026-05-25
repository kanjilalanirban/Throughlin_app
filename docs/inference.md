# Inference Layer

The hardest part of Phase 0. Read this when working on prompts, retrieval, scoring, or eval. The inference layer turns raw signals into the four primitives.

## The Four Inference Tasks

| Task | What it does | When it runs |
|------|--------------|--------------|
| **Initiative inference** | Cluster signals; propose initiatives with evidence | Scheduled (daily) + on-demand |
| **Decision validity** | Check whether a recorded decision is still defensible | Scheduled (weekly) per decision |
| **Ownership inference** | Map signals to people; identify real owners | Continuous, after every ingestion |
| **Concentration scoring** | Compute knowledge concentration per person/initiative | After ownership inference completes |

## Module Layout

```
backend/app/inference/
├── __init__.py
├── llm_client.py       # The ONLY place that calls Anthropic
├── prompts/            # Versioned prompt templates
│   ├── initiative_inference.md
│   ├── decision_validity.md
│   ├── ownership_inference.md
│   └── system.md       # Shared system prompt
├── retrieval.py        # pgvector search + structured filters
├── embedding.py        # Embedding pipeline (signal → vector)
├── pipelines/
│   ├── infer_initiatives.py
│   ├── validate_decisions.py
│   └── compute_ownership.py
├── scoring.py          # Knowledge concentration math
└── evals/              # Eval harness + golden cases
    ├── harness.py
    ├── cases/
    └── README.md
```

## LLM Client Conventions

**All Claude calls go through `llm_client.py`.** No exceptions. The client:
- Loads the model name from `app/core/config.py` (don't hardcode).
- Wraps every call in an OpenTelemetry span with attributes:
  - `llm.model`
  - `llm.input_tokens`, `llm.output_tokens`
  - `llm.latency_ms`
  - `llm.cost_estimate_usd`
  - `llm.use_case` (e.g., `initiative_inference`, `ask_query`)
- Implements retry with exponential backoff on `RateLimitError` and `APIConnectionError`.
- Streams responses where the caller requests streaming (Ask interface).
- Never logs prompts or completions to CloudWatch (audit log only stores metadata, not content).

## Model Selection

We have two tiers in Phase 0:
- **Sonnet (current Claude Sonnet model)** — for reasoning-heavy tasks: initiative inference, decision validity, Ask queries.
- **Haiku (current Claude Haiku model)** — for high-volume cheap tasks: signal classification, simple labeling, embedding-adjacent operations.

The exact model strings live in `app/core/config.py`. **Don't pin a specific dated model in code**; let configuration drive it so we can upgrade easily.

## Prompts Are Code

Treat prompts as first-class code:
- Live in `app/inference/prompts/` as Markdown files.
- Versioned with the repo. PR review covers prompt changes.
- Loaded at startup, not embedded as Python strings.
- Use Jinja2-style placeholders (`{{variable}}`) for parameterization, rendered via the `jinja2` library — never `.format()` (LLM outputs containing `{}` will break it).

### Prompt Structure (Pattern)

Each task-specific prompt follows this skeleton:

```markdown
# Role
You are a strategic technology analyst supporting a tech executive...

# Task
[Specific task description]

# Inputs
You are given:
- {{context_block_1}}
- {{context_block_2}}

# Output Format
Return JSON matching this schema:
{
  ...
}

# Constraints
- [Specific constraints]
- [Edge case handling]

# Examples
[1–3 worked examples]
```

## Retrieval

`retrieval.py` exposes one main function:

```python
async def retrieve_relevant_signals(
    query: str,
    org_id: UUID,
    filters: SignalFilters | None = None,
    top_k: int = 30,
) -> list[Signal]:
    ...
```

It combines:
1. **Vector search** (pgvector cosine similarity on the query embedding).
2. **Structured filters** (org_id always, plus optional source/date-range/initiative scope).
3. **Recency boost** (signals from the last 14 days get a small score uplift).

The top-K is generous (default 30) because Claude can absorb large context; we trim with relevance scoring rather than aggressive top-K.

## Initiative Inference Pipeline

High-level flow:

1. Gather all signals from the last N days (default 30) that aren't already linked to a confirmed initiative.
2. Cluster them by simple heuristics (same Jira epic, same repo, same set of people).
3. For each cluster, render the initiative-inference prompt with the cluster's signals as context.
4. Claude returns a structured JSON proposal with `name`, `description`, `evidence` (which signals supported the call), `confidence_score`, and `proposed_owner_id`.
5. Persist as a row in `initiatives` with `status='proposed'`. The user confirms (sets `confirmed_by_user_at`) or rejects from the See dashboard.

## Decision Validity Pipeline

For each decision with `still_valid IS NULL OR last_validated_at < now() - interval '7 days'`:
1. Retrieve signals from after `decided_at` that mention the initiative.
2. Render the decision-validity prompt.
3. Claude returns: `still_valid` (bool), `confidence`, `evidence_against` (list).
4. Update the row. Add `audit_log` entry.

## Ownership and Concentration Scoring

This is the **differentiator** capability. Most products don't do this; we do.

### Ownership inference
For each initiative, infer the real owner from:
- Named `owner_id` (declared) — weight 1.0 if present.
- Commit share to linked repos.
- Jira issue assignment share.
- Reviewer activity (PR reviews, Jira comments).

Output: a `person_initiative.ownership_strength` per person, normalized so the column sums to ≤ 1 per initiative.

### Concentration score
For each `(person, initiative)`:

```
concentration = (
    0.5 * person_ownership_strength
  + 0.3 * (1 - share_of_second_highest_contributor)
  + 0.2 * (1 if person_is_only_committer else 0)
)
```

A score ≥ 0.80 means the initiative has a **single point of failure**. The See dashboard surfaces this as a red flag.

This is not the final formula — expect to tune it with real data in weeks 5–6. **All scoring logic lives in `app/inference/scoring.py`; do not scatter it across other modules.**

## Evals

`app/inference/evals/` contains a small harness that:
- Loads "golden case" inputs (10–20 hand-crafted scenarios).
- Runs the prompt under test against each.
- Compares output to expected output using rubric scoring (LLM-as-judge for fuzzy criteria, exact match for structural).
- Outputs a pass/fail report.

**Rule:** Any non-trivial prompt change must run the eval harness and report results in the PR description. We don't merge prompt changes blind.

Cases live in `evals/cases/` as JSON files. Add new ones as the team encounters edge cases in production.

## Cost Discipline

The cost reality: Claude calls are the biggest variable in the AWS bill.

- Use Haiku where reasoning depth isn't needed.
- Cache structured outputs aggressively. Initiative-inference results don't need to be recomputed every hour — daily is fine.
- Streaming is required for the Ask interface. For batch jobs, don't stream.
- Track per-feature token spend via OTel attributes (`llm.use_case`). Build a weekly cost-by-feature dashboard.
- If a single use case crosses 20% of monthly Claude spend, audit the prompt for bloat.
