"""Unit tests for foxpilot.sites.maps_service URL/format helpers."""

from __future__ import annotations

import pytest

from foxpilot.sites import maps_service as svc


@pytest.mark.parametrize(
    "value,expected",
    [
        ("https://www.google.com/maps", True),
        ("https://www.google.com/maps/search/coffee/", True),
        ("https://google.com/maps/dir/A/B/", True),
        ("https://www.google.com/", False),
        ("https://example.com/", False),
        ("", False),
    ],
)
def test_is_maps_url(value, expected):
    assert svc.is_maps_url(value) is expected


def test_search_url():
    url = svc.search_url("coffee near me")
    assert url.startswith("https://www.google.com/maps/search/")
    assert "coffee+near+me" in url


def test_search_url_empty():
    with pytest.raises(ValueError):
        svc.search_url("   ")


def test_directions_url_default_mode():
    url = svc.directions_url("London", "Paris")
    assert url.startswith("https://www.google.com/maps/dir/")
    assert "London" in url
    assert "Paris" in url
    assert "travelmode=0" in url  # 0 = driving


def test_directions_url_transit():
    url = svc.directions_url("London", "Paris", mode="transit")
    assert "travelmode=3" in url  # 3 = transit


def test_directions_url_walking():
    url = svc.directions_url("London", "Paris", mode="walking")
    assert "travelmode=2" in url  # 2 = walking


def test_directions_url_cycling():
    url = svc.directions_url("London", "Paris", mode="cycling")
    assert "travelmode=1" in url  # 1 = cycling


def test_directions_url_bicycling_alias():
    url = svc.directions_url("London", "Paris", mode="bicycling")
    assert "travelmode=1" in url


def test_directions_url_empty_origin():
    with pytest.raises(ValueError):
        svc.directions_url("   ", "Paris")


def test_directions_url_empty_destination():
    with pytest.raises(ValueError):
        svc.directions_url("London", "   ")


def test_directions_url_invalid_mode():
    with pytest.raises(ValueError):
        svc.directions_url("London", "Paris", mode="teleport")


def test_format_open_result():
    text = svc.format_open_result({"title": "Maps", "url": "https://x"})
    assert "title: Maps" in text
    assert "url: https://x" in text


def test_format_place_empty():
    assert svc.format_place({}) == "(no place data)"


def test_format_place_renders_known_fields():
    text = svc.format_place({"name": "Eiffel Tower", "address": "Paris", "rating": "4.6"})
    assert "name: Eiffel Tower" in text
    assert "address: Paris" in text
    assert "rating: 4.6" in text


def test_format_places_empty():
    assert svc.format_places([]) == "(no results)"


def test_format_places_renders():
    text = svc.format_places([{"name": "Cafe A", "rating": "4.5", "url": "https://x"}])
    assert "[1] Cafe A" in text
    assert "rating: 4.5" in text


def test_format_directions_empty():
    assert svc.format_directions({}) == "(no directions data)"


def test_format_directions_renders_with_steps():
    text = svc.format_directions({
        "origin": "London",
        "destination": "Paris",
        "duration": "5h 30min",
        "steps": ["Head south", "Take the ferry"],
    })
    assert "origin: London" in text
    assert "duration: 5h 30min" in text
    assert "[1] Head south" in text
    assert "[2] Take the ferry" in text
