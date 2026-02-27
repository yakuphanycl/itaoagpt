from __future__ import annotations

import re

# Order matters: more-specific patterns run before the generic number sweep.
_RE_UUID = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_RE_EMAIL = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
_RE_IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_RE_HEX = re.compile(r"\b0x[0-9a-fA-F]+\b")
# 2+ digit numbers; lookbehind/ahead avoids splitting mid-number sequences.
# Does NOT use \b so it correctly matches digits adjacent to letters (e.g. "2000ms").
_RE_N = re.compile(r"(?<!\d)\d{2,}(?!\d)")
_RE_WS = re.compile(r"\s+")

_MAX_LEN = 160


def normalize_message(text: str) -> str:
    """Mask volatile tokens in a log message to produce a stable fingerprint string.

    Pipeline (order is significant):
        UUID    -> <UUID>
        e-mail  -> <EMAIL>
        IPv4    -> <IP>
        hex lit -> <HEX>
        2+ digit numbers -> <N>   (covers timestamps, durations, port numbers, …)
        whitespace runs -> single space
        truncate at 160 chars
    """
    s = text.strip()
    s = _RE_UUID.sub("<UUID>", s)
    s = _RE_EMAIL.sub("<EMAIL>", s)
    s = _RE_IP.sub("<IP>", s)
    s = _RE_HEX.sub("<HEX>", s)
    s = _RE_N.sub("<N>", s)
    s = _RE_WS.sub(" ", s)
    if len(s) > _MAX_LEN:
        s = s[:_MAX_LEN].rstrip() + "..."
    return s
