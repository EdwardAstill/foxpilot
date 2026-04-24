"""Safety utilities for browser-agent workflows."""

from __future__ import annotations

import re
from urllib.parse import urlparse


ACTION_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("delete", ("delete", "remove", "destroy", "drop")),
    ("purchase", ("purchase", "buy", "order now", "place order")),
    ("send", ("send", "email", "message", "reply")),
    ("publish", ("publish", "release", "deploy", "post")),
    ("merge", ("merge", "merge pull request", "squash and merge")),
    ("transfer", ("transfer ownership", "transfer")),
    ("payment", ("payment", "pay", "submit payment", "checkout")),
)


SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)(authorization:\s*bearer\s+)[^\s]+"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token|password)\s*[:=]\s*([^\s'\"]+)"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{10,}\b"),
)


def classify_action(label: str) -> str | None:
    """Return the dangerous-action category for a label, if any."""

    normalized = " ".join(label.casefold().split())
    if not normalized:
        return None

    for category, terms in ACTION_PATTERNS:
        if any(term in normalized for term in terms):
            return category
    return None


def detect_dangerous_actions(labels: list[str]) -> list[dict[str, str]]:
    """Detect destructive or externally visible actions in visible labels."""

    findings: list[dict[str, str]] = []
    for label in labels:
        category = classify_action(label)
        if category:
            findings.append(
                {
                    "label": label,
                    "category": category,
                    "reason": "destructive or externally visible action",
                }
            )
    return findings


def is_domain_allowed(url: str, allowlist: list[str]) -> bool:
    """Check whether a URL host is allowed by exact or wildcard host entries."""

    parsed = urlparse(url)
    host = (parsed.hostname or "").casefold().strip(".")
    if not parsed.scheme or not host:
        return False

    for entry in allowlist:
        allowed = entry.casefold().strip().strip(".")
        if not allowed:
            continue
        if allowed.startswith("*."):
            suffix = allowed[2:]
            if host.endswith(f".{suffix}") and host != suffix:
                return True
        elif host == allowed:
            return True
    return False


def redact_secrets(text: str) -> str:
    """Redact common credentials from logs, HTML, and evidence text."""

    redacted = text
    redacted = SECRET_PATTERNS[0].sub(r"\1[REDACTED]", redacted)
    redacted = SECRET_PATTERNS[1].sub(r"\1=[REDACTED]", redacted)
    redacted = SECRET_PATTERNS[2].sub("[REDACTED]", redacted)
    redacted = SECRET_PATTERNS[3].sub("[REDACTED]", redacted)
    return redacted
