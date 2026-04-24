"""Agent-friendly page understanding from browser DOM inspection."""

from __future__ import annotations

import re
from typing import Any


_DANGEROUS_RE = re.compile(
    r"\b(delete|purchase|buy|send|merge|transfer ownership|submit payment|publish)\b",
    re.IGNORECASE,
)


def understand_page(driver, *, limit: int = 100) -> dict[str, Any]:
    """Return a stable map of the current page for agent planning."""
    data = _extract_page_data(driver, limit)
    page = {
        "title": str(data.get("title") or getattr(driver, "title", "") or ""),
        "url": str(data.get("url") or getattr(driver, "current_url", "") or ""),
        "headings": _list(data.get("headings")),
        "forms": _list(data.get("forms")),
        "buttons": _list(data.get("buttons")),
        "inputs": _list(data.get("inputs")),
        "links": _list(data.get("links")),
        "dangerous_actions": [],
        "suggested_next_actions": [],
        "visible_errors": [str(item) for item in _list(data.get("visible_errors")) if str(item)],
    }
    page["dangerous_actions"] = find_dangerous_actions(page)
    page["suggested_next_actions"] = suggest_next_actions(page)
    return page


def find_dangerous_actions(page: dict[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for source_name in ("buttons", "links"):
        for item in page.get(source_name, []):
            if not isinstance(item, dict):
                continue
            label = _label(item)
            if not label or not _DANGEROUS_RE.search(label):
                continue
            actions.append(
                {
                    "label": label,
                    "source": source_name[:-1],
                    "selector": item.get("selector", ""),
                    "href": item.get("href", ""),
                }
            )
    return actions


def suggest_next_actions(page: dict[str, Any]) -> list[str]:
    suggestions: list[str] = []
    for form in page.get("forms", []):
        if not isinstance(form, dict):
            continue
        label = _label(form) or "page"
        suggestions.append(f"Fill {label} form")
    for button in page.get("buttons", []):
        if not isinstance(button, dict):
            continue
        label = _label(button)
        if label and not _DANGEROUS_RE.search(label):
            suggestions.append(f"Click {label}")
    for link in page.get("links", [])[:5]:
        if not isinstance(link, dict):
            continue
        label = _label(link)
        if label and not _DANGEROUS_RE.search(label):
            suggestions.append(f"Open {label}")
    return _dedupe(suggestions)[:10]


def _extract_page_data(driver, limit: int) -> dict[str, Any]:
    execute_script = getattr(driver, "execute_script", None)
    if not callable(execute_script):
        return {}
    try:
        data = execute_script(_PAGE_BRAIN_SCRIPT, limit)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _label(item: dict[str, Any]) -> str:
    for key in ("text", "label", "aria_label", "name", "id", "href"):
        value = item.get(key)
        if value:
            return " ".join(str(value).split())
    return ""


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


_PAGE_BRAIN_SCRIPT = r"""
const limit = Number(arguments[0]) || 100;
const cleanText = (value) => String(value || '').replace(/\s+/g, ' ').trim();
const visible = (el) => {
  if (!el) return false;
  const style = window.getComputedStyle(el);
  if (style.visibility === 'hidden' || style.display === 'none') return false;
  return !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
};
const attr = (el, name) => cleanText(el.getAttribute(name));
const cssPath = (el) => {
  if (!el || !el.tagName) return '';
  if (el.id) return `${el.tagName.toLowerCase()}#${CSS.escape(el.id)}`;
  const parts = [];
  let node = el;
  while (node && node.nodeType === Node.ELEMENT_NODE && parts.length < 4) {
    let part = node.tagName.toLowerCase();
    if (node.classList && node.classList.length) part += `.${CSS.escape(node.classList[0])}`;
    const parent = node.parentElement;
    if (parent) {
      const same = Array.from(parent.children).filter((child) => child.tagName === node.tagName);
      if (same.length > 1) part += `:nth-of-type(${same.indexOf(node) + 1})`;
    }
    parts.unshift(part);
    node = parent;
  }
  return parts.join(' > ');
};
const labelledBy = (el) => {
  const ids = attr(el, 'aria-labelledby');
  if (!ids) return '';
  return cleanText(ids.split(/\s+/).map((id) => {
    const label = document.getElementById(id);
    return label ? label.textContent : '';
  }).join(' '));
};
const labelFor = (el) => {
  const aria = attr(el, 'aria-label') || labelledBy(el);
  if (aria) return aria;
  if (el.id) {
    const label = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
    if (label) return cleanText(label.textContent);
  }
  const wrapped = el.closest('label');
  if (wrapped) return cleanText(wrapped.textContent);
  return attr(el, 'title');
};
const controlType = (el) => el.tagName.toLowerCase() === 'input'
  ? (attr(el, 'type') || 'text').toLowerCase()
  : el.tagName.toLowerCase();
const controlInfo = (el) => ({
  tag: el.tagName.toLowerCase(),
  type: controlType(el),
  label: labelFor(el),
  text: cleanText(el.innerText || el.value),
  name: attr(el, 'name'),
  id: attr(el, 'id'),
  placeholder: attr(el, 'placeholder'),
  aria_label: attr(el, 'aria-label'),
  selector: cssPath(el),
  required: !!el.required,
  disabled: !!el.disabled || attr(el, 'aria-disabled') === 'true',
});
const buttons = Array.from(document.querySelectorAll('button, input[type="button"], input[type="submit"], input[type="reset"], [role="button"]'))
  .filter(visible)
  .slice(0, limit)
  .map(controlInfo);
const inputs = Array.from(document.querySelectorAll('input, select, textarea'))
  .filter((input) => controlType(input) !== 'hidden')
  .filter(visible)
  .slice(0, limit)
  .map(controlInfo);
return {
  title: cleanText(document.title),
  url: window.location.href,
  headings: Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6'))
    .filter(visible)
    .slice(0, limit)
    .map((heading) => ({
      level: Number(heading.tagName.slice(1)),
      text: cleanText(heading.innerText || heading.textContent),
      selector: cssPath(heading),
    })),
  forms: Array.from(document.querySelectorAll('form'))
    .filter(visible)
    .slice(0, limit)
    .map((form) => ({
      label: labelFor(form) || attr(form, 'name') || attr(form, 'id'),
      method: (attr(form, 'method') || 'get').toUpperCase(),
      action: attr(form, 'action') || form.getAttribute('action') || '',
      selector: cssPath(form),
      fields: Array.from(form.querySelectorAll('input, select, textarea'))
        .filter((field) => controlType(field) !== 'hidden')
        .filter(visible)
        .map(controlInfo),
      buttons: Array.from(form.querySelectorAll('button, input[type="button"], input[type="submit"], input[type="reset"], [role="button"]'))
        .filter(visible)
        .map(controlInfo),
    })),
  buttons,
  inputs,
  links: Array.from(document.querySelectorAll('a[href], area[href]'))
    .filter(visible)
    .slice(0, limit)
    .map((link) => ({
      text: cleanText(link.innerText || link.textContent || attr(link, 'aria-label')),
      href: link.href,
      selector: cssPath(link),
    })),
  visible_errors: Array.from(document.querySelectorAll('[role="alert"], .error, .errors, .invalid, [aria-invalid="true"]'))
    .filter(visible)
    .slice(0, limit)
    .map((el) => cleanText(el.innerText || el.textContent || labelFor(el)))
    .filter(Boolean),
};
"""
