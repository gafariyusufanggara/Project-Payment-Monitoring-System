# SOP — Tooling Troubleshooting

Load only when a tool fails, output floods, or a command behaves unexpectedly.
Normal work uses `.opencode/sops/CONTEXT.md` only.

## rtk limits on Windows (verified against rtk 1.2.0)

`rtk` proxies real binaries. Anything it shells out to must exist on PATH.
This machine gets them from `C:\Program Files\Git\usr\bin` (Git for Windows
ships `grep`, `wc`, `ls`, `find`, `sed`, `awk`) and from ripgrep
(`%LOCALAPPDATA%\Programs\ripgrep\...\rg.exe`). Both are on the user PATH.
If a new machine lacks them, `bootstrap-windows.ps1` adds them.

| Do not write | Why | Write instead |
|---|---|---|
| `rtk ls <path>` | resolves native `ls`; absent without Git's usr\bin on PATH | `rtk find <path> -maxdepth 1` (always works) |
| `rtk grep <pattern> <dir>` | GNU grep is not recursive; `grep: .: Is a directory` | `rtk rg <pattern> <dir>` (ripgrep, recursive) |
| `rtk rg <pattern>` without ripgrep on PATH | `Binary 'rg' not found on PATH` | `rtk rg` after adding ripgrep to PATH |
| `rtk tree <path>` | resolves the Windows `tree.exe`, which takes different args | `rtk find <path> -maxdepth 2` |
| `rtk find ... -exec ...` | the proxied `find` rejects it | run the action as its own command |
| `-name '*.md'` in bash | bash expands the glob first | quote it in bash; PowerShell passes it literally |
| `rtk json pyproject.toml` | `rtk json` parses JSON only | `rtk read pyproject.toml` |

Verified working on this machine: `rtk find`, `rtk read`, `rtk rg`, `rtk grep`
(on a single file), `rtk wc`, `rtk ls`, `rtk git`, `rtk json` (on JSON),
`rtk tree` (needs `tree.exe`).

`rtk find` supports `-not -path` (it passes through to GNU find) — it is not
rejected. `-maxdepth N` works. `0 for '<pattern>'` when nothing matches is a
valid empty result, not a failed command. Do not retry with different flags.

## cwd and path failures

- `ctx_*` and shell run from the session cwd, not necessarily the project root.
- Use absolute paths in `ctx_batch_execute`, or `Set-Location <project>` first.
- A relative `0 for '*'` usually means wrong cwd. Re-check with an absolute path
  before reporting "file missing".

## Missing tools — degrade, never fake

| Missing | Fallback | Notice (once per session) |
|---|---|---|
| `rtk` | plain `git`, `node`, `npm`, `pytest`, ... | "rtk tidak terpasang, jalan tanpa filter." |
| `ctx_*` tools | `Read`, `Grep`, `Glob`, direct shell | "context-mode tidak aktif, baca langsung." |
| both | normal tool use, smaller batches | say once, then continue |
| `graphify` | `rtk grep` / `rg`, then read 2-3 files | "graphify tidak terpasang." |
| browser MCP | do the code work, then stop | "UI not verified — browser MCP missing." |

Never retry a missing command, pretend it ran, or claim token savings you did not
get. Install path: `.opencode/scripts/bootstrap-windows.ps1`.

## Blocked constructs (do not retry)

- `curl`, `wget` in shell — intercepted.
- Inline HTTP in scripts: `fetch('http`, `requests.get(`, `requests.post(`.
- Direct web fetch into context.

Use `ctx_fetch_and_index(url, source)` then `ctx_search`, or `ctx_execute` with
`fetch` inside the sandbox.

## Batch and concurrency

```js
ctx_batch_execute(commands: [{label:"a", command:"..."}, ...],
                  queries: ["q1","q2"], concurrency: 5)
```

- `concurrency: 4-8` for I/O-bound work (network, `gh`, API, multi-repo reads).
- `concurrency: 1` for CPU-bound (build, test, lint) or shared-state commands
  (ports, lock files, same-repo writes).
- Cap `gh` at 4 for GitHub rate limits.
- A failing label inside a batch is information, not a crash. Do not retry with
  new flags.

## Exit codes and non-errors

- `sloplint` exit `0` clean, `1` slop found (fix every FAIL), `2` no `.html`/`.tsx`
  target found — a scope problem, not a design failure.
- `rtk find` printing `0 for '<pattern>'` is a valid empty result.
- `rtk json` failing on a missing or non-JSON file is information, not a bug.
- A missing script in a verify gate is a gap: record `N/A <check>: <reason>`; never
  report the gate as passed.

## When a tool floods output

Move the command into `ctx_execute` / `ctx_execute_file` and print only the
answer (count, filenames, first N matches). Do not pipe the raw dump back into
context to "see what happened".
