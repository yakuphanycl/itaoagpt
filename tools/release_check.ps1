$ErrorActionPreference = "Stop"
function Say($msg) { Write-Host $msg }

# Anchor (file-safe + console-safe)
$invPath = $MyInvocation.MyCommand.Path
if ($invPath) {
  $here = Split-Path -Parent $invPath
} else {
  $here = (Resolve-Path ".\tools").Path
}
$root = Resolve-Path (Join-Path $here "..")

Push-Location $root
try {
  Say "==> python"
  $py = (Get-Command python).Source
  Say "python=$py"

  Say "==> ensure build installed"
  python -m pip install build -q
  if ($LASTEXITCODE -ne 0) { throw "pip install build failed" }

  Say "==> clean dist/"
  if (Test-Path ".\dist") { Remove-Item -Recurse -Force ".\dist" }

  Say "==> build wheel"
  python -m build
  if ($LASTEXITCODE -ne 0) { throw "build failed" }

  Say "==> pick latest wheel"
  $whl = (Get-ChildItem .\dist\itaoagpt-*.whl | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
  if (-not $whl) { throw "wheel not found in dist/" }
  Say "wheel=$whl"

  Say "==> force reinstall wheel (release mode)"
  python -m pip install --force-reinstall $whl
  if ($LASTEXITCODE -ne 0) { throw "pip install wheel failed" }

  Say "==> sanity: import + version + file"
  python -c "import itaoagpt, sys; print('itaoagpt.__file__=', itaoagpt.__file__); print('itaoagpt.__version__=', getattr(itaoagpt,'__version__',None)); print('python=', sys.executable)"
  if ($LASTEXITCODE -ne 0) { throw "import sanity failed" }

  Say "==> itaoagpt version"
  itaoagpt version
  if ($LASTEXITCODE -ne 0) { throw "itaoagpt version failed" }

  Write-Host "==> negative test: fail-on high should return rc=2 (expected)"
  itaoagpt analyze ".\tmp_test.log" --type log --json --fail-on high
  $rc = $LASTEXITCODE
  if ($rc -ne 2) {
    throw "Expected rc=2 for fail-on high, got rc=$rc"
  }
  Write-Host "[OK] ✅ fail-on high returned rc=2 as expected"

  Say "==> contract tests"
  $ct = Join-Path $root "tools\contract_tests.ps1"
  if (-not (Test-Path $ct)) { throw "contract_tests.ps1 not found: $ct" }
  & $ct
  $rc = $LASTEXITCODE

  if ($rc -ne 0) {
    Say "RELEASE CHECK FAIL ❌ rc=$rc"
    exit $rc
  }

  Say "RELEASE CHECK PASS ✅"
  exit 0
}
finally {
  Pop-Location
}

