from __future__ import annotations

import re
from typing import Any

_SEV_RANK: dict[str, int] = {"low": 1, "medium": 2, "high": 3}

_ACTION_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"timeout", re.I), "DB timeout/pool/latency kontrolu"),
    (re.compile(r"out of memory|oom", re.I), "memory limit/leak/payload size"),
    (re.compile(r"retry", re.I), "upstream instability, backoff/retry policy"),
    (re.compile(r"connection refused", re.I), "servis ayakta mi? port/firewall"),
    (re.compile(r"critical", re.I), "crash dump / core / immediate rollback opsiyonu"),
]


def _actions_from_top_fp(top_fp: list[dict[str, Any]]) -> list[str]:
    """Derive actions from structured top_fp (no string parsing)."""
    seen: set[str] = set()
    actions: list[str] = []
    for t in top_fp:
        text = t.get("fingerprint", "")
        for pattern, action in _ACTION_RULES:
            if pattern.search(text) and action not in seen:
                seen.add(action)
                actions.append(action)
                if len(actions) == 3:
                    return actions
    return actions


def build_triage(
    *,
    stats: dict[str, Any] | None,
    top_fingerprints: list[dict[str, Any]] | None,
    findings: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    _stats = stats or {}
    _fps = top_fingerprints or []
    _findings = findings or []

    max_sev = "none"
    for f in _findings:
        s = (f.get("severity") or "").strip().lower()
        if s in _SEV_RANK:
            if max_sev == "none" or _SEV_RANK[s] > _SEV_RANK.get(max_sev, 0):
                max_sev = s

    counts = _stats.get("counts") or {}
    total_events = int(_stats.get("total", 0))
    unique_fps = int(counts.get("unique_fingerprints", 0))
    finding_count = len(_findings)

    # confidence: based on volume of observed events
    if total_events == 0:
        confidence = 0.0
        confidence_label = "none"
    elif total_events < 50:
        confidence = 0.4
        confidence_label = "low"
    elif total_events < 500:
        confidence = 0.7
        confidence_label = "medium"
    else:
        confidence = 1.0
        confidence_label = "high"

    # summary: single-line human label (ASCII separators for terminal safety)
    summary = (
        f"{finding_count} finding{'s' if finding_count != 1 else ''}"
        f" | max: {max_sev}"
        f" | {total_events} events"
        f" | {unique_fps} unique patterns"
    )

    # top_fp: primary structured field (V0.4+)
    top_fp = [
        {
            "fingerprint": t.get("fingerprint", "?"),
            "count": t.get("count", 0),
            "severity": t.get("severity", "low"),
            "sample": t.get("sample", ""),
        }
        for t in _fps[:3]
    ]

    # actions derived from top_fp (structured — no string parsing)
    actions = _actions_from_top_fp(top_fp)

    # top_issues: formatted strings for human display
    # DEPRECATED: primary as of V0.4, deprecated in V0.5, removal candidate in V1.0
    top_issues: list[str] = [
        f"[{t['severity']}] {t['fingerprint']} ({t['count']})"
        for t in top_fp
    ]

    return {
        "max_severity": max_sev,
        "finding_count": finding_count,
        "total_events": total_events,
        "unique_fingerprints": unique_fps,
        "top_fingerprints": _fps[:3],
        "confidence": confidence,
        "confidence_label": confidence_label,
        "summary": summary,
        "top_fp": top_fp,           # primary (V0.4+)
        "top_issues": top_issues,   # deprecated V0.5, removal candidate V1.0
        "actions": actions,
    }
