"""Environment diagnostics for Foxpilot."""

from __future__ import annotations

import os
import platform
import shutil
import socket
import sys
from pathlib import Path

from foxpilot.core import CLAUDE_PROFILE_DIR


def _check_binary(name: str) -> dict[str, object]:
    path = shutil.which(name)
    if path:
        return {"ok": True, "message": path}
    return {"ok": False, "message": f"{name} not found on PATH"}


def _check_socket_bind() -> dict[str, object]:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            host, port = sock.getsockname()
        return {"ok": True, "message": f"bound {host}:{port}"}
    except OSError as exc:
        return {"ok": False, "message": str(exc)}


def _nearest_existing_parent(path: Path) -> Path:
    current = path
    while not current.exists() and current.parent != current:
        current = current.parent
    return current


def _check_profile_parent() -> dict[str, object]:
    parent = CLAUDE_PROFILE_DIR.parent
    existing = _nearest_existing_parent(parent)
    writable = os.access(existing, os.W_OK)
    if writable:
        return {"ok": True, "message": f"{existing} writable"}
    return {"ok": False, "message": f"{existing} not writable"}


def run_diagnostics() -> dict[str, dict[str, object]]:
    return {
        "python": {
            "ok": sys.version_info >= (3, 11),
            "message": f"{platform.python_version()} at {sys.executable}",
        },
        "geckodriver": _check_binary("geckodriver"),
        "firefox": _check_binary("firefox"),
        "zen_browser": _check_binary("zen-browser"),
        "socket_bind": _check_socket_bind(),
        "hyprctl": _check_binary("hyprctl"),
        "claude_profile_parent": _check_profile_parent(),
    }


def run_safe_fixes(*, profile_dir: Path = CLAUDE_PROFILE_DIR) -> dict[str, dict[str, object]]:
    """Apply safe, reversible repairs and return a report."""
    report: dict[str, dict[str, object]] = {}
    try:
        profile_dir.parent.mkdir(parents=True, exist_ok=True)
        report["claude_profile_parent"] = {
            "ok": True,
            "message": f"created or verified {profile_dir.parent}",
        }
    except OSError as exc:
        report["claude_profile_parent"] = {"ok": False, "message": str(exc)}
    return report


def format_diagnostics(report: dict[str, dict[str, object]]) -> str:
    lines = []
    for key, result in report.items():
        status = "OK" if result.get("ok") else "x"
        lines.append(f"{status} {key:<22} {result.get('message', '')}")
    return "\n".join(lines)
