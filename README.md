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

| Code | Meaning |
|------|---------|
| `0` | Success — analysis complete, no `--fail-on` threshold breached |
| `1` | User error — path not found, unreadable file, bad arguments |
| `2` | Fail-on triggered — analysis succeeded, findings meet or exceed `--fail-on` threshold |

### JSON Contract: v0.7.0

Fields guaranteed to be present in every `analyze --json` response:

| Field | Type | Meaning |
|---|---|---|
| `input_summary.lines` | int | Raw line count read from input |
| `input_summary.events` | int | Lines successfully parsed (≤ lines) |
| `input_summary.source` | str\|null | `"<stdin>"` when piped, `null` for file |
| `stats.total` | int | Always equals `input_summary.lines` |
| `triage.severity_counts` | object | `{high, medium, low}` — finding-level counts |
| `triage.confidence_label` | str | `"none"` / `"low"` / `"medium"` / `"high"` |
| `triage.confidence_reasons` | str[] | Why confidence is at this tier (≥ 1 item) |

Fields are **additive-only** — existing fields will not be removed or renamed in minor versions.

`--min-severity` filters both `findings` and triage summary/actions (top_fingerprints, top_issues, actions).

### Quality gate
Run this before releases:
```powershell
.\tools\release_check.ps1
```
