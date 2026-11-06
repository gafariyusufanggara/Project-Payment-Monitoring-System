# SOP — Context, Shell, Codebase Memory

Rules that keep the agent's context window small. Violating these is the most
expensive mistake available: one unrouted command can dump tens of KB.

---

## 1. Shell: always prefix with `rtk`

Every shell command goes through `rtk`. It filters output (60-90% reduction) and
passes through unchanged when it has no filter. It is safe as a pass-through, but
it is **not universal**: see the Windows limits table below — some commands do
not exist there at all.

```bash
rtk git status        rtk git diff        rtk git log
rtk find <path>       rtk read <file>     rtk grep <pattern>
rtk pytest tests/     rtk test <cmd>      rtk tsc
rtk lint              rtk npm run <script>
rtk gh pr view <n>    rtk docker ps       rtk pip list
```

Shell is Windows PowerShell 5.1, which has no `&&`. Prefer one tool call per command. Use `;` only when the next step may run after a failure:

```powershell
rtk git status; rtk git diff --stat
```

Exceptions — use the raw command:
- Debugging why a command produces unexpected output.
- `rtk proxy <cmd>` runs unfiltered but still counts usage.

### Command-line cheat sheet (pick before you type)

| Intent | Do this | Not this |
|---|---|---|
| List a directory | `rtk find <path> -maxdepth 1` | `rtk ls` (not on Windows) |
| Find files | `rtk find docs -name *.md` (scope path!) | `rtk find . -name *.md` (node_modules flood) |
| Read file to Edit | `Read` tool | `rtk read` (output lands in context, fine for small files only) |
| Read file to analyse | `ctx_execute_file(path, lang, code)` | `Read` the whole thing |
| Structured search | `rtk grep <pattern> <path>` | shell `grep` |
| JSON read | `rtk json <file.json>` | `rtk json <file.toml>` |
| Big analysis/logs | `ctx_execute` with a filter | raw `Get-Content` / `cat` |
| Fetch a web page | `ctx_fetch_and_index` then `ctx_search` | `curl` / `Invoke-WebRequest` (blocked) |

### `rtk find` rules that keep output small

- **Scope the path**: `rtk find src -name *.tsx`, not `rtk find . ...` from the
  repo root — unscoped walks print `node_modules` (200+ lines, truncated).
- Globs: `-name *.md` works in PowerShell. In bash, quote it (`-name '*.md'`) so the shell does not expand it first.
- `-maxdepth N` works: `rtk find . -maxdepth 2 -name package.json`.
- **`0 for '<pattern>'` is a valid "no match", NOT an error, and NOT proof the
  file is absent if the path is wrong.** If the path was absolute it is absent;
  if relative, verify the cwd first.
- No `-not`, `-exec`, or compound predicates.

### Working directory (cwd) — the silent failure

`ctx_execute`, `ctx_batch_execute` and plain shell calls run from the **session
working directory**, which is whatever folder opencode was started in. It is not
guaranteed to be the project root.

- In `ctx_batch_execute` commands, use **absolute paths**:
  `rtk find "C:/path/to/project/docs" -name *.md`.
- If a relative path returns `0 for '*'`, the likeliest cause is wrong cwd, not a
  missing file. Re-check with an absolute path before reporting "file missing".
- When the task spans a project, run `Set-Location <project>` once or pass
  absolute paths in every command.

### rtk limits on Windows (verified against rtk 0.40.0; bootstrap installs the current winget build)

| Do not write | Why | Write instead |
|---|---|---|
| `rtk ls <path>` | proxies native `ls`, absent on Windows | `rtk find <path> -maxdepth 1` |
| `rtk find ... -not -path ...` | rtk rejects compound predicates | scope the path: `rtk find docs ...` |
| `rtk find ... -exec ...` | same | run the action as its own command |
| `-name '*.md'` in bash | bash expands the glob before rtk sees it | quote it in bash; PowerShell passes the pattern literally |
| `rtk json pyproject.toml` | `rtk json` parses JSON only | `rtk read pyproject.toml` |

`rtk find` prints `0 for <pattern>` when nothing matches. That is a valid
result, not a failed command. Do not retry with different flags.

### If rtk or context-mode is missing

A fresh machine may not have the global layer yet. Degrade, never fake.

| Missing | Fallback | One-line notice |
|---|---|---|
| `rtk` | plain `git`, `node`, `npm`, `pytest`, ... | "rtk tidak terpasang, jalan tanpa filter." |
| `ctx_*` tools | `Read`, `Grep`, `Glob`, direct shell | "context-mode tidak aktif, baca langsung." |
| both | normal tool use, smaller batches | say once, then continue |

Announce once per session. Do not retry a missing command, do not pretend it
ran, and do not claim token savings you did not get. Install path:
`.opencode/scripts/bootstrap-windows.ps1`.

## 2. context-mode: route everything through the sandbox

Never read raw output into context when a derivation is possible.

| Situation | Wrong | Right |
|---|---|---|
| Analyze/parse/filter data | `Read` the file | `ctx_execute_file(path, lang, code)` |
| Multi-step investigation | 20 sequential shell calls | `ctx_batch_execute([{label, command}...], queries)` |
| Search across many results | `Grep` then read | `ctx_execute` with a JS filter, print counts only |
| Fetch a web page | `Invoke-WebRequest` | `ctx_fetch_and_index(url, source)` then `ctx_search` |
| Two questions about same data | two calls | one `ctx_search(queries: ["q1","q2"])` |

### Blocked constructs (do not retry)

- `curl`, `wget` in shell — intercepted.
- Inline HTTP in scripts: `fetch('http`, `requests.get(`, `requests.post(`.
- Direct web fetch into context.

### Batch and concurrency

```js
ctx_batch_execute(commands: [{label:"a", command:"..."}, ...],
                  queries: ["q1","q2"], concurrency: 5)
```

- Commands run from the **session cwd** (see §1 "Working directory"). Use
  absolute paths inside commands, or `cd <project-root>` first.
- `concurrency: 4-8` for I/O-bound work (network, `gh`, API, multi-repo reads).
- `concurrency: 1` for CPU-bound (build, test, lint) or state-sharing commands
  (ports, lock files, same-repo writes).
- Cap `gh` at 4 to stay under GitHub's rate limit.

### Artifacts go to files

Never return a report inline. Write it to a file and report
`path` + one-line description.

## 3. graphify: query the graph before grepping

If `graphify-out/graph.json` exists, treat any codebase question as a graph
query first.

```bash
graphify query "<question>"     # scoped subgraph, usually much smaller
graphify path "<A>" "<B>"       # how two things relate
graphify explain "<concept>"    # focused concept
graphify update .               # after editing code (AST only, no API cost)
```

Order of preference:
1. `graphify query` — scoped answer.
2. `graphify-out/wiki/index.md` — broad navigation.
3. `graphify-out/GRAPH_REPORT.md` — only for broad architecture review.
4. Raw `grep` / file reads — last resort, and only with `rtk grep`.

Dirty `graphify-out/` files are expected. Never skip graphify because the dir is
dirty.

## 3b. Source of truth — read in this order

1. **Project documents in `docs/`** — intent, requirements, decisions, stack.
2. **The existing code** — real patterns and conventions.
3. **Official library documentation** — only for third-party APIs.

Project documents win over upstream docs and over your assumptions. If a
document says "Next.js 15 App Router", do not propose Pages Router even though
the upstream docs still describe it.

### Project documents (`docs/`)

The contents of `docs/` vary per project. Do not assume filenames. Discover,
then read.

```js
ctx_batch_execute(commands: [
  {label:"docs-tree",  command:"rtk find docs -name *.md"},
  {label:"docs-root",  command:"rtk find . -maxdepth 1 -name *.md"}
], queries: ["requirements","stack","features","design system","decisions"])
```

The `docs` path is relative to the session cwd. If `docs-tree` returns
`0 for '*.md'`, retry once with the absolute project path before concluding that
`docs/` does not exist.

Then read what exists, cheapest first:

| Likely file | Purpose |
|---|---|
| `docs/PRD.md` | Requirements, goals, non-goals |
| `docs/STACK.md` | Chosen framework, versions, package manager |
| `docs/features/*.md` | Per-feature specs and acceptance criteria |
| `DESIGN.md` or `docs/DESIGN.md` | Locked design system (overrides Hallmark themes) |
| `docs/adr/*.md` | Decisions and rationale |
| anything else in `docs/` | Read it if its name maps to the task |

Rules:

- If `docs/` is large, list it first and read only the files relevant to the
  task. Never dump the whole folder into context.
- Read to **understand**, so use `ctx_execute_file` for anything over ~200 lines.
- If `docs/` does not exist, say so once, then continue.
- Never edit these documents unless asked. If the code contradicts a document,
  report the conflict rather than silently picking a side.
- Quote the requirement you are implementing.

### External library documentation (no docs MCP installed)

For a third-party API that changes fast (Next.js, React, Tailwind, Prisma,
Supabase, any framework):

```
ctx_fetch_and_index(<official docs URL>, source: "docs-<lib>")
ctx_search(queries: [...], source: "docs-<lib>")
```

If the URL is unknown: `tavily_tavily_search` first, then fetch the official URL
that comes back. Official docs only, not blogs or remembered snippets.

**Never write a library API call you have not verified in this session.** If no
documentation can be fetched, say so and stop. Guessing an API is a reportable
failure, not a shortcut.

### graphify vs documentation

| Question | Tool |
|---|---|
| "Where is auth verified in this repo?" | `graphify` |
| "Who calls this function?" | `graphify` |
| "What does our own code do?" | `graphify` |
| "What is the current API of library X?" | `ctx_fetch_and_index` + `ctx_search` |
| "What does our PRD require?" | read `docs/` |

graphify indexes this repository. It knows nothing about upstream library
documentation. Documentation tools know nothing about this repository. Never
substitute one for the other.


## 4. Session memory: search before asking

On resume, or after a compaction:

```
ctx_search(queries: ["what did we decide"], source: "decision", sort: "timeline")
ctx_search(queries: ["constraint", "blocker"], sort: "timeline")
```

Never ask "what were we working on?" before searching. Zero results means a
fresh session, not an excuse to prompt.

## 5. Reading files

| Intent | Tool |
|---|---|
| You will `Edit` this file | `Read` (exact bytes needed) |
| You will analyze/summarize it | `ctx_execute_file` |
| You need one known line range | `Read` with `offset`/`limit` |

## 6. Skill routing

| Need | Entry |
|---|---|
| Non-trivial feature | `feature-dev` (global skill) (power-pack) or `/new-feature` |
| New UI, page, or redesign | `.opencode/skills/hallmark` or `/build-ui` |
| UI is off but nothing is obviously broken | `.opencode/skills/refactoring-ui` or `/ui-audit` |
| Design bans and craft rules | `.opencode/skills/design-taste` |
| Codebase architecture survey | `improve-codebase-architecture` (global skill) |
| Need a skill by description | `find-skills` (global skill) |

The vendored skills are `hallmark`, `refactoring-ui`, `design-taste`, and
`i-have-adhd`. `vibe` was removed: it was broken (`apps/vgo-cli` missing) and
added 3.5 MB. For multi-part work use `/new-feature` or `feature-dev`.

Do not stack two orchestrators in one turn. `feature-dev` and `to-spec` both
plan; pick one.

## 7. Context budget heuristics

- One `ctx_batch_execute` replaces roughly 30 shell calls.
- If a tool result would exceed ~20 lines and you only need a fact from it,
  it belongs in `ctx_execute`, not in your context.
- Prefer printing counts, filenames, and first-N matches over full dumps.
