# `foxpilot pinterest`

Pinterest (`pinterest.com`) helpers: open sections, dump profiles, list pins and boards, run search, and perform save/repin and follow actions.

## Status

`foxpilot pinterest` is a built-in Typer command branch backed by `src/foxpilot/sites/pinterest.py` and `src/foxpilot/sites/pinterest_service.py`, registered as the built-in `pinterest` plugin under `src/foxpilot/plugins/builtin/pinterest/`.

## WARNING — login wall and politeness jitter

Pinterest requires authentication for most content. Unauthenticated sessions will hit a login wall before seeing pins or profiles. To stay polite:

- Every paginated read in the service layer waits a small random amount (`time.sleep(0.5 + random()*0.8)` — i.e. 0.5–1.3s) between batches. Keep it.
- Use modest `--limit` values (default `12`–`20`). Avoid scraping hundreds of results in a single run.
- Prefer `--zen` so the request looks like the user's normal browsing.
- Do not loop `save` or `follow` over many targets in quick succession.

## Authentication

Pinterest requires a signed-in session to browse pins and profiles. The recommended workflow is:

```bash
foxpilot --zen pinterest open
```

This reuses your already-signed-in Zen browser. Signing in fresh in the automation profile:

```bash
foxpilot login https://www.pinterest.com/
```

## Mode Support

| Command | claude | visible | zen | headless |
|---|---:|---:|---:|---:|
| `help` | yes | yes | yes | yes |
| `open` | fragile | yes | **default** | no |
| `profile` | fragile | yes | **default** | no |
| `boards` | fragile | yes | **default** | no |
| `pins` | fragile | yes | **default** | no |
| `board` | fragile | yes | **default** | no |
| `search` | fragile | yes | **default** | no |
| `save` | fragile | yes | **default** | no |
| `follow` | fragile | yes | **default** | no |

## Commands

### `foxpilot pinterest help`
Show command examples.

### `foxpilot pinterest open [SECTION] [--json]`
Open Pinterest home, or a section: `home`, `today`, `explore`, `following`, `notifications`.

```bash
foxpilot --zen pinterest open
foxpilot --zen pinterest open today
foxpilot --zen pinterest open following
```

### `foxpilot pinterest profile <user-or-url> [--json]`
Open a profile and dump username, display name, bio, and follower/following counts.

```bash
foxpilot --zen pinterest profile nasa
foxpilot --zen pinterest profile https://www.pinterest.com/nasa/
```

### `foxpilot pinterest boards <user-or-url> [--limit N] [--json]`
List boards from a profile.

```bash
foxpilot --zen pinterest boards nasa --limit 20
```

### `foxpilot pinterest pins <user-or-url> [--limit N] [--json]`
Recent pins from a profile.

```bash
foxpilot --zen pinterest pins nasa --limit 12
```

### `foxpilot pinterest board <user-or-url> <slug> [--limit N] [--json]`
Pins from a specific board. `<slug>` is the URL path segment after the username.

```bash
foxpilot --zen pinterest board nasa space-exploration --limit 12
```

### `foxpilot pinterest search "<query>" [--limit N] [--json]`
Search Pinterest pins.

```bash
foxpilot --zen pinterest search "minimalist living room" --limit 12
```

### `foxpilot pinterest save <pin-id-or-url> [--board BOARD] --yes [--json]`
Save (repin) a pin. **Requires `--yes`.** `<pin-id-or-url>` may be a numeric pin id, a `/pin/<id>/` path, or a full Pinterest pin URL. Optionally pass `--board` to save to a named board.

```bash
foxpilot --zen pinterest save 123456789 --yes
foxpilot --zen pinterest save 123456789 --board "Travel" --yes
foxpilot --zen pinterest save https://www.pinterest.com/pin/123456789/ --yes
```

### `foxpilot pinterest follow <user-or-url> --yes [--json]`
Follow a Pinterest profile. **Requires `--yes`.**

```bash
foxpilot --zen pinterest follow nasa --yes
```

## JSON Shapes

`open`:
```json
{ "title": "...", "url": "https://...", "section": "today" }
```

`profile`:
```json
{
  "username": "nasa",
  "name": "NASA",
  "bio": "...",
  "pins": "...",
  "followers": "...",
  "following": "...",
  "url": "https://www.pinterest.com/nasa/"
}
```

`boards`:
```json
[ { "title": "...", "slug": "...", "pin_count": "...", "url": "..." } ]
```

`pins` / `board` / `search`:
```json
[ { "pin_id": "...", "title": "...", "description": "", "board": "", "url": "..." } ]
```

`save`:
```json
{ "target": "123456789", "board": "Travel", "url": "...", "saved": true }
```

`follow`:
```json
{ "username": "nasa", "url": "...", "followed": true }
```

## Failure Modes & Next Actions

| Failure | Likely cause | Next step |
|---|---|---|
| Redirected to login page | Not signed in | run `foxpilot --zen pinterest open` and verify session |
| `could not find the Save button` | Pin already saved, or DOM changed | retry with `--visible` to inspect |
| `could not find board "X" in the save dialog` | Board name mismatch | check board name with `foxpilot --zen pinterest boards <user>` |
| `could not find the Follow button` | Already following, or DOM changed | open profile manually with `--visible` |
| Empty pins / boards | Login wall, or DOM markup changed | retune selectors in `_find_*` helpers in `pinterest_service.py` |
| `invalid Pinterest username` | Bad input | use a plain username like `nasa` or full profile URL |
| `cannot resolve pin target` | Not a numeric id or valid URL | use a numeric pin id or full `https://www.pinterest.com/pin/<id>/` URL |

## Limitations

- Selectors are best-effort and clearly marked as DOM-fragile. Pinterest uses React and changes markup periodically.
- `save` and `follow` require an interactive `--yes` confirmation.
- No bulk save. Single-target only.
- No story pin or video pin special handling.
- Board selection during save uses a best-effort name match; exact board name required.
- Politeness jitter slows reads on purpose; do not remove it.
