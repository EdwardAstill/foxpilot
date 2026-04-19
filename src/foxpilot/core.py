"""foxpilot.core — browser connection and shared automation logic."""

from contextlib import contextmanager
from typing import Optional

MARIONETTE_PORT = 2828


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

ZEN_BINARY = "zen-browser"


def _marionette_listening() -> bool:
    """Return True if something is accepting connections on the Marionette port."""
    import socket
    try:
        with socket.create_connection(("127.0.0.1", MARIONETTE_PORT), timeout=1):
            return True
    except OSError:
        return False


def _zen_running() -> bool:
    """Return True if a zen-bin process exists."""
    import subprocess
    result = subprocess.run(["pgrep", "-f", "zen-bin"], capture_output=True)
    return result.returncode == 0


def _launch_zen_with_marionette() -> None:
    """Launch Zen in the background with --marionette and wait for port."""
    import subprocess
    import time
    import os

    env = os.environ.copy()
    if "DISPLAY" not in env:
        env["DISPLAY"] = ":0"

    subprocess.Popen(
        [ZEN_BINARY, "--marionette"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Wait up to 10s for Marionette to come up
    for _ in range(20):
        time.sleep(0.5)
        if _marionette_listening():
            return
    raise RuntimeError("Launched Zen but Marionette port never opened.")


def _get_driver_zen():
    """Connect to running Zen via geckodriver --connect-existing.

    If Zen is not running, launches it automatically with --marionette.
    If Zen is running but Marionette is not listening, raises a clear error.
    """
    import time
    from selenium import webdriver
    from selenium.webdriver.firefox.options import Options
    from selenium.webdriver.firefox.service import Service

    if not _marionette_listening():
        if _zen_running():
            # Zen running without Marionette — kill and relaunch with it
            # Zen saves session on exit and restores tabs on next launch
            import subprocess
            subprocess.run(["pkill", "zen-bin"], check=False)
            time.sleep(2)
        _launch_zen_with_marionette()
        time.sleep(1)  # give geckodriver a moment after port opens

    opts = Options()
    service = Service(
        service_args=[
            "--connect-existing",
            "--marionette-port", str(MARIONETTE_PORT),
        ]
    )
    try:
        driver = webdriver.Firefox(options=opts, service=service)
    except Exception as e:
        raise RuntimeError(
            f"Can't connect to Zen on Marionette port {MARIONETTE_PORT}. Error: {e}"
        ) from e

    # Suppress webdriver flag to reduce bot detection
    try:
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
    except Exception:
        pass

    return driver


def _get_driver_headless():
    """Launch a headless Firefox instance."""
    from selenium import webdriver
    from selenium.webdriver.firefox.options import Options

    opts = Options()
    opts.add_argument("--headless")
    try:
        driver = webdriver.Firefox(options=opts)
    except Exception as e:
        raise RuntimeError(f"Can't launch headless Firefox: {e}") from e

    return driver


@contextmanager
def browser(mode: str = "headless"):
    """Yield a WebDriver; close it on exit.

    mode="zen"      — connect to user's running Zen browser
    mode="headless" — launch ephemeral headless Firefox
    """
    driver = None
    try:
        if mode == "zen":
            driver = _get_driver_zen()
        else:
            driver = _get_driver_headless()
        yield driver
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Tab listing — no focus stealing via raw geckodriver HTTP API
# ---------------------------------------------------------------------------

def _switch_window_no_focus(driver, handle: str) -> None:
    """Switch geckodriver context to a window without raising it.

    Selenium's switch_to.window() always sends focus=true to Marionette which
    raises the target window. The geckodriver HTTP API accepts focus=false so
    we POST directly, bypassing Selenium.
    """
    import json as _json
    import urllib.request as _ureq
    url = f"{driver.service.service_url}/session/{driver.session_id}/window"
    body = _json.dumps({"handle": handle, "focus": False}).encode()
    req = _ureq.Request(url, data=body, method="POST",
                        headers={"Content-Type": "application/json"})
    _ureq.urlopen(req, timeout=5)


def list_tabs() -> list[dict]:
    """List all open tabs without stealing window focus."""
    driver = _get_driver_zen()
    try:
        try:
            active_handle = driver.current_window_handle
        except Exception:
            active_handle = None

        tabs = []
        for handle in driver.window_handles:
            try:
                _switch_window_no_focus(driver, handle)
                tabs.append({
                    "id": handle,
                    "title": driver.title,
                    "url": driver.current_url,
                    "active": handle == active_handle,
                })
            except Exception:
                continue

        if active_handle:
            try:
                _switch_window_no_focus(driver, active_handle)
            except Exception:
                pass

        return tabs
    finally:
        try:
            driver.quit()
        except Exception:
            pass


def activate_tab(tab_id: str) -> None:
    """Switch to a tab by window handle — intentionally raises the window."""
    driver = _get_driver_zen()
    try:
        driver.switch_to.window(tab_id)
    finally:
        try:
            driver.quit()
        except Exception:
            pass


def switch_tab(target: str) -> dict:
    """Find and switch to a tab by index or URL/title substring.

    Listing uses focus=false so iterating handles doesn't steal your window.
    The final switch uses focus=true since the user explicitly requested it.
    """
    driver = _get_driver_zen()
    try:
        try:
            active_handle = driver.current_window_handle
        except Exception:
            active_handle = None

        tabs = []
        for handle in driver.window_handles:
            try:
                _switch_window_no_focus(driver, handle)
                tabs.append({
                    "id": handle,
                    "title": driver.title,
                    "url": driver.current_url,
                })
            except Exception:
                continue

        target_tab = None
        try:
            idx = int(target)
            if 0 <= idx < len(tabs):
                target_tab = tabs[idx]
            else:
                raise RuntimeError(f"Index {idx} out of range (0–{len(tabs) - 1})")
        except ValueError:
            tl = target.lower()
            for tab in tabs:
                if tl in tab.get("title", "").lower() or tl in tab.get("url", "").lower():
                    target_tab = tab
                    break

        if not target_tab:
            raise RuntimeError(f"No tab matching '{target}'")

        driver.switch_to.window(target_tab["id"])
        return target_tab
    finally:
        try:
            driver.quit()
        except Exception:
            pass




# ---------------------------------------------------------------------------
# Design inspection
# ---------------------------------------------------------------------------

def extract_styles(driver, selector: Optional[str] = None) -> dict:
    """Extract computed styles and CSS custom properties from the page."""
    return driver.execute_script("""
        const sel = arguments[0];
        const el = sel ? (document.querySelector(sel) || document.body) : document.body;
        const cs = getComputedStyle(el);
        const PROPS = [
            'color', 'background-color', 'font-family', 'font-size', 'font-weight',
            'line-height', 'letter-spacing', 'text-transform', 'border-radius',
            'box-shadow', 'padding', 'margin', 'gap', 'display', 'border',
            'border-color', 'opacity', 'flex-direction', 'grid-template-columns'
        ];
        const styles = {};
        PROPS.forEach(p => {
            const v = cs.getPropertyValue(p);
            if (v && v !== 'none' && v !== 'normal' && v !== 'auto'
                && v !== '0px' && v !== 'rgba(0, 0, 0, 0)' && v !== '')
                styles[p] = v;
        });

        const cssVars = {};
        try {
            [...document.styleSheets].forEach(sheet => {
                try {
                    [...sheet.cssRules].forEach(rule => {
                        if (rule.selectorText === ':root') {
                            for (let i = 0; i < rule.style.length; i++) {
                                const name = rule.style[i];
                                if (name.startsWith('--'))
                                    cssVars[name] = rule.style.getPropertyValue(name).trim();
                            }
                        }
                    });
                } catch(e) {}
            });
        } catch(e) {}

        const colors = new Set();
        [...document.querySelectorAll('*')].slice(0, 300).forEach(e => {
            const s = getComputedStyle(e);
            ['color', 'background-color', 'border-color'].forEach(p => {
                const v = s.getPropertyValue(p);
                if (v && v !== 'rgba(0, 0, 0, 0)') colors.add(v);
            });
        });

        return { element: sel || 'body', styles, cssVars, colors: [...colors].slice(0, 40) };
    """, selector)


def extract_assets(driver) -> dict:
    """Extract images, fonts, stylesheets, and background images from the page."""
    return driver.execute_script("""
        const images = [...document.images]
            .map(i => ({ src: i.src, alt: i.alt || '', width: i.naturalWidth, height: i.naturalHeight }))
            .filter(i => i.src && !i.src.startsWith('data:'));

        const fonts = [];
        try {
            [...document.fonts].forEach(f => {
                fonts.push({ family: f.family, style: f.style, weight: f.weight, status: f.status });
            });
        } catch(e) {}

        const families = new Set();
        [...document.querySelectorAll('*')].slice(0, 400).forEach(e => {
            const f = getComputedStyle(e).fontFamily;
            if (f) families.add(f);
        });

        const stylesheets = [...document.styleSheets].map(s => s.href).filter(Boolean);

        const faviconEl = document.querySelector('link[rel~="icon"]');
        const favicon = faviconEl ? faviconEl.href : '';

        const bgImages = new Set();
        [...document.querySelectorAll('*')].slice(0, 400).forEach(e => {
            const bg = getComputedStyle(e).backgroundImage;
            if (bg && bg !== 'none' && bg.includes('url(')) {
                const m = bg.match(/url\\(["']?([^"')]+)["']?\\)/);
                if (m && !m[1].startsWith('data:')) bgImages.add(m[1]);
            }
        });

        const svgIds = [...document.querySelectorAll('svg[id], svg[class]')]
            .map(s => s.id || s.getAttribute('class') || 'svg').slice(0, 20);

        return {
            images,
            fonts,
            fontFamilies: [...families].slice(0, 20),
            stylesheets,
            favicon,
            backgroundImages: [...bgImages].slice(0, 30),
            inlineSvgs: svgIds,
        };
    """)


def fullpage_screenshot(driver, path: str) -> tuple[str, float]:
    """Take a full-page screenshot using Firefox's native API, falling back to resize."""
    from pathlib import Path
    out = Path(path)
    try:
        driver.get_full_page_screenshot_as_file(str(out))
    except AttributeError:
        orig = driver.get_window_size()
        total_h = driver.execute_script("return document.documentElement.scrollHeight")
        driver.set_window_size(orig["width"], min(total_h, 16384))
        driver.save_screenshot(str(out))
        driver.set_window_size(orig["width"], orig["height"])
    size_kb = out.stat().st_size / 1024
    return str(out), size_kb


# ---------------------------------------------------------------------------
# Frame burst + video recording
# ---------------------------------------------------------------------------

def burst_screenshots(
    driver,
    out_dir: str,
    count: int = 10,
    interval_ms: int = 500,
    prefix: str = "frame",
) -> list[str]:
    """Take N screenshots spaced `interval_ms` milliseconds apart.

    Produces zero-padded PNGs (frame-000.png, frame-001.png, ...) in out_dir.
    Returns the list of file paths. The caller is responsible for driving the
    page (scrolling, clicking, waiting for animations) before/between bursts —
    this function just shoots frames as fast as the interval permits.
    """
    import time
    from pathlib import Path

    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    pad = max(3, len(str(count - 1)))
    paths: list[str] = []

    for i in range(count):
        p = d / f"{prefix}-{i:0{pad}d}.png"
        driver.save_screenshot(str(p))
        paths.append(str(p))
        if i < count - 1:
            time.sleep(interval_ms / 1000.0)

    return paths


def record_video(
    driver,
    out_path: str,
    duration_s: float = 5.0,
    fps: int = 5,
    tmp_dir: Optional[str] = None,
    cleanup: bool = True,
) -> tuple[str, int]:
    """Record a video clip by frame-bursting then stitching with ffmpeg.

    fps × duration frames are captured at the requested cadence, then piped
    through ffmpeg into the container inferred from out_path's extension
    (.mp4, .webm, .mkv, .gif all work).

    Returns (out_path, frame_count). Raises RuntimeError if ffmpeg is missing.
    """
    import shutil
    import subprocess
    import tempfile
    from pathlib import Path

    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not found on PATH; install it to use record.")

    total_frames = max(1, int(round(duration_s * fps)))
    interval_ms = int(1000 / max(1, fps))

    tmp = Path(tmp_dir) if tmp_dir else Path(tempfile.mkdtemp(prefix="foxpilot-rec-"))
    tmp.mkdir(parents=True, exist_ok=True)

    try:
        burst_screenshots(
            driver,
            str(tmp),
            count=total_frames,
            interval_ms=interval_ms,
            prefix="f",
        )

        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        pattern = str(tmp / "f-%03d.png")
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-i", pattern,
            "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
            "-pix_fmt", "yuv420p",
            str(out),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg failed (rc={result.returncode}): {result.stderr[-800:]}"
            )
        return str(out), total_frames
    finally:
        if cleanup:
            import shutil as _shutil
            _shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Element finding
# ---------------------------------------------------------------------------

def find_element(driver, text: str, role: Optional[str] = None, tag: Optional[str] = None):
    """Find a visible element by text, aria-label, placeholder, or title."""
    from selenium.webdriver.common.by import By

    # Escape single quotes for XPath
    escaped = text.replace("'", "\\'")
    candidates = []

    if tag:
        candidates.append(f"//{tag}[contains(., '{escaped}')]")

    if role:
        candidates += [
            f"//*[@role='{role}'][contains(., '{escaped}')]",
            f"//*[@role='{role}'][@aria-label[contains(., '{escaped}')]]",
        ]
    else:
        # Interactive elements take priority
        candidates += [
            f"//button[contains(., '{escaped}')]",
            f"//a[contains(., '{escaped}')]",
            f"//input[@placeholder[contains(., '{escaped}')]]",
            f"//textarea[@placeholder[contains(., '{escaped}')]]",
            f"//select[contains(., '{escaped}')]",
            f"//*[@aria-label[contains(., '{escaped}')]]",
            f"//*[@title[contains(., '{escaped}')]]",
            f"//*[contains(text(), '{escaped}')]",
        ]

    for xpath in candidates:
        try:
            els = driver.find_elements(By.XPATH, xpath)
            visible = [e for e in els if e.is_displayed()]
            if visible:
                return visible[0]
        except Exception:
            continue

    return None


def describe_element(el) -> str:
    """Short human-readable description of an element."""
    tag = el.tag_name
    text = (el.text or "")[:60].strip()
    role = el.get_attribute("role") or ""
    label = el.get_attribute("aria-label") or ""
    placeholder = el.get_attribute("placeholder") or ""

    parts = [f"<{tag}>"]
    if role:
        parts.append(f'role="{role}"')
    if label:
        parts.append(f'aria-label="{label}"')
    elif placeholder:
        parts.append(f'placeholder="{placeholder}"')
    elif text:
        parts.append(f'"{text}"')
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Page reading
# ---------------------------------------------------------------------------

def read_page(driver, selector: Optional[str] = None, max_chars: int = 3000) -> str:
    """Extract visible text from current page or a scoped element."""
    from selenium.webdriver.common.by import By
    from foxpilot.readability import extract_main_content

    if selector:
        try:
            el = driver.find_element(By.CSS_SELECTOR, selector)
            text = el.text
        except Exception:
            return f"(selector '{selector}' not found)"
    else:
        text = extract_main_content(driver)

    if not text:
        return "(no visible text)"

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    result = "\n".join(lines)

    if len(result) > max_chars:
        result = result[:max_chars] + f"\n... [truncated — {len(result)} total chars]"

    return result


def feedback(driver, action_msg: str, selector: Optional[str] = None, max_lines: int = 20) -> str:
    """Return action result + current page state as a formatted string."""
    lines = [action_msg, f"url: {driver.current_url}", f"title: {driver.title}"]

    text = read_page(driver, selector, max_chars=1200)
    if text and text != "(no visible text)":
        lines.append("visible:")
        content_lines = text.splitlines()
        for line in content_lines[:max_lines]:
            lines.append(f"  {line}")
        if len(content_lines) > max_lines:
            lines.append(f"  ... (+{len(content_lines) - max_lines} more lines)")

    return "\n".join(lines)
