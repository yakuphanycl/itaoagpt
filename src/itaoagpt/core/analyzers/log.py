from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any


_SEV_RANK = {"low": 1, "medium": 2, "high": 3}
_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

_RE_MS = re.compile(r"\b\d+ms\b")
_RE_INT = re.compile(r"\b\d+\b")
_RE_HEX = re.compile(r"\b0x[0-9a-fA-F]+\b")
_RE_UUID = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
_RE_IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_RE_WS = re.compile(r"\s+")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_fingerprint(msg: str) -> str:
    s = msg.strip()
    s = _RE_HEX.sub("<HEX>", s)
    s = _RE_INT.sub("<N>", s)
    if len(s) > 160:
        s = s[:160].rstrip() + "..."
    return s


def _sev_from_level(level: str) -> str:
    if level in ("ERROR", "CRITICAL"):
        return "high"
    if level == "WARNING":
        return "medium"
    return "low"


def _max_sev(sevs: list[str]) -> str:
    rank = {"low": 1, "medium": 2, "high": 3}
    best = "low"
    for sev in sevs:
        if rank.get(sev, 1) > rank[best]:
            best = sev
    return best


def _fingerprint_text(msg: str) -> str:
    s = msg.strip()
    s = _RE_UUID.sub("<uuid>", s)
    s = _RE_IP.sub("<ip>", s)
    s = _RE_MS.sub("<N>ms", s)
    s = _RE_WS.sub(" ", s)
    return _normalize_fingerprint(s)


def _normalize_level(level: str | None) -> str | None:
    if not level:
        return None
    norm = level.strip().upper()
    if norm == "WARN":
        norm = "WARNING"
    elif norm == "FATAL":
        norm = "CRITICAL"
    return norm if norm in _LEVELS else None


def _extract_level_and_message(line: str) -> tuple[str | None, str]:
    """
    Beklenen ornek: "2026-02-24 11:00:02 ERROR db timeout after 2000ms"
    Eger level yakalanamazsa (None, line) doner.
    """
    parts = line.strip().split()
    if len(parts) >= 4:
        level = _normalize_level(parts[2])
        msg = " ".join(parts[3:])
        return level, msg
    return None, line.strip()


def analyze_log(
    path: Path,
    deterministic: bool = False,
    *,
    max_lines: int | None = None,
    min_severity: str | None = None,
    debug: bool = False,
) -> dict[str, Any]:
    """
    V0 log analyzer.

    - Reads a log file (best-effort parsing).
    - Supports max_lines safety cap.
    - Supports min_severity filtering for findings.
    """
    p = Path(path)

    if not p.exists():
        by_level_out = {k: 0 for k in _LEVELS}
        out: dict[str, Any] = {
            "tool": "itaoagpt",
            "version": "0.1.0",
            "schema_version": "0.1",
            "created_at": "1970-01-01T00:00:00+00:00" if deterministic else _now_iso(),
            "input_summary": {"events": 0, "source": None},
            "by_level": by_level_out,
            "stats": {
                "total": 0,
                "by_level": by_level_out,
                "counts": {
                    "unique_fingerprints": 0,
                },
            },
            "top_fingerprints": [],
            "findings": [
                {
                    "kind": "input_error",
                    "severity": "high",
                    "title": f"log file not found: {str(p)}",
                    "evidence": [],
                    "hint": "Verilen path dogru mu? Dosya gercekten var mi?",
                }
            ],
        }
        if debug and not deterministic:
            out["debug_meta"] = {"lines_read": 0, "min_severity": None}
        return out

    ms = (min_severity or "low").strip().lower()
    ms_rank = _SEV_RANK.get(ms, 1)

    events = p.read_text(encoding="utf-8", errors="replace").splitlines()
    if max_lines is not None and max_lines > 0:
        events = events[: max_lines]

    total = len(events)

    high_hits: list[str] = []
    med_hits: list[str] = []
    low_hits: list[str] = []
    by_level: Counter[str] = Counter()
    fp_counter: Counter[str] = Counter()
    fp_sev: dict[str, str] = {}
    fp_sample: dict[str, str] = {}
    fp_levels: dict[str, Counter[str]] = {}

    for line in events:
        level, msg = _extract_level_and_message(line)
        level = level or "INFO"
        if level not in _LEVELS:
            level = "INFO"

        msg = (msg or line).strip()
        sev = _sev_from_level(level)

        by_level[level] += 1

        fp = _fingerprint_text(msg)
        fp_counter[fp] += 1
        prev = fp_sev.get(fp)
        fp_sev[fp] = sev if prev is None else _max_sev([prev, sev])
        if fp not in fp_sample:
            fp_sample[fp] = line
        if fp not in fp_levels:
            fp_levels[fp] = Counter()
        fp_levels[fp][level] += 1

        if sev == "high":
            high_hits.append(line)
        elif sev == "medium":
            med_hits.append(line)
        else:
            low_hits.append(line)

    findings: list[dict[str, Any]] = []

    if _SEV_RANK["high"] >= ms_rank and high_hits:
        findings.append(
            {
                "kind": "high_severity_present",
                "severity": "high",
                "title": f"ERROR/CRITICAL tespit edildi: {len(high_hits)} adet",
                "evidence": high_hits[:5],
                "hint": "Ilk gorunen high-severity hatadan baslayip ayni request/trace akisina bak.",
            }
        )

    if _SEV_RANK["medium"] >= ms_rank and med_hits:
        findings.append(
            {
                "kind": "medium_severity_present",
                "severity": "medium",
                "title": f"WARN tespit edildi: {len(med_hits)} adet",
                "evidence": med_hits[:5],
                "hint": "WARN kayitlari genelde gelecekteki ERROR'larin habercisi olur.",
            }
        )

    if not findings:
        findings.append(
            {
                "kind": "no_findings_above_threshold",
                "severity": "low",
                "title": f"'{ms}' esiginin ustunde bulgu yok",
                "evidence": [],
                "hint": "Esik degerini dusurerek (low) tekrar deneyebilirsin.",
            }
        )

    _ = _max_sev([str(f.get("severity", "low")) for f in findings])

    top_fingerprints = []
    for fp, cnt in fp_counter.most_common(10):
        sev = fp_sev.get(fp, "low")
        top_fingerprints.append({
            "fingerprint": fp,
            "count": int(cnt),
            "severity": sev,
            "sample": fp_sample.get(fp, ""),
            "levels": {k: int(v) for k, v in (fp_levels.get(fp) or Counter()).items()},
        })

    if min_severity:
        ms = (min_severity or "low").strip().lower()
        ms_rank = _SEV_RANK.get(ms, 1)
        top_fingerprints = [
            fp for fp in top_fingerprints
            if _SEV_RANK.get(fp["severity"], 1) >= ms_rank
        ]

    by_level_out = {k: int(by_level.get(k, 0)) for k in _LEVELS}
    stats = {
        "total": int(total),
        "by_level": by_level_out,
        "counts": {
            "unique_fingerprints": int(len(fp_counter)),
        },
    }

    result: dict[str, Any] = {
        "tool": "itaoagpt",
        "version": "0.1.0",
        "schema_version": "0.1",
        "created_at": "1970-01-01T00:00:00+00:00" if deterministic else _now_iso(),
        "input_summary": {"events": total, "source": None},
        "by_level": by_level_out,
        "stats": stats,
        "top_fingerprints": top_fingerprints,
        "findings": findings,
    }
    if debug and not deterministic:
        result["debug_meta"] = {"lines_read": total, "min_severity": ms}
    return result
