param(
  [string]$Exe = "",
  [string]$Log = ".\tmp_test.log"
)

$ErrorActionPreference = "Stop"

function Assert-True($cond, $msg) {
  if (-not $cond) { throw $msg }
}

function Resolve-Runner() {
  if ($Exe) { return $Exe }

  $env:PYTHONPATH = "src"
  return "python -m itaoagpt.cli.main"
}

function Run($cmd) {
  Write-Host "==> $cmd" -ForegroundColor Cyan
  $out = Invoke-Expression $cmd 2>&1
  $rc = $LASTEXITCODE
  return @{ rc = $rc; out = ($out | Out-String) }
}

$Runner = Resolve-Runner

# 0) basic: help/version
$r = Run "$Runner version"
Assert-True ($r.rc -eq 0) "version rc != 0"
Assert-True ($r.out -match '"tool"\s*:\s*"itaoagpt"') "version json missing tool"

# 1) analyze json
$r = Run "$Runner analyze `"$Log`" --type log --json"
Assert-True ($r.rc -eq 0) "analyze (informational) must return rc=0, got rc=$($r.rc)"
foreach ($key in @("tool", "version", "schema_version", "created_at", "input_summary", "findings", "stats", "by_level")) {
  Assert-True ($r.out -match ('"' + [regex]::Escape($key) + '"\s*:')) "json missing required key: $key"
}
Assert-True ($r.out -match '"unique_fingerprints"\s*:') "json missing stats.unique_fingerprints"
Assert-True ($r.out -match '"total"\s*:') "json missing stats.total"
Assert-True ($r.out -match '"top_fingerprints"\s*:') "json missing stats.top_fingerprints"
Assert-True ($r.out -match '"confidence_label"\s*:') "json missing triage.confidence_label"

# 2) out.json write
if (Test-Path .\out.json) { Remove-Item .\out.json -Force }
$r = Run "$Runner analyze `"$Log`" --type log --json --out .\out.json"
Assert-True ($r.rc -eq 0) "analyze --out rc != 0"
Assert-True (Test-Path .\out.json) "out.json not written"

# 3) report reads json
$r = Run "$Runner report .\out.json --text"
Assert-True ($r.rc -eq 0) "report --text rc != 0"
Assert-True ($r.out -match "Findings:\s+\d+") "report text missing Findings count"

# 3.1) human text contract
$r = Run "$Runner analyze `"$Log`" --type log --text"
Assert-True ($r.rc -eq 0) "analyze --text rc != 0"
Assert-True ($r.out -match "Unique issues:\s+\d+") "human text missing Unique issues line"
Assert-True ($r.out -match "Top issues:") "human text missing Top issues line"
Assert-True ($r.out -match "\(\d+\)") "human text missing issue count format"

# --- TEXT OUTPUT CONTRACT (human summary must exist) ---
$outText = (python -m itaoagpt.cli.main analyze ".\tmp_test.log" --type log --text) -join "`n"
if ($outText -notmatch "By level:") { throw "missing human summary: By level" }
if ($outText -notmatch "Top issues:") { throw "missing human summary: Top issues" }

function Get-Json($s) {
  if ($null -eq $s -or $s.Trim().Length -eq 0) {
    throw "Empty JSON output"
  }
  try { return ($s | ConvertFrom-Json) } catch { throw "Invalid JSON output" }
}

function Get-FindingSeverities($outObj) {
  if (-not $outObj.findings) { return @() }
  return @($outObj.findings | ForEach-Object { $_.severity })
}

# --- min-severity high ---
$r = Run "$Runner analyze `"$Log`" --type log --json --min-severity high"
Assert-True ($r.rc -eq 0) "min-severity high rc != 0"

$o = Get-Json $r.out
$sevs = Get-FindingSeverities $o

Assert-True ($sevs -contains "high") "min-severity high should include high"
Assert-True (-not ($sevs -contains "medium")) "min-severity high findings should NOT include medium"
Assert-True (-not ($sevs -contains "low")) "min-severity high findings should NOT include low"

# --- min-severity medium ---
$r = Run "$Runner analyze `"$Log`" --type log --json --min-severity medium"
Assert-True ($r.rc -eq 0) "min-severity medium rc != 0"

$o = Get-Json $r.out
$sevs = Get-FindingSeverities $o

Assert-True ($sevs -contains "high") "min-severity medium should include high"
Assert-True ($sevs -contains "medium") "min-severity medium findings should include medium"
Assert-True (-not ($sevs -contains "low")) "min-severity medium findings should NOT include low"

# 3.7) deterministic output must be stable (byte-identical)
$det1 = Run "$Runner analyze `"$Log`" --type log --json --deterministic"
Assert-True ($det1.rc -eq 0) "deterministic run1 rc != 0"
$det2 = Run "$Runner analyze `"$Log`" --type log --json --deterministic"
Assert-True ($det2.rc -eq 0) "deterministic run2 rc != 0"
Assert-True ($det1.out -eq $det2.out) "deterministic outputs differ"

# 3.8) deterministic + debug: debug_meta must be absent
$r = Run "$Runner analyze `"$Log`" --type log --json --deterministic --debug"
Assert-True ($r.rc -eq 0) "deterministic+debug rc != 0"
Assert-True ($r.out -notmatch '"debug_meta"\s*:') "deterministic+debug must NOT include debug_meta"

# 4) fail-on semantics (expected: high->2, medium->2, low->2)
$r = Run "$Runner analyze `"$Log`" --type log --json --fail-on high"
Assert-True ($r.rc -eq 2) "fail-on high expected rc=2 got $($r.rc)"

$r = Run "$Runner analyze `"$Log`" --type log --json --fail-on medium"
Assert-True ($r.rc -eq 2) "fail-on medium expected rc=2 got $($r.rc)"

$r = Run "$Runner analyze `"$Log`" --type log --json --fail-on low"
Assert-True ($r.rc -eq 2) "fail-on low expected rc=2 got $($r.rc)"

Write-Host "`nALL CONTRACT TESTS PASSED ?" -ForegroundColor Green

# 5) analyze exit code contract
$r = Run "$Runner analyze `"$Log`" --type log --json"
Assert-True ($r.rc -eq 0) "analyze (informational) must return rc=0, got rc=$($r.rc)"

$r = Run "$Runner analyze `"$Log`" --type log --json --fail-on high"
Assert-True ($r.rc -eq 2) "analyze --fail-on high must return rc=2"

exit 0
