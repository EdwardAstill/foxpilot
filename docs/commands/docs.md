# `foxpilot docs`

Documentation helpers for common agent workflows: search official docs, open a likely result, read the current docs page, list links, and extract code examples.

## Site Registry

| Key | Target |
|---|---|
| `python` | `https://docs.python.org/3/` |
| `mdn` | `https://developer.mozilla.org/en-US/docs/Web` |
| `react` | `https://react.dev/reference/react` |
| `typescript` | `https://www.typescriptlang.org/docs/` |
| `typer` | `https://typer.tiangolo.com/` |
| `selenium` | `https://www.selenium.dev/documentation/` |

Use `--site KEY` to scope search or link extraction to one target.

## Mode Support

| Command | claude | visible | zen | headless |
|---|---:|---:|---:|---:|
| `help` | yes | yes | yes | yes |
| `search` | yes | yes | yes | best effort |
| `open` | yes | yes | yes | best effort |
| `read` | yes | yes | yes | yes |
| `links` | yes | yes | yes | yes |
| `examples` | yes | yes | yes | yes |

Most documentation pages are public and should work without authentication. Search providers may still show bot checks or render different result markup in headless mode.

## Commands

### `help`

Show branch examples, registry keys, and mode guidance.

```bash
foxpilot docs help
foxpilot docs help --json
```

### `search <query>`

Search known official documentation targets.

```bash
foxpilot docs search "pathlib glob" --site python
foxpilot docs search "querySelector" --site mdn --limit 5
foxpilot docs search "useEffect cleanup" --site react --json
foxpilot docs search "webdriver wait" --site selenium
```

Search returns title, URL, detected site key, and a best-effort snippet when the search page exposes one.

### `open <target>`

Open a documentation URL, a registry-relative path, or the first docs result for a query.

```bash
foxpilot docs open https://docs.python.org/3/library/pathlib.html
foxpilot docs open /library/pathlib.html --site python
foxpilot docs open "useEffect cleanup" --site react
```

For plain queries, Foxpilot opens a scoped search page first and then follows the first visible matching docs result when one is available.

### `read [selector]`

Read visible content from the current documentation page.

```bash
foxpilot docs read
foxpilot docs read main --full
foxpilot docs read "#examples" --json
```

By default output is truncated for terminal use. Pass `--full` for a larger extraction.

### `links`

List visible links from the current documentation page.

```bash
foxpilot docs links
foxpilot docs links --site python
foxpilot docs links --limit 20 --json
```

Use `--site` to keep only links that match one registry target.

### `examples`

Extract code blocks and inline code examples from the current documentation page.

```bash
foxpilot docs examples
foxpilot docs examples --lang python
foxpilot docs examples --lang typescript --json
```

Language detection is based on common code-block classes such as `language-python`, `lang-ts`, and `highlight-js`.

## JSON Output

Structured commands support `--json`.

Search result shape:

```json
{
  "title": "pathlib - Object-oriented filesystem paths",
  "url": "https://docs.python.org/3/library/pathlib.html",
  "site": "python",
  "snippet": "Classes representing filesystem paths."
}
```

Read result shape:

```json
{
  "title": "pathlib",
  "url": "https://docs.python.org/3/library/pathlib.html",
  "site": "python",
  "selector": "",
  "chars": 12000,
  "truncated": true,
  "text": "..."
}
```

## Failure Modes

- Unknown site key: run `foxpilot docs help` to list the registry.
- Search page challenge: retry with the default `claude` profile or `--zen`.
- No matching result: run `foxpilot docs search <query> --site <key>` and inspect visible results.
- Selector missing: rerun `foxpilot docs read` without a selector or inspect links/headings from the page.
