# Copy the agent setup into a project.
#
# Result in the destination:
#   <project>/AGENTS.md          routing table (opencode reads it automatically)
#   <project>/.opencode/...      sops, agents, commands, skills, instructions, mcp,
#                                scripts, plugins, reference, README
#
# Usage:
#   powershell -NoProfile -File .opencode\scripts\copy-to-project.ps1 -Destination "C:\path\to\project"
#   powershell -NoProfile -File .opencode\scripts\copy-to-project.ps1 -Destination "..." -Force
#
# Copies the skills too (~5 MB) so every hardcoded sloplint path in the SOP works.
# Copies .opencode/plugins/ too: local OpenCode 2 plugins are project-scoped
# (the global ~/.config/opencode/plugins/ is the machine layer) and must sit in
# <project>/.opencode/plugins/ to be discovered.
# -Force replaces the template-owned folders and preserves STACK.md, plans/,
# node_modules and anything else you added under .opencode/.
#
# Ownership split (deliberate, no duplication):
#   - Per project (this copy): SOPs, agents, commands, skills, instructions, plugins.
#   - Per machine (bootstrap-windows.ps1, global ~/.config/opencode): MCP servers
#     (chrome-devtools, optional tavily), the playwright-cli CLI + skill, the
#     package plugin (context-mode), and the SHELL env var.
#   MCP + package plugins are NOT copied into the project on purpose: one definition
#   per machine keeps the context small and avoids maintaining the same data twice.

param(
  [Parameter(Mandatory = $true)]
  [string]$Destination,

  [switch]$Force
)

$ErrorActionPreference = 'Stop'
$agentsDir = Split-Path -Parent $PSScriptRoot          # .../.opencode
$sourceRoot = Split-Path -Parent $agentsDir            # folder holding AGENTS.md + .opencode

# USERPROFILE can be empty in some child-process contexts, and Join-Path then
# fails with "cannot bind argument to parameter 'Path' because it is null".
$userHome = $env:USERPROFILE
if (-not $userHome) { $userHome = $HOME }
if (-not $userHome) { $userHome = [Environment]::GetFolderPath('UserProfile') }

if (-not (Test-Path $Destination)) {
  New-Item -ItemType Directory -Path $Destination -Force | Out-Null
  Write-Host "created $Destination"
}
$Destination = (Resolve-Path $Destination).Path

if ($Destination -eq $sourceRoot) {
  Write-Host "Destination is the source folder itself. Aborting." -ForegroundColor Red
  exit 1
}

$agentsDst = Join-Path $Destination '.opencode'
if ((Test-Path $agentsDst) -and -not $Force) {
  Write-Host "'.opencode' already exists in the destination. Re-run with -Force to overwrite." -ForegroundColor Red
  exit 1
}

Write-Host "copying .opencode/ ..."
New-Item -ItemType Directory -Path $agentsDst -Force | Out-Null

if ($Force -and (Test-Path $agentsDst)) {
  foreach ($owned in @('sops','agents','commands','skills','instructions','mcp','scripts','plugins','reference')) {
    $p = Join-Path $agentsDst $owned
    if (Test-Path $p) { Remove-Item -LiteralPath $p -Recurse -Force }
  }
  $readme = Join-Path $agentsDst 'README.md'
  if (Test-Path $readme) { Remove-Item -LiteralPath $readme -Force }
  Write-Host "  replaced template-owned folders (STACK.md, plans/ and custom files kept)"
}


$dirs = Get-ChildItem $agentsDir -Directory |
  Where-Object { $_.Name -ne 'node_modules' }
foreach ($d in $dirs) {
  Copy-Item -Path $d.FullName -Destination (Join-Path $agentsDst $d.Name) -Recurse -Force
  Write-Host "  .opencode/$($d.Name)"
}

$files = Get-ChildItem $agentsDir -File | Where-Object { $_.Name -like '*.md' }
foreach ($f in $files) {
  Copy-Item -Path $f.FullName -Destination (Join-Path $agentsDst $f.Name) -Force
  Write-Host "  .opencode/$($f.Name)"
}

# AGENTS.md must sit at the project root; opencode only auto-reads it there.
Copy-Item -Path (Join-Path $sourceRoot 'AGENTS.md') -Destination (Join-Path $Destination 'AGENTS.md') -Force
Write-Host "  AGENTS.md"

# The .gitignore lives in the template root and is the single source of truth
# for what must never be committed. A fresh project needs it, so copy it in.
# If the project already has one, append only the entries that are missing
# and never touch the rules the user wrote.
$giSrc = Join-Path $sourceRoot '.gitignore'
$giDst = Join-Path $Destination '.gitignore'
if (Test-Path $giSrc) {
  $giLines = @(Get-Content $giSrc | Where-Object { $_.Trim() -ne '' -and -not $_.Trim().StartsWith('#') })
  if (-not (Test-Path $giDst)) {
    Copy-Item -Path $giSrc -Destination $giDst -Force
    Write-Host "  .gitignore"
  } else {
    $existingRaw = Get-Content $giDst -Raw
    $existing = @(Get-Content $giDst | Where-Object { $_.Trim() -ne '' -and -not $_.Trim().StartsWith('#') })
    $missing = @($giLines | Where-Object { $existing -notcontains $_ })
    if ($missing.Count -gt 0) {
      $block = "`r`n" + ($missing -join "`r`n") + "`r`n"
      Add-Content -Path $giDst -Value $block -Encoding UTF8
      Write-Host "  .gitignore (added $($missing.Count) missing rule(s))"
    } else {
      Write-Host "  .gitignore (already covers the SOP rules)"
    }
  }
}

# Keep the machine layer in sync with the template's always-on rules.
# The global AGENTS.md is what opencode actually loads in every session.
$globalAgents  = Join-Path $userHome '.config\opencode\AGENTS.md'
$alwaysOnSrc = Join-Path $agentsDir 'instructions\ALWAYS-ON.md'
if (Test-Path $alwaysOnSrc) {
  if (-not (Test-Path $globalAgents)) {
    New-Item -ItemType Directory -Path (Split-Path -Parent $globalAgents) -Force | Out-Null
    Copy-Item $alwaysOnSrc $globalAgents -Force
    Write-Host "  global AGENTS.md written"
  } else {
    $same = ((Get-Content $alwaysOnSrc -Raw) -eq (Get-Content $globalAgents -Raw))
    if (-not $same) {
      Copy-Item $alwaysOnSrc $globalAgents -Force
      Write-Host "  global AGENTS.md refreshed (always-on rules changed)"
    }
  }
}

# Remove stale global copies of the vendored skills. The skills are
# project-local by design: every agent and command references them by a
# project relative path, and hallmark's sloplint.mjs is executed from that
# path, so a global copy is never used. Only the tool-owned skills
# (graphify, playwright-cli) belong in the global folder.
$globalSkillDir = Join-Path $userHome '.config\opencode\skills'
if (Test-Path $globalSkillDir) {
  $removed = @()
  foreach ($v in @('design-taste','hallmark','i-have-adhd','refactoring-ui')) {
    $p = Join-Path $globalSkillDir $v
    if (Test-Path $p) {
      Remove-Item -LiteralPath $p -Recurse -Force
      $removed += $v
    }
  }
  if ($removed.Count -gt 0) {
    Write-Host "  removed stale global skill copy/copies: $($removed -join ', ')"
  }
}

Write-Host ""
Write-Host "Done. Destination: $Destination"

# The project copy carries the SOP only. MCP servers and package plugins are
# intentionally global (once per machine) so the same definition is not kept in
# two places. Report what the global layer is missing, not what the project lacks.
$missing = @()
if (-not (Get-Command rtk -ErrorAction SilentlyContinue)) { $missing += 'rtk' }
if (-not (Get-Command graphify -ErrorAction SilentlyContinue)) { $missing += 'graphify' }
$cfgJson = Join-Path $userHome '.config\opencode\opencode.json'
$cfgJsonc = Join-Path $userHome '.config\opencode\opencode.jsonc'
$cfgRaw = ''
if (Test-Path $cfgJson) { $cfgRaw += (Get-Content $cfgJson -Raw) }
if (Test-Path $cfgJsonc) { $cfgRaw += (Get-Content $cfgJsonc -Raw) }
if ($cfgRaw) {
  if ($cfgRaw -notmatch 'context-mode') { $missing += 'plugin context-mode' }
  if ($cfgRaw -notmatch 'chrome-devtools') { $missing += 'MCP chrome-devtools' }
  if (-not (Get-Command playwright-cli -ErrorAction SilentlyContinue)) { $missing += 'playwright-cli (npm i -g @playwright/cli)' }
} else {
  $missing += 'opencode config (plugins + MCP)'
}
if (-not [Environment]::GetEnvironmentVariable('SHELL','User')) { $missing += 'SHELL env var' }
if (-not (Test-Path $globalAgents)) { $missing += 'global AGENTS.md (always-on rules)' }

if ($missing.Count -gt 0) {
  Write-Host ""
  Write-Host "Machine layer (global) missing: $($missing -join ', ')" -ForegroundColor Yellow
  Write-Host "The SOP files are copied and the project opens, but these per-machine" -ForegroundColor Yellow
  Write-Host "pieces (MCP servers, package plugins, SHELL) live in ~/.config/opencode," -ForegroundColor Yellow
  Write-Host "not in the project. Fix once per machine:" -ForegroundColor Yellow
  Write-Host "  powershell -NoProfile -ExecutionPolicy Bypass -File `"$PSScriptRoot\bootstrap-windows.ps1`""
} else {
  Write-Host ""
  Write-Host "Machine layer (global) present: MCP + package plugins + SHELL. Good." -ForegroundColor Green
}

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Open opencode in $Destination"
Write-Host "  2. Run /stack          -> writes .opencode/STACK.md from real detection"
Write-Host "  3. Edit AGENTS.md      -> replace PROJECT_NAME"
Write-Host "  4. Put your documents in docs/ (PRD, STACK, features) - read before any code"

Write-Host ""
Write-Host "The .gitignore above already covers the generated files:" -ForegroundColor Cyan
Write-Host "  .opencode/STACK.md, .opencode/node_modules/, graphify-out/"
