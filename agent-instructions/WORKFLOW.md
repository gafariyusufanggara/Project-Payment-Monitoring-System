# Workflow

## Task Sizing (decides ceremony and tool budget)
| Size | Example | Process | Exploration budget |
|---|---|---|---|
| S | typo, label, one-function fix | inspect → edit → verify | ≤ 3 calls |
| M | feature/bug in 1–3 files | intent → search → short plan → edit → targeted verify | ≤ 8 calls |
| L | cross-module, schema/API, high-risk | intent (+Matt) → `graphify query` → plan → edit → stronger verify | ≤ 15 calls, then re-plan |

## Plan Template (M/L only, ≤ 8 lines)
- Goal / acceptance criteria
- Non-goals
- Affected files/symbols (expected change surface)
- Tools to use and why
- Risks
- Verification commands

Skip the plan if it adds no decision value (S tasks).

## Rules
- Translate the request into the actual task; do not enlarge it.
- Preserve existing behavior unless the requirement changes it.
- Prefer targeted edits and established patterns.
- If scope or budget is exceeded: stop, explain, update the plan.
- After VERIFY and REVIEW, if source files changed: `graphify update .` (once), then DONE.
- Non-trivial work: before finishing, index a ≤ 10 line handoff
  (decisions, constraints, open issues) with `ctx_index` if not auto-captured.
