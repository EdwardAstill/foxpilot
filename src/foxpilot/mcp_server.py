"""foxpilot.mcp_server — MCP stdio server for Claude Code.

Each tool mirrors the CLI command with the same name and semantics.
All tools accept an optional `mode` parameter: "headless" (default) or "zen".

Start with: foxpilot mcp
Configure in Claude Code settings:
    {
      "mcpServers": {
        "foxpilot": {
          "command": "foxpilot",
          "args": ["mcp"],
          "type": "stdio"
        }
      }
    }
"""

import time
from typing import Optional

from mcp.server.fastmcp import FastMCP

from foxpilot.core import (
    activate_tab,
    browser,
    describe_element,
    extract_assets,
    extract_styles,
    feedback,
    find_element,
    fullpage_screenshot,
    list_tabs,
    read_page,
)
from foxpilot.search import format_results, search_duckduckgo

mcp = FastMCP("foxpilot")


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
def read(selector: str = "", mode: str = "headless") -> str:
    """Extract main readable content from the current page.

    Args:
        selector: Optional CSS selector to scope extraction to a specific element.
        mode: "headless" (default) or "zen" to read from user's browser.
    """
    with browser(mode=mode) as driver:
        text = read_page(driver, selector or None, max_chars=4000)
        return f"[{driver.title}]\n{driver.current_url}\n{'-'*60}\n{text}"


@mcp.tool()
def screenshot(path: str = "/tmp/foxpilot-snap.png", selector: str = "", mode: str = "headless") -> str:
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
    with browser(mode=mode) as driver:
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
def url(mode: str = "headless") -> str:
    """Get the current page URL and title.

    Args:
        mode: "headless" or "zen".
    """
    with browser(mode=mode) as driver:
        return f"{driver.title}\n{driver.current_url}"


@mcp.tool()
def find(text: str, mode: str = "headless") -> str:
    """Find visible elements on the page matching text.

    Args:
        text: Text to search for in visible elements (content, labels, placeholders).
        mode: "headless" or "zen".
    """
    from selenium.webdriver.common.by import By

    with browser(mode=mode) as driver:
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
            return f"✗ no visible elements matching '{text}'"

        lines = [f"✓ {len(results)} element(s) matching '{text}':"]
        for i, el in enumerate(results[:20]):
            lines.append(f"  [{i}] {describe_element(el)}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Action tools
# ---------------------------------------------------------------------------

@mcp.tool()
def go(target_url: str, mode: str = "headless") -> str:
    """Navigate to a URL.

    Args:
        target_url: URL to navigate to.
        mode: "headless" or "zen".

    Returns current page state after navigation.
    """
    with browser(mode=mode) as driver:
        driver.get(target_url)
        time.sleep(1)
        return feedback(driver, f"✓ navigated to {target_url}")


@mcp.tool()
def search(query: str, mode: str = "headless") -> str:
    """Search the web via DuckDuckGo and return structured results.

    Args:
        query: Search query string.
        mode: "headless" (default) or "zen".
    """
    with browser(mode=mode) as driver:
        results = search_duckduckgo(driver, query)
        return format_results(results)


@mcp.tool()
def click(description: str, role: str = "", tag: str = "", mode: str = "headless") -> str:
    """Click an element found by visible text, aria-label, or placeholder.

    Args:
        description: Visible text, aria-label, or placeholder of the element to click.
        role: Optional ARIA role filter (e.g. "button", "link").
        tag: Optional HTML tag filter (e.g. "button", "a").
        mode: "headless" or "zen".

    Returns what was clicked and current page state.
    """
    with browser(mode=mode) as driver:
        el = find_element(driver, description, role=role or None, tag=tag or None)
        if not el:
            return f"✗ no element found matching '{description}'"
        desc = describe_element(el)
        el.click()
        time.sleep(0.8)
        return feedback(driver, f"✓ clicked {desc}")


@mcp.tool()
def fill(description: str, value: str, submit: bool = False, mode: str = "headless") -> str:
    """Fill a text input found by label or placeholder.

    Args:
        description: Label text, aria-label, or placeholder of the input.
        value: Text to type into the input.
        submit: If True, press Enter after filling.
        mode: "headless" or "zen".
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys

    with browser(mode=mode) as driver:
        el = find_element(driver, description)
        if not el:
            inputs = driver.find_elements(
                By.CSS_SELECTOR, "input:not([type=hidden]), textarea"
            )
            visible = [e for e in inputs if e.is_displayed()]
            if not visible:
                return f"✗ no input found for '{description}'"
            el = visible[0]

        desc = describe_element(el)
        el.clear()
        el.send_keys(value)

        if submit:
            el.send_keys(Keys.RETURN)
            time.sleep(0.8)
            return feedback(driver, f"✓ filled {desc} + submitted")
        return feedback(driver, f"✓ filled {desc} with '{value}'")


@mcp.tool()
def select(description: str, value: str, mode: str = "headless") -> str:
    """Select a dropdown option by label text.

    Args:
        description: Label or visible text of the dropdown.
        value: Option text or value to select.
        mode: "headless" or "zen".
    """
    from selenium.webdriver.support.ui import Select as SeleniumSelect

    with browser(mode=mode) as driver:
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
def scroll(y: int = 600, to: str = "", mode: str = "headless") -> str:
    """Scroll the page.

    Args:
        y: Pixels to scroll (negative = up). Default 600.
        to: CSS selector to scroll into view (overrides y).
        mode: "headless" or "zen".
    """
    from selenium.webdriver.common.by import By

    with browser(mode=mode) as driver:
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
def back(mode: str = "headless") -> str:
    """Navigate back in browser history.

    Args:
        mode: "headless" or "zen".
    """
    with browser(mode=mode) as driver:
        driver.back()
        time.sleep(0.8)
        return feedback(driver, "✓ back")


@mcp.tool()
def forward(mode: str = "headless") -> str:
    """Navigate forward in browser history.

    Args:
        mode: "headless" or "zen".
    """
    with browser(mode=mode) as driver:
        driver.forward()
        time.sleep(0.8)
        return feedback(driver, "✓ forward")


@mcp.tool()
def key(name: str, focus: str = "", mode: str = "headless") -> str:
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

    with browser(mode=mode) as driver:
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
        tab_list = list_tabs()
    except RuntimeError as e:
        return f"✗ {e}"

    try:
        idx = int(target)
        if 0 <= idx < len(tab_list):
            t = tab_list[idx]
            activate_tab(t["id"])
            return f"✓ switched to [{idx}] {t.get('title', '')}"
        return f"✗ index {idx} out of range (0-{len(tab_list)-1})"
    except ValueError:
        pass

    tl = target.lower()
    for i, t in enumerate(tab_list):
        if tl in t.get("title", "").lower() or tl in t.get("url", "").lower():
            activate_tab(t["id"])
            return f"✓ switched to [{i}] {t.get('title', '')} (matched '{target}')"

    return f"✗ no tab matching '{target}'"


@mcp.tool()
def new_tab(target_url: str = "", mode: str = "headless") -> str:
    """Open a new browser tab.

    Args:
        target_url: URL to open in the new tab (optional).
        mode: "headless" or "zen".
    """
    with browser(mode=mode) as driver:
        driver.execute_script("window.open('', '_blank');")
        handles = driver.window_handles
        driver.switch_to.window(handles[-1])
        if target_url:
            driver.get(target_url)
            time.sleep(1)
        return feedback(driver, "✓ opened new tab")


@mcp.tool()
def close_tab(index: int = -1, mode: str = "headless") -> str:
    """Close a browser tab.

    Args:
        index: Tab index to close (-1 = current tab).
        mode: "headless" or "zen".
    """
    with browser(mode=mode) as driver:
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
def styles(selector: str = "", mode: str = "zen") -> str:
    """Extract computed styles and CSS custom properties from the page.

    Args:
        selector: CSS selector of element to inspect (default: body).
        mode: "headless" or "zen".

    Returns computed styles, CSS variables, and colors found on the page.
    """
    with browser(mode=mode) as driver:
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
def assets(mode: str = "zen") -> str:
    """Extract all assets from the page: images, fonts, stylesheets, background images.

    Args:
        mode: "headless" or "zen".

    Returns a structured list of all assets found on the current page.
    """
    with browser(mode=mode) as driver:
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
def fullpage(path: str = "/tmp/foxpilot-full.png", mode: str = "zen") -> str:
    """Take a full-page screenshot capturing the entire scroll height.

    Args:
        path: Output file path (default: /tmp/foxpilot-full.png).
        mode: "headless" or "zen".

    Returns the saved path so you can read it with the Read tool.
    """
    with browser(mode=mode) as driver:
        out, size_kb = fullpage_screenshot(driver, path)
        return (
            f"✓ fullpage screenshot: {out} ({size_kb:.0f}KB)\n"
            f"title: {driver.title}\n"
            f"url: {driver.current_url}\n"
            f"(use Read tool on the path to view it)"
        )


# ---------------------------------------------------------------------------
# Escape hatches
# ---------------------------------------------------------------------------

@mcp.tool()
def js(expression: str, mode: str = "headless") -> str:
    """Evaluate JavaScript in the page and return the result.

    Args:
        expression: JavaScript expression (will be wrapped in `return ...`).
        mode: "headless" or "zen".
    """
    with browser(mode=mode) as driver:
        result = driver.execute_script(f"return {expression};")
        return f"✓ {result}"


@mcp.tool()
def html(selector: str = "", mode: str = "headless") -> str:
    """Extract raw HTML from the page or a specific element.

    Args:
        selector: CSS selector (default: full body HTML, truncated to 8000 chars).
        mode: "headless" or "zen".
    """
    from selenium.webdriver.common.by import By

    with browser(mode=mode) as driver:
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
def css_click(selector: str, mode: str = "headless") -> str:
    """Click an element by CSS selector (escape hatch when text matching fails).

    Args:
        selector: CSS selector of the element to click.
        mode: "headless" or "zen".
    """
    from selenium.webdriver.common.by import By

    with browser(mode=mode) as driver:
        try:
            el = driver.find_element(By.CSS_SELECTOR, selector)
            el.click()
            time.sleep(0.8)
            return feedback(driver, f"✓ clicked '{selector}'")
        except Exception as e:
            return f"✗ {e}"


@mcp.tool()
def css_fill(selector: str, value: str, mode: str = "headless") -> str:
    """Fill an input by CSS selector (escape hatch when text matching fails).

    Args:
        selector: CSS selector of the input element.
        value: Text to type.
        mode: "headless" or "zen".
    """
    from selenium.webdriver.common.by import By

    with browser(mode=mode) as driver:
        try:
            el = driver.find_element(By.CSS_SELECTOR, selector)
            el.clear()
            el.send_keys(value)
            return feedback(driver, f"✓ filled '{selector}' with '{value}'")
        except Exception as e:
            return f"✗ {e}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def serve():
    """Start the MCP server on stdio transport."""
    mcp.run(transport="stdio")
