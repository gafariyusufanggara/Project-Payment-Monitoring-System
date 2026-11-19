<!--
Project SOP template. Layout:

  my-app/
  ├── docs/                 PRD, STACK, features, ADR
  ├── src/ ...              code
  ├── AGENTS.md             this file (opencode reads it automatically)
  └── .opencode/            sops, agents, commands, skills, instructions, mcp, scripts

Fill PROJECT_NAME, then run /stack.
-->

# PROJECT PAYMENT MONITORING SYSTEM — Agent Instructions

Routing table. Detailed procedures live in `.opencode/sops/`.

## Precedence

1. System prompt and user's direct instruction.
2. This file.
3. `.opencode/sops/*.md`.
4. `.opencode/skills/*/SKILL.md`.
5. Global `~/.config/opencode/AGENTS.md` (machine-wide always-on rules).

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

Machine-wide rules are owned by `~/.config/opencode/AGENTS.md` (source:
`.opencode/instructions/ALWAYS-ON.md`) and load in every session. Follow them;
they are not restated here to avoid drift: `i-have-adhd` output style (default
on, until "stop adhd mode"), automatic `graphify update .`, `rtk` prefix on every
shell command, context-mode routing, Windows PowerShell 5.1 shell rules. Full
ruleset: `ALWAYS-ON.md` and `.opencode/skills/i-have-adhd/SKILL.md`.

Project rules (owned here):

- **`docs/` is the source of truth.** Quote the requirement before writing code.
- **No library API from memory.** Verify against official docs fetched this
  session or existing repo code. If docs cannot be fetched, say so and stop.
- **graphify before grep.** If `graphify-out/graph.json` exists,
  `graphify query "<question>"` precedes `grep`.
- **Detect, never assume, the stack.**
- **UI is not done without evidence.** `sloplint` clean; screenshots at
  320/768/1280/1440 via the Playwright CLI only after the user approves the
  browser pass.
- **No code comments unless the user asks.**
- **No commit, no push, no PR unless the user asks.**
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
| Architecture question | the `planner` subagent |
| Understand a feature | the `explore` subagent, or `graphify query` |
| Review before handoff | `reviewer` agent |
| Need a skill by description | list `.opencode/skills/` (project-local) |

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

`.opencode/sops/QUALITY_GATE.md` is the single source of truth for every gate;
do not restate thresholds elsewhere. Done = every applicable gate passed or
explicitly waived with a user-accepted reason. Handoff order: what works, how to
see it, what is not done, risks, next action.

## Communication

Shaped by `i-have-adhd` (default on, until "stop adhd mode"); the full ruleset
lives in `.opencode/skills/i-have-adhd/SKILL.md`. Invoke `/i-have-adhd` to reload.

## Where things live

| Path | Contents |
|---|---|
| `.opencode/sops/` | Five procedures + `stacks/` + `context/` |
| `.opencode/agents/` | `develop`, `ui-designer`, `reviewer`, `planner` |
| `.opencode/commands/` | `/ship`, `/new-feature`, `/ui-audit`, `/build-ui`, `/stack` |
| `.opencode/skills/` | hallmark, refactoring-ui, design-taste, i-have-adhd |
| `.opencode/instructions/` | `ALWAYS-ON.md` (source for the global always-on file) |
| `.opencode/plugins/` | `graphify-auto-update.js` |
| `.opencode/mcp/` | MCP rationale, snippet, install steps |
| `.opencode/scripts/` | Setup, copy, install helpers |
| `.opencode/STACK.md` | Written by `/stack` |

Project documents live in `docs/` and are authoritative.
