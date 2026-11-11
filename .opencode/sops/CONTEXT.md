# SOP — Context, Shell, Codebase Memory

Keep the context window small. Global tooling rules live in
`~/.config/opencode/AGENTS.md` and `instructions/ALWAYS-ON.md`; this file covers
project work. Tool errors: `.opencode/sops/context/TROUBLESHOOTING.md`.

## Read map

| Need | Section |
|---|---|
| Shell / rtk / cwd | §1 |
| Route a tool call | §2 |
| Graph or grep | §3 |
| Which source wins | §3b |
| Resume after compaction | §4 |
| Read vs analyse a file | §5 |
| Pick a skill | §6 |
| Context budget | §7 |

## 1. Shell: prefix every command with `rtk`

`rtk` filters output (60-90%) and passes through when it has no filter.

```bash
rtk git status   rtk git diff   rtk git log   rtk grep <pattern>
rtk find <path>  rtk read <file>  rtk tsc   rtk lint
rtk pytest tests/   rtk npm run <script>   rtk gh pr view <n>
```

Shell is Windows PowerShell 5.1: no `&&`. Use one call per command, or `;` when
the next step may run after a failure. Use the raw command only when debugging
rtk, or `rtk proxy <cmd>` for unfiltered but tracked.

**Scope `rtk find`**: prefer a path (`rtk find src -name *.tsx`). A root scan is
allowed only with a depth bound (`rtk find . -maxdepth 2 -name *.toml`); never an
unbounded `rtk find .` from the repo root. `-maxdepth N` works. No `-not`,
`-exec`, or compound predicates. `0 for '<pattern>'` is a valid "no match", not
proof a file is absent when the path is relative.

**cwd is not guaranteed to be the project root.** `ctx_*` and shell run from the
session cwd. Use absolute paths when cwd is uncertain, or `cd <project-root>`
first. Relative examples assume the project root. A relative `0 for '*'` means
"wrong path or empty", never proof on its own.

Missing `rtk` / `ctx_*`: announce once, use the fallback. Full table:
`context/TROUBLESHOOTING.md`.

## 2. context-mode: route everything through the sandbox

Never read raw output into context when a derivation is possible.

| Situation | Wrong | Right |
|---|---|---|
| Analyze/parse/filter data | `Read` the file | `ctx_execute_file(path, lang, code)` |
| Multi-step investigation | 20 shell calls | `ctx_batch_execute([{label, command}...], queries)` |
| Search across many results | `Grep` then read | `ctx_execute` with a filter, print counts |
| Fetch a web page | `Invoke-WebRequest` | `ctx_fetch_and_index` then `ctx_search` |
| Two questions about same data | two calls | one `ctx_search(queries: ["q1","q2"])` |

`ctx_batch_execute` with 3+ I/O commands: `concurrency: 4-8`. Keep `concurrency:
1` for CPU-bound (build, test, lint) or state-sharing commands. Cap `gh` at 4.
Blocked constructs (`curl`, `wget`, inline HTTP): do not retry — see
`context/TROUBLESHOOTING.md`.

**Artifacts go to files.** Never return a report inline; report `path` + one
line.

## 3. graphify: query the graph before grepping

If `graphify-out/graph.json` exists, treat any codebase question as a graph query
first.

```bash
graphify query "<question>"     # scoped subgraph
graphify path "<A>" "<B>"       # relationship
graphify explain "<concept>"    # focused concept
graphify update .               # after edits, AST only
```

**Auto-update:** the `graphify-auto-update` plugin runs `graphify update .` after
every edit/write, debounced 1.5 s, flushed on idle. If it did not run, run it
manually after the last edit. Skip only when the graph file is absent. Keep the
output quiet.

Order: `graphify query` -> `graphify-out/wiki/index.md` -> `GRAPH_REPORT.md`
(broad review only) -> `rtk grep` + 2-3 file reads. Dirty `graphify-out/` is
expected; never skip graphify because of it.

## 3b. Source of truth — read in this order

1. **Project documents in `docs/`** — intent, requirements, decisions, stack.
2. **The existing code** — real patterns and conventions.
3. **Official library documentation** — only for third-party APIs.

Project documents win over upstream docs and over your assumptions.

### Project documents (`docs/`)

Do not assume filenames. Discover, then read only what maps to the task:

```js
ctx_batch_execute(commands: [
  {label:"docs-tree", command:"rtk find docs -name *.md"},
  {label:"docs-root", command:"rtk find . -maxdepth 1 -name *.md"}
], queries: ["requirements","stack","features","design system","decisions"])
```

| Likely file | Purpose |
|---|---|
| `docs/PRD.md` | Requirements, goals, non-goals |
| `docs/STACK.md` | Framework, versions, package manager |
| `docs/features/*.md` | Per-feature specs and acceptance criteria |
| `DESIGN.md` / `docs/DESIGN.md` | Locked design system |
| `docs/adr/*.md` | Decisions and rationale |

Rules: list large `docs/` first; `ctx_execute_file` for files over ~200 lines;
never edit docs unless asked; report code-vs-doc conflicts; quote the requirement.

### External library documentation

```
ctx_fetch_and_index(<official docs URL>, source: "docs-<lib>")
ctx_search(queries: [...], source: "docs-<lib>")
```

URL unknown -> call whichever web-search tool is enabled (`tinyfish_search` or
`tavily_tavily_search`), then fetch the official result. If no search tool is
enabled, say so and ask for the URL. Official docs only. **Never write a library
API call you have not verified in this session.** If no docs can be fetched, say
so and stop.

### graphify vs documentation

graphify indexes this repo; it knows nothing about upstream docs. Documentation
tools know nothing about this repo. Never substitute one for the other.

| Question | Tool |
|---|---|
| "Where is auth verified here?" / "Who calls this?" | `graphify` |
| "What is the current API of library X?" | `ctx_fetch_and_index` + `ctx_search` |
| "What does our PRD require?" | read `docs/` |

## 4. Session memory: search before asking

On resume or after compaction:

```
ctx_search(queries: ["what did we decide"], source: "decision", sort: "timeline")
ctx_search(queries: ["constraint", "blocker"], sort: "timeline")
```

Never ask "what were we working on?" before searching. Zero results means a fresh
session, not an excuse to prompt.

## 5. Reading files

| Intent | Tool |
|---|---|
| You will `Edit` this file | `Read` (exact bytes needed) |
| You will analyze/summarize it | `ctx_execute_file` |
| You need one known line range | `Read` with `offset`/`limit` |

## 6. Skill routing

| Need | Entry |
|---|---|
| Non-trivial feature | `feature-dev` (global skill) or `/new-feature` |
| New UI, page, redesign | `.opencode/skills/hallmark` or `/build-ui` |
| Existing UI is off | `.opencode/skills/refactoring-ui` or `/ui-audit` |
| Design bans and craft | `.opencode/skills/design-taste` |
| Architecture survey | `improve-codebase-architecture` (global) |
| Skill by description | `find-skills` (global) |

Vendored: `hallmark`, `refactoring-ui`, `design-taste`, `i-have-adhd`. Do not
stack two orchestrators in one turn; `feature-dev` and `to-spec` both plan, pick
one.

## 7. Context budget

- One `ctx_batch_execute` replaces roughly 30 shell calls; use 5-8 queries and do
  not re-run the same batch.
- Tool output over ~100 lines or ~2k tokens: derive in the sandbox, print the
  answer, counts, or first N matches.
- After a ctx summary, act on it. Re-read the raw source only when the summary
  lacks a fact you need.
- Keep tool output per task under ~10k tokens; summarize before continuing when
  it grows past that.
- `ctx_*` is for reading and analysis. Write files with the native Write/Edit
  tools.
