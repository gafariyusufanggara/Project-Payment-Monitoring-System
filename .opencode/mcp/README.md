# MCP — what runs, why, and what it costs

Two MCP servers are used for web work. Both are local (`npx`), send no
telemetry, and are required by `.opencode/sops/WEB_DEV.md` phases 5-6.

| MCP | Source | Purpose | Needs |
|---|---|---|---|
| `playwright` | `microsoft/playwright-mcp` | Real browser: resize, screenshot, click, snapshot a11y, fill forms | Node 18+, Chromium (`npx playwright install chromium`) |
| `chrome-devtools` | `ChromeDevTools/chrome-devtools-mcp` | Console, network, a11y tree, performance trace, LCP/CLS | Node 18+, Chrome installed |

## Why these two

- **playwright** is the anti-hallucination tool for UI. Without it, "it looks
  good" is a guess. It also lets a page be checked at 320/768/1440 pixels
  without a human.
- **chrome-devtools** is the only reliable way to get LCP, CLS, console errors,
  and the a11y tree. Lighthouse-style numbers are required by
  `.opencode/sops/QUALITY_GATE.md` gates 5-6.

## Library documentation: no MCP

There is deliberately no documentation MCP. Two sources cover the need:

| Source | Covers |
|---|---|
| `docs/` in the project | What to build, the chosen stack and versions |
| `ctx_fetch_and_index` + `ctx_search` | How a third-party API works today |
| `tavily` (remote MCP) | Finding the official docs URL when it is unknown |

See `.opencode/sops/CONTEXT.md` § 3b for the procedure and the rule that an unverified
library API call must not be written.

## Explicitly not used

| MCP | Why not |
|---|---|
| `context7` | Free tier is 1.000 calls/month; anonymous is rate-limited. Duplicates what project `docs/` + `ctx_fetch_and_index` already cover, and adds a dependency and a second definition of "documentation" the agent has to disambiguate. Removed 2026-11-03. |
| `hangwin/mcp-chrome` | 12.5k stars, but extension-based and overlaps playwright. One browser tool is enough. |
| shadcn MCP (`@jpisnice/shadcn-ui-mcp-server`) | Only useful with shadcn. Enable it per project when `components.json` exists. |
| `headroom` | Left in the config but `enabled: false`. It was a proxy MCP, not needed for this workflow. |

## Security posture

- Both servers run locally and talk only to the target URL or the npm registry.
- `playwright` and `chrome-devtools` drive a browser on the machine. Do not point
  them at accounts you would not want an agent to touch.
- No secret is passed to either of them.
- Tavily: `bootstrap-windows.ps1 -TavilyKey` stores the key in the user
  environment and writes only `"Authorization": "Bearer {env:TAVILY_API_KEY}"`
  to the config. If you added it by hand, do the same; never commit the key.

## Verify the MCP servers are live

In an opencode session, ask:

```
List your MCP tools and their server names.
```

Expected: `browser_*` from playwright, `performance_*` / `console_*` /
`take_snapshot` from chrome-devtools, plus the `tavily` tools.

If a server is missing:

```bash
npx -y @playwright/mcp@latest --version
npx -y chrome-devtools-mcp@latest --version
```

First run downloads the package; a few seconds each.
