"""Typer command branch for Instagram (instagram.com) workflows."""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from typing import Any, Callable, Optional

import typer

from foxpilot.core import browser
from foxpilot.sites._cli import emit as _emit, exit_error as _exit_error
from foxpilot.sites.instagram_service import (
    FOLLOWERS_DEFAULT_LIMIT,
    INSTAGRAM_HOME,
    click_follow_button,
    click_like_button,
    detect_own_handle,
    direct_thread_url,
    extract_direct_threads,
    extract_followers,
    extract_following,
    extract_posts,
    extract_profile,
    extract_search_results,
    followers_url,
    following_url,
    format_open_result,
    format_posts,
    format_profile,
    format_search_results,
    format_threads,
    fuzzy_match_contacts,
    is_instagram_url,
    load_contacts,
    merge_contacts,
    normalize_handle,
    polite_jitter,
    post_comment,
    post_url,
    profile_url,
    reel_url,
    save_contacts,
    scroll_user_list,
    search_url,
    section_url,
    send_dm,
    tag_url,
)


app = typer.Typer(
    help="Instagram navigation, profile, search, posts, and DM helpers.",
    no_args_is_help=True,
)

BrowserFactory = Callable[[], object]


def _default_browser():
    return browser()


_browser_factory: BrowserFactory = _default_browser


def set_browser_factory(factory: BrowserFactory) -> None:
    global _browser_factory
    _browser_factory = factory


@contextmanager
def _site_browser():
    with _browser_factory() as driver:
        yield driver


@app.command(name="help")
def cmd_help() -> None:
    """Show Instagram branch help and examples."""
    typer.echo(
        """foxpilot instagram - Instagram (instagram.com) helpers

Common commands:
  foxpilot instagram open                          # open Instagram home
  foxpilot instagram open explore                  # explore/reels/direct/notifications
  foxpilot instagram profile <handle-or-url>       # dump profile fields
  foxpilot instagram posts <handle> --limit 12     # recent post grid
  foxpilot instagram tag <name> --limit 10         # posts under a hashtag
  foxpilot instagram search "<query>"              # users/tags/locations
  foxpilot instagram messages                      # list DM threads
  foxpilot instagram follow <handle> --yes
  foxpilot instagram like <shortcode-or-url> --yes
  foxpilot instagram comment <shortcode-or-url> "..." --yes
  foxpilot instagram dm <handle-or-thread> "..." --yes
  foxpilot instagram message <name> "..." --yes        # fuzzy resolve from inbox/followers/following

Confirmation gate:
  `follow`, `like`, `comment`, `dm`, and `message` are destructive — they require --yes.

Rate limits:
  Instagram is aggressive about anti-bot. Reads add a 0.7-1.5s jitter
  between paginated batches. Keep --limit modest.

Auth:
  Default mode is --zen so the user's already-signed-in Zen session
  is reused. Instagram flags new-device sessions; expect a challenge
  prompt if you sign in fresh in the automation profile.

Modes:
  default --zen (recommended), --visible, claude (fragile)

Run:
  foxpilot instagram <command> --help"""
    )


@app.command(name="open")
def cmd_open(
    section: Optional[str] = typer.Argument(
        None,
        help="Optional section: home, explore, reels, direct, notifications.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open Instagram home or a specific section."""
    if section:
        try:
            url = section_url(section)
        except ValueError as exc:
            _exit_error(str(exc))
    else:
        url = INSTAGRAM_HOME
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.0)
        data = {
            "title": driver.title,
            "url": driver.current_url,
            "section": section or "",
        }
        _emit(data, json_output, format_open_result)


@app.command(name="profile")
def cmd_profile(
    handle_or_url: str = typer.Argument(..., help="Instagram handle, @handle, or profile URL."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open a profile and dump handle, name, bio, and counts."""
    try:
        url = profile_url(handle_or_url)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.0)
        if not is_instagram_url(driver.current_url):
            _exit_error(
                "redirected away from Instagram",
                url=driver.current_url,
                next_step="run `foxpilot --zen instagram open` and complete any challenge",
            )
        data = extract_profile(driver)
        _emit(data, json_output, format_profile)


@app.command(name="posts")
def cmd_posts(
    handle_or_url: str = typer.Argument(..., help="Instagram handle, @handle, or profile URL."),
    limit: int = typer.Option(12, "--limit", "-n", help="Maximum posts."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """List recent posts from a profile grid."""
    try:
        url = profile_url(handle_or_url)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.0)
        polite_jitter()
        results = extract_posts(driver, limit=limit)
        _emit(results, json_output, format_posts)


@app.command(name="tag")
def cmd_tag(
    name: str = typer.Argument(..., help="Hashtag name (without leading #)."),
    limit: int = typer.Option(12, "--limit", "-n", help="Maximum posts."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open a hashtag page and list recent posts."""
    try:
        url = tag_url(name)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.0)
        polite_jitter()
        results = extract_posts(driver, limit=limit)
        _emit(results, json_output, format_posts)


@app.command(name="search")
def cmd_search(
    query: str = typer.Argument(..., help="Search query."),
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum results."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Run an Instagram search and emit user/tag/location/post hits."""
    try:
        url = search_url(query)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.0)
        polite_jitter()
        results = extract_search_results(driver, limit=limit)
        _emit(results, json_output, format_search_results)


@app.command(name="messages")
def cmd_messages(
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum threads."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """List recent DM threads."""
    with _site_browser() as driver:
        driver.get(section_url("direct"))
        time.sleep(2.0)
        polite_jitter()
        results = extract_direct_threads(driver, limit=limit)
        _emit(results, json_output, format_threads)


@app.command(name="follow")
def cmd_follow(
    handle: str = typer.Argument(..., help="Instagram handle, @handle, or profile URL."),
    yes: bool = typer.Option(False, "--yes", help="Confirm sending the follow."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Follow an account (confirmation gated)."""
    if not yes:
        _exit_error(
            "follow requires confirmation",
            reason="this performs a real follow",
            next_step="re-run with --yes to follow",
        )
    try:
        url = profile_url(handle)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.0)
        if not click_follow_button(driver):
            _exit_error(
                "could not find the Follow button",
                url=driver.current_url,
                next_step="open the profile manually and verify Follow is visible",
            )
        data = {"handle": normalize_handle(handle), "url": driver.current_url, "followed": True}
        _emit(data, json_output, lambda d: f"followed {d['handle']}")


@app.command(name="like")
def cmd_like(
    target: str = typer.Argument(..., help="Post shortcode or full /p/<code>/ URL."),
    yes: bool = typer.Option(False, "--yes", help="Confirm liking."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Like a post (confirmation gated)."""
    if not yes:
        _exit_error(
            "like requires confirmation",
            reason="this performs a real like",
            next_step="re-run with --yes to like",
        )
    url = _resolve_post_target(target)
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.0)
        if not click_like_button(driver):
            _exit_error(
                "could not find the Like button",
                url=driver.current_url,
                next_step="retry with --visible to inspect the post",
            )
        data = {"target": target, "url": driver.current_url, "liked": True}
        _emit(data, json_output, lambda d: f"liked {d['target']}")


@app.command(name="comment")
def cmd_comment(
    target: str = typer.Argument(..., help="Post shortcode or full /p/<code>/ URL."),
    text: str = typer.Argument(..., help="Comment text."),
    yes: bool = typer.Option(False, "--yes", help="Confirm posting."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Post a comment on a post (confirmation gated)."""
    if not yes:
        _exit_error(
            "comment requires confirmation",
            reason="this posts a real comment",
            next_step="re-run with --yes to post",
        )
    if not text or not text.strip():
        _exit_error("empty comment text")
    url = _resolve_post_target(target)
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.0)
        if not post_comment(driver, text):
            _exit_error(
                "could not post the comment",
                url=driver.current_url,
                next_step="retry with --visible and verify the comment box is enabled",
            )
        data = {"target": target, "url": driver.current_url, "posted": True}
        _emit(data, json_output, lambda d: f"posted comment on {d['target']}")


@app.command(name="dm")
def cmd_dm(
    target: str = typer.Argument(..., help="Handle, @handle, profile URL, or /direct/t/<id>/ URL or thread id."),
    text: str = typer.Argument(..., help="Message text."),
    yes: bool = typer.Option(False, "--yes", help="Confirm sending the DM."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Send a DM to a profile or thread (confirmation gated)."""
    if not yes:
        _exit_error(
            "dm requires confirmation",
            reason="this sends a real DM",
            next_step="re-run with --yes to send",
        )
    if not text or not text.strip():
        _exit_error("empty message text")

    looks_like_thread = (
        "://" in target and "/direct/t/" in target
    ) or (target.replace("_", "").isalnum() and len(target) >= 8 and "/" not in target and "@" not in target)

    if looks_like_thread:
        url = target if "://" in target else direct_thread_url(target)
    else:
        try:
            url = profile_url(target)
        except ValueError as exc:
            _exit_error(str(exc))

    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.0)
        if not looks_like_thread:
            from foxpilot.sites._dom import find_one_xpath as _find_one_xpath

            btn = _find_one_xpath(driver, [
                "//header//div[@role='button' and normalize-space()='Message']",
                "//header//button[normalize-space()='Message']",
                "//a[normalize-space()='Message']",
            ])
            if btn is None:
                _exit_error(
                    "could not find Message button on profile",
                    url=driver.current_url,
                    next_step="ensure the account allows DMs from non-followers",
                )
            try:
                btn.click()
            except Exception:
                _exit_error("could not click Message button", url=driver.current_url)
            polite_jitter(0.5, 0.5)

        if not send_dm(driver, text):
            _exit_error(
                "could not send the DM",
                url=driver.current_url,
                next_step="retry with --visible and verify the composer is open",
            )
        data = {"target": target, "url": driver.current_url, "sent": True}
        _emit(data, json_output, lambda d: f"sent DM to {d['target']}")


@app.command(name="message")
def cmd_message(
    name: str = typer.Argument(..., help="Free-text name or partial handle to find a contact."),
    text: str = typer.Argument(..., help="Message text to send."),
    sources: str = typer.Option(
        "inbox,followers,following",
        "--source",
        help="Comma-separated lookup sources, in priority order.",
    ),
    pick: Optional[str] = typer.Option(
        None,
        "--pick",
        help="Disambiguate: handle to pick when multiple matches were shown previously.",
    ),
    refresh: bool = typer.Option(False, "--refresh", help="Bust the cached contacts list."),
    owner: Optional[str] = typer.Option(
        None,
        "--owner",
        help="Your own Instagram handle (auto-detected from session if omitted).",
    ),
    followers_limit: int = typer.Option(
        FOLLOWERS_DEFAULT_LIMIT,
        "--followers-limit",
        help="Cap rows scraped from followers/following lists.",
    ),
    yes: bool = typer.Option(False, "--yes", help="Confirm sending the DM."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Resolve `<name>` to a handle via inbox/followers/following, then DM them."""
    if not yes:
        _exit_error(
            "message requires confirmation",
            reason="this resolves a contact and sends a real DM",
            next_step="re-run with --yes to send",
        )
    if not text or not text.strip():
        _exit_error("empty message text")
    if not name or not name.strip():
        _exit_error("empty contact name")

    source_list = [s.strip().lower() for s in sources.split(",") if s.strip()]
    if not source_list:
        _exit_error("no sources specified")
    for s in source_list:
        if s not in {"inbox", "followers", "following"}:
            _exit_error(f"unknown source: {s!r}", next_step="use inbox,followers,following")

    with _site_browser() as driver:
        owner_handle = (owner or "").strip()
        if not owner_handle:
            driver.get(INSTAGRAM_HOME)
            time.sleep(2.0)
            owner_handle = detect_own_handle(driver)
            if not owner_handle:
                _exit_error(
                    "could not detect your own Instagram handle",
                    url=driver.current_url,
                    next_step="re-run with --owner <yourhandle> or open Instagram in --visible to verify the session",
                )

        cached = [] if refresh else load_contacts(owner_handle)
        contacts: list[dict[str, Any]] = list(cached)

        if not contacts:
            sourced: list[list[dict[str, Any]]] = []
            for source in source_list:
                if source == "inbox":
                    driver.get(section_url("direct"))
                    time.sleep(2.0)
                    polite_jitter()
                    inbox = extract_direct_threads(driver, limit=200)
                    rows = [
                        {
                            "handle": _slug_from_inbox_peer(item.get("peer", "")),
                            "name": item.get("peer", ""),
                            "source": "inbox",
                        }
                        for item in inbox
                        if item.get("peer")
                    ]
                    sourced.append([row for row in rows if row["handle"]])
                elif source == "followers":
                    driver.get(followers_url(owner_handle))
                    time.sleep(2.0)
                    scroll_user_list(driver)
                    rows = extract_followers(driver, limit=followers_limit)
                    for row in rows:
                        row["source"] = "followers"
                    sourced.append(rows)
                elif source == "following":
                    driver.get(following_url(owner_handle))
                    time.sleep(2.0)
                    scroll_user_list(driver)
                    rows = extract_following(driver, limit=followers_limit)
                    for row in rows:
                        row["source"] = "following"
                    sourced.append(rows)
            contacts = merge_contacts(*sourced)
            if contacts:
                save_contacts(owner_handle, contacts)

        if not contacts:
            _exit_error(
                "no contacts gathered",
                next_step="check that you are signed in (`foxpilot --zen --visible instagram open`) and retry with --refresh",
            )

        matches = fuzzy_match_contacts(contacts, name)
        if not matches:
            _exit_error(
                f"no contact matched {name!r}",
                next_step="re-run with --refresh to rescrape, or message a handle directly via `instagram dm`",
            )

        chosen: Optional[dict[str, Any]] = None
        if pick:
            wanted = normalize_handle(pick)
            chosen = next((m for m in matches if (m.get("handle") or "") == wanted), None)
            if chosen is None:
                _exit_error(
                    f"--pick {pick!r} did not match any candidate",
                    next_step="re-run without --pick to see the candidate list",
                )
        elif len(matches) == 1:
            chosen = matches[0]
        else:
            top = matches[:10]
            if json_output:
                typer.echo(json.dumps({"matches": top}, ensure_ascii=False, indent=2))
            else:
                typer.echo(f"multiple matches for {name!r}:")
                for i, m in enumerate(top, 1):
                    typer.echo(
                        f"  [{i}] @{m.get('handle','')}  "
                        f"name={m.get('name','')!r}  source={m.get('source','')}"
                    )
                typer.echo("re-run with --pick <handle> to disambiguate")
            raise typer.Exit(1)

        target_handle = chosen["handle"]
        url = profile_url(target_handle)
        driver.get(url)
        time.sleep(2.0)

        from foxpilot.sites.instagram_service import _find_one_xpath  # type: ignore

        btn = _find_one_xpath(driver, [
            "//header//div[@role='button' and normalize-space()='Message']",
            "//header//button[normalize-space()='Message']",
            "//a[normalize-space()='Message']",
        ])
        if btn is None:
            _exit_error(
                "could not find Message button on profile",
                url=driver.current_url,
                next_step="ensure this account allows DMs from you",
            )
        try:
            btn.click()
        except Exception:
            _exit_error("could not click Message button", url=driver.current_url)
        polite_jitter(0.5, 0.5)

        if not send_dm(driver, text):
            _exit_error(
                "could not send the DM",
                url=driver.current_url,
                next_step="retry with --visible and verify the composer is open",
            )
        data = {
            "query": name,
            "owner": owner_handle,
            "handle": target_handle,
            "name": chosen.get("name", ""),
            "source": chosen.get("source", ""),
            "url": driver.current_url,
            "sent": True,
        }
        _emit(data, json_output, lambda d: f"sent DM to @{d['handle']} (matched {d['query']!r})")


def _slug_from_inbox_peer(peer: str) -> str:
    """Heuristic: inbox peer text is usually a display name; only return when it
    happens to also be a valid handle. The fuzzy matcher uses `name` for the
    rest, so this is OK to leave blank."""
    candidate = (peer or "").strip()
    from foxpilot.sites.instagram_service import _HANDLE_RE  # type: ignore

    if candidate and _HANDLE_RE.match(candidate):
        return candidate.lower()
    return ""


def _resolve_post_target(target: str) -> str:
    raw = (target or "").strip()
    if "://" in raw:
        return raw
    if "/reel/" in raw:
        code = raw.rsplit("/reel/", 1)[1].strip("/").split("/")[0]
        return reel_url(code)
    if "/p/" in raw:
        code = raw.rsplit("/p/", 1)[1].strip("/").split("/")[0]
        return post_url(code)
    return post_url(raw)


