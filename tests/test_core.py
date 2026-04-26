import subprocess
import sqlite3
import stat

from foxpilot import core


def test_spawn_detached_uses_own_session(monkeypatch):
    seen = {}

    def fake_popen(argv, **kwargs):
        seen["argv"] = argv
        seen["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    env = {"DISPLAY": ":0"}
    core._spawn_detached(["zen-browser", "--marionette"], env)

    assert seen["argv"] == ["zen-browser", "--marionette"]
    assert seen["kwargs"]["env"] == env
    assert seen["kwargs"]["stdin"] is subprocess.DEVNULL
    assert seen["kwargs"]["stdout"] is subprocess.DEVNULL
    assert seen["kwargs"]["stderr"] is subprocess.DEVNULL
    assert seen["kwargs"]["start_new_session"] is True
    assert seen["kwargs"]["close_fds"] is True


def test_get_driver_zen_refuses_to_restart_running_browser(monkeypatch):
    monkeypatch.setattr(core, "_marionette_listening", lambda: False)
    monkeypatch.setattr(core, "_zen_running", lambda: True)

    try:
        core._get_driver_zen()
    except RuntimeError as exc:
        assert "will not restart your real browser automatically" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_close_driver_quits_only_headless():
    events = []

    class _Service:
        def stop(self):
            events.append("stop")

    class _Driver:
        def __init__(self):
            self.service = _Service()

        def quit(self):
            events.append("quit")

    driver = _Driver()
    core._close_driver(driver, "claude")
    assert events == ["stop"]

    events.clear()
    core._close_driver(driver, "zen")
    assert events == ["stop"]

    events.clear()
    core._close_driver(driver, "headless")
    assert events == ["quit"]


def test_marionette_listening_raises_clear_error_when_sockets_are_blocked(monkeypatch):
    import socket

    def fake_connect(*args, **kwargs):
        raise PermissionError(1, "Operation not permitted")

    monkeypatch.setattr(socket, "create_connection", fake_connect)

    try:
        core._marionette_listening()
    except RuntimeError as exc:
        message = str(exc)
        assert "Local TCP sockets are blocked" in message
        assert "outside the sandbox" in message
    else:
        raise AssertionError("expected RuntimeError")


def test_claude_status_handles_socket_block(monkeypatch):
    monkeypatch.setattr(core, "_find_claude_window", lambda: None)

    def fake_listening():
        raise RuntimeError("socket blocked")

    monkeypatch.setattr(core, "_claude_marionette_listening", fake_listening)

    status = core.claude_status()

    assert status["running"] is None
    assert status["socket_access"] is False
    assert status["socket_error"] == "socket blocked"


def test_zen_status_reports_running_browser_without_marionette(monkeypatch):
    monkeypatch.setattr(core, "_zen_running", lambda: True)
    monkeypatch.setattr(core, "_marionette_listening", lambda: False)

    status = core.zen_status()

    assert status["running"] is True
    assert status["marionette_ready"] is False
    assert status["socket_access"] is True


def test_doctor_report_for_zen_recommends_computer_control(monkeypatch):
    monkeypatch.setattr(core, "_zen_running", lambda: True)
    monkeypatch.setattr(core, "_marionette_listening", lambda: False)

    report = core.doctor_report("zen")

    assert report["status"] == "needs_marionette"
    assert "computer-control" in report["fallback"]
    assert "Restart Zen with --marionette" in report["next_step"]


def _mode(path):
    return stat.S_IMODE(path.stat().st_mode)


def test_ensure_auth_storage_creates_private_dirs(tmp_path):
    profile_dir = tmp_path / "foxpilot" / "automation-profile"
    secrets_dir = tmp_path / "foxpilot" / "secrets"

    report = core.ensure_auth_storage(
        profile_dir=profile_dir,
        secrets_dir=secrets_dir,
    )

    assert report["data_dir"] == str(profile_dir.parent)
    assert report["automation_profile_dir"] == str(profile_dir)
    assert report["secrets_dir"] == str(secrets_dir)
    assert profile_dir.parent.is_dir()
    assert profile_dir.is_dir()
    assert secrets_dir.is_dir()
    assert _mode(profile_dir.parent) == 0o700
    assert _mode(profile_dir) == 0o700
    assert _mode(secrets_dir) == 0o700


def test_ensure_auth_storage_repairs_broad_permissions(tmp_path):
    data_dir = tmp_path / "foxpilot"
    profile_dir = data_dir / "automation-profile"
    secrets_dir = data_dir / "secrets"
    for path in (data_dir, profile_dir, secrets_dir):
        path.mkdir(parents=True, exist_ok=True)
        path.chmod(0o777)

    core.ensure_auth_storage(profile_dir=profile_dir, secrets_dir=secrets_dir)

    assert _mode(data_dir) == 0o700
    assert _mode(profile_dir) == 0o700
    assert _mode(secrets_dir) == 0o700


def test_ensure_auth_storage_migrates_legacy_claude_profile(tmp_path):
    data_dir = tmp_path / "foxpilot"
    profile_dir = data_dir / "automation-profile"
    legacy_profile_dir = data_dir / "claude-profile"
    legacy_profile_dir.mkdir(parents=True)
    (legacy_profile_dir / "cookies.sqlite").write_text("legacy cookies")

    report = core.ensure_auth_storage(
        profile_dir=profile_dir,
        legacy_profile_dir=legacy_profile_dir,
    )

    assert profile_dir.is_dir()
    assert not legacy_profile_dir.exists()
    assert (profile_dir / "cookies.sqlite").read_text() == "legacy cookies"
    assert report["legacy_migration"] == "moved"


def test_auth_storage_status_reports_legacy_profile_when_present(tmp_path):
    data_dir = tmp_path / "foxpilot"
    profile_dir = data_dir / "automation-profile"
    secrets_dir = data_dir / "secrets"
    legacy_profile_dir = data_dir / "claude-profile"
    legacy_profile_dir.mkdir(parents=True)

    report = core.auth_storage_status(
        profile_dir=profile_dir,
        secrets_dir=secrets_dir,
        legacy_profile_dir=legacy_profile_dir,
    )

    assert "automation_profile_dir" in report
    assert report["legacy_claude_profile_dir"]["ok"] is False
    assert "legacy" in report["legacy_claude_profile_dir"]["message"]


def test_auth_storage_report_marks_missing_profile_not_initialized(monkeypatch, tmp_path):
    data_dir = tmp_path / "foxpilot"
    profile_dir = data_dir / "automation-profile"
    secrets_dir = data_dir / "secrets"
    legacy_profile_dir = data_dir / "claude-profile"

    monkeypatch.setattr(core, "FOXPILOT_DATA_DIR", data_dir)
    monkeypatch.setattr(core, "AUTOMATION_PROFILE_DIR", profile_dir)
    monkeypatch.setattr(core, "FOXPILOT_SECRETS_DIR", secrets_dir)
    monkeypatch.setattr(core, "LEGACY_CLAUDE_PROFILE_DIR", legacy_profile_dir)

    report = core.auth_storage_report()

    assert report["status"] == "not initialized; run `foxpilot auth init`"


def test_import_cookies_accepts_multiple_domains(monkeypatch, tmp_path):
    src_profile = tmp_path / "src"
    dst_profile = tmp_path / "foxpilot" / "automation-profile"
    src_profile.mkdir()
    db = src_profile / "cookies.sqlite"
    conn = sqlite3.connect(db)
    try:
        conn.execute("CREATE TABLE moz_cookies (id INTEGER PRIMARY KEY, host TEXT)")
        conn.executemany(
            "INSERT INTO moz_cookies(host) VALUES (?)",
            [
                (".youtube.com",),
                (".google.com",),
                (".example.com",),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(core, "AUTOMATION_PROFILE_DIR", dst_profile)
    monkeypatch.setattr(core, "CLAUDE_PROFILE_DIR", dst_profile)
    monkeypatch.setattr(core, "_kill_claude_zen", lambda: None)

    report = core.import_cookies(
        src_profile=src_profile,
        domain=["youtube.com", "google.com"],
    )

    conn = sqlite3.connect(dst_profile / "cookies.sqlite")
    try:
        hosts = {
            row[0]
            for row in conn.execute("SELECT host FROM moz_cookies ORDER BY host")
        }
    finally:
        conn.close()

    assert report["cookies_copied"] == 2
    assert hosts == {".google.com", ".youtube.com"}
