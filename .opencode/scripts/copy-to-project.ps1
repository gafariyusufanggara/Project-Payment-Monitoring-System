# Copy the agent setup into a project.
#
# Result in the destination:
#   <project>/AGENTS.md          routing table (opencode reads it automatically)
#   <project>/.opencode/...      sops, agents, commands, skills, instructions, mcp, scripts, README
#
# Usage:
#   powershell -NoProfile -File .opencode\scripts\copy-to-project.ps1 -Destination "C:\path\to\project"
#   powershell -NoProfile -File .opencode\scripts\copy-to-project.ps1 -Destination "..." -WithoutSkills
#   powershell -NoProfile -File .opencode\scripts\copy-to-project.ps1 -Destination "..." -Force
#
# Default copies the skills too (~5 MB). -WithoutSkills skips them (use when the
# skills are already installed globally via install-skills.ps1).

param(
  [Parameter(Mandatory = $true)]
  [string]$Destination,

  [switch]$WithoutSkills,

  [switch]$Force
)

$ErrorActionPreference = 'Stop'
$agentsDir = Split-Path -Parent $PSScriptRoot          # .../.opencode
$sourceRoot = Split-Path -Parent $agentsDir            # folder holding AGENTS.md + .opencode

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

$skip = @()
if ($WithoutSkills) { $skip = @('skills') }

$dirs = Get-ChildItem $agentsDir -Directory |
  Where-Object { ($skip -notcontains $_.Name) -and ($_.Name -ne 'node_modules') }
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

Write-Host ""
Write-Host "Done. Destination: $Destination"

$missing = @()
if (-not (Get-Command rtk -ErrorAction SilentlyContinue)) { $missing += 'rtk' }
if (-not (Get-Command graphify -ErrorAction SilentlyContinue)) { $missing += 'graphify' }
$cfgJson = Join-Path $env:USERPROFILE '.config\opencode\opencode.json'
$cfgJsonc = Join-Path $env:USERPROFILE '.config\opencode\opencode.jsonc'
$cfgRaw = ''
if (Test-Path $cfgJson) { $cfgRaw += (Get-Content $cfgJson -Raw) }
if (Test-Path $cfgJsonc) { $cfgRaw += (Get-Content $cfgJsonc -Raw) }
if ($cfgRaw) {
  if ($cfgRaw -notmatch 'context-mode') { $missing += 'plugin context-mode' }
  if ($cfgRaw -notmatch 'opencode-power-pack') { $missing += 'plugin opencode-power-pack' }
  if ($cfgRaw -notmatch 'playwright') { $missing += 'MCP playwright' }
  if ($cfgRaw -notmatch 'chrome-devtools') { $missing += 'MCP chrome-devtools' }
} else {
  $missing += 'opencode config (plugins + MCP)'
}
if (-not [Environment]::GetEnvironmentVariable('SHELL','User')) { $missing += 'SHELL env var' }

if ($missing.Count -gt 0) {
  Write-Host ""
  Write-Host "Global layer incomplete: $($missing -join ', ')" -ForegroundColor Yellow
  Write-Host "The project works, but the SOP degrades. Fix once per machine:" -ForegroundColor Yellow
  Write-Host "  powershell -NoProfile -ExecutionPolicy Bypass -File `"$PSScriptRoot\bootstrap-windows.ps1`""
}

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Open opencode in $Destination"
Write-Host "  2. Run /stack          -> writes .opencode/STACK.md from real detection"
Write-Host "  3. Edit AGENTS.md      -> replace PROJECT_NAME"
Write-Host "  4. Put your documents in docs/ (PRD, STACK, features) - read before any code"
if ($WithoutSkills) {
  Write-Host "  5. Skills were skipped. Install them globally once:" -ForegroundColor Yellow
  Write-Host "     powershell -NoProfile -File `"$PSScriptRoot\install-skills.ps1`""
}

Write-Host ""
Write-Host "Suggested .gitignore additions:" -ForegroundColor Cyan
Write-Host "  .opencode/STACK.md"
