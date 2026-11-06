# Coding Agent Setup — SOP + Skills for Web/App Development

A portable `.opencode/` folder plus one `AGENTS.md`. Copy both into a project and
the agent knows how to build web apps without producing AI slop.

Built for **opencode**, works with any agent that reads `AGENTS.md` +
`SKILL.md`. The SOP text is portable; the install scripts are Windows
PowerShell 5.1 only.

Project root after copying:

```
my-app/
├── docs/          your documents
├── src/ ...
├── AGENTS.md      <- the only setup file at the root
└── .opencode/     <- everything else
```

---

## What is in here

| Path | What it is |
|---|---|
| `AGENTS.md` (project root) | Routing table and hard rules. opencode reads it automatically. |
| `.opencode/sops/` | Five procedures: web dev phases, design law, quality gate, context routing, per-stack matrix |
| `.opencode/agents/` | `web-dev`, `ui-designer`, `reviewer`, `planner` subagents |
| `.opencode/commands/` | `/stack`, `/new-feature`, `/ship`, `/build-ui`, `/ui-audit`, `/i-have-adhd` |
| `.opencode/skills/hallmark` | Anti-slop design skill with a deterministic linter (`sloplint.mjs`) |
| `.opencode/skills/refactoring-ui` | 151-rule design rulebook distilled from *Refactoring UI* |
| `.opencode/skills/design-taste` | Ban catalogue, motion, interaction states, OKLCH colour |
| `.opencode/skills/i-have-adhd` | Output shaping for a reader with ADHD |
| `.opencode/instructions/ADHD.md` | The same ruleset for use as an always-on instruction |
| `.opencode/mcp/` | Why these MCP servers, the config snippet, install steps |
| `.opencode/scripts/` | `bootstrap-windows.ps1`, `check-setup.ps1`, `check-template.ps1`, `copy-to-project.ps1`, `install-skills.ps1`, `lib-jsonc.ps1` |

## Why these tools

Chosen by star count, licence, recency, and whether they produce *verifiable*
output rather than opinions.

| Tool | Choice | Reason |
|---|---|---|
| Anti-slop design | **Hallmark** (46k★, MIT) | Only one that ships a deterministic linter (`sloplint.mjs`, 16 floor gates + tiered reflex gates) and renders in a real browser at 8 widths. OpenCode-aware. |
| Design rulebook | **refactoring-ui** (358★) | 151 traceable rules, Step-0 stack detection, maps directly onto Tailwind scales. Diagnostic, not a generator. |
| Design craft | **design-taste** (90★) | Merges impeccable + emilkowalski + taste-skill. The sharpest concrete ban catalogue. |
| Output style | **i-have-adhd** | Answer-first output. |
| Browser verify | **Playwright MCP** (Microsoft) | Screenshots and interaction without a human. |
| Perf/a11y verify | **Chrome DevTools MCP** (Google) | LCP, CLS, console, a11y tree. |
| Library docs | **`ctx_fetch_and_index` + Tavily** | No docs MCP. Project `docs/` first, then official library docs fetched on demand. |

Rejected, with reasons: `oil-ui` (content in Mandarin), `superdesign` (needs an
account), `wghobson/agents` (heavy duplicate of power-pack), `mcp-chrome`
(overlaps playwright). Full reasoning in `.opencode/mcp/README.md`.

---

## What runs where

The template travels per project. The global layer lives once per machine and
must exist before the SOP can run at full strength.

**Pick the agent, the SOP does not pick itself.** opencode's default agent is
`build`, not `web-dev`. In every new session either type `@web-dev` or press Tab
and select one of `web-dev` / `ui-designer` / `reviewer` / `planner`. Commands
`/stack`, `/new-feature`, `/ship` already route to `web-dev` or `ui-designer`;
an un-routed session is just `build` with the SOP in context, nothing more.

| Layer | Lives in | Carried by `copy-to-project.ps1`? | Installed by |
|---|---|---|---|
| SOPs, agents, commands, skills, instructions | `.opencode/` | yes | copy |
| `AGENTS.md` | project root | yes | copy |
| Node, Git, Chrome, uv | machine | no | `bootstrap-windows.ps1` |
| `opencode`, `rtk`, `graphify` | machine | no | `bootstrap-windows.ps1` |
| Plugins: `context-mode`, `opencode-power-pack` | `~/.config/opencode/` | no | `bootstrap-windows.ps1` |
| MCP: `playwright`, `chrome-devtools`, optional `tavily` | `~/.config/opencode/` | no | `bootstrap-windows.ps1` |
| `SHELL` env var (context-mode) | user environment | no | `bootstrap-windows.ps1` |
| Global skills (copy of the vendored skills) | `~/.config/opencode/skills/` | no | `install-skills.ps1` |

Global skills that come from the `opencode-power-pack` plugin, referenced across
the SOPs: `feature-dev`, `code-review`, `security-review`, `code-architect`,
`code-explorer`, `code-reviewer`, `to-spec`, `to-tickets`, `find-skills`,
`grill-me`, `design-patterns`, `code-quality`, `frontend-design`,
`improve-codebase-architecture`, `grill-with-docs`, `handoff`, `implement`,
`setup-matt-pocock-skills`, `writing-for-agents`.

If one of them is missing, `AGENTS.md` degraded-mode rules apply: substitute the
local agent or `/command`, say it once, keep working.

---

# FRESH WINDOWS — install from scratch

Everything below is PowerShell 5.1, top to bottom. Expect 20-40 minutes on a
clean machine, mostly downloads.

## Fast path — one script

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .opencode\scripts\bootstrap-windows.ps1
```

It runs Steps 1–6 and the global skill install: base tools, opencode, rtk,
graphify, plugin + MCP config merge, the `SHELL` variable, Playwright chromium,
skills, then `check-setup.ps1`. Safe to re-run; every config file gets a
timestamped backup first.

Useful flags: `-DryRun`, `-TavilyKey "tvly-..."`, `-SkipBrowsers`, `-SkipSkills`.

On a machine with nothing installed yet, verify the template without failing on
the missing global layer:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .opencode\scripts\check-setup.ps1 -FirstRun
```

The manual steps below stay the reference for what the script does.

## Step 1 — Base tools

```powershell
# Node LTS (includes npm)
winget install OpenJS.NodeJS.LTS

# Git
winget install Git.Git

# Chrome (needed by chrome-devtools MCP)
winget install Google.Chrome
```

Close and reopen PowerShell so PATH refreshes. Verify:

```powershell
node --version    # >= 18
npm --version     # >= 9
git --version
```

## Step 2 — opencode

```powershell
npm i -g opencode-ai
opencode --version
```

## Step 3 — rtk (token-saving shell filter)

Install the release binary, then confirm it is on PATH:

```powershell
rtk --version
```

If `rtk` is not found, place `rtk.exe` in a folder on PATH (for example
`$env:LOCALAPPDATA\Programs\rtk`) and reopen PowerShell.

rtk is optional: every SOP command works without it, you just lose 60-90% of the
context savings.

## Step 4 — graphify (codebase knowledge graph)

```powershell
# needs uv or pipx; uv is recommended
winget install astral-sh.uv
uv tool install graphifyy
uv tool update-shell
```

Reopen PowerShell, then:

```powershell
graphify --version
```

In a project, build a graph once:

```powershell
graphify .
```

## Step 5 — opencode plugins

Edit `C:\Users\<you>\.config\opencode\opencode.json` (create it if missing):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "plugin": [
    "opencode-power-pack@git+https://github.com/waybarrios/opencode-power-pack.git",
    "context-mode"
  ]
}
```

Install the plugin packages:

```powershell
cd $env:USERPROFILE\.config\opencode
npm init -y
npm i context-mode
```

`opencode-power-pack` is fetched from git on first run. `context-mode` needs the
package in that folder.

Restart opencode. Blocked constructs (`curl`, `wget`, inline HTTP) and the
context-mode tools should now be active.

### Step 5b — Point context-mode at a real shell (Windows, required)

On Windows, context-mode picks `pwsh` first. The `pwsh.exe` that ships as a
Microsoft Store alias is a 0-byte stub, so every `ctx_batch_execute` call fails
with `Executable not found in $PATH: "pwsh"` even though PowerShell 7 is
installed. Pin it explicitly:

```powershell
[Environment]::SetEnvironmentVariable(
  'SHELL',
  "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe",
  'User')
```

context-mode honours `SHELL` when the basename is allowlisted
(`bash|sh|zsh|dash|pwsh|powershell|cmd`) and the file exists. Restart opencode
afterwards. `check-setup.ps1` verifies this.

Alternative: `winget install --id Microsoft.PowerShell` installs a real
`pwsh.exe` under `C:\Program Files\PowerShell\7` and the variable is not needed.

## Step 6 — MCP servers

Follow `.opencode/mcp/INSTALL.md`. Summary:

1. Back up `opencode.json`.
2. Merge the `"mcp"` block from `.opencode/mcp/opencode-snippet.jsonc`.
3. `npx -y playwright install chromium`
4. Warm each server once (`npx -y <pkg> --help`).
5. Restart opencode, ask it to list MCP tools.

The block declares `playwright` and `chrome-devtools`.

**Security note:** a Tavily remote MCP (used by some provider configs) stores its
API key in plaintext in `opencode.jsonc`. Move it to an environment variable
(`"Bearer {env:TAVILY_API_KEY}"`) — this repo leaves that decision to you.

## Step 7 — Install this SOP folder

Copy this whole `SETUP OPENCODE` folder somewhere permanent, for example
`C:\Users\Administrator\Desktop\SETUP OPENCODE`. Then verify:

```powershell
powershell -NoProfile -File "C:\Users\Administrator\Desktop\SETUP OPENCODE\.opencode\scripts\check-setup.ps1"
```

Every line should be `[OK]`. `[WARN]` items are optional (rtk, graphify,
playwright cache). `[FAIL]` must be fixed before proceeding.

Then run the template smoke test: layout, JSONC merge, agent/command
frontmatter, and a real copy into a temp folder.

```powershell
powershell -NoProfile -File "C:\Users\Administrator\Desktop\SETUP OPENCODE\.opencode\scripts\check-template.ps1"
```

## Step 8 — Make the skills global (optional but recommended)

```powershell
powershell -NoProfile -File "C:\Users\Administrator\Desktop\SETUP OPENCODE\.opencode\scripts\install-skills.ps1"
```

Installs `hallmark`, `refactoring-ui`, `design-taste`, `i-have-adhd`
into `~/.config/opencode/skills`. The project copy still ships its own
`.opencode/skills/` so every hardcoded `sloplint` path in the SOP resolves.

To list what is vendored:

```powershell
powershell -NoProfile -File "C:\Users\Administrator\Desktop\SETUP OPENCODE\.opencode\scripts\install-skills.ps1" -List
```

## Step 9 — Make ADHD output always-on (optional)

Open `~/.config/opencode/opencode.json` and add an instructions entry:

```json
"instructions": ["~/.config/opencode/instructions/ADHD.md"]
```

First copy the file:

```powershell
New-Item -ItemType Directory "$env:USERPROFILE\.config\opencode\instructions" -Force
Copy-Item "C:\Users\Administrator\Desktop\SETUP OPENCODE\.opencode\instructions\ADHD.md" "$env:USERPROFILE\.config\opencode\instructions\ADHD.md"
```

Say "stop adhd mode" in session to disable it, as the file itself documents.

## Step 10 — First real project

```powershell
mkdir C:\dev\my-app
cd C:\dev\my-app
# scaffold your stack however you prefer (next/nuxt/vite/...)
powershell -NoProfile -File "C:\Users\Administrator\Desktop\SETUP OPENCODE\.opencode\scripts\copy-to-project.ps1" -Destination "C:\dev\my-app"
```

Then in opencode, inside that project:

```
/stack        -> writes .opencode/STACK.md
```

Edit `AGENTS.md` in the project and replace `PROJECT_NAME`.

Verify the agent behaves:

```
/ship  build a settings page with a profile form, a toggle for dark mode, and an empty state
```

Expected: stack detected, plan, implementation, `sloplint` clean, screenshots at
320/768/1440, a11y and perf numbers, review, handoff block.

---

# Project documents: `docs/`

The agent reads `docs/` **before anything else** (Phase 0a). Contents vary per
project — never assume filenames. Put whatever you have in there; the agent
lists the folder and reads the files that map to the task.

A layout that works well:

```
my-app/
├── docs/                    your documents (agent reads these first)
│   ├── PRD.md               requirements, goals, non-goals
│   ├── STACK.md             framework, versions, package manager
│   ├── features/            one file per feature + acceptance criteria
│   └── adr/                 decisions and their rationale
├── DESIGN.md                locked design system (optional; overrides Hallmark themes)
├── AGENTS.md                routing table  <- must be at the root
├── .opencode/               everything agent-related
│   ├── sops/ agents/ commands/ skills/ instructions/ mcp/ scripts/
│   ├── README.md            this guide
│   └── STACK.md             written by /stack
└── src/
```

The project root stays clean: **only `AGENTS.md`** from this setup lives at the
root. Everything else is inside `.opencode/`. `docs/` is yours.

Precedence the agent applies:

| Source | Authority |
|---|---|
| `docs/` | Highest — intent and decisions. Beats upstream docs and assumptions. |
| Existing code | High — real conventions to match. |
| Official library docs | Medium — how the API works at that version. |
| Model memory | Lowest — must be verified before use. |

Rules that follow from this:

- The requirement is quoted from a document before code is written.
- If code and a document disagree, the conflict is reported, not silently
  resolved.
- Documents are never edited unless you ask.
- If `docs/` is absent, the agent says so once and continues.

Library documentation is **not** an MCP. When an API needs checking, the agent
fetches the official docs page into the knowledge base:

```
ctx_fetch_and_index(<official docs URL>, source: "docs-<lib>")
ctx_search(queries: [...], source: "docs-<lib>")
```

If the URL is unknown it searches with `tavily` first. An unverified third-party
API call must not be written — if docs cannot be fetched, the agent says so and
stops. Full procedure: `.opencode/sops/CONTEXT.md` § 3b.

---

# Daily use (per project)

| Situation | Command |
|---|---|
| New session, unsure of stack | `/stack` |
| Multi-file feature | `/new-feature` |
| Take a feature to done | `/ship` |
| New page / landing / redesign | `/build-ui` |
| Something looks off but you cannot name it | `/ui-audit` |
| Shorter output | `/i-have-adhd` |
| One-file fix | Just ask; quality gate still applies |

## Install into a project

```powershell
powershell -NoProfile -File "C:\Users\Administrator\Desktop\SETUP OPENCODE\.opencode\scripts\copy-to-project.ps1" -Destination "<project>"
```

Produces in `<project>`:

```
AGENTS.md          <- root, opencode auto-reads it
.opencode/         <- sops, agents, commands, skills, instructions, mcp, scripts, README
```

The setup travels with the project, is commit-able, and needs no global state.
Skills are always copied: the SOP calls `.opencode/skills/hallmark/scripts/sloplint.mjs`
by path, so a copy without them would break every UI gate. `-Force` replaces the
template-owned folders and preserves `.opencode/STACK.md`, `plans/`, and custom files.

## What to gitignore

Commit the whole `.opencode/` if the team should share the SOP. Never commit the
detected stack, dependencies, or build output:

```
node_modules/
.opencode/STACK.md
.opencode/node_modules/
graphify-out/
```

---

# The rules that make it not-slop

1. **`docs/` first, detect second.** Read the project documents, then detect the
   stack. Never assume either.
2. **Three design layers.** Hallmark floor (16 non-waivable items) → refactoring-ui
   (151 rules) → design-taste (concrete bans). Lower number wins on conflict.
3. **Evidence or it did not happen.** `sloplint` exit code, screenshot paths,
   LCP/CLS numbers, a11y count. "Looks good" is not accepted.
4. **Small diffs, one concern.** Polish is a gate, not a ticket.
5. **No invented content.** No fake metrics, testimonials, logos, or images.
6. **Answer first.** No preamble, no recap, concrete time estimates.

Full text: `.opencode/sops/DESIGN.md`, `.opencode/sops/QUALITY_GATE.md`.

---

# Troubleshooting

| Symptom | Fix |
|---|---|
| Fresh PC: `check-setup` red on MCP / SHELL / opencode.json | Expected before the global layer. Run `check-setup.ps1 -FirstRun`, then `bootstrap-windows.ps1` |
| Global skill named in the SOP does not exist | `opencode-power-pack` plugin not loaded. Re-run `bootstrap-windows.ps1`, restart opencode |
| `rtk` not found | Put `rtk.exe` on PATH, reopen terminal, or run `bootstrap-windows.ps1` |
| `ctx_batch_execute` fails: `Executable not found in $PATH: "pwsh"` | Step 5b: set `SHELL` to `powershell.exe`, restart opencode |
| `rtk find` says `does not support compound predicates` | Drop `-not` / `-exec`; scope the path instead |
| `rtk find` prints `0 for '*'` | Wrong cwd or empty folder. Retry with an absolute path; `0` is not proof a file is missing |
| `rtk ls` fails: `Binary 'ls' not found` | `rtk ls` is not available on Windows. Use `rtk find <path> -maxdepth 1` |
| `rtk find .` floods with `node_modules` | Scope the path: `rtk find src -name *.md`, or add `-maxdepth 2` |
| Agent does not follow the SOP | opencode's default agent is `build`, not `web-dev`. Type `@web-dev` or press Tab and select |
| `rtk find -name '*.md'` finds nothing | Remove the quotes: `-name *.md` |
| `rtk json pyproject.toml` says `is not a JSON file` | Use `rtk read pyproject.toml` |
| MCP tools missing in opencode | Run `npx -y @playwright/mcp@latest --help`; check opencode log |
| `sloplint` exits 2 | No `.html` found. For a dev server use a URL, or export HTML first |
| `sloplint --render` cannot find Chrome | Install Chrome, or accept the static tier only and record the waiver |
| Skill not discovered | Skills must sit in `.opencode/skills/<name>/SKILL.md`; run `install-skills.ps1 -List` |
| Agent assumes Next.js in a Vue repo | `/stack` first; check `.opencode/STACK.md` exists |
| `ctx_doctor` says `No plugin array found in opencode.json or opencode.jsonc` | Cosmetic. The doctor reads `opencode.jsonc` first and stops; opencode itself merges `.json` + `.jsonc`, so context-mode loads. Confirm with `opencode debug config` and look at `plugin` |

---

# Credits

| Project | Author | Licence |
|---|---|---|
| Hallmark | Nutlope / Together AI | MIT |
| refactoring-ui skill | edisonmbli | see `.opencode/skills/refactoring-ui/` |
| design-taste | h3nryprod01 | MIT AND Apache-2.0 |
| i-have-adhd | ayghri | MIT |
| context-mode | mksglu | MIT |
| opencode-power-pack | waybarrios | see package |
| graphify | Graphify-Labs | see package |
| Playwright MCP | Microsoft | Apache-2.0 |
| Chrome DevTools MCP | Google | Apache-2.0 |
| Context7 | Upstash | MIT (not installed; see `.opencode/mcp/README.md`) |
