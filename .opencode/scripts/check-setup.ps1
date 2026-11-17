# Setup check - verifies this SOP folder can run a coding agent.
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

# USERPROFILE can be empty in some child-process contexts, and Join-Path then
# fails with "cannot bind argument to parameter 'Path' because it is null".
$userHome = $env:USERPROFILE
if (-not $userHome) { $userHome = $HOME }
if (-not $userHome) { $userHome = [Environment]::GetFolderPath('UserProfile') }

# The template ships a Setup.bat and is not a project. In the template some
# things that are wrong in a project are correct by design, so they are
# reported as information instead of warnings.
$isTemplate = (Test-Path (Join-Path $root 'Setup.bat'))

function Ok($msg)   { Write-Host "[OK]   $msg" -ForegroundColor Green }
function Bad($msg)  { Write-Host "[FAIL] $msg" -ForegroundColor Red; $script:fail++ }
function Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow; $script:warn++ }
function Gate($msg) { if ($FirstRun) { Warn $msg } else { Bad $msg } }
function Note($msg) { Write-Host "[INFO] $msg" -ForegroundColor DarkGray }

Write-Host "`n=== Toolchain ===" -ForegroundColor Cyan

foreach ($t in @('node','npm','git','npx','opencode')) {
  $c = Get-Command $t -ErrorAction SilentlyContinue
  if ($c) { Ok "$t -> $($c.Source)" } else { Gate "$t not found on PATH" }
}

if (Get-Command rtk -ErrorAction SilentlyContinue) {
  Ok "rtk -> $((Get-Command rtk).Source)"
  $rv = & rtk --version 2>&1 | Out-String
  Ok "rtk version: $($rv.Trim())"
  # rtk proxies real binaries; these must exist on PATH for the SOP commands.
  foreach ($pair in @(@('rg','ripgrep'), @('grep','Git usr\bin'), @('wc','Git usr\bin'))) {
    $bin = $pair[0]; $src = $pair[1]
    $cmd = Get-Command $bin -ErrorAction SilentlyContinue
    if ($cmd) { Ok "  helper on PATH: $bin ($src)" }
    else { Warn "  helper missing: $bin - rtk $bin will fail. Source: $src" }
  }
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

if (-not $chrome) {
  $cftRoot = Join-Path $env:LOCALAPPDATA 'chrome-for-testing\chrome'
  if (Test-Path $cftRoot) {
    $chrome = Get-ChildItem $cftRoot -Directory -ErrorAction SilentlyContinue |
              ForEach-Object { Join-Path $_.FullName 'chrome-win64\chrome.exe' } |
              Where-Object { Test-Path $_ } | Select-Object -First 1
  }
}

if ($chrome) { Ok "Chrome -> $chrome" } else { Gate "Chrome not found (chrome-devtools MCP needs it)" }
$pwCli = Get-Command playwright-cli -ErrorAction SilentlyContinue
if ($pwCli) { Ok "playwright-cli -> $($pwCli.Source)" } else { Gate "playwright-cli missing. Run: npm install -g @playwright/cli@latest" }

$pwSkill = Join-Path $userHome '.config\opencode\skills\playwright-cli\SKILL.md'
if (Test-Path $pwSkill) { Ok 'playwright-cli skill installed' } else { Warn "playwright-cli skill missing. Run: playwright-cli install --skills agents --global" }

$pwCfg = Join-Path $userHome '.playwright\cli.config.json'
if (Test-Path $pwCfg) { Ok "playwright-cli config -> $pwCfg" } else { Warn "playwright-cli global config missing; the CLI may fail to pick a browser. Run: playwright-cli install" }

$pwCache = Join-Path $env:LOCALAPPDATA 'ms-playwright'
if (Test-Path $pwCache) {
  $n = (Get-ChildItem $pwCache -Directory -ErrorAction SilentlyContinue).Count
  Ok "Playwright browser cache: $n item(s) in $pwCache"
} else {
  Warn "No Playwright browser cache. Run: playwright-cli install-browser"
}

$globalAgents = Join-Path $userHome '.config\opencode\AGENTS.md'
if (Test-Path $globalAgents) {
  Ok "global AGENTS.md -> $globalAgents"
} else {
  Warn "global AGENTS.md missing. opencode auto-loads it in every session; copy .opencode\instructions\ALWAYS-ON.md there."
}

Write-Host "`n=== opencode config ===" -ForegroundColor Cyan

$cfgDir = Join-Path $userHome '.config\opencode'
$cfgJson = Join-Path $cfgDir 'opencode.json'
if (Test-Path $cfgJson) {
  Ok "opencode.json found"
  $raw = Get-Content $cfgJson -Raw
  foreach ($m in @('chrome-devtools')) {
    if ($raw -match "`"$([regex]::Escape($m))`"") { Ok "MCP declared: $m" }
    else { Gate "MCP missing from opencode.json: $m (see .opencode/mcp/INSTALL.md)" }
  }
  if ($raw -match '"@playwright/mcp"') {
    Warn "playwright MCP is still declared. It was replaced by the Playwright CLI (token-efficient). See .opencode/mcp/README.md."
  } else {
    Ok "playwright MCP not declared (expected)"
  }
  if ($raw -match '"context7"') {
    Warn "context7 is still declared. It was dropped from this setup: project docs/ + ctx_fetch_and_index cover library docs. See .opencode/mcp/README.md."
  } else {
    Ok "context7 not declared (expected)"
  }
  foreach ($p in @('context-mode')) {
    if ($raw -match [regex]::Escape($p)) {
      Ok "plugin declared: $p"
      # opencode resolves a package plugin from its own npm cache at
      # ~/.cache/opencode/npm/<package>@latest and installs it on first use.
      # A copy in the global npm root or in the config directory is never
      # loaded, so it does not count as installed.
      $cmCache = Join-Path $userHome '.cache\opencode\npm\context-mode@latest'
      if (Test-Path $cmCache) {
        Ok "context-mode package available in the opencode npm cache"
      } else {
        Note "context-mode is not downloaded yet; opencode fetches it on first use (needs network)"
      }
    }
    else { Warn "plugin not declared: $p" }
  }
  if ($raw -match 'opencode-power-pack') {
    Warn "opencode-power-pack is still declared. It was retired: the local SOP, agents, and commands replace it. See .opencode/mcp/README.md."
  } else {
    Ok "opencode-power-pack not declared (expected)"
  }

  # The chrome-devtools MCP can carry an absolute --executablePath. That path
  # names a versioned folder (chrome-for-testing/chrome/win64-<version>), so it
  # goes stale as soon as Chrome updates. Detect that and point at the fix.
  $cfgObj = $null
  try { $cfgObj = $raw | ConvertFrom-Json } catch { $cfgObj = $null }
  if ($cfgObj) {
    $cdt = $null
    $srv = $cfgObj.mcp.servers
    if (-not $srv) { $srv = $cfgObj.mcp }
    if ($srv) { $cdt = $srv.'chrome-devtools' }
    if ($cdt -and $cdt.command) {
      $cmdArr = @($cdt.command)
      $idx = [array]::IndexOf($cmdArr, '--executablePath')
      if ($idx -ge 0 -and ($idx + 1) -lt $cmdArr.Count) {
        $cfgChrome = $cmdArr[$idx + 1]
        if (Test-Path $cfgChrome) {
          Ok "configured Chrome path -> $cfgChrome"
        } else {
          Gate "the chrome-devtools MCP points at a Chrome path that no longer exists: $cfgChrome"
          Warn "Fix: run powershell -NoProfile -ExecutionPolicy Bypass -File .opencode\scripts\bootstrap-windows.ps1 -SkipProject to rewrite the path"
        }
      } else {
        Ok "chrome-devtools MCP uses the default browser (no hardcoded path)"
      }
    }
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
      # In the template the placeholder is intentional: it is what the user
      # replaces in the project it is copied into.
      if ($isTemplate) { Note "AGENTS.md contains the PROJECT_NAME placeholder (expected in the template)" }
      else { Warn "AGENTS.md still contains the PROJECT_NAME placeholder; replace it with the project name" }
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
  # The template ships its own README plus SETUP.md. In a project, a root
  # README is normally the project's own file, so it is expected there and
  # must not be treated as a problem.
  if ($isTemplate) { Note "README.md at the template root (the setup guide is SETUP.md)" }
  else { Note "README.md at project root (the project's own readme)" }
}

# Skills are project-local by design. Every agent and command in this SOP
# references them by a project relative path, and sloplint.mjs is executed
# from that path, so a global copy is a duplicate that is never used.
$vendoredSkills = @('design-taste','hallmark','i-have-adhd','refactoring-ui')
foreach ($v in $vendoredSkills) {
  $local = Join-Path $root ".opencode\skills\$v\SKILL.md"
  if (-not (Test-Path $local)) {
    Bad "project skill missing: .opencode/skills/$v/SKILL.md"
  }
  $globalCopy = Join-Path $userHome ".config\opencode\skills\$v\SKILL.md"
  if (Test-Path $globalCopy) {
    Warn "duplicate global skill '$v': it is also in .opencode/skills/. Global copies are never used; run bootstrap-windows.ps1 to remove them."
  }
}
Ok "root: $(($((Get-ChildItem $root -Force)).Name) -join ', ')"

Write-Host "`n=== SOP files ===" -ForegroundColor Cyan

$required = @(
  'AGENTS.md','.gitignore',
  '.opencode/sops/WEB_DEV.md','.opencode/sops/DESIGN.md','.opencode/sops/QUALITY_GATE.md','.opencode/sops/CONTEXT.md','.opencode/sops/STACKS.md',
  '.opencode/sops/context/TROUBLESHOOTING.md',
  '.opencode/sops/stacks/nextjs.md','.opencode/sops/stacks/vue.md','.opencode/sops/stacks/svelte.md',
  '.opencode/sops/stacks/astro.md','.opencode/sops/stacks/vite.md','.opencode/sops/stacks/python.md',
  '.opencode/sops/stacks/go.md','.opencode/sops/stacks/rust.md','.opencode/sops/stacks/_template.md',
  '.opencode/agents/develop.md','.opencode/agents/ui-designer.md','.opencode/agents/reviewer.md','.opencode/agents/planner.md',
  '.opencode/commands/ship.md','.opencode/commands/new-feature.md','.opencode/commands/ui-audit.md','.opencode/commands/build-ui.md','.opencode/commands/stack.md','.opencode/commands/i-have-adhd.md',
  '.opencode/scripts/bootstrap-windows.ps1','.opencode/scripts/copy-to-project.ps1','.opencode/scripts/install-skills.ps1','.opencode/scripts/lib-jsonc.ps1','.opencode/scripts/check-template.ps1','.opencode/scripts/setup-menu.ps1',
  '.opencode/instructions/ALWAYS-ON.md',
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

# Setup.bat lives in the template root only, it is not copied into projects.
# It is required in the template and absent (on purpose) in a project.
$setupBat = Join-Path $root 'Setup.bat'
if (Test-Path $setupBat) {
  Ok 'Setup.bat'
} elseif (Test-Path (Join-Path $root '.opencode\scripts\setup-menu.ps1')) {
  Ok 'Setup.bat not here (expected in a project; setup-menu.ps1 is present)'
} else {
  Bad 'missing: Setup.bat'
}

# The .gitignore must cover the files the SOP generates. A project that is
# missing one of them ends up committing generated output.
$giPath = Join-Path $root '.gitignore'
if (Test-Path $giPath) {
  $giText = Get-Content $giPath -Raw
  $giNeed = @('node_modules/', '.opencode/STACK.md', 'graphify-out/')
  $giMissing = @($giNeed | Where-Object { $giText -notmatch [regex]::Escape($_) })
  if ($giMissing.Count -eq 0) {
    Ok '.gitignore covers the generated files'
  } else {
    Warn ".gitignore is missing: $($giMissing -join ', ')"
  }
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
  # Test rtk json against a JSON file that always exists. The SOP uses
  # "rtk json package.json" on the project manifest, which is absent until the
  # project has one, so checking a temp file verifies the command itself.
  $probeJson = Join-Path ([System.IO.Path]::GetTempPath()) "rtk-json-probe-$PID.json"
  try {
    '{ "rtk": "probe", "ok": true }' | Set-Content -LiteralPath $probeJson -Encoding ASCII
    $j = & rtk json $probeJson 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0 -or $j -match 'is not a JSON file|not found|Failed') {
      Bad "rtk json failed on a valid JSON file: $($j.Trim())"
    } else {
      Ok "rtk json parses a valid JSON file"
    }
  } finally {
    if (Test-Path $probeJson) { Remove-Item -LiteralPath $probeJson -Force }
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
