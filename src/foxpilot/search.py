"""foxpilot.search — web search via DuckDuckGo HTML interface."""

import urllib.parse


def search_duckduckgo(driver, query: str, max_results: int = 10) -> list[dict]:
    """Navigate to DuckDuckGo HTML search and return structured results."""
    from selenium.webdriver.common.by import By

    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    driver.get(url)

    results = []
    try:
        result_els = driver.find_elements(By.CSS_SELECTOR, ".result")
        for el in result_els[:max_results]:
            title = _text(el, ".result__title")
            url = _text(el, ".result__url")
            snippet = _text(el, ".result__snippet")

            if not url.startswith("http") and url:
                url = "https://" + url

            if title or url:
                results.append({"title": title, "url": url, "snippet": snippet})
    except Exception:
        pass

    return results


def format_results(results: list[dict]) -> str:
    """Format search results as readable text."""
    if not results:
        return "No results found."

    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] {r['title']}")
        if r["url"]:
            lines.append(f"    {r['url']}")
        if r["snippet"]:
            lines.append(f"    {r['snippet']}")
        lines.append("")

    return "\n".join(lines).rstrip()


def _text(parent, selector: str) -> str:
    """Extract text from a child element, return empty string if not found."""
    from selenium.webdriver.common.by import By
    try:
        return parent.find_element(By.CSS_SELECTOR, selector).text.strip()
    except Exception:
        return ""
