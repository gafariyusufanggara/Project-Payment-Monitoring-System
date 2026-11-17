# OpenCode setup menu - one door for everything.
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File .opencode\scripts\setup-menu.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File .opencode\scripts\setup-menu.ps1 setup "C:\dev\my-app"
#   powershell -NoProfile -ExecutionPolicy Bypass -File .opencode\scripts\setup-menu.ps1 machine
#   powershell -NoProfile -ExecutionPolicy Bypass -File .opencode\scripts\setup-menu.ps1 copy "C:\dev\my-app"
#   powershell -NoProfile -ExecutionPolicy Bypass -File .opencode\scripts\setup-menu.ps1 status
#
# This file only orchestrates. It never installs anything itself: every action
# calls the existing scripts (bootstrap-windows.ps1, copy-to-project.ps1,
# check-setup.ps1) so their behaviour stays in one place.
#
# ASCII only. PowerShell 5.1 reads a BOM-less file as ANSI, and a stray
# non-ASCII byte becomes a quote that breaks the parser.

param(
  [string]$Command = '',
  [string]$Target = '',
  [switch]$DryRun,
  [switch]$Force
)

$ErrorActionPreference = 'Continue'
$scriptDir  = $PSScriptRoot
$templateRoot = Split-Path -Parent (Split-Path -Parent $scriptDir)
$bootstrap  = Join-Path $scriptDir 'bootstrap-windows.ps1'
$copier     = Join-Path $scriptDir 'copy-to-project.ps1'
$checker    = Join-Path $scriptDir 'check-setup.ps1'

# USERPROFILE can be empty in some child-process contexts, and Join-Path then
# fails with "cannot bind argument to parameter 'Path' because it is null".
$userHome = $env:USERPROFILE
if (-not $userHome) { $userHome = $HOME }
if (-not $userHome) { $userHome = [Environment]::GetFolderPath('UserProfile') }

$target = $Target
if (-not $target) { $target = '' }
$script:done = $false

function Ok($m)   { Write-Host "[OK]   $m" -ForegroundColor Green }
function Info($m) { Write-Host "       $m" -ForegroundColor DarkGray }
function Warn($m) { Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Die($m)  { Write-Host "[FAIL] $m" -ForegroundColor Red }

function Banner {
  Write-Host ''
  Write-Host '========================================================' -ForegroundColor Cyan
  Write-Host '  OpenCode Setup  -  one door for everything' -ForegroundColor Cyan
  Write-Host '========================================================' -ForegroundColor Cyan
}

# Which pieces of the machine layer are present right now.
function MachineState {
  $s = [ordered]@{}
  $s['node']       = [bool](Get-Command node -ErrorAction SilentlyContinue)
  $s['opencode']   = [bool](Get-Command opencode -ErrorAction SilentlyContinue)
  $s['rtk']        = [bool](Get-Command rtk -ErrorAction SilentlyContinue)
  $s['graphify']   = [bool](Get-Command graphify -ErrorAction SilentlyContinue)
  $s['playwright'] = [bool](Get-Command playwright-cli -ErrorAction SilentlyContinue)
  $cfg = Join-Path $userHome '.config\opencode'
  $raw = ''
  foreach ($f in @('opencode.json','opencode.jsonc')) {
    $p = Join-Path $cfg $f
    if (Test-Path $p) { $raw += (Get-Content $p -Raw) }
  }
  $s['mcp']     = $raw -match 'chrome-devtools'
  $s['plugin']  = $raw -match 'context-mode'
  $s['agents']  = Test-Path (Join-Path $cfg 'AGENTS.md')
  # Only tool-owned skills live globally (graphify, playwright-cli). The
  # vendored template skills are project-local on purpose.
  $s['skills']  = $true
  $globalSkillDir = Join-Path $cfg 'skills'
  if (Test-Path $globalSkillDir) {
    $toolOwned = @('graphify','playwright-cli')
    $found = @(Get-ChildItem $globalSkillDir -Directory -ErrorAction SilentlyContinue |
                Where-Object { $toolOwned -notcontains $_.Name })
    $s['skills'] = ($found.Count -eq 0)
  }
  return $s
}

function ShowState {
  $st = MachineState
  Write-Host ''
  Write-Host '  Machine layer (per PC)' -ForegroundColor White
  $pairs = @(
    @('node',        'Node.js'),
    @('opencode',    'opencode'),
    @('rtk',         'rtk'),
    @('graphify',    'graphify'),
    @('playwright',  'playwright-cli'),
    @('mcp',         'MCP chrome-devtools'),
    @('plugin',      'plugin context-mode'),
    @('agents',      'global AGENTS.md'),
    @('skills',      'global skills clean')
  )
  foreach ($p in $pairs) {
    $v = $st[$p[0]]
    if ($v) { Write-Host "    [OK]   $($p[1])" -ForegroundColor Green }
    else    { Write-Host "    [--]   $($p[1])" -ForegroundColor DarkGray }
  }
  Write-Host ''
  if (-not $target) {
    Write-Host '  Target project : (not chosen yet)' -ForegroundColor DarkGray
  } else {
    Write-Host "  Target project : $target" -ForegroundColor White
    if (Test-Path $target) {
      if (Test-Path (Join-Path $target '.opencode')) {
        Write-Host '               already has .opencode/ (will need -Force to overwrite)' -ForegroundColor Yellow
      } else {
        Write-Host '               folder exists, no SOP yet' -ForegroundColor DarkGray
      }
    } else {
      Write-Host '               (does not exist yet)' -ForegroundColor DarkGray
    }
  }
}

# Pick the destination folder. Uses the Windows folder picker when a desktop is
# available, and falls back to typed input everywhere else.
function ChooseTarget {
  $pick = $null
  # A modal dialog blocks forever when stdin is redirected (pipes, CI, a
  # non-interactive shell). Detect that first and skip the picker.
  $redirected = $false
  try {
    $redirected = [Console]::IsInputRedirected
  } catch {
    $redirected = $false
  }
  $canPick = -not $redirected -and $userHome -and [Environment]::UserInteractive

  if ($canPick) {
    try {
      Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
      $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
      $dlg.Description = 'Pilih folder project (bisa bikin baru)'
      $dlg.ShowNewFolderButton = $true
      if ($target -and (Test-Path $target)) { $dlg.SelectedPath = $target }
      if ($dlg.ShowDialog() -eq 'OK') { $pick = $dlg.SelectedPath }
      $dlg.Dispose()
    } catch {
      Info 'folder picker unavailable, type the path instead'
    }
  }

  if (-not $pick) {
    if ($canPick) {
      $answer = Read-Host '  Folder project (Kosongkan untuk memakai picker lagi)'
    } else {
      $answer = Read-Host '  Folder project'
    }
    if ($answer) { $pick = $answer.Trim() }
  }
  if ($pick) {
    $pick = $pick.Trim('"')
    if (-not [System.IO.Path]::IsPathRooted($pick)) {
      $pick = Join-Path (Get-Location).Path $pick
    }
    return $pick
  }
  return $null
}

function Confirm($msg) {
  $a = Read-Host "  $msg [y/N]"
  return ($a -match '^(y|yes)$')
}

function Invoke-Script($path, $argList) {
  if (-not (Test-Path $path)) {
    Die "missing script: $path"
    return 1
  }
  # Pipe the child output to Out-Host so it still shows in the console but does
  # not enter this function's output pipeline. Without this, the return value
  # becomes an array of every output line plus the exit code, and the caller
  # then sees a wrong exit status.
  & powershell -NoProfile -ExecutionPolicy Bypass -File $path @argList | Out-Host
  return $LASTEXITCODE
}

function ActionMachine {
  Write-Host ''
  $args = @()
  if ($DryRun) { $args += '-DryRun' }
  return (Invoke-Script $bootstrap ($args + @('-SkipProject')))
}

function ActionCopy {
  if (-not $target) { Die 'no target folder chosen'; return 1 }
  $args = @('-Destination', $target)
  if ($Force) { $args += '-Force' }
  if ($DryRun) { Info '(dry-run: dry-run flag is not supported by copy-to-project.ps1)' }
  return (Invoke-Script $copier $args)
}

function ActionSetup {
  if (-not $target) { Die 'no target folder chosen'; return 1 }
  $args = @('-Project', $target)
  if ($DryRun)  { $args += '-DryRun' }
  if ($Force)   { $args += '-Force' }
  return (Invoke-Script $bootstrap $args)
}

function ActionStatus {
  Write-Host ''
  $code = Invoke-Script $checker @()
  Write-Host ''
  Write-Host '  Template check' -ForegroundColor White
  $tpl = Join-Path $scriptDir 'check-template.ps1'
  $code2 = Invoke-Script $tpl @()
  if ($code -ne 0) { return $code }
  return $code2
}

function ActionSync {
  # Re-run the machine layer with no project copy. Every step is idempotent.
  return (ActionMachine)
}

function ActionOpen {
  if (-not $target) { Die 'no target folder chosen'; return 1 }
  if (-not (Test-Path $target)) { Die "target folder does not exist: $target"; return 1 }
  if (-not (Get-Command opencode -ErrorAction SilentlyContinue)) {
    Die 'opencode is not on PATH; run the machine layer setup first'
    return 1
  }
  Write-Host ''
  Write-Host "  Opening opencode in $target" -ForegroundColor Cyan
  Write-Host '  (close opencode to return to this menu)' -ForegroundColor DarkGray
  Write-Host ''
  Push-Location $target
  & opencode
  Pop-Location
}

function Menu {
  Banner
  ShowState
  Write-Host '  1. Setup lengkap          (machine layer + salin SOP ke project)'
  Write-Host '  2. Machine layer saja     (sekali per PC)'
  Write-Host '  3. Salin SOP ke project   (tanpa machine layer)'
  Write-Host '  4. Cek status             (apa yang sudah / belum ada)'
  Write-Host '  5. Sinkronkan ulang       (rules global + config)'
  Write-Host '  6. Buka project di opencode'
  Write-Host '  7. Preview                (dry-run setup lengkap)'
  Write-Host '  0. Keluar'
  Write-Host ''

  $choice = Read-Host '  Pilih'
  switch ($choice.Trim()) {
    '1' {
      if (-not $target) {
        $target = ChooseTarget
        if (-not $target) { Write-Host '  dibatalkan' -ForegroundColor Yellow; return }
      }
      ActionSetup | Out-Null
    }
    '2' { ActionMachine | Out-Null }
    '3' {
      if (-not $target) {
        $target = ChooseTarget
        if (-not $target) { Write-Host '  dibatalkan' -ForegroundColor Yellow; return }
      }
      ActionCopy | Out-Null
    }
    '4' { ActionStatus | Out-Null }
    '5' { ActionSync | Out-Null }
    '6' {
      if (-not $target) {
        $target = ChooseTarget
        if (-not $target) { Write-Host '  dibatalkan' -ForegroundColor Yellow; return }
      }
      ActionOpen | Out-Null
    }
    '7' {
      if (-not $target) {
        $target = ChooseTarget
        if (-not $target) { Write-Host '  dibatalkan' -ForegroundColor Yellow; return }
      }
      $saveDry = $DryRun
      $DryRun = $true
      ActionSetup | Out-Null
      $DryRun = $saveDry
    }
    '0' { $script:done = $true }
    default { Write-Host '  pilihan tidak dikenal' -ForegroundColor Yellow }
  }
}

# ------------------------------------------------------------ non-interactive
if ($Command) {
  switch ($Command.ToLower()) {
    'setup' {
      if (-not $target) { Die 'setup needs a target folder: setup-menu.ps1 setup "C:\dev\my-app"'; exit 1 }
      exit (ActionSetup)
    }
    'machine' { exit (ActionMachine) }
    'copy' {
      if (-not $target) { Die 'copy needs a target folder: setup-menu.ps1 copy "C:\dev\my-app"'; exit 1 }
      exit (ActionCopy)
    }
    'status'  { exit (ActionStatus) }
    'sync'   { exit (ActionSync) }
    'open' {
      if (-not $target) { Die 'open needs a target folder'; exit 1 }
      ActionOpen
      exit $?
    }
    default { Die "unknown command: $Command"; exit 1 }
  }
}

# -------------------------------------------------------------- interactive
if (-not $target) {
  $suggest = Join-Path 'C:\dev' (Split-Path -Leaf $templateRoot)
  Write-Host ''
  Info "suggested target: $suggest"
}

while (-not $script:done) {
  Menu
  if (-not $script:done) { Write-Host '' }
}
Write-Host ''
Ok 'done'
exit 0
