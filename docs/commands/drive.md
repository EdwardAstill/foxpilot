# `foxpilot drive`

Google Drive helpers for browser-first navigation: open common views, list visible files and folders, search Drive, download files via the right-click menu, open an item by name, and read the current breadcrumb path.

Foxpilot drives the Drive web UI rather than the Drive REST API. Use this plugin to script reads and downloads from your real signed-in Drive session.

## Status

Initial release. Selectors are best-effort; Drive is React-rendered and class names rotate.

## Authentication

Drive requires a signed-in Google account. Use the dedicated Foxpilot claude profile when possible:

```bash
foxpilot login https://drive.google.com
foxpilot import-cookies --domain google.com --include-storage
```

Use `--zen` when you want to reuse the Zen browser session:

```bash
foxpilot --zen drive files
```

## Mode Support

| Command | claude | visible | zen | headless |
|---|---:|---:|---:|---:|
| `help` | yes | yes | yes | yes |
| `open` | yes | yes | yes | best effort |
| `files` | yes | yes | yes | best effort |
| `search` | yes | yes | yes | best effort |
| `download` | yes | yes | yes | usually no |
| `wait-download` | yes | yes | yes | yes |
| `open-item` | yes | yes | yes | usually no |
| `path` | yes | yes | yes | best effort |

Default mode is `claude`.

## Commands

### `help`

```bash
foxpilot drive help
```

### `open [view-or-url]`

Open Drive at a high-level view or direct Drive URL.

```bash
foxpilot drive open
foxpilot drive open recent
foxpilot drive open starred
foxpilot drive open shared
foxpilot drive open trash
foxpilot drive open https://drive.google.com/drive/folders/0ABC123
```

Known views: `home`, `recent`, `starred`, `shared`, `trash`. Aliases include `my-drive`, `bin`, `favorites`, and `shared-with-me`.

### `files [--folder <id>] [--limit N] [--json]`

List visible files and folders on the current Drive page. Pass `--folder <id>` to navigate to a folder by id first.

```bash
foxpilot drive files
foxpilot drive files --limit 20
foxpilot drive files --folder 0ABC123def456 --json
```

Returned fields include visible name, URL, inferred kind (`folder`, `doc`, `sheet`, `slides`, `pdf`, `file`), owner, modified date, size, and shared flag when visible.

### `search "<query>"`

Search Drive through the web UI and list visible results. Foxpilot navigates to `https://drive.google.com/drive/search?q=...` and reads the rendered results.

```bash
foxpilot drive search "budget 2026"
foxpilot drive search "invoice" --json
```

If results do not appear, retry visibly:

```bash
foxpilot --visible drive search "budget 2026"
```

### `download <name>`

Right-click a visible Drive item, click Download, and wait for a completed file in the watched download directory.

```bash
foxpilot drive download "Budget.xlsx"
foxpilot drive download "Budget.xlsx" --dir ~/Downloads --timeout 90 --json
```

Drive downloads Google Docs/Sheets/Slides as exported files (typically `.docx`, `.xlsx`, `.pptx`). The `--dir` option must match the browser's actual download destination.

### `wait-download`

Wait for a new completed browser download to appear. `wait-for-download` is a longer alias.

```bash
foxpilot drive wait-download --dir ~/Downloads
foxpilot drive wait-for-download --dir ~/Downloads --timeout 120 --json
```

Foxpilot ignores temporary download files such as `.part`, `.crdownload`, and `.tmp`.

### `open-item <name>`

Open a visible file or folder by name (double-click).

```bash
foxpilot drive open-item "Budget.xlsx"
foxpilot drive open-item "Project Docs"
```

Use `foxpilot drive files` first to get the exact visible name.

### `path`

Show the current Drive breadcrumb path.

```bash
foxpilot drive path
foxpilot drive path --json
```

## JSON Output

Item shape:

```json
{
  "name": "Budget.xlsx",
  "url": "https://drive.google.com/...",
  "kind": "sheet",
  "owner": "me",
  "modified": "Yesterday",
  "size": "12 KB",
  "shared": false
}
```

Path shape:

```json
{
  "path": ["My Drive", "Projects"],
  "url": "https://drive.google.com/drive/folders/...",
  "title": "Projects - Google Drive"
}
```

Download shape:

```json
{
  "status": "downloaded",
  "name": "Budget.xlsx",
  "download_dir": "/home/alice/Downloads",
  "files": ["/home/alice/Downloads/Budget.xlsx"],
  "url": "https://drive.google.com/..."
}
```

## Failure Modes

- Sign-in or consent: run `foxpilot login https://drive.google.com` or use `--zen`.
- Browser unavailable: run `foxpilot doctor`.
- Empty `files` output: Drive may still be rendering; retry visibly with `foxpilot --visible drive files`.
- Search box not found: Drive UI may have changed; use `foxpilot page inputs` to inspect.
- Download timeout: confirm the browser downloads to the directory passed via `--dir`. Drive sometimes shows a "Zip preparing" prompt — retry visibly to dismiss.
- `open-item` cannot find a name: copy the exact visible name from `foxpilot drive files`.

## Limitations

- No Drive REST API; all operations go through the rendered web UI.
- Folder navigation by id only (Drive does not expose stable name-only URLs).
- Bulk operations and uploads are out of scope.
