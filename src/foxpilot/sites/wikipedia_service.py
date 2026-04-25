"""Wikipedia browser workflow helpers.

Pure-function URL helpers, title normalisation, formatters, and DOM
extraction for the `foxpilot wikipedia` command branch. Selenium imports
are local to extraction helpers so unit tests can exercise the URL +
formatter logic without a live driver.
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Any, Optional


DEFAULT_LANG = "en"
WIKIPEDIA_HOST_RE = re.compile(r"^([a-z]{2,3}(?:-[a-z]+)?)\.(?:m\.)?wikipedia\.org$", re.I)


def normalize_title(title: str) -> str:
    """Normalise a Wikipedia article title.

    - Strip surrounding whitespace.
    - Collapse internal whitespace runs.
    - Replace spaces with underscores.
    - Capitalise the first character (Wikipedia article titles are
      case-sensitive after the first character but always upper-case the
      first character).
    """
    cleaned = re.sub(r"\s+", " ", title.strip())
    if not cleaned:
        return ""
    cleaned = cleaned.replace(" ", "_")
    return cleaned[0].upper() + cleaned[1:]


def is_wikipedia_url(value: str) -> bool:
    """Return True when value looks like a wikipedia.org URL."""
    parsed = _parse_url(value)
    host = parsed.netloc.lower()
    if not host:
        return False
    return bool(WIKIPEDIA_HOST_RE.match(host))


def lang_from_url(value: str) -> Optional[str]:
    """Return the language subdomain for a wikipedia URL, or None."""
    parsed = _parse_url(value)
    match = WIKIPEDIA_HOST_RE.match(parsed.netloc.lower())
    if not match:
        return None
    return match.group(1).lower()


def article_url(title_or_url: str, lang: str = DEFAULT_LANG) -> str:
    """Return the canonical article URL for a title or pass-through URL."""
    value = title_or_url.strip()
    if is_wikipedia_url(value):
        parsed = _parse_url(value)
        scheme = parsed.scheme or "https"
        return urllib.parse.urlunparse(
            (scheme, parsed.netloc, parsed.path, "", parsed.query, "")
        )
    title = normalize_title(value)
    if not title:
        raise ValueError("empty Wikipedia title")
    base = _base_for_lang(lang)
    return f"{base}/wiki/{urllib.parse.quote(title, safe='_(),:')}"


def search_url(query: str, lang: str = DEFAULT_LANG) -> str:
    """Return a Wikipedia on-site search URL."""
    base = _base_for_lang(lang)
    encoded = urllib.parse.urlencode({"search": query})
    return f"{base}/w/index.php?{encoded}"


def random_url(lang: str = DEFAULT_LANG) -> str:
    """Return the language-aware Special:Random URL."""
    return f"{_base_for_lang(lang)}/wiki/Special:Random"


def references_url(title_or_url: str, lang: str = DEFAULT_LANG) -> str:
    """Return the article URL with a fragment pointing at #References."""
    url = article_url(title_or_url, lang=lang)
    return f"{url}#References"


def title_from_url(value: str) -> str:
    """Extract a (raw) title segment from a wikipedia article URL."""
    parsed = _parse_url(value)
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 2 and parts[0] == "wiki":
        return urllib.parse.unquote(parts[1])
    return ""


def format_search_results(results: list[dict[str, Any]]) -> str:
    if not results:
        return "No Wikipedia results found."
    lines: list[str] = []
    for i, result in enumerate(results, 1):
        title = result.get("title") or "(no title)"
        lines.append(f"[{i}] {title}")
        url = result.get("url")
        if url:
            lines.append(f"    {url}")
        snippet = result.get("snippet")
        if snippet:
            lines.append(f"    {snippet}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_summary(summary: dict[str, Any]) -> str:
    if not summary:
        return "No Wikipedia summary found."
    lines: list[str] = []
    title = summary.get("title")
    if title:
        lines.append(f"title: {title}")
    url = summary.get("url")
    if url:
        lines.append(f"url: {url}")
    lang = summary.get("lang")
    if lang:
        lines.append(f"lang: {lang}")
    lead = summary.get("lead")
    if lead:
        lines.append("")
        lines.append(lead)
    infobox = summary.get("infobox") or {}
    if infobox:
        lines.append("")
        lines.append("infobox:")
        for key, value in infobox.items():
            lines.append(f"  {key}: {value}")
    return "\n".join(lines)


def format_links(links: list[dict[str, Any]]) -> str:
    if not links:
        return "No internal links found."
    lines: list[str] = []
    for i, link in enumerate(links, 1):
        title = link.get("title") or "(no title)"
        url = link.get("url") or ""
        lines.append(f"[{i}] {title}")
        if url:
            lines.append(f"    {url}")
    return "\n".join(lines)


def format_references(references: list[dict[str, Any]]) -> str:
    if not references:
        return "No references found."
    lines: list[str] = []
    for i, ref in enumerate(references, 1):
        text = ref.get("text") or "(no text)"
        lines.append(f"[{i}] {text}")
        for url in ref.get("urls") or []:
            lines.append(f"    {url}")
    return "\n".join(lines)


# ---------- DOM extraction (live driver) ----------


def extract_search_results(driver, limit: int = 10) -> list[dict[str, Any]]:
    """Extract on-page search results from a Wikipedia search page.

    Wikipedia's `/w/index.php?search=...` may either redirect straight to
    a matching article or render a search results page with `.mw-search-result`.
    """
    from selenium.webdriver.common.by import By

    results: list[dict[str, Any]] = []

    # Direct hit: search redirected to article page.
    if "/wiki/" in driver.current_url and not _is_search_results_page(driver):
        heading = _safe_text(driver, By.CSS_SELECTOR, "#firstHeading")
        if heading:
            results.append(
                {
                    "title": heading,
                    "url": driver.current_url,
                    "snippet": _safe_text(
                        driver,
                        By.CSS_SELECTOR,
                        "#mw-content-text .mw-parser-output > p",
                    ),
                }
            )
            return results[:limit]

    rows = driver.find_elements(By.CSS_SELECTOR, "li.mw-search-result, ul.mw-search-results > li")
    for row in rows:
        if len(results) >= limit:
            break
        link = _first_element(row, By.CSS_SELECTOR, ".mw-search-result-heading a, a")
        if not link:
            continue
        title = (link.get_attribute("title") or link.text or "").strip()
        href = link.get_attribute("href") or ""
        if not title or not href:
            continue
        snippet = _first_text(row, By.CSS_SELECTOR, ".searchresult, .mw-search-result-data")
        results.append({"title": title, "url": href, "snippet": snippet})
    return results


def extract_summary(driver, lang: str = DEFAULT_LANG) -> dict[str, Any]:
    """Extract title, lead paragraph, and infobox key/values from the page."""
    from selenium.webdriver.common.by import By

    title = _safe_text(driver, By.CSS_SELECTOR, "#firstHeading")
    lead = _extract_lead_paragraph(driver)
    infobox = _extract_infobox(driver)
    return {
        "title": title,
        "url": driver.current_url,
        "lang": lang_from_url(driver.current_url) or lang,
        "lead": lead,
        "infobox": infobox,
    }


def extract_links(driver, limit: int = 50) -> list[dict[str, Any]]:
    """Extract internal article links from the current Wikipedia page."""
    from selenium.webdriver.common.by import By

    seen: set[str] = set()
    links: list[dict[str, Any]] = []
    anchors = driver.find_elements(
        By.CSS_SELECTOR,
        "#mw-content-text .mw-parser-output a[href^='/wiki/']",
    )
    for anchor in anchors:
        if len(links) >= limit:
            break
        href = anchor.get_attribute("href") or ""
        if not href or _looks_internal_namespace(href):
            continue
        if href in seen:
            continue
        seen.add(href)
        title = (anchor.get_attribute("title") or anchor.text or "").strip()
        if not title:
            continue
        links.append({"title": title, "url": href})
    return links


def extract_references(driver, limit: int = 200) -> list[dict[str, Any]]:
    """Extract entries from the article's references list."""
    from selenium.webdriver.common.by import By

    refs: list[dict[str, Any]] = []
    items = driver.find_elements(
        By.CSS_SELECTOR,
        "ol.references > li, .references > li, .mw-references-wrap li",
    )
    for li in items:
        if len(refs) >= limit:
            break
        text = (li.text or "").strip()
        if not text:
            continue
        urls: list[str] = []
        for a in li.find_elements(By.CSS_SELECTOR, "a.external, a[href^='http']"):
            href = a.get_attribute("href") or ""
            if href and href not in urls:
                urls.append(href)
        refs.append({"text": text, "urls": urls})
    return refs


# ---------- private helpers ----------


def _base_for_lang(lang: str) -> str:
    lang = (lang or DEFAULT_LANG).strip().lower() or DEFAULT_LANG
    if not re.match(r"^[a-z]{2,3}(-[a-z]+)?$", lang):
        raise ValueError(f"invalid Wikipedia language code: {lang!r}")
    return f"https://{lang}.wikipedia.org"


def _parse_url(value: str) -> urllib.parse.ParseResult:
    value = value.strip()
    if value.startswith("//"):
        value = "https:" + value
    if "://" not in value and value.lower().endswith("wikipedia.org"):
        value = "https://" + value
    if "://" not in value and ".wikipedia.org/" in value:
        value = "https://" + value
    return urllib.parse.urlparse(value)


def _is_search_results_page(driver) -> bool:
    return "search=" in (driver.current_url or "") and "/w/index.php" in driver.current_url


def _looks_internal_namespace(href: str) -> bool:
    # Skip Wikipedia internal namespaces like /wiki/File:, Help:, Special:, etc.
    parsed = urllib.parse.urlparse(href)
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2 or parts[0] != "wiki":
        return True
    title = urllib.parse.unquote(parts[1])
    if ":" in title.split("/", 1)[0]:
        return True
    return False


def _extract_lead_paragraph(driver) -> str:
    from selenium.webdriver.common.by import By

    paragraphs = driver.find_elements(
        By.CSS_SELECTOR,
        "#mw-content-text .mw-parser-output > p",
    )
    for para in paragraphs:
        text = (para.text or "").strip()
        if text and len(text) > 40:
            return text
    return ""


def _extract_infobox(driver) -> dict[str, str]:
    from selenium.webdriver.common.by import By

    infobox: dict[str, str] = {}
    rows = driver.find_elements(
        By.CSS_SELECTOR,
        "table.infobox tr",
    )
    for row in rows:
        try:
            header = row.find_element(By.CSS_SELECTOR, "th")
            data = row.find_element(By.CSS_SELECTOR, "td")
        except Exception:
            continue
        key = (header.text or "").strip()
        value = (data.text or "").strip()
        if key and value:
            infobox[key] = value
    return infobox


def _first_element(parent, by, selector):
    try:
        return parent.find_element(by, selector)
    except Exception:
        return None


def _first_text(parent, by, selector) -> str:
    el = _first_element(parent, by, selector)
    if not el:
        return ""
    try:
        return (el.text or "").strip()
    except Exception:
        return ""


def _safe_text(driver, by, selector) -> str:
    try:
        el = driver.find_element(by, selector)
        return (el.text or "").strip()
    except Exception:
        return ""
