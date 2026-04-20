# foxpilot

Firefox browser automation for AI agents. Three modes: a dedicated **claude profile** that runs hidden in a Hyprland scratchpad (default), an attach-to-your-real-Zen mode, and a fully ephemeral **headless** mode for stateless research.

Available as both a **CLI tool** and an **MCP server** for Claude Code.

---

## Installation

```bash
pip install -e .
```

Requires:
- Python 3.11+
- Firefox / Zen installed (`zen-browser` on `PATH` for the `claude` and `zen` modes)
- `geckodriver` on `PATH`
- `hyprctl` on `PATH` if you want the hide/show toggling in `claude` mode

---

## Modes

| Mode | Profile | Window | Shares your session? | Use when |
|---|---|---|---|---|
| `claude` (default) | dedicated `~/.local/share/foxpilot/claude-profile` | Hyprland `special:claude` scratchpad (hidden), or active workspace if `--visible` | No — its own profile, you log it in once via `foxpilot login` | The agent should drive a real, authenticated browser without taking over your screen. |
| `zen` | your real Zen profile | your real Zen window | Yes — same tabs, same logins | The agent specifically needs to act on your real browsing session (e.g. open a tab in the window you're using). |
| `headless` | ephemeral, throwaway | none — no display | No | One-shot stateless research where no session is needed and zero side effects are wanted. |

### Claude mode — how it works

`claude` mode launches Zen with `--no-remote --profile <claude-profile-dir> --marionette --marionette-port 2829 --class ClaudeZen`. That gives the dedicated instance:

- **Its own profile dir**, so cookies / extensions / logins are isolated from your main browsing.
- **A separate Marionette port** (2829), so it doesn't collide with `zen` mode (port 2828).
- **A unique WM class** (`ClaudeZen`), so Hyprland can target it independently of your main Zen.

When the agent runs a command:

1. If the claude Zen process isn't running, foxpilot launches it in the background.
2. Once the window appears, foxpilot moves it according to `--visible`:
   - `--visible` → moved onto your active workspace.
   - default (hidden) → moved into the `special:claude` scratchpad workspace.
3. The agent drives the browser via Marionette as usual.

The window stays where it was placed across subsequent commands — running an agent task does **not** disturb your active workspace unless you explicitly ask for `--visible`.

#### First-time login

The claude profile starts empty. Two ways to populate it.

**Option 1 — import cookies from your main Zen profile (preferred for sites that block WebDriver):**

```bash
foxpilot import-cookies                                  # all cookies, every domain
foxpilot import-cookies --domain google.com              # filter by host
foxpilot import-cookies --domain github.com --include-storage   # also localStorage
foxpilot import-cookies --include-passwords              # also key4.db + logins.json
```

Your main Zen can stay running — foxpilot snapshots the SQLite files first to avoid lock contention. The claude profile is killed during the import and re-launched on the next agent command. After importing, the agent is signed in immediately — no login flow.

This is the only reliable approach for sites with active anti-automation (Google, Cloudflare-walled apps, Twitter/X, Discord). They detect Marionette/WebDriver and refuse to let an automated browser sign in even with valid credentials.

**Option 2 — interactive login (sites that don't block WebDriver):**

```bash
foxpilot login                          # opens about:preferences visibly
foxpilot login https://github.com       # opens straight to a login page
```

The window appears visibly on your active workspace. You sign in. Once the URL changes and stays stable for ~8 seconds (the typical post-login redirect to a dashboard), the browser auto-hides. Pass `--no-auto-hide` to keep it visible.

Cookies persist in `~/.local/share/foxpilot/claude-profile` regardless of which method you used.

#### Limitation

`foxpilot login` cannot bypass anti-automation pages — Google, for example, redirects WebDriver-controlled browsers straight to `signin/rejected`. When that happens, use `import-cookies` instead.

#### Switching visibility on the fly

```bash
foxpilot show       # bring claude Zen onto active workspace
foxpilot hide       # send it back to special:claude
foxpilot status     # show running / window present / visibility / port
```

You can also call `hyprctl dispatch togglespecialworkspace claude` directly — the special workspace is a normal Hyprland scratchpad, so all the usual keybinds work.

### Zen mode — how it works

foxpilot connects to Zen via the [Marionette](https://firefox-source-docs.mozilla.org/testing/marionette/) WebDriver protocol on port 2828. Marionette must be active when Zen launches — it cannot be enabled on a running instance.

foxpilot handles this automatically. When you run any `--zen` command:

1. **Marionette already listening** → connects immediately, no disruption
2. **Zen running without Marionette** → kills Zen, relaunches it with `--marionette`, reconnects. Zen's built-in session restore brings your tabs back.
3. **Zen not running at all** → launches Zen with `--marionette` in the background, waits for it to start, then connects

In practice this means `foxpilot --zen <anything>` just works — no manual setup, no wrapper scripts.

### Why `zen-browser --marionette` and not just `zen-browser`

The `zen-browser` CLI script is a thin wrapper: `exec /opt/zen-browser-bin/zen-bin "$@"`. It does not read or apply flags from the `.desktop` entry. Marionette must be passed explicitly on the command line at launch time — Firefox does not support enabling it on a running process.

foxpilot handles this by detecting the port state and managing the relaunch itself, so you never need to think about it.

---

## CLI

### Global flags

```bash
foxpilot [--zen | --visible | --headless-mode] <command> [args]
```

| Flag | Effect |
|---|---|
| *(none)* | **Default** — uses the dedicated `claude` profile, hidden in `special:claude` workspace. |
| `-V` / `--visible` | With `claude` mode, places the window on your active workspace for this run. |
| `-z` / `--zen` | Operate on your real running Zen instance instead. |
| `--headless-mode` | Force ephemeral headless Firefox (no profile, no session). |

Examples:

```bash
foxpilot go https://example.com           # claude profile, hidden
foxpilot --visible go https://example.com # claude profile, on screen
foxpilot --zen tabs                        # your real Zen
foxpilot --headless-mode search "query"   # one-shot ephemeral
```

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

### Claude profile lifecycle

Manages the dedicated `claude`-mode Zen instance — does not perform browser actions.

#### `login [url]`

Open the claude profile **visibly** so you can sign into a site once. Cookies persist in the profile dir, so subsequent hidden agent commands reuse the session.

```bash
foxpilot login                          # opens about:preferences
foxpilot login https://github.com       # opens straight to a login page
```

#### `show` / `hide`

Move the claude Zen window between the active workspace (`show`) and the `special:claude` Hyprland scratchpad (`hide`).

```bash
foxpilot show
foxpilot hide
```

#### `status`

Report whether the claude profile is running, where its window lives, and which port it's on.

```bash
foxpilot status
# running            True
# window_present     True
# visible            False
# workspace          special:claude
# profile_dir        /home/you/.local/share/foxpilot/claude-profile
# marionette_port    2829
```

#### `import-cookies [--from PATH] [--domain SUB] [--include-storage] [--include-passwords]`

Copy cookies from your main Zen profile into the claude profile. Required for sites that block WebDriver-controlled sign-in (Google et al.). Auto-detects the source profile from `~/.zen/profiles.ini` if `--from` is omitted.

```
--from              Source Zen profile dir (default: auto-detect)
--domain            Only import cookies whose host LIKE %domain%
--include-storage   Also copy webappsstore.sqlite (localStorage)
--include-passwords Also copy logins.json + key4.db
```

```bash
foxpilot import-cookies --domain google.com --include-storage
foxpilot go https://myaccount.google.com    # already signed in
```

Stops the claude Zen process before writing, snapshots the source SQLite files first so the user's live Zen doesn't lock the import.

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

#### `burst [target_url] [--count N] [--interval MS] [--out DIR]`

Take a burst of N screenshots spaced `--interval` milliseconds apart. Produces
zero-padded PNG frames the agent's `Read` tool can view directly — use this
when you want an agent-readable time-lapse of a page.

```
target_url     URL to navigate to first (optional; omit to burst the current page)
--count / -n   Number of frames (default 10)
--interval /-i Milliseconds between frames (default 500)
--out / -o     Output directory (default /tmp/foxpilot-burst)
--prefix       Filename prefix (default "frame")
--warmup       Seconds to wait after navigate before first frame (default 1.0)
```

```bash
foxpilot burst http://localhost:3000 --count 20 --interval 250
foxpilot --zen burst --count 5 --interval 1000 --out /tmp/live-frames/
```

#### `record [target_url] [--duration S] [--fps N] [--out FILE]`

Record a video clip by frame-bursting, then stitching the PNGs together with
`ffmpeg`. Output container inferred from the extension (`.mp4`, `.webm`,
`.mkv`, `.gif` all work).

**NOTE:** agents can't read video files — use `burst` if the frames need to go
to an agent. `record` is for human-debug clips.

```
target_url      URL to navigate to first (optional)
--duration / -d Recording length in seconds (default 5)
--fps           Frames per second (default 5)
--out / -o      Output file (default /tmp/foxpilot-clip.mp4)
--warmup        Seconds to wait after navigate (default 1.0)
--keep-frames   Keep the raw PNG frames alongside the video
```

```bash
foxpilot record http://localhost:3000 --duration 10 --fps 10 --out /tmp/demo.mp4
foxpilot --zen record --duration 3 --fps 5 --out /tmp/session.webm
```

Requires `ffmpeg` on `PATH`.

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

All CLI commands are available as MCP tools with the same names. Each accepts:

- `mode` — `"claude"` (default), `"zen"`, or `"headless"`.
- `visible` — only meaningful when `mode="claude"`. `False` (default) keeps the window in `special:claude`. `True` brings it onto the active workspace for this run.

The tab switching command is named `tab_switch` and `new_tab` / `close_tab` use underscores.

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
| `show` | `show` |
| `hide` | `hide` |
| `status` | `status` |
| `login` | `login` |

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

## Known limitations

### `read` is stateless in headless mode

Each CLI invocation opens a new browser process. `foxpilot go https://example.com` navigates, returns content, and exits. A subsequent `foxpilot read` opens a fresh Firefox on `about:blank` — there is no shared session between calls.

**In headless mode:** use `go`, which already returns visible page content inline via the `feedback()` helper. `read` as a standalone is not useful after `go`.

**In zen mode:** this is not a problem. Both commands connect to the same running Zen instance, so `foxpilot --zen go <url>` followed by `foxpilot --zen read` works correctly.

Tracked in [#1](https://github.com/EdwardAstill/foxpilot/issues/1). A `--url` flag on `read` would fix the headless case.

### Tab titles missing on fresh Zen session

After foxpilot auto-restarts Zen, `foxpilot --zen tabs` may show blank titles for tabs that haven't finished loading yet. Wait a few seconds and run again — titles populate as Zen's session restore completes.

### Zen session restore timing

When foxpilot kills and relaunches Zen to enable Marionette, Zen's session restore runs asynchronously. The relaunch is considered ready when the Marionette port opens (up to 10s), but tabs may still be loading. Commands issued immediately after a cold restart may land on `about:blank` rather than the restored tab.

---

## Architecture

```
foxpilot/
├── core.py         Browser connection, Zen auto-launch, tab listing, element finding, page reading
├── cli.py          Typer CLI (foxpilot command)
├── mcp_server.py   FastMCP server (foxpilot mcp)
├── search.py       DuckDuckGo search via HTML interface
└── readability.py  Main content extraction heuristics
```
