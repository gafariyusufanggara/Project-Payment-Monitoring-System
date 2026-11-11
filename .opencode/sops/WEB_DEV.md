# SOP — Web / App Development (phases 0a-7)

End-to-end procedure. Each phase has an exit condition. Do not skip an unmet
exit; do not loop back without saying why.

## Read map

| Need | Phase |
|---|---|
| Requirements from `docs/` | 0a |
| Detect stack | 0b + `STACKS.md` |
| Understand the codebase | 1 |
| Spec / plan | 2-3 |
| Build | 4 |
| Mechanical verify | 5 |
| Visual / browser verify | 6 |
| Review and hand off | 7 |

Missing tools: fallback per `.opencode/sops/CONTEXT.md` and
`context/TROUBLESHOOTING.md`. Announce once, continue.

## Phase 0a — Read the project documents (always first)

**Exit:** you can quote the requirement, or have said no project documents exist.

Discover, do not assume filenames:

```js
ctx_batch_execute(commands: [
  {label:"docs-tree", command:"rtk find docs -name *.md"},
  {label:"docs-root", command:"rtk find . -maxdepth 1 -name *.md"}
], queries: ["requirements","stack","features","design system"])
```

Read only files that map to the task. Common: `docs/PRD.md`, `docs/STACK.md`,
`docs/features/*.md`, `DESIGN.md` / `docs/DESIGN.md`, `docs/adr/*.md`.

Rules: docs are the source of truth and beat upstream docs and training data.
Quote the requirement before writing code. `ctx_execute_file` for a doc over
~200 lines. Never edit docs unless asked. Report code-vs-doc conflicts; never
silently pick a side. If `docs/` is absent, say so once and continue.

## Phase 0b — Detect stack

**Exit:** `.opencode/STACK.md` exists, or the agent said "no stack detected" and
stopped.

Read `.opencode/sops/STACKS.md`. Detect with one batch call, write
`.opencode/STACK.md`, then load **one** file from `.opencode/sops/stacks/`.
`docs/STACK.md` is authoritative; `.opencode/STACK.md` records what the code
contains. Report differences. Never assume a framework or scaffold into an
unknown directory.

## Phase 1 — Understand the codebase

**Exit:** you can name the files you will touch and the pattern you will follow.

```bash
graphify query "<feature area>"     # when graphify-out/ exists
graphify explain "<concept>"
graphify .                          # build once if no graph and repo is non-trivial
```

Read sibling components and nearest tests before writing. Match file naming,
import style, error handling, and state management.

## Phase 2 — Spec (only when >1 file or >1 concern)

**Exit:** a concrete spec with user-approved scope.

- `to-spec` (global skill); `to-tickets` when it should become tickets.
- Ambiguity means ask **once**, in a short numbered list, then proceed.
- Design-heavy feature: short `grill-me` (global skill) first.
- One-file bug fix: skip and say so.

## Phase 3 — Plan

**Exit:** ordered steps, each naming a file.

- `code-architect` (global skill) for a new module or non-obvious data flow.
- Otherwise 3-7 numbered steps inline.

## Phase 4 — Build

**Exit:** the change compiles and runs locally.

Order: data/types -> logic -> UI shell -> UI polish.

Rules:

- UI work loads `.opencode/skills/hallmark` (new page/design) or
  `.opencode/skills/refactoring-ui` (existing UI), plus `.opencode/sops/DESIGN.md`
  for the floor and bans.
- No comments unless asked. No dead code. No `TODO` in a handoff.
- New behaviour gets a test when the stack has a runner (stack file **Verify**).
  No runner: say so.
- No new dependency without saying why and confirming it is absent.
- Security: never log secrets, never ship secrets to the client, validate at the
  boundary, encode output.
- Keep diffs small; one concern per change.

## Phase 5 — Verify (mechanical)

**Exit:** all commands pass, or every failure is explained and accepted.

Take exact commands from the stack file's **Verify** section. Prefer
`package.json` scripts. JS example, with `rtk` prefix:

```bash
rtk npm run build
rtk npx tsc --noEmit        # or vue-tsc / svelte-check / astro check
rtk npx eslint .            # or biome check
rtk npx vitest run          # or pytest / go test / cargo test
```

Then build and start the production/preview server (background) before Phase 6.
Dev-server numbers are not gate evidence.

## Phase 6 — Verify (visual and real)

**Exit:** sloplint 0 FAIL, screenshots at 320/768/1280/1440, no console errors,
no critical a11y issue, LCP < 2.5 s, CLS < 0.1 on desktop 1440.

**Ask the user before the browser pass.** Screenshots and DevTools are slow. If
declined, record `WAIVED G5/G6`, state "UI not visually verified", and continue.
Never tick a visual gate without evidence.

```bash
node .opencode/skills/hallmark/scripts/sloplint.mjs <path> --render
```

Then `playwright` MCP: resize and screenshot 320 / 768 / 1280 / 1440. Then
`chrome-devtools` MCP against the production/preview server: console, network,
a11y, performance trace.

Browser MCP missing: stop and report "UI not verified, browser MCP missing".
Never tick a checklist without evidence. Full gate items:
`.opencode/sops/QUALITY_GATE.md` gates 4-6.

## Phase 7 — Review and hand off

**Exit:** an independent review pass found nothing blocking.

- `code-review` (global skill) for logic and convention bugs.
- `security-review` (global skill) for auth, input, network, or files.
- Report: what now works, how to see it, what is deliberately not done, open
  risks, next action.

Never claim a UI looks right without Phase 6 evidence.

## Definition of done

`.opencode/sops/QUALITY_GATE.md`. Done = every box checked or explicitly waived
with a user-accepted reason.

## Failure modes to avoid

| Sloppy | Correct |
|---|---|
| Assuming Next.js in a Vue repo | detect, write `.opencode/STACK.md` |
| Reading 40 files to "understand" | `graphify query`, then read 3 |
| Writing the whole page before rendering | build the hero, render, continue |
| "Should look good now" | screenshot at 4 viewports, paste evidence |
| Fixing 9 things in one diff | smallest change that satisfies the task |
| Dependency for a 5-line util | write the 5 lines |
| Placeholder copy in a handoff | real copy, or label as placeholder |
