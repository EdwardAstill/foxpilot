# `foxpilot page`

Generic page inspection helpers for turning the current browser page into stable, structured data.

The page branch is useful before choosing a site-specific command and after navigation when an agent needs to know what a page contains, what can be clicked, what forms exist, or how the page is described by metadata and accessibility landmarks.

## Mode Support

| Command | claude | visible | zen | headless |
|---|---:|---:|---:|---:|
| `help` | yes | yes | yes | yes |
| `outline` | yes | yes | yes | best effort |
| `links` | yes | yes | yes | best effort |
| `forms` | yes | yes | yes | best effort |
| `buttons` | yes | yes | yes | best effort |
| `inputs` | yes | yes | yes | best effort |
| `metadata` | yes | yes | yes | best effort |
| `landmarks` | yes | yes | yes | best effort |
| `understand` | yes | yes | yes | best effort |

Headless mode is best effort because some sites require login, cookies, JavaScript state, or anti-bot checks that work better in a persisted browser profile.

## Workflow

Navigate first, then inspect the current page:

```bash
foxpilot go https://example.com
foxpilot page outline
foxpilot page links --external
foxpilot page forms --json
foxpilot page understand --json
```

Use `--zen` when the target page only exists in your real browser session:

```bash
foxpilot --zen page inputs
```

## Commands

### `help`

Show branch examples and mode guidance.

```bash
foxpilot page help
```

### `outline`

Extract the visible heading outline from the current page.

```bash
foxpilot page outline
foxpilot page outline --limit 20
foxpilot page outline --json
```

Returned fields include heading level, text, id, and a best-effort CSS selector.

### `links`

Extract visible links from the current page.

```bash
foxpilot page links
foxpilot page links --internal
foxpilot page links --external
foxpilot page links --all --limit 50
foxpilot page links --json
```

`--internal`, `--external`, and `--all` are mutually exclusive. If no filter is supplied, `--all` is implied.

Returned fields include text, href, title, rel, target, internal/external classification, and selector.

### `forms`

Extract forms and their visible controls.

```bash
foxpilot page forms
foxpilot page forms --json
```

Returned fields include form label, method, action, id, name, selector, visible fields, and visible buttons.

### `buttons`

Extract visible buttons and button-like controls.

```bash
foxpilot page buttons
foxpilot page buttons --limit 25
foxpilot page buttons --json
```

Returned fields include type, label/text, name, id, disabled state, and selector.

### `inputs`

Extract visible input, select, and textarea controls.

```bash
foxpilot page inputs
foxpilot page inputs --json
```

Returned fields include type, label, name, id, placeholder, autocomplete, required state, disabled state, checked state, and selector.

### `metadata`

Extract title, URL, canonical URL, language, charset, viewport, robots, favicon, Open Graph metadata, Twitter metadata, and other meta tags.

```bash
foxpilot page metadata
foxpilot page metadata --json
```

### `landmarks`

Extract accessible landmarks from the current page.

```bash
foxpilot page landmarks
foxpilot page landmarks --json
```

Landmarks include semantic elements such as `main`, `nav`, `aside`, top-level `header`, top-level `footer`, labelled `form`, labelled `section`, and explicit ARIA landmark roles.

### `understand`

Return an agent-friendly map of the current page in one command.

```bash
foxpilot page understand
foxpilot page understand --json
foxpilot page understand --limit 50
```

The result includes title, URL, headings, forms, buttons, inputs, links, visible errors, dangerous actions, and suggested next actions. Use this before choosing click/fill steps or before a mission needs a page-state checkpoint.

## JSON Output

Every inspection command supports `--json`. This is the preferred output when another agent or script will consume the result.

Example link result:

```json
{
  "text": "Docs",
  "href": "https://docs.example.com/",
  "title": "Documentation",
  "rel": "",
  "target": "",
  "is_internal": false,
  "selector": "nav > a:nth-of-type(1)"
}
```

Example input result:

```json
{
  "tag": "input",
  "type": "email",
  "label": "Email address",
  "text": "",
  "name": "email",
  "id": "email",
  "placeholder": "you@example.com",
  "autocomplete": "email",
  "required": true,
  "disabled": false,
  "checked": false,
  "selector": "input#email"
}
```

## Failure Modes

- Empty output: the page may not expose that element type, or controls may be hidden behind a collapsed UI.
- Login required: use the default `claude` profile after login, or retry with `--zen`.
- JavaScript-rendered pages: wait for the page to finish rendering before inspecting.
- Headless blocked: retry in the default profile or with `--visible`.
