# `foxpilot onedrive`

OneDrive Online helpers for browser-first navigation: open common views, list visible files and folders, search, select items, download files, open an item by name, and read the current breadcrumb path.

Microsoft's support docs describe OneDrive on the web as the place to sign in, view files, upload files, and open Office documents in Microsoft 365 for the web. Foxpilot uses that web surface rather than the Microsoft Graph API.

## Authentication

OneDrive normally requires a signed-in Microsoft account. Use the dedicated Foxpilot profile when possible:

```bash
foxpilot login https://onedrive.live.com
foxpilot import-cookies --domain live.com --include-storage
foxpilot import-cookies --domain microsoft365.com --include-storage
```

Use `--zen` when the command needs your real browser session:

```bash
foxpilot --zen onedrive files
```

## Accounts

| Account | Start URL | Use when |
|---|---|---|
| `personal` | `https://onedrive.live.com/` | Personal Microsoft account |
| `work` | `https://www.microsoft365.com/onedrive` | Work or school Microsoft 365 account |

Aliases: `business`, `school`, `m365`, and `office` map to `work`; `consumer` and `live` map to `personal`.

## Mode Support

| Command | claude | visible | zen | headless |
|---|---:|---:|---:|---:|
| `help` | yes | yes | yes | yes |
| `open` | yes | yes | yes | usually no |
| `files` | yes | yes | yes | usually no |
| `search` | yes | yes | yes | usually no |
| `select` | yes | yes | yes | usually no |
| `download` | yes | yes | yes | usually no |
| `download-selected` | yes | yes | yes | usually no |
| `wait-download` | yes | yes | yes | yes |
| `open-item` | yes | yes | yes | usually no |
| `path` | yes | yes | yes | usually no |

Headless mode is usually not useful for OneDrive because Microsoft sign-in and the file app are interactive.

## Commands

### `help`

```bash
foxpilot onedrive help
```

### `open [view-or-url]`

Open OneDrive at a high-level view or direct OneDrive URL.

```bash
foxpilot onedrive open
foxpilot onedrive open files
foxpilot onedrive open recent
foxpilot onedrive open shared
foxpilot onedrive open photos
foxpilot onedrive open recycle
foxpilot onedrive open shared --account work
foxpilot onedrive open https://onedrive.live.com/
```

Known views: `home`, `files`, `recent`, `shared`, `photos`, `recycle`.

For personal OneDrive, Foxpilot navigates to `onedrive.live.com` view URLs. For work/school OneDrive, Foxpilot opens Microsoft 365 OneDrive and then best-effort clicks the visible navigation label for the requested view.

### `files`

List visible files and folders on the current OneDrive page.

```bash
foxpilot onedrive files
foxpilot onedrive files --limit 20
foxpilot onedrive files --json
```

Returned fields include visible name, URL, inferred kind, modified date, size, and shared flag when visible.

### `search <query>`

Search OneDrive through the web UI and list visible results.

```bash
foxpilot onedrive search "budget 2026"
foxpilot onedrive search "invoice" --account work
foxpilot onedrive search "slides" --json
```

If Foxpilot cannot find the search box, retry visibly:

```bash
foxpilot --visible onedrive search "budget 2026"
```

### `select <name>`

Select a visible file or folder without opening it.

```bash
foxpilot onedrive select "Budget.xlsx"
foxpilot onedrive select "Project Docs" --json
```

Use `foxpilot onedrive files` first if you need the exact visible name. Selection uses the row checkbox when OneDrive exposes one.

### `download <name>`

Select a visible file or folder, click OneDrive's Download action, and wait for a completed file to appear in the watched download directory.

```bash
foxpilot onedrive download "Budget.xlsx"
foxpilot onedrive download "Budget.xlsx" --dir ~/Downloads --timeout 90
foxpilot onedrive download "Project Docs" --dir /tmp/onedrive-downloads --json
```

The `--dir` option is the directory Foxpilot watches for completed downloads. It should match the browser's actual download destination. Firefox/Zen usually downloads to `~/Downloads` unless you configured another path.

### `download-selected`

Click Download for the current OneDrive selection and wait for a completed file.

```bash
foxpilot onedrive download-selected
foxpilot onedrive download-selected --dir ~/Downloads --timeout 90
```

This is useful when you selected files manually or with `foxpilot onedrive select`.

### `wait-download`

Wait for a new completed browser download to appear. `wait-for-download` is also registered as a longer alias.

```bash
foxpilot onedrive wait-download --dir ~/Downloads
foxpilot onedrive wait-for-download --dir ~/Downloads --timeout 120 --json
```

Foxpilot ignores temporary download files such as `.part`, `.crdownload`, and `.tmp`, and returns only completed files.

### `open-item <name>`

Open a visible file or folder by name.

```bash
foxpilot onedrive open-item "Budget.xlsx"
foxpilot onedrive open-item "Project Docs"
```

Use `foxpilot onedrive files` first if you need the exact visible name.

### `path`

Show the current OneDrive breadcrumb path.

```bash
foxpilot onedrive path
foxpilot onedrive path --json
```

## JSON Output

Commands with `--json` return stable dictionaries or lists.

File item shape:

```json
{
  "name": "Budget.xlsx",
  "url": "https://onedrive.live.com/...",
  "kind": "file",
  "modified": "Yesterday",
  "size": "12 KB",
  "shared": false,
  "owner": ""
}
```

Path shape:

```json
{
  "path": ["My files", "Projects"],
  "url": "https://onedrive.live.com/...",
  "title": "OneDrive"
}
```

Download shape:

```json
{
  "status": "downloaded",
  "name": "Budget.xlsx",
  "download_dir": "/home/alice/Downloads",
  "files": ["/home/alice/Downloads/Budget.xlsx"],
  "url": "https://onedrive.live.com/..."
}
```

## Failure Modes

- Sign-in page or consent prompt: run `foxpilot login https://onedrive.live.com` or use `--zen`.
- Browser unavailable or Marionette port errors: run `foxpilot doctor`; Foxpilot needs local WebDriver socket access and writable auth storage.
- Empty `files` output: wait for OneDrive to finish rendering or retry with `foxpilot --visible onedrive files`.
- Search box not found: OneDrive UI may have changed; use `foxpilot page inputs` or `foxpilot page buttons` to inspect the visible controls.
- Download timeout: check that the browser is downloading to the same directory passed with `--dir`, and retry visibly if OneDrive shows a confirmation prompt.
- `open-item` cannot find a name: run `foxpilot onedrive files` and copy the exact visible name.

## Sources

- Microsoft Support: [Using Office for the web in OneDrive](https://support.microsoft.com/en-us/office/using-office-for-the-web-in-onedrive-dc62cfd4-120f-4dc8-b3a6-7aec6c26b55d)
- Microsoft Support: [Introducing the new OneDrive app for Microsoft 365 web and Microsoft 365 Windows](https://support.microsoft.com/en-us/office/introducing-the-new-onedrive-app-for-microsoft-365-web-and-microsoft-365-windows-b63dc035-c2fb-4912-9bd2-102968981c82)
