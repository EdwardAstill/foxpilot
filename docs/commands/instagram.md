# `foxpilot instagram`

Instagram (`instagram.com`) helpers: open sections, dump profiles, list posts and hashtag feeds, run search, list DM threads, and perform follow / like / comment / DM actions.

## Status

`foxpilot instagram` is a built-in Typer command branch backed by `src/foxpilot/sites/instagram.py` and `src/foxpilot/sites/instagram_service.py`, registered as the built-in `instagram` plugin under `src/foxpilot/plugins/builtin/instagram/`.

## WARNING — anti-bot and politeness jitter

Instagram is aggressive about anti-bot detection, "suspicious activity" lockouts, login challenges, and DOM churn (including shadow-roots and lazy-loaded content). To stay polite:

- Every paginated read in the service layer waits a small random amount (`time.sleep(0.7 + random()*0.8)` — i.e. 0.7–1.5s) between batches. This is intentional. Keep it.
- Use modest `--limit` values (default `10`–`12`). Avoid scraping hundreds of results in a single run.
- Prefer `--zen` so the request looks like the user's normal browsing.
- Do not loop `follow`, `like`, or `comment` over many targets in quick succession. Instagram restricts daily action counts and will block the account on abuse.
- If you get redirected to a `/challenge/` URL the session is challenged — open `--visible` and resolve manually before retrying.

## Authentication

Instagram is hostile to new-device sessions. The recommended workflow is:

```bash
foxpilot --zen instagram open
```

This reuses your already-signed-in Zen browser. Signing in fresh in the automation profile will likely trip a verification prompt — complete it once visibly, then run hidden afterwards:

```bash
foxpilot login https://www.instagram.com/
```

## Mode Support

| Command | claude | visible | zen | headless |
|---|---:|---:|---:|---:|
| `help` | yes | yes | yes | yes |
| `open` | fragile | yes | **default** | no |
| `profile` | fragile | yes | **default** | no |
| `posts` | fragile | yes | **default** | no |
| `tag` | fragile | yes | **default** | no |
| `search` | fragile | yes | **default** | no |
| `messages` | fragile | yes | **default** | no |
| `follow` | fragile | yes | **default** | no |
| `like` | fragile | yes | **default** | no |
| `comment` | fragile | yes | **default** | no |
| `dm` | fragile | yes | **default** | no |
| `message` | fragile | yes | **default** | no |

## Commands

### `foxpilot instagram help`
Show command examples.

### `foxpilot instagram open [SECTION] [--json]`
Open Instagram home, or a section: `home`, `explore`, `reels`, `direct`, `notifications`.

```bash
foxpilot --zen instagram open
foxpilot --zen instagram open explore
foxpilot --zen instagram open direct
```

### `foxpilot instagram profile <handle-or-url> [--json]`
Open a profile and dump handle, display name, bio, and post/follower/following counts.

```bash
foxpilot --zen instagram profile natgeo
foxpilot --zen instagram profile @natgeo
foxpilot --zen instagram profile https://www.instagram.com/natgeo/
```

### `foxpilot instagram posts <handle-or-url> [--limit N] [--json]`
Recent posts from a profile grid.

```bash
foxpilot --zen instagram posts natgeo --limit 12
```

### `foxpilot instagram tag <name> [--limit N] [--json]`
Posts on a hashtag page (no leading `#`).

```bash
foxpilot --zen instagram tag wildlife --limit 10
```

### `foxpilot instagram search "<query>" [--limit N] [--json]`
Search hits across users, tags, locations, and posts.

```bash
foxpilot --zen instagram search "national geographic" --limit 5
```

### `foxpilot instagram messages [--limit N] [--json]`
List recent DM threads.

### `foxpilot instagram follow <handle> --yes [--json]`
Follow an account. **Requires `--yes`.**

```bash
foxpilot --zen instagram follow natgeo --yes
```

### `foxpilot instagram like <shortcode-or-url> --yes [--json]`
Like a post. **Requires `--yes`.** `<shortcode-or-url>` may be a bare shortcode, a `/p/<code>/` URL, or a `/reel/<code>/` URL.

```bash
foxpilot --zen instagram like CXXXXXXXX --yes
```

### `foxpilot instagram comment <shortcode-or-url> "<text>" --yes [--json]`
Post a comment. **Requires `--yes`.**

```bash
foxpilot --zen instagram comment CXXXXXXXX "Beautiful shot." --yes
```

### `foxpilot instagram dm <handle-or-thread> "<text>" --yes [--json]`
Send a DM. **Requires `--yes`.** `<handle-or-thread>` may be a handle, `@handle`, profile URL, `/direct/t/<id>/` URL, or bare thread id.

```bash
foxpilot --zen instagram dm natgeo "Hi there!" --yes
```

### `foxpilot instagram message <name> "<text>" --yes [--source ...] [--pick HANDLE] [--refresh] [--owner H] [--followers-limit N] [--json]`

Higher-level send: takes a free-text contact name, fuzzy-matches across your **inbox**, **followers**, and **following**, then sends the DM. **Requires `--yes`.**

Resolution order (default `--source inbox,followers,following`):
1. **inbox** — peers from your DM inbox (cheapest, smallest set).
2. **followers** — your followers list at `/<owner>/followers/`.
3. **following** — accounts you follow at `/<owner>/following/`.

The merged contact list is cached at `~/.cache/foxpilot/instagram/<owner>-contacts.json` (24h TTL). Pass `--refresh` to bust the cache and re-scrape.

Disambiguation:
- Exactly one match → auto-proceeds and sends.
- Two or more matches → exits with a numbered candidate list. Re-run with `--pick <handle>` to choose.
- No match → exits with a hint to `--refresh` or fall back to `instagram dm <handle>`.

Owner handle: auto-detected from the signed-in session header. Pass `--owner <yourhandle>` to skip auto-detect (faster, also useful when detection fails).

```bash
# happy path: only one Maddy in your contacts
foxpilot --zen instagram message "maddy rodriguez" "Hey, free Friday?" --yes

# multiple matches → list, then pick
foxpilot --zen instagram message "maddy" "Hey!" --yes
foxpilot --zen instagram message "maddy" "Hey!" --pick maddy.rodriguez --yes

# rescrape cache
foxpilot --zen instagram message "alice" "Yo" --refresh --yes

# skip auto-detect of your own handle
foxpilot --zen instagram message "alice" "Yo" --owner myhandle --yes
```

JSON success:
```json
{
  "query": "maddy rodriguez",
  "owner": "myhandle",
  "handle": "maddy.rodriguez",
  "name": "Maddy Rodriguez",
  "source": "followers",
  "url": "https://www.instagram.com/direct/t/...",
  "sent": true
}
```

JSON ambiguity (exit code 1):
```json
{ "matches": [ { "handle": "...", "name": "...", "source": "..." } ] }
```

## JSON Shapes

`open`:
```json
{ "title": "...", "url": "https://...", "section": "explore" }
```

`profile`:
```json
{
  "handle": "natgeo",
  "name": "National Geographic",
  "bio": "...",
  "posts": "29,123",
  "followers": "281M",
  "following": "143",
  "url": "https://..."
}
```

`posts`:
```json
[ { "shortcode": "...", "caption": "...", "likes": "", "comments": "", "url": "..." } ]
```

`search`:
```json
[ { "kind": "user|tag|location|post|reel", "label": "...", "subtitle": "...", "url": "..." } ]
```

`messages`:
```json
[ { "peer": "...", "snippet": "...", "when": "...", "thread_id": "..." } ]
```

`follow` / `like` / `comment` / `dm`:
```json
{ "handle": "...", "url": "...", "followed": true }
```

## Failure Modes & Next Actions

| Failure | Likely cause | Next step |
|---|---|---|
| Redirected to `/challenge/` | Instagram challenge | run `foxpilot --zen instagram open`, complete challenge manually |
| `could not find the Follow button` | Already following, or button hidden | open profile manually with `--visible` |
| Empty posts / search results | DOM markup changed, or rate-limit page | retune selectors in `_find_*` helpers in `instagram_service.py`; back off |
| `invalid Instagram handle` | Bad input | use a plain handle like `natgeo` or full URL |
| `could not find Message button` | Account does not allow DMs from non-followers | follow first or send via an existing thread id |

## Limitations

- Selectors are best-effort and clearly marked as DOM-fragile. Instagram changes markup very frequently and uses shadow roots in places.
- `follow`, `like`, `comment`, and `dm` require an interactive `--yes` confirmation.
- No bulk send. Single-target only.
- No story / live-stream interactions.
- No multi-image carousel awareness on `posts` — only the first image is referenced.
- Politeness jitter slows reads on purpose; do not remove it.
