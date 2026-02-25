param(
  [string]$Log = ".\tmp_test.log"
)

function Run-Case($level, $expect) {
  Write-Host "`n=== CASE fail-on=$level (expect rc=$expect) ==="
  itaoagpt analyze $Log --json --fail-on $level | Out-Null
  $rc = $LASTEXITCODE
  Write-Host "rc=$rc"
  if ($rc -ne $expect) {
    throw "[FAIL] expected rc=$expect but got rc=$rc"
  }
  Write-Host "[OK] ✅"
}

$allOk = $true
try {
  Run-Case "high"   2
  Run-Case "medium" 2
  Run-Case "low"    0   # low = don't fail (v0 contract)
} catch {
  $allOk = $false
  Write-Host $_ -ForegroundColor Red
}

if ($allOk) {
  Write-Host "`nALL CONTRACT CASES PASSED ✅" -ForegroundColor Green
} else {
  exit 1
}
