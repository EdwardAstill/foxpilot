"""foxpilot.readability — extract main readable content from a page."""


def extract_main_content(driver) -> str:
    """Extract the main readable content block from the current page.

    Priority:
    1. Semantic containers: article, main, [role=main]
    2. Common content IDs/classes
    3. Full body text as fallback
    """
    from selenium.webdriver.common.by import By

    selectors = [
        "article",
        "main",
        "[role='main']",
        "[role=\"main\"]",
        "#content",
        "#main",
        "#main-content",
        ".content",
        ".main-content",
        ".post-content",
        ".article-body",
        ".entry-content",
    ]

    for sel in selectors:
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            text = el.text.strip()
            if len(text) > 200:
                return text
        except Exception:
            continue

    # Fallback: full body text
    try:
        text = driver.find_element(By.TAG_NAME, "body").text
        if text and text.strip():
            return text
    except Exception:
        pass

    # Selenium's `.text` can come back blank on reconnect-attached sessions
    # even when the page clearly has rendered text. Ask the DOM directly as a
    # final fallback so `read` stays useful on short/static pages.
    try:
        text = driver.execute_script(
            """
            const body = document.body;
            if (!body) return "";
            return (body.innerText || body.textContent || "").trim();
            """
        )
        if isinstance(text, str):
            return text
    except Exception:
        return ""

    return ""
