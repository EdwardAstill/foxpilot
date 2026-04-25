"""Typer command branch for Excel Online (excel.cloud.microsoft) workflows."""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from typing import Callable, NoReturn, Optional

import typer

from foxpilot.core import browser
from foxpilot.sites.excel_service import (
    EXCEL_HOME,
    apply_alignment,
    apply_number_format,
    apply_toggle_format,
    clear_format,
    create_blank_workbook,
    define_name,
    extract_active_cell,
    extract_sheet_tabs,
    extract_workbook_title,
    fill_direction,
    format_cell,
    format_open_result,
    format_sheets,
    goto_cell,
    is_excel_url,
    list_defined_names,
    normalize_alignment,
    normalize_cell_ref,
    normalize_defined_name,
    normalize_number_format,
    select_range,
    write_cell,
)


app = typer.Typer(
    help="Excel Online navigation and cell read/write helpers.",
    no_args_is_help=True,
)

BrowserFactory = Callable[[], object]


def _default_browser():
    return browser()


_browser_factory: BrowserFactory = _default_browser


def set_browser_factory(factory: BrowserFactory) -> None:
    global _browser_factory
    _browser_factory = factory


@contextmanager
def _site_browser():
    with _browser_factory() as driver:
        yield driver


@app.command(name="help")
def cmd_help() -> None:
    """Show Excel branch help and examples."""
    typer.echo(
        """foxpilot excel - Excel Online (excel.cloud.microsoft) helpers

Common commands:
  foxpilot excel open                       # open Excel home
  foxpilot excel open <workbook-url>        # open a specific workbook
  foxpilot excel new                        # create a blank workbook
  foxpilot excel sheets                     # list sheet tabs
  foxpilot excel goto B7                    # jump to a cell via Name Box
  foxpilot excel select A1:C10              # select a range
  foxpilot excel read B7                    # read formula-bar value at a cell
  foxpilot excel write B7 "hello"           # type into a cell + Enter
  foxpilot excel write D2 "=SUM(A2:C2)"     # write a formula
  foxpilot excel fill-down A1:A20           # Ctrl+D fill from top of range
  foxpilot excel fill-right A1:E1           # Ctrl+R fill from left of range
  foxpilot excel name B2:B20 Revenue        # define a named range
  foxpilot excel names                      # list defined names
  foxpilot excel active                     # report current active cell

Formatting:
  foxpilot excel bold A1:A5                 # toggle bold (Ctrl+B)
  foxpilot excel italic A1                  # toggle italic (Ctrl+I)
  foxpilot excel underline A1               # toggle underline (Ctrl+U)
  foxpilot excel number-format B2:B20 currency
  foxpilot excel number-format B2:B20 percent
  foxpilot excel align A1:C5 center         # ribbon-based, best effort
  foxpilot excel clear-format A1:Z100       # ribbon-based, best effort

Notes:
  Excel Online renders cells on a canvas, so reads/writes go through the
  Name Box and Formula Bar instead of DOM cell scraping.

Auth:
  Sign into excel.cloud.microsoft once in the foxpilot browser. Cookie
  state persists across runs in the claude profile.

Modes:
  default claude (recommended), --visible, --zen, --headless-mode

Run:
  foxpilot excel <command> --help"""
    )


@app.command(name="open")
def cmd_open(
    target: Optional[str] = typer.Argument(
        None,
        help="Workbook URL. Omit to open Excel home.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open Excel home or a specific workbook URL."""
    url = target if target else EXCEL_HOME
    if target and not is_excel_url(target) and "://" not in target:
        _exit_error(
            "target does not look like an Excel Online URL",
            reason="expected https://excel.cloud.microsoft/... or office.com/...",
        )
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.0)
        data = {
            "title": driver.title,
            "url": driver.current_url,
            "workbook": extract_workbook_title(driver),
        }
        _emit(data, json_output, format_open_result)


@app.command(name="sheets")
def cmd_sheets(
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """List sheet tabs in the currently open workbook."""
    with _site_browser() as driver:
        sheets = extract_sheet_tabs(driver)
        _emit(sheets, json_output, format_sheets)


@app.command(name="active")
def cmd_active(
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Report the active cell reference and formula-bar value."""
    with _site_browser() as driver:
        data = extract_active_cell(driver)
        _emit(data, json_output, format_cell)


@app.command(name="goto")
def cmd_goto(
    cell: str = typer.Argument(..., help="Cell reference, e.g. A1 or B7."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Jump to a cell using the Name Box."""
    try:
        ref = normalize_cell_ref(cell)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        try:
            goto_cell(driver, ref)
        except RuntimeError as exc:
            _exit_error(
                str(exc),
                next_step="ensure a workbook is open and the Name Box is visible",
            )
        time.sleep(0.4)
        data = extract_active_cell(driver)
        _emit(data, json_output, format_cell)


@app.command(name="read")
def cmd_read(
    cell: str = typer.Argument(..., help="Cell to read, e.g. A1."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Read the formula-bar value at the given cell."""
    try:
        ref = normalize_cell_ref(cell)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        try:
            goto_cell(driver, ref)
        except RuntimeError as exc:
            _exit_error(str(exc))
        time.sleep(0.4)
        data = extract_active_cell(driver)
        _emit(data, json_output, format_cell)


@app.command(name="new")
def cmd_new(
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Create a blank workbook from Excel home."""
    with _site_browser() as driver:
        try:
            data = create_blank_workbook(driver)
        except RuntimeError as exc:
            _exit_error(str(exc), next_step="open Excel home manually and verify the tile label")
        time.sleep(2.0)
        data["workbook"] = extract_workbook_title(driver)
        _emit(data, json_output, format_open_result)


@app.command(name="select")
def cmd_select(
    cells: str = typer.Argument(..., help="Cell or range, e.g. A1 or A1:C10."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Select a cell or range via the Name Box."""
    try:
        ref = normalize_cell_ref(cells)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        try:
            select_range(driver, ref)
        except RuntimeError as exc:
            _exit_error(str(exc))
        time.sleep(0.3)
        data = extract_active_cell(driver)
        _emit(data, json_output, format_cell)


@app.command(name="fill-down")
def cmd_fill_down(
    range_ref: str = typer.Argument(..., help="Range, e.g. A1:A20."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Select a range and apply Ctrl+D to fill the top cell down."""
    try:
        ref = normalize_cell_ref(range_ref)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        try:
            data = fill_direction(driver, ref, "down")
        except (RuntimeError, ValueError) as exc:
            _exit_error(str(exc))
        _emit(data, json_output, lambda d: f"filled {d['range']} {d['direction']}")


@app.command(name="fill-right")
def cmd_fill_right(
    range_ref: str = typer.Argument(..., help="Range, e.g. A1:E1."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Select a range and apply Ctrl+R to fill the leftmost cell right."""
    try:
        ref = normalize_cell_ref(range_ref)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        try:
            data = fill_direction(driver, ref, "right")
        except (RuntimeError, ValueError) as exc:
            _exit_error(str(exc))
        _emit(data, json_output, lambda d: f"filled {d['range']} {d['direction']}")


@app.command(name="name")
def cmd_name(
    range_ref: str = typer.Argument(..., help="Range to name, e.g. B2:B20."),
    name: str = typer.Argument(..., help="Defined name, e.g. Revenue."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Define a name for a cell or range via the Name Box."""
    try:
        ref = normalize_cell_ref(range_ref)
        defined = normalize_defined_name(name)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        try:
            data = define_name(driver, ref, defined)
        except RuntimeError as exc:
            _exit_error(str(exc))
        _emit(data, json_output, lambda d: f"named {d['range']} -> {d['name']}")


@app.command(name="names")
def cmd_names(
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """List defined names from the Name Box dropdown (best effort)."""
    with _site_browser() as driver:
        names = list_defined_names(driver)
        _emit(
            names,
            json_output,
            lambda items: "\n".join(n["name"] for n in items) if items else "(no defined names found)",
        )


@app.command(name="bold")
def cmd_bold(
    range_ref: str = typer.Argument(..., help="Cell or range, e.g. A1 or A1:C5."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Toggle bold on a range (Ctrl+B)."""
    try:
        ref = normalize_cell_ref(range_ref)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        try:
            data = apply_toggle_format(driver, ref, "b")
        except RuntimeError as exc:
            _exit_error(str(exc))
        _emit(data, json_output, lambda d: f"toggled bold on {d['range']}")


@app.command(name="italic")
def cmd_italic(
    range_ref: str = typer.Argument(..., help="Cell or range."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Toggle italic on a range (Ctrl+I)."""
    try:
        ref = normalize_cell_ref(range_ref)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        try:
            data = apply_toggle_format(driver, ref, "i")
        except RuntimeError as exc:
            _exit_error(str(exc))
        _emit(data, json_output, lambda d: f"toggled italic on {d['range']}")


@app.command(name="underline")
def cmd_underline(
    range_ref: str = typer.Argument(..., help="Cell or range."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Toggle underline on a range (Ctrl+U)."""
    try:
        ref = normalize_cell_ref(range_ref)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        try:
            data = apply_toggle_format(driver, ref, "u")
        except RuntimeError as exc:
            _exit_error(str(exc))
        _emit(data, json_output, lambda d: f"toggled underline on {d['range']}")


@app.command(name="number-format")
def cmd_number_format(
    range_ref: str = typer.Argument(..., help="Cell or range."),
    kind: str = typer.Argument(
        ...,
        help="Format kind: number, currency, percent, date, time, general.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Apply a number format via Ctrl+Shift shortcut."""
    try:
        ref = normalize_cell_ref(range_ref)
        cleaned = normalize_number_format(kind)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        try:
            data = apply_number_format(driver, ref, cleaned)
        except (RuntimeError, ValueError) as exc:
            _exit_error(str(exc))
        _emit(data, json_output, lambda d: f"applied {d['format']} format to {d['range']}")


@app.command(name="align")
def cmd_align(
    range_ref: str = typer.Argument(..., help="Cell or range."),
    alignment: str = typer.Argument(..., help="Alignment: left, center, right."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Set horizontal alignment via the ribbon (best effort)."""
    try:
        ref = normalize_cell_ref(range_ref)
        cleaned = normalize_alignment(alignment)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        try:
            data = apply_alignment(driver, ref, cleaned)
        except (RuntimeError, ValueError) as exc:
            _exit_error(
                str(exc),
                next_step="run `foxpilot --visible excel align ...` to inspect the Home ribbon",
            )
        _emit(data, json_output, lambda d: f"aligned {d['range']} {d['alignment']}")


@app.command(name="clear-format")
def cmd_clear_format(
    range_ref: str = typer.Argument(..., help="Cell or range."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Clear formatting on a range via the ribbon (best effort)."""
    try:
        ref = normalize_cell_ref(range_ref)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        try:
            data = clear_format(driver, ref)
        except RuntimeError as exc:
            _exit_error(
                str(exc),
                next_step="open Home > Clear menu manually then re-run; the menu may need to be expanded first",
            )
        _emit(data, json_output, lambda d: f"cleared formatting on {d['range']}")


@app.command(name="write")
def cmd_write(
    cell: str = typer.Argument(..., help="Cell to write to, e.g. A1."),
    value: str = typer.Argument(..., help="Value (or formula like '=SUM(A1:A5)')."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Write a value or formula to a cell, finishing with Enter."""
    try:
        ref = normalize_cell_ref(cell)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        try:
            data = write_cell(driver, ref, value)
        except RuntimeError as exc:
            _exit_error(str(exc))
        _emit(data, json_output, format_cell)


def _emit(data, json_output: bool, formatter) -> None:
    if json_output:
        typer.echo(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        typer.echo(formatter(data))


def _exit_error(
    message: str,
    *,
    url: str = "",
    reason: str = "",
    next_step: str = "",
) -> NoReturn:
    typer.echo(f"error: {message}", err=True)
    if url:
        typer.echo(f"url: {url}", err=True)
    if reason:
        typer.echo(f"reason: {reason}", err=True)
    if next_step:
        typer.echo(f"next: {next_step}", err=True)
    raise typer.Exit(1)
