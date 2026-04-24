import subprocess

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
