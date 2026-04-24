"""Typer command branches for synchronization and page assertions."""

from __future__ import annotations

import re
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, Optional

import typer

from foxpilot.core import browser, read_page


wait_app = typer.Typer(
    help="Wait for page state such as text, selectors, URL changes, and idle load.",
    no_args_is_help=True,
)
expect_app = typer.Typer(
    help="Assert current page state immediately and exit non-zero on failure.",
    no_args_is_help=True,
)

BrowserFactory = Callable[[], object]
Condition = Callable[[], "CheckResult"]
Clock = Callable[[], float]
Sleeper = Callable[[float], None]


@dataclass(frozen=True)
class CheckResult:
    """Immediate condition result used by wait and expect commands."""

    ok: bool
    message: str
    url: str = ""
    title: str = ""

    def to_text(self) -> str:
        prefix = "OK" if self.ok else "x"
        lines = [f"{prefix} {self.message}"]
        if self.url:
            lines.append(f"url: {self.url}")
        if self.title:
            lines.append(f"title: {self.title}")
        return "\n".join(lines)


@dataclass(frozen=True)
class WaitResult(CheckResult):
    """Polling result with attempt and elapsed metadata."""

    attempts: int = 0
    elapsed_s: float = 0.0


def _default_browser():
    return browser()


_browser_factory: BrowserFactory = _default_browser


def set_browser_factory(factory: BrowserFactory) -> None:
    """Set the browser factory used by both wait and expect branches."""
    global _browser_factory
    _browser_factory = factory


@contextmanager
def _site_browser():
    with _browser_factory() as driver:
        yield driver


def pattern_matches(
    value: str,
    pattern: str,
    *,
    regex: bool = False,
    case_sensitive: bool = False,
) -> bool:
    """Return True when value contains pattern, or regex matches when enabled."""
    value = value or ""
    pattern = pattern or ""
    if regex:
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            return re.search(pattern, value, flags=flags) is not None
        except re.error:
            return False
    if case_sensitive:
        return pattern in value
    return pattern.casefold() in value.casefold()


def wait_until(
    condition: Condition,
    *,
    timeout_s: float = 10.0,
    poll_s: float = 0.25,
    monotonic: Optional[Clock] = None,
    sleeper: Optional[Sleeper] = None,
) -> WaitResult:
    """Poll condition until it succeeds or timeout_s expires."""
    monotonic = monotonic or time.monotonic
    sleeper = sleeper or time.sleep
    timeout_s = max(0.0, timeout_s)
    poll_s = max(0.01, poll_s)
    start = monotonic()
    deadline = start + timeout_s
    attempts = 0
    last = CheckResult(ok=False, message="condition did not run")

    while True:
        attempts += 1
        last = condition()
        if last.ok:
            return WaitResult(
                ok=True,
                message=last.message,
                url=last.url,
                title=last.title,
                attempts=attempts,
                elapsed_s=monotonic() - start,
            )

        now = monotonic()
        if now >= deadline:
            return WaitResult(
                ok=False,
                message=f"timed out after {timeout_s:.1f}s: {last.message}",
                url=last.url,
                title=last.title,
                attempts=attempts,
                elapsed_s=now - start,
            )

        sleeper(min(poll_s, deadline - now))


def check_text(
    driver,
    text: str,
    *,
    selector: Optional[str] = None,
    case_sensitive: bool = False,
) -> CheckResult:
    """Check current visible page text, optionally scoped to a CSS selector."""
    url, title = _page_state(driver)
    content = _read_visible_text(driver, selector)
    scope = f" in selector {selector!r}" if selector else ""
    if content is None:
        return CheckResult(
            ok=False,
            message=f"selector not found: {selector}",
            url=url,
            title=title,
        )

    if pattern_matches(content, text, case_sensitive=case_sensitive):
        return CheckResult(ok=True, message=f"text found{scope}: {text}", url=url, title=title)
    return CheckResult(ok=False, message=f"text not found{scope}: {text}", url=url, title=title)


def check_selector(driver, selector: str) -> CheckResult:
    """Check that a visible CSS selector exists."""
    from selenium.webdriver.common.by import By

    url, title = _page_state(driver)
    try:
        element = driver.find_element(By.CSS_SELECTOR, selector)
    except Exception:
        return CheckResult(ok=False, message=f"selector not found: {selector}", url=url, title=title)

    if _is_displayed(element):
        return CheckResult(ok=True, message=f"selector visible: {selector}", url=url, title=title)
    return CheckResult(ok=False, message=f"selector hidden: {selector}", url=url, title=title)


def check_gone(driver, selector: str) -> CheckResult:
    """Check that a CSS selector has no visible matching elements."""
    from selenium.webdriver.common.by import By

    url, title = _page_state(driver)
    try:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
    except Exception:
        elements = []

    visible_count = sum(1 for element in elements if _is_displayed(element))
    if visible_count == 0:
        return CheckResult(ok=True, message=f"selector gone: {selector}", url=url, title=title)
    return CheckResult(
        ok=False,
        message=f"selector still visible: {selector} ({visible_count})",
        url=url,
        title=title,
    )


def check_url(
    driver,
    expected: str,
    *,
    regex: bool = False,
    case_sensitive: bool = False,
) -> CheckResult:
    """Check current URL against a substring or regex."""
    url, title = _page_state(driver)
    if pattern_matches(url, expected, regex=regex, case_sensitive=case_sensitive):
        return CheckResult(ok=True, message=f"url matched: {expected}", url=url, title=title)
    return CheckResult(ok=False, message=f"url did not match: {expected}", url=url, title=title)


def check_title(
    driver,
    expected: str,
    *,
    regex: bool = False,
    case_sensitive: bool = False,
) -> CheckResult:
    """Check current page title against a substring or regex."""
    url, title = _page_state(driver)
    if pattern_matches(title, expected, regex=regex, case_sensitive=case_sensitive):
        return CheckResult(ok=True, message=f"title matched: {expected}", url=url, title=title)
    return CheckResult(ok=False, message=f"title did not match: {expected}", url=url, title=title)


def check_idle(driver, *, quiet_ms: int = 500) -> CheckResult:
    """Best-effort check that document loading and recent resources are idle."""
    url, title = _page_state(driver)
    try:
        state = driver.execute_script(
            """
            const resources = performance.getEntriesByType('resource');
            const lastEnd = resources.reduce(
              (max, r) => Math.max(max, r.responseEnd || r.startTime || 0),
              0
            );
            const pending = resources.filter(r => !r.responseEnd).length;
            return {
              ready: document.readyState,
              pending,
              quietFor: performance.now() - lastEnd
            };
            """
        ) or {}
    except Exception as exc:
        return CheckResult(ok=False, message=f"idle check failed: {exc}", url=url, title=title)

    ready = state.get("ready") == "complete"
    pending = int(state.get("pending") or 0)
    quiet_for = float(state.get("quietFor") or 0.0)
    if ready and pending == 0 and quiet_for >= quiet_ms:
        return CheckResult(ok=True, message="page idle", url=url, title=title)
    return CheckResult(
        ok=False,
        message=(
            "page not idle: "
            f"ready={state.get('ready')}, pending={pending}, quiet_for={quiet_for:.0f}ms"
        ),
        url=url,
        title=title,
    )


@wait_app.command(name="help")
def wait_help():
    """Show wait command examples."""
    typer.echo(
        """foxpilot wait - poll until a browser condition becomes true

Common commands:
  foxpilot wait text "Signed in"
  foxpilot wait text "Done" --in main --timeout 15
  foxpilot wait selector "button[type=submit]"
  foxpilot wait url "dashboard"
  foxpilot wait url "/items/\\d+$" --regex
  foxpilot wait gone ".spinner"
  foxpilot wait idle

Options:
  --timeout SEC       Seconds before failing, default 10
  --poll SEC          Poll interval, default 0.25
  --regex             Treat URL patterns as regular expressions
  --case-sensitive    Use case-sensitive text/URL matching

Run:
  foxpilot wait <command> --help"""
    )


@wait_app.command(name="text")
def wait_text(
    text: str = typer.Argument(..., help="Visible text to wait for."),
    selector: Optional[str] = typer.Option(None, "--in", help="Scope to a CSS selector."),
    timeout: float = typer.Option(10.0, "--timeout", "-t", min=0.0, help="Seconds before failing."),
    poll: float = typer.Option(0.25, "--poll", min=0.01, help="Polling interval in seconds."),
    case_sensitive: bool = typer.Option(False, "--case-sensitive", help="Use case-sensitive matching."),
):
    """Wait until visible text appears on the page."""
    _run_wait(
        lambda driver: check_text(
            driver,
            text,
            selector=selector,
            case_sensitive=case_sensitive,
        ),
        timeout_s=timeout,
        poll_s=poll,
    )


@wait_app.command(name="selector")
def wait_selector(
    selector: str = typer.Argument(..., help="CSS selector to wait for."),
    timeout: float = typer.Option(10.0, "--timeout", "-t", min=0.0, help="Seconds before failing."),
    poll: float = typer.Option(0.25, "--poll", min=0.01, help="Polling interval in seconds."),
):
    """Wait until a visible CSS selector exists."""
    _run_wait(lambda driver: check_selector(driver, selector), timeout_s=timeout, poll_s=poll)


@wait_app.command(name="url")
def wait_url(
    expected: str = typer.Argument(..., help="URL substring, or regex with --regex."),
    timeout: float = typer.Option(10.0, "--timeout", "-t", min=0.0, help="Seconds before failing."),
    poll: float = typer.Option(0.25, "--poll", min=0.01, help="Polling interval in seconds."),
    regex: bool = typer.Option(False, "--regex", help="Treat expected as a regular expression."),
    case_sensitive: bool = typer.Option(False, "--case-sensitive", help="Use case-sensitive matching."),
):
    """Wait until the current URL matches."""
    _run_wait(
        lambda driver: check_url(
            driver,
            expected,
            regex=regex,
            case_sensitive=case_sensitive,
        ),
        timeout_s=timeout,
        poll_s=poll,
    )


@wait_app.command(name="gone")
def wait_gone(
    selector: str = typer.Argument(..., help="CSS selector that should disappear."),
    timeout: float = typer.Option(10.0, "--timeout", "-t", min=0.0, help="Seconds before failing."),
    poll: float = typer.Option(0.25, "--poll", min=0.01, help="Polling interval in seconds."),
):
    """Wait until a CSS selector is absent or hidden."""
    _run_wait(lambda driver: check_gone(driver, selector), timeout_s=timeout, poll_s=poll)


@wait_app.command(name="idle")
def wait_idle(
    timeout: float = typer.Option(10.0, "--timeout", "-t", min=0.0, help="Seconds before failing."),
    poll: float = typer.Option(0.25, "--poll", min=0.01, help="Polling interval in seconds."),
    quiet_ms: int = typer.Option(500, "--quiet-ms", min=0, help="Required quiet window in milliseconds."),
):
    """Wait until document.readyState is complete and resources are quiet."""
    _run_wait(lambda driver: check_idle(driver, quiet_ms=quiet_ms), timeout_s=timeout, poll_s=poll)


@expect_app.command(name="help")
def expect_help():
    """Show expect command examples."""
    typer.echo(
        """foxpilot expect - assert current browser state immediately

Common commands:
  foxpilot expect text "Signed in"
  foxpilot expect text "Dashboard" --in main
  foxpilot expect selector "button[type=submit]"
  foxpilot expect url "dashboard"
  foxpilot expect url "/items/\\d+$" --regex
  foxpilot expect title "Settings"

Options:
  --regex             Treat URL/title patterns as regular expressions
  --case-sensitive    Use case-sensitive text/URL/title matching

Run:
  foxpilot expect <command> --help"""
    )


@expect_app.command(name="text")
def expect_text(
    text: str = typer.Argument(..., help="Visible text that must be present."),
    selector: Optional[str] = typer.Option(None, "--in", help="Scope to a CSS selector."),
    case_sensitive: bool = typer.Option(False, "--case-sensitive", help="Use case-sensitive matching."),
):
    """Assert visible text is present immediately."""
    _run_expect(
        lambda driver: check_text(
            driver,
            text,
            selector=selector,
            case_sensitive=case_sensitive,
        )
    )


@expect_app.command(name="selector")
def expect_selector(selector: str = typer.Argument(..., help="CSS selector that must be visible.")):
    """Assert a visible CSS selector exists immediately."""
    _run_expect(lambda driver: check_selector(driver, selector))


@expect_app.command(name="url")
def expect_url(
    expected: str = typer.Argument(..., help="URL substring, or regex with --regex."),
    regex: bool = typer.Option(False, "--regex", help="Treat expected as a regular expression."),
    case_sensitive: bool = typer.Option(False, "--case-sensitive", help="Use case-sensitive matching."),
):
    """Assert current URL matches immediately."""
    _run_expect(
        lambda driver: check_url(
            driver,
            expected,
            regex=regex,
            case_sensitive=case_sensitive,
        )
    )


@expect_app.command(name="title")
def expect_title(
    expected: str = typer.Argument(..., help="Title substring, or regex with --regex."),
    regex: bool = typer.Option(False, "--regex", help="Treat expected as a regular expression."),
    case_sensitive: bool = typer.Option(False, "--case-sensitive", help="Use case-sensitive matching."),
):
    """Assert current page title matches immediately."""
    _run_expect(
        lambda driver: check_title(
            driver,
            expected,
            regex=regex,
            case_sensitive=case_sensitive,
        )
    )


def _run_wait(
    check: Callable[[object], CheckResult],
    *,
    timeout_s: float,
    poll_s: float,
) -> None:
    with _site_browser() as driver:
        result = wait_until(lambda: check(driver), timeout_s=timeout_s, poll_s=poll_s)
        typer.echo(result.to_text())
        if not result.ok:
            raise typer.Exit(1)


def _run_expect(check: Callable[[object], CheckResult]) -> None:
    with _site_browser() as driver:
        result = check(driver)
        typer.echo(result.to_text())
        if not result.ok:
            raise typer.Exit(1)


def _read_visible_text(driver, selector: Optional[str]) -> Optional[str]:
    if not selector:
        return read_page(driver, max_chars=50000)

    from selenium.webdriver.common.by import By

    try:
        element = driver.find_element(By.CSS_SELECTOR, selector)
    except Exception:
        return None
    return element.text or ""


def _is_displayed(element) -> bool:
    try:
        return bool(element.is_displayed())
    except Exception:
        return False


def _page_state(driver) -> tuple[str, str]:
    try:
        url = str(driver.current_url or "")
    except Exception:
        url = ""
    try:
        title = str(driver.title or "")
    except Exception:
        title = ""
    return url, title
