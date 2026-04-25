"""Service layer for Amazon browser workflows.

Pure URL helpers, formatters, and DOM extraction stubs for the `amazon`
plugin. Selenium is imported locally inside any function that touches the
live driver so the URL helpers remain trivially unit-testable.
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Any, Optional


SUPPORTED_REGIONS = ("com", "com.au", "co.uk")
DEFAULT_REGION = "com.au"

ASIN_RE = re.compile(r"[A-Z0-9]{10}")
_ASIN_PATH_RE = re.compile(r"/(?:dp|gp/product|gp/aw/d|product)/([A-Z0-9]{10})")

SECTION_PATHS = {
    "home": "/",
    "orders": "/gp/your-account/order-history",
    "wishlist": "/hz/wishlist/ls",
    "cart": "/gp/cart/view.html",
}


def normalize_region(region: Optional[str]) -> str:
    """Return a supported Amazon region suffix or raise ValueError."""
    value = (region or DEFAULT_REGION).strip().lower()
    if value.startswith("amazon."):
        value = value[len("amazon.") :]
    if value.startswith("."):
        value = value[1:]
    if value not in SUPPORTED_REGIONS:
        raise ValueError(
            f"unsupported region: {region!r} (expected one of {', '.join(SUPPORTED_REGIONS)})"
        )
    return value


def amazon_host(region: Optional[str] = DEFAULT_REGION) -> str:
    return f"www.amazon.{normalize_region(region)}"


def amazon_origin(region: Optional[str] = DEFAULT_REGION) -> str:
    return f"https://{amazon_host(region)}"


def build_amazon_url(section: str, region: Optional[str] = DEFAULT_REGION) -> str:
    """Build an Amazon URL for a known section name (`home`, `orders`, ...)."""
    key = (section or "home").strip().lower()
    if key not in SECTION_PATHS:
        raise ValueError(
            f"unknown amazon section: {section!r} "
            f"(expected one of {', '.join(SECTION_PATHS)})"
        )
    return f"{amazon_origin(region)}{SECTION_PATHS[key]}"


def build_search_url(query: str, region: Optional[str] = DEFAULT_REGION) -> str:
    """Build a search-results URL for the given query and region."""
    q = (query or "").strip()
    if not q:
        raise ValueError("search query is empty")
    encoded = urllib.parse.urlencode({"k": q})
    return f"{amazon_origin(region)}/s?{encoded}"


def build_product_url(asin: str, region: Optional[str] = DEFAULT_REGION) -> str:
    """Build a canonical product URL from an ASIN."""
    cleaned = (asin or "").strip().upper()
    if not ASIN_RE.fullmatch(cleaned):
        raise ValueError(f"invalid ASIN: {asin!r} (expected 10 alphanumeric chars)")
    return f"{amazon_origin(region)}/dp/{cleaned}"


def build_track_url(order_id: str, region: Optional[str] = DEFAULT_REGION) -> str:
    """Build a track-package URL for the given order id."""
    cleaned = (order_id or "").strip()
    if not cleaned:
        raise ValueError("order id is empty")
    encoded = urllib.parse.urlencode({"orderId": cleaned})
    return f"{amazon_origin(region)}/gp/your-account/order-details?{encoded}"


def build_orders_url(
    region: Optional[str] = DEFAULT_REGION,
    year: Optional[int] = None,
) -> str:
    """Build an order-history URL, optionally filtered to a given year."""
    base = build_amazon_url("orders", region)
    if year is None:
        return base
    encoded = urllib.parse.urlencode({"orderFilter": f"year-{int(year)}"})
    return f"{base}?{encoded}"


def is_amazon_url(value: str) -> bool:
    """Return True when value's host is on a known Amazon domain."""
    if not value:
        return False
    parsed = urllib.parse.urlparse(value if "://" in value else f"https://{value}")
    host = (parsed.netloc or "").lower()
    if not host:
        return False
    if host.startswith("www."):
        host = host[4:]
    if not host.startswith("amazon."):
        return False
    suffix = host[len("amazon.") :]
    return suffix in SUPPORTED_REGIONS


def parse_asin_from_url(value: str) -> Optional[str]:
    """Pull a 10-char ASIN from any common Amazon product URL shape."""
    if not value:
        return None
    candidate = value.strip()
    if ASIN_RE.fullmatch(candidate.upper()):
        return candidate.upper()
    parsed = urllib.parse.urlparse(candidate if "://" in candidate else f"https://{candidate}")
    match = _ASIN_PATH_RE.search(parsed.path or "")
    if match:
        return match.group(1).upper()
    query = urllib.parse.parse_qs(parsed.query or "")
    for key in ("asin", "ASIN"):
        if key in query and query[key]:
            value0 = query[key][0].upper()
            if ASIN_RE.fullmatch(value0):
                return value0
    return None


def parse_region_from_url(value: str) -> Optional[str]:
    """Best-effort: pull the Amazon region (`com`, `com.au`, ...) from a URL."""
    if not value:
        return None
    parsed = urllib.parse.urlparse(value if "://" in value else f"https://{value}")
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if not host.startswith("amazon."):
        return None
    suffix = host[len("amazon.") :]
    return suffix if suffix in SUPPORTED_REGIONS else None


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def format_open_result(data: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"title: {data.get('title', '')}",
            f"url: {data.get('url', '')}",
            f"section: {data.get('section', '')}",
            f"region: {data.get('region', '')}",
        ]
    )


def format_search_results(results: list[dict[str, Any]]) -> str:
    if not results:
        return "(no Amazon search results found)"
    lines: list[str] = []
    for i, result in enumerate(results, 1):
        lines.append(f"[{i}] {result.get('title', '(no title)')}")
        for key in ("price", "rating", "reviews", "prime", "url", "asin"):
            value = result.get(key)
            if value in (None, "", False):
                continue
            if key == "url":
                lines.append(f"    {value}")
            else:
                lines.append(f"    {key}: {value}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_product(data: dict[str, Any]) -> str:
    if not data:
        return "(no product info)"
    lines: list[str] = []
    for key in (
        "title",
        "asin",
        "price",
        "rating",
        "reviews",
        "availability",
        "prime",
        "url",
    ):
        value = data.get(key)
        if value not in (None, "", []):
            lines.append(f"{key}: {value}")
    bullets = data.get("bullets") or []
    if bullets:
        lines.append("bullets:")
        for bullet in bullets:
            lines.append(f"  - {bullet}")
    return "\n".join(lines)


def format_orders(orders: list[dict[str, Any]]) -> str:
    if not orders:
        return "(no orders found)"
    lines: list[str] = []
    for order in orders:
        lines.append(
            f"{order.get('order_id', '')}  {order.get('placed', '')}  {order.get('total', '')}"
        )
        for item in order.get("items", []) or []:
            lines.append(f"  - {item.get('title', '')}")
    return "\n".join(lines)


def format_cart(cart: dict[str, Any]) -> str:
    items = cart.get("items") or []
    if not items:
        return "(cart is empty)"
    lines: list[str] = []
    for item in items:
        lines.append(
            f"{item.get('qty', 1)}x  {item.get('title', '')}  {item.get('price', '')}"
        )
    subtotal = cart.get("subtotal")
    if subtotal:
        lines.append(f"subtotal: {subtotal}")
    return "\n".join(lines)


def format_track(data: dict[str, Any]) -> str:
    if not data:
        return "(no tracking info)"
    return "\n".join(
        [
            f"order: {data.get('order_id', '')}",
            f"status: {data.get('status', '')}",
            f"eta: {data.get('eta', '')}",
            f"carrier: {data.get('carrier', '')}",
            f"url: {data.get('url', '')}",
        ]
    )


# ---------------------------------------------------------------------------
# DOM extraction stubs (best-effort, selectors centralised in helpers)
# ---------------------------------------------------------------------------


def extract_search_results(driver, limit: int = 10) -> list[dict[str, Any]]:
    """Pull search-result cards from the current Amazon search page."""
    cards = _find_search_cards(driver)
    results: list[dict[str, Any]] = []
    for card in cards:
        if len(results) >= limit:
            break
        try:
            if not card.is_displayed():
                continue
        except Exception:
            continue
        asin = (card.get_attribute("data-asin") or "").strip().upper()
        if not asin or not ASIN_RE.fullmatch(asin):
            continue
        title = _text_in(card, "h2 a span, h2 span")
        link = _attr_in(card, "h2 a", "href") or _attr_in(card, "a.a-link-normal", "href")
        price = _text_in(card, "span.a-price > span.a-offscreen")
        rating = _attr_in(card, "i.a-icon-star-small, i.a-icon-star", "aria-label") or _text_in(
            card, "span.a-icon-alt"
        )
        reviews = _text_in(card, "span.a-size-base.s-underline-text, span.a-size-base")
        prime = bool(_first_in(card, "i.a-icon-prime, [aria-label='Prime']"))
        results.append(
            {
                "title": title,
                "asin": asin,
                "url": link or build_product_url(asin),
                "price": price,
                "rating": rating,
                "reviews": reviews,
                "prime": prime,
            }
        )
    return results


def extract_product(driver) -> dict[str, Any]:
    """Pull product detail fields from the current Amazon product page."""
    url = driver.current_url
    asin = parse_asin_from_url(url) or ""
    title = _driver_text(driver, "#productTitle")
    price = _driver_text(driver, "span.a-price > span.a-offscreen")
    rating = _driver_text(driver, "#acrPopover span.a-icon-alt") or _driver_attr(
        driver, "#acrPopover", "title"
    )
    reviews = _driver_text(driver, "#acrCustomerReviewText")
    availability = _driver_text(driver, "#availability span")
    prime = bool(_driver_first(driver, "#primeSupportLink, i.a-icon-prime"))
    bullets = _driver_texts(driver, "#feature-bullets ul li span.a-list-item")
    return {
        "title": title,
        "asin": asin,
        "url": url,
        "price": price,
        "rating": rating,
        "reviews": reviews,
        "availability": availability,
        "prime": prime,
        "bullets": [b for b in bullets if b],
    }


def extract_orders(driver, limit: int = 10) -> list[dict[str, Any]]:
    """Pull recent order summaries from the order-history page."""
    cards = _driver_all(driver, ".order-card, .order, .a-box-group.order")
    orders: list[dict[str, Any]] = []
    for card in cards:
        if len(orders) >= limit:
            break
        order_id = _text_in(
            card, ".yohtmlc-order-id span:nth-child(2), .a-color-secondary.value"
        )
        placed = _text_in(card, ".a-column.a-span3 .a-color-secondary.value")
        total = _text_in(card, ".a-column.a-span2 .a-color-secondary.value")
        items = []
        for row in _all_in(card, ".a-fixed-left-grid .yohtmlc-product-title, .a-row .a-link-normal"):
            text = (row.text or "").strip()
            if text:
                items.append({"title": text})
        orders.append(
            {
                "order_id": order_id,
                "placed": placed,
                "total": total,
                "items": items,
            }
        )
    return orders


def extract_cart(driver) -> dict[str, Any]:
    """Pull cart contents from the cart page."""
    items: list[dict[str, Any]] = []
    rows = _driver_all(driver, "[data-name='Active Items'] [data-asin], .sc-list-item")
    for row in rows:
        title = _text_in(row, ".sc-product-title, .a-truncate-cut")
        price = _text_in(row, ".sc-product-price, .a-price > .a-offscreen")
        qty_attr = _attr_in(row, "input[name='quantity']", "value")
        items.append({"title": title, "price": price, "qty": qty_attr or "1"})
    subtotal = _driver_text(driver, "#sc-subtotal-amount-activecart .a-price-whole") or _driver_text(
        driver, "#sc-subtotal-amount-buybox"
    )
    return {"items": items, "subtotal": subtotal}


def extract_tracking(driver) -> dict[str, Any]:
    """Pull tracking summary from the order-details / tracking page."""
    return {
        "order_id": _driver_text(driver, ".order-id, [data-test-id='order-id']"),
        "status": _driver_text(driver, "#primaryStatus, .milestone-primaryMessage"),
        "eta": _driver_text(driver, "#deliveryDate, .promise"),
        "carrier": _driver_text(driver, "#carrierRelatedInfo, .carrierRelatedInfo-mfn-providerTitle"),
        "url": driver.current_url,
    }


# ---------------------------------------------------------------------------
# Private DOM helpers — selenium imported lazily so unit tests stay light
# ---------------------------------------------------------------------------


def _find_search_cards(driver):
    return _driver_all(
        driver,
        "div.s-result-item[data-asin], div[data-component-type='s-search-result']",
    )


def _driver_all(driver, selector):
    from selenium.webdriver.common.by import By

    try:
        return driver.find_elements(By.CSS_SELECTOR, selector)
    except Exception:
        return []


def _driver_first(driver, selector):
    from selenium.webdriver.common.by import By

    try:
        return driver.find_element(By.CSS_SELECTOR, selector)
    except Exception:
        return None


def _driver_text(driver, selector) -> str:
    el = _driver_first(driver, selector)
    if el is None:
        return ""
    text = (el.text or el.get_attribute("textContent") or "").strip()
    return text


def _driver_attr(driver, selector, attr) -> str:
    el = _driver_first(driver, selector)
    if el is None:
        return ""
    return (el.get_attribute(attr) or "").strip()


def _driver_texts(driver, selector) -> list[str]:
    return [(e.text or "").strip() for e in _driver_all(driver, selector)]


def _all_in(parent, selector):
    from selenium.webdriver.common.by import By

    try:
        return parent.find_elements(By.CSS_SELECTOR, selector)
    except Exception:
        return []


def _first_in(parent, selector):
    from selenium.webdriver.common.by import By

    try:
        return parent.find_element(By.CSS_SELECTOR, selector)
    except Exception:
        return None


def _text_in(parent, selector) -> str:
    el = _first_in(parent, selector)
    if el is None:
        return ""
    return (el.text or el.get_attribute("textContent") or "").strip()


def _attr_in(parent, selector, attr) -> str:
    el = _first_in(parent, selector)
    if el is None:
        return ""
    return (el.get_attribute(attr) or "").strip()


__all__ = [
    "ASIN_RE",
    "DEFAULT_REGION",
    "SECTION_PATHS",
    "SUPPORTED_REGIONS",
    "amazon_host",
    "amazon_origin",
    "build_amazon_url",
    "build_orders_url",
    "build_product_url",
    "build_search_url",
    "build_track_url",
    "extract_cart",
    "extract_orders",
    "extract_product",
    "extract_search_results",
    "extract_tracking",
    "format_cart",
    "format_open_result",
    "format_orders",
    "format_product",
    "format_search_results",
    "format_track",
    "is_amazon_url",
    "normalize_region",
    "parse_asin_from_url",
    "parse_region_from_url",
]
