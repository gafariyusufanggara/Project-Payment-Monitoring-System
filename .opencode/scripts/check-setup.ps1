# Setup check — verifies this SOP folder can run a coding agent.
# Usage: powershell -NoProfile -File .opencode\scripts\check-setup.ps1
#        powershell -NoProfile -File .opencode\scripts\check-setup.ps1 -FirstRun
#
# -FirstRun downgrades the global-layer checks (config, MCP, SHELL, Chrome) to
# warnings, so a fresh Windows machine can verify the template before running
# bootstrap-windows.ps1.

param(
  [switch]$FirstRun
)

$ErrorActionPreference = 'Continue'
$agentsDir = Split-Path -Parent $PSScriptRoot        # .opencode
$root = Split-Path -Parent $agentsDir                # project root
$fail = 0
$warn = 0

function Ok($msg)   { Write-Host "[OK]   $msg" -ForegroundColor Green }
function Bad($msg)  { Write-Host "[FAIL] $msg" -ForegroundColor Red; $script:fail++ }
function Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow; $script:warn++ }
function Gate($msg) { if ($FirstRun) { Warn $msg } else { Bad $msg } }

Write-Host "`n=== Toolchain ===" -ForegroundColor Cyan

foreach ($t in @('node','npm','git','npx','opencode')) {
  $c = Get-Command $t -ErrorAction SilentlyContinue
  if ($c) { Ok "$t -> $($c.Source)" } else { Gate "$t not found on PATH" }
}

if (Get-Command rtk -ErrorAction SilentlyContinue) {
  Ok "rtk -> $((Get-Command rtk).Source)"
} else {
  Warn "rtk not found. Commands still work but context savings are lost. Install: cargo install rtk (or the rtk release binary)."
}

if (Get-Command graphify -ErrorAction SilentlyContinue) {
  Ok "graphify -> $((Get-Command graphify).Source)"
  $gv = & graphify --version 2>&1 | Out-String
  if ($gv -match 'warning: skill .* is from graphify') {
    Warn "graphify skill/package drift detected. Run once: graphify install"
  }
} else {
  Warn "graphify not found. Run: uv tool install graphifyy"
}

Write-Host "`n=== context-mode shell ===" -ForegroundColor Cyan

$shellVal = [Environment]::GetEnvironmentVariable('SHELL','User')
if (-not $shellVal) { $shellVal = $env:SHELL }
if ($shellVal -and (Test-Path $shellVal)) {
  $base = Split-Path $shellVal -Leaf
  if ($base -match '^(bash|sh|zsh|dash|pwsh|powershell|cmd)(\.exe)?$') {
    Ok "SHELL -> $shellVal"
  } else {
    Bad "SHELL basename '$base' is not allowlisted by context-mode (allowed: bash, sh, zsh, dash, pwsh, powershell, cmd)"
  }
} else {
  Gate "SHELL unset or missing. ctx_batch_execute fails on Windows with: Executable not found in PATH: pwsh"
  Warn "Fix: [Environment]::SetEnvironmentVariable('SHELL','C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe','User') then restart opencode"
}

Write-Host "`n=== Browser ===" -ForegroundColor Cyan

$chrome = @(
  "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
  "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
  "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($chrome) { Ok "Chrome -> $chrome" } else { Gate "Chrome not found (chrome-devtools MCP needs it)" }

$pwCache = Join-Path $env:LOCALAPPDATA 'ms-playwright'
if (Test-Path $pwCache) {
  $n = (Get-ChildItem $pwCache -Directory -ErrorAction SilentlyContinue).Count
  Ok "Playwright browser cache: $n item(s) in $pwCache"
} else {
  Warn "No Playwright browser cache. Run: npx -y playwright install chromium"
}

Write-Host "`n=== opencode config ===" -ForegroundColor Cyan

$cfgDir = Join-Path $env:USERPROFILE '.config\opencode'
$cfgJson = Join-Path $cfgDir 'opencode.json'
if (Test-Path $cfgJson) {
  Ok "opencode.json found"
  $raw = Get-Content $cfgJson -Raw
  foreach ($m in @('playwright','chrome-devtools')) {
    if ($raw -match "`"$([regex]::Escape($m))`"") { Ok "MCP declared: $m" }
    else { Gate "MCP missing from opencode.json: $m (see .opencode/mcp/INSTALL.md)" }
  }
  if ($raw -match '"context7"') {
    Warn "context7 is still declared. It was dropped from this setup: project docs/ + ctx_fetch_and_index cover library docs. See .opencode/mcp/README.md."
  } else {
    Ok "context7 not declared (expected)"
  }
  foreach ($p in @('context-mode','opencode-power-pack')) {
    if ($raw -match [regex]::Escape($p)) { Ok "plugin declared: $p" }
    else { Warn "plugin not declared: $p" }
  }
} else {
  Gate "opencode.json not found at $cfgJson"
}

Write-Host "`n=== Layout ===" -ForegroundColor Cyan

if (Test-Path (Join-Path $root 'AGENTS.md')) {
  Ok "AGENTS.md at project root (opencode reads it automatically)"
  if (-not (Test-Path (Join-Path $root 'CARA PAKAI.md'))) {
    $agentsRaw = Get-Content (Join-Path $root 'AGENTS.md') -Raw
    if ($agentsRaw -match 'PROJECT_NAME') {
      Warn "AGENTS.md still contains the PROJECT_NAME placeholder; replace it with the project name"
    } else {
      Ok "PROJECT_NAME replaced"
    }
  }
} else {
  Bad "AGENTS.md missing from project root"
}

foreach ($stray in @('sops','agents','commands','skills','instructions','mcp','scripts')) {
  if (Test-Path (Join-Path $root $stray)) {
    Warn "stray '$stray/' at project root; everything agent-related belongs in .opencode/"
  }
}
foreach ($junk in @('Microsoft','rtk')) {
  if (Test-Path (Join-Path $root $junk)) {
    Warn "stray '$junk/' at project root: cache/history artifact (usually from running PowerShell or rtk with a redirected USERPROFILE). Safe to delete."
  }
}
if (Test-Path (Join-Path $root 'README.md')) {
  Warn "README.md at project root: that is usually the project's own readme. The SOP readme lives in .opencode/README.md"
}
Ok "root: $(($((Get-ChildItem $root -Force)).Name) -join ', ')"

Write-Host "`n=== SOP files ===" -ForegroundColor Cyan

$required = @(
  'AGENTS.md','.opencode/README.md',
  '.opencode/sops/WEB_DEV.md','.opencode/sops/DESIGN.md','.opencode/sops/QUALITY_GATE.md','.opencode/sops/CONTEXT.md','.opencode/sops/STACKS.md',
  '.opencode/sops/context/TROUBLESHOOTING.md',
  '.opencode/sops/stacks/nextjs.md','.opencode/sops/stacks/vue.md','.opencode/sops/stacks/svelte.md',
  '.opencode/sops/stacks/astro.md','.opencode/sops/stacks/vite.md','.opencode/sops/stacks/python.md',
  '.opencode/sops/stacks/go.md','.opencode/sops/stacks/rust.md','.opencode/sops/stacks/_template.md',
  '.opencode/agents/develop.md','.opencode/agents/ui-designer.md','.opencode/agents/reviewer.md','.opencode/agents/planner.md',
  '.opencode/commands/ship.md','.opencode/commands/new-feature.md','.opencode/commands/ui-audit.md','.opencode/commands/build-ui.md','.opencode/commands/stack.md','.opencode/commands/i-have-adhd.md',
  '.opencode/scripts/bootstrap-windows.ps1','.opencode/scripts/copy-to-project.ps1','.opencode/scripts/install-skills.ps1','.opencode/scripts/lib-jsonc.ps1','.opencode/scripts/check-template.ps1',
  '.opencode/instructions/ADHD.md','.opencode/instructions/ALWAYS-ON.md',
  '.opencode/plugins/graphify-auto-update.js',
  '.opencode/skills/hallmark/SKILL.md','.opencode/skills/hallmark/scripts/sloplint.mjs',
  '.opencode/skills/refactoring-ui/SKILL.md','.opencode/skills/design-taste/SKILL.md',
  '.opencode/skills/i-have-adhd/SKILL.md',
  '.opencode/mcp/README.md','.opencode/mcp/INSTALL.md','.opencode/mcp/opencode-snippet.jsonc'
)
foreach ($f in $required) {
  $p = Join-Path $root ($f -replace '/','\')
  if (Test-Path $p) { Ok $f } else { Bad "missing: $f" }
}

Write-Host "`n=== Removed skills ===" -ForegroundColor Cyan
$vibe = Join-Path $root '.opencode\skills\vibe'
if (Test-Path $vibe) {
  Warn "vibe is still vendored at .opencode/skills/vibe (broken, unused, ~3.5 MB). Delete it."
} else {
  Ok "vibe not present (removed)"
}

Write-Host "`n=== sloplint smoke test ===" -ForegroundColor Cyan
$lint = Join-Path $root '.opencode\skills\hallmark\scripts\sloplint.mjs'
if ((Test-Path $lint) -and (Get-Command node -ErrorAction SilentlyContinue)) {
  $out = & node $lint --help 2>&1 | Out-String
  if ($LASTEXITCODE -eq 0 -or $out -match 'Usage|sloplint') { Ok "sloplint runs" }
  else { Warn "sloplint ran with unexpected output: $($out.Substring(0,[Math]::Min(200,$out.Length)))" }
} else {
  Bad "sloplint.mjs missing or node unavailable"
}

Write-Host "`n=== rtk smoke test ===" -ForegroundColor Cyan
if (Get-Command rtk -ErrorAction SilentlyContinue) {
  $r = & rtk find . -maxdepth 1 -name *.md 2>&1 | Out-String
  if ($r -match 'does not support|not found on PATH|Failed to resolve') {
    Bad "rtk find rejected the SOP flags: $($r.Trim().Substring(0,[Math]::Min(160,$r.Trim().Length)))"
  } else {
    Ok "rtk find accepts unquoted globs and -maxdepth"
  }
  $pkg = Join-Path $agentsDir 'package.json'
  if (Test-Path $pkg) {
    $j = & rtk json $pkg 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0 -or $j -match 'is not a JSON file|not found|Failed') {
      Bad "rtk json failed on .opencode/package.json: $($j.Trim())"
    } else {
      Ok "rtk json parses .opencode/package.json"
    }
  } else {
    Warn "skipped rtk json check: .opencode/package.json absent"
  }
} else {
  Warn "rtk not installed; skipped"
}

Write-Host "`n=== Summary ===" -ForegroundColor Cyan
Write-Host "failures: $fail   warnings: $warn"
if ($fail -eq 0) {
  Write-Host "Setup is usable." -ForegroundColor Green
  exit 0
} else {
  Write-Host "Fix the [FAIL] items, then re-run this script." -ForegroundColor Red
  exit 1
}
