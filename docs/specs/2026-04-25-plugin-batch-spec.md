# Foxpilot Plugin Batch — Spec

Date: 2026-04-25

Status: Draft

Owner: Foxpilot

## Summary

Build ten new built-in plugins in parallel, each following the established `youtube` / `excel` pattern: one `sites/<name>.py` Typer branch, one `sites/<name>_service.py` service module, one `plugins/builtin/<name>/plugin.py` registration, one `docs/commands/<name>.md` doc, and CLI wiring in `src/foxpilot/cli.py`.

User context: University of Western Australia student. Zen browser already signed into UWA LMS (Blackboard Ultra at `https://lms.uwa.edu.au/ultra/stream`). Default browser mode for these plugins should be `--zen` where the user already has a real session, with `claude` profile fallback after `foxpilot login`.

The ten plugins, prioritised:

| # | Plugin | Target host(s) | Why |
|---|---|---|---|
| 1 | `lms` | `lms.uwa.edu.au` (Blackboard Ultra) | Daily-use academic surface |
| 2 | `gmail` | `mail.google.com` | Most-touched mail account |
| 3 | `gcal` | `calendar.google.com` | Deadline + event surface |
| 4 | `outlook` | `outlook.office.com` | M365 mail (likely UWA student mail) |
| 5 | `teams` | `teams.microsoft.com` | UWA student communication |
| 6 | `drive` | `drive.google.com` | Google file storage |
| 7 | `wikipedia` | `*.wikipedia.org` | Reference reads |
| 8 | `linkedin` | `linkedin.com` | Profile + messaging |
| 9 | `youtube-music` | `music.youtube.com` | Playlist + library mgmt |
| 10 | `amazon` | `amazon.com` / `amazon.com.au` | Order history + product search |

## Goals

1. Each plugin ships as a built-in plugin with auto-discovery via `foxpilot plugins list`.
2. Each plugin has a `help` command, a JSON-output mode on every read command, and clear failure messages with `next:` hints.
3. Auth is documented per plugin: which login URL, which mode is recommended, whether cookies need importing.
4. Each plugin's service layer is unit-testable without a live browser (URL helpers, formatters, parsers).
5. Selectors are best-effort and clearly marked; this spec is the source of truth for *what* each plugin does, not the final selector list.
6. Default browser mode per plugin matches the user's actual session location: `--zen` for sites already signed in, `claude` for newly added accounts.

## Non-goals

1. Full read-and-write parity with each site's web UI.
2. OAuth, official APIs, or Graph API usage — these are browser automation plugins.
3. Bulk export tooling. Single-record commands now; bulk later.
4. Complex media playback control beyond track + playlist navigation.
5. Cross-plugin orchestration (mission-level features stay in `foxpilot mission`).

## Shared Conventions (apply to every plugin)

- File layout: `sites/<name>.py`, `sites/<name>_service.py`, `plugins/builtin/<name>/{__init__.py,plugin.py}`, `docs/commands/<name>.md`.
- Plugin name: short lowercase, hyphen-allowed (`youtube-music`).
- Required commands per plugin: `help`, plus a domain-specific `open` (or equivalent navigation entrypoint).
- All read commands accept `--json`.
- All commands fail with `error:` line on stderr, plus `url:`, `reason:`, and `next:` lines where useful, then exit code 1.
- `set_browser_factory` exported, wired from `cli.py` via `_branch_browser`.
- Plugin `register()` returns `Plugin(...)` with `auth_notes`, `browser_modes`, `docs_path` set.
- Service layer holds URL helpers, formatters, DOM extraction, structured-output shaping. CLI layer is thin: parse args → call service → emit.
- DOM-fragile selectors live in named private helpers (`_find_<thing>`) so future tuning is one edit.
- Selenium imports are local-to-function (matches existing onedrive/excel pattern).

## Per-Plugin Specs

### 1. `lms` — UWA Blackboard Ultra

Host: `https://lms.uwa.edu.au/ultra/`. Stream lives at `/ultra/stream`. Course list at `/ultra/course`. Calendar at `/ultra/calendar`. Grades at `/ultra/grades`. Messages at `/ultra/messages`.

Default mode: **`--zen`** (user signed in there). Add cookie import path for `claude` profile.

| Command | Behaviour |
|---|---|
| `help` | Print usage, link to Blackboard Ultra layout. |
| `open [section]` | Navigate to `stream`, `courses`, `calendar`, `grades`, `messages`. |
| `stream [--limit N] [--json]` | List recent stream items with title, course, kind, timestamp. |
| `courses [--json]` | List enrolled courses with title, code, term, link. |
| `course <id-or-name>` | Open course landing page. |
| `assignments [--course X] [--due-soon] [--json]` | List assignment items: name, course, due date, status. |
| `grades [--course X] [--json]` | List grade items: name, score, weight, posted-at. |
| `announcements [--limit N] [--course X] [--json]` | List announcements with course + posted-at. |
| `download <assignment>` | Save attached files for an assignment to a target dir. |

Selectors of interest (Blackboard Ultra is React-rendered, watch for stable `data-*` hooks):
- Stream cards: `[data-testid='stream-item']` or `.stream-item`.
- Course cards on `/ultra/course`: `[data-testid='course-link']` or `.js-course-card`.
- Grade rows: `[data-testid='grade-row']` or table rows under `[role='grid']`.

Failure modes: SSO redirect to UWA Pheme login (visible in URL `auth.uwa.edu.au`); message: "session expired" + `next: foxpilot --zen lms open stream and complete SSO`.

### 2. `gmail`

Host: `https://mail.google.com/`. Default mode: `claude` profile after `foxpilot login https://mail.google.com`.

| Command | Behaviour |
|---|---|
| `help` | |
| `open [label]` | Open inbox or a label like `Starred`, `Important`. |
| `list [--label X] [--limit N] [--unread] [--json]` | List messages: from, subject, snippet, age, id. |
| `read <id-or-search>` | Open and dump message body + headers. |
| `search "<query>"` | Run Gmail search. |
| `compose --to X --subject Y --body Z` | Open compose pane and fill fields. |
| `send` | Send the currently open compose draft. Confirmation required unless `--yes`. |
| `archive <id>` / `delete <id>` / `star <id>` | Apply action to a message thread. |

Notes: Gmail uses dynamic class names; rely on `[role='listitem']`, `[aria-label]`, and visible-text matching. Avoid Gmail Lite.

### 3. `gcal`

Host: `https://calendar.google.com/`. Default mode: `claude`.

| Command | Behaviour |
|---|---|
| `help` | |
| `open [view]` | View `day`, `week`, `month`, `agenda`. |
| `events [--from D] [--to D] [--json]` | List upcoming events with title, time, calendar, location. |
| `event <title-or-id>` | Open detail panel + dump JSON. |
| `create --title T --when "<datetime>" [--duration M] [--invitees ...]` | Open quick-create or full create dialog. |
| `today [--json]` | Today's events shortcut. |

Calendar URL date hint: `?dates=YYYYMMDD`.

### 4. `outlook` (Microsoft 365 Outlook on the web)

Host: `https://outlook.office.com/mail/`. Calendar at `/calendar/`. Default mode: `--zen` (likely signed-in for UWA M365).

| Command | Behaviour |
|---|---|
| `help` | |
| `open [folder]` | `inbox`, `sent`, `drafts`, `archive`. |
| `list [--limit N] [--unread] [--json]` | List messages. |
| `read <id-or-search>` | Show body + headers. |
| `search "<query>"` | Run search. |
| `compose --to ...` | Same shape as gmail. |
| `send [--yes]` | |
| `calendar [--from D] [--to D]` | Outlook calendar listing (avoid duplicating gcal). |

Selectors: `div[role='option']` for message rows, `[aria-label='Reading pane']` for body.

### 5. `teams`

Host: `https://teams.microsoft.com/`. Default mode: `--zen`.

| Command | Behaviour |
|---|---|
| `help` | |
| `open [section]` | `chat`, `teams`, `calendar`, `calls`, `activity`. |
| `chats [--json]` | List recent chats with peer + last-message snippet. |
| `chat <name>` | Open a 1:1 or group chat. |
| `messages [--chat X] [--limit N] [--json]` | Recent messages. |
| `post <chat-or-channel> "<message>"` | Post into a chat or channel; confirmation gated. |
| `teams [--json]` | List joined teams. |
| `channel <team> <channel>` | Open a channel. |

Notes: Teams web is Electron-style; iframes possible. Watch for `iframe#embedded-page-container`.

### 6. `drive` — Google Drive

Host: `https://drive.google.com/`. Default mode: `claude`.

| Command | Behaviour |
|---|---|
| `help` | |
| `open [view]` | `home`, `recent`, `starred`, `shared`, `trash`. |
| `files [--folder X] [--limit N] [--json]` | List files: name, kind, owner, modified-at, link. |
| `search "<query>"` | Drive search. |
| `download <name-or-id>` | Trigger download (uses browser download dir; mirror onedrive `wait-download`). |
| `open-item <name>` | Open a file (in Docs/Sheets/Slides as appropriate). |
| `path` | Breadcrumb of current folder. |

Mirror onedrive's `wait-download` snapshot+poll pattern.

### 7. `wikipedia`

Host: `https://en.wikipedia.org/` and other-language subdomains. Default mode: `claude` (no auth needed).

| Command | Behaviour |
|---|---|
| `help` | |
| `open <title-or-url>` | Navigate to article. |
| `search "<query>" [--limit N] [--json]` | Use Wikipedia OpenSearch via the on-page search; return title + snippet + link. |
| `summary <title-or-url> [--lang en]` | Return lead paragraph + infobox key/values. |
| `links <title> [--limit N]` | Internal links from current article. |
| `references <title>` | Reference list with cite text + URL. |
| `random [--lang en]` | Open a random article. |

Notes: language sub-domain via `--lang`. Stable selectors: `#firstHeading`, `#mw-content-text > .mw-parser-output`.

### 8. `linkedin`

Host: `https://www.linkedin.com/`. Default mode: `--zen` (LinkedIn aggressive about new-device challenges; reuse signed-in session).

| Command | Behaviour |
|---|---|
| `help` | |
| `open [section]` | `feed`, `mynetwork`, `messaging`, `notifications`, `jobs`. |
| `profile <slug-or-url>` | Open a profile, dump headline, location, current role, skills. |
| `search-people "<query>" [--limit N] [--json]` | People-search results. |
| `search-jobs "<query>" [--location X] [--limit N] [--json]` | Job-search results. |
| `connect <slug>` | Send connection request (confirmation gated, no custom note unless `--note`). |
| `messages [--limit N] [--json]` | Recent inbox threads. |
| `message <slug-or-thread> "<text>"` | Send a DM (confirmation gated). |

Notes: LinkedIn rate-limits aggressive scraping. Keep limits modest and add jitter.

### 9. `youtube-music`

Host: `https://music.youtube.com/`. Default mode: `claude` after `foxpilot login`.

| Command | Behaviour |
|---|---|
| `help` | |
| `open [section]` | `home`, `explore`, `library`, `playlists`. |
| `search "<query>" [--kind track|artist|album|playlist] [--limit N] [--json]` | Search results. |
| `play <title-or-url>` | Start playback (cell URL or top search hit). |
| `pause` / `resume` / `next` / `previous` | Player controls via media keys / on-page buttons. |
| `now-playing [--json]` | Current track title, artist, album, position. |
| `playlists [--json]` | List user's playlists. |
| `playlist <name>` | Open a playlist; list tracks. |
| `add-to-playlist <playlist> <track>` | Add a track to a playlist (confirmation gated). |

Notes: YouTube Music is a YouTube-frontend; some logic may share `youtube_service.py` URL helpers.

### 10. `amazon`

Hosts: `amazon.com`, `amazon.com.au`, etc. Default mode: `--zen` (Amazon hostile to new-device sessions).

| Command | Behaviour |
|---|---|
| `help` | |
| `open [section]` | `home`, `orders`, `wishlist`, `cart`. |
| `search "<query>" [--limit N] [--json]` | Product search results: title, price, rating, prime, link. |
| `product <asin-or-url> [--json]` | Product detail: title, price, rating, availability, key bullets. |
| `orders [--limit N] [--year YYYY] [--json]` | Order history. |
| `track <order-id>` | Tracking page contents. |
| `cart [--json]` | Cart contents. |

Notes: support `--region` (`com`, `com.au`, `co.uk`) — service layer builds the URL. Default region inferred from current URL or `com.au` for AU users.

## Cross-Cutting Concerns

### Auth + Session

- For each plugin, document the canonical login URL.
- Recommend `--zen` for sites the user already accesses interactively.
- For `claude`-mode plugins, `foxpilot login <url>` must work end-to-end before the plugin is considered ready.
- Cookie-import notes per site where session import is the easier path.

### Confirmation Gates

Send / post / connect / add commands MUST require interactive confirmation (or `--yes`) before performing the destructive-ish action. Reads, lists, and opens are unconfirmed.

### Output Shape

- Default text output is human-readable and aligned.
- `--json` returns a list of dicts for list commands, a single dict for detail commands. Keys are lowercase snake_case.

### Failure Reporting

`error: <message>` on stderr, optionally followed by `url:`, `reason:`, `next:` — matches existing youtube/onedrive/excel pattern.

### Mode Support Matrix (target)

| Plugin | claude | visible | zen | headless |
|---|---:|---:|---:|---:|
| lms | yes (after login) | yes | **default** | no (SSO) |
| gmail | **default** | yes | yes | best effort |
| gcal | **default** | yes | yes | best effort |
| outlook | yes (after login) | yes | **default** | no (SSO) |
| teams | yes (after login) | yes | **default** | no |
| drive | **default** | yes | yes | best effort |
| wikipedia | **default** | yes | yes | yes |
| linkedin | yes (fragile) | yes | **default** | no |
| youtube-music | **default** | yes | yes | best effort |
| amazon | yes (fragile) | yes | **default** | no |

### Test Strategy

Per plugin:
- Unit tests for service-layer helpers (URL builders, formatters, parsers) in `tests/sites/test_<name>_service.py`.
- No live-browser tests in CI. Mark integration-style tests `@pytest.mark.live` and skip by default.
- Smoke test: `foxpilot <name> help` runs without import errors and lists every command.

## Build Order

Each plugin is independent → fully parallelisable. Suggested batch composition for parallel manager dispatch:

- **Batch A** (Microsoft/UWA stack — share auth assumptions): `lms`, `outlook`, `teams`.
- **Batch B** (Google stack): `gmail`, `gcal`, `drive`.
- **Batch C** (read-mostly + public): `wikipedia`, `youtube-music`.
- **Batch D** (auth-fragile): `linkedin`, `amazon`.

Each batch can run as 2–3 parallel subagents. Each subagent owns one full plugin (sites/, service, plugin.py, doc, CLI wiring).

## Acceptance Criteria (per plugin)

1. `foxpilot plugins info <name>` returns metadata with `auth_notes` and `browser_modes` set.
2. `foxpilot <name> help` runs and lists every documented command.
3. `foxpilot <name> --help` shows every command with one-line descriptions.
4. `docs/commands/<name>.md` exists with: status, auth, mode matrix, command reference, JSON shapes, failure modes, limitations.
5. Service-layer unit tests exist and pass (`uv run pytest tests/sites/test_<name>_service.py`).
6. CLI wiring is added in `src/foxpilot/cli.py`.
7. No new permanent pyright errors beyond the project's existing selenium/typer noise.

## Out of Scope (this spec)

- Mission-level workflows that combine plugins.
- MCP tool generation per plugin (registry already supports `mcp_tools=()`; populate later).
- Auth-token vaulting; cookie import remains the single auth path.
- Notification / push features.
- Mobile-site fallbacks.

## Source-of-Truth Pointers

- Plugin layer types: `src/foxpilot/plugins/types.py`
- Plugin discovery: `src/foxpilot/plugins/loader.py`
- Reference plugin: `src/foxpilot/plugins/builtin/youtube/plugin.py`
- Reference site module: `src/foxpilot/sites/youtube.py` + `youtube_service.py`
- Reference docs: `docs/commands/youtube.md`
- Reference CLI wiring: `src/foxpilot/cli.py` (`set_youtube_browser_factory`, `app.add_typer(...)`).
- Plugin vs site-module guide: `docs/plugin-vs-site-module.md`
