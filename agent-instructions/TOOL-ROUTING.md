# Tool Routing

> Cheapest tool that can answer the question. Never run all tools by default.

## Decision Table
| Question / situation | Use | Do not |
|---|---|---|
| Where is X defined/used? | `ctx_search` → sandbox grep (`ctx_execute`) | Read whole files |
| What depends on X? What breaks if I change it? How do A and B connect? | `graphify query` / `path` | Grep chains |
| First time in an unfamiliar subsystem | `graphify query` (global), then `ctx_search` | Open many files |
| Output may exceed ~20 lines (tests, logs, JSON, diffs) | `ctx_execute` / `ctx_execute_file` | Dump raw output |
| 3+ independent read-only commands | `ctx_batch_execute` | Sequential single calls |
| External docs / URL | `ctx_fetch_and_index` → `ctx_search` | curl/wget raw |
| Requirement ambiguous | Matt Pocock grilling/spec | Guess business rules |
| Hard bug, cause unknown | Matt Pocock diagnosis | Trial-and-error edits |
| New logic with testable behavior | Matt Pocock TDD | — |
| UI change meeting the browser gate | Impeccable + browser | Screenshots for logic-only changes |
| Exact edit | `Read` target range → `Edit` | Broad find/replace |
| Code finished | `graphify update .` | Per-edit updates |

## Cost Ladder (go up only if the lower rung is insufficient)
1. Already in context / memory (`ctx_search timeline`)
2. `ctx_search` over indexed content
3. Sandbox grep / `ctx_execute_file`
4. `graphify query --budget 1500`
5. Native `Read` of an exact range
6. Matt skills / Impeccable / browser

## Graphify (CLI)
Graph lives in `graphify-out/` (`graph.json`, `GRAPH_REPORT.md`). Run all commands through
the sandbox (`ctx_execute`, shell) and return only the relevant nodes/files.

| Purpose | Command |
|---|---|
| Global/architecture question | `graphify query "<question>" --budget 1500` |
| Trace a flow / call chain | `graphify query "<question>" --dfs --budget 1500` |
| How are A and B connected | `graphify path "A" "B"` |
| Everything about one node | `graphify explain "X"` |
| Refresh graph after code changes | `graphify update .` |

### When to QUERY
- Global exploration, impact analysis, unfamiliar subsystem, unclear ownership, non-local consequences.
- NOT for single-file/local work or "where is symbol X" (use `ctx_search` / grep).
- Always pass `--budget` (≤ 1500) so output stays small. Start broad, then narrow with
  `path`/`explain`. Max 3 graphify calls per question; if still unclear, switch to Matt grilling.
- First time per session: `ctx_index` the head of `GRAPH_REPORT.md` (god nodes, communities),
  then use `ctx_search` on it. Never paste the whole report into context.
- Graph output is INFERENCE: confirm the file/symbol with grep before editing.

### When to UPDATE (mandatory)
- After code changes are FINAL (edits done and verification passed), run `graphify update .` ONCE.
  Not after every edit. Skip only if no source file changed (docs-only / read-only task).
- Also run it before a Graphify query if the working tree changed since the last update
  (e.g. after a branch switch or large merge) and the query depends on the changed code.
- Run it in the sandbox; report only success/failure. If it fails: report it as a
  limitation in Notes, do not retry in a loop.
- If `graphify-out/` does not exist: for S tasks skip Graphify; for L tasks run
  `graphify update .` once to build it, else fall back to `ctx_search`.
- If git hooks are installed (`graphify hook install`: post-commit/post-checkout run update),
  the manual update is still done when uncommitted changes will be queried later.

## Verification of tool availability
At session start, note which tools actually exist. Missing tool → use the fallback in
AGENTS.md §4; do not retry a failing tool repeatedly.
