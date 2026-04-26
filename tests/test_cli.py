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


def test_auth_init_reports_private_storage_paths(monkeypatch):
    monkeypatch.setattr(
        cli,
        "ensure_auth_storage",
        lambda: {
            "data_dir": "/tmp/foxpilot",
            "automation_profile_dir": "/tmp/foxpilot/automation-profile",
            "secrets_dir": "/tmp/foxpilot/secrets",
            "legacy_migration": "none",
        },
    )

    result = runner.invoke(cli.app, ["auth", "--init"])

    assert result.exit_code == 0
    assert "data_dir" in result.stdout
    assert "/tmp/foxpilot" in result.stdout
    assert "automation_profile_dir" in result.stdout
    assert "secrets_dir" in result.stdout
    assert "browser_auth" in result.stdout


def test_auth_status_command_explains_storage(monkeypatch):
    monkeypatch.setattr(
        cli,
        "auth_storage_report",
        lambda: {
            "data_dir": "/tmp/foxpilot",
            "automation_profile_dir": "/tmp/foxpilot/automation-profile",
            "secrets_dir": "/tmp/foxpilot/secrets",
            "browser_auth": "browser cookies stay in automation_profile_dir",
            "api_secrets": "non-browser tokens belong in secrets_dir",
            "legacy": "no legacy claude-profile found",
            "status": "private",
        },
    )

    result = runner.invoke(cli.app, ["auth", "status"])

    assert result.exit_code == 0
    assert "automation_profile_dir" in result.stdout
    assert "browser_auth" in result.stdout
    assert "legacy" in result.stdout


def test_auth_explain_command_describes_browser_vs_api_secrets():
    result = runner.invoke(cli.app, ["auth", "explain"])

    assert result.exit_code == 0
    assert "automation-profile" in result.stdout
    assert "browser cookies" in result.stdout
    assert "API tokens" in result.stdout


def test_import_cookies_accepts_repeatable_domain_options(monkeypatch):
    seen = {}

    def fake_import_cookies(**kwargs):
        seen.update(kwargs)
        return {
            "src": "/tmp/source-profile",
            "dst": "/tmp/foxpilot/automation-profile",
            "cookies_copied": 2,
            "storage_copied": False,
            "passwords_copied": False,
        }

    monkeypatch.setattr(cli, "import_cookies", fake_import_cookies)

    result = runner.invoke(
        cli.app,
        [
            "import-cookies",
            "--domain",
            "youtube.com",
            "--domain",
            "google.com",
        ],
    )

    assert result.exit_code == 0
    assert seen["domain"] == ["youtube.com", "google.com"]
    assert "filtered to *youtube.com*, *google.com*" in result.stdout
