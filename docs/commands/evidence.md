# `foxpilot evidence`

Evidence bundles capture the current browser state into a small audit directory. They are intended for agent workflows where a human may need to review what page was open, what visible text was present, and what artifacts were available when a command ran.

## Bundle Contents

The CLI command is backed by `create_evidence_bundle(driver, output_dir, *, command="", plugin="", mode="")`.

When the browser driver supports the relevant capabilities, a bundle includes:

| File | Purpose |
|---|---|
| `bundle.json` | Metadata, command context, artifact list, and redaction summary. |
| `url.txt` | The current browser URL. |
| `readable.txt` | Best-effort visible page text from `document.body.innerText`. |
| `page.html` | Best-effort page HTML from `driver.page_source`. |
| `screenshot.png` | Best-effort screenshot from `driver.save_screenshot`. |

Drivers that do not expose screenshots, page source, or JavaScript execution are handled gracefully. The bundle records only the artifacts that could be captured.

## Usage

```bash
foxpilot evidence bundle /tmp/task-name
foxpilot evidence bundle /tmp/task-name --json
foxpilot evidence bundle /tmp/github-check --plugin github --command "github repo" --json
```

Plugin and mission code can use the same foundation directly:

```python
from foxpilot.evidence import create_evidence_bundle

bundle = create_evidence_bundle(
    driver,
    "/tmp/task-name",
    command="github repo",
    plugin="github",
    mode="visible",
)
```

The returned dictionary matches the saved `bundle.json` content.

## Privacy Notes

Evidence files are redacted before writing wherever the foundation handles text, HTML, JSON, or URLs. Current redaction targets obvious secret shapes:

- `password=...`
- `token=...`
- `api_key=...` and `api-key=...`
- `Authorization: Bearer ...`

Redaction is best effort. Screenshots may still contain sensitive visible data because image redaction is not part of this foundation. Prefer capturing evidence only into trusted local directories, and review bundles before sharing them outside the machine.

## Failure Modes

- Missing `screenshot.png`: the driver does not support `save_screenshot`, or screenshot capture failed.
- Missing `page.html`: the driver does not expose `page_source`.
- Missing `readable.txt`: the driver does not support JavaScript execution, or page text extraction failed.
- Empty text artifacts: the page may be blank, blocked, cross-origin restricted, or still loading.
