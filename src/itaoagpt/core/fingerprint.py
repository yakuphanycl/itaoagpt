from __future__ import annotations

import re


# Precompiled patterns: small, readable, deterministic
_RE_UUID = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_RE_HEX = re.compile(r"\b0x[0-9a-fA-F]+\b")
_RE_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_RE_EMAIL = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")

# Numbers: 2+ digits. Uses lookahead/lookbehind instead of \b so that
# adjacent-letter sequences like "2000ms" are also matched ("2000" has no
# word boundary before "m", but it is not preceded/followed by another digit).
_RE_NUM = re.compile(r"(?<!\d)\d{2,}(?!\d)")


def normalize_message(text: str) -> str:
    """
    Normalize volatile tokens in log messages so the same issue groups together.

    This function is intentionally conservative: it aims to reduce entropy
    without requiring format-specific knowledge.

    Examples:
      - "timeout after 2000ms" -> "timeout after <N>ms"
      - "uuid=..." -> "uuid=<UUID>"
      - "0xDEADBEEF" -> "<HEX>"
    """
    if not text:
        return ""

    s = text.strip()

    # Order matters: do specific tokens first, then generic numbers
    s = _RE_UUID.sub("<UUID>", s)
    s = _RE_HEX.sub("<HEX>", s)
    s = _RE_IPV4.sub("<IP>", s)
    s = _RE_EMAIL.sub("<EMAIL>", s)
    s = _RE_NUM.sub("<N>", s)

    # Collapse repeated whitespace
    s = " ".join(s.split())
    return s
