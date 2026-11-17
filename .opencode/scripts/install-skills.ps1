# Install the vendored skills into a project so they are discoverable there.
# Copies, never moves the source.
#
# Usage:
#   powershell -NoProfile -File .opencode\scripts\install-skills.ps1 -Project "C:\path\to\app"
#   powershell -NoProfile -File .opencode\scripts\install-skills.ps1 -List
#
# Why project-local and not global:
#   Every agent and command in this SOP references the skills by a project
#   relative path, for example ".opencode/skills/hallmark/scripts/sloplint.mjs",
#   and that file is executed directly. A global copy cannot satisfy a relative
#   path, so a global install is a duplicate that is never used. The only
#   global skills are the ones owned by the tools themselves (graphify,
#   playwright-cli), which those tools install on their own.
#
# The global always-on rules are handled separately: they live in
# ~/.config/opencode/AGENTS.md and are written by bootstrap-windows.ps1 and
# copy-to-project.ps1.
#
# ASCII only. PowerShell 5.1 reads a BOM-less file as ANSI, and a stray
# non-ASCII byte becomes a quote that breaks the parser.

param(
  [string]$Project = '',
  [switch]$Force,
  [switch]$List
)

$ErrorActionPreference = 'Stop'
$agentsDir = Split-Path -Parent $PSScriptRoot
$skillsDir = Join-Path $agentsDir 'skills'

if (-not (Test-Path $skillsDir)) {
  Write-Host "No skills/ folder next to .opencode/." -ForegroundColor Red
  exit 1
}

$names = Get-ChildItem $skillsDir -Directory | Where-Object {
  $_.Name -ne 'vibe' -and (Test-Path (Join-Path $_.FullName 'SKILL.md'))
} | Select-Object -ExpandProperty Name

if ($List) {
  Write-Host "Vendored skills in $skillsDir :"
  foreach ($n in $names) {
    $desc = ''
    $head = Get-Content (Join-Path $skillsDir "$n\SKILL.md") -TotalCount 12 -ErrorAction SilentlyContinue
    $d = $head | Where-Object { $_ -match '^description:' } | Select-Object -First 1
    if ($d) { $desc = ($d -replace '^description:\s*', '').Trim() }
    $desc = $desc.Trim([char]'"', [char]"'")
    if ($desc.Length -gt 90) { $desc = $desc.Substring(0, 90) + '...' }
    Write-Host ("  {0,-18} {1}" -f $n, $desc)
  }
  exit 0
}

if (-not $Project) {
  Write-Host "install-skills.ps1 needs a destination project." -ForegroundColor Red
  Write-Host "  powershell -NoProfile -File .opencode\scripts\install-skills.ps1 -Project `"C:\path\to\app`"" -ForegroundColor Red
  Write-Host "  powershell -NoProfile -File .opencode\scripts\install-skills.ps1 -List" -ForegroundColor Red
  exit 1
}

if (-not (Test-Path $Project)) {
  Write-Host "Project path not found: $Project" -ForegroundColor Red
  exit 1
}

$target = Join-Path (Resolve-Path $Project).Path '.opencode\skills'
if (-not (Test-Path $target)) { New-Item -ItemType Directory -Path $target -Force | Out-Null }

foreach ($n in $names) {
  $dst = Join-Path $target $n
  if ((Test-Path $dst) -and -not $Force) {
    Write-Host "skip (exists, use -Force): $n" -ForegroundColor Yellow
    continue
  }
  if (Test-Path $dst) { Remove-Item -Recurse -Force $dst }
  Copy-Item -Path (Join-Path $skillsDir $n) -Destination $dst -Recurse -Force
  Write-Host "installed $n"
}

Write-Host "`nInstalled to: $target"
Write-Host "These skills stay project-local on purpose. Every agent and command"
Write-Host "in this SOP references them by a project relative path."
