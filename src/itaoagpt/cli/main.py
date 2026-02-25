
from __future__ import annotations

# stdlib
import sys
import json
import argparse
import importlib.metadata as imd
from pathlib import Path
from typing import Any

# severity ranking (single source of truth)
SEV_RANK = {
    "low": 1,
    "medium": 2,
    "high": 3,
}

DETERMINISTIC_CREATED_AT = "1970-01-01T00:00:00Z"


def _ensure_created_at(out: dict[str, Any], deterministic: bool = False) -> None:
    if "created_at" in out:
        return
    if deterministic:
        out["created_at"] = DETERMINISTIC_CREATED_AT
        return
    from datetime import datetime, timezone

    out["created_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _dump_json(out: dict[str, Any], deterministic: bool = False) -> str:
    return json.dumps(out, ensure_ascii=False, indent=2, sort_keys=deterministic)


# --- FAIL-ON / EXIT-CODE CONTRACT HELPERS ---
def _sev_rank(sev: str) -> int:
    sev = (sev or "").lower().strip()
    return {"low": 1, "medium": 2, "high": 3}.get(sev, 0)

def _max_finding_severity(report: dict) -> str:
    mx = 0
    for f in (report.get("findings") or []):
        mx = max(mx, _sev_rank(f.get("severity")))
    inv = {1: "low", 2: "medium", 3: "high"}
    return inv.get(mx, "low")

def _exit_code_from_fail_on(out: dict, fail_on: str) -> int:
    """
    fail_on semantics (threshold):
      - high   -> rc=2 if any finding severity is high
      - medium -> rc=2 if any finding severity is medium or high
      - low    -> rc=2 if there is any finding at all
      - none/empty -> rc=0 always
    """
    if not fail_on:
        return 0

    fail_on = (fail_on or "").strip().lower()
    if fail_on in ("none", "off", "false", "0"):
        return 0
    if fail_on not in ("low", "medium", "high"):
        # keep CLI resilient; parser should already restrict, but don't crash
        return 0

    findings = (out.get("findings") or [])
    if not findings:
        return 0

    # compute max severity present
    max_rank = 0
    for f in findings:
        s = str(f.get("severity") or "").strip().lower()
        max_rank = max(max_rank, SEV_RANK.get(s, 0))

    # threshold compare
    threshold = SEV_RANK[fail_on]
    return 2 if max_rank >= threshold else 0

def _norm_sev(sev: str | None) -> str:
    s = (sev or "low").strip().lower()
    if s not in SEV_RANK:
        return "low"
    return s


def _rank(sev: str | None) -> int:
    return SEV_RANK.get(_norm_sev(sev), 1)


def _should_fail(findings: list[dict[str, Any]], fail_on: str) -> bool:
    fo = (fail_on or "none").strip().lower()
    if fo == "none":
        return False
    if fo not in SEV_RANK:
        fo = "none"
    thr = SEV_RANK.get(fo, 999)
    for f in findings or []:
        if _rank(f.get("severity")) >= thr:
            return True
    return False

def _norm_sev(s: str | None) -> str:
    x = (s or "low").strip().lower()
    return x if x in SEV_RANK else "low"


def _filter_findings(findings: list[dict[str, Any]], min_severity: str) -> list[dict[str, Any]]:
    m = _norm_sev(min_severity)
    out: list[dict[str, Any]] = []
    for f in findings or []:
        sev = _norm_sev(f.get("severity"))
        if SEV_RANK.get(sev, 1) >= SEV_RANK[m]:
            out.append(f)
    return out


def _print_text(result: dict[str, Any], min_severity: str) -> None:
    print(f"ItaoaGPT v{result.get('version')} ({result.get('schema_version')})")
    print(f"analyzer: {result.get('analyzer')}")

    inp = result.get("input", {}) or {}
    print(f"path: {inp.get('path')}")
    if inp.get("glob") is not None:
        print(f"glob: {inp.get('glob')}")
    if inp.get("max_lines") is not None:
        print(f"max_lines: {inp.get('max_lines')}")

    s = result.get("summary", {}) or {}
    print("")
    print("SUMMARY")
    for k in ("files", "events", "errors", "longest_error_streak"):
        if k in s:
            print(f"- {k}: {s.get(k)}")

    findings = _filter_findings(result.get("findings", []) or [], min_severity)

    print("")
    print(f"FINDINGS (min_severity={_norm_sev(min_severity)})")
    if not findings:
        print("0. (none)")
        return

    for i, f in enumerate(findings, start=1):
        print(f"{i}. [{_norm_sev(f.get('severity'))}] {f.get('title')}")
        hint = f.get("hint")
        if hint:
            print(f"   hint: {hint}")
        ev = f.get("evidence", []) or []
        if ev:
            for line in ev[:5]:
                print(f"   - {line}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="itaoagpt", description="ItaoaGPT (CLI-first analysis tool)")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_an = sub.add_parser("analyze", help="Analyze a path using a specific analyzer type")
    p_an.add_argument("path", help="File or directory path")
    p_an.add_argument("--type", dest="atype", default="log", help="Analyzer type (V0: log)")
    p_an.add_argument("--glob", default="*.log", help="When path is a directory: file glob to include (default: *.log)")
    p_an.add_argument("--max-lines", type=int, default=20000, help="Total max lines to read (V0 safety)")
    p_an.add_argument("--min-severity", default="low", help="Filter findings: low|medium|high (default: low)")
    p_an.add_argument("--fail-on", default="none", help="Exit non-zero if findings at/above: none|low|medium|high")
    p_an.add_argument("--out", default=None, help="Write JSON report to a file")
    p_an.add_argument("--json", action="store_true", help="Print JSON output to stdout")
    p_an.add_argument("--text", action="store_true", help="Print human-readable output to stdout")
    p_an.add_argument("--deterministic", action="store_true", help="Deterministic mode for testing/repeatability")

    p_rep = sub.add_parser("report", help="Print a saved JSON report (from --out)")
    p_rep.add_argument("in_json", help="Path to report JSON")
    p_rep.add_argument("--min-severity", default="low", help="Filter findings: low|medium|high (default: low)")
    p_rep.add_argument("--fail-on", default="none", help="Exit non-zero if findings at/above: none|low|medium|high")
    p_rep.add_argument("--json", action="store_true", help="Print JSON output to stdout")
    p_rep.add_argument("--text", action="store_true", help="Print human-readable output to stdout")

    sub.add_parser("version", help="Print version info")
    return p
def cmd_version() -> int:
    # Version: package metadata (editable install dahil) → en sağlam kaynak
    try:
        ver = imd.version("itaoagpt")
    except Exception:
        ver = "0.0.0"

    out = {"tool": "itaoagpt", "version": ver, "schema_version": "0.1"}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_analyze(
    path_str: str,
    atype: str,
    as_json: bool,
    as_text: bool,
    deterministic: bool,
    glob: str,
    max_lines: int,
    min_severity: str,
    out_path: str | None,
    fail_on: str,
) -> int:
    p = Path(path_str).expanduser().resolve()
    if not p.exists():
        print(f"[ERR] path not found: {p}", file=sys.stderr)
        return 2

    # lazy import so `version` never depends on engine
    from itaoagpt.core.engine import run_analysis

    result = run_analysis(
        path=p,
        analyzer_type=atype,
        deterministic=deterministic,
        glob=glob,
        max_lines=max_lines,
    )

    # default output mode
    if not as_json and not as_text:
        as_text = True

    # optionally write JSON to file (raw engine result)
    if out_path:
        outp = Path(out_path).expanduser().resolve()
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(_dump_json(result, deterministic=deterministic), encoding="utf-8")
        print(f"[OK] wrote: {outp}")

    # Build a "contract-safe" output object (used for stdout + fail-on decisions).
    out2 = dict(result)
    out2["findings"] = _filter_findings(result.get("findings", []) or [], min_severity)

    # normalize severity: treat any CRITICAL evidence as high (contract expectation)
    try:
        for f in (out2.get("findings") or []):
            ev = " ".join((f.get("evidence") or []))
            if "CRITICAL" in ev.upper():
                f["severity"] = "high"
    except Exception:
        pass

    # ensure created_at exists (contract)
    _ensure_created_at(out2, deterministic=deterministic)

    # ensure input_summary exists (contract)
    if "input_summary" not in out2:
        summ = out2.get("summary") or {}
        inp = out2.get("input") or {}
        out2["input_summary"] = {
            "events": summ.get("events"),
            "source": inp.get("source"),
        }

    # stdout
    if as_json:
        print(_dump_json(out2, deterministic=deterministic))
    if as_text:
        # Human output MUST be derived from JSON output (single source of truth)
        print(render_human_from_json(out2))

    fail_on = (fail_on or "").strip().lower()
    if fail_on in ("none", "off", "false", "0") or fail_on not in SEV_RANK:
        fail_on = ""

    sev_rank = SEV_RANK
    max_sev = None
    for f in (out2.get("findings") or []):
        sev = str(f.get("severity") or "").strip().lower()
        if sev not in sev_rank:
            continue
        if max_sev is None or sev_rank[sev] > sev_rank[max_sev]:
            max_sev = sev

    # ------------------------------------------------------------
    # EXIT CODE CONTRACT
    # analyze is informational unless --fail-on is explicitly used
    # ------------------------------------------------------------

    if fail_on:
        # fail-on threshold breached?
        if max_sev is not None:
            if sev_rank[max_sev] >= sev_rank[fail_on]:
                return 2

    # informational analyze (even if ERROR/CRITICAL exists)
    return 0

def cmd_report(in_json: str, as_json: bool, as_text: bool, min_severity: str, fail_on: str) -> int:
    p = Path(in_json).expanduser().resolve()
    if not p.exists():
        print(f"[ERR] report json not found: {p}", file=sys.stderr)
        return 2

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[ERR] failed to parse json: {p}", file=sys.stderr)
        print(str(e), file=sys.stderr)
        return 2

    if not as_json and not as_text:
        as_text = True

    out2 = dict(data)
    out2["findings"] = _filter_findings(out2.get("findings", []) or [], min_severity)

    # normalize severity: treat any CRITICAL evidence as high (contract expectation)
    try:
        for f in (out2.get("findings") or []):
            ev = " ".join((f.get("evidence") or []))
            if "CRITICAL" in ev.upper():
                f["severity"] = "high"
    except Exception:
        pass

    # ensure created_at exists (contract)
    _ensure_created_at(out2, deterministic=False)

    # ensure input_summary exists (contract)
    if "input_summary" not in out2:
        summ = out2.get("summary") or {}
        inp = out2.get("input") or {}
        out2["input_summary"] = {
            "events": summ.get("events"),
            "source": inp.get("source"),
        }

    if as_text:
        print(render_human_from_json(out2))
    if as_json:
        print(_dump_json(out2, deterministic=False))

    return _exit_code_from_fail_on(out2, fail_on)
def render_human_from_json(out: dict) -> str:
    # Human output MUST be derived from JSON output (single source of truth)
    inp = out.get("input_summary") or {}
    findings = out.get("findings") or []

    lines = []
    lines.append("ItaoaGPT")
    lines.append(f"Events: {inp.get('events')}")
    lines.append(f"Source: {inp.get('source')}")
    lines.append("")
    lines.append(f"Findings: {len(findings)}")

    for i, f in enumerate(findings, 1):
        sev = f.get("severity")
        title = f.get("title")
        lines.append(f"{i}. [{sev}] {title}")

    return "\n".join(lines)


def render_human_report(out: dict) -> str:
    return render_human_from_json(out)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.cmd == "version":
        return cmd_version()

    if args.cmd == "analyze":
        return cmd_analyze(
            path_str=args.path,
            atype=args.atype,
            as_json=args.json,
            as_text=args.text,
            deterministic=args.deterministic,
            glob=args.glob,
            max_lines=args.max_lines,
            min_severity=args.min_severity,
            out_path=args.out, fail_on=args.fail_on)

    if args.cmd == "report":
        return cmd_report(
            in_json=args.in_json,
            as_json=args.json,
            as_text=args.text,
            min_severity=args.min_severity, fail_on=args.fail_on)

    print("[ERR] unknown command", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())



































