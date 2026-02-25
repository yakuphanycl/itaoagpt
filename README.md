# itaoagpt

CLI-first AI analysis tool.

## Install (dev)
pip install -e .

## Quick start
itaoagpt version
itaoagpt analyze .\tmp_test.log --type log --text

## Contract tests
pwsh .\tools\contract_tests.ps1

## Contracts (V0)

### Deterministic output
- `itaoagpt analyze ... --json --deterministic` MUST produce byte-identical output for the same input.
- This is enforced by `tools/contract_tests.ps1` and `tools/release_check.ps1`.

### Exit codes
- `0` = success
- `2` = contract/validation failure (e.g., `--fail-on`, invalid args, missing file)

### Quality gate
Run this before releases:
```powershell
.\tools\release_check.ps1
```
