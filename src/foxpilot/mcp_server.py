"""foxpilot.mcp_server — MCP stdio server for Claude Code.

Each tool mirrors the CLI command with the same name and semantics.

All tools accept:
    mode    — "claude" (default), "zen", or "headless".
              "claude" uses a dedicated Zen profile, hidden in a Hyprland
              special workspace so it does not steal the user's screen.
              "zen" attaches to the user's running Zen instance (shares tabs).
              "headless" launches an ephemeral Firefox with no session.
    visible — only meaningful for mode="claude". When False (default) the
              window stays in the special:claude scratchpad. Set True to
              bring it onto the user's active workspace.

Lifecycle tools (`show`, `hide`, `status`, `login`) manage the dedicated
claude profile without performing browser actions.

Start with: foxpilot mcp
"""

import json as jsonlib
import time
from dataclasses import asdict
from typing import Optional

from mcp.server.fastmcp import FastMCP

from foxpilot.actions import click_action, fill_action
from foxpilot.core import (
    browser,
    burst_screenshots,
    claude_hide,
    claude_show,
    claude_status,
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
from foxpilot.search import format_results, search_duckduckgo
from foxpilot.evidence import create_evidence_bundle
from foxpilot.mission import create_mission
from foxpilot.page_brain import understand_page
from foxpilot.plugins import discover_plugins
from foxpilot.qa import build_qa_report

mcp = FastMCP("foxpilot")


@mcp.tool()
def plugins_list() -> str:
    """List loaded Foxpilot plugins as JSON."""
    registry = discover_plugins()
    return jsonlib.dumps(
        [
            {
                "name": plugin.name,
                "source": plugin.source,
                "help": plugin.help,
                "docs": str(plugin.docs_path or ""),
                "auth": plugin.auth_notes or "",
                "modes": list(plugin.browser_modes),
            }
            for plugin in registry.list()
        ],
        indent=2,
    )


@mcp.tool()
def evidence_bundle(
    output_dir: str,
    command: str = "",
    plugin: str = "",
    mode: str = "claude",
    visible: bool = False,
) -> str:
    """Capture current page state into an evidence bundle and return JSON metadata."""
    with browser(mode=mode, visible=visible) as driver:
        bundle = create_evidence_bundle(
            driver,
            output_dir,
            command=command,
            plugin=plugin,
            mode=mode,
        )
    return jsonlib.dumps(bundle, indent=2)


@mcp.tool()
def page_understand(mode: str = "claude", visible: bool = False, limit: int = 100) -> str:
    """Return an agent-friendly JSON map of the current page."""
    with browser(mode=mode, visible=visible) as driver:
        return jsonlib.dumps(understand_page(driver, limit=limit), indent=2)


@mcp.tool()
def mission_run(task: str, root: str = "") -> str:
    """Create a planned mission state file and return it as JSON."""
    state = create_mission(task, root=root or None)
    return jsonlib.dumps(asdict(state), indent=2)


@mcp.tool()
def qa_run(
    target_url: str,
    output_dir: str = "/tmp/foxpilot-qa",
    mode: str = "claude",
    visible: bool = False,
) -> str:
    """Capture a basic visual QA report for a URL and return JSON."""
    with browser(mode=mode, visible=visible) as driver:
        report = build_qa_report(driver, target_url, output_dir)
    return jsonlib.dumps(report, indent=2)


# ---------------------------------------------------------------------------
# Observation tools
# ---------------------------------------------------------------------------

@mcp.tool()
def tabs() -> str:
    """List all open tabs in the user's Zen browser.
    Requires Zen running with --marionette.
    """
    try:
        tab_list = list_tabs()
    except RuntimeError as e:
        return f"✗ {e}"

    if not tab_list:
        return "(no tabs found)"

    lines = []
    for i, tab in enumerate(tab_list):
        marker = ">" if tab.get("active") else " "
        lines.append(f"{marker}[{i}] {tab.get('title', '(no title)')}")
        lines.append(f"     {tab.get('url', '')}")
    return "\n".join(lines)


@mcp.tool()
def read(selector: str = "", mode: str = "claude", visible: bool = False) -> str:
    """Extract main readable content from the current page.

    Args:
        selector: Optional CSS selector to scope extraction to a specific element.
        mode: "headless" (default) or "zen" to read from user's browser.
    """
    with browser(mode=mode, visible=visible) as driver:
        text = read_page(driver, selector or None, max_chars=4000)
        return f"[{driver.title}]\n{driver.current_url}\n{'-'*60}\n{text}"


@mcp.tool()
def screenshot(path: str = "/tmp/foxpilot-snap.png", selector: str = "", mode: str = "claude", visible: bool = False) -> str:
    """Take a screenshot and save to disk.

    Args:
        path: Output file path (default: /tmp/foxpilot-snap.png).
        selector: Optional CSS selector to screenshot a specific element.
        mode: "headless" or "zen".

    Returns the saved path so you can read it with the Read tool.
    """
    from pathlib import Path
    from selenium.webdriver.common.by import By

    out = Path(path)
    with browser(mode=mode, visible=visible) as driver:
        if selector:
            try:
                el = driver.find_element(By.CSS_SELECTOR, selector)
                el.screenshot(str(out))
            except Exception as e:
                return f"✗ selector '{selector}' not found: {e}"
        else:
            driver.save_screenshot(str(out))

        size_kb = out.stat().st_size / 1024
        return (
            f"✓ screenshot saved: {out} ({size_kb:.0f}KB)\n"
            f"title: {driver.title}\n"
            f"url: {driver.current_url}\n"
            f"(use Read tool on the path to view it)"
        )


@mcp.tool()
def url(mode: str = "claude", visible: bool = False) -> str:
    """Get the current page URL and title.

    Args:
        mode: "headless" or "zen".
    """
    with browser(mode=mode, visible=visible) as driver:
        return f"{driver.title}\n{driver.current_url}"


@mcp.tool()
def find(text: str, mode: str = "claude", visible: bool = False) -> str:
    """Find visible elements on the page matching text.

    Args:
        text: Text to search for in visible elements (content, labels, placeholders).
        mode: "headless" or "zen".
    """
    from selenium.webdriver.common.by import By

    with browser(mode=mode, visible=visible) as driver:
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
            return f"✗ no visible elements matching '{text}'"

        lines = [f"✓ {len(results)} element(s) matching '{text}':"]
        for i, el in enumerate(results[:20]):
            lines.append(f"  [{i}] {describe_element(el)}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Action tools
# ---------------------------------------------------------------------------

@mcp.tool()
def go(target_url: str, mode: str = "claude", visible: bool = False) -> str:
    """Navigate to a URL.

    Args:
        target_url: URL to navigate to.
        mode: "headless" or "zen".

    Returns current page state after navigation.
    """
    with browser(mode=mode, visible=visible) as driver:
        driver.get(target_url)
        time.sleep(1)
        return feedback(driver, f"✓ navigated to {target_url}")


@mcp.tool()
def search(query: str, mode: str = "claude", visible: bool = False) -> str:
    """Search the web via DuckDuckGo and return structured results.

    Args:
        query: Search query string.
        mode: "headless" (default) or "zen".
    """
    with browser(mode=mode, visible=visible) as driver:
        results = search_duckduckgo(driver, query)
        return format_results(results)


@mcp.tool()
def click(description: str, role: str = "", tag: str = "", mode: str = "claude", visible: bool = False) -> str:
    """Click an element found by visible text, aria-label, or placeholder.

    Args:
        description: Visible text, aria-label, or placeholder of the element to click.
        role: Optional ARIA role filter (e.g. "button", "link").
        tag: Optional HTML tag filter (e.g. "button", "a").
        mode: "headless" or "zen".

    Returns what was clicked and current page state.
    """
    with browser(mode=mode, visible=visible) as driver:
        return click_action(
            driver,
            description,
            role=role or None,
            tag=tag or None,
        ).to_text()


@mcp.tool()
def fill(description: str, value: str, submit: bool = False, mode: str = "claude", visible: bool = False) -> str:
    """Fill a text input found by label or placeholder.

    Args:
        description: Label text, aria-label, or placeholder of the input.
        value: Text to type into the input.
        submit: If True, press Enter after filling.
        mode: "headless" or "zen".
    """
    with browser(mode=mode, visible=visible) as driver:
        return fill_action(driver, description, value, submit=submit).to_text()


@mcp.tool()
def select(description: str, value: str, mode: str = "claude", visible: bool = False) -> str:
    """Select a dropdown option by label text.

    Args:
        description: Label or visible text of the dropdown.
        value: Option text or value to select.
        mode: "headless" or "zen".
    """
    from selenium.webdriver.support.ui import Select as SeleniumSelect

    with browser(mode=mode, visible=visible) as driver:
        el = find_element(driver, description, tag="select")
        if not el:
            return f"✗ no dropdown found for '{description}'"

        sel = SeleniumSelect(el)
        try:
            sel.select_by_visible_text(value)
        except Exception:
            try:
                sel.select_by_value(value)
            except Exception:
                return f"✗ option '{value}' not found in dropdown"

        return feedback(driver, f"✓ selected '{value}' in {describe_element(el)}")


@mcp.tool()
def scroll(y: int = 600, to: str = "", mode: str = "claude", visible: bool = False) -> str:
    """Scroll the page.

    Args:
        y: Pixels to scroll (negative = up). Default 600.
        to: CSS selector to scroll into view (overrides y).
        mode: "headless" or "zen".
    """
    from selenium.webdriver.common.by import By

    with browser(mode=mode, visible=visible) as driver:
        if to:
            try:
                el = driver.find_element(By.CSS_SELECTOR, to)
                driver.execute_script(
                    "arguments[0].scrollIntoView({behavior: 'smooth'});", el
                )
                time.sleep(0.5)
                return feedback(driver, f"✓ scrolled to '{to}'")
            except Exception:
                return f"✗ selector '{to}' not found"
        else:
            driver.execute_script(f"window.scrollBy(0, {y});")
            time.sleep(0.5)
            pos = driver.execute_script("return window.scrollY;")
            return feedback(driver, f"✓ scrolled {y}px (position: {pos}px)")


@mcp.tool()
def back(mode: str = "claude", visible: bool = False) -> str:
    """Navigate back in browser history.

    Args:
        mode: "headless" or "zen".
    """
    with browser(mode=mode, visible=visible) as driver:
        driver.back()
        time.sleep(0.8)
        return feedback(driver, "✓ back")


@mcp.tool()
def forward(mode: str = "claude", visible: bool = False) -> str:
    """Navigate forward in browser history.

    Args:
        mode: "headless" or "zen".
    """
    with browser(mode=mode, visible=visible) as driver:
        driver.forward()
        time.sleep(0.8)
        return feedback(driver, "✓ forward")


@mcp.tool()
def key(name: str, focus: str = "", mode: str = "claude", visible: bool = False) -> str:
    """Press a keyboard key.

    Args:
        name: Key name: enter, tab, escape, space, backspace, delete,
              arrowup, arrowdown, arrowleft, arrowright, home, end, pageup, pagedown.
        focus: Optional CSS selector to focus before pressing the key.
        mode: "headless" or "zen".
    """
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
        return f"✗ unknown key '{name}'. Supported: {', '.join(KEY_MAP)}"

    with browser(mode=mode, visible=visible) as driver:
        if focus:
            try:
                el = driver.find_element(By.CSS_SELECTOR, focus)
                el.click()
            except Exception:
                return f"✗ selector '{focus}' not found"

        active = driver.switch_to.active_element
        active.send_keys(key_val)
        time.sleep(0.5)
        return feedback(driver, f"✓ pressed {name}")


@mcp.tool()
def tab_switch(target: str) -> str:
    """Switch to a tab in the user's Zen browser by index or URL/title substring.
    Operates on the real browser UI (requires zen mode connection).

    Args:
        target: Tab index (number) or URL/title substring to match.
    """
    try:
        t = switch_tab(target)
        return f"✓ switched to {t.get('title', '') or t.get('url', '')}"
    except RuntimeError as e:
        return f"✗ {e}"


@mcp.tool()
def new_tab(target_url: str = "", mode: str = "claude", visible: bool = False) -> str:
    """Open a new browser tab.

    Args:
        target_url: URL to open in the new tab (optional).
        mode: "headless" or "zen".
    """
    with browser(mode=mode, visible=visible) as driver:
        driver.execute_script("window.open('', '_blank');")
        handles = driver.window_handles
        driver.switch_to.window(handles[-1])
        if target_url:
            driver.get(target_url)
            time.sleep(1)
        return feedback(driver, "✓ opened new tab")


@mcp.tool()
def close_tab(index: int = -1, mode: str = "claude", visible: bool = False) -> str:
    """Close a browser tab.

    Args:
        index: Tab index to close (-1 = current tab).
        mode: "headless" or "zen".
    """
    with browser(mode=mode, visible=visible) as driver:
        if index >= 0:
            handles = driver.window_handles
            if index < len(handles):
                driver.switch_to.window(handles[index])
            else:
                return f"✗ index {index} out of range"
        title = driver.title
        driver.close()
        return f"✓ closed: {title}"


# ---------------------------------------------------------------------------
# Design inspection
# ---------------------------------------------------------------------------

@mcp.tool()
def styles(selector: str = "", mode: str = "claude", visible: bool = False) -> str:
    """Extract computed styles and CSS custom properties from the page.

    Args:
        selector: CSS selector of element to inspect (default: body).
        mode: "headless" or "zen".

    Returns computed styles, CSS variables, and colors found on the page.
    """
    with browser(mode=mode, visible=visible) as driver:
        data = extract_styles(driver, selector or None)
        lines = [f"[{data['element']}]", driver.current_url]

        if data["styles"]:
            lines.append("\n── computed styles ──")
            for k, v in data["styles"].items():
                lines.append(f"  {k:<28} {v}")

        if data["cssVars"]:
            lines.append(f"\n── css variables ({len(data['cssVars'])}) ──")
            for k, v in list(data["cssVars"].items())[:60]:
                lines.append(f"  {k:<40} {v}")

        if data["colors"]:
            lines.append(f"\n── colors on page ({len(data['colors'])}) ──")
            for c in data["colors"]:
                lines.append(f"  {c}")

        return "\n".join(lines)


@mcp.tool()
def assets(mode: str = "claude", visible: bool = False) -> str:
    """Extract all assets from the page: images, fonts, stylesheets, background images.

    Args:
        mode: "headless" or "zen".

    Returns a structured list of all assets found on the current page.
    """
    with browser(mode=mode, visible=visible) as driver:
        data = extract_assets(driver)
        lines = [driver.current_url]

        lines.append(f"\n── images ({len(data['images'])}) ──")
        for img in data["images"][:30]:
            dim = f"{img['width']}×{img['height']}" if img["width"] else "?"
            alt = f' "{img["alt"]}"' if img["alt"] else ""
            lines.append(f"  {dim:<12} {img['src']}{alt}")

        lines.append(f"\n── font families ({len(data['fontFamilies'])}) ──")
        for f in data["fontFamilies"]:
            lines.append(f"  {f}")

        if data["fonts"]:
            lines.append(f"\n── loaded fonts ({len(data['fonts'])}) ──")
            for f in data["fonts"]:
                lines.append(f"  {f['family']:<30} weight={f['weight']} style={f['style']} [{f['status']}]")

        if data["stylesheets"]:
            lines.append(f"\n── stylesheets ({len(data['stylesheets'])}) ──")
            for s in data["stylesheets"]:
                lines.append(f"  {s}")

        if data["favicon"]:
            lines.append(f"\n── favicon ──\n  {data['favicon']}")

        if data["backgroundImages"]:
            lines.append(f"\n── background images ({len(data['backgroundImages'])}) ──")
            for b in data["backgroundImages"]:
                lines.append(f"  {b}")

        if data["inlineSvgs"]:
            lines.append(f"\n── inline svgs ({len(data['inlineSvgs'])}) ──")
            for s in data["inlineSvgs"]:
                lines.append(f"  {s}")

        return "\n".join(lines)


@mcp.tool()
def fullpage(path: str = "/tmp/foxpilot-full.png", mode: str = "claude", visible: bool = False) -> str:
    """Take a full-page screenshot capturing the entire scroll height.

    Args:
        path: Output file path (default: /tmp/foxpilot-full.png).
        mode: "headless" or "zen".

    Returns the saved path so you can read it with the Read tool.
    """
    with browser(mode=mode, visible=visible) as driver:
        out, size_kb = fullpage_screenshot(driver, path)
        return (
            f"✓ fullpage screenshot: {out} ({size_kb:.0f}KB)\n"
            f"title: {driver.title}\n"
            f"url: {driver.current_url}\n"
            f"(use Read tool on the path to view it)"
        )


@mcp.tool()
def burst(
    target_url: str = "",
    count: int = 10,
    interval_ms: int = 500,
    out_dir: str = "/tmp/foxpilot-burst",
    warmup_s: float = 1.0,
    mode: str = "claude",
    visible: bool = False,
) -> str:
    """Take a burst of N screenshots spaced `interval_ms` apart.

    Produces PNG frames the agent's Read tool can view directly — use this
    when you want an agent-readable time-lapse. Prefer over `record` if the
    frames need to go to an agent: Read tool doesn't eat video.

    Args:
        target_url: URL to navigate to first (empty to use current page).
        count: Number of frames (default 10).
        interval_ms: Milliseconds between frames (default 500).
        out_dir: Output directory for frames (default /tmp/foxpilot-burst).
        warmup_s: Seconds to wait after navigate before first frame.
        mode: "headless" or "zen".
    """
    with browser(mode=mode, visible=visible) as driver:
        if target_url:
            driver.get(target_url)
            time.sleep(warmup_s)
        paths = burst_screenshots(
            driver, out_dir, count=count, interval_ms=interval_ms
        )
        return (
            f"✓ burst: {len(paths)} frames in {out_dir}/\n"
            f"first: {paths[0]}\n"
            f"last:  {paths[-1]}\n"
            f"title: {driver.title}\n"
            f"url: {driver.current_url}\n"
            f"(use Read tool on individual frame paths to view)"
        )


@mcp.tool()
def record(
    target_url: str = "",
    duration_s: float = 5.0,
    fps: int = 5,
    out_path: str = "/tmp/foxpilot-clip.mp4",
    warmup_s: float = 1.0,
    keep_frames: bool = False,
    mode: str = "claude",
    visible: bool = False,
) -> str:
    """Record a video clip by frame-bursting, then stitching with ffmpeg.

    Agents CANNOT read video files — use `burst` instead if the frames need
    to be readable. Call `record` only for human-debug clips.

    Args:
        target_url: URL to navigate to first (empty to use current page).
        duration_s: Recording length in seconds (default 5).
        fps: Frames per second (default 5).
        out_path: Output video file (.mp4/.webm/.mkv/.gif).
        warmup_s: Seconds to wait after navigate before recording.
        keep_frames: If True, keep raw PNG frames alongside the video.
        mode: "headless" or "zen".
    """
    with browser(mode=mode, visible=visible) as driver:
        if target_url:
            driver.get(target_url)
            time.sleep(warmup_s)
        try:
            path, n = record_video(
                driver,
                out_path,
                duration_s=duration_s,
                fps=fps,
                cleanup=not keep_frames,
            )
        except RuntimeError as e:
            return f"✗ {e}"
        return (
            f"✓ recorded: {path} ({n} frames @ {fps}fps, {duration_s}s)\n"
            f"title: {driver.title}\n"
            f"url: {driver.current_url}\n"
            f"(video is for human viewing — use `burst` for agent-readable frames)"
        )


# ---------------------------------------------------------------------------
# Escape hatches
# ---------------------------------------------------------------------------

@mcp.tool()
def js(expression: str, mode: str = "claude", visible: bool = False) -> str:
    """Evaluate JavaScript in the page and return the result.

    Args:
        expression: JavaScript expression (will be wrapped in `return ...`).
        mode: "headless" or "zen".
    """
    with browser(mode=mode, visible=visible) as driver:
        result = driver.execute_script(f"return {expression};")
        return f"✓ {result}"


@mcp.tool()
def html(selector: str = "", mode: str = "claude", visible: bool = False) -> str:
    """Extract raw HTML from the page or a specific element.

    Args:
        selector: CSS selector (default: full body HTML, truncated to 8000 chars).
        mode: "headless" or "zen".
    """
    from selenium.webdriver.common.by import By

    with browser(mode=mode, visible=visible) as driver:
        if selector:
            try:
                el = driver.find_element(By.CSS_SELECTOR, selector)
                return el.get_attribute("outerHTML") or ""
            except Exception:
                return f"✗ selector '{selector}' not found"
        body = driver.find_element(By.TAG_NAME, "body")
        content = body.get_attribute("innerHTML") or ""
        if len(content) > 8000:
            content = content[:8000] + "\n... [truncated]"
        return content


@mcp.tool()
def css_click(selector: str, mode: str = "claude", visible: bool = False) -> str:
    """Click an element by CSS selector (escape hatch when text matching fails).

    Args:
        selector: CSS selector of the element to click.
        mode: "headless" or "zen".
    """
    from selenium.webdriver.common.by import By

    with browser(mode=mode, visible=visible) as driver:
        try:
            el = driver.find_element(By.CSS_SELECTOR, selector)
            el.click()
            time.sleep(0.8)
            return feedback(driver, f"✓ clicked '{selector}'")
        except Exception as e:
            return f"✗ {e}"


@mcp.tool()
def css_fill(selector: str, value: str, mode: str = "claude", visible: bool = False) -> str:
    """Fill an input by CSS selector (escape hatch when text matching fails).

    Args:
        selector: CSS selector of the input element.
        value: Text to type.
        mode: "headless" or "zen".
    """
    from selenium.webdriver.common.by import By

    with browser(mode=mode, visible=visible) as driver:
        try:
            el = driver.find_element(By.CSS_SELECTOR, selector)
            el.clear()
            el.send_keys(value)
            return feedback(driver, f"✓ filled '{selector}' with '{value}'")
        except Exception as e:
            return f"✗ {e}"


# ---------------------------------------------------------------------------
# Claude profile lifecycle (Hyprland scratchpad)
# ---------------------------------------------------------------------------

@mcp.tool()
def show() -> str:
    """Bring the claude-profile Zen window onto the user's active workspace.

    Use only when the user explicitly wants to see the agent operate the
    browser (e.g. they ask to demo a flow, or solve a CAPTCHA). Otherwise
    leave the browser hidden — it works fine off-screen.
    """
    result = claude_show()
    status = result["status"]
    if status == "not_running":
        return "x claude window not running"
    if status == "already_visible":
        return "OK claude window already visible"
    return "OK claude window -> active workspace"


@mcp.tool()
def hide() -> str:
    """Send the claude-profile Zen window to the special:claude scratchpad.

    Call this after a `show` once the user has seen what they wanted.
    """
    result = claude_hide()
    status = result["status"]
    if status == "not_running":
        return "x claude window not running"
    if status == "already_hidden":
        return "OK claude window already hidden"
    return "OK claude window -> special:claude (hidden)"


@mcp.tool()
def status() -> str:
    """Report claude-profile state — running, visibility, profile dir, port."""
    s = claude_status()
    return "\n".join(f"{k:<18} {v}" for k, v in s.items())


@mcp.tool()
def login(target_url: str = "") -> str:
    """Open the claude profile visibly so the USER can log into a site once.

    Cookies persist in the profile dir, so subsequent hidden agent commands
    reuse the session. Use this when the agent needs an authenticated session
    on a site for the first time. After this, run `hide` (or just leave it —
    next agent command will not move the window unless asked).

    Args:
        target_url: Site URL to open for login (default: about:preferences).
    """
    with browser(mode="claude", visible=True) as driver:
        driver.get(target_url or "about:preferences")
    return (
        "✓ claude profile open and visible. Hand off to the user — they should "
        "log in, then call `hide` (or do nothing; the window stays put)."
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def serve():
    """Start the MCP server on stdio transport."""
    mcp.run(transport="stdio")
