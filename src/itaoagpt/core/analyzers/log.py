from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from collections import Counter
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

_RE_MS = re.compile(r"\b\d+ms\b")
_RE_INT = re.compile(r"\b\d+\b")
_RE_HEX = re.compile(r"\b0x[0-9a-fA-F]+\b")
_RE_UUID = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
_RE_IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_RE_WS = re.compile(r"\s+")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fingerprint_text(msg: str) -> str:
    s = msg.strip()
    s = _RE_UUID.sub("<uuid>", s)
    s = _RE_HEX.sub("<hex>", s)
    s = _RE_IP.sub("<ip>", s)
    s = _RE_MS.sub("<num>ms", s)
    s = _RE_INT.sub("<num>", s)
    s = _RE_WS.sub(" ", s)
    return s


def _extract_level_and_message(line: str) -> tuple[str | None, str]:
    """
    Beklenen örnek: "2026-02-24 11:00:02 ERROR db timeout after 2000ms"
    Eğer level yakalanamazsa (None, line) döner.
    """
    parts = line.strip().split()
    if len(parts) >= 4:
        level = parts[2].upper()
        msg = " ".join(parts[3:])
        return level, msg
    return None, line.strip()


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
            "by_level": {},
            "stats": {
                "total": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "unknown": 0,
                "by_level": {},
                "unique_fingerprints": 0,
                "total_lines": 0,
                "top_fingerprints": [],
            },
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

    events = p.read_text(encoding="utf-8", errors="replace").splitlines()
    if max_lines is not None and max_lines > 0:
        events = events[: max_lines]

    total = len(events)

    # Collect evidence lines by severity
    high_hits: list[str] = []
    med_hits: list[str] = []
    low_hits: list[str] = []
    by_level: Counter[str] = Counter()
    fp_counter: Counter[str] = Counter()
    fp_examples: dict[str, str] = {}

    for line in events:
        level, msg = _extract_level_and_message(line)
        sev = _LEVEL_TO_SEV.get(level or "INFO", "low")
        if level:
            by_level[level] += 1
            if level in ("WARN", "ERROR", "CRITICAL"):
                fp = f"{level}|{_fingerprint_text(msg)}"
                fp_counter[fp] += 1
                if fp not in fp_examples:
                    fp_examples[fp] = line

        if sev == "high":
            high_hits.append(line)
        elif sev == "medium":
            med_hits.append(line)
        else:
            low_hits.append(line)

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

    top_fingerprints = []
    for fp, cnt in fp_counter.most_common(5):
        top_fingerprints.append({
            "fp": fp,
            "count": int(cnt),
            "example": fp_examples.get(fp),
        })

    high_lvls = {"ERROR", "CRITICAL"}
    medium_lvls = {"WARN", "WARNING"}
    low_lvls = {"INFO", "DEBUG", "TRACE"}
    high = sum(by_level.get(k, 0) for k in high_lvls)
    medium = sum(by_level.get(k, 0) for k in medium_lvls)
    low = sum(by_level.get(k, 0) for k in low_lvls)
    unknown = int(by_level.get("UNKNOWN", 0))
    by_level_out = dict(sorted(by_level.items()))

    return {
        "tool": "itaoagpt",
        "version": "0.1.0",
        "schema_version": "0.1",
        "created_at": "1970-01-01T00:00:00+00:00" if deterministic else _now_iso(),
        "input_summary": {"events": total, "source": None},
        "by_level": by_level_out,
        "stats": {
            "total": int(sum(by_level.values())),
            "high": int(high),
            "medium": int(medium),
            "low": int(low),
            "unknown": int(unknown),
            "by_level": by_level_out,
            "unique_fingerprints": len(fp_counter),
            "total_lines": total,
            "top_fingerprints": top_fingerprints,
        },
        "findings": findings,
    }

