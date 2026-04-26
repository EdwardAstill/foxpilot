"""foxpilot.core — browser connection and shared automation logic."""

from collections.abc import Sequence
from contextlib import contextmanager
from pathlib import Path
import stat
from typing import Optional

MARIONETTE_PORT = 2828

# Claude mode — dedicated Zen profile with its own marionette port and WM class
# so it can run alongside the user's main Zen without conflict, and be hidden
# in a Hyprland special workspace when the agent is working in the background.
CLAUDE_MARIONETTE_PORT = 2829
CLAUDE_WM_CLASS = "ClaudeZen"
CLAUDE_SPECIAL_WORKSPACE = "claude"
FOXPILOT_DATA_DIR = Path.home() / ".local/share/foxpilot"
AUTOMATION_PROFILE_DIR = FOXPILOT_DATA_DIR / "automation-profile"
LEGACY_CLAUDE_PROFILE_DIR = FOXPILOT_DATA_DIR / "claude-profile"
FOXPILOT_SECRETS_DIR = FOXPILOT_DATA_DIR / "secrets"
# Backwards-compatible import name for older callers. This now points at the
# model-neutral automation profile path.
CLAUDE_PROFILE_DIR = AUTOMATION_PROFILE_DIR


def _ensure_private_dir(path: Path) -> None:
    """Create a directory and remove group/other permissions."""
    if path.exists() and path.is_symlink():
        raise RuntimeError(f"Refusing to use symlinked auth directory: {path}")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        path.chmod(mode & ~0o077)


def _ensure_private_file(path: Path) -> None:
    """Remove group/other permissions from a file containing browser state."""
    if path.exists() and path.is_symlink():
        raise RuntimeError(f"Refusing to use symlinked auth file: {path}")
    if path.exists():
        path.chmod(0o600)


def _write_private_file(path: Path, text: str) -> None:
    path.write_text(text)
    _ensure_private_file(path)


def migrate_legacy_profile(
    *,
    profile_dir: Optional[Path] = None,
    legacy_profile_dir: Optional[Path] = None,
) -> dict[str, str]:
    """Move the old claude-profile directory to automation-profile when safe."""
    import shutil

    profile_dir = profile_dir or AUTOMATION_PROFILE_DIR
    legacy_profile_dir = legacy_profile_dir or LEGACY_CLAUDE_PROFILE_DIR

    if legacy_profile_dir == profile_dir:
        return {
            "legacy_migration": "none",
            "legacy": "legacy and automation profile paths are identical",
        }
    if not legacy_profile_dir.exists():
        return {
            "legacy_migration": "none",
            "legacy": f"no legacy profile at {legacy_profile_dir}",
        }
    if legacy_profile_dir.is_symlink():
        raise RuntimeError(f"Refusing to migrate symlinked legacy profile: {legacy_profile_dir}")
    if profile_dir.exists():
        return {
            "legacy_migration": "skipped_new_exists",
            "legacy": (
                f"legacy profile remains at {legacy_profile_dir}; "
                f"automation profile already exists at {profile_dir}"
            ),
        }

    _ensure_private_dir(profile_dir.parent)
    shutil.move(str(legacy_profile_dir), str(profile_dir))
    _ensure_private_dir(profile_dir)
    return {
        "legacy_migration": "moved",
        "legacy": f"moved {legacy_profile_dir} to {profile_dir}",
    }


def ensure_auth_storage(
    *,
    profile_dir: Optional[Path] = None,
    secrets_dir: Optional[Path] = None,
    legacy_profile_dir: Optional[Path] = None,
) -> dict[str, str]:
    """Create foxpilot's private auth storage.

    Browser session auth stays in the dedicated browser profile. The secrets
    directory is for non-browser tokens/config that should not live in repos.
    """
    profile_dir = profile_dir or AUTOMATION_PROFILE_DIR
    secrets_dir = secrets_dir or (profile_dir.parent / "secrets")
    legacy_profile_dir = legacy_profile_dir or LEGACY_CLAUDE_PROFILE_DIR
    data_dir = profile_dir.parent

    _ensure_private_dir(data_dir)
    migration = migrate_legacy_profile(
        profile_dir=profile_dir,
        legacy_profile_dir=legacy_profile_dir,
    )
    _ensure_private_dir(profile_dir)
    _ensure_private_dir(secrets_dir)

    readme = secrets_dir / "README.txt"
    if not readme.exists():
        _write_private_file(
            readme,
            "Foxpilot secrets directory.\n"
            "\n"
            "Browser cookies stay in ../automation-profile/ as browser profile "
            "state.\n"
            "Put only non-browser API tokens or local auth config here.\n"
            "Do not symlink or commit this directory.\n",
        )
    else:
        _ensure_private_file(readme)

    return {
        "data_dir": str(data_dir),
        "automation_profile_dir": str(profile_dir),
        "legacy_claude_profile_dir": str(legacy_profile_dir),
        "secrets_dir": str(secrets_dir),
        "legacy_migration": migration["legacy_migration"],
        "browser_auth": "browser cookies/session storage stay in automation_profile_dir",
        "api_secrets": "non-browser tokens belong in secrets_dir, never project .secrets",
    }


def auth_storage_status(
    *,
    profile_dir: Optional[Path] = None,
    secrets_dir: Optional[Path] = None,
    legacy_profile_dir: Optional[Path] = None,
) -> dict[str, dict[str, object]]:
    profile_dir = profile_dir or AUTOMATION_PROFILE_DIR
    secrets_dir = secrets_dir or (profile_dir.parent / "secrets")
    legacy_profile_dir = legacy_profile_dir or LEGACY_CLAUDE_PROFILE_DIR
    paths = {
        "foxpilot_data_dir": profile_dir.parent,
        "automation_profile_dir": profile_dir,
        "secrets_dir": secrets_dir,
    }
    report: dict[str, dict[str, object]] = {}
    for key, path in paths.items():
        if not path.exists():
            report[key] = {
                "ok": True,
                "message": f"{path} not created yet",
            }
            continue
        if path.is_symlink():
            report[key] = {
                "ok": False,
                "message": f"{path} is a symlink; refusing auth storage",
            }
            continue
        if not path.is_dir():
            report[key] = {"ok": False, "message": f"{path} is not a directory"}
            continue
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode & 0o077:
            report[key] = {
                "ok": False,
                "message": f"{path} permissions are {mode:o}, expected 700",
            }
        else:
            report[key] = {"ok": True, "message": f"{path} private ({mode:o})"}
    if legacy_profile_dir.exists():
        report["legacy_claude_profile_dir"] = {
            "ok": False,
            "message": (
                f"legacy profile exists at {legacy_profile_dir}; "
                "run `foxpilot auth migrate`"
            ),
        }
    else:
        report["legacy_claude_profile_dir"] = {
            "ok": True,
            "message": f"no legacy profile at {legacy_profile_dir}",
        }
    return report


def auth_storage_report() -> dict[str, str]:
    status = auth_storage_status()
    ok = all(item.get("ok") for item in status.values())
    initialized = (
        FOXPILOT_DATA_DIR.exists()
        and AUTOMATION_PROFILE_DIR.exists()
        and FOXPILOT_SECRETS_DIR.exists()
    )
    legacy = status["legacy_claude_profile_dir"]["message"]
    if not initialized:
        summary = "not initialized; run `foxpilot auth init`"
    elif ok:
        summary = "private"
    else:
        summary = "run `foxpilot auth doctor` or `foxpilot auth init`"
    return {
        "data_dir": str(FOXPILOT_DATA_DIR),
        "automation_profile_dir": str(AUTOMATION_PROFILE_DIR),
        "legacy_claude_profile_dir": str(LEGACY_CLAUDE_PROFILE_DIR),
        "secrets_dir": str(FOXPILOT_SECRETS_DIR),
        "browser_auth": "browser cookies/session/localStorage stay in automation_profile_dir",
        "api_secrets": "API tokens and non-browser auth config belong in secrets_dir",
        "legacy": str(legacy),
        "status": summary,
    }


def _normalize_cookie_domains(domain: Optional[str | Sequence[str]]) -> list[str]:
    if domain is None:
        return []
    if isinstance(domain, str):
        return [domain] if domain else []
    return [item for item in domain if item]


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

ZEN_BINARY = "zen-browser"


def _socket_access_error(target: str) -> RuntimeError:
    return RuntimeError(
        "Local TCP sockets are blocked in this environment, so foxpilot can't "
        f"talk to {target}. Re-run foxpilot outside the sandbox or with "
        "escalated permissions."
    )


def _tcp_port_listening(port: int, target: str) -> bool:
    import socket

    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except PermissionError as e:
        raise _socket_access_error(target) from e
    except OSError:
        return False


def _ensure_local_socket_access(target: str) -> None:
    import socket

    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.close()
    except PermissionError as e:
        raise _socket_access_error(target) from e


def _spawn_detached(argv: list[str], env: dict[str, str]) -> None:
    """Launch a long-lived browser process detached from the invoking CLI.

    foxpilot commands are one-shot processes. If Zen inherits the command's
    session/stdio, it can die as soon as the Python process exits. Start it in
    its own session with stdio disconnected so the browser survives across
    separate foxpilot invocations.
    """
    import subprocess

    subprocess.Popen(
        argv,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )


def _marionette_listening() -> bool:
    """Return True if something is accepting connections on the Marionette port."""
    return _tcp_port_listening(MARIONETTE_PORT, f"Zen Marionette on port {MARIONETTE_PORT}")


def _zen_running() -> bool:
    """Return True if a zen-bin process exists."""
    import subprocess
    result = subprocess.run(["pgrep", "-f", "zen-bin"], capture_output=True)
    return result.returncode == 0


def _launch_zen_with_marionette() -> None:
    """Launch Zen in the background with --marionette and wait for port."""
    import time
    import os

    env = os.environ.copy()
    if "DISPLAY" not in env:
        env["DISPLAY"] = ":0"

    _spawn_detached([ZEN_BINARY, "--marionette"], env)
    # Wait up to 10s for Marionette to come up
    for _ in range(20):
        time.sleep(0.5)
        if _marionette_listening():
            return
    raise RuntimeError("Launched Zen but Marionette port never opened.")


def _get_driver_zen():
    """Connect to running Zen via geckodriver --connect-existing.

    If Zen is not running, launches it automatically with --marionette.
    If Zen is running but Marionette is not listening, fail loudly without
    restarting the user's browser. Auto-restarting a real session is intrusive
    and can trigger session-restore window churn.
    """
    import time
    from selenium import webdriver
    from selenium.webdriver.firefox.options import Options
    from selenium.webdriver.firefox.service import Service

    if not _marionette_listening():
        if _zen_running():
            raise RuntimeError(
                "Zen is already running but Marionette is not enabled. "
                "foxpilot will not restart your real browser automatically. "
                "If you need this exact live window, switch to desktop "
                "automation / computer-control. If you only need the login "
                "state, use claude mode plus import-cookies. Restart Zen "
                "yourself with --marionette only if you specifically need "
                "foxpilot --zen."
            )
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


def _close_driver(driver, mode: str) -> None:
    """Tear down WebDriver state without needlessly killing persistent browsers."""
    if mode == "headless":
        driver.quit()
        return

    # For connect-existing claude/zen sessions, stop the geckodriver sidecar
    # but leave the browser itself running. This is especially important for
    # `--zen`, which attaches to the user's real browser session.
    service = getattr(driver, "service", None)
    if service is not None:
        try:
            service.stop()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Claude mode — dedicated Zen profile, hidden by default via Hyprland
# ---------------------------------------------------------------------------

def _claude_marionette_listening() -> bool:
    return _tcp_port_listening(
        CLAUDE_MARIONETTE_PORT,
        f"the claude Marionette bridge on port {CLAUDE_MARIONETTE_PORT}",
    )


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


def _set_claude_visibility(visible: bool) -> dict:
    """Move the claude Zen window onto the active workspace (visible) or into
    the special:claude scratchpad (hidden)."""
    win = _find_claude_window()
    if not win:
        return {"status": "not_running", "workspace": None}
    address = win.get("address")
    if not address:
        return {"status": "not_running", "workspace": None}

    ws_data = win.get("workspace", {}) or {}
    current_workspace = ws_data.get("name")
    currently_visible = not (current_workspace or "").startswith("special:")
    if visible and currently_visible:
        return {"status": "already_visible", "workspace": current_workspace}
    if not visible and not currently_visible:
        return {"status": "already_hidden", "workspace": current_workspace}

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
        return {"status": "changed", "workspace": ws}
    else:
        _hyprctl_move_window(address, f"special:{CLAUDE_SPECIAL_WORKSPACE}")
        return {
            "status": "changed",
            "workspace": f"special:{CLAUDE_SPECIAL_WORKSPACE}",
        }


def _ensure_claude_user_js() -> None:
    """Write a user.js into the automation profile pinning the Marionette port.

    Firefox / Zen do not honor a `--marionette-port` CLI flag; the listener
    port is read from the `marionette.port` pref when `--marionette` enables
    the agent. So we set it via user.js, which is loaded before Marionette
    starts and overrides any prefs.js value.
    """
    _ensure_private_dir(CLAUDE_PROFILE_DIR)
    user_js = CLAUDE_PROFILE_DIR / "user.js"
    pref_line = f'user_pref("marionette.port", {CLAUDE_MARIONETTE_PORT});'
    existing = user_js.read_text() if user_js.exists() else ""
    if pref_line not in existing:
        _write_private_file(user_js, existing + pref_line + "\n")
    else:
        _ensure_private_file(user_js)


def _launch_claude_zen() -> None:
    """Launch a dedicated Zen instance against the automation profile dir, on a
    separate marionette port, with a custom WM class so Hyprland can target it.
    """
    import os
    import time

    ensure_auth_storage()
    _ensure_claude_user_js()

    env = os.environ.copy()
    if "DISPLAY" not in env:
        env["DISPLAY"] = ":0"

    _spawn_detached(
        [
            ZEN_BINARY,
            "--no-remote",
            "--profile", str(CLAUDE_PROFILE_DIR),
            "--class", CLAUDE_WM_CLASS,
            "--name", CLAUDE_WM_CLASS,
            "--marionette",
        ],
        env=env,
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


def claude_show() -> dict:
    """Bring the claude Zen window onto the active workspace."""
    return _set_claude_visibility(True)


def claude_hide() -> dict:
    """Send the claude Zen window to the special:claude scratchpad."""
    return _set_claude_visibility(False)


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
    domain: Optional[str | Sequence[str]] = None,
    include_storage: bool = False,
    include_passwords: bool = False,
) -> dict:
    """Copy cookies (and optionally localStorage / saved logins) from the
    user's main Zen profile into the automation profile.

    Uses SQLite's online backup API so copying from a live source database
    (the user's running Zen) is safe. The automation profile must NOT be running
    while we write to it — this function kills it first.

    Args:
        src_profile: path to source Zen profile dir; auto-detected if None.
        domain: if given, only import cookies whose host LIKE one of these domains.
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
    domains = _normalize_cookie_domains(domain)

    _kill_claude_zen()
    ensure_auth_storage()
    _ensure_claude_user_js()

    report: dict = {
        "src": str(src_profile),
        "dst": str(CLAUDE_PROFILE_DIR),
        "cookies_copied": 0,
        "domains": domains,
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
            if domains:
                predicate = " OR ".join("host LIKE ?" for _ in domains)
                snap_conn.execute(
                    f"DELETE FROM moz_cookies WHERE NOT ({predicate})",
                    tuple(f"%{item}%" for item in domains),
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
        _ensure_private_file(dst_cookies)
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
            _ensure_private_file(dst_store)
            for ext in ("-wal", "-shm"):
                src_extra = Path(str(src_store) + ext)
                if src_extra.exists():
                    shutil.copy2(src_extra, str(dst_store) + ext)
                    _ensure_private_file(Path(str(dst_store) + ext))
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
                _ensure_private_file(CLAUDE_PROFILE_DIR / fname)
                report["passwords_copied"] = True

    return report


def claude_status() -> dict:
    """Report automation profile state — running, marionette port, visibility."""
    win = _find_claude_window()
    visible = False
    workspace = None
    if win:
        ws = win.get("workspace", {}) or {}
        workspace = ws.get("name")
        visible = not (workspace or "").startswith("special:")
    socket_error = None
    running = None
    try:
        running = _claude_marionette_listening()
    except RuntimeError as exc:
        socket_error = str(exc)
    return {
        "running": running,
        "window_present": win is not None,
        "visible": visible,
        "workspace": workspace,
        "profile_dir": str(CLAUDE_PROFILE_DIR),
        "marionette_port": CLAUDE_MARIONETTE_PORT,
        "socket_access": socket_error is None,
        "socket_error": socket_error,
    }


def zen_status() -> dict:
    """Report real Zen state — process presence, Marionette reachability."""
    socket_error = None
    marionette_ready = None
    try:
        marionette_ready = _marionette_listening()
    except RuntimeError as exc:
        socket_error = str(exc)
    return {
        "running": _zen_running(),
        "marionette_ready": marionette_ready,
        "marionette_port": MARIONETTE_PORT,
        "socket_access": socket_error is None,
        "socket_error": socket_error,
    }


def doctor_report(mode: str = "claude") -> dict:
    """Return a mode-aware diagnostic report with next-step guidance."""
    if mode == "zen":
        zen = zen_status()
        report = {
            "mode": "zen",
            "zen_running": zen["running"],
            "zen_marionette_ready": zen["marionette_ready"],
            "marionette_port": zen["marionette_port"],
            "socket_access": zen["socket_access"],
        }
        if zen["socket_error"]:
            report["socket_error"] = zen["socket_error"]
        if not zen["socket_access"]:
            report.update(
                status="blocked",
                summary="foxpilot cannot reach local browser sockets from this environment.",
                next_step="Run foxpilot outside the sandbox, then retry the same --zen command.",
                fallback="If the visible on-screen browser matters, hand off to desktop automation / computer-control.",
            )
        elif zen["marionette_ready"]:
            report.update(
                status="ready",
                summary="Your real Zen session is attachable right now.",
                next_step="Run foxpilot --zen <command>.",
                fallback="Use default claude mode instead if you do not need the exact live window.",
            )
        elif zen["running"]:
            report.update(
                status="needs_marionette",
                summary="Your real Zen browser is open, but Marionette is off, so foxpilot cannot attach.",
                next_step="Restart Zen with --marionette only if you need this exact live session.",
                fallback="Otherwise use claude mode with import-cookies, or hand off to desktop automation / computer-control for the visible window.",
            )
        else:
            report.update(
                status="launchable",
                summary="Real Zen is not running; foxpilot can launch it with Marionette for you.",
                next_step="Run foxpilot --zen <command>.",
                fallback="Use default claude mode if you want an isolated browser instead of your real session.",
            )
        return report

    if mode == "headless":
        socket_error = None
        try:
            _ensure_local_socket_access("headless Firefox via geckodriver")
        except RuntimeError as exc:
            socket_error = str(exc)
        report = {
            "mode": "headless",
            "socket_access": socket_error is None,
        }
        if socket_error:
            report["socket_error"] = socket_error
            report.update(
                status="blocked",
                summary="headless Firefox cannot launch from this environment.",
                next_step="Run foxpilot outside the sandbox, then retry.",
                fallback="If you need the browser already on screen, use desktop automation / computer-control.",
            )
        else:
            report.update(
                status="ready",
                summary="Headless Firefox should be launchable.",
                next_step="Run foxpilot --headless-mode <command>.",
                fallback="Switch to claude mode if you need a persistent authenticated session.",
            )
        return report

    claude = claude_status()
    zen = zen_status()
    report = {
        "mode": "claude",
        "claude_running": claude["running"],
        "window_present": claude["window_present"],
        "visible": claude["visible"],
        "workspace": claude["workspace"],
        "profile_dir": claude["profile_dir"],
        "marionette_port": claude["marionette_port"],
        "socket_access": claude["socket_access"],
        "real_zen_running": zen["running"],
        "real_zen_marionette_ready": zen["marionette_ready"],
    }
    if claude["socket_error"]:
        report["socket_error"] = claude["socket_error"]
    if not claude["socket_access"]:
        report.update(
            status="blocked",
            summary="foxpilot cannot reach the automation-profile browser from this environment.",
            next_step="Run foxpilot outside the sandbox, then retry.",
            fallback="If you need the visible on-screen browser right now, hand off to desktop automation / computer-control.",
        )
    elif claude["running"]:
        report.update(
            status="ready",
            summary="The dedicated claude browser is already up and reachable.",
            next_step="Run foxpilot <command>.",
            fallback="Use --zen only when you explicitly need the user's exact live session.",
        )
    else:
        report.update(
            status="launchable",
            summary="The dedicated claude browser is not running yet, but foxpilot can launch it automatically.",
            next_step="Run foxpilot <command>; it will start the automation profile for you.",
            fallback="Use --zen only for the user's real session, or desktop automation / computer-control if the exact visible window matters.",
        )
    return report


def _get_driver_headless():
    """Launch a headless Firefox instance."""
    from selenium import webdriver
    from selenium.webdriver.firefox.options import Options

    _ensure_local_socket_access("headless Firefox via geckodriver")

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
                _close_driver(driver, mode)
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
            _close_driver(driver, "zen")
        except Exception:
            pass


def activate_tab(tab_id: str) -> None:
    """Switch to a tab by window handle — intentionally raises the window."""
    driver = _get_driver_zen()
    try:
        driver.switch_to.window(tab_id)
    finally:
        try:
            _close_driver(driver, "zen")
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
            _close_driver(driver, "zen")
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
            f"//*[@role='{role}'][contains(@aria-label, '{escaped}')]",
        ]
    else:
        # Interactive elements take priority
        candidates += [
            f"//button[contains(., '{escaped}')]",
            f"//a[contains(., '{escaped}')]",
            f"//input[contains(@placeholder, '{escaped}')]",
            f"//textarea[contains(@placeholder, '{escaped}')]",
            f"//select[contains(., '{escaped}')]",
            f"//*[contains(@aria-label, '{escaped}')]",
            f"//*[contains(@title, '{escaped}')]",
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


def find_input_element(driver, text: str):
    """Find a form input (input/textarea/select) by label text, placeholder, name, or id.

    Resolves label→input associations properly so fill() doesn't match label
    spans instead of their associated inputs.
    """
    from selenium.webdriver.common.by import By

    escaped = text.replace("'", "\\'")

    # 1. Label text → associated input via `for` attribute
    try:
        labels = driver.find_elements(By.XPATH, f"//label[contains(., '{escaped}')]")
        for label in labels:
            if not label.is_displayed():
                continue
            for_id = label.get_attribute("for")
            if for_id:
                try:
                    inp = driver.find_element(By.ID, for_id)
                    if inp.is_displayed():
                        return inp
                except Exception:
                    pass
            # Label wrapping an input directly
            for tag in ("input", "textarea", "select"):
                try:
                    inp = label.find_element(By.TAG_NAME, tag)
                    if inp.is_displayed():
                        return inp
                except Exception:
                    pass
    except Exception:
        pass

    # 2. Input/textarea/select by placeholder, name, id, aria-label
    for attr in ("placeholder", "name", "id", "aria-label"):
        for tag in ("input", "textarea", "select"):
            try:
                els = driver.find_elements(
                    By.XPATH,
                    f"//{tag}[@{attr}[contains(., '{escaped}')]]",
                )
                visible = [e for e in els if e.is_displayed()]
                if visible:
                    return visible[0]
            except Exception:
                continue

    # 3. Any visible input/textarea if only one exists (last resort)
    try:
        inputs = driver.find_elements(
            By.CSS_SELECTOR, "input:not([type=hidden]), textarea, select"
        )
        visible = [e for e in inputs if e.is_displayed()]
        if len(visible) == 1:
            return visible[0]
    except Exception:
        pass

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
