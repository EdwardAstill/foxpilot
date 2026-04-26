# `foxpilot maps`

Google Maps (`google.com/maps`) helpers: search for places, look up a single place, and get directions between two points.

## Status

`foxpilot maps` is a built-in Typer command branch backed by `src/foxpilot/sites/maps.py` and `src/foxpilot/sites/maps_service.py`, registered as the built-in `maps` plugin under `src/foxpilot/plugins/builtin/maps/`.

## Authentication

No login required for basic search and directions. Use `--zen` for a consistent locale and access to signed-in Google features such as saved places.

## Mode Support

All commands work in every mode. Headless is supported but the JS-heavy Maps UI may be unreliable.

| Command | claude | visible | zen | headless |
|---|---:|---:|---:|---:|
| `help` | yes | yes | yes | yes |
| `open` | yes | yes | yes | yes |
| `search` | yes | yes | yes | fragile |
| `place` | yes | yes | yes | fragile |
| `directions` | yes | yes | yes | fragile |

## Commands

### `foxpilot maps help`
Show command examples.

### `foxpilot maps open [--json]`
Open Google Maps home.

### `foxpilot maps search "<query>" [--limit N] [--json]`
Search for places (place name, category, address).

```bash
foxpilot maps search "coffee shops near me" --limit 5
foxpilot maps search "1600 Amphitheatre Parkway"
```

### `foxpilot maps place "<query>" [--json]`
Look up a single place and dump its name, address, rating, phone, hours, and website.

```bash
foxpilot maps place "Eiffel Tower"
foxpilot maps place "British Museum, London"
```

### `foxpilot maps directions "<origin>" "<destination>" [--mode MODE] [--json]`
Get directions between two places. `--mode` accepts `driving` (default), `transit`, `walking`, `cycling` (alias `bicycling`).

```bash
foxpilot maps directions "London" "Paris"
foxpilot maps directions "King's Cross, London" "Heathrow Airport" --mode transit
foxpilot maps directions "Soho, London" "Camden Town" --mode walking
```

## JSON Shapes

`open`:
```json
{ "title": "...", "url": "..." }
```

`search`:
```json
[ { "name": "...", "address": "...", "rating": "4.5", "url": "..." } ]
```

`place`:
```json
{
  "name": "Eiffel Tower",
  "address": "...",
  "rating": "4.6",
  "reviews": "...",
  "phone": "...",
  "hours": "...",
  "website": "...",
  "url": "..."
}
```

`directions`:
```json
{
  "origin": "London",
  "destination": "Paris",
  "mode": "driving",
  "duration": "5h 30min",
  "distance": "...",
  "summary": "...",
  "steps": ["Head south...", "..."],
  "url": "..."
}
```

## Failure Modes & Next Actions

| Failure | Likely cause | Next step |
|---|---|---|
| Empty `place` data | DOM changed, or search did not zoom to a single place | retry with a more specific query |
| Empty `directions` data | Routing failed, or DOM changed | retry `--visible` to inspect |
| `invalid travel mode` | Unsupported mode | use `driving`, `transit`, `walking`, or `cycling` |

## Limitations

- Selectors are best-effort and DOM-fragile.
- No turn-by-turn navigation streaming. Step list is best-effort.
- No multi-stop directions or alternative routes.
- No place reviews or photos extraction.
- Politeness jitter slows reads on purpose; do not remove it.
