# Context Mode

Goal: raw output never floods the context window. Process in the sandbox, return the answer.

## Routing
1. `ctx_batch_execute` — 3+ related commands (opt-in `concurrency: 1-8` for I/O-bound
   work; never parallelize stateful writes or CPU-heavy commands)
2. `ctx_execute` — programmatic analysis/filtering/counting
3. `ctx_execute_file` — analyze a file without loading it
4. `ctx_search` — retrieval; pass multiple questions in ONE array call
5. `ctx_fetch_and_index` → `ctx_search` — web/docs (no direct curl/wget)
6. `ctx_index` — save reusable knowledge (project map, verify commands, handoff)
7. `Read` — only when exact bytes are needed for an edit

## Recipes (return derived results only)
| Need | Sandbox does | Return |
|---|---|---|
| Run tests | run, parse output | pass/fail counts + failing test names + first error lines |
| Lint/typecheck | run, group by rule/file | counts + top offenders + the errors in changed files |
| Find usages | grep with `-n` | file:line list, capped (top ~15) |
| Large JSON/CSV | parse | schema + counts + the relevant records only |
| Git state | `git status -s`, `git diff --stat` | summary; per-file diff only for files to review |
| Dependency check | read manifest | only the relevant package/version |
| Build log | run | exit code + first error block |

## Rules
- Cap results (top N). If cut, state that it was cut.
- Index stable, reusable facts once (repo structure, verify commands, key decisions);
  query them later instead of re-discovering.
- On resume: `ctx_search(sort: "timeline")`; zero results → fresh session.
- No maintenance commands (stats/doctor/upgrade/purge) without a reason.
