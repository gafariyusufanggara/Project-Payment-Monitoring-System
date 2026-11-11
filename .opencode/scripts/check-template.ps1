# Smoke test for the SOP template itself.
# Usage: powershell -NoProfile -File .opencode\scripts\check-template.ps1
#        powershell -NoProfile -File .opencode\scripts\check-template.ps1 -SkipCopy -SkipAgents

param(
  [switch]$SkipCopy,
  [switch]$SkipAgents,
  [switch]$KeepTemp
)

$ErrorActionPreference = 'Stop'
$scriptsDir = $PSScriptRoot
$agentsDir = Split-Path -Parent $scriptsDir
$root = Split-Path -Parent $agentsDir
. (Join-Path $scriptsDir 'lib-jsonc.ps1')

$fail = 0
$warn = 0

function Ok($m)   { Write-Host "[OK]   $m" -ForegroundColor Green }
function Bad($m)  { Write-Host "[FAIL] $m" -ForegroundColor Red; $script:fail++ }
function Warn($m) { Write-Host "[WARN] $m" -ForegroundColor Yellow; $script:warn++ }

Write-Host "`n=== Layout ===" -ForegroundColor Cyan

$required = @(
  'AGENTS.md',
  '.opencode/sops/WEB_DEV.md','.opencode/sops/DESIGN.md','.opencode/sops/QUALITY_GATE.md',
  '.opencode/sops/CONTEXT.md','.opencode/sops/STACKS.md',
  '.opencode/sops/context/TROUBLESHOOTING.md',
  '.opencode/sops/stacks/nextjs.md','.opencode/sops/stacks/vue.md','.opencode/sops/stacks/svelte.md',
  '.opencode/sops/stacks/astro.md','.opencode/sops/stacks/vite.md','.opencode/sops/stacks/python.md',
  '.opencode/sops/stacks/go.md','.opencode/sops/stacks/rust.md','.opencode/sops/stacks/_template.md',
  '.opencode/agents/develop.md','.opencode/agents/ui-designer.md','.opencode/agents/reviewer.md','.opencode/agents/planner.md',
  '.opencode/commands/stack.md','.opencode/commands/new-feature.md','.opencode/commands/build-ui.md',
  '.opencode/commands/ui-audit.md','.opencode/commands/ship.md','.opencode/commands/i-have-adhd.md',
  '.opencode/scripts/bootstrap-windows.ps1','.opencode/scripts/copy-to-project.ps1',
  '.opencode/scripts/install-skills.ps1','.opencode/scripts/lib-jsonc.ps1',
  '.opencode/skills/hallmark/SKILL.md','.opencode/skills/hallmark/scripts/sloplint.mjs',
  '.opencode/skills/refactoring-ui/SKILL.md','.opencode/skills/design-taste/SKILL.md',
  '.opencode/skills/i-have-adhd/SKILL.md',
  '.opencode/instructions/ALWAYS-ON.md',
  '.opencode/plugins/graphify-auto-update.js'
)
foreach ($f in $required) {
  $p = Join-Path $root ($f -replace '/','\')
  if (Test-Path $p) { Ok $f } else { Bad "missing: $f" }
}

$vibe = Join-Path $root '.opencode\skills\vibe'
if (Test-Path $vibe) { Warn 'vibe is still vendored; delete it' } else { Ok 'vibe absent' }

Write-Host "`n=== Frontmatter ===" -ForegroundColor Cyan

$agentFiles = Get-ChildItem (Join-Path $agentsDir 'agents') -File -Filter *.md
foreach ($f in $agentFiles) {
  $head = Get-Content $f.FullName -TotalCount 30
  $text = $head -join "`n"
  $problems = @()
  if ($head[0] -ne '---') { $problems += 'missing opening ---' }
  if ($text -notmatch '(?m)^description:') { $problems += 'missing description' }
  if ($text -notmatch '(?m)^mode:') { $problems += 'missing mode' }
  if ($problems.Count -eq 0) { Ok "agent $($f.BaseName)" } else { Bad "agent $($f.BaseName): $($problems -join ', ')" }
}

$commandFiles = Get-ChildItem (Join-Path $agentsDir 'commands') -File -Filter *.md
foreach ($f in $commandFiles) {
  $head = Get-Content $f.FullName -TotalCount 20
  $text = $head -join "`n"
  if ($head[0] -eq '---' -and $text -match '(?m)^description:') {
    Ok "command $($f.BaseName)"
  } else {
    Bad "command $($f.BaseName): frontmatter must start with --- and contain description"
  }
}

Write-Host "`n=== JSONC parser ===" -ForegroundColor Cyan

$tmpJson = Join-Path ([System.IO.Path]::GetTempPath()) "sop-jsonc-$PID.jsonc"
try {
  @'
{
  // line comment
  "a": 1,
  /* block */
  "b": [1, 2,],
  "s": "a,}",
}
'@ | Set-Content -LiteralPath $tmpJson -Encoding ASCII

  $r = Read-JsonFile -Path $tmpJson
  if ($r.Ok -and $r.Value.a -eq 1 -and $r.Value.b.Count -eq 2 -and $r.Value.s -eq 'a,}') {
    Ok 'JSONC with comments and trailing commas parses'
  } else {
    Bad "JSONC parse failed: $($r.Error)"
  }

  '{ "a": }' | Set-Content -LiteralPath $tmpJson -Encoding ASCII
  $r2 = Read-JsonFile -Path $tmpJson
  if (-not $r2.Ok) { Ok 'invalid JSON is reported, not accepted' } else { Bad 'invalid JSON was accepted' }
} finally {
  if (Test-Path $tmpJson) { Remove-Item -LiteralPath $tmpJson -Force }
}

Write-Host "`n=== Copy into a temp project ===" -ForegroundColor Cyan

if ($SkipCopy) {
  Warn 'skipped (-SkipCopy)'
} else {
  $tmpProj = Join-Path ([System.IO.Path]::GetTempPath()) "sop-copy-$PID"
  try {
    if (Test-Path $tmpProj) { Remove-Item -LiteralPath $tmpProj -Recurse -Force }
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $scriptsDir 'copy-to-project.ps1') -Destination $tmpProj | Out-Null
    if ($LASTEXITCODE -ne 0) {
      Bad "copy-to-project exited $LASTEXITCODE"
    } else {
      $expect = @(
        'AGENTS.md',
        '.opencode/sops/WEB_DEV.md',
        '.opencode/agents/develop.md',
        '.opencode/commands/ship.md',
        '.opencode/skills/hallmark/scripts/sloplint.mjs',
        '.opencode/scripts/lib-jsonc.ps1',
        '.opencode/scripts/check-template.ps1'
      )
      foreach ($f in $expect) {
        $p = Join-Path $tmpProj ($f -replace '/','\')
        if (Test-Path $p) { Ok "copied $f" } else { Bad "copy missing $f" }
      }
      if (Test-Path (Join-Path $tmpProj '.opencode\skills\vibe')) { Bad 'copy contains vibe' } else { Ok 'copy excludes vibe' }
    }
  } finally {
    if (-not $KeepTemp -and (Test-Path $tmpProj)) { Remove-Item -LiteralPath $tmpProj -Recurse -Force }
  }
}

Write-Host "`n=== Agents load ===" -ForegroundColor Cyan

if ($SkipAgents) {
  Warn 'skipped (-SkipAgents)'
} elseif (-not (Get-Command opencode -ErrorAction SilentlyContinue)) {
  Warn 'opencode not on PATH; skipped'
} else {
  $list = & opencode agent list 2>&1 | Out-String
  foreach ($name in @('develop','ui-designer','reviewer','planner')) {
    if ($list -match "(?m)^$([regex]::Escape($name)) \((primary|subagent)\)\s*$") {
      Ok "agent loaded: $name"
    } else {
      Bad "agent not loaded: $name"
    }
  }
}

Write-Host "`n=== Summary ===" -ForegroundColor Cyan
Write-Host "failures: $fail   warnings: $warn"
if ($fail -eq 0) {
  Write-Host 'Template smoke test passed.' -ForegroundColor Green
  exit 0
} else {
  Write-Host 'Fix the [FAIL] items.' -ForegroundColor Red
  exit 1
}
