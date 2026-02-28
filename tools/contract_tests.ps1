param(
  [string]$Exe = "",
  [string]$Log = ".\tmp_test.log"
)

# Fail fast: herhangi bir hata scripti dusursun
$ErrorActionPreference = "Stop"

# --- UTF-8 hygiene (Windows PowerShell 5.1 dahil) ---
try { chcp 65001 *> $null } catch {}
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = $utf8NoBom
[Console]::OutputEncoding = $utf8NoBom

function ConvertFrom-JsonStrict {
  param(
    [Parameter(Mandatory=$true)]
    [object]$Raw
  )

  # CLI output bazen string[] donebilir -> tek stringe indir
  if ($Raw -is [System.Array]) {
    $text = ($Raw -join "`n")
  } else {
    $text = [string]$Raw
  }

  # guvenlik: gorunmez karakterleri temizle
  $text = $text.TrimStart([char]0xFEFF) -replace "`0", ""

  try {
    return $text | ConvertFrom-Json -ErrorAction Stop
  } catch {
    throw "ConvertFrom-Json failed. Raw output was:`n$text"
  }
}

function Get-Json {
  param(
    [Parameter(Mandatory=$true)]
    [object] $Text
  )

  return (ConvertFrom-JsonStrict $Text)
}

function Assert-HasPath {
  param(
    [Parameter(Mandatory=$true)] $Obj,
    [Parameter(Mandatory=$true)] [string] $Path
  )

  $cur = $Obj
  foreach ($k in ($Path -split '\.')) {
    if ($null -eq $cur) { throw "Missing JSON path: $Path (null at '$k')" }

    # PSObject property check
    $p = $cur.PSObject.Properties[$k]
    if ($null -eq $p) { throw "Missing JSON path: $Path (no property '$k')" }

    $cur = $p.Value
  }
  return $cur
}

function Assert-True($cond, $msg) {
  if (-not $cond) { throw $msg }
}

function Assert($cond, $msg) {
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

try {
$Runner = Resolve-Runner
$Py     = ($Runner -split ' ')[0]   # python executable derived from Runner

# Repo root'tan çalıştırma sözleşmesi
if (-not (Test-Path ".\pyproject.toml")) {
  throw "Run contract_tests.ps1 from repo root (pyproject.toml not found)."
}

$log = Join-Path (Get-Location).Path "tmp_test.log"

@'
2026-02-24 11:00:00 INFO boot
2026-02-24 11:00:01 ERROR db timeout after 2000ms
2026-02-24 11:00:02 CRITICAL out of memory at 0xDEADBEEF
2026-02-24 11:00:03 WARN retrying
2026-02-24 11:00:05 ERROR db timeout after 3000ms
'@ | Set-Content -LiteralPath $log -Encoding utf8

# 0) basic: help/version
$r = Run "$Runner version"
Assert-True ($r.rc -eq 0) "version rc != 0"
Assert-True ($r.out -match '"tool"\s*:\s*"itaoagpt"') "version json missing tool"

# --- install / version sanity gates ---
# expected version auto-derived from latest git tag (v0.4.2 -> 0.4.2)
$tag = (git describe --tags --abbrev=0 2>&1 | Out-String).Trim()
$expected = $tag.TrimStart("v")

# gate A1: CLI JSON version must match tag
$jv = Get-Json $r.out
Assert-True ($jv.version -eq $expected) "version.json must be $expected (got $($jv.version))"

# gate A2: importlib.metadata must match tag
$metaVer = (& $Py -c "import importlib.metadata as m; print(m.version('itaoagpt'))" 2>&1 | Out-String).Trim()
Assert-True ($metaVer -eq $expected) "metadata version must be $expected (got $metaVer)"

# gate B: must import from repo (editable), not site-packages
$pkgPath = (& $Py -c "import itaoagpt; print(itaoagpt.__file__)" 2>&1 | Out-String).Trim()
Assert-True ($pkgPath -notmatch "\\site-packages\\") "itaoagpt imported from site-packages: $pkgPath"
Assert-True ($pkgPath -match "\\src\\itaoagpt\\__init__\.py$") "itaoagpt must import from src: $pkgPath"

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
Assert-True ($r.out -match '"actions"\s*:') "json missing triage.actions"
$o = Get-Json $r.out
Assert-True ($null -ne $o.input_summary.lines) "json missing input_summary.lines"
Assert-True ($null -ne $o.stats.by_level) "json missing stats.by_level (nested)"
[void](Assert-HasPath $o "stats.total")
[void](Assert-HasPath $o "triage.top_fingerprints")
Assert-True ($o.stats.total -eq $o.input_summary.lines) "stats.total must equal input_summary.lines"
Assert-True ($o.input_summary.events -le $o.input_summary.lines) "input_summary.events must be <= input_summary.lines"
Assert-True ((($o.stats.by_level.INFO + $o.stats.by_level.WARNING + $o.stats.by_level.ERROR + $o.stats.by_level.CRITICAL + $o.stats.by_level.DEBUG) -eq $o.input_summary.events)) "by_level total must equal input_summary.events"
Assert-True ($o.stats.counts.unique_fingerprints -ge 1) "unique_fingerprints must be >= 1"
[void](Assert-HasPath $o "triage.actions")
Assert-True ($o.triage.actions -is [System.Array]) "triage.actions must be an array"
$invalidActions = @($o.triage.actions | Where-Object { $_ -isnot [string] -or [string]::IsNullOrWhiteSpace($_) })
Assert-True ($invalidActions.Count -eq 0) "triage.actions must contain only non-empty strings"
Assert-True ($o.triage.top_issues.Count -ge 1) "triage.top_issues must be non-empty"

# fingerprint masking: "db timeout after 2000ms" and "db timeout after 3000ms"
# must collapse to the same masked fingerprint via normalize_message
$fp_strings = @($o.triage.top_fingerprints | ForEach-Object { $_.fingerprint })
Assert-True ($fp_strings -contains "db timeout after <N>ms") "triage.top_fingerprints must contain masked fingerprint 'db timeout after <N>ms'"

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
$outText = (Invoke-Expression "$Runner analyze `"$log`" --type log --text") -join "`n"
if ($outText -notmatch "By level:") { throw "missing human summary: By level" }
if ($outText -notmatch "Top issues:") { throw "missing human summary: Top issues" }

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

# 5) analyze exit code contract
$r = Run "$Runner analyze `"$Log`" --type log --json"
Assert-True ($r.rc -eq 0) "analyze (informational) must return rc=0, got rc=$($r.rc)"

$r = Run "$Runner analyze `"$Log`" --type log --json --fail-on high"
Assert-True ($r.rc -eq 2) "analyze --fail-on high must return rc=2"

# --- A3: version consistency gate (CLI vs metadata) ---
$cliVer = (Invoke-Expression "$Runner version" | ConvertFrom-Json).version
$metaVer = (& $Py -c "import importlib.metadata as imd; print(imd.version('itaoagpt'))" | Out-String).Trim()
Assert ($cliVer -eq $metaVer) "version mismatch: cli=$cliVer metadata=$metaVer"

# --- stdin gate: pipe log content to 'analyze -' and verify JSON output ---
$runnerBase = $Runner -split ' '
$stdinArgs  = $runnerBase[1..($runnerBase.Count - 1)] + @('analyze', '-', '--type', 'log', '--json')
$stdinOut   = (Get-Content -LiteralPath $log -Encoding utf8 | & $Py @stdinArgs) -join "`n"
$stdinJson  = ConvertFrom-JsonStrict $stdinOut
Assert-True ($null -ne $stdinJson) "stdin: JSON parse failed"
Assert-True ($stdinJson.input_summary.source -eq "<stdin>") "stdin: source must be '<stdin>' (got $($stdinJson.input_summary.source))"
Assert-True ($stdinJson.input_summary.lines -ge 1) "stdin: input_summary.lines must be >= 1"
Assert-True ($null -ne $stdinJson.triage) "stdin: triage must be present"

# --- triage new fields gate ---
$triage = $o.triage
[void](Assert-HasPath $o "triage.severity_counts")
Assert-True ($null -ne $triage.severity_counts.high)   "triage.severity_counts.high must exist"
Assert-True ($null -ne $triage.severity_counts.medium) "triage.severity_counts.medium must exist"
Assert-True ($null -ne $triage.severity_counts.low)    "triage.severity_counts.low must exist"
[void](Assert-HasPath $o "triage.confidence_reasons")
Assert-True ($triage.confidence_reasons -is [System.Array])  "triage.confidence_reasons must be an array"
Assert-True ($triage.confidence_reasons.Count -ge 1)         "triage.confidence_reasons must be non-empty"

# --- stdin smoke test: full structural contract for 'analyze -' ---
# $stdinOut / $stdinJson already captured in stdin gate above
$t = $stdinJson
Assert ($t.tool -eq "itaoagpt")                                     "smoke: tool must be itaoagpt"
Assert ($t.schema_version)                                          "smoke: schema_version missing"
Assert ($t.input_summary.source -eq "<stdin>")                      "smoke: input_summary.source must be <stdin>"
Assert ($t.input_summary.lines -ge 1)                               "smoke: input_summary.lines must be >= 1"
Assert ($t.input_summary.events -ge 1)                              "smoke: input_summary.events must be >= 1"
Assert ($t.stats.total -eq $t.input_summary.lines)                  "smoke: stats.total must equal input_summary.lines"
Assert ($t.by_level.ERROR -eq $t.stats.by_level.ERROR)              "smoke: by_level.ERROR must equal stats.by_level.ERROR"
Assert ($t.by_level.CRITICAL -eq $t.stats.by_level.CRITICAL)        "smoke: by_level.CRITICAL must equal stats.by_level.CRITICAL"
# severity_counts lives in triage (not stats)
Assert ($null -ne $t.triage.severity_counts)                        "smoke: triage.severity_counts missing"
Assert ($t.triage.severity_counts.high -ge 0)                       "smoke: triage.severity_counts.high must be >= 0"
Assert ($t.triage.severity_counts.medium -ge 0)                     "smoke: triage.severity_counts.medium must be >= 0"
Assert ($t.triage.severity_counts.low -ge 0)                        "smoke: triage.severity_counts.low must be >= 0"
Assert ($null -ne $t.triage)                                        "smoke: triage missing"
Assert ($t.triage.total_events -eq $t.input_summary.lines)          "smoke: triage.total_events must equal input_summary.lines"
Assert ($t.triage.unique_fingerprints -eq $t.stats.counts.unique_fingerprints) "smoke: triage.unique_fingerprints must equal stats.counts.unique_fingerprints"
Assert ($t.triage.summary)                                          "smoke: triage.summary missing"
# if any high-severity finding exists, kind=high_severity_present must be present
if ($t.triage.severity_counts.high -gt 0) {
  $hasHighFinding = $false
  foreach ($f in $t.findings) {
    if ($f.kind -eq "high_severity_present") { $hasHighFinding = $true; break }
  }
  Assert ($hasHighFinding) "smoke: expected findings to include kind=high_severity_present when severity_counts.high > 0"
}

# --- loose_events field gate (normal log → 0; field must always exist) ---
Assert-True ($null -ne $o.input_summary.loose_events -or $o.input_summary.loose_events -eq 0) "input_summary.loose_events must exist"
Assert-True ([int]$o.input_summary.loose_events -ge 0) "input_summary.loose_events must be >= 0"

# --- loose parser gate: timestamp-less lines with level keyword are parsed ---
$looseLog = Join-Path (Get-Location).Path "tmp_loose.log"
@'
2026-02-24 11:00:00 INFO boot ok
2026 ERROR db timeout after 3000ms
ERROR out of memory
some random line without a level
'@ | Set-Content -LiteralPath $looseLog -Encoding utf8
$looseOut  = (Invoke-Expression "$Runner analyze `"$looseLog`" --type log --json") -join "`n"
$looseJson = ConvertFrom-JsonStrict $looseOut
Assert-True ($looseJson.input_summary.lines -eq 4)        "loose: lines must be 4"
Assert-True ($looseJson.input_summary.events -eq 3)       "loose: events must be 3 (1 strict + 2 loose)"
Assert-True ($looseJson.input_summary.loose_events -eq 2) "loose: loose_events must be 2"
Assert-True ($looseJson.triage.confidence_reasons -match "loose pattern") "loose: confidence_reasons must mention loose pattern"
# fingerprint engine must produce a fingerprint for the timestamp-less ERROR line
$looseFps = $looseJson.triage.top_fingerprints | ForEach-Object { $_.fingerprint }
Assert-True ($looseFps -contains "db timeout after <N>ms") "loose: fingerprint 'db timeout after <N>ms' must be present"
Remove-Item -LiteralPath $looseLog -Force

# --- directory scan gate ---
$dirPath = Join-Path (Get-Location).Path "tmp_scandir"
$null = New-Item -ItemType Directory -Force -Path $dirPath
@'
2026-02-24 11:00:00 INFO boot
2026-02-24 11:00:01 ERROR db timeout after 2000ms
'@ | Set-Content -LiteralPath (Join-Path $dirPath "a.log") -Encoding utf8
@'
2026-02-24 11:00:02 CRITICAL out of memory
2026-02-24 11:00:03 WARN retrying
'@ | Set-Content -LiteralPath (Join-Path $dirPath "b.log") -Encoding utf8
$dirOut  = (Invoke-Expression "$Runner analyze `"$dirPath`" --glob `"*.log`" --type log --json") -join "`n"
$dirJson = ConvertFrom-JsonStrict $dirOut
Assert-True ($dirJson.input_summary.files -eq 2)  "dirscan: input_summary.files must be 2"
Assert-True ($dirJson.input_summary.lines -eq 4)  "dirscan: input_summary.lines must be 4"
Assert-True ($dirJson.input_summary.source -eq $null) "dirscan: source must be null"
Assert-True ($null -ne $dirJson.triage)            "dirscan: triage must be present"
Remove-Item -Recurse -Force $dirPath

Write-Host "ALL CONTRACT TESTS PASSED OK" -ForegroundColor Green
exit 0
} catch {
  Write-Host "Contract tests failed" -ForegroundColor Red
  Write-Host $_.Exception.Message
  exit 1
}
