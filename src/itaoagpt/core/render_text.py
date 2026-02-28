from __future__ import annotations

from typing import Any


def render_text_ci(out: dict[str, Any]) -> str:
    """CI-friendly deterministic key=value text renderer."""
    lines: list[str] = []

    tool = out.get("tool", "itaoagpt")
    version = out.get("version", "?")
    schema = out.get("schema_version", "?")
    lines.append(f"{tool} v{version} schema={schema}")

    # --- Input summary ---
    inp = out.get("input_summary") or {}
    stats = out.get("stats") or {}
    counts = stats.get("counts") or {}
    lines.append(f"file={inp.get('source')}")
    lines.append(
        f"lines={inp.get('lines', 0)} "
        f"events={inp.get('events', 0)} "
        f"loose={inp.get('loose_events', 0)} "
        f"unique={counts.get('unique_fingerprints', 0)}"
    )

    # --- Result summary ---
    triage = out.get("triage") or {}
    findings = out.get("findings") or []
    lines.append("")
    lines.append(f"result.findings={len(findings)}")
    lines.append(f"result.max_severity={triage.get('max_severity')}")
    lines.append(f"result.confidence={triage.get('confidence')}")

    # --- By level ---
    by_level = stats.get("by_level") or out.get("by_level") or {}
    lines.append("")
    for level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        lines.append(f"by_level.{level}={by_level.get(level, 0)}")

    # --- Top fingerprints ---
    top_fps = triage.get("top_fingerprints") or []
    if top_fps:
        lines.append("")
        for idx, fp in enumerate(top_fps, start=1):
            lines.append(f"top_issue.{idx}.severity={fp.get('severity')}")
            lines.append(f"top_issue.{idx}.fingerprint={fp.get('fingerprint')}")
            lines.append(f"top_issue.{idx}.count={fp.get('count')}")

    # --- Actions ---
    actions = triage.get("actions") or []
    if actions:
        lines.append("")
        for idx, action in enumerate(actions, start=1):
            lines.append(f"action.{idx}={action}")

    return "\n".join(lines)
