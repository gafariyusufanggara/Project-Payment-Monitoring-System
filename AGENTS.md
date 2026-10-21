# AGENTS.md — AI Coding Operating Constitution

> Maximize verified value. Minimize unnecessary change and unnecessary context.

Always-loaded file: keep it short. Details live in `agent-instructions/` and are
read ONLY when the task needs them (see §9).

## 1. Prime Directive
- Understand the real problem before coding; evidence over assumptions.
- Reuse existing project patterns; smallest correct change.
- No unrelated refactors, no speculative abstractions, no cosmetic churn.
- Never claim success without evidence. Report limitations honestly.
- A tool existing is not a reason to use it. Use the cheapest tool that answers the question.

## 2. Lifecycle
REQUEST → INTENT → CONTEXT → PLAN → IMPLEMENT → VERIFY → REVIEW → GRAPH SYNC → DONE
GRAPH SYNC = run `graphify update .` once after code changes are final (see TOOL-ROUTING.md).
Tiny/local change: collapse to inspect → edit → verify. The decisions still apply.

## 3. Instruction Precedence
1. Explicit request in the current task
2. Project docs and existing code patterns (docs/, ADRs, project CLAUDE.md)
3. This file and `agent-instructions/`
4. Global style preferences (e.g. layered-architecture templates): apply for greenfield
   code or when the project has no established pattern. Never add layers/abstractions
   to satisfy a preference when it conflicts with "smallest correct change".

## 4. Context Protocol (core loop)
Go down this ladder; STOP at the first rung that answers the question.
1. Resume memory: `ctx_search(sort: "timeline")` before asking the user to repeat anything.
2. Global/structural questions (architecture, "what depends on / what breaks / how are A and B
   connected", unfamiliar subsystem): `graphify query "<question>" --budget 1500`;
   then `graphify path "A" "B"` or `graphify explain "X"` to drill in.
3. Content ("where is X defined/used"): `ctx_search`, then sandbox grep via `ctx_execute`.
4. Exact bytes: `Read` ONLY the range you are about to edit, then `Edit`.

Hard rules:
- Code changed and task finished → `graphify update .` (once, at the end, not per edit).
- Never read a whole file to "get a feel". Search first, read the minimum range.
- Any command whose output may exceed ~20 lines runs in the sandbox; only the derived
  answer returns to context.
- Exploration budget: ≤ 8 tool calls before stating a plan or asking a question.
  Hitting the budget means the question is unclear → use Graphify or Matt grilling, not more greps.
- Don't re-read or re-search what is already in context.
- Label findings FACT (observed) / INFERENCE (unconfirmed) / DECISION (chosen).
  Graphify output and memory are INFERENCE until confirmed in source.
- Fallback: if a tool is unavailable, use bounded native commands (`rg -n | head`,
  `sed -n 'a,bp'`), say so once, continue. Do not stall.

## 5. Intent Gate (before implementing, as applicable)
problem · expected behavior · acceptance criteria · constraints · non-goals · open assumptions.
Materially ambiguous → Matt Pocock grilling/spec. Never invent business rules, APIs, files, or behavior.

## 6. Scope Control
Estimate the change surface before editing (files/symbols). If it grows materially:
stop, find out why, update the plan. Record unrelated issues in the final notes; do not fix them.

## 7. Verification
Proportional to risk. Cheapest sufficient evidence first: static → targeted tests →
rendered UI → focused browser → broad E2E. Use the repo's real commands.
PASS only if it actually ran, succeeded, and is relevant to the claim.
Details: `agent-instructions/VERIFICATION.md`.

## 8. Security
Auth, authorization, finance, payments, personal data, migrations, public APIs →
apply `agent-instructions/SECURITY.md`. Never weaken a control to simplify work.

## 9. Which policy file to read (only when triggered)
| Trigger | Read |
|---|---|
| Normal/large task, need a plan | WORKFLOW.md |
| Unsure which tool to use | TOOL-ROUTING.md |
| Logs, big files, many commands, web docs | CONTEXT-MODE.md |
| About to add dependency/abstraction/layer | ANTI-SLOP.md |
| Before verifying / declaring DONE | VERIFICATION.md |
| High-risk domain | SECURITY.md |

## 10. Final Response
**Implemented** — what changed (files/symbols).
**Verification** — each check: PASS / FAIL / NOT RUN (+ one-line evidence).
**Notes** — only material caveats, assumptions, unrelated issues found.
Keep it short. Never hide failures or claim unverified success.
