# foxpilot

Firefox browser automation for AI agents. Controls headless Firefox for independent web research, or connects to a running [Zen browser](https://zen-browser.app/) session to act with your existing logins and cookies.

Available as both a **CLI tool** and an **MCP server** for Claude Code.

---

## Installation

```bash
pip install -e .
```

Requires:
- Python 3.11+
- Firefox installed
- `geckodriver` on `PATH` (for Zen mode and headless)

---

## Modes

| Mode | Description |
|---|---|
| `headless` | Launches a fresh, ephemeral Firefox instance. No existing session. Default. |
| `zen` | Connects to your running Zen browser via Marionette (port 2828). Uses your cookies and logins. |

### Starting Zen with remote access

Zen must be launched with the `--marionette` flag:

```bash
zen-browser --marionette
```

- `--marionette` — enables the WebDriver control connection on port 2828

Tab listing and switching use Marionette directly — no `--remote-debugging-port` needed.

---

## CLI

### Global flag

```bash
foxpilot [--zen] <command> [args]
```

Pass `--zen` / `-z` before the command to operate on your running Zen browser. Omit it for headless.

### Observation commands

#### `tabs`

List all open tabs. Marks the active tab with `>`. Requires `--zen` and Zen running with `--marionette`.

```bash
foxpilot --zen tabs
```

#### `url`

Print the current page URL and title.

```bash
foxpilot url
foxpilot --zen url
```

#### `read [selector] [--tab <tab>] [--full]`

Extract readable text from the current page.

```
selector   CSS selector to scope extraction (optional)
--tab, -t  Switch to this tab first (index or URL/title substring)
--full     Disable truncation (default cap: 3000 chars)
```

```bash
foxpilot read
foxpilot read "article.main"
foxpilot --zen read --tab github --full
```

#### `find <text>`

Find all visible elements containing the given text (checks text content, `aria-label`, `placeholder`, `title`).

```bash
foxpilot find "Sign in"
foxpilot --zen find "Submit"
```

#### `screenshot [path] [--el <selector>] [--tab <tab>]`

Take a screenshot and save to disk.

```
path        Output path (default: /tmp/foxpilot-snap.png)
--el        CSS selector to capture a specific element
--tab, -t   Switch to this tab first
```

```bash
foxpilot screenshot /tmp/page.png
foxpilot --zen screenshot --el "#header"
```

#### `html [selector]`

Extract raw HTML from the page body (truncated to 8000 chars) or a specific element.

```bash
foxpilot html
foxpilot html ".sidebar"
```

### Action commands

#### `go <url>`

Navigate to a URL. Returns the new page state.

```bash
foxpilot go https://example.com
foxpilot --zen go https://github.com
```

#### `search <query>`

Search via DuckDuckGo HTML interface and return structured results.

```bash
foxpilot search "python asyncio tutorial"
```

#### `click <description> [--role <role>] [--tag <tag>]`

Click a visible element found by text, `aria-label`, or placeholder.

```
description  Text or label to match
--role, -r   Filter by ARIA role (e.g. button, link)
--tag, -t    Filter by HTML tag (e.g. button, a)
```

```bash
foxpilot click "Sign in"
foxpilot click "Submit" --role button
foxpilot --zen click "New issue" --tag a
```

#### `fill <description> <value> [--submit]`

Fill a text input found by label, placeholder, or `aria-label`.

```
description  Label or placeholder text
value        Text to type
--submit, -s Press Enter after filling
```

```bash
foxpilot fill "Search" "foxpilot"
foxpilot fill "Username" "alice" 
foxpilot fill "Password" "secret" --submit
```

#### `select <description> <value>`

Select a `<select>` dropdown option by visible text or value attribute.

```bash
foxpilot select "Country" "United Kingdom"
```

#### `scroll [--y <pixels>] [--to <selector>]`

Scroll the page.

```
--y     Pixels to scroll (negative = up, default: 600)
--to    CSS selector to scroll into view (overrides --y)
```

```bash
foxpilot scroll --y 1200
foxpilot scroll --y -600
foxpilot scroll --to "#footer"
```

#### `back` / `forward`

Navigate browser history.

```bash
foxpilot back
foxpilot forward
```

#### `key <name> [--focus <selector>]`

Press a keyboard key on the active element.

```
name     Key name (see table below)
--focus  CSS selector to focus/click before pressing the key
```

Supported keys: `enter`, `tab`, `escape`, `space`, `backspace`, `delete`, `arrowup`, `arrowdown`, `arrowleft`, `arrowright`, `home`, `end`, `pageup`, `pagedown`

```bash
foxpilot key enter
foxpilot key escape --focus "#modal-close"
foxpilot key arrowdown --focus "select#sort"
```

### Tab management

#### `tab <target>`

Switch to a tab in the Zen browser UI by index or substring match. Requires `--zen`.

```bash
foxpilot --zen tab 2
foxpilot --zen tab github
```

#### `new-tab [url]`

Open a new tab, optionally navigating to a URL.

```bash
foxpilot new-tab
foxpilot --zen new-tab https://example.com
```

#### `close-tab [index]`

Close a tab. Omit index to close the current tab.

```bash
foxpilot close-tab
foxpilot --zen close-tab 3
```

### Design inspection

Three commands for capturing a page's visual design — useful for replicating styles, auditing design systems, or extracting assets.

#### `styles [selector]`

Extract computed CSS properties, design tokens (CSS custom properties), and the full color palette from any element on the page.

```
selector   CSS selector to inspect (default: body)
```

```bash
foxpilot --zen styles
foxpilot --zen styles "nav"
foxpilot --zen styles ".hero-section"
foxpilot --zen styles ":root"
```

**Computed styles** covers the key visual properties: `color`, `background-color`, `font-family`, `font-size`, `font-weight`, `line-height`, `letter-spacing`, `text-transform`, `border-radius`, `box-shadow`, `padding`, `margin`, `gap`, `display`, `border`, `opacity`.

**CSS variables** scans all stylesheets for `:root` declarations and dumps every custom property — this is where design systems store their tokens (colors, spacing scale, type scale, etc.).

**Colors** scans up to 300 elements and collects every unique value from `color`, `background-color`, and `border-color` — giving you the full palette in use.

Example output:

```
[body]
https://example.com

── computed styles ──
  background-color             rgb(4, 28, 28)
  color                        color(srgb 1 0.9 0.8)
  font-family                  "Mondwest", sans-serif
  font-size                    14px
  font-weight                  400
  line-height                  21px
  text-transform               uppercase

── css variables (15) ──
  --background-base                        #041C1C
  --foreground-base                        #FFFFFF
  --midground-base                         #ffe6cb
  --font-sans                              "Collapse", sans-serif
  --font-mono                              "Courier Prime", monospace

── colors on page (12) ──
  rgb(4, 28, 28)
  color(srgb 1 0.9 0.8)
  oklab(0.938 0.016 0.042 / 0.2)
```

#### `assets`

Extract all assets from the current page in a single pass.

```bash
foxpilot --zen assets
```

Output includes:

| Section | Contents |
|---|---|
| images | URL, natural dimensions (px), alt text |
| font families | All unique `font-family` values found in computed styles |
| loaded fonts | Font face registry: family, weight, style, load status |
| stylesheets | URLs of all external CSS files |
| favicon | Resolved favicon URL |
| background images | CSS `background-image` URLs (excludes `data:` URIs) |
| inline SVGs | `id` or `class` of SVG elements embedded in the HTML |

**Font load status** can be `loaded`, `loading`, or `unloaded`. Only `loaded` fonts are actually active — `unloaded` entries are registered but not yet fetched.

Example output:

```
https://example.com

── images (3) ──
  1444×1444    https://example.com/static/hero.jpg
  200×200      https://example.com/static/logo.svg "Logo"

── font families (4) ──
  "Collapse", sans-serif
  "Mondwest", sans-serif
  "Courier Prime", monospace

── loaded fonts (6) ──
  Mondwest                       weight=400 style=normal [loaded]
  Courier Prime                  weight=400 style=normal [loaded]
  Courier Prime                  weight=700 style=normal [unloaded]

── stylesheets (1) ──
  https://example.com/static/main.css

── favicon ──
  https://example.com/favicon.ico

── background images (2) ──
  https://example.com/static/grain.png
```

#### `fullpage [path]`

Take a full-page screenshot capturing the entire scroll height, not just the visible viewport.

```
path   Output path (default: /tmp/foxpilot-full.png)
```

```bash
foxpilot --zen fullpage
foxpilot --zen fullpage /tmp/mysite-full.png
```

Uses Firefox's native full-page screenshot API (`get_full_page_screenshot_as_file`). Falls back to resizing the viewport to `document.documentElement.scrollHeight` if the native API is unavailable. Maximum height is capped at 16384px to avoid memory issues.

---

### Design replication workflow

To fully capture a page's visual design for replication:

```bash
# 1. Full visual reference
foxpilot --zen fullpage /tmp/reference-full.png

# 2. Design tokens and color palette
foxpilot --zen styles ":root"

# 3. Body / global type and color
foxpilot --zen styles

# 4. Specific section (e.g. navigation)
foxpilot --zen styles "header"

# 5. All assets — fonts, images, stylesheets
foxpilot --zen assets

# 6. Raw stylesheet if you want the actual rules
foxpilot --zen js "[...document.styleSheets].map(s=>s.href)"
# then fetch the stylesheet URL directly
```

The CSS variables output from `styles` maps directly to a design token file. The `assets` font list gives you the exact font names and weights to source. The `fullpage` screenshot gives you the complete layout reference.

---

### Escape hatches

For when text-based matching isn't specific enough:

#### `js <expression>`

Evaluate a JavaScript expression in the page context.

```bash
foxpilot js "document.title"
foxpilot js "document.querySelectorAll('a').length"
```

#### `css-click <selector>`

Click an element by CSS selector.

```bash
foxpilot css-click "#submit-btn"
foxpilot --zen css-click ".modal button[type=submit]"
```

#### `css-fill <selector> <value>`

Fill an input by CSS selector.

```bash
foxpilot css-fill "input[name=email]" "alice@example.com"
```

---

## MCP Server

foxpilot exposes all its tools as an MCP server for use with Claude Code.

### Start the server

```bash
foxpilot mcp
```

### Configure in Claude Code

Add to your MCP settings (`.claude/settings.json` or global settings):

```json
{
  "mcpServers": {
    "foxpilot": {
      "command": "foxpilot",
      "args": ["mcp"],
      "type": "stdio"
    }
  }
}
```

### MCP tools

All CLI commands are available as MCP tools with the same names, plus a `mode` parameter (`"headless"` or `"zen"`). The tab switching command is named `tab_switch` and `new_tab` / `close_tab` use underscores.

| CLI command | MCP tool |
|---|---|
| `tabs` | `tabs` |
| `url` | `url` |
| `read` | `read` |
| `find` | `find` |
| `screenshot` | `screenshot` |
| `html` | `html` |
| `go` | `go` |
| `search` | `search` |
| `click` | `click` |
| `fill` | `fill` |
| `select` | `select` |
| `scroll` | `scroll` |
| `back` | `back` |
| `forward` | `forward` |
| `key` | `key` |
| `tab` | `tab_switch` |
| `new-tab` | `new_tab` |
| `close-tab` | `close_tab` |
| `js` | `js` |
| `css-click` | `css_click` |
| `css-fill` | `css_fill` |
| `styles` | `styles` |
| `assets` | `assets` |
| `fullpage` | `fullpage` |

Screenshot paths returned by the MCP `screenshot` tool can be opened with the Claude Code `Read` tool to view the image.

---

## Python API

```python
from foxpilot.core import browser, read_page, find_element, feedback

# Headless
with browser(mode="headless") as driver:
    driver.get("https://example.com")
    text = read_page(driver)
    print(text)

# Zen
with browser(mode="zen") as driver:
    el = find_element(driver, "Sign in", role="button")
    if el:
        el.click()
    print(feedback(driver, "clicked sign in"))
```

### `browser(mode)`

Context manager. Yields a Selenium `WebDriver`. Automatically quits on exit.

### `list_tabs()`

Returns a list of open tab dicts via Marionette. Each dict has `id` (window handle), `title`, `url`, `active` (bool).

### `activate_tab(tab_id)`

Switch to a tab by its window handle (the `id` field from `list_tabs`).

### `find_element(driver, text, role=None, tag=None)`

Find a visible element by text content, `aria-label`, placeholder, or title. Returns the first visible match or `None`.

### `describe_element(el)`

Return a short human-readable string describing an element: `<tag> role="..." aria-label="..." "text..."`.

### `read_page(driver, selector=None, max_chars=3000)`

Extract readable text from the page. If `selector` is given, scopes to that element. Uses semantic content detection (prefers `article`, `main`, `[role=main]`).

### `extract_styles(driver, selector=None)`

Extract computed styles, CSS custom properties from `:root`, and all colors found on the page. Returns a dict with `element`, `styles`, `cssVars`, `colors`.

### `extract_assets(driver)`

Extract all page assets. Returns a dict with `images`, `fonts`, `fontFamilies`, `stylesheets`, `favicon`, `backgroundImages`, `inlineSvgs`.

### `fullpage_screenshot(driver, path)`

Take a full-page screenshot using Firefox's native API. Falls back to viewport resize. Returns `(path, size_kb)`.

### `feedback(driver, action_msg, selector=None, max_lines=20)`

Return a formatted string combining an action message, current URL, title, and visible page text. Useful for returning state after an action.

---

## Architecture

```
foxpilot/
├── core.py         Browser connection, tab listing, element finding, page reading
├── cli.py          Typer CLI (foxpilot command)
├── mcp_server.py   FastMCP server (foxpilot mcp)
├── search.py       DuckDuckGo search via HTML interface
└── readability.py  Main content extraction heuristics
```
