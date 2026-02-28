param(
  [string]$Runner = "itaoagpt"
)

$ErrorActionPreference = "Stop"

$log = ".\tmp_test.log"
if (-not (Test-Path $log)) {
  throw "smoke_text.ps1: log file not found: $log (run from repo root)"
}

# --- TEXT output marker gates ---
$t = (Invoke-Expression "$Runner analyze `"$log`" --type log --text") | Out-String

if ($t -notmatch '\bfile=')             { throw 'TEXT CI missing: file=' }
if ($t -notmatch '\blines=\d+')         { throw 'TEXT CI missing: lines=' }
if ($t -notmatch '\bevents=\d+')        { throw 'TEXT CI missing: events=' }
if ($t -notmatch '\bresult\.findings=') { throw 'TEXT CI missing: result.findings=' }
if ($t -notmatch '\bby_level\.ERROR=')  { throw 'TEXT CI missing: by_level.ERROR=' }

# --- Deterministic text: byte-identical across two runs ---
$a = (Invoke-Expression "$Runner analyze `"$log`" --type log --text --deterministic") | Out-String
$b = (Invoke-Expression "$Runner analyze `"$log`" --type log --text --deterministic") | Out-String
if ($a -ne $b) { throw 'TEXT CI: deterministic text mismatch' }

# --- min-severity high must not leak medium into triage ---
$j = (Invoke-Expression "$Runner analyze `"$log`" --type log --json --min-severity high") | ConvertFrom-Json

# top_fingerprints are dicts — check .severity directly
$medFps = @($j.triage.top_fingerprints | Where-Object { $_.severity -eq 'medium' })
if ($medFps.Count -gt 0) {
  throw "TEXT CI: min-severity high leak — triage.top_fingerprints contains medium"
}

# top_issues are formatted strings like "[high] fingerprint (N)"
$medIssues = @($j.triage.top_issues | Where-Object { $_ -match '\[medium\]' })
if ($medIssues.Count -gt 0) {
  throw "TEXT CI: min-severity high leak — triage.top_issues contains [medium]"
}

# retry action must not appear when medium fps are filtered
$acts = ($j.triage.actions | ForEach-Object { "$_" }) -join "`n"
if ($acts -match '(?i)retry') {
  throw "TEXT CI: min-severity high leak — triage.actions contains retry action"
}

# --- fail-on exit code ---
Invoke-Expression "$Runner analyze `"$log`" --type log --text --fail-on high" *> $null
if ($LASTEXITCODE -eq 0) {
  throw "TEXT CI: fail-on high expected non-zero exit, got 0"
}

Write-Host "[OK] TEXT smoke OK" -ForegroundColor Green
