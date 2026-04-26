# `foxpilot auth`

`foxpilot auth` explains and manages where Foxpilot stores authentication
state. It separates browser session state from ordinary local secrets.

## Storage Model

Foxpilot uses `~/.local/share/foxpilot/` as its private application data
directory.

| Path | Purpose | Contents |
|---|---|---|
| `automation-profile/` | Dedicated browser profile for `claude` mode | Browser cookies, localStorage, `user.js`, profile databases |
| `secrets/` | Non-browser local secrets | API tokens or auth config for future integrations |
| `claude-profile/` | Legacy name | Migrated to `automation-profile/` when safe |

Browser cookies belong in the automation profile because Firefox/Zen expects
session auth to live in browser profile files such as `cookies.sqlite` and
`webappsstore.sqlite`. They should not be copied into `.env`, project
`.secrets`, or generic token files.

API tokens are different. They are not browser profile state, so they belong in
`~/.local/share/foxpilot/secrets/` when Foxpilot needs them.

## Commands

### `foxpilot auth`

Show the current auth storage paths and a short explanation of what belongs
where.

```bash
foxpilot auth
```

### `foxpilot auth status`

Alias for the default status view.

```bash
foxpilot auth status
```

### `foxpilot auth init`

Create or repair the private storage directories.

```bash
foxpilot auth init
```

This ensures directories are owner-only (`0700`) and creates a short
`secrets/README.txt` file as owner-only (`0600`). It also migrates a legacy
`claude-profile/` directory to `automation-profile/` when the new path does not
already exist.

For compatibility, this still works:

```bash
foxpilot auth --init
```

### `foxpilot auth explain`

Print the authentication model in plain language.

```bash
foxpilot auth explain
```

Use this when you need to know whether something should live in the browser
profile or in the secrets directory.

### `foxpilot auth doctor`

Check permissions and legacy profile state.

```bash
foxpilot auth doctor
```

The command exits nonzero if a directory is too broadly readable/writable or a
legacy profile still needs migration.

### `foxpilot auth migrate`

Rename a legacy `claude-profile/` directory to `automation-profile/` when safe.

```bash
foxpilot auth migrate
```

If both directories already exist, Foxpilot does not merge them automatically.
That avoids losing cookies or silently mixing two browser sessions.

## Cookie Import

Use `import-cookies` to copy browser auth from your real Zen profile into the
automation profile:

```bash
foxpilot import-cookies --domain youtube.com --domain google.com --include-storage
```

`--domain` is repeatable. This matters for Google-owned apps such as YouTube
Music because the UI may need both YouTube cookies and Google account cookies.

`--include-passwords` copies `logins.json` and `key4.db`. Avoid it unless you
explicitly need saved browser passwords in the automation profile.

## Rules

- Browser cookies/session/localStorage stay in `automation-profile/`.
- API tokens and non-browser auth config belong in `secrets/`.
- Do not put auth material in repo-local `.secrets` directories.
- Do not commit anything under `~/.local/share/foxpilot/`.
- Do not symlink auth directories; Foxpilot refuses symlinked auth storage.
