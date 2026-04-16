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
        return driver.find_element(By.TAG_NAME, "body").text
    except Exception:
        return ""
