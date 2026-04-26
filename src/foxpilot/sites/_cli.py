"""Shared CLI helpers for site command branches.

Every site CLI module needs the same JSON-or-text emitter and the same error
exit helper. This module owns the canonical implementations so site files do
not each carry their own copies.
"""

from __future__ import annotations

import json
from typing import Any, Callable, NoReturn

import typer


def emit(data: Any, json_output: bool, formatter: Callable[[Any], str]) -> None:
    """Print ``data`` either as pretty JSON or via a human formatter."""
    if json_output:
        typer.echo(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        typer.echo(formatter(data))


def exit_error(
    message: str,
    *,
    url: str = "",
    reason: str = "",
    next_step: str = "",
) -> NoReturn:
    """Print a structured error to stderr and raise ``typer.Exit(1)``.

    The optional ``url``, ``reason``, and ``next_step`` fields render on
    their own lines so agents and humans can both parse the failure and
    decide on a recovery action.
    """
    typer.echo(f"error: {message}", err=True)
    if url:
        typer.echo(f"url: {url}", err=True)
    if reason:
        typer.echo(f"reason: {reason}", err=True)
    if next_step:
        typer.echo(f"next: {next_step}", err=True)
    raise typer.Exit(1)


__all__ = ["emit", "exit_error"]
