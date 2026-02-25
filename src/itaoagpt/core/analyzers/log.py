from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_SEV_RANK = {"low": 1, "medium": 2, "high": 3}
_LEVEL_TO_SEV = {
    "DEBUG": "low",
    "INFO": "low",
    "WARN": "medium",
    "WARNING": "medium",
    "ERROR": "high",
    "CRITICAL": "high",
    "FATAL": "high",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def analyze_log(
    path: Path,
    deterministic: bool = False,
    *,
    max_lines: int | None = None,
    min_severity: str | None = None,
) -> dict[str, Any]:
    """
    V0 log analyzer.

    - Reads a log file (best-effort parsing).
    - Supports max_lines safety cap.
    - Supports min_severity filtering for findings.
    """
    p = Path(path)

    if not p.exists():
        return {
            "tool": "itaoagpt",
            "version": "0.1.0",
            "schema_version": "0.1",
            "created_at": "1970-01-01T00:00:00+00:00" if deterministic else _now_iso(),
            "input_summary": {"events": 0, "source": None},
            "findings": [
                {
                    "kind": "input_error",
                    "severity": "high",
                    "title": f"log file not found: {str(p)}",
                    "evidence": [],
                    "hint": "Verilen path doğru mu? Dosya gerçekten var mı?",
                }
            ],
        }

    # Normalize knobs
    ms = (min_severity or "low").strip().lower()
    if ms not in _SEV_RANK:
        ms = "low"
    ms_rank = _SEV_RANK[ms]

    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    if max_lines is not None and max_lines > 0:
        lines = lines[: max_lines]

    total = len(lines)

    # Collect evidence lines by severity
    high_hits: list[str] = []
    med_hits: list[str] = []
    low_hits: list[str] = []

    for ln in lines:
        # crude level detection (works for: "YYYY ... LEVEL message")
        parts = ln.strip().split()
        level = None
        for token in parts[:6]:  # look at early tokens
            t = token.strip().upper().rstrip(":")
            if t in _LEVEL_TO_SEV:
                level = t
                break

        sev = _LEVEL_TO_SEV.get(level or "INFO", "low")
        if sev == "high":
            high_hits.append(ln)
        elif sev == "medium":
            med_hits.append(ln)
        else:
            low_hits.append(ln)

    findings: list[dict[str, Any]] = []

    # Findings: high severity
    if _SEV_RANK["high"] >= ms_rank and high_hits:
        findings.append(
            {
                "kind": "high_severity_present",
                "severity": "high",
                "title": f"ERROR/CRITICAL tespit edildi: {len(high_hits)} adet",
                "evidence": high_hits[:5],
                "hint": "İlk görünen high-severity hatadan başlayıp aynı request/trace akışını takip et.",
            }
        )

    # Findings: medium severity
    if _SEV_RANK["medium"] >= ms_rank and med_hits:
        findings.append(
            {
                "kind": "medium_severity_present",
                "severity": "medium",
                "title": f"WARN tespit edildi: {len(med_hits)} adet",
                "evidence": med_hits[:5],
                "hint": "WARN'lar genelde gelecekteki ERROR'ların habercisi. Cache/timeout/limit izleri var mı bak.",
            }
        )

    # If nothing found above threshold, add a calm finding
    if not findings:
        findings.append(
            {
                "kind": "no_findings_above_threshold",
                "severity": "low",
                "title": f"'{ms}' eşiğinin üstünde bulgu yok",
                "evidence": [],
                "hint": "Eşik değerini düşürerek (low) tekrar deneyebilirsin.",
            }
        )

    return {
        "tool": "itaoagpt",
        "version": "0.1.0",
        "schema_version": "0.1",
        "created_at": "1970-01-01T00:00:00+00:00" if deterministic else _now_iso(),
        "input_summary": {"events": total, "source": None},
        "findings": findings,
    }
