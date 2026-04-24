"""Documentation-site workflow helpers."""

from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class DocsSite:
    key: str
    name: str
    base_url: str
    search_scope: str
    description: str


DOCS_SITE_REGISTRY: dict[str, DocsSite] = {
    "python": DocsSite(
        key="python",
        name="Python",
        base_url="https://docs.python.org/3/",
        search_scope="docs.python.org/3",
        description="Python standard library and language docs.",
    ),
    "mdn": DocsSite(
        key="mdn",
        name="MDN Web Docs",
        base_url="https://developer.mozilla.org/en-US/docs/Web",
        search_scope="developer.mozilla.org/en-US/docs/Web",
        description="Web platform APIs, CSS, HTML, and JavaScript.",
    ),
    "react": DocsSite(
        key="react",
        name="React",
        base_url="https://react.dev/reference/react",
        search_scope="react.dev",
        description="React reference and learn docs.",
    ),
    "typescript": DocsSite(
        key="typescript",
        name="TypeScript",
        base_url="https://www.typescriptlang.org/docs/",
        search_scope="typescriptlang.org/docs",
        description="TypeScript handbook and reference docs.",
    ),
    "typer": DocsSite(
        key="typer",
        name="Typer",
        base_url="https://typer.tiangolo.com/",
        search_scope="typer.tiangolo.com",
        description="Typer CLI framework docs.",
    ),
    "selenium": DocsSite(
        key="selenium",
        name="Selenium",
        base_url="https://www.selenium.dev/documentation/",
        search_scope="selenium.dev/documentation",
        description="Selenium browser automation docs.",
    ),
}


def resolve_docs_site(site_key: Optional[str]) -> Optional[DocsSite]:
    """Return a registry site or raise a clear ValueError for unknown keys."""
    if not site_key:
        return None
    key = site_key.strip().lower()
    try:
        return DOCS_SITE_REGISTRY[key]
    except KeyError as exc:
        known = ", ".join(sorted(DOCS_SITE_REGISTRY))
        raise ValueError(f"unknown docs site '{site_key}' (known: {known})") from exc


def list_docs_sites() -> list[dict[str, str]]:
    return [
        {
            "key": site.key,
            "name": site.name,
            "base_url": site.base_url,
            "search_scope": site.search_scope,
            "description": site.description,
        }
        for site in DOCS_SITE_REGISTRY.values()
    ]


def docs_search_url(query: str, site_key: Optional[str] = None) -> str:
    """Build a docs-focused search URL using the known registry scopes."""
    query = query.strip()
    if not query:
        raise ValueError("search query cannot be empty")

    site = resolve_docs_site(site_key)
    scopes = [site.search_scope] if site else [item.search_scope for item in DOCS_SITE_REGISTRY.values()]
    scoped_query = " OR ".join(f"site:{scope}" for scope in scopes)
    encoded = urllib.parse.urlencode({"q": f"{query} {scoped_query}"})
    return f"https://duckduckgo.com/?{encoded}"


def normalize_docs_target(target: str, site_key: Optional[str] = None) -> str:
    """Resolve URLs, registry-relative paths, or plain queries to a navigable URL."""
    target = target.strip()
    if not target:
        raise ValueError("target cannot be empty")

    if _looks_like_url(target):
        return _ensure_url_scheme(target)

    site = resolve_docs_site(site_key)
    if target.startswith("/") and site:
        parsed_base = urllib.parse.urlparse(site.base_url)
        base_path = parsed_base.path.rstrip("/")
        target_path = target.rstrip("/")
        join_base = (
            f"{parsed_base.scheme}://{parsed_base.netloc}/"
            if base_path and (target_path == base_path or target_path.startswith(f"{base_path}/"))
            else f"{site.base_url.rstrip('/')}/"
        )
        return urllib.parse.urljoin(join_base, target.lstrip("/"))

    return docs_search_url(target, site_key=site_key)


def detect_docs_site(url: str) -> str:
    parsed = urllib.parse.urlparse(_ensure_url_scheme(url) if _looks_like_url(url) else url)
    host = _strip_www(parsed.netloc.lower())
    for site in DOCS_SITE_REGISTRY.values():
        scope = site.search_scope.lower().rstrip("/")
        scope_host = _strip_www(scope.split("/", 1)[0])
        scope_path = scope.split("/", 1)[1] if "/" in scope else ""
        path = parsed.path.lstrip("/").lower()
        if host == scope_host and (not scope_path or path.startswith(scope_path)):
            return site.key
    return ""


def is_known_docs_url(url: str, site_key: Optional[str] = None) -> bool:
    site = resolve_docs_site(site_key)
    if site:
        return detect_docs_site(url) == site.key
    return bool(detect_docs_site(url))


def format_search_results(results: list[dict[str, Any]]) -> str:
    if not results:
        return "No documentation results found."

    lines: list[str] = []
    for i, result in enumerate(results, 1):
        title = result.get("title") or "(no title)"
        lines.append(f"[{i}] {title}")
        if result.get("url"):
            lines.append(f"    {result['url']}")
        if result.get("site"):
            lines.append(f"    site: {result['site']}")
        if result.get("snippet"):
            lines.append(f"    {result['snippet']}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_open_result(data: dict[str, Any]) -> str:
    return "\n".join(
        line
        for line in [
            f"title: {data.get('title', '')}",
            f"url: {data.get('url', '')}",
            f"site: {data.get('site', '')}",
        ]
        if line.split(": ", 1)[1]
    )


def format_page_read(data: dict[str, Any]) -> str:
    lines = [
        f"[{data.get('title', '')}]",
        str(data.get("url", "")),
    ]
    if data.get("site"):
        lines.append(f"site: {data['site']}")
    lines.append("-" * 60)
    lines.append(str(data.get("text") or "(no visible text)"))
    return "\n".join(lines)


def format_links(links: list[dict[str, Any]]) -> str:
    if not links:
        return "No links found."

    lines: list[str] = []
    for i, link in enumerate(links, 1):
        text = link.get("text") or "(no text)"
        lines.append(f"[{i}] {text}")
        if link.get("url"):
            lines.append(f"    {link['url']}")
        if link.get("site"):
            lines.append(f"    site: {link['site']}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_examples(examples: list[dict[str, Any]]) -> str:
    if not examples:
        return "No examples found."

    blocks: list[str] = []
    for i, example in enumerate(examples, 1):
        language = str(example.get("language") or "").strip()
        text = str(example.get("text") or "").strip()
        fence = f"```{language}" if language else "```"
        blocks.append(f"[{i}]")
        blocks.append(fence)
        blocks.append(text)
        blocks.append("```")
    return "\n".join(blocks)


def to_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def extract_search_results(driver, limit: int = 10, site_key: Optional[str] = None) -> list[dict[str, Any]]:
    """Extract visible docs links from a search results page."""
    from selenium.webdriver.common.by import By

    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    anchors = driver.find_elements(By.CSS_SELECTOR, "a[href]")

    for anchor in anchors:
        if len(results) >= limit:
            break
        try:
            if not anchor.is_displayed():
                continue
        except Exception:
            continue

        raw_url = anchor.get_attribute("href") or ""
        url = unwrap_search_redirect_url(raw_url)
        if not _is_http_url(url) or not is_known_docs_url(url, site_key):
            continue
        if url in seen:
            continue

        title = _clean_text(anchor.text or anchor.get_attribute("aria-label") or "")
        if not title:
            continue
        seen.add(url)
        results.append(
            {
                "title": title,
                "url": url,
                "site": detect_docs_site(url),
                "snippet": _nearby_text(anchor, title),
            }
        )

    return results


def extract_page_read(driver, selector: Optional[str] = None, max_chars: int = 3000) -> dict[str, Any]:
    """Extract readable text from the current docs page."""
    from selenium.webdriver.common.by import By

    if selector:
        try:
            element = driver.find_element(By.CSS_SELECTOR, selector)
            text = element.text
        except Exception:
            text = f"(selector '{selector}' not found)"
    else:
        text = driver.execute_script(
            """
            const root = document.querySelector('main, article, [role="main"]') || document.body;
            return root ? (root.innerText || root.textContent || '') : '';
            """
        )
        if not text:
            try:
                text = driver.find_element(By.TAG_NAME, "body").text
            except Exception:
                text = ""

    cleaned = _clean_multiline(str(text or ""))
    total_chars = len(cleaned)
    if max_chars and total_chars > max_chars:
        cleaned = cleaned[:max_chars].rstrip() + f"\n... [truncated - {total_chars} total chars]"

    url = getattr(driver, "current_url", "")
    return {
        "title": getattr(driver, "title", ""),
        "url": url,
        "site": detect_docs_site(url),
        "selector": selector or "",
        "chars": total_chars,
        "truncated": bool(max_chars and total_chars > max_chars),
        "text": cleaned or "(no visible text)",
    }


def extract_links(driver, limit: int = 50, site_key: Optional[str] = None) -> list[dict[str, Any]]:
    """Extract visible links from the current docs page."""
    from selenium.webdriver.common.by import By

    links: list[dict[str, Any]] = []
    seen: set[str] = set()
    anchors = driver.find_elements(By.CSS_SELECTOR, "a[href]")

    for anchor in anchors:
        if len(links) >= limit:
            break
        try:
            if not anchor.is_displayed():
                continue
        except Exception:
            continue

        url = unwrap_search_redirect_url(anchor.get_attribute("href") or "")
        if not _is_http_url(url):
            continue
        if site_key and not is_known_docs_url(url, site_key):
            continue
        if url in seen:
            continue

        text = _clean_text(anchor.text or anchor.get_attribute("aria-label") or "")
        if not text:
            text = urllib.parse.urlparse(url).path.rstrip("/").rsplit("/", 1)[-1] or url
        seen.add(url)
        links.append({"text": text, "url": url, "site": detect_docs_site(url)})

    return links


def extract_examples(driver, lang: Optional[str] = None, limit: int = 20) -> list[dict[str, Any]]:
    """Extract code examples from the current docs page."""
    from selenium.webdriver.common.by import By

    wanted = (lang or "").strip().lower()
    examples: list[dict[str, Any]] = []
    seen: set[str] = set()
    elements = driver.find_elements(By.CSS_SELECTOR, "pre, code")

    for element in elements:
        if len(examples) >= limit:
            break
        try:
            if not element.is_displayed():
                continue
        except Exception:
            continue

        text = _clean_multiline(element.text or "")
        if not text or text in seen:
            continue

        language = _detect_code_language(element)
        if wanted and wanted not in {language.lower(), _language_alias(language).lower()}:
            continue

        seen.add(text)
        examples.append({"language": language, "text": text})

    return examples


def unwrap_search_redirect_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    for key in ("uddg", "url", "u"):
        values = params.get(key)
        if values:
            return urllib.parse.unquote(values[0])
    return url


def _looks_like_url(value: str) -> bool:
    value = value.strip()
    if not value or any(ch.isspace() for ch in value):
        return False
    host = value.split("/", 1)[0]
    return "://" in value or host.startswith("www.") or "." in host


def _ensure_url_scheme(value: str) -> str:
    if "://" in value:
        return value
    return f"https://{value}"


def _strip_www(host: str) -> str:
    return host[4:] if host.startswith("www.") else host


def _is_http_url(value: str) -> bool:
    return urllib.parse.urlparse(value).scheme in {"http", "https"}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _clean_multiline(value: str) -> str:
    lines = [line.rstrip() for line in value.splitlines()]
    compacted: list[str] = []
    previous_blank = False
    for line in lines:
        blank = not line.strip()
        if blank and previous_blank:
            continue
        compacted.append(line.strip() if blank else line)
        previous_blank = blank
    return "\n".join(compacted).strip()


def _nearby_text(anchor, title: str) -> str:
    try:
        text = anchor.find_element("xpath", "./ancestor::*[self::article or self::div][1]").text
    except Exception:
        return ""
    cleaned = _clean_text(text)
    if not cleaned:
        return ""
    if cleaned.startswith(title):
        cleaned = cleaned[len(title):].strip(" -")
    return cleaned[:240]


def _detect_code_language(element) -> str:
    values: list[str] = []
    for attr in ("class", "data-language", "lang"):
        try:
            value = element.get_attribute(attr) or ""
        except Exception:
            value = ""
        if value:
            values.append(value)
    try:
        parent_class = element.find_element("xpath", "..").get_attribute("class") or ""
    except Exception:
        parent_class = ""
    if parent_class:
        values.append(parent_class)

    joined = " ".join(values).lower()
    patterns = [
        r"language-([a-z0-9_#+-]+)",
        r"lang-([a-z0-9_#+-]+)",
        r"highlight-([a-z0-9_#+-]+)",
        r"\b(js|jsx|ts|tsx|python|py|bash|shell|html|css|json)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, joined)
        if match:
            return _language_alias(match.group(1))
    return ""


def _language_alias(language: str) -> str:
    aliases = {
        "py": "python",
        "js": "javascript",
        "jsx": "javascript",
        "ts": "typescript",
        "tsx": "typescript",
        "sh": "bash",
        "shell": "bash",
    }
    return aliases.get(language.lower(), language.lower())
