"""Deterministic PII scrubbing and untrusted-text sanitization helpers."""

from __future__ import annotations

import re

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(r"(?:\+?91[\s-]?)?[6-9]\d{9}\b|\+\d{1,3}[\s-]?\d{6,12}\b")
_API_KEY_RE = re.compile(r"\bAIza[0-9A-Za-z_-]{16,}\b")
_BEARER_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._-]{12,}\b", re.I)

_INJECTION_SUMMARY_RE = re.compile(
    r"(ignore\s+(all\s+)?(previous|prior)\s+instructions|"
    r"<\s*/?\s*system\s*>|\[admin\s+override\]|developer\s+instruction|"
    r"drop\s+table|union\s+select|gemini_api_key|respond\s+only\s+with|"
    r"pretend\s+there\s+is\s+no|skip\s+human\s+review)",
    re.I,
)


def scrub_pii(text: str) -> str:
    """Redact common citizen PII and credentials before LLM/telemetry boundaries."""
    if not text:
        return ""
    cleaned = _API_KEY_RE.sub("[REDACTED_KEY]", text)
    cleaned = _BEARER_RE.sub("Bearer [REDACTED_TOKEN]", cleaned)
    cleaned = _EMAIL_RE.sub("[REDACTED_EMAIL]", cleaned)
    cleaned = _PHONE_RE.sub("[REDACTED_PHONE]", cleaned)
    return cleaned


def sanitize_untrusted_summary(text: str, *, fallback_label: str) -> str:
    """Return a clean summary without echoing PII or prompt-injection payloads."""
    normalized = " ".join(scrub_pii(text).split())
    if not normalized or _INJECTION_SUMMARY_RE.search(normalized):
        return (
            f"Citizen waste report classified by deterministic fallback ({fallback_label}); "
            "operator review recommended."
        )
    if len(normalized) > 220:
        return normalized[:217].rstrip() + "..."
    return normalized

