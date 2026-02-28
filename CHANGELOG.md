# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [0.8.1] — 2026-02-28

### Changed
- Version bump; release_check.ps1 passed clean on v0.8.0 codebase

---

## [0.8.0] — 2026-02-28

### Added
- Two-layer log parser:
  - **Layer A (strict)**: existing `timestamp + level + message` format
  - **Layer B (loose)**: lines without timestamps are matched by `ERROR|WARN|CRITICAL|FATAL` keyword; fingerprint engine still applies
- `input_summary.loose_events`: count of lines parsed via loose fallback
- `triage.confidence_reasons` now includes `"parsed via loose pattern (no timestamp): N events"` when loose parsing occurred
- Contract test: `loose_events` field gate + dedicated loose-parse log test (fingerprint, event count, confidence_reasons)

---

## [0.7.1] — 2026-02-28

### Fixed
- `src/itaoagpt/__init__.py`: eliminated stale hardcoded `__version__ = "0.5.0"`;
  now derived from `importlib.metadata` — same source as the CLI `version` command

### Added
- `README.md`: JSON Contract v0.7.0 table documenting guaranteed output fields

---

## [0.7.0] — 2026-02-28

### Added
- `triage.severity_counts`: `{high: N, medium: N, low: N}` — CI-friendly numeric finding breakdown
- `triage.confidence_reasons`: list of strings explaining the confidence tier
  (e.g. `["low sample size: 3 events (threshold: 50)"]`)
- Contract test: `triage.severity_counts` and `triage.confidence_reasons` gate
- Stdin smoke test block: full structural contract for `analyze -` output

---

## [0.6.0] — 2026-02-28

### Added
- `itaoagpt analyze -` stdin support: pipe log content directly into the CLI
  (`cat app.log | itaoagpt analyze - --type log --json`)
- `input_summary.source` reports `"<stdin>"` when reading from stdin
- Contract test stdin gate: verifies `source`, `lines`, and `triage` fields

---

## [0.5.1] — 2026-02-28

Patch release — release tooling hardened for repeatable CI/local runs.

### Changes
- `tools/release_check.ps1`: replaced `pip show build` check with `pip install build -q` (idempotent, no crash on missing dep).
- `tools/contract_tests.ps1`: ensured wheel smoke tests run gates using the wheel venv interpreter (`.venv_wheel_test` Python), preventing PATH / interpreter drift.

### Why this matters
These changes make release verification more deterministic across machines and CI by removing dependency on global pip state and guaranteeing tests run against the intended environment.

---

## [0.5.0] — 2026-02-28

Minor version milestone — consolidates all 0.4.x work into a stable baseline.

### Summary of 0.4.x → 0.5.0
- `fingerprint.py`: `normalize_message()` pipeline (UUID / HEX / IPv4 / EMAIL / 2+ digit numbers)
- `triage.top_fingerprints`: single canonical source; root duplicate and `top_fp` removed
- Version read from `importlib.metadata` — hardcoded `"0.1.0"` eliminated
- BOM (`\ufeff`) stripped from first log line
- Contract tests: version + editable install sanity gates (A1 / A2 / B)
- `release.ps1`: tag/version/working-tree/editable guards; `$LASTEXITCODE` error surfacing

---

## [0.4.5] — 2026-02-28

### Changed
- Version bump; no functional changes

---

## [0.4.4] — 2026-02-28

### Fixed
- `release.ps1`: `| Out-Null` was silently swallowing `gh create/edit` errors;
  replaced with `$LASTEXITCODE` check — failures now surface immediately

---

## [0.4.3] — 2026-02-28

### Added
- `src/itaoagpt/core/fingerprint.py`: new `normalize_message()` pipeline masks
  UUID / HEX / IPv4 / EMAIL / 2+ digit numbers in deterministic order
- `tools/release.ps1`: create-or-edit GitHub release with tag/version guard,
  working-tree cleanliness check, and editable-install guard
- `tools/contract_tests.ps1`: version + editable install sanity gates
  (A1: CLI JSON version matches git tag; A2: `importlib.metadata` matches;
  B: import must come from `src/`, not site-packages)

### Changed
- `triage.top_fingerprints` is now the single canonical source; root-level
  `top_fingerprints` and `triage.top_fp` removed
- Version read from `importlib.metadata.version("itaoagpt")` in engine and
  log analyzer — no more hardcoded `"0.1.0"` in JSON output
- Confidence formula documented in-code with threshold table
- Expected version in contract tests auto-derived from `git describe --tags`

### Fixed
- BOM (`\ufeff`) stripped from first log line — prevents parse miss on
  Windows-encoded files
- `release.ps1`: `| Out-Null` was silently swallowing `gh` errors; fixed with
  `$LASTEXITCODE` check

---

## [0.4.2] — 2026-02-27

### Added
- `src/itaoagpt/core/fingerprint.py`: new `normalize_message()` pipeline masks
  UUID / HEX / IPv4 / EMAIL / 2+ digit numbers in deterministic order
- `tools/release.ps1`: create-or-edit GitHub release with tag/version guard
  and working-tree cleanliness check

### Changed
- `triage.top_fingerprints` is the single canonical source for fingerprint data;
  root-level `top_fingerprints` and `triage.top_fp` removed
- Version now read from `importlib.metadata.version("itaoagpt")` in engine and
  log analyzer — no more hardcoded `"0.1.0"` in JSON output
- Confidence formula documented in-code with threshold table

### Fixed
- BOM (`\ufeff`) stripped from first log line — prevents parse miss on
  Windows-encoded files

### Tooling
- `tools/contract_tests.ps1`: version + editable install sanity gates
  (A1: CLI JSON version matches git tag; A2: `importlib.metadata` matches;
  B: import must come from `src/`, not site-packages)
- `tools/release.ps1`: refuses release if package imports from site-packages
- Expected version auto-derived from `git describe --tags` — no hardcoding

---

## [0.4.1] — 2026-02-27

### Changed
- Typed JSON assertions in contract tests (`input_summary`, `stats.by_level`,
  `unique_fingerprints`) — previously only string-match checks

---

## [0.4.0] — 2026-02-27

### Added
- Stable, deterministic fingerprint sort: count desc → severity desc → fingerprint asc
- `triage.actions` derived from `top_fingerprints` via keyword map (no raw string parsing)

---

## [0.3.0] — 2026-02-27

### Added
- `fingerprint.sample`: first raw log line that produced the fingerprint
- `fingerprint.levels`: per-level breakdown (ERROR/WARNING/…) per fingerprint
- `triage.top_fp`: structured top-fingerprint list (later superseded by `triage.top_fingerprints`)

---

## [0.2.1] — 2026-02-27

### Added
- `triage.summary`: single-line human label (findings / max severity / event count)
- `triage.confidence` + `confidence_label`: volume-based confidence score
- `triage.top_issues`: formatted strings for human display (deprecated as of 0.4.2)
- `triage.actions`: up to 3 deterministic actions derived from keyword map

---

## [0.2.0] — 2026-02-27

### Added
- `stats.by_level`: per-level event counts in JSON output
- `stats.counts.unique_fingerprints`: distinct fingerprint count
- `top_fingerprints`: top-10 fingerprints with count and severity
- `input_summary.lines` / `input_summary.events`: raw line count vs parsed event count
- CI: GitHub Actions wheel smoke test + contract tests on push and tags

### Fixed
- UTF-8 stdout/stderr forced on Windows (avoids cp1252 UnicodeEncodeError)
- `analyze` exit code is now informational (rc=0) unless `--fail-on` is set

---

## [0.1.2] — 2026-02-27

### Changed
- Triage actions derived deterministically from keyword→action map (capped at 3)
- Contract strengthened: `triage.actions` must be a non-empty array of non-empty strings

---

## [0.1.1] — 2026-02-27

### Fixed
- Robust JSON parse in PowerShell contract tests (UTF-8 safe, handles string arrays)
- `triage.total_events` aligned with `input_summary.lines`
- Contract tests made self-contained (no external fixtures)

---

## [0.1.0] — 2026-02-26

### Added
- Initial release: `itaoagpt analyze` command with `--type log`
- Log analyzer: best-effort line parsing, severity classification (high/medium/low)
- `--fail-on` exit code contract (rc=2 on threshold breach)
- `--min-severity` finding filter
- `--deterministic` mode for repeatable output
- `--json` / `--text` output modes; `--out` for file write
- `itaoagpt version` command (reads from package metadata)
- `tools/contract_tests.ps1`: PowerShell contract test suite
- `tools/release_check.ps1`: wheel build + reinstall smoke test
