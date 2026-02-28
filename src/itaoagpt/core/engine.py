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

    # For now, treat `path` as a file path; directory+glob can be implemented later.
    # We keep `glob` in signature to match CLI contract and avoid TypeError.
    p = Path(path)

    # Delegate to log analyzer.
    # If analyze_log does not accept these yet, adapt here.
    out = analyze_log(
        p,
        lines=lines,
        max_lines=max_lines,
        min_severity=min_severity,
        deterministic=deterministic,
        debug=debug,
    )

    out["version"] = _pkg_version()  # A: single version source (overrides analyzer hardcode)

    out["triage"] = build_triage(
        stats=out.get("stats"),
        top_fingerprints=out.get("top_fingerprints"),
        findings=out.get("findings"),
    )

    out.pop("top_fingerprints", None)  # C: canonical home is triage.top_fingerprints

    return out

