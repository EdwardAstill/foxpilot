"""foxpilot.cli — typer CLI.

Usage:
    foxpilot [--zen | --visible | --headless-mode] <command> [args]

Default mode is **claude** — a dedicated Zen profile, hidden in a Hyprland
special workspace so the agent can drive the browser without taking over
the user's screen. Pass --visible to bring the window onto the active
workspace for the duration of the run. Pass --zen to operate on the user's
own running Zen instance instead.
"""

import json as jsonlib
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import typer

from foxpilot.actions import click_action, fill_action
from foxpilot.evidence import create_evidence_bundle
from foxpilot.mission import create_mission, load_mission, update_mission_status
from foxpilot.qa import build_qa_report
from foxpilot.core import (
    browser,
    burst_screenshots,
    claude_hide,
    claude_show,
    claude_status,
    doctor_report,
    import_cookies,
    describe_element,
    extract_assets,
    extract_styles,
    feedback,
    find_element,
    fullpage_screenshot,
    list_tabs,
    read_page,
    record_video,
    switch_tab,
    zen_status,
)
from foxpilot.sites.youtube import app as youtube_app
from foxpilot.sites.youtube import set_browser_factory as set_youtube_browser_factory
from foxpilot.sites.page import app as page_app
from foxpilot.sites.page import set_browser_factory as set_page_browser_factory
from foxpilot.sites.wait_expect import expect_app, wait_app
from foxpilot.sites.wait_expect import set_browser_factory as set_wait_expect_browser_factory
from foxpilot.sites.docs import app as docs_app
from foxpilot.sites.docs import set_browser_factory as set_docs_browser_factory
from foxpilot.sites.github import app as github_app
from foxpilot.sites.github import set_browser_factory as set_github_browser_factory
from foxpilot.sites.macro import app as macro_app
from foxpilot.sites.macro import set_command_prefix_factory as set_macro_command_prefix_factory
from foxpilot.sites.onedrive import app as onedrive_app
from foxpilot.sites.onedrive import set_browser_factory as set_onedrive_browser_factory
from foxpilot.sites.excel import app as excel_app
from foxpilot.sites.excel import set_browser_factory as set_excel_browser_factory
from foxpilot.sites.youtube_music import app as youtube_music_app
from foxpilot.sites.youtube_music import set_browser_factory as set_youtube_music_browser_factory
from foxpilot.sites.lms import app as lms_app
from foxpilot.sites.lms import set_browser_factory as set_lms_browser_factory
from foxpilot.sites.gmail import app as gmail_app
from foxpilot.sites.gmail import set_browser_factory as set_gmail_browser_factory
from foxpilot.sites.gcal import app as gcal_app
from foxpilot.sites.gcal import set_browser_factory as set_gcal_browser_factory
from foxpilot.sites.outlook import app as outlook_app
from foxpilot.sites.outlook import set_browser_factory as set_outlook_browser_factory
from foxpilot.sites.teams import app as teams_app
from foxpilot.sites.teams import set_browser_factory as set_teams_browser_factory
from foxpilot.sites.drive import app as drive_app
from foxpilot.sites.drive import set_browser_factory as set_drive_browser_factory
from foxpilot.sites.wikipedia import app as wikipedia_app
from foxpilot.sites.wikipedia import set_browser_factory as set_wikipedia_browser_factory
from foxpilot.sites.linkedin import app as linkedin_app
from foxpilot.sites.linkedin import set_browser_factory as set_linkedin_browser_factory
from foxpilot.sites.amazon import app as amazon_app
from foxpilot.sites.amazon import set_browser_factory as set_amazon_browser_factory
from foxpilot.plugins import Plugin, discover_plugins

app = typer.Typer(
    help="foxpilot — Firefox browser automation for AI agents.",
    no_args_is_help=True,
)

# Global mode — set by callback before subcommand runs
_MODE = "claude"
_VISIBLE = False


@app.callback()
def _global(
    zen: bool = typer.Option(
        False, "--zen", "-z",
        help="Use user's running Zen browser (shares the user's tabs/cookies).",
    ),
    visible: bool = typer.Option(
        False, "--visible", "-V",
        help="Show the claude-mode browser window on the active workspace.",
    ),
    headless_mode: bool = typer.Option(
        False, "--headless-mode",
        help="Force ephemeral headless Firefox (no profile, no session).",
    ),
):
    global _MODE, _VISIBLE
    if zen:
        _MODE = "zen"
    elif headless_mode:
        _MODE = "headless"
    else:
        _MODE = "claude"
    _VISIBLE = visible


def _mode(override: str = "") -> str:
    return override if override else _MODE


# Helper so every command can pass the right kwargs through to browser()
@contextmanager
def _browser():
    try:
        with browser(mode=_MODE, visible=_VISIBLE) as driver:
            yield driver
    except RuntimeError as exc:
        typer.echo(f"x {exc}", err=True)
        raise typer.Exit(1)


def _branch_browser():
    return browser(mode=_MODE, visible=_VISIBLE)


def _echo_mapping(data: dict) -> None:
    for key, value in data.items():
        typer.echo(f"{key:<22} {value if value is not None else '-'}")


def _macro_command_prefix() -> list[str]:
    if _MODE == "zen":
        return ["--zen"]
    if _MODE == "headless":
        return ["--headless-mode"]
    if _VISIBLE:
        return ["--visible"]
    return []


set_youtube_browser_factory(_browser)
app.add_typer(
    youtube_app,
    name="youtube",
    help="YouTube search, metadata, transcripts, and playlists.",
)
set_page_browser_factory(_browser)
app.add_typer(
    page_app,
    name="page",
    help="Generic page inspection helpers.",
)
set_wait_expect_browser_factory(_browser)
app.add_typer(
    wait_app,
    name="wait",
    help="Wait for browser state.",
)
app.add_typer(
    expect_app,
    name="expect",
    help="Assert current browser state.",
)
set_docs_browser_factory(_browser)
app.add_typer(
    docs_app,
    name="docs",
    help="Documentation search and extraction helpers.",
)
set_github_browser_factory(_branch_browser)
app.add_typer(
    github_app,
    name="github",
    help="GitHub browser helpers.",
)
set_macro_command_prefix_factory(_macro_command_prefix)
app.add_typer(
    macro_app,
    name="macro",
    help="Reusable browser workflow macros.",
)
set_onedrive_browser_factory(_branch_browser)
app.add_typer(
    onedrive_app,
    name="onedrive",
    help="OneDrive Online navigation helpers.",
)
set_excel_browser_factory(_branch_browser)
app.add_typer(
    excel_app,
    name="excel",
    help="Excel Online navigation and cell helpers.",
)
set_youtube_music_browser_factory(_branch_browser)
app.add_typer(
    youtube_music_app,
    name="youtube-music",
    help="YouTube Music search, playback, and playlist helpers.",
)
set_lms_browser_factory(_branch_browser)
app.add_typer(
    lms_app,
    name="lms",
    help="UWA Blackboard Ultra (lms.uwa.edu.au) navigation, stream, courses, grades.",
)
set_gmail_browser_factory(_branch_browser)
app.add_typer(
    gmail_app,
    name="gmail",
    help="Gmail navigation, message list/read/search, compose + thread actions.",
)
set_gcal_browser_factory(_branch_browser)
app.add_typer(
    gcal_app,
    name="gcal",
    help="Google Calendar navigation and event helpers.",
)
set_outlook_browser_factory(_branch_browser)
app.add_typer(
    outlook_app,
    name="outlook",
    help="Microsoft 365 Outlook on the web (mail + calendar) helpers.",
)
set_teams_browser_factory(_branch_browser)
app.add_typer(
    teams_app,
    name="teams",
    help="Microsoft Teams web navigation and messaging helpers.",
)
set_drive_browser_factory(_branch_browser)
app.add_typer(
    drive_app,
    name="drive",
    help="Google Drive navigation, search, and download helpers.",
)
set_wikipedia_browser_factory(_branch_browser)
app.add_typer(
    wikipedia_app,
    name="wikipedia",
    help="Wikipedia article lookup, search, summary, and reference helpers.",
)
set_linkedin_browser_factory(_branch_browser)
app.add_typer(
    linkedin_app,
    name="linkedin",
    help="LinkedIn navigation, profile, search, and messaging helpers.",
)
set_amazon_browser_factory(_branch_browser)
app.add_typer(
    amazon_app,
    name="amazon",
    help="Amazon search, product, orders, cart, and tracking helpers.",
)


plugins_app = typer.Typer(
    help="Discover and inspect Foxpilot plugins.",
    no_args_is_help=True,
)
app.add_typer(plugins_app, name="plugins", help="Discover and inspect Foxpilot plugins.")

evidence_app = typer.Typer(
    help="Capture auditable browser evidence bundles.",
    no_args_is_help=True,
)
app.add_typer(evidence_app, name="evidence", help="Capture auditable browser evidence bundles.")

mission_app = typer.Typer(
    help="Plan and track multi-step browser missions.",
    no_args_is_help=True,
)
app.add_typer(mission_app, name="mission", help="Plan and track multi-step browser missions.")


@plugins_app.command(name="list")
def cmd_plugins_list(
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show load errors."),
):
    """List loaded Foxpilot plugins."""
    registry = _plugin_registry()
    plugins = registry.list()
    if json_output:
        typer.echo(jsonlib.dumps([_plugin_payload(plugin) for plugin in plugins], indent=2))
        return

    if not plugins:
        typer.echo("(no plugins loaded)")
    for plugin in plugins:
        typer.echo(f"{plugin.name:<16} {plugin.source:<7} {plugin.help}")

    errors = registry.load_errors()
    if verbose and errors:
        typer.echo("\nload errors:")
        for error in errors:
            typer.echo(f"  {error.name}: {error.message}")


@plugins_app.command(name="info")
def cmd_plugins_info(
    name: str = typer.Argument(..., help="Plugin name."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
):
    """Show metadata for one plugin."""
    registry = _plugin_registry()
    plugin = registry.info(name)
    if plugin is None:
        error = registry.load_error(name)
        if error is not None:
            typer.echo(f"error: plugin '{name}' failed to load: {error.message}", err=True)
        else:
            typer.echo(f"error: plugin '{name}' not found", err=True)
        raise typer.Exit(1)

    payload = _plugin_payload(plugin)
    if json_output:
        typer.echo(jsonlib.dumps(payload, indent=2))
        return

    for key in ("name", "source", "help", "docs", "auth", "modes"):
        value = payload.get(key)
        if value not in (None, "", []):
            typer.echo(f"{key}: {value}")


@plugins_app.command(name="path")
def cmd_plugins_path():
    """Print plugin search roots."""
    roots = _plugin_roots()
    typer.echo(f"builtins: {roots['builtins']}")
    typer.echo(f"local: {roots['local']}")


@plugins_app.command(name="doctor")
def cmd_plugins_doctor():
    """Check plugin discovery and report load failures."""
    registry = _plugin_registry()
    typer.echo(f"loaded: {len(registry.list())}")
    errors = registry.load_errors()
    if not errors:
        typer.echo("load errors: 0")
        return
    typer.echo(f"load errors: {len(errors)}")
    for error in errors:
        typer.echo(f"- {error.name} ({error.source}) {error.path}: {error.message}")
    raise typer.Exit(1)


def _plugin_registry():
    return discover_plugins(project_root=_project_root())


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _plugin_roots() -> dict[str, Path]:
    root = _project_root()
    return {
        "builtins": Path(__file__).resolve().parent / "plugins" / "builtin",
        "local": root / "plugins",
    }


def _plugin_payload(plugin: Plugin) -> dict[str, object]:
    return {
        "name": plugin.name,
        "source": plugin.source,
        "help": plugin.help,
        "docs": str(plugin.docs_path or ""),
        "auth": plugin.auth_notes or "",
        "modes": list(plugin.browser_modes),
    }


@evidence_app.command(name="bundle")
def cmd_evidence_bundle(
    output_dir: str = typer.Argument(..., help="Directory to write evidence artifacts into."),
    command: str = typer.Option("", "--command", help="Command name to record in metadata."),
    plugin: str = typer.Option("", "--plugin", help="Plugin name to record in metadata."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
):
    """Capture current page URL, text, HTML, screenshot, and metadata."""
    with _browser() as driver:
        bundle = create_evidence_bundle(
            driver,
            output_dir,
            command=command,
            plugin=plugin,
            mode=_MODE,
        )
    if json_output:
        typer.echo(jsonlib.dumps(bundle, indent=2))
        return
    typer.echo(f"bundle: {Path(output_dir) / 'bundle.json'}")
    typer.echo(f"url: {bundle.get('url', '')}")
    typer.echo(f"artifacts: {', '.join(bundle.get('artifacts', []))}")


@mission_app.command(name="run")
def cmd_mission_run(
    task: str = typer.Argument(..., help="Plain-language browser task."),
    root: Optional[str] = typer.Option(None, "--root", help="Mission state root."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
):
    """Create a planned mission state file."""
    from dataclasses import asdict

    state = create_mission(task, root=root)
    payload = asdict(state)
    if json_output:
        typer.echo(jsonlib.dumps(payload, indent=2))
        return
    typer.echo(f"mission: {state.mission_id}")
    typer.echo(f"status: {state.status}")
    for index, step in enumerate(state.steps, 1):
        typer.echo(f"{index}. [{step.status}] {step.kind}: {step.description}")


@mission_app.command(name="status")
def cmd_mission_status(
    mission_id: str = typer.Argument(..., help="Mission id."),
    root: Optional[str] = typer.Option(None, "--root", help="Mission state root."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
):
    """Show mission state."""
    from dataclasses import asdict

    state = load_mission(mission_id, root=root)
    payload = asdict(state)
    if json_output:
        typer.echo(jsonlib.dumps(payload, indent=2))
        return
    typer.echo(f"mission: {state.mission_id}")
    typer.echo(f"task: {state.task}")
    typer.echo(f"status: {state.status}")
    for index, step in enumerate(state.steps, 1):
        typer.echo(f"{index}. [{step.status}] {step.kind}: {step.description}")


@mission_app.command(name="cancel")
def cmd_mission_cancel(
    mission_id: str = typer.Argument(..., help="Mission id."),
    root: Optional[str] = typer.Option(None, "--root", help="Mission state root."),
):
    """Mark a mission as cancelled."""
    state = update_mission_status(mission_id, "cancelled", root=root)
    typer.echo(f"mission: {state.mission_id}")
    typer.echo("status: cancelled")


@app.command(name="qa")
def cmd_qa(
    target_url: str = typer.Argument(..., help="URL to inspect."),
    out: str = typer.Option("/tmp/foxpilot-qa", "--out", "-o", help="Output directory."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
):
    """Capture a basic visual QA report for a URL."""
    with _browser() as driver:
        report = build_qa_report(driver, target_url, out)
    if json_output:
        typer.echo(jsonlib.dumps(report, indent=2))
        return
    typer.echo(f"report: {Path(out) / 'qa-report.json'}")
    typer.echo(f"findings: {len(report.get('findings', []))}")


# ---------------------------------------------------------------------------
# Observation commands
# ---------------------------------------------------------------------------

@app.command(name="tabs")
def cmd_tabs():
    """List all open tabs (requires --zen + Zen running with --marionette)."""
    try:
        tab_list = list_tabs()
    except RuntimeError as e:
        typer.echo(f"✗ {e}", err=True)
        raise typer.Exit(1)

    if not tab_list:
        typer.echo("(no tabs found)")
        return

    for i, tab in enumerate(tab_list):
        marker = ">" if tab.get("active") else " "
        typer.echo(f"{marker}[{i}] {tab.get('title', '(no title)')}")
        typer.echo(f"     {tab.get('url', '')}")


@app.command(name="read")
def cmd_read(
    selector: Optional[str] = typer.Argument(None, help="CSS selector to scope to."),
    tab: Optional[str] = typer.Option(None, "--tab", "-t", help="Tab index or URL substring."),
    full: bool = typer.Option(False, "--full", help="No truncation."),
):
    """Extract main content from current page."""
    max_chars = 50000 if full else 3000
    with _browser() as driver:
        if tab:
            _switch_tab(driver, tab)
        text = read_page(driver, selector, max_chars)
        typer.echo(f"[{driver.title}]")
        typer.echo(driver.current_url)
        typer.echo("-" * 60)
        typer.echo(text)


@app.command(name="screenshot")
def cmd_screenshot(
    path: str = typer.Argument("/tmp/foxpilot-snap.png", help="Output path."),
    selector: Optional[str] = typer.Option(None, "--el", help="Element CSS selector."),
    tab: Optional[str] = typer.Option(None, "--tab", "-t", help="Tab index or URL substring."),
):
    """Take a screenshot and save to disk."""
    from pathlib import Path
    from selenium.webdriver.common.by import By

    out = Path(path)
    with _browser() as driver:
        if tab:
            _switch_tab(driver, tab)
        if selector:
            try:
                el = driver.find_element(By.CSS_SELECTOR, selector)
                el.screenshot(str(out))
            except Exception:
                typer.echo(f"✗ selector '{selector}' not found", err=True)
                raise typer.Exit(1)
        else:
            driver.save_screenshot(str(out))

        size_kb = out.stat().st_size / 1024
        typer.echo(f"✓ screenshot: {out} ({size_kb:.0f}KB)")
        typer.echo(f"  title: {driver.title}")
        typer.echo(f"  url: {driver.current_url}")


@app.command(name="url")
def cmd_url():
    """Show current URL and title."""
    with _browser() as driver:
        typer.echo(driver.title)
        typer.echo(driver.current_url)


@app.command(name="find")
def cmd_find(
    text: str = typer.Argument(..., help="Text to search for in visible elements."),
):
    """Find visible elements matching text and list them."""
    from selenium.webdriver.common.by import By

    with _browser() as driver:
        xpaths = [
            f"//*[contains(text(), '{text}')]",
            f"//*[contains(@aria-label, '{text}')]",
            f"//*[contains(@placeholder, '{text}')]",
            f"//*[contains(@title, '{text}')]",
        ]
        seen: set[int] = set()
        results = []
        for xpath in xpaths:
            try:
                for el in driver.find_elements(By.XPATH, xpath):
                    eid = id(el)
                    if eid not in seen and el.is_displayed():
                        seen.add(eid)
                        results.append(el)
            except Exception:
                continue

        if not results:
            typer.echo(f"✗ no visible elements matching '{text}'")
        else:
            typer.echo(f"✓ {len(results)} element(s) matching '{text}':")
            for i, el in enumerate(results[:20]):
                typer.echo(f"  [{i}] {describe_element(el)}")


# ---------------------------------------------------------------------------
# Action commands
# ---------------------------------------------------------------------------

@app.command(name="go")
def cmd_go(
    target_url: str = typer.Argument(..., help="URL to navigate to."),
):
    """Navigate to URL."""
    with _browser() as driver:
        driver.get(target_url)
        time.sleep(1)
        typer.echo(feedback(driver, f"✓ navigated to {target_url}"))


@app.command(name="search")
def cmd_search(
    query: str = typer.Argument(..., help="Search query."),
):
    """Web search via DuckDuckGo."""
    from foxpilot.search import format_results, search_duckduckgo

    with _browser() as driver:
        results = search_duckduckgo(driver, query)
        typer.echo(format_results(results))


@app.command(name="click")
def cmd_click(
    description: str = typer.Argument(..., help="Visible text, label, or placeholder."),
    role: Optional[str] = typer.Option(None, "--role", "-r", help="Filter by ARIA role."),
    tag: Optional[str] = typer.Option(None, "--tag", "-t", help="Filter by HTML tag."),
):
    """Click an element by visible text."""
    with _browser() as driver:
        result = click_action(driver, description, role=role, tag=tag)
        typer.echo(result.to_text())
        if not result.ok:
            raise typer.Exit(1)


@app.command(name="fill")
def cmd_fill(
    description: str = typer.Argument(..., help="Input label or placeholder."),
    value: str = typer.Argument(..., help="Text to type."),
    submit: bool = typer.Option(False, "--submit", "-s", help="Press Enter after."),
):
    """Fill a text input found by label or placeholder."""
    with _browser() as driver:
        result = fill_action(driver, description, value, submit=submit)
        typer.echo(result.to_text())
        if not result.ok:
            raise typer.Exit(1)


@app.command(name="select")
def cmd_select(
    description: str = typer.Argument(..., help="Dropdown label or name."),
    value: str = typer.Argument(..., help="Option text or value to select."),
):
    """Select a dropdown option."""
    from selenium.webdriver.support.ui import Select

    with _browser() as driver:
        el = find_element(driver, description, tag="select")
        if not el:
            typer.echo(f"✗ no dropdown found for '{description}'")
            raise typer.Exit(1)

        sel = Select(el)
        try:
            sel.select_by_visible_text(value)
        except Exception:
            try:
                sel.select_by_value(value)
            except Exception:
                typer.echo(f"✗ option '{value}' not found")
                raise typer.Exit(1)

        typer.echo(feedback(driver, f"✓ selected '{value}' in {describe_element(el)}"))


@app.command(name="scroll")
def cmd_scroll(
    y: int = typer.Option(600, "--y", help="Pixels to scroll (negative = up)."),
    to: Optional[str] = typer.Option(None, "--to", help="CSS selector to scroll into view."),
):
    """Scroll the page."""
    from selenium.webdriver.common.by import By

    with _browser() as driver:
        if to:
            try:
                el = driver.find_element(By.CSS_SELECTOR, to)
                driver.execute_script(
                    "arguments[0].scrollIntoView({behavior: 'smooth'});", el
                )
                time.sleep(0.5)
                typer.echo(feedback(driver, f"✓ scrolled to '{to}'"))
            except Exception:
                typer.echo(f"✗ selector '{to}' not found", err=True)
                raise typer.Exit(1)
        else:
            driver.execute_script(f"window.scrollBy(0, {y});")
            time.sleep(0.5)
            pos = driver.execute_script("return window.scrollY;")
            typer.echo(feedback(driver, f"✓ scrolled {y}px (position: {pos}px)"))


@app.command(name="back")
def cmd_back():
    """Navigate back."""
    with _browser() as driver:
        driver.back()
        time.sleep(0.8)
        typer.echo(feedback(driver, "✓ back"))


@app.command(name="forward")
def cmd_forward():
    """Navigate forward."""
    with _browser() as driver:
        driver.forward()
        time.sleep(0.8)
        typer.echo(feedback(driver, "✓ forward"))


@app.command(name="key")
def cmd_key(
    name: str = typer.Argument(..., help="Key: enter, tab, escape, space, backspace, arrowup/down/left/right, home, end, pageup, pagedown"),
    focus: Optional[str] = typer.Option(None, "--focus", help="CSS selector to focus first."),
):
    """Press a keyboard key."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys

    KEY_MAP = {
        "enter": Keys.RETURN, "return": Keys.RETURN,
        "tab": Keys.TAB, "escape": Keys.ESCAPE,
        "space": Keys.SPACE, "backspace": Keys.BACKSPACE, "delete": Keys.DELETE,
        "arrowup": Keys.ARROW_UP, "arrowdown": Keys.ARROW_DOWN,
        "arrowleft": Keys.ARROW_LEFT, "arrowright": Keys.ARROW_RIGHT,
        "home": Keys.HOME, "end": Keys.END,
        "pageup": Keys.PAGE_UP, "pagedown": Keys.PAGE_DOWN,
    }
    key_val = KEY_MAP.get(name.lower())
    if not key_val:
        typer.echo(f"✗ unknown key '{name}'. Supported: {', '.join(KEY_MAP)}")
        raise typer.Exit(1)

    with _browser() as driver:
        if focus:
            try:
                el = driver.find_element(By.CSS_SELECTOR, focus)
                el.click()
            except Exception:
                typer.echo(f"✗ selector '{focus}' not found", err=True)
                raise typer.Exit(1)

        active = driver.switch_to.active_element
        active.send_keys(key_val)
        time.sleep(0.5)
        typer.echo(feedback(driver, f"✓ pressed {name}"))


@app.command(name="tab")
def cmd_tab(
    target: str = typer.Argument(..., help="Tab index or URL/title substring."),
):
    """Switch to a tab by index or substring (zen mode — operates on real browser)."""
    try:
        t = switch_tab(target)
        typer.echo(f"✓ switched to {t.get('title', '') or t.get('url', '')}")
    except RuntimeError as e:
        typer.echo(f"✗ {e}", err=True)
        raise typer.Exit(1)


@app.command(name="new-tab")
def cmd_new_tab(
    target_url: Optional[str] = typer.Argument(None, help="URL to open (optional)."),
):
    """Open a new tab."""
    with _browser() as driver:
        driver.execute_script("window.open('', '_blank');")
        handles = driver.window_handles
        driver.switch_to.window(handles[-1])
        if target_url:
            driver.get(target_url)
            time.sleep(1)
        typer.echo(feedback(driver, "✓ opened new tab"))


@app.command(name="close-tab")
def cmd_close_tab(
    index: Optional[int] = typer.Argument(None, help="Tab index to close (default: current)."),
):
    """Close a tab."""
    with _browser() as driver:
        if index is not None:
            handles = driver.window_handles
            if 0 <= index < len(handles):
                driver.switch_to.window(handles[index])
            else:
                typer.echo(f"✗ index {index} out of range")
                raise typer.Exit(1)
        title = driver.title
        driver.close()
        typer.echo(f"✓ closed: {title}")


# ---------------------------------------------------------------------------
# Design inspection
# ---------------------------------------------------------------------------

@app.command(name="styles")
def cmd_styles(
    selector: Optional[str] = typer.Argument(None, help="CSS selector (default: body)."),
):
    """Extract computed styles and CSS variables from the page."""
    with _browser() as driver:
        data = extract_styles(driver, selector)

        typer.echo(f"[{data['element']}]")
        typer.echo(driver.current_url)

        if data["styles"]:
            typer.echo("\n── computed styles ──")
            for k, v in data["styles"].items():
                typer.echo(f"  {k:<28} {v}")

        if data["cssVars"]:
            typer.echo(f"\n── css variables ({len(data['cssVars'])}) ──")
            for k, v in list(data["cssVars"].items())[:60]:
                typer.echo(f"  {k:<40} {v}")

        if data["colors"]:
            typer.echo(f"\n── colors on page ({len(data['colors'])}) ──")
            for c in data["colors"]:
                typer.echo(f"  {c}")


@app.command(name="assets")
def cmd_assets():
    """Extract all assets from the page: images, fonts, stylesheets, background images."""
    with _browser() as driver:
        data = extract_assets(driver)

        typer.echo(driver.current_url)

        typer.echo(f"\n── images ({len(data['images'])}) ──")
        for img in data["images"][:30]:
            dim = f"{img['width']}×{img['height']}" if img["width"] else "?"
            alt = f' "{img["alt"]}"' if img["alt"] else ""
            typer.echo(f"  {dim:<12} {img['src']}{alt}")

        typer.echo(f"\n── font families ({len(data['fontFamilies'])}) ──")
        for f in data["fontFamilies"]:
            typer.echo(f"  {f}")

        if data["fonts"]:
            typer.echo(f"\n── loaded fonts ({len(data['fonts'])}) ──")
            for f in data["fonts"]:
                typer.echo(f"  {f['family']:<30} weight={f['weight']} style={f['style']} [{f['status']}]")

        if data["stylesheets"]:
            typer.echo(f"\n── stylesheets ({len(data['stylesheets'])}) ──")
            for s in data["stylesheets"]:
                typer.echo(f"  {s}")

        if data["favicon"]:
            typer.echo(f"\n── favicon ──\n  {data['favicon']}")

        if data["backgroundImages"]:
            typer.echo(f"\n── background images ({len(data['backgroundImages'])}) ──")
            for b in data["backgroundImages"]:
                typer.echo(f"  {b}")

        if data["inlineSvgs"]:
            typer.echo(f"\n── inline svgs ({len(data['inlineSvgs'])}) ──")
            for s in data["inlineSvgs"]:
                typer.echo(f"  {s}")


@app.command(name="fullpage")
def cmd_fullpage(
    path: str = typer.Argument("/tmp/foxpilot-full.png", help="Output path."),
):
    """Take a full-page screenshot (captures entire scroll height)."""
    with _browser() as driver:
        out, size_kb = fullpage_screenshot(driver, path)
        typer.echo(f"✓ fullpage screenshot: {out} ({size_kb:.0f}KB)")
        typer.echo(f"  title: {driver.title}")
        typer.echo(f"  url: {driver.current_url}")


@app.command(name="burst")
def cmd_burst(
    target_url: Optional[str] = typer.Argument(None, help="URL to navigate to first (optional)."),
    count: int = typer.Option(10, "--count", "-n", help="Number of frames to capture."),
    interval: int = typer.Option(500, "--interval", "-i", help="Milliseconds between frames."),
    out: str = typer.Option("/tmp/foxpilot-burst", "--out", "-o", help="Output directory."),
    prefix: str = typer.Option("frame", "--prefix", help="Filename prefix."),
    warmup: float = typer.Option(1.0, "--warmup", help="Seconds to wait after navigate."),
):
    """Take N screenshots spaced --interval ms apart.

    Produces PNGs the agent's Read tool can view directly — unlike video.
    Use this when you want an agent-readable time-lapse of a page.
    """
    with _browser() as driver:
        if target_url:
            driver.get(target_url)
            time.sleep(warmup)
        paths = burst_screenshots(driver, out, count=count, interval_ms=interval, prefix=prefix)
        typer.echo(f"✓ burst: {len(paths)} frames → {out}/")
        typer.echo(f"  first: {paths[0]}")
        typer.echo(f"  last:  {paths[-1]}")
        typer.echo(f"  title: {driver.title}")
        typer.echo(f"  url:   {driver.current_url}")


@app.command(name="record")
def cmd_record(
    target_url: Optional[str] = typer.Argument(None, help="URL to navigate to first (optional)."),
    duration: float = typer.Option(5.0, "--duration", "-d", help="Recording length in seconds."),
    fps: int = typer.Option(5, "--fps", help="Frames per second."),
    out: str = typer.Option("/tmp/foxpilot-clip.mp4", "--out", "-o", help="Output file (.mp4/.webm/.mkv/.gif)."),
    warmup: float = typer.Option(1.0, "--warmup", help="Seconds to wait after navigate."),
    keep_frames: bool = typer.Option(False, "--keep-frames", help="Keep the raw PNG frames."),
):
    """Record a video clip by frame-bursting, then stitching with ffmpeg.

    NOTE: agents can't read video — use `burst` if the frames need to go to
    an agent. `record` is for human-debug clips.
    """
    with _browser() as driver:
        if target_url:
            driver.get(target_url)
            time.sleep(warmup)
        try:
            path, n = record_video(
                driver, out, duration_s=duration, fps=fps, cleanup=not keep_frames
            )
        except RuntimeError as e:
            typer.echo(f"✗ {e}", err=True)
            raise typer.Exit(1)
        typer.echo(f"✓ recorded: {path} ({n} frames @ {fps}fps, {duration}s)")
        typer.echo(f"  title: {driver.title}")
        typer.echo(f"  url:   {driver.current_url}")


# ---------------------------------------------------------------------------
# Testing / assertion commands
# ---------------------------------------------------------------------------

@app.command(name="assert")
def cmd_assert(
    text: str = typer.Argument(..., help="Text that must be present on the page."),
    selector: Optional[str] = typer.Option(None, "--in", help="Scope to a CSS selector."),
    invert: bool = typer.Option(False, "--not", help="Assert text is NOT present."),
):
    """Assert page contains (or lacks) text. Exits 1 on failure — use in test scripts."""
    with _browser() as driver:
        content = read_page(driver, selector, max_chars=50000)
        found = text.lower() in content.lower()
        url = driver.current_url

        if invert:
            if found:
                typer.echo(f"✗ ASSERT FAILED: '{text}' was found but should not be present")
                typer.echo(f"  url: {url}")
                raise typer.Exit(1)
            typer.echo(f"✓ ASSERT PASSED: '{text}' not present (as expected)")
            typer.echo(f"  url: {url}")
        else:
            if not found:
                typer.echo(f"✗ ASSERT FAILED: '{text}' not found on page")
                typer.echo(f"  url: {url}")
                raise typer.Exit(1)
            typer.echo(f"✓ ASSERT PASSED: '{text}' found")
            typer.echo(f"  url: {url}")


@app.command(name="canvas-screenshot")
def cmd_canvas_screenshot(
    path: str = typer.Argument("/tmp/foxpilot-canvas.png", help="Output path for PNG."),
    selector: Optional[str] = typer.Option(None, "--el", help="CSS selector for canvas (default: first canvas)."),
):
    """Capture a canvas element's pixels via toDataURL().

    Works for Canvas 2D contexts. WebGL canvases are security-tainted and will
    fail — WebGL content cannot be read back from JavaScript.
    """
    import base64
    from pathlib import Path as _Path

    out = _Path(path)
    css = selector or "canvas"

    with _browser() as driver:
        result = driver.execute_script(f"""
            const c = document.querySelector({repr(css)});
            if (!c) return null;
            try {{ return c.toDataURL('image/png').split(',')[1]; }}
            catch (e) {{ return 'ERROR:' + e.message; }}
        """)

        if result is None:
            typer.echo(f"✗ no canvas found matching '{css}'", err=True)
            raise typer.Exit(1)
        if isinstance(result, str) and result.startswith("ERROR:"):
            typer.echo(f"✗ canvas capture failed: {result[6:]}", err=True)
            raise typer.Exit(1)

        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(base64.b64decode(result))
        size_kb = out.stat().st_size / 1024
        typer.echo(f"✓ canvas screenshot: {out} ({size_kb:.0f}KB)")
        typer.echo(f"  title: {driver.title}")
        typer.echo(f"  url: {driver.current_url}")


# ---------------------------------------------------------------------------
# Escape hatches
# ---------------------------------------------------------------------------

@app.command(name="js")
def cmd_js(
    expr: str = typer.Argument(..., help="JavaScript expression to evaluate."),
):
    """Evaluate JavaScript in the page context."""
    with _browser() as driver:
        result = driver.execute_script(f"return {expr};")
        typer.echo(f"✓ {result}")


@app.command(name="html")
def cmd_html(
    selector: Optional[str] = typer.Argument(None, help="CSS selector (default: full body)."),
):
    """Extract raw HTML from page or element."""
    from selenium.webdriver.common.by import By

    with _browser() as driver:
        if selector:
            try:
                el = driver.find_element(By.CSS_SELECTOR, selector)
                typer.echo(el.get_attribute("outerHTML"))
            except Exception:
                typer.echo(f"✗ selector '{selector}' not found", err=True)
                raise typer.Exit(1)
        else:
            body = driver.find_element(By.TAG_NAME, "body")
            typer.echo(body.get_attribute("innerHTML")[:8000])


@app.command(name="css-click")
def cmd_css_click(
    selector: str = typer.Argument(..., help="CSS selector to click."),
):
    """Click an element by CSS selector (escape hatch)."""
    from selenium.webdriver.common.by import By

    with _browser() as driver:
        try:
            el = driver.find_element(By.CSS_SELECTOR, selector)
            el.click()
            time.sleep(0.8)
            typer.echo(feedback(driver, f"✓ clicked '{selector}'"))
        except Exception as e:
            typer.echo(f"✗ {e}", err=True)
            raise typer.Exit(1)


@app.command(name="css-fill")
def cmd_css_fill(
    selector: str = typer.Argument(..., help="CSS selector of input."),
    value: str = typer.Argument(..., help="Text to type."),
):
    """Fill an input by CSS selector (escape hatch)."""
    from selenium.webdriver.common.by import By

    with _browser() as driver:
        try:
            el = driver.find_element(By.CSS_SELECTOR, selector)
            el.clear()
            el.send_keys(value)
            typer.echo(feedback(driver, f"✓ filled '{selector}' with '{value}'"))
        except Exception as e:
            typer.echo(f"✗ {e}", err=True)
            raise typer.Exit(1)


# ---------------------------------------------------------------------------
# MCP server launcher
# ---------------------------------------------------------------------------

@app.command(name="mcp")
def cmd_mcp():
    """Start the foxpilot MCP server (stdio transport for Claude Code)."""
    from foxpilot.mcp_server import serve
    serve()


@app.command(name="doctor")
def cmd_doctor(
    fix: bool = typer.Option(False, "--fix", help="Apply safe local repairs before reporting."),
):
    """Check local Foxpilot browser automation prerequisites."""
    from foxpilot.doctor import format_diagnostics, run_diagnostics, run_safe_fixes

    if fix:
        typer.echo("safe fixes:")
        typer.echo(format_diagnostics(run_safe_fixes()))
        typer.echo("")
    report = run_diagnostics()
    typer.echo(format_diagnostics(report))
    if any(not item.get("ok") for item in report.values()):
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Claude profile lifecycle (Hyprland scratchpad)
# ---------------------------------------------------------------------------

@app.command(name="show")
def cmd_show():
    """Bring the claude-profile Zen window onto the active workspace."""
    result = claude_show()
    status = result["status"]
    if status == "not_running":
        typer.echo("x claude window not running", err=True)
        raise typer.Exit(1)
    if status == "already_visible":
        typer.echo("OK claude window already visible")
        return
    typer.echo("OK claude window -> active workspace")


@app.command(name="hide")
def cmd_hide():
    """Send the claude-profile Zen window to the special:claude scratchpad."""
    result = claude_hide()
    status = result["status"]
    if status == "not_running":
        typer.echo("x claude window not running", err=True)
        raise typer.Exit(1)
    if status == "already_hidden":
        typer.echo("OK claude window already hidden")
        return
    typer.echo("OK claude window -> special:claude")


@app.command(name="import-cookies")
def cmd_import_cookies(
    src: Optional[str] = typer.Option(
        None, "--from", help="Source Zen profile dir (default: auto-detect).",
    ),
    domain: Optional[str] = typer.Option(
        None, "--domain", help="Only import cookies whose host LIKE %domain%.",
    ),
    include_storage: bool = typer.Option(
        False, "--include-storage", help="Also copy DOM Storage / localStorage.",
    ),
    include_passwords: bool = typer.Option(
        False, "--include-passwords",
        help="Also copy logins.json + key4.db (saved passwords).",
    ),
):
    """Copy cookies from your main Zen profile into the claude profile.

    Bypasses sites that block WebDriver-based logins (Google, Cloudflare-walled
    sites, etc.). Kills the claude Zen process first so files aren't locked.
    Your main Zen can stay running — uses SQLite's online backup API.
    """
    from pathlib import Path as _Path
    try:
        report = import_cookies(
            src_profile=_Path(src) if src else None,
            domain=domain,
            include_storage=include_storage,
            include_passwords=include_passwords,
        )
    except RuntimeError as e:
        typer.echo(f"✗ {e}", err=True)
        raise typer.Exit(1)
    typer.echo(f"✓ imported from: {report['src']}")
    typer.echo(f"  → {report['dst']}")
    typer.echo(f"  cookies:   {report['cookies_copied']} rows"
               + (f" (filtered to *{domain}*)" if domain else ""))
    typer.echo(f"  storage:   {'yes' if report['storage_copied'] else 'no'}")
    typer.echo(f"  passwords: {'yes' if report['passwords_copied'] else 'no'}")


@app.command(name="status")
def cmd_status():
    """Report state for the selected mode."""
    if _MODE == "zen":
        report = {"mode": "zen"} | zen_status()
    elif _MODE == "headless":
        report = doctor_report("headless")
    else:
        report = {"mode": "claude"} | claude_status()
    _echo_mapping(report)


@app.command(name="doctor")
def cmd_doctor():
    """Diagnose the selected mode and print next-step guidance."""
    _echo_mapping(doctor_report(_MODE))


@app.command(name="login")
def cmd_login(
    target_url: Optional[str] = typer.Argument(
        None, help="Site to open for login (default: about:preferences)."
    ),
    auto_hide: bool = typer.Option(
        True, "--auto-hide/--no-auto-hide",
        help="Hide the browser automatically once URL has changed and stayed "
             "stable (heuristic for sign-in completion).",
    ),
    stable_secs: float = typer.Option(
        8.0, "--stable", help="Seconds the URL must stay unchanged after a "
        "change to count as 'signed in'.",
    ),
    timeout_secs: float = typer.Option(
        300.0, "--timeout", help="Hard timeout — hide after this many seconds "
        "regardless of state.",
    ),
):
    """Open the claude profile visibly so the user can log into sites once.

    With --auto-hide (default): polls the page URL every ~2s and, once the URL
    has changed from the initial target and then stayed stable for --stable
    seconds, hides the browser. This catches the typical post-login redirect
    to a dashboard / home page.

    With --no-auto-hide: opens visibly and exits — user runs `foxpilot hide`
    when ready.

    Either way, cookies persist in the profile dir for subsequent hidden runs.
    """
    from foxpilot.core import claude_hide as _hide

    initial_url = target_url or "about:preferences"

    # Use mode="claude" + visible=True. Don't drop the driver via `with` —
    # we want to keep the marionette session alive so we can poll URL.
    from foxpilot.core import _get_driver_claude
    driver = _get_driver_claude(visible=True)
    try:
        driver.get(initial_url)
        if not auto_hide:
            typer.echo(
                "✓ claude profile open and visible. Run `foxpilot hide` when done."
            )
            return

        typer.echo(
            f"✓ claude profile visible at {initial_url}\n"
            f"  watching for sign-in (URL change + {stable_secs:.0f}s stable).\n"
            f"  ctrl-c to cancel auto-hide and leave window visible."
        )

        import time as _t
        start = _t.monotonic()
        last_url = driver.current_url
        last_change = start
        url_ever_changed = False

        try:
            while True:
                _t.sleep(2.0)
                elapsed = _t.monotonic() - start
                if elapsed > timeout_secs:
                    typer.echo(f"⚠ timeout after {timeout_secs:.0f}s — hiding anyway.")
                    break
                try:
                    cur = driver.current_url
                except Exception:
                    continue
                if cur != last_url:
                    last_url = cur
                    last_change = _t.monotonic()
                    if cur != initial_url:
                        url_ever_changed = True
                    typer.echo(f"  url → {cur}")
                    continue
                if (
                    url_ever_changed
                    and (_t.monotonic() - last_change) >= stable_secs
                ):
                    typer.echo(f"✓ stable at {cur} — hiding.")
                    break
        except KeyboardInterrupt:
            typer.echo("\n(cancelled — leaving window visible)")
            return
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    _hide()
    typer.echo("✓ hidden — claude profile keeps the cookies for next run.")


# ---------------------------------------------------------------------------
# Tab switching helper for driver context (not browser UI)
# ---------------------------------------------------------------------------

def _switch_tab(driver, target: str) -> bool:
    """Switch driver window context by index or URL/title substring."""
    handles = driver.window_handles
    try:
        idx = int(target)
        if 0 <= idx < len(handles):
            driver.switch_to.window(handles[idx])
            return True
    except ValueError:
        pass
    tl = target.lower()
    for h in handles:
        driver.switch_to.window(h)
        if tl in driver.title.lower() or tl in driver.current_url.lower():
            return True
    return False


def _run():
    try:
        app()
    except RuntimeError as e:
        typer.echo(f"✗ {e}", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    _run()
