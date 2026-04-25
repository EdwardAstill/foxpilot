# `foxpilot wikipedia`

Wikipedia helpers for common agent workflows: open articles, search, summarise the lead paragraph plus infobox, list internal links, dump references, and open a random page. Multilingual via `--lang`.

## Status

`foxpilot wikipedia` ships as a built-in plugin backed by `src/foxpilot/sites/wikipedia.py` and `src/foxpilot/sites/wikipedia_service.py`.

## Authentication

Public site, no login needed. Wikipedia content is fully accessible to anonymous browsers.

## Mode Support

| Command | claude | visible | zen | headless |
|---|---:|---:|---:|---:|
| `help` | yes | yes | yes | yes |
| `open` | yes | yes | yes | yes |
| `search` | yes | yes | yes | yes |
| `summary` | yes | yes | yes | yes |
| `links` | yes | yes | yes | yes |
| `references` | yes | yes | yes | yes |
| `random` | yes | yes | yes | yes |

Default mode is `claude` (dedicated profile). Other modes work fine because Wikipedia does not gate content behind a session.

## Commands

### `help`

Show branch examples and option summary.

```bash
foxpilot wikipedia help
```

### `open <title-or-url> [--lang en]`

Navigate to an article. Accepts a plain title (`"Ada Lovelace"`) or any wikipedia URL.

```bash
foxpilot wikipedia open "Ada Lovelace"
foxpilot wikipedia open https://en.wikipedia.org/wiki/Ada_Lovelace
foxpilot wikipedia open "Ada Lovelace" --lang fr
```

### `search "<query>" [--limit N] [--lang en] [--json]`

Run an on-site Wikipedia search. Returns `title`, `url`, `snippet` per hit. If Wikipedia redirects directly to a single matching article, that article is returned as the sole result.

```bash
foxpilot wikipedia search "rust programming language"
foxpilot wikipedia search "ada lovelace" --limit 5 --json
foxpilot wikipedia search "tour eiffel" --lang fr
```

### `summary <title-or-url> [--lang en] [--json]`

Open an article and extract the lead paragraph plus infobox key/values.

```bash
foxpilot wikipedia summary "Ada Lovelace"
foxpilot wikipedia summary "Ada Lovelace" --json
```

### `links <title-or-url> [--limit N] [--lang en] [--json]`

List internal `/wiki/...` links from the article body, skipping File:, Help:, Special: and other namespace links.

```bash
foxpilot wikipedia links "Ada Lovelace" --limit 25
```

### `references <title-or-url> [--limit N] [--lang en] [--json]`

Extract entries from the references list. Each entry includes the visible reference text and any external URLs cited.

```bash
foxpilot wikipedia references "Ada Lovelace" --json
```

### `random [--lang en] [--json]`

Open a random Wikipedia article (Special:Random) in the chosen language.

```bash
foxpilot wikipedia random
foxpilot wikipedia random --lang ja
```

## JSON Output

All read commands accept `--json`.

Search result shape:

```json
{
  "title": "Ada Lovelace",
  "url": "https://en.wikipedia.org/wiki/Ada_Lovelace",
  "snippet": "Augusta Ada King, Countess of Lovelace ..."
}
```

Summary shape:

```json
{
  "title": "Ada Lovelace",
  "url": "https://en.wikipedia.org/wiki/Ada_Lovelace",
  "lang": "en",
  "lead": "Augusta Ada King, Countess of Lovelace ...",
  "infobox": {
    "Born": "Augusta Ada Byron 10 December 1815, London, England",
    "Died": "27 November 1852 (aged 36)"
  }
}
```

Reference shape:

```json
{
  "text": "Smith, J. (1999). 'Title'. Journal.",
  "urls": ["https://example.org/article"]
}
```

## Failure Modes

- `error: empty Wikipedia title` — title resolved to empty after normalisation. Pass a real title.
- `error: invalid Wikipedia language code` — `--lang` must be a 2-3 letter code (optionally with a region, e.g. `zh-yue`).
- `error: no Wikipedia article found` — search redirected to an error page or article does not exist. Try `foxpilot wikipedia search` first.

## Limitations

- Selectors target the standard desktop Wikipedia skin. Mobile (`m.wikipedia.org`) and skin-customised pages may parse differently.
- Infobox parsing only captures rows with one `<th>` and one `<td>`. Spanning headers, image rows, and nested tables are skipped.
- References extraction returns visible reference list items; inline footnote markers are not deduplicated against duplicate-target citations.
- Language code validation is shape-only (regex), not a registry lookup. An invalid subdomain will fail at navigation time.
