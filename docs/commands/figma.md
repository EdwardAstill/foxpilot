# `foxpilot figma`

Figma (`figma.com`) helpers: open the dashboard, list recent files, open specific files, and search.

## Status

`foxpilot figma` is a built-in Typer command branch backed by `src/foxpilot/sites/figma.py` and `src/foxpilot/sites/figma_service.py`, registered as the built-in `figma` plugin under `src/foxpilot/plugins/builtin/figma/`.

## Authentication

Figma requires authentication for all content. The recommended workflow is:

```bash
foxpilot --zen figma open
```

This reuses your already-signed-in Zen browser. To sign in fresh in the automation profile:

```bash
foxpilot login https://www.figma.com/
```

All foxpilot Figma operations are read-only — no editing of files, comments, or shares.

## Mode Support

| Command | claude | visible | zen | headless |
|---|---:|---:|---:|---:|
| `help` | yes | yes | yes | yes |
| `open` | fragile | yes | **default** | no |
| `files` | fragile | yes | **default** | no |
| `file` | fragile | yes | **default** | no |
| `search` | fragile | yes | **default** | no |

## Commands

### `foxpilot figma help`
Show command examples.

### `foxpilot figma open [--json]`
Open Figma home (the dashboard, post-auth).

### `foxpilot figma files [--limit N] [--json]`
List recent and shared files from the Figma dashboard.

```bash
foxpilot --zen figma files --limit 20
```

### `foxpilot figma file <key-or-url> [--json]`
Open a specific Figma file and dump its title and metadata. The file key is the alphanumeric ID in a Figma URL: `https://www.figma.com/file/<KEY>/Title`.

```bash
foxpilot --zen figma file ABCdef12345
foxpilot --zen figma file https://www.figma.com/file/ABCdef12345/Mockups
```

### `foxpilot figma search "<query>" [--limit N] [--json]`
Search Figma files.

```bash
foxpilot --zen figma search "design system"
```

## JSON Shapes

`open`:
```json
{ "title": "...", "url": "..." }
```

`files` / `search`:
```json
[ { "name": "...", "last_modified": "...", "url": "..." } ]
```

`file`:
```json
{ "name": "Mockups", "url": "https://www.figma.com/file/.../Mockups" }
```

## Failure Modes & Next Actions

| Failure | Likely cause | Next step |
|---|---|---|
| Redirected away from Figma | Not signed in | run `foxpilot --zen figma open` and verify session |
| Empty `files` list | Dashboard DOM changed, or empty workspace | retune selectors in `_find_*` helpers in `figma_service.py` |
| `cannot resolve Figma file target` | Bad input | use the alphanumeric file key or full URL |

## Limitations

- Selectors are best-effort and DOM-fragile. Figma is a complex React app and changes frequently.
- All operations are read-only. Foxpilot will not create, comment on, or modify files.
- No team or project listing — only the user's own recents and shared files.
- No design inspection (frames, components, styles). Use foxpilot's generic `styles`/`assets` commands or the dedicated Figma API for that.
- Politeness jitter slows reads on purpose; do not remove it.
