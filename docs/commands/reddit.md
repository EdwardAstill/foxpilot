# `foxpilot reddit`

Reddit (`reddit.com`) helpers: open sections, list subreddit posts, open posts, search, submit posts, and post comments.

## Status

`foxpilot reddit` is a built-in Typer command branch backed by `src/foxpilot/sites/reddit.py` and `src/foxpilot/sites/reddit_service.py`, registered as the built-in `reddit` plugin under `src/foxpilot/plugins/builtin/reddit/`.

## Authentication

Read-only browsing (subreddit lists, posts, search) works without authentication. Write actions (`submit`, `comment`) require a signed-in session.

```bash
foxpilot --zen reddit open                # uses your signed-in Zen session
foxpilot login https://www.reddit.com/    # interactive sign-in into automation profile
```

## Mode Support

| Command | claude | visible | zen | headless |
|---|---:|---:|---:|---:|
| `help` | yes | yes | yes | yes |
| `open` | yes | yes | yes | yes |
| `subreddit` | yes | yes | yes | yes |
| `post` | yes | yes | yes | yes |
| `search` | yes | yes | yes | yes |
| `submit` | fragile | yes | **default** | no |
| `comment` | fragile | yes | **default** | no |

## Commands

### `foxpilot reddit help`
Show command examples.

### `foxpilot reddit open [SECTION] [--json]`
Open Reddit home or a section: `home`, `popular`, `all`, `saved`.

```bash
foxpilot reddit open popular
```

### `foxpilot reddit subreddit <name> [--limit N] [--sort SORT] [--json]`
List posts in a subreddit. `--sort` accepts `hot` (default), `new`, `top`, `rising`.

```bash
foxpilot reddit subreddit python --limit 10 --sort new
```

### `foxpilot reddit post <id-or-url> [--json]`
Open a post and dump its title, body, subreddit, author, and score.

```bash
foxpilot reddit post abc123
foxpilot reddit post https://www.reddit.com/r/python/comments/abc123/title/
```

### `foxpilot reddit search "<query>" [--sub SUB] [--limit N] [--sort SORT] [--json]`
Search Reddit posts. `--sort` accepts `relevance` (default), `new`, `top`, `comments`. Use `--sub` to restrict to a single subreddit.

```bash
foxpilot reddit search "rust async" --limit 10
foxpilot reddit search "rust async" --sub rust
```

### `foxpilot reddit submit <subreddit> "<title>" "<body>" --yes [--json]`
Submit a text post to a subreddit. **Requires `--yes`.** Body may be empty for link-only posts.

```bash
foxpilot --zen reddit submit testingground "First post" "Body text" --yes
```

### `foxpilot reddit comment <post-id-or-url> "<text>" --yes [--json]`
Post a comment on an existing post. **Requires `--yes`.**

```bash
foxpilot --zen reddit comment abc123 "Great write-up." --yes
```

## JSON Shapes

`open`:
```json
{ "title": "...", "url": "...", "section": "popular" }
```

`subreddit` / `search`:
```json
[ { "title": "...", "subreddit": "r/python", "author": "alice", "score": "42", "comments": "12", "url": "..." } ]
```

`post`:
```json
{ "title": "...", "subreddit": "r/python", "author": "alice", "score": "42", "text": "...", "url": "..." }
```

`submit` / `comment`:
```json
{ "subreddit": "...", "title": "...", "url": "...", "submitted": true }
```

## Failure Modes & Next Actions

| Failure | Likely cause | Next step |
|---|---|---|
| `could not complete the submission form` | Submit UI changed, or not signed in | retry `--visible` and verify the form |
| `could not post the comment` | Not signed in, or comment composer changed | retry `--visible`, verify session |
| Empty subreddit listings | New Reddit DOM changed, or subreddit private | retune selectors in `_find_*` helpers in `reddit_service.py` |
| `invalid subreddit name` | Bad input | use a plain name like `python` or `r/python` |

## Limitations

- Selectors are best-effort and DOM-fragile. New Reddit changes markup periodically.
- `submit` and `comment` require an interactive `--yes` confirmation.
- No vote, save, or share actions.
- Single text post only — no link-post-only nor media uploads.
- Politeness jitter slows reads on purpose; do not remove it.
