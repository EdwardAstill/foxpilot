"""Unit tests for foxpilot.sites.twitter_service URL/format helpers."""

from __future__ import annotations

import pytest

from foxpilot.sites import twitter_service as svc


@pytest.mark.parametrize(
    "value,expected",
    [
        ("https://x.com/", True),
        ("https://www.x.com/jack", True),
        ("https://twitter.com/jack", True),
        ("https://example.com/", False),
        ("", False),
        ("not-a-url", False),
    ],
)
def test_is_twitter_url(value, expected):
    assert svc.is_twitter_url(value) is expected


@pytest.mark.parametrize(
    "section,expected_suffix",
    [
        ("home", "home"),
        ("explore", "explore"),
        ("notifications", "notifications"),
        ("messages", "messages"),
        ("bookmarks", "i/bookmarks"),
    ],
)
def test_section_url(section, expected_suffix):
    assert svc.section_url(section) == f"https://x.com/{expected_suffix}"


def test_section_url_unknown_raises():
    with pytest.raises(ValueError):
        svc.section_url("nope")


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("jack", "jack"),
        ("@jack", "jack"),
        ("/jack/", "jack"),
        ("https://x.com/jack", "jack"),
        ("https://twitter.com/jack/status/123", "jack"),
        ("x.com/jack", "jack"),
    ],
)
def test_normalize_username(raw, expected):
    assert svc.normalize_username(raw) == expected


@pytest.mark.parametrize("bad", ["", "   ", "@", "/", "in valid"])
def test_normalize_username_invalid(bad):
    with pytest.raises(ValueError):
        svc.normalize_username(bad)


def test_profile_url():
    assert svc.profile_url("jack") == "https://x.com/jack"


def test_search_url():
    url = svc.search_url("python tips")
    assert url.startswith("https://x.com/search?")
    assert "q=python+tips" in url


def test_search_url_with_tab():
    url = svc.search_url("python", tab="Latest")
    assert "f=Latest" in url


def test_search_url_empty():
    with pytest.raises(ValueError):
        svc.search_url("   ")


def test_tweet_url():
    assert svc.tweet_url("jack", "1234") == "https://x.com/jack/status/1234"


def test_tweet_url_empty_id():
    with pytest.raises(ValueError):
        svc.tweet_url("jack", "")


def test_format_open_result():
    text = svc.format_open_result({"title": "X", "url": "https://x", "section": "home"})
    assert "title: X" in text
    assert "section: home" in text


def test_format_profile_empty():
    assert svc.format_profile({}) == "(no profile data)"


def test_format_profile_renders_known_fields():
    text = svc.format_profile({"username": "jack", "name": "Jack", "followers": "5M"})
    assert "username: jack" in text
    assert "followers: 5M" in text


def test_format_tweets_empty():
    assert svc.format_tweets([]) == "(no tweets)"


def test_format_tweets_truncates_text():
    long = "x" * 500
    text = svc.format_tweets([{"text": long, "username": "jack"}])
    # Text gets truncated to 120 chars
    assert "x" * 120 in text
    assert "username: jack" in text
