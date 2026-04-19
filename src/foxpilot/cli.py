"""foxpilot.cli — typer CLI.

Usage:
    foxpilot [--zen] <command> [args]

Pass --zen to operate on the user's running Zen browser.
Default is headless Firefox (ephemeral, no existing session).
"""

import time
from typing import Optional

import typer

from foxpilot.core import (
    browser,
    burst_screenshots,
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
)

app = typer.Typer(
    help="foxpilot — Firefox browser automation for AI agents.",
    no_args_is_help=True,
)

# Global mode — set by --zen callback before subcommand runs
_MODE = "headless"


@app.callback()
def _global(
    zen: bool = typer.Option(False, "--zen", "-z", help="Use user's running Zen browser."),
):
    global _MODE
    _MODE = "zen" if zen else "headless"


def _mode(override: str = "") -> str:
    return override if override else _MODE


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
    with browser(mode=_MODE) as driver:
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
    with browser(mode=_MODE) as driver:
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
    with browser(mode=_MODE) as driver:
        typer.echo(driver.title)
        typer.echo(driver.current_url)


@app.command(name="find")
def cmd_find(
    text: str = typer.Argument(..., help="Text to search for in visible elements."),
):
    """Find visible elements matching text and list them."""
    from selenium.webdriver.common.by import By

    with browser(mode=_MODE) as driver:
        xpaths = [
            f"//*[contains(text(), '{text}')]",
            f"//*[@aria-label[contains(., '{text}')]]",
            f"//*[@placeholder[contains(., '{text}')]]",
            f"//*[@title[contains(., '{text}')]]",
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
    with browser(mode=_MODE) as driver:
        driver.get(target_url)
        time.sleep(1)
        typer.echo(feedback(driver, f"✓ navigated to {target_url}"))


@app.command(name="search")
def cmd_search(
    query: str = typer.Argument(..., help="Search query."),
):
    """Web search via DuckDuckGo."""
    from foxpilot.search import format_results, search_duckduckgo

    with browser(mode=_MODE) as driver:
        results = search_duckduckgo(driver, query)
        typer.echo(format_results(results))


@app.command(name="click")
def cmd_click(
    description: str = typer.Argument(..., help="Visible text, label, or placeholder."),
    role: Optional[str] = typer.Option(None, "--role", "-r", help="Filter by ARIA role."),
    tag: Optional[str] = typer.Option(None, "--tag", "-t", help="Filter by HTML tag."),
):
    """Click an element by visible text."""
    with browser(mode=_MODE) as driver:
        el = find_element(driver, description, role=role, tag=tag)
        if not el:
            typer.echo(f"✗ no element found matching '{description}'")
            raise typer.Exit(1)
        desc = describe_element(el)
        el.click()
        time.sleep(0.8)
        typer.echo(feedback(driver, f"✓ clicked {desc}"))


@app.command(name="fill")
def cmd_fill(
    description: str = typer.Argument(..., help="Input label or placeholder."),
    value: str = typer.Argument(..., help="Text to type."),
    submit: bool = typer.Option(False, "--submit", "-s", help="Press Enter after."),
):
    """Fill a text input found by label or placeholder."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys

    with browser(mode=_MODE) as driver:
        el = find_element(driver, description)
        if not el:
            # Fallback: first visible input/textarea
            inputs = driver.find_elements(
                By.CSS_SELECTOR, "input:not([type=hidden]), textarea"
            )
            visible = [e for e in inputs if e.is_displayed()]
            if not visible:
                typer.echo(f"✗ no input found for '{description}'")
                raise typer.Exit(1)
            el = visible[0]

        desc = describe_element(el)
        el.clear()
        el.send_keys(value)

        if submit:
            el.send_keys(Keys.RETURN)
            time.sleep(0.8)
            typer.echo(feedback(driver, f"✓ filled {desc} + submitted"))
        else:
            typer.echo(feedback(driver, f"✓ filled {desc} with '{value}'"))


@app.command(name="select")
def cmd_select(
    description: str = typer.Argument(..., help="Dropdown label or name."),
    value: str = typer.Argument(..., help="Option text or value to select."),
):
    """Select a dropdown option."""
    from selenium.webdriver.support.ui import Select

    with browser(mode=_MODE) as driver:
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

    with browser(mode=_MODE) as driver:
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
    with browser(mode=_MODE) as driver:
        driver.back()
        time.sleep(0.8)
        typer.echo(feedback(driver, "✓ back"))


@app.command(name="forward")
def cmd_forward():
    """Navigate forward."""
    with browser(mode=_MODE) as driver:
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
        "enter": Keys.RETURN, "tab": Keys.TAB, "escape": Keys.ESCAPE,
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

    with browser(mode=_MODE) as driver:
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
    with browser(mode=_MODE) as driver:
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
    with browser(mode=_MODE) as driver:
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
    with browser(mode=_MODE) as driver:
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
    with browser(mode=_MODE) as driver:
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
    with browser(mode=_MODE) as driver:
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
    with browser(mode=_MODE) as driver:
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
    with browser(mode=_MODE) as driver:
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
# Escape hatches
# ---------------------------------------------------------------------------

@app.command(name="js")
def cmd_js(
    expr: str = typer.Argument(..., help="JavaScript expression to evaluate."),
):
    """Evaluate JavaScript in the page context."""
    with browser(mode=_MODE) as driver:
        result = driver.execute_script(f"return {expr};")
        typer.echo(f"✓ {result}")


@app.command(name="html")
def cmd_html(
    selector: Optional[str] = typer.Argument(None, help="CSS selector (default: full body)."),
):
    """Extract raw HTML from page or element."""
    from selenium.webdriver.common.by import By

    with browser(mode=_MODE) as driver:
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

    with browser(mode=_MODE) as driver:
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

    with browser(mode=_MODE) as driver:
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
    app()
