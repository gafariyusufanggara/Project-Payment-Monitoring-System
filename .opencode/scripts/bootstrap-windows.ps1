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
#   powershell -NoProfile -File .opencode\scripts\bootstrap-windows.ps1 -Project "C:\dev\my-app"
#
# -Project copies the SOP into that folder and sets it up in one pass.
# -SkipProject leaves the project copy for later.
# -Force overwrites the SOP folders in an existing project.
# Safe to re-run: every step checks first and skips what already exists.
# Every config edit is backed up next to the original file.

param(
  [switch]$DryRun,
  [switch]$SkipBrowsers,
  [switch]$SkipSkills,
  [switch]$SkipProject,
  [switch]$Force,
  [string]$TavilyKey,
  [string]$Project
)

$ErrorActionPreference = 'Continue'
$agentsDir = Split-Path -Parent $PSScriptRoot
$root = Split-Path -Parent $agentsDir

# USERPROFILE can be empty in some child-process contexts, and Join-Path then
# fails with "cannot bind argument to parameter 'Path' because it is null".
$userHome = $env:USERPROFILE
if (-not $userHome) { $userHome = $HOME }
if (-not $userHome) { $userHome = [Environment]::GetFolderPath('UserProfile') }

$cfgDir = Join-Path $userHome '.config\opencode'
. (Join-Path $PSScriptRoot 'lib-jsonc.ps1')

$fail = 0
$warn = 0

function Ok($m)    { Write-Host "[OK]   $m" -ForegroundColor Green }
function Bad($m)   { Write-Host "[FAIL] $m" -ForegroundColor Red; $script:fail++ }
function Warn($m)  { Write-Host "[WARN] $m" -ForegroundColor Yellow; $script:warn++ }
function Info($m)  { Write-Host "       $m" -ForegroundColor DarkGray }
function Step($m)  { Write-Host "`n=== $m ===" -ForegroundColor Cyan }

# The opencode config directory is the target of several steps (global AGENTS.md,
# graphify's plugin, the context-mode package, the playwright skill). Create it
# once, up front, so no step depends on an earlier one having run first.
if (-not (Test-Path $cfgDir)) {
  if ($DryRun) { Write-Host "       DRY: create $cfgDir" -ForegroundColor DarkGray }
  else { New-Item -ItemType Directory -Path $cfgDir -Force | Out-Null }
}

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
    (Join-Path $userHome '.local\bin'),
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
  ) | Where-Object { Test-Path $_ } | Select-Object -First 1
  if ($c) { return $c }
  return $null
}

function Chrome-For-Testing-Exe {
  $root = Join-Path $env:LOCALAPPDATA 'chrome-for-testing\chrome'
  if (-not (Test-Path $root)) { return $null }
  # Pick the newest version folder. The folder name carries the version
  # (win64-<version>), so sort descending instead of taking an arbitrary one:
  # a stale path in opencode.json breaks the chrome-devtools MCP.
  $hit = Get-ChildItem $root -Directory -ErrorAction SilentlyContinue |
         Sort-Object Name -Descending |
         ForEach-Object { Join-Path $_.FullName 'chrome-win64\chrome.exe' } |
         Where-Object { Test-Path $_ } | Select-Object -First 1
  return $hit
}

function Ensure-Chrome {
  if (Chrome-Present) { Ok 'Chrome present'; return (Chrome-Present) }
  if (Has-Cmd 'winget') {
    Write-Host "       installing Chrome via winget"
    Run 'winget' @('install','--id','Google.Chrome.EXE','-e','--source','winget','--accept-package-agreements','--accept-source-agreements','--silent') | Out-Null
    if (-not (Chrome-Present)) {
      Run 'winget' @('install','--id','Google.Chrome','-e','--source','winget','--accept-package-agreements','--accept-source-agreements','--silent') | Out-Null
    }
    if (Chrome-Present) { Ok 'Chrome installed'; return (Chrome-Present) }
  }
  $cft = Chrome-For-Testing-Exe
  if ($cft) { Ok "Chrome for Testing present: $cft"; return $cft }
  if (-not (Has-Cmd 'npx')) { Warn 'npx missing; install Chrome manually'; return $null }
  $dest = Join-Path $env:LOCALAPPDATA 'chrome-for-testing'
  Write-Host "       downloading Chrome for Testing to $dest"
  Run 'npx' @('-y','@puppeteer/browsers','install','chrome@stable','--path',$dest) | Out-Null
  $cft = Chrome-For-Testing-Exe
  if ($cft) { Ok "Chrome for Testing installed: $cft"; return $cft }
  Warn 'Chrome not available; chrome-devtools MCP needs it'
  return $null
}

function Save-Json($path, $obj) {
  if ($DryRun) { Write-Host "       DRY: write $path" -ForegroundColor DarkGray; return }
  $backup = "$path.bak-bootstrap-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
  if (Test-Path $path) { Copy-Item $path $backup -Force }
  try {
    Write-JsonFile -Path $path -Object $obj
    if (Test-Path $backup) { Info "backup: $backup" }
  } catch {
    Bad "failed to write $path : $($_.Exception.Message)"
  }
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

$chromeExe = Ensure-Chrome
Refresh-Path

# ------------------------------------------------------------------ sloplint render
# sloplint --render (Hallmark) needs puppeteer-core (global npm root) and a Chrome
# binary via CHROME_PATH. Without them the gate silently drops to the static tier.
Step 'sloplint render deps'
if (Has-Cmd 'npm') {
  $groot = (& npm root -g 2>$null); if ($groot) { $groot = "$groot".Trim() }
  if ($groot -and (Test-Path (Join-Path $groot 'puppeteer-core'))) { Ok 'puppeteer-core present' }
  elseif ($DryRun) { Write-Host '       DRY: npm install -g puppeteer-core' -ForegroundColor DarkGray }
  else {
    Write-Host '       installing puppeteer-core'
    Run 'npm' @('install','-g','puppeteer-core') | Out-Null
    $g2 = (& npm root -g 2>$null); if ($g2) { $g2 = "$g2".Trim() }
    if ($g2 -and (Test-Path (Join-Path $g2 'puppeteer-core'))) { Ok 'puppeteer-core installed' } else { Warn 'puppeteer-core install did not resolve; sloplint --render stays static' }
  }
} else { Warn 'npm missing; sloplint --render stays static until puppeteer-core is installed' }
if ($chromeExe) {
  $curChrome = [Environment]::GetEnvironmentVariable('CHROME_PATH','User')
  if ($curChrome -eq $chromeExe) { Ok "CHROME_PATH already set" }
  elseif ($DryRun) { Write-Host "       DRY: set user CHROME_PATH=$chromeExe" -ForegroundColor DarkGray }
  else {
    [Environment]::SetEnvironmentVariable('CHROME_PATH', $chromeExe, 'User')
    $env:CHROME_PATH = $chromeExe
    Ok "CHROME_PATH -> $chromeExe"
  }
} else { Warn 'Chrome not resolved; CHROME_PATH not set, sloplint --render stays static' }

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

# rtk proxies real binaries. On Windows it needs Git's usr\bin (grep, wc, ls,
# find) and ripgrep (rg) on PATH, or several subcommands fail with
# "Binary 'rg' not found on PATH".
Step 'rtk helper binaries'

$helperDirs = @()
$gitUsrBin = "$env:ProgramFiles\Git\usr\bin"
if (Test-Path $gitUsrBin) { $helperDirs += $gitUsrBin }
elseif (Test-Path "${env:ProgramFiles(x86)}\Git\usr\bin") { $helperDirs += "${env:ProgramFiles(x86)}\Git\usr\bin" }

$rgDir = Get-ChildItem (Join-Path $env:LOCALAPPDATA 'Programs\ripgrep') -Directory -ErrorAction SilentlyContinue |
         ForEach-Object { $_.FullName } | Where-Object { Test-Path (Join-Path $_ 'rg.exe') } | Select-Object -First 1
if ($rgDir) { $helperDirs += $rgDir }
elseif (-not (Has-Cmd 'rg')) {
  Write-Host "       installing ripgrep"
  Run 'winget' @('install','--id','BurntSushi.ripgrep.MSVC','-e','--source','winget','--accept-package-agreements','--accept-source-agreements','--silent') | Out-Null
  $rgDir = Get-ChildItem (Join-Path $env:LOCALAPPDATA 'Programs\ripgrep') -Directory -ErrorAction SilentlyContinue |
           ForEach-Object { $_.FullName } | Where-Object { Test-Path (Join-Path $_ 'rg.exe') } | Select-Object -First 1
  if ($rgDir) { $helperDirs += $rgDir } else { Warn 'ripgrep install failed; rtk rg will not work' }
}

if ($helperDirs.Count -gt 0) {
  $userPath = [Environment]::GetEnvironmentVariable('Path','User')
  $parts = @($userPath -split ';' | Where-Object { $_ })
  $added = @()
  foreach ($d in $helperDirs) {
    if (-not ($parts | Where-Object { $_.TrimEnd('\') -ieq $d.TrimEnd('\') })) {
      $parts += $d
      $added += $d
    }
  }
  if ($added.Count -gt 0) {
    if ($DryRun) { Write-Host "       DRY: add to user PATH: $($added -join ', ')" -ForegroundColor DarkGray }
    else {
      [Environment]::SetEnvironmentVariable('Path', (($parts -join ';') + ';'), 'User')
      Ok "user PATH += $($added -join ', ')"
    }
  } else {
    Ok 'rtk helper binaries already on user PATH'
  }
  Refresh-Path
} else {
  Warn 'no rtk helper binaries found (Git usr\bin, ripgrep); rtk rg / rtk wc / rtk ls will fail'
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

if (Has-Cmd 'graphify') {
  if (Has-Cmd 'uv') {
    if ($DryRun) { Write-Host '       DRY: uv tool update-shell' -ForegroundColor DarkGray }
    else { Run 'uv' @('tool','update-shell') | Out-Null }
  }
  # graphify install writes the global reminder plugin
  # (~/.config/opencode/plugins/graphify.js) and the global graphify skill.
  # Without it the plugin is missing on a fresh machine.
  $gPlugin = Join-Path $cfgDir 'plugins\graphify.js'
  if (Test-Path $gPlugin) {
    Ok 'graphify global plugin present'
  } else {
    Write-Host '       installing the graphify global plugin'
    if ($DryRun) { Write-Host '       DRY: graphify install' -ForegroundColor DarkGray }
    else {
      Run 'graphify' @('install') | Out-Null
      if (Test-Path $gPlugin) { Ok 'graphify global plugin installed' }
      else { Warn 'graphify install did not create the global plugin; run: graphify install' }
    }
  }
  $gv = & graphify --version 2>&1 | Out-String
  if ($gv -match 'warning: skill .* is from graphify') {
    Warn 'graphify skill/package drift detected. Run once: graphify install'
  }
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

# ------------------------------------------------------- global always-on rules
# opencode auto-loads ~/.config/opencode/AGENTS.md in every session, in every
# project. It is the only global instruction path that works reliably: a
# relative "instructions" entry in the global config is skipped because the
# file is resolved against the workspace, not the config directory.
Step 'global always-on rules'

$alwaysOnSrc = Join-Path (Split-Path -Parent $PSScriptRoot) 'instructions\ALWAYS-ON.md'
$alwaysOnDst = Join-Path $cfgDir 'AGENTS.md'

if (-not (Test-Path $alwaysOnSrc)) {
  Warn "ALWAYS-ON.md not found at $alwaysOnSrc; skipping global AGENTS.md"
} elseif (Test-Path $alwaysOnDst) {
  $same = ((Get-Content $alwaysOnSrc -Raw) -eq (Get-Content $alwaysOnDst -Raw))
  if ($same) { Ok 'global AGENTS.md already current' }
  else {
    if ($DryRun) { Write-Host "       DRY: refresh $alwaysOnDst" -ForegroundColor DarkGray }
    else { Copy-Item $alwaysOnSrc $alwaysOnDst -Force; Ok "global AGENTS.md refreshed" }
  }
} else {
  if ($DryRun) { Write-Host "       DRY: write $alwaysOnDst" -ForegroundColor DarkGray }
  else { Copy-Item $alwaysOnSrc $alwaysOnDst -Force; Ok "global AGENTS.md written" }
}

# --------------------------------------------------------------- opencode config
Step 'opencode config (plugins + MCP)'

$jsonPath  = Join-Path $cfgDir 'opencode.json'
$jsoncPath = Join-Path $cfgDir 'opencode.jsonc'
$jsonRead  = Read-JsonFile -Path $jsonPath
$jsoncRead = Read-JsonFile -Path $jsoncPath
$jsonObj   = $jsonRead.Value
$jsoncObj  = $jsoncRead.Value

$parseErrors = @()
if (-not $jsonRead.Ok)  { $parseErrors += "opencode.json: $($jsonRead.Error)" }
if (-not $jsoncRead.Ok) { $parseErrors += "opencode.jsonc: $($jsoncRead.Error)" }
$configWritable = ($parseErrors.Count -eq 0)

$targetPath = $null
# Prefer the file that already carries the machine layer (mcp / plugins).
# Both files are loaded by opencode, so writing to the wrong one duplicates
# the same MCP server under two files.
$jsonHasMachine = (Get-Prop $jsonObj 'mcp') -or (Get-Prop $jsonObj 'plugins') -or (Get-Prop $jsonObj 'plugin')
$jsoncHasMachine = (Get-Prop $jsoncObj 'mcp') -or (Get-Prop $jsoncObj 'plugins') -or (Get-Prop $jsoncObj 'plugin')
if ($jsonHasMachine -and -not $jsoncHasMachine) {
  $targetPath = $jsonPath
} elseif ($jsoncHasMachine -and -not $jsonHasMachine) {
  $targetPath = $jsoncPath
} elseif ($jsonHasMachine -and $jsoncHasMachine) {
  $targetPath = $jsonPath
} elseif (Test-Path $jsoncPath) {
  $targetPath = $jsoncPath
} else {
  $targetPath = $jsonPath
}

$cfgRead = Read-JsonFile -Path $targetPath
$cfg = $cfgRead.Value
if ($null -eq $cfg) {
  if ($cfgRead.Exists -and -not $cfgRead.Ok) { $configWritable = $false }
  $cfg = [pscustomobject]@{ '$schema' = 'https://opencode.ai/config.json' }
}
Info "target: $targetPath"

if (-not $configWritable) {
  Bad "config parse failed; nothing written: $($parseErrors -join '; ')"
} else {

$desiredPlugins = @(
  'context-mode'
)
$otherPath = if ($targetPath -eq $jsoncPath) { $jsonPath } else { $jsoncPath }
$otherObj = (Read-JsonFile -Path $otherPath).Value
$otherPlugins = @()
$op = Get-Prop $otherObj 'plugins'
if (-not $op) { $op = Get-Prop $otherObj 'plugin' }
if ($op) { $otherPlugins = @($op) }

$pluginList = @()
$existingPlugins = Get-Prop $cfg 'plugins'
if (-not $existingPlugins) { $existingPlugins = Get-Prop $cfg 'plugin' }
if ($existingPlugins) { $pluginList = @($existingPlugins) }
$changed = $false
foreach ($p in $desiredPlugins) {
  $inTarget = $pluginList | Where-Object { $_ -eq $p -or ($_ -like 'context-mode*' -and $p -eq 'context-mode') }
  $inOther = $otherPlugins | Where-Object { $_ -eq $p -or ($_ -like 'context-mode*' -and $p -eq 'context-mode') }
  if ($inTarget) { Ok "plugin present: $p" }
  elseif ($inOther) { Ok "plugin present in the other config file: $p" }
  else { $pluginList += $p; $changed = $true; Ok "plugin added: $p" }
}
# drop any retired plugin entries (opencode-power-pack) that are still listed
foreach ($stale in @('opencode-power-pack')) {
  if ($pluginList | Where-Object { $_ -like "*$stale*" }) {
    $pluginList = @($pluginList | Where-Object { $_ -notlike "*$stale*" })
    $changed = $true
    Ok "plugin removed: $stale"
  }
}
if (-not $DryRun -and $pluginList.Count -gt 0) { Set-Prop $cfg 'plugins' $pluginList }

$mcp = Get-Prop $cfg 'mcp'
if (-not $mcp) {
  $mcp = [pscustomobject]@{}
  if (-not $DryRun) { Set-Prop $cfg 'mcp' $mcp }
}

# opencode accepts both shapes: "mcp": { "<name>": {...} } and
# "mcp": { "servers": { "<name>": {...} } }. Detect the one already in use so
# a second copy of the same server is not written under the other shape.
$mcpServers = Get-Prop $mcp 'servers'
if (-not $mcpServers) {
  $mcpServers = [pscustomobject]@{}
  if (-not $DryRun) { Set-Prop $mcp 'servers' $mcpServers }
}

$otherMcp = Get-Prop $otherObj 'mcp'
$otherMcpServers = Get-Prop $otherMcp 'servers'
if (-not $otherMcpServers) { $otherMcpServers = $otherMcp }

$cdtArgs = @('npx','-y','chrome-devtools-mcp@latest')
if ($chromeExe) { $cdtArgs += @('--executablePath', $chromeExe) }
$mcpWanted = @{
  'chrome-devtools' = [pscustomobject]@{ type = 'local'; command = $cdtArgs; enabled = $true }
}
foreach ($k in $mcpWanted.Keys) {
  $existing = Get-Prop $mcpServers $k
  if ($existing) {
    # Repair a stale --executablePath. The path names a versioned Chrome
    # folder, so it breaks as soon as Chrome updates and the MCP then fails
    # to start. Rewrite it with the browser that is on disk right now.
    $existingCmd = @(Get-Prop $existing 'command')
    $exIdx = [array]::IndexOf($existingCmd, '--executablePath')
    if ($exIdx -ge 0 -and ($exIdx + 1) -lt $existingCmd.Count) {
      $curPath = $existingCmd[$exIdx + 1]
      if (-not (Test-Path $curPath)) {
        if ($chromeExe) {
          if ($DryRun) { Write-Host "       DRY: repoint chrome-devtools to $chromeExe" -ForegroundColor DarkGray }
          else {
            $existingCmd[$exIdx + 1] = $chromeExe
            Set-Prop $existing 'command' $existingCmd
            $changed = $true
            Ok "repaired stale Chrome path: $curPath -> $chromeExe"
          }
        } else {
          Warn "chrome-devtools points at a missing Chrome path ($curPath) and no replacement was found"
        }
      } else {
        Ok "MCP present: $k"
      }
    } else {
      Ok "MCP present: $k"
    }
  }
  elseif (Get-Prop $otherMcpServers $k) { Ok "MCP present in the other config file: $k" }
  elseif ($DryRun) { Write-Host "       DRY: add MCP $k" -ForegroundColor DarkGray }
  else { Set-Prop $mcpServers $k $mcpWanted[$k]; $changed = $true; Ok "MCP added: $k" }
}

$tavilyPresent = (Get-Prop $mcpServers 'tavily') -or (Get-Prop $otherMcpServers 'tavily')
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
    Set-Prop $mcpServers 'tavily' $tavily
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

}

# ------------------------------------------------------- context-mode package
# opencode resolves a package plugin from its own npm cache at
# ~/.cache/opencode/npm/<package>@latest and installs it on first use. No npm
# install is needed here, and installing it elsewhere only creates a copy that
# is never loaded.
Step 'context-mode package'

$cmCache = Join-Path $userHome '.cache\opencode\npm\context-mode@latest'
if (Test-Path $cmCache) {
  Ok "context-mode available in the opencode npm cache ($cmCache)"
} elseif ($DryRun) {
  Write-Host "       DRY: opencode downloads context-mode on first use" -ForegroundColor DarkGray
} else {
  Info 'context-mode is not cached yet; opencode downloads it on first use'
}

# Remove copies that opencode never loads. A package in the global npm root
# or in the config directory is not what opencode resolves, so those are dead
# weight that only confuse the next reader.
$deadCopies = @(
  (Join-Path (Join-Path $env:APPDATA 'npm\node_modules') 'context-mode'),
  (Join-Path $cfgDir 'node_modules\context-mode')
)
foreach ($dead in $deadCopies) {
  if (Test-Path $dead) {
    if ($DryRun) { Write-Host "       DRY: remove $dead" -ForegroundColor DarkGray }
    else {
      Remove-Item -LiteralPath $dead -Recurse -Force
      Ok "removed the unused context-mode copy at $dead"
    }
  }
}

# The npm init in the config directory was only there to host that copy.
# Without it the directory holds a package.json that installs nothing.
$cfgPkg = Join-Path $cfgDir 'package.json'
if (Test-Path $cfgPkg) {
  $pkgRaw = Get-Content $cfgPkg -Raw
  $onlyContextMode = $false
  try {
    $pkgObj = $pkgRaw | ConvertFrom-Json
    $deps = $pkgObj.dependencies
    if ($deps) {
      $names = @($deps.PSObject.Properties | ForEach-Object { $_.Name })
      $onlyContextMode = ($names.Count -eq 1 -and $names[0] -eq 'context-mode')
    }
  } catch { $onlyContextMode = $false }
  if ($onlyContextMode) {
    if ($DryRun) { Write-Host "       DRY: remove $cfgPkg" -ForegroundColor DarkGray }
    else {
      Remove-Item -LiteralPath $cfgPkg -Force
      $cfgLock = Join-Path $cfgDir 'package-lock.json'
      if (Test-Path $cfgLock) { Remove-Item -LiteralPath $cfgLock -Force }
      $cfgBin = Join-Path $cfgDir 'node_modules\.bin'
      if (Test-Path $cfgBin) { Remove-Item -LiteralPath $cfgBin -Recurse -Force }
      Ok 'removed the leftover package.json in the config dir (it only held context-mode)'
    }
  }
}

# --------------------------------------------------- playwright CLI + browsers
Step 'Playwright CLI'

if ($SkipBrowsers) {
  Warn 'skipped (-SkipBrowsers)'
} elseif (-not (Has-Cmd 'npm')) {
  Warn 'npm missing; run: npm install -g @playwright/cli@latest'
} else {
  if (Has-Cmd 'playwright-cli') {
    Ok 'playwright-cli present'
  } else {
    Write-Host "       installing @playwright/cli"
    Run 'npm' @('install','-g','@playwright/cli@latest') | Out-Null
    Refresh-Path
    if (Has-Cmd 'playwright-cli') { Ok 'playwright-cli installed' } else { Warn 'playwright-cli not on PATH yet; reopen the terminal after this script' }
  }

  $cache = Join-Path $env:LOCALAPPDATA 'ms-playwright'
  if (Test-Path $cache) {
    $n = (Get-ChildItem $cache -Directory -ErrorAction SilentlyContinue).Count
    Ok "cache present: $n item(s)"
  } else {
    Write-Host "       downloading chromium"
    Run 'playwright-cli' @('install-browser') | Out-Null
    if (Test-Path $cache) { Ok 'chromium installed' } else { Warn 'chromium install did not complete' }
  }

  $pwSkillSrc = Join-Path $userHome '.agents\skills\playwright-cli'
  $pwSkillDst = Join-Path $cfgDir 'skills\playwright-cli'

  $pwCfg = Join-Path $userHome '.playwright\cli.config.json'
  if (Test-Path $pwCfg) {
    Ok 'playwright-cli global config present'
  } else {
    if ($DryRun) { Write-Host "       DRY: write $pwCfg" -ForegroundColor DarkGray }
    else {
      New-Item -ItemType Directory -Path (Split-Path -Parent $pwCfg) -Force | Out-Null
      Set-Content -Path $pwCfg -Value (@{ browser = @{ browserName = 'chromium' } } | ConvertTo-Json -Depth 5) -Encoding UTF8
      Ok 'playwright-cli global config written (chromium)'
    }
  }
  if (Test-Path $pwSkillDst) {
    Ok 'playwright-cli skill present'
  } else {
    if (Test-Path $pwSkillSrc) {
      if ($DryRun) { Write-Host "       DRY: copy playwright-cli skill to $pwSkillDst" -ForegroundColor DarkGray }
      else {
        New-Item -ItemType Directory -Path (Split-Path -Parent $pwSkillDst) -Force | Out-Null
        Copy-Item $pwSkillSrc $pwSkillDst -Recurse -Force
        Ok 'playwright-cli skill installed'
      }
    } else {
      Write-Host "       installing playwright-cli skill"
      Run 'playwright-cli' @('install','--skills','agents','--global') | Out-Null
      if (Test-Path $pwSkillSrc) {
        if ($DryRun) { Write-Host "       DRY: copy playwright-cli skill to $pwSkillDst" -ForegroundColor DarkGray }
        else {
          New-Item -ItemType Directory -Path (Split-Path -Parent $pwSkillDst) -Force | Out-Null
          Copy-Item $pwSkillSrc $pwSkillDst -Recurse -Force
          Ok 'playwright-cli skill installed'
        }
      } else {
        Warn 'playwright-cli skill not found at ~/.agents/skills; run: playwright-cli install --skills agents --global'
      }
    }
  }
}

# ------------------------------------------------------------------- skills
# The vendored skills are project-local on purpose: every agent and command in
# this SOP references them by a project relative path, and hallmark's
# sloplint.mjs is executed directly from that path. A global copy would be a
# duplicate that is never used. The global always-on rules live in
# ~/.config/opencode/AGENTS.md, written by the "global always-on rules" step
# above. The only global skills are the ones owned by the tools themselves
# (graphify, playwright-cli), installed by those tools.
Step 'Skills'

if ($SkipSkills) {
  Warn 'skipped (-SkipSkills)'
} else {
  Write-Host '       skills are project-local; nothing to install globally' -ForegroundColor DarkGray
  $globalSkillDir = Join-Path $userHome '.config\opencode\skills'
  if (Test-Path $globalSkillDir) {
    $vendored = @('design-taste', 'hallmark', 'i-have-adhd', 'refactoring-ui')
    $stale = @()
    foreach ($v in $vendored) {
      if (Test-Path (Join-Path $globalSkillDir $v)) { $stale += $v }
    }
    if ($stale.Count -gt 0) {
      if ($DryRun) {
        Write-Host "       DRY: remove stale global skill copies: $($stale -join ', ')" -ForegroundColor DarkGray
      } else {
        foreach ($v in $stale) {
          Remove-Item -Recurse -Force (Join-Path $globalSkillDir $v)
        }
        Ok "removed $($stale.Count) stale global skill copy/copies: $($stale -join ', ')"
      }
    } else {
      Ok 'no stale global skill copies'
    }
  } else {
    Ok 'no global skills folder to clean'
  }
}

# ------------------------------------------------------------- first project
# One command to lay down the SOP in a fresh project folder. Optional: skip it
# with -SkipProject, or pass -Project "C:\dev\my-app" to do it automatically.
Step 'First project'

if ($SkipProject) {
  Warn 'skipped (-SkipProject)'
} elseif ($Project) {
  if (-not (Test-Path $Project)) {
    if ($DryRun) { Write-Host "       DRY: create $Project" -ForegroundColor DarkGray }
    else { New-Item -ItemType Directory -Path $Project -Force | Out-Null }
  }
  $copier = Join-Path $PSScriptRoot 'copy-to-project.ps1'
  if (-not (Test-Path $copier)) {
    Warn 'copy-to-project.ps1 not found'
  } elseif ($DryRun) {
    Write-Host "       DRY: copy-to-project.ps1 -Destination `"$Project`"" -ForegroundColor DarkGray
  } else {
    $copyArgs = @('-Destination', $Project)
    if ($Force) { $copyArgs += '-Force' }
    & powershell -NoProfile -ExecutionPolicy Bypass -File $copier @copyArgs
    if ($LASTEXITCODE -eq 0) { Ok "SOP copied to $Project" }
    else { Warn "copy-to-project.ps1 returned a non-zero exit code" }
  }
} else {
  Info 'no -Project given; skipping the project copy'
  Info 'run it later: powershell -NoProfile -File copy-to-project.ps1 -Destination "C:\dev\my-app"'
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
