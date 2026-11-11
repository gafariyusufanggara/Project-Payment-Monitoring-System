<!--
Project SOP template. Layout:

  my-app/
  ├── docs/                 PRD, STACK, features, ADR
  ├── src/ ...              code
  ├── AGENTS.md             this file (opencode reads it automatically)
  └── .opencode/            sops, agents, commands, skills, instructions, mcp, scripts

Fill PROJECT_NAME, then run /stack.
-->

# PROJECT_NAME — Agent Instructions

Routing table. Detailed procedures live in `.opencode/sops/`.

## Precedence

1. System prompt and user's direct instruction.
2. This file.
3. `.opencode/sops/*.md`.
4. `.opencode/skills/*/SKILL.md`.
5. Global `~/.config/opencode/AGENTS.md` and `instructions/ALWAYS-ON.md`.

Lowest number wins. When a skill conflicts with `.opencode/sops/DESIGN.md`, the
SOP wins.

## Load order (by trigger, not all up front)

0. **`docs/`** — always first. Source of truth; beats every rule below.
1. `.opencode/STACK.md` — before any implementation. Missing -> `/stack`.
2. `.opencode/sops/WEB_DEV.md` — before the first implementation step.
3. `.opencode/sops/CONTEXT.md` — before the first shell or context-mode call.
   Add `.opencode/sops/context/TROUBLESHOOTING.md` only when a tool errors.
4. `.opencode/sops/QUALITY_GATE.md` — before claiming done.
5. `.opencode/sops/DESIGN.md` — only if the task touches user-visible UI.
6. `.opencode/sops/STACKS.md` at Phase 0b, then **one** file in
   `.opencode/sops/stacks/`.

Load a SOP when its trigger fires. Do not preload all of them.

## Hard rules (never violate)

- **Output style is `i-have-adhd` on every response.** First line = next action,
  command, path, or answer. Number multi-step work. Restate state each turn.
  No preamble, recap, or closers. Persist until the user says "stop adhd mode".
  Full ruleset: `.opencode/instructions/ADHD.md`.
- **After every file edit or write, run `graphify update .`.** The
  `graphify-auto-update` plugin runs it automatically (debounced, flushed on
  idle). Run it manually if the plugin did not. Skip only when
  `graphify-out/graph.json` is absent. Keep the output quiet.
- **`rtk` prefix on every shell command.** Unfiltered only when debugging rtk or
  when the wrapper rejects the flags. Limits: `CONTEXT.md` and
  `context/TROUBLESHOOTING.md`.
- **context-mode is mandatory.** Analyse/parse/filter with `ctx_execute` /
  `ctx_execute_file` / `ctx_batch_execute`; `Read` only when you will `Edit`.
- **`docs/` is the source of truth.** Quote the requirement before writing code.
- **No library API from memory.** Verify against official docs fetched this
  session or existing repo code. If docs cannot be fetched, say so and stop.
- **graphify before grep.** If `graphify-out/graph.json` exists,
  `graphify query "<question>"` precedes `grep`.
- **Detect, never assume, the stack.**
- **UI is not done without evidence.** `sloplint` clean; screenshots at
  320/768/1280/1440 via playwright only after the user approves the browser pass.
- **No code comments unless the user asks.**
- **No commit, no push, no PR unless the user asks.**
- **Shell is Windows PowerShell 5.1.** No `&&`. Use separate calls or `;`.
- **Never invent content.** No fake metrics, testimonials, logos, or images.
- **cwd is not guaranteed to be the project root.** Use absolute paths in
  `ctx_*` and shell when you are not sure the session is at the project root.
  Relative paths in the examples assume the project root.

## Routing table

| Task | Do this |
|---|---|
| Unclear stack / new session | `/stack` |
| New feature, multiple files | `/new-feature` |
| Feature taken to done | `/ship` |
| New page, landing, redesign | `/build-ui` (Hallmark) |
| Existing UI looks off | `/ui-audit` |
| Small fix, one file | Just do it, follow `QUALITY_GATE.md` |
| Architecture question | `code-architect` subagent or global skill |
| Understand a feature | `code-explorer` subagent, or `graphify query` |
| Review before handoff | `reviewer` agent |
| Need a skill by description | `find-skills` (global skill) |

Tool routing, `rtk` limits, and degraded-mode fallbacks:
`.opencode/sops/CONTEXT.md` and `.opencode/sops/context/TROUBLESHOOTING.md`.

## Design is not optional

Any user-visible change:

1. Load `.opencode/skills/hallmark` (new page) or `.opencode/skills/refactoring-ui` (existing UI).
2. Apply `.opencode/sops/DESIGN.md` — all three layers.
3. Verify with `sloplint --render`, then ask before the browser pass
   (screenshots + DevTools). Declined -> record `WAIVED G5/G6`.

The 16-item floor is non-waivable. The concrete ban table is match-and-refuse.

## Definition of done

See `.opencode/sops/QUALITY_GATE.md`. Summarised:

- Behaviour runs and is verified by running.
- build / typecheck / lint (0 new) / test all pass.
- UI: sloplint 0 FAIL; screenshots at 4 viewports (320/768/1280/1440) after user
  approval; 0 critical a11y; LCP < 2.5 s; CLS < 0.1. Declined -> waived, not
  verified.
- Review passed, blocking findings addressed.
- `graphify update .` run after the last edit.
- Handoff states: what works, how to see it, what is not done, risks, next action.

## Communication

Shaped by `i-have-adhd`: answer first, numbered steps, state restated, concrete
estimates, visible wins, no preamble or closer. Full ruleset in
`.opencode/instructions/ADHD.md`; invoke `/i-have-adhd` to reload it.

## Where things live

| Path | Contents |
|---|---|
| `.opencode/sops/` | Five procedures + `stacks/` + `context/` |
| `.opencode/agents/` | `develop`, `ui-designer`, `reviewer`, `planner` |
| `.opencode/commands/` | `/ship`, `/new-feature`, `/ui-audit`, `/build-ui`, `/stack` |
| `.opencode/skills/` | hallmark, refactoring-ui, design-taste, i-have-adhd |
| `.opencode/instructions/` | `ADHD.md`, `ALWAYS-ON.md` |
| `.opencode/plugins/` | `graphify-auto-update.js` |
| `.opencode/mcp/` | MCP rationale, snippet, install steps |
| `.opencode/scripts/` | Setup, copy, install helpers |
| `.opencode/README.md` | Full setup guide |
| `.opencode/STACK.md` | Written by `/stack` |

Project documents live in `docs/` and are authoritative.
