# MCP Install — step by step

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

Chromium for Playwright is downloaded in step 5; Chrome is used by
chrome-devtools.

## 1. Back up the config

```powershell
$c = "$env:USERPROFILE\.config\opencode"
Copy-Item "$c\opencode.json" "$c\opencode.json.bak" -Force
if (Test-Path "$c\opencode.jsonc") {
  Copy-Item "$c\opencode.jsonc" "$c\opencode.jsonc.bak" -Force
}
```

## 2. Merge the MCP block

Read `.opencode/mcp/opencode-snippet.jsonc` in this folder. Add its `"mcp"` entries into
the existing `"mcp"` object of `$env:USERPROFILE\.config\opencode\opencode.json`.
Keep any server already present (do not delete `tavily` etc.).

The two entries:

```json
"playwright":      { "type": "local", "command": ["npx","-y","@playwright/mcp@latest"], "enabled": true },
"chrome-devtools": { "type": "local", "command": ["npx","-y","chrome-devtools-mcp@latest"], "enabled": true }
```

Validate the JSON before restarting opencode:

```powershell
node -e "const a=require('$env:USERPROFILE/.config/opencode/opencode.json'.replace(/\\/g,'/')); console.log('OK', Object.keys(a.mcp))"
```

## 3. Install Chromium for Playwright

```powershell
npx -y playwright install chromium
```

~150 MB on first run. Skip only if you will never take screenshots (you will).

## 4. Warm both servers

First run of each downloads the package, so run them once outside opencode:

```powershell
npx -y @playwright/mcp@latest --help
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
| playwright | `browser_navigate`, `browser_resize`, `browser_take_screenshot`, `browser_snapshot`, `browser_click`, `browser_type` |
| chrome-devtools | `navigate_page`, `take_snapshot`, `performance_start_trace`, `performance_stop_trace`, `list_console_messages`, `list_network_requests` |

If one is missing, check the opencode log for the server start error, then rerun
the matching `--help` command from step 4.

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

## Re-applying the VibeSkills MCP override

VibeSkills ships a policy that forbids playwright, chrome-devtools,
and chrome. This repo's vendored copy already overrides it. After a VibeSkills
update, re-apply:

```powershell
$p = "skills\vibe\config\forbidden-mcp-policy.json"
node -e "const fs=require('fs');const f='$($p -replace '\\','/')';const j=JSON.parse(fs.readFileSync(f,'utf8'));j.installation='allowed';j.runtime_recommendation='allowed';j.forbidden_mcp_ids=[];j.reason='Local override: browser MCP required for UI verification (.opencode/sops/DESIGN.md, .opencode/sops/WEB_DEV.md).';j.updated_at=new Date().toISOString().slice(0,10);fs.writeFileSync(f,JSON.stringify(j,null,2));console.log('patched')"
```

Confirm:

```powershell
node -e "console.log(JSON.stringify(require('./skills/vibe/config/forbidden-mcp-policy.json').forbidden_mcp_ids))"
```

Expected: `[]`.

---

## Uninstall

Remove the three entries from `opencode.json`'s `"mcp"` object and restart
opencode. The packages live in the npm cache; nothing else needs cleaning.
