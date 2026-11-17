# MCP + browser install — step by step

All commands are PowerShell 5.1. Run as the same user that runs opencode.
`~` means `C:\Users\<you>`.

Fast path: `.opencode/scripts/bootstrap-windows.ps1` performs every step below
and verifies the result. Use this document when you want to install manually or
understand what the script changed.

---

## 0. Prerequisites

| Need | Check | If missing |
|---|---|---|
| Node 18+ | `node --version` | https://nodejs.org (LTS) |
| npm 9+ | `npm --version` | ships with Node |
| Chrome | open Chrome once | https://google.com/chrome |
| Git | `git --version` | https://git-scm.com |
| opencode | `opencode --version` | `npm i -g opencode-ai` |

Chromium for the Playwright CLI is downloaded in step 4; Chrome is used by
chrome-devtools.

## 1. Back up the config

```powershell
$c = "$env:USERPROFILE\.config\opencode"
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
Copy-Item "$c\opencode.json" "$c\opencode.json.bak-$stamp" -Force
if (Test-Path "$c\opencode.jsonc") {
  Copy-Item "$c\opencode.jsonc" "$c\opencode.jsonc.bak-$stamp" -Force
}
```
`bootstrap-windows.ps1` uses the same `<file>.bak-bootstrap-<timestamp>` naming
when it rewrites the config, so both kinds of backup are restored the same way.

## 2. Merge the MCP block

Read `.opencode/mcp/opencode-snippet.jsonc` in this folder. Add its `"mcp"`
entries into the existing `"mcp"` object of
`$env:USERPROFILE\.config\opencode\opencode.json`. Keep any server already
present (do not delete `tavily` etc.).

The entry:

```json
"chrome-devtools": { "type": "local", "command": ["npx","-y","chrome-devtools-mcp@latest"], "enabled": true }
```

There is deliberately **no** `playwright` MCP server. Browser interaction runs
through the Playwright CLI (step 3) so the agent does not carry a large tool
schema and accessibility snapshots in every turn.

Validate the JSON before restarting opencode:

```powershell
node -e "const a=require('$env:USERPROFILE/.config/opencode/opencode.json'.replace(/\\/g,'/')); console.log('OK', Object.keys(a.mcp.servers))"
```

## 3. Install the Playwright CLI and its skill

```powershell
npm install -g @playwright/cli@latest
playwright-cli install-browser
playwright-cli install --skills agents --global
```

`install-browser` downloads Chromium (~150 MB, first run only).
`install --skills agents --global` writes the skill to `~\.agents\skills`;
copy it into opencode's global skills folder so the agent picks it up:

```powershell
Copy-Item "$env:USERPROFILE\.agents\skills\playwright-cli" `
          "$env:USERPROFILE\.config\opencode\skills\playwright-cli" -Recurse -Force
```

The CLI also needs a browser choice. `playwright-cli install` writes
`~\.playwright\cli.config.json`; if it is missing, the CLI fails with
"Chromium distribution 'chrome' is not found". Fix it with:

```powershell
New-Item -ItemType Directory -Path "$env:USERPROFILE\.playwright" -Force | Out-Null
'{"browser":{"browserName":"chromium"}}' |
  Set-Content "$env:USERPROFILE\.playwright\cli.config.json" -Encoding UTF8
```

## 4. Warm the MCP server

First run downloads the package, so run it once outside opencode:

```powershell
npx -y chrome-devtools-mcp@latest --help
```

No error means the package resolves. Then restart opencode.

## 5. Verify inside opencode

Open a session and ask:

```
List your MCP tools and their server names.
```

Expected tool families:

| Server | Tool names you should see |
|---|---|
| chrome-devtools | `navigate_page`, `take_snapshot`, `performance_start_trace`, `performance_stop_trace`, `list_console_messages`, `list_network_requests`, `take_screenshot` |

The Playwright CLI is not an MCP server, so it does not appear in that list.
Verify it separately from a shell:

```powershell
playwright-cli --version
playwright-cli open https://example.com
playwright-cli snapshot
playwright-cli close-all
```

If the MCP server is missing, check the opencode log for the server start
error, then rerun the `--help` command from step 4.

---

## Optional: shadcn MCP (per project)

Only for projects that use shadcn/ui (`components.json` present). Add to the
project's `.opencode/opencode.json` or the global config:

```json
"shadcn": {
  "type": "local",
  "command": ["npx", "-y", "@jpisnice/shadcn-ui-mcp-server"],
  "enabled": true
}
```

---

## Uninstall

Remove the `chrome-devtools` and optional `tavily` entries from the `"mcp"`
object and restart opencode. Then:

```powershell
npm uninstall -g @playwright/cli
Remove-Item "$env:USERPROFILE\.config\opencode\skills\playwright-cli" -Recurse -Force
```

The npm packages live in the npm cache; nothing else needs cleaning.
