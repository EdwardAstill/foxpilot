"""foxpilot.core — browser connection and shared automation logic."""

from contextlib import contextmanager
from pathlib import Path
from typing import Optional

MARIONETTE_PORT = 2828

# Claude mode — dedicated Zen profile with its own marionette port and WM class
# so it can run alongside the user's main Zen without conflict, and be hidden
# in a Hyprland special workspace when the agent is working in the background.
CLAUDE_MARIONETTE_PORT = 2829
CLAUDE_WM_CLASS = "ClaudeZen"
CLAUDE_SPECIAL_WORKSPACE = "claude"
CLAUDE_PROFILE_DIR = Path.home() / ".local/share/foxpilot/claude-profile"


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


# ---------------------------------------------------------------------------
# Claude mode — dedicated Zen profile, hidden by default via Hyprland
# ---------------------------------------------------------------------------

def _claude_marionette_listening() -> bool:
    import socket
    try:
        with socket.create_connection(("127.0.0.1", CLAUDE_MARIONETTE_PORT), timeout=1):
            return True
    except OSError:
        return False


def _hyprctl_clients() -> list:
    """Return parsed `hyprctl clients -j`, or [] if Hyprland not available."""
    import json
    import subprocess
    try:
        out = subprocess.run(
            ["hyprctl", "clients", "-j"],
            capture_output=True, text=True, timeout=2,
        )
        if out.returncode != 0:
            return []
        return json.loads(out.stdout)
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        return []


def _find_claude_window():
    """Return the first hyprctl client whose initialClass matches our claude
    Zen window, or None."""
    for c in _hyprctl_clients():
        if c.get("initialClass") == CLAUDE_WM_CLASS or c.get("class") == CLAUDE_WM_CLASS:
            return c
    return None


def _hyprctl_move_window(address: str, workspace: str) -> None:
    import subprocess
    subprocess.run(
        ["hyprctl", "dispatch", "movetoworkspacesilent",
         f"{workspace},address:{address}"],
        capture_output=True, timeout=2,
    )


def _set_claude_visibility(visible: bool) -> None:
    """Move the claude Zen window onto the active workspace (visible) or into
    the special:claude scratchpad (hidden). No-op if window not found yet."""
    win = _find_claude_window()
    if not win:
        return
    address = win.get("address")
    if not address:
        return
    if visible:
        # Move to whatever workspace the user is currently looking at
        import json
        import subprocess
        try:
            mon = subprocess.run(
                ["hyprctl", "activeworkspace", "-j"],
                capture_output=True, text=True, timeout=2,
            )
            ws = json.loads(mon.stdout).get("name", "1")
        except Exception:
            ws = "1"
        _hyprctl_move_window(address, ws)
    else:
        _hyprctl_move_window(address, f"special:{CLAUDE_SPECIAL_WORKSPACE}")


def _ensure_claude_user_js() -> None:
    """Write a user.js into the claude profile pinning the Marionette port.

    Firefox / Zen do not honor a `--marionette-port` CLI flag; the listener
    port is read from the `marionette.port` pref when `--marionette` enables
    the agent. So we set it via user.js, which is loaded before Marionette
    starts and overrides any prefs.js value.
    """
    user_js = CLAUDE_PROFILE_DIR / "user.js"
    pref_line = f'user_pref("marionette.port", {CLAUDE_MARIONETTE_PORT});'
    existing = user_js.read_text() if user_js.exists() else ""
    if pref_line not in existing:
        user_js.write_text(existing + pref_line + "\n")


def _launch_claude_zen() -> None:
    """Launch a dedicated Zen instance against the claude profile dir, on a
    separate marionette port, with a custom WM class so Hyprland can target it.
    """
    import os
    import subprocess
    import time

    CLAUDE_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    _ensure_claude_user_js()

    env = os.environ.copy()
    if "DISPLAY" not in env:
        env["DISPLAY"] = ":0"

    subprocess.Popen(
        [
            ZEN_BINARY,
            "--no-remote",
            "--profile", str(CLAUDE_PROFILE_DIR),
            "--class", CLAUDE_WM_CLASS,
            "--name", CLAUDE_WM_CLASS,
            "--marionette",
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(20):
        time.sleep(0.5)
        if _claude_marionette_listening():
            return
    raise RuntimeError("Launched claude Zen but Marionette port never opened.")


def _get_driver_claude(visible: bool = False):
    """Connect to (or launch) the dedicated claude Zen profile.

    visible=False (default): the window lives in the Hyprland special:claude
        scratchpad — off-screen, but driveable via Marionette.
    visible=True: window moved onto the user's active workspace.
    """
    import time
    from selenium import webdriver
    from selenium.webdriver.firefox.options import Options
    from selenium.webdriver.firefox.service import Service

    if not _claude_marionette_listening():
        _launch_claude_zen()
        time.sleep(1)

    # Place the window per the requested visibility BEFORE we start driving it,
    # so the user never sees it pop up if they asked for hidden.
    # Small retry loop because the window may take a beat to register with WM.
    import time as _t
    for _ in range(10):
        if _find_claude_window():
            break
        _t.sleep(0.2)
    _set_claude_visibility(visible)

    opts = Options()
    service = Service(
        service_args=[
            "--connect-existing",
            "--marionette-port", str(CLAUDE_MARIONETTE_PORT),
        ]
    )
    try:
        driver = webdriver.Firefox(options=opts, service=service)
    except Exception as e:
        raise RuntimeError(
            f"Can't connect to claude Zen on Marionette port "
            f"{CLAUDE_MARIONETTE_PORT}. Error: {e}"
        ) from e

    try:
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
    except Exception:
        pass

    return driver


def claude_show() -> None:
    """Bring the claude Zen window onto the active workspace."""
    _set_claude_visibility(True)


def claude_hide() -> None:
    """Send the claude Zen window to the special:claude scratchpad."""
    _set_claude_visibility(False)


def _detect_main_zen_profile() -> Optional[Path]:
    """Read ~/.zen/profiles.ini and return the path of the active zen profile.

    Prefers the profile pinned by the Install section, falls back to the
    profile with Default=1, then the most recently-modified cookies.sqlite.
    """
    import configparser
    zen_root = Path.home() / ".zen"
    ini = zen_root / "profiles.ini"
    if not ini.exists():
        return None

    cp = configparser.ConfigParser(strict=False)
    try:
        cp.read(ini)
    except Exception:
        return None

    install_default = None
    profiles: list[Path] = []
    default_profile: Optional[Path] = None

    for section in cp.sections():
        if section.startswith("Install"):
            install_default = cp[section].get("Default")
        elif section.startswith("Profile"):
            path = cp[section].get("Path")
            if not path:
                continue
            is_relative = cp[section].get("IsRelative", "1") == "1"
            full = (zen_root / path) if is_relative else Path(path)
            if (full / "cookies.sqlite").exists():
                profiles.append(full)
            if cp[section].get("Default") == "1":
                default_profile = full

    if install_default:
        candidate = zen_root / install_default
        if candidate.exists():
            return candidate
    if default_profile:
        return default_profile
    if profiles:
        profiles.sort(
            key=lambda p: (p / "cookies.sqlite").stat().st_mtime, reverse=True
        )
        return profiles[0]
    return None


def _kill_claude_zen() -> None:
    """Kill any running ClaudeZen-class zen processes so we can write to the
    profile dir without locking issues."""
    import subprocess
    import time
    # `--` stops pkill from treating later args starting with `--` as options.
    subprocess.run(
        ["pkill", "-f", "--", CLAUDE_WM_CLASS],
        capture_output=True,
    )
    for _ in range(20):
        if not _claude_marionette_listening():
            break
        time.sleep(0.3)


def import_cookies(
    src_profile: Optional[Path] = None,
    domain: Optional[str] = None,
    include_storage: bool = False,
    include_passwords: bool = False,
) -> dict:
    """Copy cookies (and optionally localStorage / saved logins) from the
    user's main Zen profile into the claude profile.

    Uses SQLite's online backup API so copying from a live source database
    (the user's running Zen) is safe. The claude profile must NOT be running
    while we write to it — this function kills it first.

    Args:
        src_profile: path to source Zen profile dir; auto-detected if None.
        domain: if given, only import cookies whose host LIKE %domain%.
        include_storage: also copy webappsstore.sqlite (DOM Storage / localStorage).
        include_passwords: also copy logins.json + key4.db (saved passwords).
    """
    import shutil
    import sqlite3

    if src_profile is None:
        src_profile = _detect_main_zen_profile()
    if src_profile is None or not src_profile.exists():
        raise RuntimeError(
            "Couldn't auto-detect a main Zen profile. Pass --from explicitly."
        )

    _kill_claude_zen()
    CLAUDE_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    _ensure_claude_user_js()

    report: dict = {
        "src": str(src_profile),
        "dst": str(CLAUDE_PROFILE_DIR),
        "cookies_copied": 0,
        "storage_copied": False,
        "passwords_copied": False,
    }

    # ---- cookies.sqlite ----
    # SQLite's online backup retries on SQLITE_BUSY, which the user's live
    # Zen triggers constantly. Instead: take a filesystem snapshot of the
    # .sqlite + .sqlite-wal pair, then operate on the snapshot.
    src_cookies = src_profile / "cookies.sqlite"
    dst_cookies = CLAUDE_PROFILE_DIR / "cookies.sqlite"
    if not src_cookies.exists():
        raise RuntimeError(f"No cookies.sqlite at {src_cookies}")

    import tempfile
    tmp_dir = Path(tempfile.mkdtemp(prefix="foxpilot-cookies-"))
    try:
        snap = tmp_dir / "cookies.sqlite"
        shutil.copy2(src_cookies, snap)
        for ext in ("-wal", "-shm"):
            src_extra = Path(str(src_cookies) + ext)
            if src_extra.exists():
                shutil.copy2(src_extra, str(snap) + ext)

        # Now operate on the snapshot — no live writer to fight.
        snap_conn = sqlite3.connect(snap)
        try:
            if domain:
                snap_conn.execute(
                    "DELETE FROM moz_cookies WHERE host NOT LIKE ?",
                    (f"%{domain}%",),
                )
                snap_conn.commit()
            # Force WAL contents into the main db file so we can move just the
            # one file across.
            snap_conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            report["cookies_copied"] = snap_conn.execute(
                "SELECT COUNT(*) FROM moz_cookies"
            ).fetchone()[0]
        finally:
            snap_conn.close()

        # Replace dst — wipe any old WAL/SHM that referenced the prior file.
        for ext in ("", "-wal", "-shm"):
            p = Path(str(dst_cookies) + ext)
            if p.exists():
                p.unlink()
        shutil.move(str(snap), str(dst_cookies))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # ---- webappsstore.sqlite (DOM Storage / localStorage) ----
    if include_storage:
        src_store = src_profile / "webappsstore.sqlite"
        if src_store.exists():
            dst_store = CLAUDE_PROFILE_DIR / "webappsstore.sqlite"
            for ext in ("", "-wal", "-shm"):
                p = Path(str(dst_store) + ext)
                if p.exists():
                    p.unlink()
            shutil.copy2(src_store, dst_store)
            for ext in ("-wal", "-shm"):
                src_extra = Path(str(src_store) + ext)
                if src_extra.exists():
                    shutil.copy2(src_extra, str(dst_store) + ext)
            # Checkpoint to consolidate
            try:
                conn = sqlite3.connect(dst_store)
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                conn.close()
            except Exception:
                pass
            report["storage_copied"] = True

    # ---- logins.json + key4.db (saved passwords) ----
    if include_passwords:
        for fname in ("logins.json", "key4.db"):
            src_f = src_profile / fname
            if src_f.exists():
                shutil.copy2(src_f, CLAUDE_PROFILE_DIR / fname)
                report["passwords_copied"] = True

    return report


def claude_status() -> dict:
    """Report claude profile state — running, marionette port, visibility."""
    win = _find_claude_window()
    visible = False
    workspace = None
    if win:
        ws = win.get("workspace", {}) or {}
        workspace = ws.get("name")
        visible = not (workspace or "").startswith("special:")
    return {
        "running": _claude_marionette_listening(),
        "window_present": win is not None,
        "visible": visible,
        "workspace": workspace,
        "profile_dir": str(CLAUDE_PROFILE_DIR),
        "marionette_port": CLAUDE_MARIONETTE_PORT,
    }


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
def browser(mode: str = "claude", visible: bool = False):
    """Yield a WebDriver; close it on exit.

    mode="claude"   — dedicated Zen profile, hidden by default (default)
    mode="zen"      — connect to user's running Zen browser (shares your tabs)
    mode="headless" — launch ephemeral headless Firefox (no session)
    visible         — only meaningful for mode="claude"; True puts the window
                      on the active workspace, False leaves it hidden in the
                      Hyprland special:claude scratchpad.
    """
    driver = None
    try:
        if mode == "claude":
            driver = _get_driver_claude(visible=visible)
        elif mode == "zen":
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
