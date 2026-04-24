"""Visual QA report helpers with fake-driver friendly browser hooks."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


DESKTOP_SIZE = (1440, 900)
MOBILE_SIZE = (390, 844)


def detect_blank_page(text_or_html: str | None) -> bool:
    """Return true when page text/html has no meaningful body content."""

    if not text_or_html:
        return True
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", text_or_html, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", "", text)
    return not text.strip()


def detect_missing_images(data: list[dict[str, Any]]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for image in data:
        src = str(image.get("src") or "")
        if not src:
            continue
        findings.append(
            {
                "type": "missing-image",
                "severity": "warning",
                "message": f"Image failed to load: {src}",
                "src": src,
                "alt": str(image.get("alt") or ""),
            }
        )
    return findings


def _call_if_exists(obj: object, name: str, *args):
    method = getattr(obj, name, None)
    if callable(method):
        return method(*args)
    return None


def _execute(driver, script: str):
    method = getattr(driver, "execute_script", None)
    if callable(method):
        return method(script)
    return None


def _capture_screenshot(driver, path: Path) -> str | None:
    if callable(getattr(driver, "save_screenshot", None)):
        driver.save_screenshot(str(path))
        return str(path)
    if callable(getattr(driver, "get_screenshot_as_file", None)):
        driver.get_screenshot_as_file(str(path))
        return str(path)
    return None


def _console_logs(driver) -> list[dict[str, Any]]:
    try:
        logs = _call_if_exists(driver, "get_log", "browser")
    except Exception:
        return []
    return list(logs or [])


def build_qa_report(driver, url: str, output_dir: str | Path) -> dict[str, Any]:
    """Capture a minimal visual QA report using whatever driver hooks exist."""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    _call_if_exists(driver, "get", url)

    artifacts: dict[str, str] = {}
    for name, size in (("desktop", DESKTOP_SIZE), ("mobile", MOBILE_SIZE)):
        _call_if_exists(driver, "set_window_size", *size)
        screenshot = _capture_screenshot(driver, output_path / f"{name}.png")
        if screenshot:
            artifacts[name] = screenshot

    _call_if_exists(driver, "set_window_size", *DESKTOP_SIZE)
    fullpage = _capture_screenshot(driver, output_path / "fullpage.png")
    if fullpage:
        artifacts["fullpage"] = fullpage

    html = _execute(driver, "return document.documentElement.outerHTML") or ""
    visible_text = _execute(driver, "return document.body.innerText") or ""
    missing_images = _execute(
        driver,
        """
        return Array.from(document.images || [])
          .filter((img) => img.complete && img.naturalWidth === 0)
          .map((img) => ({src: img.currentSrc || img.src, alt: img.alt || ""}));
        """,
    )
    findings = detect_missing_images(list(missing_images or []))
    if detect_blank_page(visible_text or html):
        findings.append(
            {
                "type": "blank-page",
                "severity": "error",
                "message": "Page appears to have no visible text",
            }
        )

    console = _console_logs(driver)
    for entry in console:
        if str(entry.get("level", "")).upper() in {"SEVERE", "ERROR"}:
            findings.append(
                {
                    "type": "console-error",
                    "severity": "error",
                    "message": str(entry.get("message", "")),
                }
            )

    report = {
        "url": getattr(driver, "current_url", url),
        "title": getattr(driver, "title", ""),
        "artifacts": artifacts,
        "console": console,
        "findings": findings,
    }

    (output_path / "qa-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    (output_path / "summary.md").write_text(summarize_qa(report))
    return report


def summarize_qa(report: dict[str, Any]) -> str:
    findings = list(report.get("findings") or [])
    artifacts = dict(report.get("artifacts") or {})
    lines = [
        "# QA Report",
        "",
        f"URL: {report.get('url', '')}",
        f"Title: {report.get('title', '')}",
        f"Findings: {len(findings)}",
        "",
        "## Artifacts",
    ]
    if artifacts:
        lines.extend(f"- {name}: {path}" for name, path in artifacts.items())
    else:
        lines.append("- none")
    if findings:
        lines.extend(["", "## Findings"])
        lines.extend(
            f"- {finding.get('severity', 'info')}: {finding.get('message', '')}"
            for finding in findings
        )
    return "\n".join(lines) + "\n"
