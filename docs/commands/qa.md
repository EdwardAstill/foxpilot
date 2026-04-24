# `foxpilot qa`

Visual QA Mode captures a small report bundle for a page and flags obvious rendering problems.

## Planned Command

```bash
foxpilot qa http://localhost:3000
```

## Output

The report directory contains:

```text
qa-report.json
desktop.png
mobile.png
fullpage.png
summary.md
```

## Checks

The standalone QA helpers currently support:

- Desktop screenshot capture.
- Mobile screenshot capture.
- Full-page screenshot placeholder capture through the available driver API.
- Console error collection when the driver supports browser logs.
- Blank page detection from visible text or HTML.
- Missing image detection from browser-provided image data.

Text overflow and contrast checks are planned as future report enhancements.

## Driver Expectations

`build_qa_report(driver, url, output_dir)` is intentionally fake-driver friendly. It uses methods only when present:

- `get(url)`
- `set_window_size(width, height)`
- `save_screenshot(path)` or `get_screenshot_as_file(path)`
- `execute_script(script)`
- `get_log("browser")`
