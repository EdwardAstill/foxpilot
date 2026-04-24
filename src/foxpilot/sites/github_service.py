"""GitHub-specific URL, formatting, and browser extraction helpers."""

from __future__ import annotations

import json
import re
import urllib.parse
from typing import Any, Optional


GITHUB_ORIGINS = {"github.com", "www.github.com"}

SEARCH_TYPES = {
    "repos": "repositories",
    "code": "code",
    "issues": "issues",
    "prs": "pullrequests",
    "users": "users",
}

ISSUE_STATES = {
    "open": ("is:issue", "is:open"),
    "closed": ("is:issue", "is:closed"),
    "all": ("is:issue",),
}

PR_STATES = {
    "open": ("is:pr", "is:open"),
    "closed": ("is:pr", "is:closed", "-is:merged"),
    "merged": ("is:pr", "is:merged"),
    "all": ("is:pr",),
}

TRENDING_WINDOWS = {"daily", "weekly", "monthly"}


def parse_repo_slug(value: str) -> str:
    """Return an ``owner/repo`` slug from a GitHub slug, URL, or SSH remote."""
    raw = value.strip()
    if not raw:
        raise ValueError("empty GitHub repository value")

    ssh_match = re.fullmatch(
        r"git@github\.com:(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?/?",
        raw,
    )
    if ssh_match:
        return _validate_repo_slug(f"{ssh_match.group('owner')}/{ssh_match.group('repo')}")

    if _looks_like_url(raw):
        parsed = _parse_url(raw)
        if parsed.netloc.lower() not in GITHUB_ORIGINS:
            raise ValueError(f"not a GitHub URL: {value}")
        parts = [urllib.parse.unquote(part) for part in parsed.path.split("/") if part]
        if len(parts) < 2:
            raise ValueError(f"GitHub URL does not include owner and repo: {value}")
        return _validate_repo_slug(f"{parts[0]}/{_strip_git_suffix(parts[1])}")

    return _validate_repo_slug(_strip_git_suffix(raw.rstrip("/")))


def build_repo_url(repo_or_url: str) -> str:
    slug = parse_repo_slug(repo_or_url)
    return f"https://github.com/{slug}"


def normalize_github_url(value: str) -> str:
    """Return a navigable GitHub URL, accepting either URLs or repo slugs."""
    raw = value.strip()
    if _looks_like_url(raw):
        parsed = _parse_url(raw)
        if parsed.netloc.lower() not in GITHUB_ORIGINS:
            raise ValueError(f"not a GitHub URL: {value}")
        return urllib.parse.urlunparse(
            (
                "https",
                "github.com",
                parsed.path or "/",
                "",
                parsed.query,
                parsed.fragment,
            )
        )
    return build_repo_url(raw)


def build_issues_url(repo_or_url: str, state: str = "open") -> str:
    terms = state_filter_terms("issues", state)
    return _repo_query_url(repo_or_url, "issues", terms)


def build_prs_url(repo_or_url: str, state: str = "open") -> str:
    terms = state_filter_terms("prs", state)
    return _repo_query_url(repo_or_url, "pulls", terms)


def build_pr_url(repo_or_url: str, number_or_url: str) -> str:
    target = number_or_url.strip()
    if _looks_like_url(target):
        parsed = _parse_url(target)
        if parsed.netloc.lower() not in GITHUB_ORIGINS:
            raise ValueError(f"not a GitHub PR URL: {number_or_url}")
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 4 and parts[2] == "pull" and parts[3].isdigit():
            slug = parse_repo_slug(target)
            return f"https://github.com/{slug}/pull/{parts[3]}"
        raise ValueError(f"not a GitHub PR URL: {number_or_url}")

    if not re.fullmatch(r"\d+", target):
        raise ValueError("PR target must be a number or GitHub pull request URL")

    slug = parse_repo_slug(repo_or_url)
    return f"https://github.com/{slug}/pull/{target}"


def build_actions_url(repo_or_url: str, branch: Optional[str] = None) -> str:
    slug = parse_repo_slug(repo_or_url)
    url = f"https://github.com/{slug}/actions"
    if branch:
        query = urllib.parse.urlencode({"query": f"branch:{branch}"})
        return f"{url}?{query}"
    return url


def build_file_url(repo_or_url: str, path: str, branch: str = "main") -> str:
    slug = parse_repo_slug(repo_or_url)
    clean_path = path.strip("/")
    if not clean_path:
        raise ValueError("file path is required")
    clean_branch = branch.strip("/") or "main"
    encoded_branch = urllib.parse.quote(clean_branch, safe="/")
    encoded_path = urllib.parse.quote(clean_path, safe="/")
    return f"https://github.com/{slug}/blob/{encoded_branch}/{encoded_path}"


def build_github_search_url(query: str, search_type: str = "repos") -> str:
    github_type = SEARCH_TYPES.get(search_type)
    if not github_type:
        expected = ", ".join(sorted(SEARCH_TYPES))
        raise ValueError(f"unknown GitHub search type: {search_type}; expected {expected}")
    params = urllib.parse.urlencode({"q": query, "type": github_type})
    return f"https://github.com/search?{params}"


def build_github_explore_url(
    *,
    topic: str = "",
    language: str = "",
    since: str = "daily",
    trending: bool = False,
) -> str:
    """Build a GitHub discovery URL for Explore, Topics, or Trending."""
    topic = topic.strip()
    language = language.strip()
    since = (since or "daily").strip().lower()
    if since not in TRENDING_WINDOWS:
        expected = ", ".join(sorted(TRENDING_WINDOWS))
        raise ValueError(f"unknown trending window: {since}; expected {expected}")
    if topic and (language or trending):
        raise ValueError("cannot combine --topic with --language or --trending")

    if topic:
        return f"https://github.com/topics/{_slugify_topic(topic)}"

    if language or trending:
        path = "/trending"
        if language:
            path += f"/{urllib.parse.quote(_slugify_topic(language), safe='')}"
        query = urllib.parse.urlencode({"since": since})
        return f"https://github.com{path}?{query}"

    return "https://github.com/explore"


def state_filter_terms(kind: str, state: str) -> tuple[str, ...]:
    kind = kind.lower()
    state = state.lower()
    filters = ISSUE_STATES if kind == "issues" else PR_STATES if kind == "prs" else None
    if filters is None:
        raise ValueError("kind must be issues or prs")
    terms = filters.get(state)
    if terms is None:
        expected = ", ".join(filters)
        raise ValueError(f"unknown {kind} state: {state}; expected {expected}")
    return terms


def format_repo_summary(summary: dict[str, Any]) -> str:
    if not summary:
        return "No GitHub repo summary found."

    preferred = [
        "name",
        "url",
        "description",
        "default_branch",
        "visibility",
        "stars",
        "forks",
        "watchers",
        "open_issues",
        "language",
        "license",
        "last_updated",
    ]
    return _format_mapping(summary, preferred, empty="No GitHub repo summary found.")


def format_issue_results(results: list[dict[str, Any]], label: str = "issues") -> str:
    if not results:
        return f"No GitHub {label} found."

    lines: list[str] = []
    for index, result in enumerate(results, 1):
        number = result.get("number")
        number_text = f"#{number} " if number else ""
        title = result.get("title") or "(no title)"
        lines.append(f"[{index}] {number_text}{title}")
        for key in ("url", "state", "author", "labels", "comments", "updated"):
            value = result.get(key)
            if value in (None, "", []):
                continue
            if isinstance(value, list):
                value = ", ".join(str(item) for item in value)
            if key == "url":
                lines.append(f"    {value}")
            else:
                lines.append(f"    {key}: {value}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_actions_runs(runs: list[dict[str, Any]]) -> str:
    if not runs:
        return "No GitHub Actions runs found."

    lines: list[str] = []
    for index, run in enumerate(runs, 1):
        lines.append(f"[{index}] {run.get('title') or '(no title)'}")
        for key in ("url", "status", "branch", "event", "actor", "updated"):
            value = run.get(key)
            if not value:
                continue
            if key == "url":
                lines.append(f"    {value}")
            else:
                lines.append(f"    {key}: {value}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_file_view(file_view: dict[str, Any]) -> str:
    if not file_view:
        return "No GitHub file content found."

    lines = []
    for key in ("path", "url", "branch", "language"):
        value = file_view.get(key)
        if value:
            lines.append(f"{key}: {value}")
    text = file_view.get("text") or ""
    if text:
        if lines:
            lines.append("")
        lines.append(str(text))
    return "\n".join(lines) if lines else "No GitHub file content found."


def format_search_results(results: list[dict[str, Any]]) -> str:
    if not results:
        return "No GitHub search results found."
    return format_issue_results(results, label="search results")


def format_explore_results(results: list[dict[str, Any]]) -> str:
    if not results:
        return "No GitHub explore repositories found."

    lines: list[str] = []
    for index, result in enumerate(results, 1):
        lines.append(f"[{index}] {result.get('name') or '(unknown repo)'}")
        for key in ("url", "description", "language", "stars", "forks", "updated"):
            value = result.get(key)
            if value in (None, "", []):
                continue
            if key == "url":
                lines.append(f"    {value}")
            else:
                lines.append(f"    {key}: {value}")
        topics = result.get("topics") or []
        if topics:
            lines.append("    topics: " + ", ".join(str(topic) for topic in topics))
        lines.append("")
    return "\n".join(lines).rstrip()


def to_json(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def extract_repo_summary(driver) -> dict[str, Any]:
    """Extract a best-effort repository summary from the current GitHub page."""
    from selenium.webdriver.common.by import By

    url = driver.current_url
    name = _safe_repo_slug_from_url(url)
    description = _text_by_selectors(
        driver,
        [
            "p.f4.my-3",
            "span[data-pjax='#repo-content-pjax-container']",
            "meta[name='description']",
        ],
        attr_fallbacks={"meta[name='description']": "content"},
    )
    default_branch = _text_by_selectors(
        driver,
        [
            "summary[title='Switch branches or tags'] span",
            "button[data-hotkey='w'] span",
            "[data-testid='branch-picker-button'] span",
        ],
    )
    stats = _extract_repo_stats(driver, By)

    return {
        "name": name,
        "url": build_repo_url(name) if name else url,
        "title": driver.title,
        "description": _clean_text(description),
        "default_branch": _clean_text(default_branch),
        "visibility": _text_by_selectors(driver, ["span.Label"]).lower(),
        "stars": stats.get("stars", ""),
        "forks": stats.get("forks", ""),
        "watchers": stats.get("watchers", ""),
        "open_issues": stats.get("open_issues", ""),
        "language": _first_repo_language(driver, By),
        "license": _text_by_selectors(driver, ["a[href*='/blob/'][href*='LICENSE']"]),
        "last_updated": _text_by_selectors(driver, ["relative-time"]),
    }


def extract_issue_results(driver, limit: int = 20) -> list[dict[str, Any]]:
    """Extract visible issue or PR rows from GitHub list/search pages."""
    from selenium.webdriver.common.by import By

    rows = driver.find_elements(
        By.CSS_SELECTOR,
        "div.js-issue-row, [data-testid='issue-row'], [id^='issue_'], div.Box-row",
    )
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if len(results) >= limit:
            break
        link = _first_element(
            row,
            By.CSS_SELECTOR,
            "a.Link--primary, a[data-hovercard-type='issue'], a[href*='/issues/'], a[href*='/pull/']",
        )
        if not link:
            continue
        href = link.get_attribute("href") or ""
        number = _extract_issue_number(href)
        if not href or href in seen:
            continue
        seen.add(href)
        results.append(
            {
                "number": number,
                "title": _clean_text(link.text or link.get_attribute("aria-label") or ""),
                "url": href,
                "state": _infer_state(row),
                "author": _text_by_selectors(row, ["a.Link--muted, a.author, a[data-hovercard-type='user']"]),
                "labels": _texts_by_selector(row, By.CSS_SELECTOR, "a.IssueLabel, span.IssueLabel"),
                "comments": _text_by_selectors(row, ["a[href$='#issuecomment-new'] span, a[href*='#issuecomment']"]),
                "updated": _text_by_selectors(row, ["relative-time"]),
            }
        )
    return results


def extract_pr_summary(driver) -> dict[str, Any]:
    """Extract a best-effort PR summary from the current GitHub PR page."""
    from selenium.webdriver.common.by import By

    title = _text_by_selectors(
        driver,
        [
            "bdi.js-issue-title",
            "span.js-issue-title",
            "[data-testid='issue-title']",
            "h1 bdi",
            "h1",
        ],
    )
    body = _text_by_selectors(driver, ["td.comment-body, div.comment-body, .markdown-body"])
    number = _extract_issue_number(driver.current_url)
    return {
        "number": number,
        "title": _clean_text(title or driver.title),
        "url": driver.current_url,
        "state": _text_by_selectors(driver, [".State, [data-testid='header-state']"]),
        "author": _text_by_selectors(driver, ["a.author, a.Link--primary[data-hovercard-type='user']"]),
        "base": _text_by_selectors(driver, [".base-ref, span.commit-ref.base-ref"]),
        "head": _text_by_selectors(driver, [".head-ref, span.commit-ref.head-ref"]),
        "body": _clean_text(body),
    }


def extract_actions_runs(driver, limit: int = 10) -> list[dict[str, Any]]:
    """Extract visible workflow run rows from a GitHub Actions page."""
    from selenium.webdriver.common.by import By

    rows = driver.find_elements(
        By.CSS_SELECTOR,
        "[data-testid='workflow-run-row'], div.workflow-run, div.Box-row, li.Box-row",
    )
    runs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if len(runs) >= limit:
            break
        link = _first_element(row, By.CSS_SELECTOR, "a[href*='/actions/runs/']")
        if not link:
            continue
        href = link.get_attribute("href") or ""
        if not href or href in seen:
            continue
        seen.add(href)
        runs.append(
            {
                "title": _clean_text(link.text or link.get_attribute("aria-label") or ""),
                "url": href,
                "status": _infer_actions_status(row),
                "branch": _text_by_selectors(row, ["a[href*='/tree/'], span.commit-ref"]),
                "event": _text_by_selectors(row, ["span[title='Event'], [data-testid='event']"]),
                "actor": _text_by_selectors(row, ["a[data-hovercard-type='user'], a.author"]),
                "updated": _text_by_selectors(row, ["relative-time"]),
            }
        )
    return runs


def extract_file_view(driver, path: str = "") -> dict[str, Any]:
    """Extract rendered text or source text from the current GitHub file page."""
    from selenium.webdriver.common.by import By

    text = _extract_blob_text(driver, By)
    if not text:
        text = _text_by_selectors(driver, ["article.markdown-body, div.markdown-body"])

    return {
        "path": path or _path_from_blob_url(driver.current_url),
        "url": driver.current_url,
        "branch": _branch_from_blob_url(driver.current_url),
        "language": _text_by_selectors(driver, ["span.color-fg-muted.text-small"]),
        "text": text,
    }


def extract_search_results(driver, limit: int = 20) -> list[dict[str, Any]]:
    """Extract visible GitHub search results from the current search page."""
    from selenium.webdriver.common.by import By

    rows = driver.find_elements(
        By.CSS_SELECTOR,
        "div.Box-row, div[data-testid='results-list'] div, div.search-title",
    )
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if len(results) >= limit:
            break
        link = _first_element(row, By.CSS_SELECTOR, "a[href]")
        if not link:
            continue
        href = link.get_attribute("href") or ""
        title = _clean_text(link.text or link.get_attribute("aria-label") or "")
        if not href or not title or href in seen:
            continue
        seen.add(href)
        results.append(
            {
                "title": title,
                "url": href,
                "description": _clean_text(row.text).replace(title, "", 1).strip(),
            }
        )
    return results


def extract_explore_results(driver, limit: int = 20) -> list[dict[str, Any]]:
    """Extract visible repository cards from GitHub Explore, Topics, or Trending."""
    return _list_result(driver.execute_script(_EXPLORE_REPOS_SCRIPT, limit))


def _repo_query_url(repo_or_url: str, path: str, terms: tuple[str, ...]) -> str:
    slug = parse_repo_slug(repo_or_url)
    query = urllib.parse.urlencode({"q": " ".join(terms)})
    return f"https://github.com/{slug}/{path}?{query}"


def _format_mapping(data: dict[str, Any], preferred: list[str], empty: str) -> str:
    lines: list[str] = []
    for key in preferred:
        value = data.get(key)
        if value not in (None, "", []):
            lines.append(f"{key}: {value}")
    for key, value in data.items():
        if key not in preferred and value not in (None, "", []):
            lines.append(f"{key}: {value}")
    return "\n".join(lines) if lines else empty


def _validate_repo_slug(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value):
        raise ValueError(f"expected GitHub repository as owner/repo, got: {value}")
    return value


def _strip_git_suffix(value: str) -> str:
    return value[:-4] if value.endswith(".git") else value


def _slugify_topic(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")


def _looks_like_url(value: str) -> bool:
    return "://" in value or value.startswith("github.com/") or value.startswith("www.github.com/")


def _parse_url(value: str) -> urllib.parse.ParseResult:
    if value.startswith("github.com/") or value.startswith("www.github.com/"):
        value = "https://" + value
    return urllib.parse.urlparse(value)


def _safe_repo_slug_from_url(url: str) -> str:
    try:
        return parse_repo_slug(url)
    except ValueError:
        return ""


def _extract_issue_number(url: str) -> str:
    match = re.search(r"/(?:issues|pull)/(\d+)(?:\D|$)", url)
    return match.group(1) if match else ""


def _path_from_blob_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    parts = [urllib.parse.unquote(part) for part in parsed.path.split("/") if part]
    if len(parts) >= 5 and parts[2] == "blob":
        return "/".join(parts[4:])
    return ""


def _branch_from_blob_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    parts = [urllib.parse.unquote(part) for part in parsed.path.split("/") if part]
    if len(parts) >= 4 and parts[2] == "blob":
        return parts[3]
    return ""


def _extract_repo_stats(driver, by) -> dict[str, str]:
    stats = {"stars": "", "forks": "", "watchers": "", "open_issues": ""}
    for link in driver.find_elements(by.CSS_SELECTOR, "a[href$='/stargazers'], a[href$='/forks'], a[href$='/watchers'], a[href$='/issues']"):
        href = link.get_attribute("href") or ""
        text = _clean_text(link.text)
        if not text:
            continue
        if href.endswith("/stargazers"):
            stats["stars"] = text
        elif href.endswith("/forks"):
            stats["forks"] = text
        elif href.endswith("/watchers"):
            stats["watchers"] = text
        elif href.endswith("/issues"):
            stats["open_issues"] = text
    return stats


def _first_repo_language(driver, by) -> str:
    selectors = [
        "li.d-inline a[href*='search?l='] span[itemprop='programmingLanguage']",
        "span[itemprop='programmingLanguage']",
    ]
    for selector in selectors:
        text = _text_by_selectors(driver, [selector])
        if text:
            return text
    return ""


def _extract_blob_text(driver, by) -> str:
    rows = driver.find_elements(by.CSS_SELECTOR, "td.blob-code, [data-testid='blob-code-cell']")
    if rows:
        return "\n".join(_clean_text(row.text) for row in rows if _clean_text(row.text))
    pre = _first_driver_element(driver, by, "pre, textarea")
    if pre:
        return pre.text or pre.get_attribute("value") or ""
    return ""


def _infer_state(row) -> str:
    text = _clean_text(row.text).lower()
    aria = (row.get_attribute("aria-label") or "").lower()
    combined = f"{text} {aria}"
    if "merged" in combined:
        return "merged"
    if "closed" in combined:
        return "closed"
    if "open" in combined:
        return "open"
    return ""


def _infer_actions_status(row) -> str:
    text = _clean_text(row.text).lower()
    aria = (row.get_attribute("aria-label") or "").lower()
    combined = f"{text} {aria}"
    for value in ("failure", "failed", "cancelled", "success", "passing", "queued", "in progress"):
        if value in combined:
            return "passing" if value == "success" else value
    return ""


def _first_element(parent, by, selector):
    try:
        return parent.find_element(by, selector)
    except Exception:
        return None


def _first_driver_element(driver, by, selector):
    try:
        return driver.find_element(by, selector)
    except Exception:
        return None


def _texts_by_selector(parent, by, selector) -> list[str]:
    try:
        elements = [element for element in parent.find_elements(by, selector) if element.is_displayed()]
        return [_clean_text(element.text) for element in elements if _clean_text(element.text)]
    except Exception:
        return []


def _text_by_selectors(
    parent,
    selectors: list[str],
    attr_fallbacks: Optional[dict[str, str]] = None,
) -> str:
    attr_fallbacks = attr_fallbacks or {}
    for selector in selectors:
        try:
            element = parent.find_element("css selector", selector)
            attr = attr_fallbacks.get(selector)
            value = element.get_attribute(attr) if attr else element.text
            if value:
                return _clean_text(value)
        except Exception:
            continue
    return ""


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _list_result(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


_EXPLORE_REPOS_SCRIPT = r"""
const limit = Number(arguments[arguments.length - 1]) || 20;
const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();
const visible = (el) => {
  if (!el) return false;
  const style = window.getComputedStyle(el);
  if (style.display === 'none' || style.visibility === 'hidden') return false;
  return !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
};
const repoPath = (href) => {
  try {
    const url = new URL(href, window.location.origin);
    if (url.hostname !== 'github.com') return '';
    const parts = url.pathname.split('/').filter(Boolean);
    if (parts.length !== 2) return '';
    if (!/^[A-Za-z0-9_.-]+$/.test(parts[0]) || !/^[A-Za-z0-9_.-]+$/.test(parts[1])) return '';
    return `${parts[0]}/${parts[1]}`;
  } catch {
    return '';
  }
};
const bestContainer = (link) => {
  return link.closest('article') ||
    link.closest('.Box-row') ||
    link.closest('[data-hpc]') ||
    link.closest('li') ||
    link.parentElement;
};
const items = [];
const seen = new Set();
const links = Array.from(document.querySelectorAll("a[href]")).filter(visible);

for (const link of links) {
  if (items.length >= limit) break;
  const name = repoPath(link.href);
  if (!name || seen.has(name)) continue;
  const container = bestContainer(link);
  const text = clean(container?.innerText || link.innerText || '');
  if (!text || text.length < name.length) continue;
  seen.add(name);

  const description = clean(
    container?.querySelector?.("p, [itemprop='description']")?.innerText || ''
  );
  const language = clean(
    container?.querySelector?.("[itemprop='programmingLanguage']")?.innerText || ''
  );
  const starsLink = container?.querySelector?.("a[href$='/stargazers']");
  const forksLink = container?.querySelector?.("a[href$='/forks']");
  const topics = Array.from(container?.querySelectorAll?.("a.topic-tag, a[href^='/topics/']") || [])
    .map((el) => clean(el.innerText || el.textContent))
    .filter(Boolean);
  const updated = clean(container?.querySelector?.("relative-time")?.innerText || '') ||
    (text.match(/\bUpdated [^\n]+/i)?.[0] || '');

  items.push({
    name,
    url: `https://github.com/${name}`,
    description,
    language,
    stars: clean(starsLink?.innerText || ''),
    forks: clean(forksLink?.innerText || ''),
    updated,
    topics,
  });
}

return items;
"""
