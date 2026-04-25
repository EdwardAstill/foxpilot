# `foxpilot youtube-music`

YouTube Music helpers: search, playback control, now-playing, and playlist management.

## Status

`foxpilot youtube-music` ships as a built-in Typer command branch backed by
`src/foxpilot/sites/youtube_music.py` and `src/foxpilot/sites/youtube_music_service.py`.
It is registered with the plugin registry as the `youtube-music` plugin.

YouTube Music is a YouTube-frontend; the service layer reuses
`foxpilot.sites.youtube_service.extract_video_id` for URL parsing.

## Authentication

YouTube Music requires a logged-in Google account for personalised library,
playlists, and add-to-playlist actions. The recommended flow:

```bash
foxpilot login https://music.youtube.com
```

If you already have a signed-in session in your main Zen browser you can
reuse those cookies in the claude profile:

```bash
foxpilot import-cookies --domain youtube.com --include-storage
```

`--zen` is supported when you want to drive your real browser session.

## Mode Support

| Command | claude | visible | zen | headless |
|---|---:|---:|---:|---:|
| `help` | yes | yes | yes | yes |
| `open` | yes | yes | yes | best effort |
| `search` | yes | yes | yes | best effort |
| `play` | yes | yes | yes | no |
| `pause` / `resume` / `next` / `previous` | yes | yes | yes | no |
| `now-playing` | yes | yes | yes | best effort |
| `playlists` | yes | yes | yes | best effort |
| `playlist` | yes | yes | yes | best effort |
| `add-to-playlist` | yes | yes | yes | no |

`headless` is best-effort because YouTube Music gates a lot of UI on
authenticated state and a real layout engine.

## Commands

### `help`

Show usage and examples.

```bash
foxpilot youtube-music help
```

### `open [section]`

Open YouTube Music home, or a named section.

Sections: `home`, `explore`, `library`, `playlists`.

```bash
foxpilot youtube-music open
foxpilot youtube-music open library
foxpilot youtube-music open playlists --json
```

### `search "<query>" [--kind ...] [--limit N] [--json]`

Search YouTube Music. `--kind` is one of `track`, `artist`, `album`, `playlist`
and is applied as a client-side filter against visible row metadata.

```bash
foxpilot youtube-music search "deftones change"
foxpilot youtube-music search "deftones" --kind album --limit 5 --json
```

### `play <target>`

Start playback for a watch URL, video id, or top hit of a free-text query.

```bash
foxpilot youtube-music play https://music.youtube.com/watch?v=VIDEO_ID
foxpilot youtube-music play "deftones change"
```

### `pause` / `resume` / `next` / `previous`

Toggle the play/pause button or skip tracks via the player bar.

```bash
foxpilot youtube-music pause
foxpilot youtube-music resume
foxpilot youtube-music next
foxpilot youtube-music previous
```

### `now-playing [--json]`

Report the currently playing track from the persistent player bar.

```bash
foxpilot youtube-music now-playing
foxpilot youtube-music now-playing --json
```

### `playlists [--json]`

List playlists from your library.

```bash
foxpilot youtube-music playlists --json
```

### `playlist <name-or-url>`

Open a playlist by name (matched against visible rows on the library page) or
by direct URL, and dump its track list.

```bash
foxpilot youtube-music playlist "Daily mix 1"
foxpilot youtube-music playlist https://music.youtube.com/playlist?list=PL... --json
```

### `add-to-playlist <playlist> <track> --yes`

Add a track to a playlist. Requires `--yes` because it modifies your library.

```bash
foxpilot youtube-music add-to-playlist "Daily mix 1" "deftones change" --yes
```

## JSON Output

All read commands accept `--json`. Shapes:

Search result row:

```json
{
  "title": "Change (In the House of Flies)",
  "url": "https://music.youtube.com/watch?v=...",
  "kind": "track",
  "artist": "Deftones",
  "album": "White Pony",
  "duration": "5:00"
}
```

Now-playing:

```json
{
  "title": "Change (In the House of Flies)",
  "artist": "Deftones",
  "album": "White Pony",
  "byline": "Deftones • White Pony • 2000",
  "position": "1:23",
  "duration": "5:00",
  "url": "https://music.youtube.com/watch?v=..."
}
```

Playlist detail:

```json
{
  "name": "Daily mix 1",
  "tracks": [
    {"title": "...", "artist": "...", "album": "...", "duration": "...", "url": "..."}
  ]
}
```

## Failure Modes

- Login required: run `foxpilot login https://music.youtube.com`, then retry.
- Player bar not present: open `music.youtube.com` and start a track first.
- Playlist name not found: run `foxpilot youtube-music playlists` to list available names, or pass a full playlist URL.
- Add-to-playlist menu shape changed: re-run with `--visible` and inspect via `foxpilot find` / `foxpilot html`.
- DOM drift: selectors live in `_find_player_bar`, `_extract_track_metadata`, and the helpers in `youtube_music.py`; tune those when the YT Music UI rolls a new layout.

## Limitations

- Search filters (`--kind`) operate on visible row metadata; YouTube Music's
  own chip-based filtering is not applied URL-side.
- No queue editing, no like/dislike, no shuffle/repeat toggles yet.
- No bulk track import, no playlist creation, no track removal — single-track
  add only, gated by `--yes`.
