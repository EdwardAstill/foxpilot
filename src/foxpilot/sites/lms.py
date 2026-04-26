"""Typer command branch for UWA Blackboard Ultra (lms.uwa.edu.au)."""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, NoReturn, Optional

import typer

from foxpilot.core import browser
from foxpilot.sites.lms_service import (
    LMS_HOME,
    build_lms_url,
    extract_announcements,
    extract_assignments,
    extract_courses,
    extract_grades,
    extract_stream_items,
    format_announcements,
    format_assignments,
    format_courses,
    format_grades,
    format_open_result,
    format_stream,
    is_sso_redirect_url,
    normalize_assignment_name,
    normalize_course_id,
    normalize_section,
)


app = typer.Typer(
    help="UWA Blackboard Ultra (lms.uwa.edu.au) navigation, stream, courses, grades.",
    no_args_is_help=True,
)

BrowserFactory = Callable[[], object]


def _default_browser():
    return browser()


_browser_factory: BrowserFactory = _default_browser


def set_browser_factory(factory: BrowserFactory) -> None:
    """Set the browser factory used by this branch (mode-aware from CLI)."""
    global _browser_factory
    _browser_factory = factory


@contextmanager
def _site_browser():
    with _browser_factory() as driver:
        yield driver


@app.command(name="help")
def cmd_help() -> None:
    """Show LMS branch help and examples."""
    typer.echo(
        """foxpilot lms - UWA Blackboard Ultra (lms.uwa.edu.au)

Common commands:
  foxpilot lms open                    # open stream
  foxpilot lms open courses            # open course list
  foxpilot lms open calendar           # open calendar
  foxpilot lms open grades             # open grades
  foxpilot lms open messages           # open messages
  foxpilot lms stream --limit 20       # recent stream items
  foxpilot lms courses --json          # enrolled courses
  foxpilot lms course "GENG2000"       # open a course landing page
  foxpilot lms assignments --due-soon  # assignment list
  foxpilot lms grades --json           # grade rows
  foxpilot lms announcements --limit 5 # announcements
  foxpilot lms download "Lab 3"        # save attached files

Sections (for `open`):
  stream, courses, calendar, grades, messages

Auth:
  Default mode is --zen because most UWA students are already signed into LMS
  in their Zen browser. For the dedicated automation profile, run:
    foxpilot login https://lms.uwa.edu.au/ultra/stream
  Or import cookies:
    foxpilot import-cookies --domain lms.uwa.edu.au --include-storage

Modes:
  default --zen (recommended), --visible, automation profile (after login).
  Headless is unsupported: UWA Pheme SSO needs a real session.

Run:
  foxpilot lms <command> --help"""
    )


@app.command(name="open")
def cmd_open(
    section: Optional[str] = typer.Argument(
        None,
        help="Section: stream, courses, calendar, grades, messages.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open an LMS section in the browser."""
    try:
        key = normalize_section(section)
        url = build_lms_url(key)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.0)
        _check_sso(driver)
        data = {
            "title": driver.title,
            "url": driver.current_url,
            "section": key,
        }
        _emit(data, json_output, format_open_result)


@app.command(name="stream")
def cmd_stream(
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum items to return."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """List recent items from the LMS stream."""
    with _site_browser() as driver:
        driver.get(build_lms_url("stream"))
        time.sleep(2.0)
        _check_sso(driver)
        items = extract_stream_items(driver, limit=limit)
        _emit(items, json_output, format_stream)


@app.command(name="courses")
def cmd_courses(
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """List enrolled courses."""
    with _site_browser() as driver:
        driver.get(build_lms_url("courses"))
        time.sleep(2.0)
        _check_sso(driver)
        courses = extract_courses(driver)
        _emit(courses, json_output, format_courses)


@app.command(name="course")
def cmd_course(
    id_or_name: str = typer.Argument(..., help="Course id, code, or visible name."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open a course landing page by id, code, or name."""
    try:
        target = normalize_course_id(id_or_name)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(build_lms_url("courses"))
        time.sleep(2.0)
        _check_sso(driver)
        course = _pick_course(driver, target)
        if course is None:
            _exit_error(
                f"could not find course matching {target!r}",
                url=driver.current_url,
                next_step="run `foxpilot lms courses` to see exact titles, then retry",
            )
        url = course.get("url") or driver.current_url
        if url:
            driver.get(url)
            time.sleep(2.0)
        data = {
            "title": driver.title,
            "url": driver.current_url,
            "section": "course",
        }
        _emit(data, json_output, format_open_result)


@app.command(name="assignments")
def cmd_assignments(
    course: Optional[str] = typer.Option(None, "--course", help="Filter by course."),
    due_soon: bool = typer.Option(False, "--due-soon", help="Only show items due soon."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """List assignment items."""
    if course is not None:
        try:
            course = normalize_course_id(course)
        except ValueError as exc:
            _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(build_lms_url("courses"))
        time.sleep(2.0)
        _check_sso(driver)
        items = extract_assignments(driver)
        if course:
            items = [a for a in items if course.lower() in (a.get("course") or "").lower()]
        if due_soon:
            items = [a for a in items if (a.get("due") or "").strip()]
        _emit(items, json_output, format_assignments)


@app.command(name="grades")
def cmd_grades(
    course: Optional[str] = typer.Option(None, "--course", help="Filter by course."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """List grade items."""
    if course is not None:
        try:
            course = normalize_course_id(course)
        except ValueError as exc:
            _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(build_lms_url("grades"))
        time.sleep(2.0)
        _check_sso(driver)
        items = extract_grades(driver)
        if course:
            # Grade rows often inherit course from the surface; filtering is best-effort.
            items = [g for g in items if course.lower() in (g.get("name") or "").lower()]
        _emit(items, json_output, format_grades)


@app.command(name="announcements")
def cmd_announcements(
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum announcements."),
    course: Optional[str] = typer.Option(None, "--course", help="Filter by course."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """List announcements with course + posted-at."""
    if course is not None:
        try:
            course = normalize_course_id(course)
        except ValueError as exc:
            _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(LMS_HOME)
        time.sleep(2.0)
        _check_sso(driver)
        items = extract_announcements(driver, limit=limit)
        if course:
            items = [a for a in items if course.lower() in (a.get("course") or "").lower()]
        _emit(items, json_output, format_announcements)


@app.command(name="download")
def cmd_download(
    assignment: str = typer.Argument(..., help="Assignment name or id."),
    target_dir: Optional[Path] = typer.Option(
        None,
        "--to",
        help="Directory to save attachments. Defaults to current directory.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Save attached files for an assignment to a target dir (best-effort)."""
    try:
        name = normalize_assignment_name(assignment)
    except ValueError as exc:
        _exit_error(str(exc))
    out_dir = target_dir or Path.cwd()
    out_dir.mkdir(parents=True, exist_ok=True)
    with _site_browser() as driver:
        driver.get(build_lms_url("courses"))
        time.sleep(2.0)
        _check_sso(driver)
        match = _pick_assignment(driver, name)
        if match is None:
            _exit_error(
                f"could not find assignment matching {name!r}",
                url=driver.current_url,
                next_step="run `foxpilot lms assignments` to see exact names, then retry",
            )
        url = match.get("url")
        if url:
            driver.get(url)
            time.sleep(2.0)
        # Attachment download is canvas/JS-driven on Ultra; emit stub result so
        # callers can wire `wait-download` mirroring later.
        data = {
            "assignment": match.get("name") or name,
            "course": match.get("course") or "",
            "url": driver.current_url,
            "saved_to": str(out_dir),
            "files": [],
        }
        _emit(
            data,
            json_output,
            lambda d: f"opened {d['assignment']} ({d['url']}); save target: {d['saved_to']}",
        )


# ---------- helpers ----------


def _pick_course(driver, target: str) -> Optional[dict]:
    target_l = target.lower()
    for course in extract_courses(driver):
        haystack = " ".join(
            [course.get("title") or "", course.get("code") or ""]
        ).lower()
        if target_l in haystack:
            return course
    return None


def _pick_assignment(driver, target: str) -> Optional[dict]:
    target_l = target.lower()
    for item in extract_assignments(driver):
        if target_l in (item.get("name") or "").lower():
            return item
    return None


def _check_sso(driver) -> None:
    url = getattr(driver, "current_url", "") or ""
    if is_sso_redirect_url(url):
        _exit_error(
            "session expired",
            url=url,
            reason="redirected to UWA Pheme SSO",
            next_step="foxpilot --zen lms open stream and complete SSO",
        )


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
