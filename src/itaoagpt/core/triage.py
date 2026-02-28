from __future__ import annotations

from typing import Any

_SEV_RANK: dict[str, int] = {"low": 1, "medium": 2, "high": 3}

_ACTION_KEYWORD_MAP: tuple[tuple[str, str], ...] = (
    ("timeout", "DB timeout/pool/latency kontrolu"),
    ("out of memory", "memory limit/leak/payload size"),
    ("oom", "memory limit/leak/payload size"),
    ("retry", "upstream instability, backoff/retry policy"),
    ("connection refused", "servis ayakta mi? port/firewall"),
    ("critical", "crash dump / core / immediate rollback opsiyonu"),
)


def _actions_from_fps(top_fp: list[dict[str, Any]]) -> list[str]:
    """Derive deterministic actions from keyword->action map."""
    seen: set[str] = set()
    actions: list[str] = []
    for t in top_fp:
        text = str(t.get("fingerprint", "")).lower()
        for keyword, action in _ACTION_KEYWORD_MAP:
            if keyword in text and action not in seen:
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
    loose_events: int = 0,
    min_severity: str = "low",
) -> dict[str, Any]:
    _stats = stats or {}
    _min_rank = _SEV_RANK.get((min_severity or "low").strip().lower(), 1)
    _fps = [
        fp for fp in (top_fingerprints or [])
        if _SEV_RANK.get((fp.get("severity") or "low").strip().lower(), 1) >= _min_rank
    ]
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

    # severity_counts: finding-level severity breakdown (CI-friendly numeric fields)
    severity_counts: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
    for f in _findings:
        s = (f.get("severity") or "low").strip().lower()
        if s in severity_counts:
            severity_counts[s] += 1

    # Confidence formula (V0.4+, deterministic — based on observed event volume):
    #   0 events       -> 0.0 / "none"   — no data
    #   1–49 events    -> 0.4 / "low"    — too few events for strong conclusions
    #   50–499 events  -> 0.7 / "medium" — moderate signal
    #   500+ events    -> 1.0 / "high"   — sufficient volume for pattern analysis
    if total_events == 0:
        confidence = 0.0
        confidence_label = "none"
        confidence_reasons: list[str] = ["no data: 0 events"]
    elif total_events < 50:
        confidence = 0.4
        confidence_label = "low"
        confidence_reasons = [f"low sample size: {total_events} events (threshold: 50)"]
    elif total_events < 500:
        confidence = 0.7
        confidence_label = "medium"
        confidence_reasons = [f"moderate sample: {total_events} events (threshold: 500)"]
    else:
        confidence = 1.0
        confidence_label = "high"
        confidence_reasons = [f"sufficient volume: {total_events} events"]

    if loose_events > 0:
        confidence_reasons.append(f"parsed via loose pattern (no timestamp): {loose_events} events")

    # summary: single-line human label (ASCII separators for terminal safety)
    summary = (
        f"{finding_count} finding{'s' if finding_count != 1 else ''}"
        f" | max: {max_sev}"
        f" | {total_events} events"
        f" | {unique_fps} unique patterns"
    )

    # top_fingerprints: canonical structured field (V0.4+)
    top_fps = _fps[:3]

    # actions derived from top_fingerprints (keyword matching — no string parsing of raw lines)
    actions = _actions_from_fps(top_fps)

    # top_issues: formatted strings for human display
    # DEPRECATED: removal candidate V1.0 — use top_fingerprints
    top_issues: list[str] = [
        f"[{t.get('severity', 'low')}] {t.get('fingerprint', '?')} ({t.get('count', 0)})"
        for t in top_fps
    ]

    return {
        "max_severity": max_sev,
        "finding_count": finding_count,
        "total_events": total_events,
        "unique_fingerprints": unique_fps,
        "severity_counts": severity_counts,
        "confidence": confidence,
        "confidence_label": confidence_label,
        "confidence_reasons": confidence_reasons,
        "summary": summary,
        "top_fingerprints": top_fps,  # canonical (V0.4+)
        "top_issues": top_issues,     # deprecated: use top_fingerprints; removal candidate V1.0
        "actions": actions,
    }
