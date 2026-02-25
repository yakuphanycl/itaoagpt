param(
  [string]$Exe = "itaoagpt",
  [string]$Py  = ".\src\itaoagpt\cli\main.py",
  [string]$Log = ".\tmp_test.log",
  [switch]$Wheel
)

$ErrorActionPreference = "Stop"

function Step($name, [scriptblock]$fn) {
  Write-Host "`n==> $name" -ForegroundColor Cyan
  & $fn
}

function Run($cmd) {
  $out = & powershell -NoProfile -Command $cmd 2>&1 | Out-String
  $rc = $LASTEXITCODE
  return [pscustomobject]@{ rc=$rc; out=$out }
}

function Assert-True($cond, $msg) {
  if (-not $cond) { throw $msg }
}

Step "ensure test log" {
  if (-not (Test-Path $Log)) {
    @"
2026-02-24 11:00:00 INFO boot
2026-02-24 11:00:01 WARN cache miss
2026-02-24 11:00:02 ERROR db timeout after 2000ms
2026-02-24 11:00:03 INFO retry
2026-02-24 11:00:04 CRITICAL out of memory
"@ | Set-Content -LiteralPath $Log -Encoding UTF8
    Write-Host "created test log: $Log" -ForegroundColor DarkGreen
  }
}
Step "py_compile" {
  python -m py_compile $Py
  Assert-True ($LASTEXITCODE -eq 0) "py_compile failed"
}

Step "$Exe version" {
  $r = Run "$Exe version"
  Assert-True ($r.rc -eq 0) "version rc != 0"
  Write-Host $r.out
}

Step "contract tests" {
  .\tools\contract_tests.ps1
}

Step "deterministic x3 (byte-identical)" {
  Assert-True (Test-Path $Log) "missing log file: $Log"

  $r1 = Run "$Exe analyze `"$Log`" --type log --json --deterministic"
  $r2 = Run "$Exe analyze `"$Log`" --type log --json --deterministic"
  $r3 = Run "$Exe analyze `"$Log`" --type log --json --deterministic"

  Assert-True ($r1.rc -eq 0) "det run1 rc != 0"
  Assert-True ($r2.rc -eq 0) "det run2 rc != 0"
  Assert-True ($r3.rc -eq 0) "det run3 rc != 0"

  Assert-True ($r1.out -eq $r2.out) "det outputs differ (1 vs 2)"
  Assert-True ($r2.out -eq $r3.out) "det outputs differ (2 vs 3)"
}

Step "out + report roundtrip" {
  $tmp = Join-Path $PWD "out_gate.json"
  if (Test-Path $tmp) { Remove-Item -LiteralPath $tmp -Force }

  $r = Run "$Exe analyze `"$Log`" --type log --json --deterministic --out `"$tmp`""
  Assert-True ($r.rc -eq 0) "analyze --out rc != 0"
  Assert-True (Test-Path $tmp) "expected out file not created"

  $r2 = Run "$Exe report `"$tmp`" --text"
  Assert-True ($r2.rc -eq 0) "report rc != 0"
  Write-Host $r2.out
}

Write-Host "`nRELEASE CHECK PASSED ✅" -ForegroundColor Green


Step "wheel build + install smoke test" {
  if (-not $Wheel) {
    Write-Host "skip: -Wheel not set" -ForegroundColor DarkYellow
    return
  }

  python -m pip install --upgrade build | Out-Null
  python -m build
  Assert-True ($LASTEXITCODE -eq 0) "python -m build failed"

  $whl = Get-ChildItem .\dist -Filter *.whl | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  Assert-True ($null -ne $whl) "No wheel found in .\dist after build"

  $venv = ".\.venv_wheel_test"
  if (Test-Path $venv) { Remove-Item -Recurse -Force $venv }
  python -m venv $venv
  Assert-True ($LASTEXITCODE -eq 0) "venv create failed"

  & "$venv\Scripts\python.exe" -m pip install --upgrade pip | Out-Null
  & "$venv\Scripts\python.exe" -m pip install "$($whl.FullName)" | Out-Null

  & "$venv\Scripts\itaoagpt.exe" version | Out-Null
  Assert-True ($LASTEXITCODE -eq 0) "itaoagpt version failed in wheel venv"

  Assert-True (Test-Path $Log) "missing log file: $Log"
  & "$venv\Scripts\itaoagpt.exe" analyze "$Log" --type log --json --deterministic | Out-Null
  Assert-True ($LASTEXITCODE -eq 0) "itaoagpt analyze failed in wheel venv"

  Write-Host "wheel install smoke test PASSED ✅" -ForegroundColor Green
}



