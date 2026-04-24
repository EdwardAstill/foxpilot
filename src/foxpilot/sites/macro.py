"""Typer command branch for reusable browser macros."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

import typer

from foxpilot.sites.macro_service import (
    DEFAULT_MACRO_DIR,
    MacroError,
    delete_macro,
    export_macro,
    format_commands,
    format_macro,
    format_macro_list,
    list_macros,
    load_macro,
    render_macro_steps,
    run_macro,
)


app = typer.Typer(
    help="Reusable browser workflow macros.",
    no_args_is_help=True,
)

CommandPrefixFactory = Callable[[], list[str]]


def _default_command_prefix() -> list[str]:
    return []


_command_prefix_factory: CommandPrefixFactory = _default_command_prefix


def set_command_prefix_factory(factory: CommandPrefixFactory) -> None:
    """Set global Foxpilot flags inherited by macro-run steps."""
    global _command_prefix_factory
    _command_prefix_factory = factory


@app.command(name="help")
def cmd_help():
    """Show macro branch help and examples."""
    typer.echo(
        f"""foxpilot macro - reusable browser workflow macros

Macro files:
  {DEFAULT_MACRO_DIR}

Common commands:
  foxpilot macro list
  foxpilot macro show search-docs
  foxpilot macro run search-docs python
  foxpilot macro run search-docs python --dry-run
  foxpilot macro export search-docs python --format shell
  foxpilot macro export search-docs python --format python
  foxpilot macro export search-docs python --format mcp
  foxpilot macro export search-docs python --format markdown
  foxpilot macro delete search-docs --yes

JSON macro shape:
  {{
    "name": "search-docs",
    "description": "Open a search page.",
    "params": ["query"],
    "steps": [
      {{"command": "go", "args": ["https://example.test/search?q={{{{query}}}}"]}}
    ]
  }}

Template values:
  Use {{{{name}}}} placeholders for params declared in the macro.

Planned:
  record and edit are reserved commands. For now, create or edit JSON files directly.

Run:
  foxpilot macro <command> --help"""
    )


@app.command(name="list")
def cmd_list(
    macro_dir: Optional[Path] = typer.Option(
        None,
        "--dir",
        help="Macro directory. Defaults to ~/.local/share/foxpilot/macros.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
):
    """List available macros."""
    try:
        macros = list_macros(macro_dir)
    except MacroError as exc:
        _exit_error(str(exc))
    _emit(macros, json_output, format_macro_list)


@app.command(name="show")
def cmd_show(
    name: str = typer.Argument(..., help="Macro name."),
    macro_dir: Optional[Path] = typer.Option(
        None,
        "--dir",
        help="Macro directory. Defaults to ~/.local/share/foxpilot/macros.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
):
    """Show a macro definition."""
    try:
        macro = load_macro(name, macro_dir)
    except MacroError as exc:
        _exit_error(str(exc))
    _emit(macro, json_output, format_macro)


@app.command(name="run")
def cmd_run(
    name: str = typer.Argument(..., help="Macro name."),
    args: Optional[list[str]] = typer.Argument(
        None,
        help="Positional values for the macro params.",
    ),
    macro_dir: Optional[Path] = typer.Option(
        None,
        "--dir",
        help="Macro directory. Defaults to ~/.local/share/foxpilot/macros.",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print rendered steps without running."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
):
    """Run a macro by invoking Foxpilot commands in order."""
    values = list(args or [])
    try:
        if dry_run:
            macro = load_macro(name, macro_dir)
            commands = render_macro_steps(macro, values)
            data = {"name": macro["name"], "status": "dry-run", "commands": commands}
            _emit(data, json_output, lambda item: format_commands(item["commands"]))
            return

        result = run_macro(name, values, macro_dir, runner=_run_foxpilot_command)
    except MacroError as exc:
        _exit_error(str(exc))

    _emit(result, json_output, _format_run_result)
    if result.get("status") != "ok":
        raise typer.Exit(int(result.get("exit_code") or 1))


@app.command(name="delete")
def cmd_delete(
    name: str = typer.Argument(..., help="Macro name."),
    macro_dir: Optional[Path] = typer.Option(
        None,
        "--dir",
        help="Macro directory. Defaults to ~/.local/share/foxpilot/macros.",
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Delete without confirmation."),
):
    """Delete a macro file."""
    if not yes:
        typer.confirm(f"Delete macro {name!r}?", abort=True)
    try:
        delete_macro(name, macro_dir)
    except MacroError as exc:
        _exit_error(str(exc))
    typer.echo(f"deleted macro: {name}")


@app.command(name="export")
def cmd_export(
    name: str = typer.Argument(..., help="Macro name."),
    args: Optional[list[str]] = typer.Argument(
        None,
        help="Positional values for the macro params.",
    ),
    macro_dir: Optional[Path] = typer.Option(
        None,
        "--dir",
        help="Macro directory. Defaults to ~/.local/share/foxpilot/macros.",
    ),
    output_format: str = typer.Option(
        "shell",
        "--format",
        help="Export format: shell, python, mcp, or markdown.",
    ),
):
    """Export a rendered macro as shell, Python, MCP JSON, or Markdown."""
    try:
        typer.echo(
            export_macro(
                name,
                list(args or []),
                macro_dir,
                output_format=output_format,
                command_prefix=_command_prefix_factory(),
            ),
            nl=False,
        )
    except MacroError as exc:
        _exit_error(str(exc))


@app.command(name="record")
def cmd_record(
    name: str = typer.Argument(..., help="Macro name to record."),
):
    """Reserved for future interactive macro recording."""
    _planned("record", name)


@app.command(name="edit")
def cmd_edit(
    name: str = typer.Argument(..., help="Macro name to edit."),
):
    """Reserved for future macro editing."""
    _planned("edit", name)


def _emit(data, json_output: bool, formatter) -> None:
    if json_output:
        typer.echo(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        typer.echo(formatter(data))


def _format_run_result(result: dict) -> str:
    lines = [f"macro: {result['name']}", f"status: {result['status']}"]
    if result.get("steps") is not None:
        lines.append(f"steps: {result['steps']}")
    if result.get("step") is not None:
        lines.append(f"failed_step: {result['step']}")
    if result.get("exit_code") is not None:
        lines.append(f"exit_code: {result['exit_code']}")
    if result.get("commands"):
        lines.append("commands:")
        lines.extend(f"  {' '.join(argv)}" for argv in result["commands"])
    return "\n".join(lines)


def _run_foxpilot_command(argv) -> int:
    completed = subprocess.run(
        [sys.executable, "-m", "foxpilot.cli", *_command_prefix_factory(), *argv],
        check=False,
    )
    return completed.returncode


def _planned(command: str, name: str) -> None:
    typer.echo(
        (
            f"error: foxpilot macro {command} is planned, but not implemented yet.\n"
            f"macro: {name}\n"
            f"next: create or edit JSON files in {DEFAULT_MACRO_DIR}"
        ),
        err=True,
    )
    raise typer.Exit(1)


def _exit_error(message: str) -> None:
    typer.echo(f"error: {message}", err=True)
    raise typer.Exit(1)
