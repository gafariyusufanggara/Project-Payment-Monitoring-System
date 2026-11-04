# Fresh Windows bootstrap for this SOP setup.
#
# Installs the global layer that the template cannot carry: base tools,
# opencode, rtk, graphify, plugins, MCP servers, the context-mode shell,
# Playwright browsers, and the vendored skills.
#
# Usage:
#   powershell -NoProfile -File .opencode\scripts\bootstrap-windows.ps1
#   powershell -NoProfile -File .opencode\scripts\bootstrap-windows.ps1 -DryRun
#   powershell -NoProfile -File .opencode\scripts\bootstrap-windows.ps1 -TavilyKey "tvly-..."
#   powershell -NoProfile -File .opencode\scripts\bootstrap-windows.ps1 -SkipBrowsers -SkipSkills
#
# Safe to re-run: every step checks first and skips what already exists.
# Every config edit is backed up next to the original file.

param(
  [switch]$DryRun,
  [switch]$SkipBrowsers,
  [switch]$SkipSkills,
  [string]$TavilyKey
)

$ErrorActionPreference = 'Continue'
$agentsDir = Split-Path -Parent $PSScriptRoot
$root = Split-Path -Parent $agentsDir
$cfgDir = Join-Path $env:USERPROFILE '.config\opencode'

$fail = 0
$warn = 0

function Ok($m)    { Write-Host "[OK]   $m" -ForegroundColor Green }
function Bad($m)   { Write-Host "[FAIL] $m" -ForegroundColor Red; $script:fail++ }
function Warn($m)  { Write-Host "[WARN] $m" -ForegroundColor Yellow; $script:warn++ }
function Info($m)  { Write-Host "       $m" -ForegroundColor DarkGray }
function Step($m)  { Write-Host "`n=== $m ===" -ForegroundColor Cyan }

function Run($exe, $argsArr) {
  if ($DryRun) { Write-Host "       DRY: $exe $($argsArr -join ' ')" -ForegroundColor DarkGray; return 0 }
  & $exe @argsArr
  return $LASTEXITCODE
}

function Refresh-Path {
  $machine = [Environment]::GetEnvironmentVariable('Path','Machine')
  $user    = [Environment]::GetEnvironmentVariable('Path','User')
  $extra   = @(
    (Join-Path $env:LOCALAPPDATA 'Programs\rtk'),
    (Join-Path $env:USERPROFILE '.local\bin'),
    (Join-Path $env:APPDATA 'npm')
  )
  $parts = @()
  foreach ($p in @($machine, $user) + $extra) {
    if ($p) { $parts += $p }
  }
  $env:Path = ($parts -join ';')
}

function Has-Cmd($name) {
  return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

function Install-Winget($id, $label, $probe) {
  if (Has-Cmd $probe) { Ok "$label present"; return }
  if (-not (Has-Cmd 'winget')) { Bad "winget missing; install $label manually"; return }
  Write-Host "       installing $label ($id)"
  Run 'winget' @('install','--id',$id,'-e','--source','winget','--accept-package-agreements','--accept-source-agreements','--silent') | Out-Null
  Refresh-Path
  if (Has-Cmd $probe) { Ok "$label installed" } else { Warn "$label not on PATH yet; reopen the terminal after this script" }
}

function Chrome-Present {
  $c = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
  ) | Where-Object { Test-Path $_ }
  return [bool]$c
}

function Read-Json($path) {
  if (-not (Test-Path $path)) { return $null }
  try { return (Get-Content $path -Raw | ConvertFrom-Json) } catch { return $null }
}

function Save-Json($path, $obj) {
  if ($DryRun) { Write-Host "       DRY: write $path" -ForegroundColor DarkGray; return }
  $backup = "$path.bak-bootstrap-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
  if (Test-Path $path) { Copy-Item $path $backup -Force }
  $obj | ConvertTo-Json -Depth 30 | Set-Content $path -Encoding UTF8
  if (Test-Path $backup) { Info "backup: $backup" }
}

function Get-Prop($obj, $name) {
  if ($null -eq $obj) { return $null }
  $p = $obj.PSObject.Properties[$name]
  if ($p) { return $p.Value }
  return $null
}

function Set-Prop($obj, $name, $value) {
  if ($obj.PSObject.Properties[$name]) { $obj.$name = $value }
  else { $obj | Add-Member -NotePropertyName $name -NotePropertyValue $value }
}

Write-Host "`nSOP bootstrap (Windows)" -ForegroundColor White
Write-Host "template: $root"
Write-Host "config:   $cfgDir"
if ($DryRun) { Write-Host "mode:     DRY RUN (no changes)" -ForegroundColor Yellow }

# ---------------------------------------------------------------- base tools
Step 'Base tools'

Install-Winget 'OpenJS.NodeJS.LTS' 'Node.js LTS' 'node'
Install-Winget 'Git.Git' 'Git' 'git'
Install-Winget 'astral-sh.uv' 'uv' 'uv'

if (Chrome-Present) {
  Ok 'Chrome present'
} elseif (Has-Cmd 'winget') {
  Write-Host "       installing Chrome"
  Run 'winget' @('install','--id','Google.Chrome.EXE','-e','--source','winget','--accept-package-agreements','--accept-source-agreements','--silent') | Out-Null
  if (-not (Chrome-Present)) {
    Run 'winget' @('install','--id','Google.Chrome','-e','--source','winget','--accept-package-agreements','--accept-source-agreements','--silent') | Out-Null
  }
  if (Chrome-Present) { Ok 'Chrome installed' } else { Warn 'Chrome not detected; chrome-devtools MCP needs it' }
} else {
  Warn 'winget missing; install Chrome manually'
}

Refresh-Path

# ------------------------------------------------------------------ opencode
Step 'opencode'

if (Has-Cmd 'opencode') {
  Ok "opencode present ($((Get-Command opencode).Source))"
} else {
  if (Has-Cmd 'npm') {
    Write-Host "       installing opencode-ai"
    Run 'npm' @('i','-g','opencode-ai@latest') | Out-Null
    Refresh-Path
    if (Has-Cmd 'opencode') { Ok 'opencode installed' } else { Warn 'opencode not on PATH yet; reopen the terminal' }
  } else {
    Bad 'npm missing; cannot install opencode'
  }
}

# ----------------------------------------------------------------------- rtk
Step 'rtk (token filter)'

if (Has-Cmd 'rtk') {
  Ok "rtk present ($(rtk --version 2>$null))"
} elseif (Has-Cmd 'winget') {
  Write-Host "       installing rtk-ai.rtk"
  Run 'winget' @('install','--id','rtk-ai.rtk','-e','--source','winget','--accept-package-agreements','--accept-source-agreements','--silent') | Out-Null
  Refresh-Path
  if (Has-Cmd 'rtk') { Ok 'rtk installed' } else { Warn 'rtk not on PATH yet; reopen the terminal' }
} else {
  Warn 'rtk missing; SOP commands still work but lose 60-90% context savings'
}

if (Has-Cmd 'rtk') {
  $probe = & rtk find . -maxdepth 1 -name *.md 2>&1 | Out-String
  if ($probe -match 'does not support|Failed to resolve|not found on PATH') {
    Warn "rtk version rejects the SOP flags; re-check .opencode/sops/CONTEXT.md. Output: $($probe.Trim())"
  } else {
    Ok 'rtk accepts the SOP flags'
  }
}

# ------------------------------------------------------------------ graphify
Step 'graphify (codebase graph)'

if (Has-Cmd 'graphify') {
  Ok 'graphify present'
} elseif (Has-Cmd 'uv') {
  Write-Host "       installing graphifyy"
  Run 'uv' @('tool','install','graphifyy') | Out-Null
  Refresh-Path
  if (Has-Cmd 'graphify') { Ok 'graphify installed' } else { Warn 'graphify not on PATH yet; reopen the terminal' }
} else {
  Warn 'uv missing; graphify skipped (optional)'
}

# ------------------------------------------------------------ context-mode shell
Step 'context-mode shell'

$shellExe = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$current = [Environment]::GetEnvironmentVariable('SHELL','User')
if ($current -eq $shellExe) {
  Ok "SHELL already set"
} elseif ($DryRun) {
  Write-Host "       DRY: set user SHELL=$shellExe" -ForegroundColor DarkGray
} else {
  [Environment]::SetEnvironmentVariable('SHELL', $shellExe, 'User')
  $env:SHELL = $shellExe
  Ok "SHELL -> $shellExe"
}

# --------------------------------------------------------------- opencode config
Step 'opencode config (plugins + MCP)'

if (-not (Test-Path $cfgDir)) {
  if ($DryRun) { Write-Host "       DRY: create $cfgDir" -ForegroundColor DarkGray }
  else { New-Item -ItemType Directory -Path $cfgDir -Force | Out-Null }
}

$jsonPath  = Join-Path $cfgDir 'opencode.json'
$jsoncPath = Join-Path $cfgDir 'opencode.jsonc'
$jsonObj   = Read-Json $jsonPath
$jsoncObj  = Read-Json $jsoncPath

$targetPath = $null
if ((Get-Prop $jsoncObj 'plugin') -or (Get-Prop $jsonObj 'plugin')) {
  if (Get-Prop $jsoncObj 'plugin') { $targetPath = $jsoncPath }
  else { $targetPath = $jsonPath }
} elseif (Test-Path $jsoncPath) {
  $targetPath = $jsoncPath
} else {
  $targetPath = $jsonPath
}

$cfg = Read-Json $targetPath
if ($null -eq $cfg) {
  $cfg = [pscustomobject]@{ '$schema' = 'https://opencode.ai/config.json' }
}
Info "target: $targetPath"

$desiredPlugins = @(
  'opencode-power-pack@git+https://github.com/waybarrios/opencode-power-pack.git',
  'context-mode'
)
$otherPath = if ($targetPath -eq $jsoncPath) { $jsonPath } else { $jsoncPath }
$otherObj = Read-Json $otherPath
$otherPlugins = @()
$op = Get-Prop $otherObj 'plugin'
if ($op) { $otherPlugins = @($op) }

$pluginList = @()
$existingPlugins = Get-Prop $cfg 'plugin'
if ($existingPlugins) { $pluginList = @($existingPlugins) }
$changed = $false
foreach ($p in $desiredPlugins) {
  $inTarget = $pluginList | Where-Object { $_ -eq $p -or ($_ -like 'context-mode*' -and $p -eq 'context-mode') }
  $inOther = $otherPlugins | Where-Object { $_ -eq $p -or ($_ -like 'context-mode*' -and $p -eq 'context-mode') }
  if ($inTarget) { Ok "plugin present: $p" }
  elseif ($inOther) { Ok "plugin present in the other config file: $p" }
  else { $pluginList += $p; $changed = $true; Ok "plugin added: $p" }
}
if (-not $DryRun -and $pluginList.Count -gt 0) { Set-Prop $cfg 'plugin' $pluginList }

$mcp = Get-Prop $cfg 'mcp'
if (-not $mcp) {
  $mcp = [pscustomobject]@{}
  if (-not $DryRun) { Set-Prop $cfg 'mcp' $mcp }
}

$otherMcp = Get-Prop $otherObj 'mcp'
$mcpWanted = @{
  'playwright'      = [pscustomobject]@{ type = 'local'; command = @('npx','-y','@playwright/mcp@latest'); enabled = $true }
  'chrome-devtools' = [pscustomobject]@{ type = 'local'; command = @('npx','-y','chrome-devtools-mcp@latest'); enabled = $true }
}
foreach ($k in $mcpWanted.Keys) {
  if (Get-Prop $mcp $k) { Ok "MCP present: $k" }
  elseif (Get-Prop $otherMcp $k) { Ok "MCP present in the other config file: $k" }
  elseif ($DryRun) { Write-Host "       DRY: add MCP $k" -ForegroundColor DarkGray }
  else { Set-Prop $mcp $k $mcpWanted[$k]; $changed = $true; Ok "MCP added: $k" }
}

$tavilyPresent = (Get-Prop $mcp 'tavily') -or (Get-Prop $otherMcp 'tavily')
if ($TavilyKey) {
  if ($DryRun) {
    Write-Host "       DRY: set TAVILY_API_KEY and add remote MCP tavily" -ForegroundColor DarkGray
  } else {
    [Environment]::SetEnvironmentVariable('TAVILY_API_KEY', $TavilyKey, 'User')
    $env:TAVILY_API_KEY = $TavilyKey
    $tavily = [pscustomobject]@{
      type = 'remote'
      url = 'https://mcp.tavily.com/mcp'
      oauth = $false
      enabled = $true
      headers = [pscustomobject]@{ Authorization = 'Bearer {env:TAVILY_API_KEY}' }
    }
    Set-Prop $mcp 'tavily' $tavily
    $changed = $true
    Ok 'MCP added: tavily (key stored in user env, not in config)'
  }
} elseif ($tavilyPresent) {
  Ok 'MCP present: tavily'
} else {
  Warn 'tavily MCP not configured. Re-run with -TavilyKey "tvly-..." to add it'
}

if ($changed -or -not (Test-Path $targetPath)) {
  Save-Json $targetPath $cfg
} else {
  Info 'config unchanged, not rewritten'
}

# ---------------------------------------------- context-mode package in config dir
Step 'context-mode package'

$pkgJson = Join-Path $cfgDir 'package.json'
if (-not (Test-Path $pkgJson)) {
  if ($DryRun) { Write-Host "       DRY: npm init -y in $cfgDir" -ForegroundColor DarkGray }
  else {
    Push-Location $cfgDir
    Run 'npm' @('init','-y') | Out-Null
    Pop-Location
  }
}
if (Has-Cmd 'npm') {
  if ($DryRun) {
    Write-Host "       DRY: npm i context-mode@latest in $cfgDir" -ForegroundColor DarkGray
  } else {
    Write-Host "       installing context-mode"
    Push-Location $cfgDir
    & npm i context-mode@latest --no-fund --no-audit 2>&1 | Out-Null
    $code = $LASTEXITCODE
    Pop-Location
    if ($code -eq 0) { Ok 'context-mode installed in config dir' } else { Warn 'npm install context-mode failed' }
  }
} else {
  Bad 'npm missing; context-mode plugin will not load'
}

# --------------------------------------------------------------- playwright browsers
Step 'Playwright browsers'

if ($SkipBrowsers) {
  Warn 'skipped (-SkipBrowsers)'
} elseif (-not (Has-Cmd 'npx')) {
  Warn 'npx missing; run: npx -y playwright install chromium'
} else {
  $cache = Join-Path $env:LOCALAPPDATA 'ms-playwright'
  if (Test-Path $cache) {
    $n = (Get-ChildItem $cache -Directory -ErrorAction SilentlyContinue).Count
    Ok "cache present: $n item(s)"
  } else {
    Write-Host "       downloading chromium"
    Run 'npx' @('-y','playwright','install','chromium') | Out-Null
    if (Test-Path $cache) { Ok 'chromium installed' } else { Warn 'chromium install did not complete' }
  }
}

# ------------------------------------------------------------------- skills
Step 'Global skills'

if ($SkipSkills) {
  Warn 'skipped (-SkipSkills)'
} else {
  $installer = Join-Path $PSScriptRoot 'install-skills.ps1'
  if (-not (Test-Path $installer)) {
    Warn 'install-skills.ps1 not found'
  } elseif ($DryRun) {
    Write-Host "       DRY: install-skills.ps1 -Force" -ForegroundColor DarkGray
  } else {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $installer -Force
    if ($LASTEXITCODE -eq 0) { Ok 'skills installed globally' } else { Warn 'skill install returned a non-zero exit code' }
  }
}

# --------------------------------------------------------------------- verify
Step 'Verification'

if (-not (Test-Path (Join-Path $PSScriptRoot 'check-setup.ps1'))) {
  Warn 'check-setup.ps1 not found'
} elseif ($DryRun) {
  Write-Host "       DRY: check-setup.ps1" -ForegroundColor DarkGray
} else {
  & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'check-setup.ps1')
}

Write-Host ''
if ($fail -eq 0) {
  Write-Host 'Bootstrap finished. Close and reopen the terminal, then restart opencode.' -ForegroundColor Green
} else {
  Write-Host "Bootstrap finished with $fail failure(s) and $warn warning(s). Fix the [FAIL] lines above." -ForegroundColor Yellow
}
Write-Host ''
Write-Host 'Next:' -ForegroundColor Cyan
Write-Host '  1. Restart opencode'
Write-Host '  2. Copy the template into a project:'
Write-Host "     powershell -NoProfile -File `"$PSScriptRoot\copy-to-project.ps1`" -Destination `"C:\dev\my-app`""
Write-Host '  3. In the project: /stack, then edit PROJECT_NAME in AGENTS.md'
