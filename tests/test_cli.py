from typer.testing import CliRunner

from foxpilot import cli


runner = CliRunner()


def test_zen_status_uses_zen_report(monkeypatch):
    def fail_claude_status():
        raise AssertionError("claude_status should not run for --zen status")

    monkeypatch.setattr(cli, "claude_status", fail_claude_status)
    monkeypatch.setattr(
        cli,
        "zen_status",
        lambda: {
            "running": True,
            "marionette_ready": False,
            "marionette_port": 2828,
            "socket_access": True,
            "socket_error": None,
        },
    )

    result = runner.invoke(cli.app, ["--zen", "status"])

    assert result.exit_code == 0
    assert "mode" in result.stdout
    assert "zen" in result.stdout
    assert "marionette_port" in result.stdout
    assert "2828" in result.stdout
    assert "profile_dir" not in result.stdout
