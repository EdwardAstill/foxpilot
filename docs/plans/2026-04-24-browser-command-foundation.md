# Browser Command Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development to implement this plan task-by-task. For same-session manual execution, route back through `executor`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Foxpilot's browser commands reliable, testable, and consistent across CLI and MCP.

**Machine plan:** 2026-04-24-browser-command-foundation.yaml

**Architecture:** Introduce a shared command service layer that owns browser-backed behavior once. The CLI and MCP server become thin adapters that call the same functions and format the same result objects for their surface.

**Tech Stack:** Python 3.11+, Typer, Selenium, MCP FastMCP, unittest, local HTML fixtures.

---

## Executive Decision

Keep MCP, but treat it as an adapter, not a second implementation.

MCP is valuable for agent workflows because it gives Claude Code and similar clients direct tool calls with named arguments, structured affordances, and no shell parsing. It is costly because every browser command exposed through MCP can drift from the CLI if logic is duplicated. The plan below keeps the benefits by routing MCP through the same shared actions as the CLI.

## MCP Cost-Benefit Analysis

### Benefits

- **Agent ergonomics:** MCP tools are easier for agents to call correctly than shell commands with positional arguments.
- **Lower parsing risk:** Named parameters like `description`, `mode`, and `visible` avoid shell quoting and output scraping problems.
- **Better future contract:** MCP can eventually return structured JSON-like payloads while CLI keeps human-readable text.
- **Natural integration:** Browser automation is a strong MCP use case because the agent can reason in tool calls rather than subprocess text.
- **Mode control:** MCP can expose `mode="claude" | "zen" | "headless"` directly without relying on global CLI flags.

### Costs

- **Duplicate surface area:** Every CLI command mirrored in MCP doubles maintenance unless shared functions exist.
- **Behavior drift:** The current MCP `click` and `fill` already diverge from CLI behavior.
- **Test burden:** CLI and MCP both need contract tests, even when they use the same core action.
- **Error handling complexity:** MCP users need concise error strings or structured failures, not raw Selenium tracebacks.
- **Dependency footprint:** The MCP package is an always-installed runtime dependency today, even for users who only want the CLI.

### Decision Rules

- Keep MCP when the command is useful to agents as a reusable tool.
- Do not expose an MCP tool until the equivalent shared action has tests.
- MCP tools must not contain browser behavior beyond argument normalization and output formatting.
- MCP should stay optional only if install size or dependency conflicts become a real user problem.
- CLI remains the canonical human interface; shared action functions are the canonical implementation.

## Target File Structure

```text
src/foxpilot/
  actions.py              # shared browser command implementations
  results.py              # CommandResult and formatting helpers
  doctor.py               # environment diagnostics
  cli.py                  # thin Typer adapter
  mcp_server.py           # thin MCP adapter
tests/
  fixtures/
    browser_form.html
    browser_content.html
  test_actions.py
  test_cli_surface.py
  test_doctor.py
```

## Implementation Tasks

### Task 1: Standardize Test Command

**Files:**
- Modify: `docs/plans/2026-04-24-browser-command-foundation.md`

- [x] **Step 1: Use the stdlib test runner for this pass**

The current tests are `unittest` tests and run without adding new dependencies.

- [x] **Step 2: Verify tests can run with normal command**

Run:

```bash
./.venv/bin/python -m unittest discover -s tests -v
```

Expected: tests pass, with browser smoke skipped in restricted sandboxes.

- [ ] **Step 3: Optional future pytest migration**

Once network/cache is healthy, add pytest as a dev dependency if richer markers and fixtures become necessary.

- [ ] **Step 4: Commit**

```bash
git add tests docs/plans/2026-04-24-browser-command-foundation.md
git commit -m "test: standardize unittest command"
```

### Task 2: Add Shared Result Type

**Files:**
- Create: `src/foxpilot/results.py`
- Test: `tests/test_results.py`

- [ ] **Step 1: Write failing tests**

Create tests for successful and failed result formatting:

```python
from foxpilot.results import CommandResult


def test_command_result_text_includes_message_and_page_state():
    result = CommandResult(
        ok=True,
        message="clicked button",
        title="Example",
        url="https://example.test",
        visible_text="Done",
    )

    assert "clicked button" in result.to_text()
    assert "title: Example" in result.to_text()
    assert "url: https://example.test" in result.to_text()
    assert "Done" in result.to_text()


def test_command_result_failure_text_is_clear():
    result = CommandResult(ok=False, message="no input found")

    assert result.to_text() == "x no input found"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python -m unittest discover -s tests -p 'test_results.py' -v
```

Expected: import fails because `foxpilot.results` does not exist.

- [ ] **Step 3: Implement minimal result object**

Create:

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CommandResult:
    ok: bool
    message: str
    title: str = ""
    url: str = ""
    visible_text: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    def to_text(self) -> str:
        prefix = "OK" if self.ok else "x"
        lines = [f"{prefix} {self.message}"]
        if self.url:
            lines.append(f"url: {self.url}")
        if self.title:
            lines.append(f"title: {self.title}")
        if self.visible_text:
            lines.append("visible:")
            lines.extend(f"  {line}" for line in self.visible_text.splitlines())
        return "\n".join(lines)
```

- [x] **Step 4: Run test to verify it passes**

Run:

```bash
./.venv/bin/python -m unittest discover -s tests -p 'test_results.py' -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/foxpilot/results.py tests/test_results.py
git commit -m "feat: add shared command result"
```

### Task 3: Extract Shared Action Layer

**Files:**
- Create: `src/foxpilot/actions.py`
- Modify: `src/foxpilot/cli.py`
- Modify: `src/foxpilot/mcp_server.py`
- Test: `tests/test_actions.py`

- [ ] **Step 1: Write unit tests with fake drivers**

Use fake drivers/elements to test behavior without opening Firefox:

```python
from foxpilot.actions import click_action, fill_action


class FakeElement:
    tag_name = "button"
    text = "Submit"

    def __init__(self, fail_click=False):
        self.fail_click = fail_click
        self.clicked = False
        self.value = ""

    def click(self):
        if self.fail_click:
            raise RuntimeError("intercepted")
        self.clicked = True

    def clear(self):
        self.value = ""

    def send_keys(self, value):
        self.value += value

    def get_attribute(self, name):
        return ""


class FakeDriver:
    title = "Fixture"
    current_url = "https://fixture.test"

    def __init__(self, element):
        self.element = element
        self.scripts = []

    def execute_script(self, script, *args):
        self.scripts.append(script)


def test_click_action_uses_js_fallback_when_native_click_fails(monkeypatch):
    element = FakeElement(fail_click=True)
    driver = FakeDriver(element)
    monkeypatch.setattr("foxpilot.actions.find_element", lambda *args, **kwargs: element)
    monkeypatch.setattr("foxpilot.actions.read_page", lambda *args, **kwargs: "")

    result = click_action(driver, "Submit")

    assert result.ok is True
    assert driver.scripts == ["arguments[0].click();"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
./.venv/bin/python -m unittest discover -s tests -p 'test_actions.py' -v
```

Expected: `foxpilot.actions` does not exist.

- [ ] **Step 3: Implement action functions**

Create functions for the first high-risk duplicated commands:

```python
from selenium.webdriver.common.keys import Keys

from foxpilot.core import describe_element, find_element, find_input_element, read_page
from foxpilot.results import CommandResult


def page_state(driver) -> dict[str, str]:
    return {
        "title": driver.title,
        "url": driver.current_url,
        "visible_text": read_page(driver, max_chars=1200),
    }


def click_action(driver, description: str, role: str | None = None, tag: str | None = None) -> CommandResult:
    el = find_element(driver, description, role=role, tag=tag)
    if not el:
        return CommandResult(ok=False, message=f"no element found matching '{description}'")
    desc = describe_element(el)
    try:
        el.click()
    except Exception:
        driver.execute_script("arguments[0].click();", el)
    return CommandResult(ok=True, message=f"clicked {desc}", **page_state(driver))


def fill_action(driver, description: str, value: str, submit: bool = False) -> CommandResult:
    el = find_input_element(driver, description)
    if not el:
        return CommandResult(ok=False, message=f"no input found for '{description}'")
    desc = describe_element(el)
    el.clear()
    el.send_keys(value)
    if submit:
        el.send_keys(Keys.RETURN)
        return CommandResult(ok=True, message=f"filled {desc} + submitted", **page_state(driver))
    return CommandResult(ok=True, message=f"filled {desc} with '{value}'", **page_state(driver))
```

- [ ] **Step 4: Route CLI and MCP through shared functions**

In CLI:

```python
from foxpilot.actions import click_action, fill_action


result = click_action(driver, description, role=role, tag=tag)
typer.echo(result.to_text())
if not result.ok:
    raise typer.Exit(1)
```

In MCP:

```python
from foxpilot.actions import click_action, fill_action


return click_action(driver, description, role=role or None, tag=tag or None).to_text()
```

- [x] **Step 5: Run tests**

Run:

```bash
./.venv/bin/python -m unittest discover -s tests -p 'test_actions.py' -v
./.venv/bin/python -m unittest discover -s tests -p 'test_youtube_site.py' -v
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add src/foxpilot/actions.py src/foxpilot/cli.py src/foxpilot/mcp_server.py tests/test_actions.py
git commit -m "refactor: share click and fill actions"
```

### Task 4: Add Browser Fixture Smoke Tests

**Files:**
- Create: `tests/fixtures/browser_form.html`
- Create: `tests/fixtures/browser_content.html`
- Create: `tests/test_browser_smoke.py`

- [ ] **Step 1: Create local fixture pages**

`tests/fixtures/browser_form.html`:

```html
<!doctype html>
<html>
  <head><title>Foxpilot Form Fixture</title></head>
  <body>
    <main>
      <h1>Form Fixture</h1>
      <label for="username">Username</label>
      <input id="username" name="username" placeholder="Username">
      <button id="submit" onclick="document.body.dataset.clicked='yes'">Submit</button>
      <select id="plan" aria-label="Plan">
        <option value="free">Free</option>
        <option value="pro">Pro</option>
      </select>
    </main>
  </body>
</html>
```

- [ ] **Step 2: Write browser smoke tests**

Use `browser(mode="headless")` and `file://` URLs:

```python
from pathlib import Path

from foxpilot.actions import click_action, fill_action
from foxpilot.core import browser


def fixture_url(name: str) -> str:
    return Path("tests/fixtures", name).resolve().as_uri()


def test_headless_fill_and_click_fixture():
    with browser(mode="headless") as driver:
        driver.get(fixture_url("browser_form.html"))
        fill = fill_action(driver, "Username", "alice")
        click = click_action(driver, "Submit", tag="button")

        assert fill.ok is True
        assert click.ok is True
        assert driver.find_element("id", "username").get_attribute("value") == "alice"
        assert driver.execute_script("return document.body.dataset.clicked") == "yes"
```

- [x] **Step 3: Run smoke tests locally**

Run:

```bash
./.venv/bin/python -m unittest discover -s tests -p 'test_browser_smoke.py' -v
```

Expected outside restricted sandbox: pass. In this sandbox it skips because local WebDriver socket binding is unavailable.

- [x] **Step 4: Mark sandbox-sensitive tests**

The unittest smoke test skips with a clear message when Selenium cannot bind the local WebDriver socket.

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures tests/test_browser_smoke.py
git commit -m "test: add local browser smoke fixtures"
```

### Task 5: Add `foxpilot doctor`

**Files:**
- Create: `src/foxpilot/doctor.py`
- Modify: `src/foxpilot/cli.py`
- Test: `tests/test_doctor.py`

- [ ] **Step 1: Write failing doctor tests**

```python
from foxpilot.doctor import run_diagnostics


def test_doctor_reports_socket_bind_status():
    report = run_diagnostics()

    assert "socket_bind" in report
    assert "ok" in report["socket_bind"]
```

- [ ] **Step 2: Implement diagnostics**

Checks:

- Python version
- `geckodriver` on PATH
- Firefox on PATH
- `zen-browser` on PATH
- local socket bind availability
- Hyprland `hyprctl` availability
- claude profile parent writability

- [ ] **Step 3: Add CLI command**

```python
@app.command(name="doctor")
def cmd_doctor():
    """Check local Foxpilot browser automation prerequisites."""
```

- [x] **Step 4: Run tests**

Run:

```bash
./.venv/bin/python -m unittest discover -s tests -p 'test_doctor.py' -v
./.venv/bin/foxpilot doctor
```

Expected: command reports each check as pass, fail, or warning.

- [ ] **Step 5: Commit**

```bash
git add src/foxpilot/doctor.py src/foxpilot/cli.py tests/test_doctor.py
git commit -m "feat: add doctor diagnostics"
```

### Task 6: Fix Lifecycle Command Truthfulness

**Files:**
- Modify: `src/foxpilot/core.py`
- Modify: `src/foxpilot/cli.py`
- Modify: `src/foxpilot/mcp_server.py`
- Test: `tests/test_lifecycle.py`

- [ ] **Step 1: Write failing tests**

Test `show` and `hide` when no claude window exists:

```python
from foxpilot.core import claude_hide, claude_show


def test_show_reports_not_running_when_no_window(monkeypatch):
    monkeypatch.setattr("foxpilot.core._find_claude_window", lambda: None)

    result = claude_show()

    assert result["status"] == "not_running"
```

- [ ] **Step 2: Change core lifecycle functions to return status**

Return one of:

- `changed`
- `already_visible`
- `already_hidden`
- `not_running`

- [ ] **Step 3: Update CLI and MCP output**

CLI should print `x claude window not running` and exit nonzero for `not_running`.

MCP should return the same clear message string.

- [x] **Step 4: Run tests**

Run:

```bash
./.venv/bin/python -m unittest discover -s tests -p 'test_lifecycle.py' -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/foxpilot/core.py src/foxpilot/cli.py src/foxpilot/mcp_server.py tests/test_lifecycle.py
git commit -m "fix: report lifecycle no-op states"
```

### Task 7: Fix Module Execution

**Files:**
- Modify: `src/foxpilot/cli.py`
- Test: `tests/test_cli_surface.py`

- [ ] **Step 1: Write failing test**

```python
import subprocess
import sys


def test_module_execution_shows_help():
    result = subprocess.run(
        [sys.executable, "-m", "foxpilot.cli", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Usage:" in result.stdout
```

- [ ] **Step 2: Add module entry block**

At bottom of `src/foxpilot/cli.py`:

```python
if __name__ == "__main__":
    _run()
```

- [x] **Step 3: Run test**

Run:

```bash
./.venv/bin/python -m unittest discover -s tests -p 'test_cli_surface.py' -v
```

Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add src/foxpilot/cli.py tests/test_cli_surface.py
git commit -m "fix: support python module execution"
```

## Verification Gate

Before calling this complete, run:

```bash
./.venv/bin/python -m unittest discover -s tests -v
./.venv/bin/foxpilot --help
./.venv/bin/foxpilot doctor
./.venv/bin/foxpilot youtube help
```

On a non-sandboxed machine with local socket binding available, also run:

```bash
./.venv/bin/python -m unittest discover -s tests -p 'test_browser_smoke.py' -v
./.venv/bin/foxpilot --headless-mode go file://$(pwd)/tests/fixtures/browser_content.html
```

## Order Rationale

1. Dev tooling first makes every later task easy to verify.
2. Shared result objects give CLI and MCP a common return contract.
3. Shared actions fix the highest-risk architecture issue: duplicated behavior.
4. Browser fixture tests prove real features without relying on live websites.
5. `doctor` explains environment problems before users hit Selenium tracebacks.
6. Lifecycle truthfulness cleans up false success messages.
7. Module execution is small and isolated, so it can land late without disturbing the main refactor.
