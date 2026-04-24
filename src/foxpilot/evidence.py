"""Evidence bundle creation for auditable browser work."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_REDACTION_PATTERNS = [
    re.compile(r"(?i)\b(password)\s*[:=]\s*([^\s&\"'<>]+)"),
    re.compile(r"(?i)\b(token)\s*[:=]\s*([^\s&\"'<>]+)"),
    re.compile(r"(?i)\b(api[_-]?key)\s*[:=]\s*([^\s&\"'<>]+)"),
    re.compile(r"(?i)\b(authorization)\s*:\s*(bearer\s+)([A-Za-z0-9._~+/=-]+)"),
]


def redact_text(value: Any) -> str:
    """Redact obvious secret shapes from browser-derived text."""
    text = "" if value is None else str(value)
    for pattern in _REDACTION_PATTERNS:
        if pattern.pattern.lower().find("authorization") != -1:
            text = pattern.sub(lambda match: f"{match.group(1)}: {match.group(2)}[REDACTED]", text)
        else:
            text = pattern.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)
    return text


def redaction_count(before: Any, after: Any) -> int:
    """Return an approximate count of redaction markers introduced."""
    return str(after).count("[REDACTED]") - str(before).count("[REDACTED]")


def create_evidence_bundle(
    driver,
    output_dir: str | Path,
    *,
    command: str = "",
    plugin: str = "",
    mode: str = "",
) -> dict[str, Any]:
    """Capture browser state into a redacted evidence bundle directory."""
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    artifacts: list[str] = []
    redactions = 0

    title = _safe_text(getattr(driver, "title", ""))
    url = redact_text(_safe_text(getattr(driver, "current_url", "")))

    redactions += _write_text(root, "url.txt", url)
    artifacts.append("url.txt")

    readable = _readable_text(driver)
    if readable is not None:
        redactions += _write_text(root, "readable.txt", readable)
        artifacts.append("readable.txt")

    page_html = getattr(driver, "page_source", None)
    if page_html is not None:
        redactions += _write_text(root, "page.html", page_html)
        artifacts.append("page.html")

    if _save_screenshot(driver, root / "screenshot.png"):
        artifacts.append("screenshot.png")

    bundle = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "title": redact_text(title),
        "url": url,
        "command": command,
        "plugin": plugin,
        "artifacts": artifacts.copy(),
        "redactions": {"count": redactions, "strategy": "common secret patterns"},
    }
    artifacts.insert(0, "bundle.json")
    bundle["artifacts"] = artifacts

    bundle_text = json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True)
    (root / "bundle.json").write_text(redact_text(bundle_text) + "\n", encoding="utf-8")
    return json.loads((root / "bundle.json").read_text(encoding="utf-8"))


def _write_text(root: Path, name: str, value: Any) -> int:
    before = _safe_text(value)
    after = redact_text(before)
    root.joinpath(name).write_text(after, encoding="utf-8")
    return redaction_count(before, after)


def _readable_text(driver) -> str | None:
    execute_script = getattr(driver, "execute_script", None)
    if not callable(execute_script):
        return None
    try:
        value = execute_script("return document.body ? document.body.innerText : '';")
    except Exception:
        return None
    return _safe_text(value)


def _save_screenshot(driver, path: Path) -> bool:
    save_screenshot = getattr(driver, "save_screenshot", None)
    if not callable(save_screenshot):
        return False
    try:
        return bool(save_screenshot(str(path))) and path.exists()
    except Exception:
        return False


def _safe_text(value: Any) -> str:
    return "" if value is None else str(value)
