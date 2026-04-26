# `foxpilot twitter`

X / Twitter (`x.com`) helpers: open sections, dump profiles, fetch the home timeline, search, post tweets, follow accounts, and send DMs.

## Status

`foxpilot twitter` is a built-in Typer command branch backed by `src/foxpilot/sites/twitter.py` and `src/foxpilot/sites/twitter_service.py`, registered as the built-in `twitter` plugin under `src/foxpilot/plugins/builtin/twitter/`.

## WARNING — anti-bot and politeness jitter

X is aggressive about anti-bot detection, new-device session challenges, login walls on most content, and DOM churn. To stay polite:

- Every paginated read in the service layer waits a small random amount (`time.sleep(0.6 + random()*0.8)` — i.e. 0.6–1.4s) between batches. Keep it.
- Use modest `--limit` values (default `10`). Avoid scraping hundreds of results in a single run.
- Prefer `--zen` so the request looks like the user's normal browsing.
- Do not loop `tweet`, `follow`, or `dm` over many targets in quick succession.

## Authentication

X requires authentication for most browsing. The recommended workflow is:

```bash
foxpilot --zen twitter open
```

This reuses your already-signed-in Zen browser. Signing in fresh in the automation profile will likely trip a verification prompt — complete it visibly:

```bash
foxpilot login https://x.com/
```

## Mode Support

| Command | claude | visible | zen | headless |
|---|---:|---:|---:|---:|
| `help` | yes | yes | yes | yes |
| `open` | fragile | yes | **default** | no |
| `profile` | fragile | yes | **default** | no |
| `timeline` | fragile | yes | **default** | no |
| `search` | fragile | yes | **default** | no |
| `tweet` | fragile | yes | **default** | no |
| `follow` | fragile | yes | **default** | no |
| `dm` | fragile | yes | **default** | no |

## Commands

### `foxpilot twitter help`
Show command examples.

### `foxpilot twitter open [SECTION] [--json]`
Open X home or a section: `home`, `explore`, `notifications`, `messages`, `bookmarks`.

```bash
foxpilot --zen twitter open
foxpilot --zen twitter open explore
```

### `foxpilot twitter profile <user-or-url> [--json]`
Open a profile and dump username, name, bio, location, and counts.

```bash
foxpilot --zen twitter profile jack
foxpilot --zen twitter profile @jack
```

### `foxpilot twitter timeline [--limit N] [--json]`
Fetch tweets from your home timeline.

```bash
foxpilot --zen twitter timeline --limit 10
```

### `foxpilot twitter search "<query>" [--limit N] [--tab TAB] [--json]`
Search X. `--tab` accepts `Top`, `Latest`, `People`, `Media`.

```bash
foxpilot --zen twitter search "claude code" --tab Latest
```

### `foxpilot twitter tweet "<text>" --yes [--json]`
Post a tweet. **Requires `--yes`.**

```bash
foxpilot --zen twitter tweet "Hello from foxpilot" --yes
```

### `foxpilot twitter follow <user> --yes [--json]`
Follow a profile. **Requires `--yes`.**

```bash
foxpilot --zen twitter follow jack --yes
```

### `foxpilot twitter dm <user> "<text>" --yes [--json]`
Send a DM to a user. **Requires `--yes`.**

```bash
foxpilot --zen twitter dm jack "Hi there" --yes
```

## JSON Shapes

`open`:
```json
{ "title": "...", "url": "...", "section": "home" }
```

`profile`:
```json
{
  "username": "jack",
  "name": "Jack",
  "bio": "...",
  "location": "...",
  "tweets": "...",
  "followers": "...",
  "following": "...",
  "url": "..."
}
```

`timeline` / `search`:
```json
[ { "text": "...", "username": "...", "time": "...", "likes": "", "retweets": "", "url": "..." } ]
```

`tweet` / `follow` / `dm`:
```json
{ "username": "jack", "url": "...", "sent": true }
```

## Failure Modes & Next Actions

| Failure | Likely cause | Next step |
|---|---|---|
| Redirected to login wall | Not signed in | run `foxpilot --zen twitter open` and verify session |
| `could not open the tweet compose box` | Compose UI changed, or session blocked | retry with `--visible` |
| `could not find the Follow button` | Already following, or DOM changed | open profile manually with `--visible` |
| Empty timeline / search results | DOM markup changed, or rate-limited | retune selectors in `_find_*` helpers in `twitter_service.py`; back off |
| `invalid X username` | Bad input | use a plain handle like `jack` or full profile URL |

## Limitations

- Selectors are best-effort and clearly marked as DOM-fragile. X changes markup frequently.
- `tweet`, `follow`, and `dm` require an interactive `--yes` confirmation.
- No bulk send. Single-target only.
- No reply / quote-tweet / thread support — single tweet only.
- No media uploads.
- DM thread resolution uses `messages/compose?recipient_id=<handle>` which works for permitted DM recipients only.
- Politeness jitter slows reads on purpose; do not remove it.
