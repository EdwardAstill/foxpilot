"""Macro storage, rendering, and execution helpers."""

from __future__ import annotations

import json
import re
import shlex
from pathlib import Path
from typing import Any, Callable, Sequence


DEFAULT_MACRO_DIR = Path.home() / ".local" / "share" / "foxpilot" / "macros"

MacroRunner = Callable[[Sequence[str]], int]

_SAFE_MACRO_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_SAFE_PARAM_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_PLACEHOLDER = re.compile(r"{{\s*([A-Za-z_][A-Za-z0-9_]*)\s*}}")


class MacroError(ValueError):
    """Raised when a macro file or invocation is invalid."""


def macro_path(name: str, macro_dir: Path | str | None = None) -> Path:
    """Return the JSON path for a macro name."""
    root = Path(macro_dir) if macro_dir is not None else DEFAULT_MACRO_DIR
    return root / f"{validate_macro_name(name)}.json"


def validate_macro_name(name: str) -> str:
    """Validate a macro file stem and return the stripped value."""
    value = name.strip()
    if not _SAFE_MACRO_NAME.fullmatch(value):
        raise MacroError(
            "invalid macro name: use letters, numbers, dots, dashes, and underscores"
        )
    return value


def list_macros(macro_dir: Path | str | None = None) -> list[dict[str, Any]]:
    """List macro summaries from a directory."""
    root = Path(macro_dir) if macro_dir is not None else DEFAULT_MACRO_DIR
    if not root.exists():
        return []

    summaries: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        macro = _load_macro_path(path)
        summaries.append(
            {
                "name": macro["name"],
                "description": macro["description"],
                "params": macro["params"],
                "steps": len(macro["steps"]),
                "path": str(path),
            }
        )
    return sorted(summaries, key=lambda item: item["name"])


def load_macro(name: str, macro_dir: Path | str | None = None) -> dict[str, Any]:
    """Load and validate one macro by name."""
    path = macro_path(name, macro_dir)
    if not path.exists():
        raise MacroError(f"macro not found: {validate_macro_name(name)}")
    return _load_macro_path(path)


def delete_macro(name: str, macro_dir: Path | str | None = None) -> bool:
    """Delete one macro file."""
    path = macro_path(name, macro_dir)
    if not path.exists():
        raise MacroError(f"macro not found: {validate_macro_name(name)}")
    path.unlink()
    return True


def render_macro_steps(macro: dict[str, Any], values: Sequence[str]) -> list[list[str]]:
    """Render a macro's steps with positional values for declared params."""
    params = macro["params"]
    if len(values) != len(params):
        raise MacroError(f"expected {len(params)} arg(s), got {len(values)}")

    context = {name: str(value) for name, value in zip(params, values)}
    rendered: list[list[str]] = []
    for index, step in enumerate(macro["steps"], start=1):
        try:
            rendered_step = _substitute(step, context)
            rendered.append(_step_to_argv(rendered_step))
        except MacroError as exc:
            raise MacroError(f"step {index}: {exc}") from exc
    return rendered


def run_macro(
    name: str,
    values: Sequence[str],
    macro_dir: Path | str | None = None,
    *,
    runner: MacroRunner,
) -> dict[str, Any]:
    """Run a macro by calling runner once per rendered command argv."""
    macro = load_macro(name, macro_dir)
    commands = render_macro_steps(macro, values)

    for index, argv in enumerate(commands, start=1):
        exit_code = runner(argv)
        if exit_code != 0:
            return {
                "name": macro["name"],
                "status": "failed",
                "step": index,
                "exit_code": exit_code,
                "commands": commands,
            }

    return {
        "name": macro["name"],
        "status": "ok",
        "steps": len(commands),
        "commands": commands,
    }


def export_macro(
    name: str,
    values: Sequence[str],
    macro_dir: Path | str | None = None,
    *,
    output_format: str = "shell",
    command_prefix: Sequence[str] = (),
) -> str:
    """Export a rendered macro as shell, Python, MCP JSON, or Markdown."""
    macro = load_macro(name, macro_dir)
    commands = render_macro_steps(macro, values)
    prefixed = [[*command_prefix, *command] for command in commands]
    output_format = output_format.lower()
    if output_format == "shell":
        return _export_shell(prefixed)
    if output_format == "python":
        return _export_python(prefixed)
    if output_format == "mcp":
        return _export_mcp(macro["name"], prefixed)
    if output_format == "markdown":
        return _export_markdown(macro, prefixed)
    raise MacroError("export format must be shell, python, mcp, or markdown")


def format_macro_list(macros: Sequence[dict[str, Any]]) -> str:
    """Format macro summaries for humans."""
    if not macros:
        return "No macros found."

    lines: list[str] = []
    for item in macros:
        summary = item["name"]
        if item.get("description"):
            summary += f" - {item['description']}"
        lines.append(summary)
        params = ", ".join(item.get("params", [])) or "(none)"
        lines.append(f"  params: {params}")
        lines.append(f"  steps: {item.get('steps', 0)}")
    return "\n".join(lines)


def format_macro(macro: dict[str, Any]) -> str:
    """Format one macro definition for humans."""
    params = ", ".join(macro["params"]) or "(none)"
    lines = [
        f"name: {macro['name']}",
        f"description: {macro['description'] or '(none)'}",
        f"params: {params}",
        f"path: {macro['path']}",
        "steps:",
    ]

    if not macro["steps"]:
        lines.append("  (none)")
        return "\n".join(lines)

    for index, step in enumerate(macro["steps"], start=1):
        argv = _step_to_argv(step)
        lines.append(f"  {index}. {' '.join(argv)}")
    return "\n".join(lines)


def format_commands(commands: Sequence[Sequence[str]]) -> str:
    """Format rendered command argv lines."""
    if not commands:
        return "(no steps)"
    return "\n".join(" ".join(argv) for argv in commands)


def _export_shell(commands: Sequence[Sequence[str]]) -> str:
    lines = ["#!/usr/bin/env bash", "set -euo pipefail", ""]
    lines.extend(f"foxpilot {shlex.join(list(command))}" for command in commands)
    return "\n".join(lines) + "\n"


def _export_python(commands: Sequence[Sequence[str]]) -> str:
    return (
        "import subprocess\n"
        "import sys\n\n"
        f"commands = {json.dumps([list(command) for command in commands], indent=2)}\n\n"
        "for command in commands:\n"
        "    subprocess.run([sys.executable, '-m', 'foxpilot.cli', *command], check=True)\n"
    )


def _export_mcp(name: str, commands: Sequence[Sequence[str]]) -> str:
    payload = {
        "name": name,
        "steps": [
            {
                "tool": command[0],
                "args": list(command[1:]),
            }
            for command in commands
        ],
    }
    return json.dumps(payload, indent=2) + "\n"


def _export_markdown(macro: dict[str, Any], commands: Sequence[Sequence[str]]) -> str:
    lines = [
        f"# Macro: {macro['name']}",
        "",
        macro.get("description") or "No description.",
        "",
        "## Steps",
        "",
    ]
    if not commands:
        lines.append("No steps.")
    for index, command in enumerate(commands, 1):
        lines.append(f"{index}. `foxpilot {' '.join(command)}`")
    return "\n".join(lines) + "\n"


def _load_macro_path(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MacroError(f"invalid JSON in {path}: {exc.msg}") from exc

    if not isinstance(raw, dict):
        raise MacroError(f"invalid macro in {path}: expected a JSON object")

    name = validate_macro_name(str(raw.get("name") or path.stem))
    description = raw.get("description", "")
    if not isinstance(description, str):
        raise MacroError(f"invalid macro in {path}: description must be a string")

    params = raw.get("params", [])
    if not isinstance(params, list) or not all(isinstance(item, str) for item in params):
        raise MacroError(f"invalid macro in {path}: params must be a list of strings")
    for param in params:
        if not _SAFE_PARAM_NAME.fullmatch(param):
            raise MacroError(f"invalid macro in {path}: invalid param name {param!r}")

    steps = raw.get("steps", [])
    if not isinstance(steps, list):
        raise MacroError(f"invalid macro in {path}: steps must be a list")

    return {
        "name": name,
        "description": description,
        "params": params,
        "steps": steps,
        "path": str(path),
    }


def _substitute(value: Any, context: dict[str, str]) -> Any:
    if isinstance(value, str):
        return _PLACEHOLDER.sub(lambda match: _replacement(match, context), value)
    if isinstance(value, list):
        return [_substitute(item, context) for item in value]
    if isinstance(value, dict):
        return {key: _substitute(item, context) for key, item in value.items()}
    return value


def _replacement(match: re.Match[str], context: dict[str, str]) -> str:
    name = match.group(1)
    if name not in context:
        raise MacroError(f"unknown placeholder: {name}")
    return context[name]


def _step_to_argv(step: Any) -> list[str]:
    if isinstance(step, str):
        argv = [step]
    elif isinstance(step, list):
        argv = [_stringify_part(part) for part in step]
    elif isinstance(step, dict):
        argv = _dict_step_to_argv(step)
    else:
        raise MacroError("step must be a string, list, or object")

    if not argv or not argv[0]:
        raise MacroError("step command cannot be empty")
    return argv


def _dict_step_to_argv(step: dict[str, Any]) -> list[str]:
    if "argv" in step:
        argv = step["argv"]
        if not isinstance(argv, list):
            raise MacroError("argv must be a list")
        return [_stringify_part(part) for part in argv]

    if "command" in step:
        command = _stringify_part(step["command"])
        args = step.get("args", [])
        if isinstance(args, str):
            arg_parts = [args]
        elif isinstance(args, list):
            arg_parts = [_stringify_part(part) for part in args]
        else:
            raise MacroError("args must be a string or list")
        argv = [command, *arg_parts]
        _append_options(argv, step.get("options", {}))
        return argv

    if len(step) == 1:
        command, payload = next(iter(step.items()))
        argv = [_stringify_part(command)]
        if payload is None:
            return argv
        if isinstance(payload, list):
            argv.extend(_stringify_part(part) for part in payload)
        elif isinstance(payload, dict):
            _append_options(argv, payload)
        else:
            argv.append(_stringify_part(payload))
        return argv

    raise MacroError("object step needs command, argv, or one shorthand command")


def _append_options(argv: list[str], options: Any) -> None:
    if options in (None, {}):
        return
    if not isinstance(options, dict):
        raise MacroError("options must be an object")

    for key, value in options.items():
        flag = str(key) if str(key).startswith("-") else f"--{str(key).replace('_', '-')}"
        if value is True:
            argv.append(flag)
        elif value in (False, None):
            continue
        elif isinstance(value, list):
            for item in value:
                argv.extend([flag, _stringify_part(item)])
        else:
            argv.extend([flag, _stringify_part(value)])


def _stringify_part(value: Any) -> str:
    if isinstance(value, (dict, list)):
        raise MacroError("command parts must be scalar values")
    return str(value)
