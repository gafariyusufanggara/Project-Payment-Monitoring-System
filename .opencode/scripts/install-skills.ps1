# Install the vendored skills into opencode so they are discoverable globally,
# or into a project so they are local. Copies, never moves the source.
#
# Usage:
#   powershell -NoProfile -File .opencode\scripts\install-skills.ps1                 # global
#   powershell -NoProfile -File .opencode\scripts\install-skills.ps1 -Project "C:\path\to\app"
#   powershell -NoProfile -File .opencode\scripts\install-skills.ps1 -List
#
# global   -> ~/.config/opencode/skills/<name>/SKILL.md
# project  -> <project>/.opencode/skills/<name>/SKILL.md

param(
  [string]$Project,
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

if ($Project) {
  if (-not (Test-Path $Project)) { Write-Host "Project path not found: $Project" -ForegroundColor Red; exit 1 }
  $target = Join-Path (Resolve-Path $Project).Path '.opencode\skills'
} else {
  $target = Join-Path $env:USERPROFILE '.config\opencode\skills'
}

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
Write-Host "Restart opencode, then verify with: ask it to list its skills."
