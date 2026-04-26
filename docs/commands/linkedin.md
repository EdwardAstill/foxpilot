# `foxpilot linkedin`

LinkedIn (`linkedin.com`) helpers: open sections, dump profiles, run people / jobs search, list inbox threads, send connection requests and DMs.

## Status

`foxpilot linkedin` is a built-in Typer command branch backed by `src/foxpilot/sites/linkedin.py` and `src/foxpilot/sites/linkedin_service.py`, registered as the built-in `linkedin` plugin under `src/foxpilot/plugins/builtin/linkedin/`.

## WARNING — rate limits and politeness jitter

LinkedIn rate-limits aggressive scraping and is quick to surface CAPTCHAs, "unusual activity" blocks, and challenge prompts. To stay polite:

- Every paginated read in the service layer waits a small random amount (`time.sleep(0.5 + random()*0.5)` — i.e. 0.5–1.0s) between batches of 5 cards. This is intentional. Keep it.
- Use modest `--limit` values (default `10`). Avoid scraping hundreds of results in a single run.
- Prefer `--zen` so the request looks like the user's normal browsing.
- Do not loop `connect` over many slugs in quick succession. LinkedIn restricts weekly invitation count.
- If you get redirected to a `/checkpoint/` URL the session is challenged — open `--visible` and resolve manually before retrying.

## Authentication

LinkedIn is hostile to new-device sessions. The recommended workflow is:

```bash
foxpilot --zen linkedin open feed
```

This reuses your already-signed-in Zen browser. Signing in fresh in the automation profile will likely trip a verification prompt — complete it once visibly, then run hidden afterwards:

```bash
foxpilot login https://www.linkedin.com/
```

## Mode Support

| Command | claude | visible | zen | headless |
|---|---:|---:|---:|---:|
| `help` | yes | yes | yes | yes |
| `open` | fragile | yes | **default** | no |
| `profile` | fragile | yes | **default** | no |
| `search-people` | fragile | yes | **default** | no |
| `search-jobs` | fragile | yes | **default** | no |
| `connect` | fragile | yes | **default** | no |
| `messages` | fragile | yes | **default** | no |
| `message` | fragile | yes | **default** | no |

## Commands

### `foxpilot linkedin help`
Show command examples.

### `foxpilot linkedin open [SECTION] [--json]`
Open LinkedIn home, or a section: `feed`, `mynetwork`, `messaging`, `notifications`, `jobs`.

```bash
foxpilot --zen linkedin open
foxpilot --zen linkedin open feed
foxpilot --zen linkedin open jobs
```

### `foxpilot linkedin profile <slug-or-url> [--json]`
Open a profile and dump headline, location, current role, and skills.

```bash
foxpilot --zen linkedin profile satyanadella
foxpilot --zen linkedin profile https://www.linkedin.com/in/satyanadella/
```

### `foxpilot linkedin search-people "<query>" [--limit N] [--json]`
People-search results.

```bash
foxpilot --zen linkedin search-people "site reliability engineer" --limit 5
```

### `foxpilot linkedin search-jobs "<query>" [--location X] [--limit N] [--json]`
Job-search results.

```bash
foxpilot --zen linkedin search-jobs "rust developer" --location "Perth" --limit 5
```

### `foxpilot linkedin connect <slug> [--note "..."] --yes [--json]`
Send a connection request. **Requires `--yes`.** Optional `--note` adds a custom invitation note.

```bash
foxpilot --zen linkedin connect somebody --yes
foxpilot --zen linkedin connect somebody --note "Met you at the Rust meetup." --yes
```

### `foxpilot linkedin messages [--limit N] [--json]`
List recent inbox threads.

### `foxpilot linkedin message <slug-or-thread> "<text>" --yes [--json]`
Send a DM. **Requires `--yes`.** `<slug-or-thread>` may be a profile slug, a `/in/` URL, or a `/messaging/thread/<id>/` URL or bare thread id.

```bash
foxpilot --zen linkedin message somebody "Quick question about your post." --yes
```

## JSON Shapes

`open`:
```json
{ "title": "...", "url": "https://...", "section": "feed" }
```

`profile`:
```json
{
  "name": "Satya Nadella",
  "headline": "Chairman and CEO at Microsoft",
  "location": "Redmond, Washington",
  "current_role": "Microsoft",
  "skills": ["Cloud Computing", "Leadership"],
  "url": "https://..."
}
```

`search-people`:
```json
[ { "name": "...", "headline": "...", "location": "...", "url": "..." } ]
```

`search-jobs`:
```json
[ { "title": "...", "company": "...", "location": "...", "posted": "...", "url": "..." } ]
```

`messages`:
```json
[ { "peer": "...", "snippet": "...", "when": "...", "thread_id": "..." } ]
```

`connect` / `message`:
```json
{ "slug": "...", "url": "...", "sent": true }
```

## Failure Modes & Next Actions

| Failure | Likely cause | Next step |
|---|---|---|
| Redirected to `/checkpoint/` | LinkedIn challenge | run `foxpilot --zen linkedin open feed`, complete challenge manually |
| `could not find the Connect button` | "More" menu hides Connect, or already connected | open profile manually with `--visible` |
| Empty people / jobs results | DOM markup changed, or rate-limit page | retune selectors in `_find_*` helpers in `linkedin_service.py`; back off |
| `invalid LinkedIn profile slug` | Bad input | use slug like `satyanadella` or full `/in/<slug>` URL |

## Limitations

- Selectors are best-effort and clearly marked as DOM-fragile. LinkedIn changes markup frequently.
- `connect` and `message` require an interactive `--yes` confirmation.
- No bulk send. Single-target only.
- No InMail support — connection-restricted DMs only.
- Politeness jitter slows reads on purpose; do not remove it.
