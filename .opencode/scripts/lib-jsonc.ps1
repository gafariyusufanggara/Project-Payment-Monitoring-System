function ConvertFrom-Jsonc {
  param([Parameter(Mandatory = $true)][string]$Text)

  $src = $Text
  if ($src.Length -gt 0 -and $src[0] -eq [char]0xFEFF) { $src = $src.Substring(1) }

  $sb = New-Object System.Text.StringBuilder
  $inString = $false
  $escaped = $false
  $i = 0

  while ($i -lt $src.Length) {
    $c = $src[$i]

    if ($inString) {
      [void]$sb.Append($c)
      if ($escaped) { $escaped = $false }
      elseif ($c -eq '\') { $escaped = $true }
      elseif ($c -eq '"') { $inString = $false }
      $i++
      continue
    }

    if ($c -eq '"') { $inString = $true; [void]$sb.Append($c); $i++; continue }

    if ($c -eq '/' -and ($i + 1) -lt $src.Length -and $src[$i + 1] -eq '/') {
      while ($i -lt $src.Length -and $src[$i] -ne "`n") { $i++ }
      continue
    }

    if ($c -eq '/' -and ($i + 1) -lt $src.Length -and $src[$i + 1] -eq '*') {
      $i += 2
      while (($i + 1) -lt $src.Length -and -not ($src[$i] -eq '*' -and $src[$i + 1] -eq '/')) { $i++ }
      $i += 2
      continue
    }

    [void]$sb.Append($c)
    $i++
  }

  return (Remove-TrailingCommas -Text $sb.ToString())
}

function Remove-TrailingCommas {
  param([Parameter(Mandatory = $true)][string]$Text)

  $sb = New-Object System.Text.StringBuilder
  $inString = $false
  $escaped = $false
  $i = 0

  while ($i -lt $Text.Length) {
    $c = $Text[$i]

    if ($inString) {
      [void]$sb.Append($c)
      if ($escaped) { $escaped = $false }
      elseif ($c -eq '\') { $escaped = $true }
      elseif ($c -eq '"') { $inString = $false }
      $i++
      continue
    }

    if ($c -eq '"') { $inString = $true; [void]$sb.Append($c); $i++; continue }

    if ($c -eq ',') {
      $j = $i + 1
      while ($j -lt $Text.Length -and [char]::IsWhiteSpace($Text[$j])) { $j++ }
      if ($j -lt $Text.Length -and ($Text[$j] -eq '}' -or $Text[$j] -eq ']')) { $i++; continue }
    }

    [void]$sb.Append($c)
    $i++
  }

  return $sb.ToString()
}

function Read-JsonFile {
  param([Parameter(Mandatory = $true)][string]$Path)

  if (-not (Test-Path -LiteralPath $Path)) {
    return [pscustomobject]@{ Exists = $false; Ok = $true; Value = $null; Error = $null }
  }

  try {
    $raw = Get-Content -LiteralPath $Path -Raw
    $clean = ConvertFrom-Jsonc -Text $raw
    $value = $clean | ConvertFrom-Json
    return [pscustomobject]@{ Exists = $true; Ok = $true; Value = $value; Error = $null }
  } catch {
    return [pscustomobject]@{ Exists = $true; Ok = $false; Value = $null; Error = $_.Exception.Message }
  }
}

function Write-JsonFile {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)]$Object
  )

  $json = $Object | ConvertTo-Json -Depth 30
  $utf8 = New-Object System.Text.UTF8Encoding($false)
  $tmp = "$Path.tmp-$PID"
  try {
    [System.IO.File]::WriteAllText($tmp, $json, $utf8)
    Move-Item -LiteralPath $tmp -Destination $Path -Force
  } finally {
    if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }
  }
}
