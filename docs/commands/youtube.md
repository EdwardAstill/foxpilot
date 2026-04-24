# `foxpilot youtube`

YouTube helpers for common agent workflows: search, open, metadata extraction, and transcript extraction.

## Status

`foxpilot youtube` is available today as a built-in Typer command branch backed by `src/foxpilot/sites/youtube.py` and `src/foxpilot/sites/youtube_service.py`.

The plugin registry now exposes YouTube as a built-in `youtube` plugin while reusing the existing command branch and service module. Use the commands below as the source of truth for the current CLI.

## Authentication

Public videos and search pages often work without login. Some pages require a logged-in profile or show consent and anti-automation screens.

Use the dedicated Foxpilot profile when possible:

```bash
foxpilot login https://youtube.com
foxpilot import-cookies --domain youtube.com --include-storage
```

Use `--zen` only when the command needs your real browser session.

## Mode Support

| Command | claude | visible | zen | headless |
|---|---:|---:|---:|---:|
| `help` | yes | yes | yes | yes |
| `search` | yes | yes | yes | best effort |
| `open` | yes | yes | yes | best effort |
| `metadata` | yes | yes | yes | best effort |
| `transcript` | yes | yes | yes | best effort |

`headless` is best effort because YouTube may require consent, login, or JavaScript state that is easier to handle in the persisted `claude` profile.

## Commands

### `help`

Show branch examples, auth notes, and mode guidance.

```bash
foxpilot youtube help
```

### `search <query>`

Search YouTube and return visible video results.

```bash
foxpilot youtube search "rust async tutorial"
foxpilot youtube search "python pathlib" --limit 5
foxpilot youtube search "browser automation" --json
```

Returned fields include title, URL, video id, channel, duration, views, published date, and thumbnail when visible.

### `open <target>`

Open a YouTube URL, video id, or search query.

```bash
foxpilot youtube open https://www.youtube.com/watch?v=VIDEO_ID
foxpilot youtube open https://youtu.be/VIDEO_ID
foxpilot youtube open "rust async tutorial"
foxpilot youtube open "rust async tutorial" --kind video
```

By default, plain text opens YouTube search results. With `--kind video`, Foxpilot searches and opens the first visible video result.

### `metadata [url]`

Extract metadata from the current YouTube page or from a provided URL.

```bash
foxpilot youtube metadata
foxpilot youtube metadata https://www.youtube.com/watch?v=VIDEO_ID
foxpilot youtube metadata --json
```

Video metadata includes title, URL, video id, channel, channel URL, views, published date, duration, description, and short/live flags when available.

### `transcript [url]`

Extract a transcript from the current YouTube page or from a provided URL.

```bash
foxpilot youtube transcript
foxpilot youtube transcript https://www.youtube.com/watch?v=VIDEO_ID
foxpilot youtube transcript --lang en
foxpilot youtube transcript --format segments
foxpilot youtube transcript --format srt
foxpilot youtube transcript --format json
```

Transcript extraction is best effort. It first tries caption data exposed by the loaded page, then falls back to visible transcript panel extraction. If captions are disabled, hidden, age-gated, region-gated, or blocked by a UI change, the command exits non-zero and prints the current URL plus the next action to try.

Planned plugin extensions include playlist inspection and comment extraction. Those commands are not part of the current command branch unless `foxpilot youtube --help` shows them in your checkout.

## JSON Output

Structured commands support `--json` or `--format json`.

Search result shape:

```json
{
  "title": "Example Video",
  "url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "video_id": "VIDEO_ID",
  "channel": "Example Channel",
  "channel_url": "https://www.youtube.com/@example",
  "duration": "12:34",
  "views": "120K views",
  "published": "2 years ago",
  "thumbnail": "https://..."
}
```

Transcript shape:

```json
{
  "title": "Example Video",
  "url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "language": "en",
  "segments": [
    {
      "start": 0.0,
      "duration": 2.5,
      "text": "Example transcript text."
    }
  ],
  "text": "Example transcript text."
}
```

Search and metadata JSON are meant for downstream agents: prefer `--json` when the result will be parsed by another tool, and use the default text output for quick terminal inspection.

## Failure Modes

- Login or consent required: run `foxpilot login https://youtube.com`, then retry. If another browser profile already has the session, import it with `foxpilot import-cookies --domain youtube.com --include-storage`.
- Current page is not a watch page: pass an explicit URL or video id, for example `foxpilot youtube open https://www.youtube.com/watch?v=VIDEO_ID`.
- Transcript controls are missing: verify the video has captions, then retry with `--visible` so the transcript panel can be opened and inspected.
- YouTube blocked automation or showed an interstitial: retry in the default `claude` profile after logging in, or use `--zen` when you need the real browser session.
- YouTube DOM changed: inspect with `foxpilot --visible youtube metadata`, `foxpilot read`, `foxpilot find`, or `foxpilot html`, then file the page shape as implementation evidence.
- Headless blocked or incomplete: retry in the default `claude` profile or with `--zen`.

## Plugin Migration Notes

The plugin command shape remains:

```bash
foxpilot youtube search "rust async tutorial" --json
foxpilot youtube metadata --json
foxpilot youtube transcript --format json
```

The built-in plugin metadata points at the existing YouTube service so CLI and future MCP site tools can share the same behavior.
