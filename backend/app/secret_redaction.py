import re
from typing import Any


SECRET_PATTERNS = [
    re.compile(r"(?im)^(\s*x-anthropic-billing-header\s*:\s*).*$"),
    re.compile(r"(?i)\bcch\s*=\s*[^;\s,\n]+"),
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9_\-.=]{8,}", re.IGNORECASE),
    re.compile(r"(api[_-]?key\s*[:=]\s*)[A-Za-z0-9_\-.]{8,}", re.IGNORECASE),
]


def redact_text(text: str) -> str:
    out = text
    for pattern in SECRET_PATTERNS:
        out = pattern.sub(lambda m: (m.group(1) if m.lastindex else "") + "<redacted>", out)
    return out


def redact(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, dict):
        return {
            k: (
                "<redacted>"
                if k.lower()
                in {
                    "authorization",
                    "api_key",
                    "x-api-key",
                    "cookie",
                    "x-anthropic-billing-header",
                    "x-anthropic-billing-request",
                }
                else redact(v)
            )
            for k, v in value.items()
        }
    return value
