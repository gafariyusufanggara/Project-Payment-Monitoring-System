<!--
Project SOP template.

Layout this file expects in a project root:

  my-app/
  ├── docs/                 your documents (PRD, STACK, features, ADR)
  ├── src/ ...              your code
  ├── AGENTS.md             this file  (opencode reads it automatically)
  └── .opencode/            everything agent-related, kept out of the root
      ├── sops/             procedures
      ├── agents/           subagents
      ├── commands/         slash commands
      ├── skills/           vendored skills
      ├── instructions/     always-on instruction files
      ├── mcp/              MCP rationale, snippet, install steps
      ├── scripts/          setup, copy, install helpers
      ├── README.md         the full setup guide
      └── STACK.md          written by /stack from real detection

Placeholders to fill: PROJECT_NAME, and the stack after running /stack.
-->

# PROJECT PAYMENT MONITORING SYSTEM — Agent Instructions

You are a coding agent working in this repository. This file is the routing
table. Detailed procedures live in `.opencode/sops/`.

## Precedence

1. System prompt and user's direct instruction.
2. This file.
3. `.opencode/sops/*.md` (procedure).
4. `.opencode/skills/*/SKILL.md` (specialist method).
5. Global `~/.config/opencode/AGENTS.md` (tooling: rtk, context-mode).

When two rules conflict, the higher number wins. When a skill conflicts with
`.opencode/sops/DESIGN.md`, the SOP wins.

## Read order at session start

0. **`docs/`** — the project documents. Contents vary per project: list it, read
   what is relevant (PRD, STACK, features, DESIGN, ADR). These are the source of
   truth and beat every rule below them.
1. `.opencode/STACK.md` — if missing, run `/stack` first. Never assume a stack.
2. `.opencode/sops/WEB_DEV.md` — the phase procedure.
3. `.opencode/sops/CONTEXT.md` — tool routing (rtk, context-mode, graphify, docs).
4. `.opencode/sops/QUALITY_GATE.md` — definition of done.
5. `.opencode/sops/DESIGN.md` — only if the task touches user-visible UI.

## Hard rules (never violate)

- **`rtk` prefix on every shell command.** `rtk git status`, `rtk npx tsc`,
  `rtk pytest`. Unfiltered only when debugging rtk itself or when the `rtk`
  wrapper rejects the flags — limits are listed in `.opencode/sops/CONTEXT.md`
  §1 (`-not`/`-exec`, quoted globs, TOML via `rtk json`, `rtk ls`).
- **`docs/` is the source of truth.** Quote the requirement before writing code.
  Project documents beat upstream docs and your assumptions.
- **No library API from memory.** Verify against official docs fetched this
  session (`ctx_fetch_and_index` / `tavily`) or existing repo code. If docs
  cannot be fetched, say so and stop.
- **context-mode routing.** Do not read raw output into context when a
  derivation is possible. `ctx_execute` / `ctx_batch_execute` /
  `ctx_execute_file` for analysis; `Read` only when you will `Edit`.
- **graphify before grep.** If `graphify-out/graph.json` exists, `graphify query
  "<question>"` precedes `grep`.
- **Detect, never assume, the stack.**
- **UI is not done without evidence.** `sloplint` clean plus screenshots at
  320/768/1440 via playwright. A visual claim without a screenshot is a guess.
- **No code comments unless the user asks.**
- **No commit, no push, no PR unless the user asks.**
- **Never invent content.** No fake metrics, testimonials, logos, or images.

## Degraded mode — when tooling is missing

A fresh machine may not have every layer installed yet. Missing tooling is a
known state, not a reason to stop or to fake results.

| Missing | Do this | Never do this |
|---|---|---|
| `rtk` | Run the plain command. Say once: "rtk tidak terpasang, jalan tanpa filter." | Retry `rtk ...`, pretend it filtered |
| `context-mode` (`ctx_*` tools) | Use `Read` / `Grep` / shell directly, one question per call | Claim you routed through the sandbox |
| Global skill (`code-review`, `feature-dev`, `security-review`, `to-spec`, `to-tickets`, `find-skills`, `code-architect`, `grill-me`, `design-patterns`, `code-quality`, `frontend-design`) | Substitute the local path: `reviewer` agent, `/new-feature`, `.opencode/skills/*`. Say the skill was unavailable | Silently skip the review step |
| `playwright` / `chrome-devtools` MCP | Do the code work, then stop and report "UI not verified — browser MCP missing" | Claim a screenshot or a11y pass |
| `graphify` | Fall back to `rtk grep` / `rg` | Skip straight to reading whole files |

Rules:

- Announce a missing tool **once per session**, then continue.
- The fix is `.opencode/scripts/bootstrap-windows.ps1`, not a workaround.
- A missing QA tool downgrades the claim ("not verified"), it never upgrades it.
- If the user asked for something that genuinely cannot be done without the
  missing tool, say which tool and what to install. One line.


## Routing table

| Task | Do this |
|---|---|
| Unclear stack / new session | `/stack` |
| New feature, multiple files | `/new-feature` |
| Feature taken to done | `/ship` |
| New page, landing, redesign | `/build-ui` (Hallmark) |
| Existing UI looks off | `/ui-audit` |
| Small fix, one file | Just do it, follow `.opencode/sops/QUALITY_GATE.md` |
| Architecture question | `code-architect` subagent or `code-architect` (global skill) |
| Understand a feature | `code-explorer` subagent, or `graphify query` |
| Review before handoff | `reviewer` agent |
| Ambiguous multi-part work | `$vibe` |
| Need a skill by description | `find-skills` (global skill) |

## Design is not optional

Any user-visible change:

1. Load `.opencode/skills/hallmark` (new page) or `.opencode/skills/refactoring-ui` (existing UI).
2. Apply `.opencode/sops/DESIGN.md` — all three layers.
3. Verify with `sloplint --render`, then screenshots, then DevTools.

The 16-item floor is non-waivable. The concrete ban table is match-and-refuse.

## Definition of done

See `.opencode/sops/QUALITY_GATE.md`. Summarised:

- Behaviour runs and is verified by running.
- build / typecheck / lint (0 new) / test all pass.
- UI: sloplint 0 FAIL, screenshots at 3 viewports, 0 critical a11y,
  LCP < 2.5 s, CLS < 0.1.
- Review passed, blocking findings addressed.
- Handoff states: what works, how to see it, what is not done, risks, next action.

## Communication

- Answer first, explanation second.
- Multi-step work gets a numbered list.
- State which phase or step you are in when it is not obvious.
- Errors: cause and fix on one line. No "uh oh".
- No preamble, no recap, no "let me know if you need anything else".
- Concrete estimates (minutes/hours), never "a bit of work".

## Where things live

Everything agent-related is under `.opencode/`, so the project root stays clean.

| Path | Contents |
|---|---|
| `.opencode/sops/` | The five procedure documents |
| `.opencode/agents/` | `web-dev`, `ui-designer`, `reviewer`, `planner` |
| `.opencode/commands/` | `/ship`, `/new-feature`, `/ui-audit`, `/build-ui`, `/stack` |
| `.opencode/skills/hallmark` | Anti-slop design skill + deterministic linter |
| `.opencode/skills/refactoring-ui` | 151-rule design rulebook and diagnostic |
| `.opencode/skills/design-taste` | Ban catalogue, motion, interaction states |
| `.opencode/skills/vibe` | Governed skill orchestrator (`$vibe`) |
| `.opencode/skills/i-have-adhd` | Output shaping for a reader with ADHD |
| `.opencode/instructions/ADHD.md` | Same ruleset, as an always-on instruction file |
| `.opencode/mcp/` | MCP rationale, snippet, and install steps |
| `.opencode/scripts/` | Setup check, project copy, skill install |
| `.opencode/README.md` | Full setup guide, fresh-install steps, troubleshooting |
| `.opencode/STACK.md` | Written by `/stack`; the detected stack, not your decision |

Your own documents live in `docs/` at the project root. They are authoritative
and the agent reads them before anything in `.opencode/`.

Skills from `opencode-power-pack` (`feature-dev`, `code-review`, `code-architect`,
`to-spec`, `find-skills`, ...) are installed globally, not vendored here. If one
is missing, the power-pack plugin is not loaded.
