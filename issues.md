# Foxpilot Feature Test Issues

Date: 2026-04-24

## Current Test Status

Verified after the browser-command foundation changes:

- CLI help renders from the installed `foxpilot` entrypoint.
- `python -m foxpilot.cli --help` now renders help.
- `foxpilot youtube help` works.
- Shared action unit tests cover CLI/MCP drift risks for `click` and `fill`.
- Lifecycle tests cover `show` / `hide` no-op states.
- `foxpilot doctor` reports dependency and environment state.

Automated test result:

- `./.venv/bin/python -m unittest discover -s tests -v`
- 81 tests run
- 80 passed
- 1 skipped because this sandbox cannot bind the local WebDriver socket

## Verified Commands

```bash
./.venv/bin/python -m unittest discover -s tests -v
./.venv/bin/foxpilot --help
./.venv/bin/python -m foxpilot.cli --help
./.venv/bin/foxpilot youtube help
./.venv/bin/foxpilot doctor
./.venv/bin/foxpilot show
```

## Live Findings

### 1. Browser-backed commands cannot be exercised in this sandbox

Severity: Environment blocker

Reproduction:

```bash
UV_CACHE_DIR=/tmp/uv-cache UV_PYTHON_INSTALL_DIR=/tmp/uv-python \
  uv run python - <<'PY'
from foxpilot.core import browser
with browser(mode='headless') as driver:
    driver.get('data:text/html,<title>ok</title><h1>Hello</h1>')
PY
```

Observed:

- Selenium fails before browser interaction begins.
- Underlying error is `PermissionError: [Errno 1] Operation not permitted`.
- geckodriver setup then raises `RuntimeError: Can't find free port (Unable to bind to IPv4 or IPv6)`.
- `foxpilot doctor` reports `socket_bind` as failed for the same reason.

Reference:

- [src/foxpilot/core.py](/home/eastill/projects/foxpilot/src/foxpilot/core.py:502)
- [src/foxpilot/doctor.py](/home/eastill/projects/foxpilot/src/foxpilot/doctor.py:21)

Impact:

This prevents end-to-end verification of live Firefox behavior in this session. The new smoke test is present and will run on a normal machine, but it skips here with a clear reason.

### 2. `uv sync` cannot rebuild the project while DNS is blocked

Severity: Environment blocker

Observed:

- `uv sync` resolves dependencies but fails while building the editable project.
- The isolated build environment needs `hatchling`.
- DNS lookup for `pypi.org` fails before `hatchling` can be fetched.

Impact:

The existing `.venv` is still usable for tests and CLI smoke checks, but this sandbox cannot recreate the environment from scratch until PyPI DNS works or `hatchling` is available in cache.

### 3. Claude profile parent is not writable in this sandbox

Severity: Environment blocker

Observed:

- `foxpilot doctor` reports `/home/eastill/.local/share` is not writable.

Impact:

Commands that need to create or update the claude browser profile may fail here. This is separate from browser socket binding.

## Resolved During Session

- `python -m foxpilot.cli --help` now works.
- MCP `click` now uses the same shared action path as CLI `click`.
- MCP `fill` now uses the same shared action path as CLI `fill`.
- `show` and `hide` now report `not_running`, `already_visible`, `already_hidden`, or `changed` instead of unconditional success.
- Added `foxpilot doctor`.
- Added local browser fixture smoke test.
- Added shared `CommandResult`.
- Added shared `click_action` and `fill_action`.
- CLI browser startup failures now print a concise error instead of a traceback.
