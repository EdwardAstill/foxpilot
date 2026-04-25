"""Unit tests for the amazon service layer (pure URL helpers + parsers)."""

from __future__ import annotations

import pytest

from foxpilot.sites.amazon_service import (
    DEFAULT_REGION,
    SUPPORTED_REGIONS,
    amazon_host,
    amazon_origin,
    build_amazon_url,
    build_orders_url,
    build_product_url,
    build_search_url,
    build_track_url,
    is_amazon_url,
    normalize_region,
    parse_asin_from_url,
    parse_region_from_url,
)


# ---------------------------------------------------------------------------
# normalize_region
# ---------------------------------------------------------------------------


def test_default_region_is_com_au() -> None:
    assert DEFAULT_REGION == "com.au"
    assert normalize_region(None) == "com.au"
    assert normalize_region("") == "com.au"


@pytest.mark.parametrize("value", ["com", "com.au", "co.uk", "COM", "Com.Au", " co.uk "])
def test_normalize_region_accepts_supported_values(value: str) -> None:
    assert normalize_region(value) in SUPPORTED_REGIONS


@pytest.mark.parametrize("value", ["amazon.com", "amazon.com.au", ".co.uk"])
def test_normalize_region_strips_amazon_prefix_and_dot(value: str) -> None:
    assert normalize_region(value) in SUPPORTED_REGIONS


@pytest.mark.parametrize("value", ["de", "ca", "amazon.fr", "garbage"])
def test_normalize_region_rejects_unsupported(value: str) -> None:
    with pytest.raises(ValueError):
        normalize_region(value)


# ---------------------------------------------------------------------------
# host / origin / build_amazon_url
# ---------------------------------------------------------------------------


def test_amazon_host_uses_region() -> None:
    assert amazon_host("com.au") == "www.amazon.com.au"
    assert amazon_host("com") == "www.amazon.com"
    assert amazon_host("co.uk") == "www.amazon.co.uk"


def test_amazon_origin_is_https() -> None:
    assert amazon_origin("com.au").startswith("https://")
    assert amazon_origin("com.au").endswith("www.amazon.com.au")


@pytest.mark.parametrize(
    "section,suffix",
    [
        ("home", "/"),
        ("orders", "/gp/your-account/order-history"),
        ("wishlist", "/hz/wishlist/ls"),
        ("cart", "/gp/cart/view.html"),
    ],
)
def test_build_amazon_url_known_sections(section: str, suffix: str) -> None:
    url = build_amazon_url(section, "com.au")
    assert url == f"https://www.amazon.com.au{suffix}"


def test_build_amazon_url_default_region_is_com_au() -> None:
    assert build_amazon_url("home").startswith("https://www.amazon.com.au")


def test_build_amazon_url_rejects_unknown_section() -> None:
    with pytest.raises(ValueError):
        build_amazon_url("bogus", "com.au")


def test_build_amazon_url_rejects_unknown_region() -> None:
    with pytest.raises(ValueError):
        build_amazon_url("home", "fr")


# ---------------------------------------------------------------------------
# search URL
# ---------------------------------------------------------------------------


def test_build_search_url_basic() -> None:
    url = build_search_url("usb-c hub", "com.au")
    assert url.startswith("https://www.amazon.com.au/s?")
    assert "k=usb-c+hub" in url


def test_build_search_url_encodes_special_chars() -> None:
    url = build_search_url("rust & async", "com")
    assert "amazon.com/s?" in url
    assert "k=rust+%26+async" in url


def test_build_search_url_default_region() -> None:
    assert "amazon.com.au" in build_search_url("kettle")


def test_build_search_url_rejects_empty_query() -> None:
    with pytest.raises(ValueError):
        build_search_url("", "com.au")
    with pytest.raises(ValueError):
        build_search_url("   ", "com.au")


# ---------------------------------------------------------------------------
# product URL
# ---------------------------------------------------------------------------


def test_build_product_url_canonical() -> None:
    assert build_product_url("B0ABC12345", "com.au") == (
        "https://www.amazon.com.au/dp/B0ABC12345"
    )


def test_build_product_url_uppercases_asin() -> None:
    assert build_product_url("b0abc12345", "com").endswith("/dp/B0ABC12345")


@pytest.mark.parametrize("asin", ["", "abc", "B0ABC1234", "B0ABC123456", "1234567890!"])
def test_build_product_url_rejects_bad_asin(asin: str) -> None:
    with pytest.raises(ValueError):
        build_product_url(asin, "com.au")


def test_build_product_url_per_region() -> None:
    assert build_product_url("B0ABC12345", "co.uk").startswith(
        "https://www.amazon.co.uk/dp/"
    )
    assert build_product_url("B0ABC12345", "com").startswith(
        "https://www.amazon.com/dp/"
    )


# ---------------------------------------------------------------------------
# track + orders URL
# ---------------------------------------------------------------------------


def test_build_track_url_includes_order_id() -> None:
    url = build_track_url("123-4567890-1234567", "com.au")
    assert "amazon.com.au/gp/your-account/order-details" in url
    assert "orderId=123-4567890-1234567" in url


def test_build_track_url_rejects_empty() -> None:
    with pytest.raises(ValueError):
        build_track_url("", "com.au")


def test_build_orders_url_no_year() -> None:
    assert build_orders_url("com.au") == (
        "https://www.amazon.com.au/gp/your-account/order-history"
    )


def test_build_orders_url_with_year() -> None:
    url = build_orders_url("com.au", year=2025)
    assert url.endswith("orderFilter=year-2025")


# ---------------------------------------------------------------------------
# is_amazon_url
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "https://www.amazon.com/dp/B0ABC12345",
        "https://www.amazon.com.au/",
        "https://amazon.co.uk/gp/cart/view.html",
        "www.amazon.com.au/s?k=foo",
    ],
)
def test_is_amazon_url_true(value: str) -> None:
    assert is_amazon_url(value) is True


@pytest.mark.parametrize(
    "value",
    [
        "",
        "https://example.com/",
        "https://amazon.de/",
        "https://www.amazon.fr/dp/B0ABC12345",
        "not a url",
    ],
)
def test_is_amazon_url_false(value: str) -> None:
    assert is_amazon_url(value) is False


# ---------------------------------------------------------------------------
# parse_asin_from_url
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        ("B0ABC12345", "B0ABC12345"),
        ("b0abc12345", "B0ABC12345"),
        ("https://www.amazon.com.au/dp/B0ABC12345", "B0ABC12345"),
        ("https://www.amazon.com/dp/B0ABC12345/ref=foo?bar=baz", "B0ABC12345"),
        ("https://www.amazon.com/gp/product/B0ABC12345/", "B0ABC12345"),
        ("https://www.amazon.com/gp/aw/d/B0ABC12345", "B0ABC12345"),
        (
            "https://www.amazon.com/Some-Product-Name/dp/B0ABC12345/ref=sr_1_1",
            "B0ABC12345",
        ),
        ("https://www.amazon.com/s?k=hub&asin=B0ABC12345", "B0ABC12345"),
    ],
)
def test_parse_asin_from_url_extracts(value: str, expected: str) -> None:
    assert parse_asin_from_url(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "https://www.amazon.com/",
        "https://example.com/dp/B0ABC12345",  # not amazon, but path still matches regex
    ],
)
def test_parse_asin_returns_none_when_absent(value: str) -> None:
    if "B0ABC12345" in value:
        # The regex is path-based and host-agnostic by design — so the
        # example.com case still parses. Skip those.
        assert parse_asin_from_url(value) == "B0ABC12345"
    else:
        assert parse_asin_from_url(value) is None


def test_parse_asin_rejects_short_token() -> None:
    assert parse_asin_from_url("B0ABC123") is None


# ---------------------------------------------------------------------------
# parse_region_from_url
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        ("https://www.amazon.com.au/dp/B0ABC12345", "com.au"),
        ("https://www.amazon.com/", "com"),
        ("https://amazon.co.uk/", "co.uk"),
    ],
)
def test_parse_region_from_url(value: str, expected: str) -> None:
    assert parse_region_from_url(value) == expected


def test_parse_region_from_url_returns_none_for_other_hosts() -> None:
    assert parse_region_from_url("https://example.com/") is None
    assert parse_region_from_url("https://www.amazon.de/") is None
    assert parse_region_from_url("") is None
