from __future__ import annotations

import shutil
from typing import Any


def _term_width(default: int = 80) -> int:
    try:
        return shutil.get_terminal_size(fallback=(default, 24)).columns
    except Exception:
        return default


def _box_kv(rows: list[tuple[str, str]], width: int) -> list[str]:
    if not rows:
        return []
    width = max(30, min(width, 120))
    inner = width - 4
    key_w = min(12, max(len(k) for k, _ in rows))
    val_w = max(10, inner - (key_w + 3))
    key_w = min(key_w, inner - 10)
    top = "┌" + "─" * (width - 2) + "┐"
    bot = "└" + "─" * (width - 2) + "┘"
    sep = "│"
    lines = [top]
    for k, v in rows:
        k = (k[:key_w]).ljust(key_w)
        v = str(v)
        if len(v) > val_w:
            v = v[: max(0, val_w - 1)] + "…"
        v = v.ljust(val_w)
        line = f"{sep} {k} │ {v} {sep}"
        if len(line) > width:
            line = line[: width - 1] + "│"
        lines.append(line)
    lines.append(bot)
    return lines


def render_text_table(result: dict) -> str:
    """Human-friendly box-table renderer."""
    w = _term_width(default=80)
    tool = result.get("tool", "itaoagpt")
    ver = result.get("version", "?")
    schema = result.get("schema_version", "?")
    inp = result.get("input_summary", {}) or {}
    tri = result.get("triage", {}) or {}
    stats = result.get("stats") or {}
    counts = stats.get("counts") or {}
    by_level = stats.get("by_level") or result.get("by_level") or {}
    lines: list[str] = []
    lines.append(f"{tool} v{ver} schema={schema}")
    src = inp.get("source", "")
    lns = inp.get("lines", 0)
    evs = inp.get("events", 0)
    loose = inp.get("loose_events", 0)
    uniq = tri.get("unique_fingerprints", counts.get("unique_fingerprints", 0))
    lines.append(f"file={inp.get('source') or inp.get('input_summary', {}).get('source') or src or '?'}")
    lines.append(f"lines={lns} events={evs} loose={loose} unique={uniq}")
    lines.append("")
    box_rows: list[tuple[str, str]] = [
        ("max", str(tri.get("max_severity", "n/a"))),
        ("findings", str(tri.get("finding_count", 0))),
        ("confidence", str(tri.get("confidence", 0.0))),
        ("label", str(tri.get("confidence_label", "n/a"))),
    ]
    lines.extend(_box_kv(box_rows, width=min(w, 72)))
    lines.append("")
    lines.append("By level")
    for k in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        if k in by_level:
            lines.append(f"  {k:<8} {by_level.get(k, 0)}")
    lines.append("")
    top_issues = tri.get("top_issues", []) or []
    if top_issues:
        lines.append("Top issues")
        for i, item in enumerate(top_issues[:5], start=1):
            lines.append(f"  {i}) {item}")
        lines.append("")
    actions = tri.get("actions", []) or []
    if actions:
        lines.append("Actions")
        for a in actions[:8]:
            lines.append(f"  - {a}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


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
    lines.append(f"file={((inp.get('source')) or inp.get('input_summary', {}).get('source') or '?')}")
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


