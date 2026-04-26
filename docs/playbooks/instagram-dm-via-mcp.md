# Playbook — Instagram DM via the foxpilot MCP browser

A hands-on recipe for sending an Instagram DM end-to-end using the
**foxpilot MCP server's claude-profile browser**, when the high-level
`foxpilot instagram message` CLI can't run (typically because the
user's Zen browser is up but does not have Marionette enabled).

This playbook captures the working pattern after several failed
attempts so the next run can go straight from "find the contact" to
"message sent" without rediscovering the gotchas.

## When to use this playbook

- The user wants to send a DM to someone on Instagram and is happy for
  Claude to drive the browser interactively.
- The high-level CLI command fails or is blocked (e.g. Zen running
  without `--marionette`, or no contacts cache yet).
- You want a deterministic, "no fuzzy fallback" path you can step
  through one MCP call at a time.

## Prerequisites

1. The **foxpilot MCP server** is loaded in the session — that gives
   you the `mcp__foxpilot__*` tool family.
2. The **claude profile** has an active Instagram session (cookies in
   `~/.local/share/foxpilot/claude-profile`). If not, run the login
   step first (see Step 0 below).
3. You have **explicit user authorization** for the destructive part
   (sending the DM). Don't compose-and-send without it.

## Why the simpler routes fail

- **`foxpilot --zen instagram message ...`** — Errors with
  `Zen is already running but Marionette is not enabled.` foxpilot
  refuses to restart the user's real browser. So `--zen` is out
  unless the user restarts Zen with `--marionette`.
- **`foxpilot instagram message ...` (claude profile)** — Works in
  principle but requires a populated contacts cache (followers /
  following / inbox scrape), and you usually don't have one yet.
- **`mcp__foxpilot__fill` on the IG composer** — IG's composer is a
  Lexical-managed `contenteditable` div, not a real input. `fill`
  ends up matching the search bar instead, and even when it targets
  the right element React ignores the value.
- **`document.execCommand('insertText', ...)`** — Returns `true` but
  produces empty text. Lexical won't accept it.

The pattern below works around all four.

## The working flow

### Step 0 — make sure claude profile is signed in

Check status and try the home page:

```text
mcp__foxpilot__status
mcp__foxpilot__go { target_url: "https://www.instagram.com/" }
```

If the page shows the login wall ("Log into Instagram", username/
password fields), open the profile visibly so the **user** can sign
in once. Cookies persist after that — future runs are hidden.

```text
mcp__foxpilot__login { target_url: "https://www.instagram.com/" }
```

Hand off to the user. Wait for them to confirm. Then:

```text
mcp__foxpilot__hide
```

(`hide` is idempotent — fine to call even if the window is already
hidden.)

### Step 1 — own handle

Look at `mcp__foxpilot__page_understand` on the home page. Find the
sidebar `Profile` link — its `href` is `https://www.instagram.com/<your-handle>/`.
This is the signed-in user's handle. You'll need it for the
followers/following URLs if you ever do that route, and it's a good
sanity check that you're actually signed in as the right account.

### Step 2 — find the target

Click the sidebar Search link. It opens a panel with two `Search input`
fields:

```text
mcp__foxpilot__click { description: "Search" }
mcp__foxpilot__fill  { description: "Search input", value: "<query>" }
```

Pull the candidates with `page_understand` — look for `links` with
`href` like `https://www.instagram.com/<handle>/` and `text`
containing the candidate's display name. Mutual-followers indicators
appear in the same `text` field as `"... • Followed by alice + N more"`.

> ⚠ **Disambiguation gate.** If multiple matches, present them to the
> user with mutuals counts and the display name. Do NOT auto-pick.
> The cost of DMing the wrong person is high.

### Step 3 — open the conversation

Two routes; prefer the second when an existing thread already exists.

**Route A — click Message on the profile (flaky).**

```text
mcp__foxpilot__go    { target_url: "https://www.instagram.com/<handle>/" }
mcp__foxpilot__click { description: "Message", role: "button" }
```

Sometimes the first `click` doesn't navigate; the page title may flip
to the unread-count style (e.g. `(2) Instagram`) but the URL stays on
the profile. Re-clicking sometimes helps; usually Route B is faster.

**Route B — open the existing thread directly.**

After Route A's click, `page_understand` exposes a sidebar inbox link
with `href` like `https://www.instagram.com/direct/t/<thread_id>`.
That's the open conversation with this person. Navigate straight to
it:

```text
mcp__foxpilot__go { target_url: "https://www.instagram.com/direct/t/<thread_id>/" }
```

You can also pull this thread id from a prior `messages` run, or from
your DM inbox URL bar.

If there's **no** existing thread, you have to use Route A and hope
the click sticks. If it doesn't, fall back to clicking via JS:

```text
mcp__foxpilot__js {
  expression: "(() => { const btn = Array.from(document.querySelectorAll(\"[role='button'], button, div\")).find(b => (b.textContent||'').trim() === 'Message'); btn && btn.click(); return btn ? 'clicked' : 'no-button'; })()"
}
```

### Step 4 — type into the Lexical composer

This is the bit that breaks every "obvious" approach. Use a synthetic
`InputEvent` with `inputType: 'insertText'` and `data` set to the
message text. Dispatch `beforeinput` then `input`:

```text
mcp__foxpilot__js {
  expression: "(() => { const el = document.querySelector(\"div[role='textbox'][contenteditable='true']\"); if (!el) return 'no-composer'; el.focus(); const text = \"<MESSAGE TEXT>\"; el.dispatchEvent(new InputEvent('beforeinput', { inputType: 'insertText', data: text, bubbles: true, cancelable: true })); el.dispatchEvent(new InputEvent('input', { inputType: 'insertText', data: text, bubbles: true, cancelable: true })); return JSON.stringify({ text: (el.innerText||'').slice(0, 200) }); })()"
}
```

The returned `text` should match what you intended. If it's still
empty, you targeted the wrong element — confirm there's only one
`div[role='textbox'][contenteditable='true']` on the page and that
the URL is the thread URL (not the inbox listing).

### Step 5 — send

The Send button is a `[role='button']` with both `aria-label="Send"`
and visible text `Send`. Click it via JS — the high-level `click` tool
sometimes gets confused by inbox sidebar items also called "Send":

```text
mcp__foxpilot__js {
  expression: "(() => { const btn = Array.from(document.querySelectorAll(\"[role='button']\")).find(b => (b.textContent||'').trim() === 'Send' && b.getAttribute('aria-label') === 'Send'); if (!btn) return 'no-send-button'; btn.click(); return 'clicked'; })()"
}
```

### Step 6 — verify

Read the composer back; it should be empty. The just-sent text should
appear in the thread DOM:

```text
mcp__foxpilot__js {
  expression: "(() => { const el = document.querySelector(\"div[role='textbox'][contenteditable='true']\"); const composerText = (el && el.innerText) || ''; const sent = Array.from(document.querySelectorAll('span')).map(e => (e.textContent||'').trim()).filter(t => t.includes('<UNIQUE SUBSTRING OF MESSAGE>')); return JSON.stringify({ composerText, sentEchoed: sent.slice(0, 3) }); })()"
}
```

A clean send shows `composerText` empty and the message echoed in
`sentEchoed`.

### Step 7 — read the reply

`mcp__foxpilot__read` on the thread URL returns the full transcript as
plain text, including their reply when it arrives. You'll see lines
like `mads sent,<their text>` and `Seen just now`.

## Failure modes & fixes

| Symptom | Fix |
|---|---|
| `Zen is already running but Marionette is not enabled` | Don't use `--zen`. Use the claude profile via MCP (this playbook). Or have the user relaunch Zen with `--marionette`. |
| `mcp__foxpilot__fill` writes to the search bar instead of the composer | Don't use `fill` on Lexical. Use the `InputEvent` pattern in Step 4. |
| `execCommand('insertText', ...)` returns `true` but composer stays empty | Same — Lexical ignores execCommand. Use `InputEvent`. |
| Profile Message button click doesn't navigate | Open the existing `direct/t/<thread_id>/` URL directly (Route B), or click via JS. |
| `StaleElementReferenceError` on `fill`/`click` after a navigation | Re-run `page_understand` first to refresh element refs, then retry. |
| Multiple search hits | Stop. Show the user mutuals + display names. Wait for an explicit pick. Never auto-pick on a destructive action. |
| Target profile is private and you don't follow them | No Message button will appear. Tell the user; ask whether to follow first. Don't follow without explicit `--yes`-equivalent confirmation. |

## Hard rules

1. **Never compose and send without explicit authorization.** "Send
   her a message saying X" is fine. "Tell maddy something" is not —
   ask for content.
2. **Never auto-pick on ambiguous matches.** Always show the
   candidates with mutuals/display name and require a numeric pick
   from the user.
3. **Never type credentials.** Use `mcp__foxpilot__login` and hand
   off to the user.
4. **Verify after sending.** Confirm the message text actually
   appears in the thread before reporting success.

## Promotion path

Once this pattern is reliable, fold the Step 4 / Step 5 JS snippets
into `foxpilot.sites.instagram_service.send_dm` so the high-level
`foxpilot instagram dm` and `foxpilot instagram message` CLIs can
drive the Lexical composer without the JS escape hatch. The current
selectors in `send_dm` rely on `send_keys` to a `contenteditable`,
which is what the live Lexical composer rejects.
