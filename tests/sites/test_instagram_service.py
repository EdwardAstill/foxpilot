"""Unit tests for foxpilot.sites.instagram_service URL/handle/format helpers."""

from __future__ import annotations

import pytest

from foxpilot.sites import instagram_service as svc


# ---------------------------------------------------------------------------
# is_instagram_url
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "value,expected",
    [
        ("https://www.instagram.com/", True),
        ("https://instagram.com/natgeo/", True),
        ("https://au.instagram.com/natgeo/", True),
        ("https://example.com/", False),
        ("", False),
        ("not-a-url", False),
    ],
)
def test_is_instagram_url(value, expected):
    assert svc.is_instagram_url(value) is expected


# ---------------------------------------------------------------------------
# section_url
# ---------------------------------------------------------------------------

def test_section_url_known():
    assert svc.section_url("home") == "https://www.instagram.com/"
    assert svc.section_url("explore") == "https://www.instagram.com/explore/"
    assert svc.section_url("reels") == "https://www.instagram.com/reels/"
    assert svc.section_url("direct") == "https://www.instagram.com/direct/inbox/"
    assert svc.section_url("notifications") == "https://www.instagram.com/accounts/activity/"


def test_section_url_case_insensitive():
    assert svc.section_url("EXPLORE") == "https://www.instagram.com/explore/"
    assert svc.section_url("  Direct  ") == "https://www.instagram.com/direct/inbox/"


def test_section_url_unknown_raises():
    with pytest.raises(ValueError):
        svc.section_url("nope")
    with pytest.raises(ValueError):
        svc.section_url("")


# ---------------------------------------------------------------------------
# normalize_handle + profile_url
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "value,expected",
    [
        ("natgeo", "natgeo"),
        ("@natgeo", "natgeo"),
        ("  natgeo  ", "natgeo"),
        ("natgeo/", "natgeo"),
        ("https://www.instagram.com/natgeo/", "natgeo"),
        ("https://www.instagram.com/natgeo", "natgeo"),
        ("www.instagram.com/natgeo/", "natgeo"),
        ("instagram.com/natgeo", "natgeo"),
        ("first.last_1234", "first.last_1234"),
    ],
)
def test_normalize_handle_ok(value, expected):
    assert svc.normalize_handle(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "/",
        "bad handle with spaces",
        "weird!chars",
        "way_too_long_handle_that_exceeds_thirty_chars_for_real",
    ],
)
def test_normalize_handle_bad(value):
    with pytest.raises(ValueError):
        svc.normalize_handle(value)


def test_profile_url():
    assert svc.profile_url("natgeo") == "https://www.instagram.com/natgeo/"
    assert (
        svc.profile_url("https://www.instagram.com/natgeo/")
        == "https://www.instagram.com/natgeo/"
    )
    assert svc.profile_url("@natgeo") == "https://www.instagram.com/natgeo/"


# ---------------------------------------------------------------------------
# normalize_tag + tag_url
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "value,expected",
    [
        ("wildlife", "wildlife"),
        ("#wildlife", "wildlife"),
        ("Wildlife", "wildlife"),
        ("  #wildlife  ", "wildlife"),
        ("photo_of_the_day", "photo_of_the_day"),
    ],
)
def test_normalize_tag_ok(value, expected):
    assert svc.normalize_tag(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "with spaces",
        "weird!chars",
    ],
)
def test_normalize_tag_bad(value):
    with pytest.raises(ValueError):
        svc.normalize_tag(value)


def test_tag_url():
    assert svc.tag_url("wildlife") == "https://www.instagram.com/explore/tags/wildlife/"
    assert svc.tag_url("#wildlife") == "https://www.instagram.com/explore/tags/wildlife/"


# ---------------------------------------------------------------------------
# post_url / reel_url
# ---------------------------------------------------------------------------

def test_post_url():
    assert svc.post_url("CXXXXXXXX") == "https://www.instagram.com/p/CXXXXXXXX/"


def test_post_url_strips_slashes():
    assert svc.post_url("/CXXXXXXXX/") == "https://www.instagram.com/p/CXXXXXXXX/"


def test_post_url_empty():
    with pytest.raises(ValueError):
        svc.post_url("")


def test_reel_url():
    assert svc.reel_url("CYYYYYYYY") == "https://www.instagram.com/reel/CYYYYYYYY/"


def test_reel_url_empty():
    with pytest.raises(ValueError):
        svc.reel_url("")


# ---------------------------------------------------------------------------
# search_url
# ---------------------------------------------------------------------------

def test_search_url_basic():
    url = svc.search_url("national geographic")
    assert url.startswith("https://www.instagram.com/explore/search/keyword/?")
    assert "q=national+geographic" in url


def test_search_url_special_chars():
    url = svc.search_url("c++ photographer")
    assert "q=c%2B%2B+photographer" in url


def test_search_url_empty():
    with pytest.raises(ValueError):
        svc.search_url("")
    with pytest.raises(ValueError):
        svc.search_url("   ")


# ---------------------------------------------------------------------------
# direct_thread_url
# ---------------------------------------------------------------------------

def test_direct_thread_url():
    url = svc.direct_thread_url("abc123")
    assert url == "https://www.instagram.com/direct/t/abc123/"


def test_direct_thread_url_quoting():
    url = svc.direct_thread_url("a/b c")
    assert "direct/t/a%2Fb%20c/" in url


def test_direct_thread_url_empty():
    with pytest.raises(ValueError):
        svc.direct_thread_url("")


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def test_format_open_result():
    out = svc.format_open_result({"title": "T", "url": "U", "section": "explore"})
    assert "title: T" in out
    assert "url: U" in out
    assert "section: explore" in out


def test_format_profile_basic():
    data = {
        "handle": "natgeo",
        "name": "National Geographic",
        "bio": "Stories that matter.",
        "posts": "29,123",
        "followers": "281M",
        "following": "143",
        "url": "https://www.instagram.com/natgeo/",
    }
    out = svc.format_profile(data)
    assert "handle: natgeo" in out
    assert "followers: 281M" in out


def test_format_profile_empty():
    assert svc.format_profile({}) == "(no profile data)"


def test_format_posts_empty():
    assert svc.format_posts([]) == "(no posts)"


def test_format_posts_basic():
    out = svc.format_posts([
        {"shortcode": "C1", "caption": "Cap", "url": "U"},
    ])
    assert "[1] C1" in out
    assert "caption: Cap" in out
    assert "url: U" in out


def test_format_search_results_empty():
    assert svc.format_search_results([]) == "(no search results)"


def test_format_search_results_basic():
    out = svc.format_search_results([
        {"kind": "user", "label": "@natgeo", "subtitle": "National Geographic", "url": "U"},
    ])
    assert "[1] (user) @natgeo" in out
    assert "subtitle: National Geographic" in out


def test_format_threads_empty():
    assert svc.format_threads([]) == "(no direct threads)"


def test_format_threads_basic():
    out = svc.format_threads([
        {"peer": "P", "snippet": "S", "when": "W", "thread_id": "T"},
    ])
    assert "[1] P" in out
    assert "snippet: S" in out
    assert "thread: T" in out


# ---------------------------------------------------------------------------
# polite_jitter
# ---------------------------------------------------------------------------

def test_polite_jitter_calls_sleep(monkeypatch):
    captured: list[float] = []
    monkeypatch.setattr(svc.time, "sleep", lambda s: captured.append(s))
    monkeypatch.setattr(svc.random, "random", lambda: 0.5)
    svc.polite_jitter()
    assert captured == [0.7 + 0.5 * 0.8]


def test_polite_jitter_custom(monkeypatch):
    captured: list[float] = []
    monkeypatch.setattr(svc.time, "sleep", lambda s: captured.append(s))
    monkeypatch.setattr(svc.random, "random", lambda: 0.0)
    svc.polite_jitter(min_secs=2.0, spread=3.0)
    assert captured == [2.0]


# ---------------------------------------------------------------------------
# home_url
# ---------------------------------------------------------------------------

def test_home_url():
    assert svc.home_url() == "https://www.instagram.com/"


# ---------------------------------------------------------------------------
# Internal classifier
# ---------------------------------------------------------------------------

def test_classify_search_href_user():
    kind, label = svc._classify_search_href("https://www.instagram.com/natgeo/")
    assert kind == "user"
    assert label == "@natgeo"


def test_classify_search_href_tag():
    kind, label = svc._classify_search_href("https://www.instagram.com/explore/tags/wildlife/")
    assert kind == "tag"
    assert label == "#wildlife"


def test_classify_search_href_post():
    kind, label = svc._classify_search_href("https://www.instagram.com/p/CXXXXXXXX/")
    assert kind == "post"
    assert label == "CXXXXXXXX"


def test_classify_search_href_reel():
    kind, label = svc._classify_search_href("https://www.instagram.com/reel/CYYYYYYYY/")
    assert kind == "reel"
    assert label == "CYYYYYYYY"


def test_classify_search_href_empty():
    assert svc._classify_search_href("") == ("", "")
    assert svc._classify_search_href("https://www.instagram.com/")[0] == ""


def test_shortcode_from_url():
    assert svc._shortcode_from_url("https://www.instagram.com/p/CXXX/") == "CXXX"
    assert svc._shortcode_from_url("https://www.instagram.com/reel/CYYY/") == "CYYY"
    assert svc._shortcode_from_url("https://www.instagram.com/natgeo/") == ""
    assert svc._shortcode_from_url("") == ""


# ---------------------------------------------------------------------------
# followers / following url builders
# ---------------------------------------------------------------------------

def test_followers_url():
    assert svc.followers_url("natgeo") == "https://www.instagram.com/natgeo/followers/"
    assert svc.followers_url("@natgeo") == "https://www.instagram.com/natgeo/followers/"


def test_following_url():
    assert svc.following_url("natgeo") == "https://www.instagram.com/natgeo/following/"


def test_followers_url_invalid():
    with pytest.raises(ValueError):
        svc.followers_url("")


# ---------------------------------------------------------------------------
# Contact cache
# ---------------------------------------------------------------------------

def test_save_and_load_contacts(tmp_path):
    cache_dir = tmp_path / "cache"
    contacts = [
        {"handle": "alice", "name": "Alice A", "source": "followers"},
        {"handle": "bob", "name": "Bob B", "source": "inbox"},
    ]
    svc.save_contacts("me", contacts, cache_dir=cache_dir, now=1000.0)
    loaded = svc.load_contacts("me", cache_dir=cache_dir, now=1000.0)
    assert loaded == contacts


def test_load_contacts_missing(tmp_path):
    assert svc.load_contacts("nope", cache_dir=tmp_path) == []


def test_load_contacts_stale(tmp_path):
    svc.save_contacts(
        "me",
        [{"handle": "a", "name": "A"}],
        cache_dir=tmp_path,
        now=1000.0,
    )
    # 25h later: stale
    assert svc.load_contacts("me", cache_dir=tmp_path, now=1000.0 + 25 * 3600) == []


def test_load_contacts_within_ttl(tmp_path):
    svc.save_contacts(
        "me",
        [{"handle": "a", "name": "A"}],
        cache_dir=tmp_path,
        now=1000.0,
    )
    fresh = svc.load_contacts("me", cache_dir=tmp_path, now=1000.0 + 23 * 3600)
    assert len(fresh) == 1


def test_cache_path_uses_handle(tmp_path):
    path = svc.cache_path("@me", cache_dir=tmp_path)
    assert path == tmp_path / "me-contacts.json"


def test_default_cache_dir_respects_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert svc.default_cache_dir() == tmp_path / "foxpilot" / "instagram"


# ---------------------------------------------------------------------------
# merge_contacts
# ---------------------------------------------------------------------------

def test_merge_contacts_dedup_by_handle():
    a = [{"handle": "alice", "name": "", "source": "followers"}]
    b = [{"handle": "alice", "name": "Alice A", "source": "inbox"}]
    out = svc.merge_contacts(a, b)
    assert len(out) == 1
    assert out[0]["handle"] == "alice"
    assert out[0]["name"] == "Alice A"
    assert "followers" in out[0]["source"]


def test_merge_contacts_skips_blank_handles():
    out = svc.merge_contacts(
        [{"handle": "", "name": "Nope"}],
        [{"handle": "alice", "name": "A"}],
    )
    assert [c["handle"] for c in out] == ["alice"]


# ---------------------------------------------------------------------------
# fuzzy_match_contacts
# ---------------------------------------------------------------------------

CONTACTS = [
    {"handle": "maddy.rodriguez", "name": "Maddy Rodriguez", "source": "followers"},
    {"handle": "maddyrod", "name": "Maddy R.", "source": "inbox"},
    {"handle": "rodtheguy", "name": "Rod Stewart", "source": "followers"},
    {"handle": "alice", "name": "Alice A", "source": "followers"},
]


def test_fuzzy_match_token_and():
    out = svc.fuzzy_match_contacts(CONTACTS, "maddy rodriguez")
    handles = [m["handle"] for m in out]
    assert "maddy.rodriguez" in handles
    assert "rodtheguy" not in handles
    assert "alice" not in handles


def test_fuzzy_match_partial_handle():
    out = svc.fuzzy_match_contacts(CONTACTS, "maddyrod")
    assert out and out[0]["handle"] == "maddyrod"


def test_fuzzy_match_case_insensitive():
    out = svc.fuzzy_match_contacts(CONTACTS, "MADDY")
    assert {m["handle"] for m in out} >= {"maddy.rodriguez", "maddyrod"}


def test_fuzzy_match_empty_query():
    assert svc.fuzzy_match_contacts(CONTACTS, "") == []
    assert svc.fuzzy_match_contacts(CONTACTS, "   ") == []


def test_fuzzy_match_no_hit():
    assert svc.fuzzy_match_contacts(CONTACTS, "zzz") == []


def test_fuzzy_match_score_orders_handle_first():
    out = svc.fuzzy_match_contacts(CONTACTS, "alice")
    assert out[0]["handle"] == "alice"
