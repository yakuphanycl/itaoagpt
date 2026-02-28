from __future__ import annotations

import importlib.metadata as _imd
from pathlib import Path
from typing import Any

from itaoagpt.core.analyzers.log import analyze_log
from itaoagpt.core.triage import build_triage


def _pkg_version() -> str:
    try:
        return _imd.version("itaoagpt")
    except Exception:
        return "0.4.2"


def _scan_directory(
    path: Path,
    glob_pattern: str,
    max_lines: int | None,
) -> tuple[list[str], int]:
    """Collect lines from all matching files in a directory (sorted for determinism)."""
    files = sorted(f for f in path.glob(glob_pattern) if f.is_file())
    all_lines: list[str] = []
    for f in files:
        file_lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        all_lines.extend(file_lines)
        if max_lines is not None and max_lines > 0 and len(all_lines) >= max_lines:
            all_lines = all_lines[:max_lines]
            break
    return all_lines, len(files)


def run_analysis(
    path: Path,
    analyzer_type: str = "log",
    *,
    lines: list[str] | None = None,
    glob: str | None = None,
    max_lines: int | None = None,
    min_severity: str | None = None,
    deterministic: bool = False,
    debug: bool = False,
) -> dict[str, Any]:
    """
    Contract-safe analysis router.

    CLI may pass extra knobs (glob/max_lines/min_severity). For V0:
    - analyzer_type: only "log" supported
    - glob: accepted for compatibility (directory scanning can be added later)
    - max_lines/min_severity: forwarded to analyzer when supported
    """
    atype = (analyzer_type or "log").strip().lower()

    if atype != "log":
        # V0: keep it explicit
        return {
            "tool": "itaoagpt",
            "version": _pkg_version(),
            "schema_version": "0.1",
            "error": f"unsupported analyzer_type: {analyzer_type} (V0 supports only: log)",
        }

    p = Path(path)
    dir_file_count: int | None = None

    # Directory scan: collect lines from all matching files, pass as lines=
    if lines is None and p.is_dir():
        lines, dir_file_count = _scan_directory(p, glob or "*.log", max_lines)

    out = analyze_log(
        p,
        lines=lines,
        max_lines=max_lines,
        min_severity=min_severity,
        deterministic=deterministic,
        debug=debug,
    )

    if dir_file_count is not None:
        out["input_summary"]["files"] = dir_file_count
        out["input_summary"]["source"] = None  # directory scan, not stdin

    out["version"] = _pkg_version()  # A: single version source (overrides analyzer hardcode)

    out["triage"] = build_triage(
        stats=out.get("stats"),
        top_fingerprints=out.get("top_fingerprints"),
        findings=out.get("findings"),
        loose_events=int((out.get("input_summary") or {}).get("loose_events", 0)),
    )

    out.pop("top_fingerprints", None)  # C: canonical home is triage.top_fingerprints

    return out

