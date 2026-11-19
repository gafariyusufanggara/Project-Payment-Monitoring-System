# MCP — what runs, why, and what it costs

Browser work is split across **one MCP server and one CLI + skill**, not two
MCP servers. Both run locally, send no telemetry.

| Tool | Source | Transport | Purpose | Needs |
|---|---|---|---|---|
| `chrome-devtools` | `ChromeDevTools/chrome-devtools-mcp` | MCP | Console, network, a11y tree, performance trace, LCP/CLS, Lighthouse | Node 18+, Chrome |
| `playwright-cli` | `@playwright/cli` | CLI + skill | Interaction: open, click, fill, snapshot, screenshot, resize | Node 18+, Chromium |
| `tavily` | remote MCP (optional) | MCP | Find the official docs URL when it is unknown | API key |

## Why this split, and why not two MCP servers

`@playwright/mcp` was the previous default and has been **removed**. It works,
but it injects a large tool schema and verbose accessibility trees into every
model turn. `@playwright/cli` does the same browser work through short
commands whose output the agent reads on demand. For a coding agent that is
already holding a codebase in context, that difference decides whether the
browser pass fits in the remaining budget.

`chrome-devtools-mcp` stays an MCP server because its value is *structured
introspection* — performance insights, network entries, console messages — which
the agent queries, and there is no cheaper CLI equivalent that returns the same
data.

- **playwright-cli** is the anti-hallucination tool for UI. Without it, "it
  looks good" is a guess. It also lets a page be checked at 320/768/1280/1440
  pixels without a human.
- **chrome-devtools** is the only reliable way to get LCP, CLS, console errors,
  and the a11y tree. Lighthouse-style numbers are required by
  `.opencode/sops/QUALITY_GATE.md` gates 5-6.

## Usage shape

MCP server (ask for data):

```
analyse the console errors on the preview server
```

CLI (drive the page):

```
playwright-cli open https://localhost:3000
playwright-cli resize 375 812
playwright-cli snapshot
playwright-cli screenshot
playwright-cli close-all
```

The agent reads `playwright-cli --help` when it needs the full command list, and
the `playwright-cli` skill is installed globally for the guided flow.

## Library documentation: no MCP
There is deliberately no documentation MCP. Two sources cover the need:
| Source | Covers |
|---|---|
| `docs/` in the project | What to build, the chosen stack and versions |
| `ctx_index` + `ctx_search` | How a third-party API works today |
| `tavily` (remote MCP) | Finding the official docs URL when it is unknown |
See `.opencode/sops/CONTEXT.md` → **External library documentation** for the
procedure and the rule that an unverified library API call must not be written.

## Explicitly not used
| MCP | Why not |
|---|---|
| `@playwright/mcp` | Removed 2026-11-16. Same capability as `playwright-cli` but MCP tool schemas and a11y snapshots cost more context than they return. |
| `context7` | Free tier is 1.000 calls/month; anonymous is rate-limited. Duplicates what project `docs/` + `ctx_index` already cover, and adds a dependency and a second definition of "documentation" the agent has to disambiguate. Removed 2026-11-03. |
| `hangwin/mcp-chrome` | 12.5k stars, but extension-based and overlaps playwright. One browser tool is enough. |
| shadcn MCP (`@jpisnice/shadcn-ui-mcp-server`) | Only useful with shadcn. Enable it per project when `components.json` exists. |
| `headroom` | Not installed. It was a proxy MCP, not needed for this workflow. |

## Security posture
- `chrome-devtools` and `playwright-cli` run locally and talk only to the target
  URL or the npm registry.
- `playwright-cli` and `chrome-devtools` drive a browser on the machine. Do not
  point them at accounts you would not want an agent to touch.
- No secret is passed to either of them.
- Tavily is a **remote** MCP server. `bootstrap-windows.ps1 -TavilyKey` stores
  the key in the user environment and writes only
  `"Authorization": "Bearer {env:TAVILY_API_KEY}"` to the config. If you added
  it by hand, do the same; never commit the key.
- Any other remote MCP you add yourself sends its requests to that provider,
  not to your machine. Read what it sends before trusting it with a URL.

## Verify the MCP server is live
In an opencode session, ask:
```
List your MCP tools and their server names.
```
Expected: `performance_*` / `console_*` / `take_snapshot` from
`chrome-devtools`, plus the `tavily` tools.

If the server is missing:
```bash
npx -y chrome-devtools-mcp@latest --version
```

Verify the CLI separately:
```bash
playwright-cli --version
playwright-cli open https://example.com
playwright-cli close-all
```
