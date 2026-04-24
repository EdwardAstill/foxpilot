"""Generic page inspection helpers for site command branches."""

from __future__ import annotations

from typing import Any, Literal


LinkFilter = Literal["all", "internal", "external"]


def extract_outline(driver, limit: int = 100) -> list[dict[str, Any]]:
    """Extract visible document headings from the current page."""
    return _list_result(driver.execute_script(_OUTLINE_SCRIPT, limit))


def extract_links(
    driver,
    link_filter: LinkFilter = "all",
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Extract visible links from the current page."""
    if link_filter not in {"all", "internal", "external"}:
        raise ValueError("link_filter must be all, internal, or external")
    return _list_result(driver.execute_script(_LINKS_SCRIPT, link_filter, limit))


def extract_forms(driver, limit: int = 50) -> list[dict[str, Any]]:
    """Extract forms and visible controls from the current page."""
    return _list_result(driver.execute_script(_FORMS_SCRIPT, limit))


def extract_buttons(driver, limit: int = 100) -> list[dict[str, Any]]:
    """Extract visible buttons and button-like controls from the current page."""
    return _list_result(driver.execute_script(_BUTTONS_SCRIPT, limit))


def extract_inputs(driver, limit: int = 100) -> list[dict[str, Any]]:
    """Extract visible user-editable inputs from the current page."""
    return _list_result(driver.execute_script(_INPUTS_SCRIPT, limit))


def extract_metadata(driver) -> dict[str, Any]:
    """Extract document metadata from the current page."""
    data = driver.execute_script(_METADATA_SCRIPT)
    if not isinstance(data, dict):
        data = {}
    data.setdefault("title", getattr(driver, "title", ""))
    data.setdefault("url", getattr(driver, "current_url", ""))
    return data


def extract_landmarks(driver, limit: int = 100) -> list[dict[str, Any]]:
    """Extract accessible landmarks from the current page."""
    return _list_result(driver.execute_script(_LANDMARKS_SCRIPT, limit))


def format_outline(outline: list[dict[str, Any]]) -> str:
    if not outline:
        return "No page outline found."

    lines: list[str] = []
    for item in outline:
        level = _int_value(item.get("level"), default=1)
        text = _display_text(item.get("text"), "(no text)")
        suffix = ""
        if item.get("id"):
            suffix = f" #{item['id']}"
        elif item.get("selector"):
            suffix = f" {item['selector']}"
        lines.append(f"{'  ' * max(0, level - 1)}H{level} {text}{suffix}")
    return "\n".join(lines)


def format_links(links: list[dict[str, Any]]) -> str:
    if not links:
        return "No links found."

    lines: list[str] = []
    for index, link in enumerate(links, 1):
        text = _display_text(link.get("text"), "(no text)")
        kind = "internal" if link.get("is_internal") else "external"
        lines.append(f"[{index}] [{kind}] {text}")
        href = link.get("href")
        if href:
            lines.append(f"    {href}")
        for key in ("title", "rel", "target"):
            value = link.get(key)
            if value:
                lines.append(f"    {key}: {value}")
        if link.get("selector"):
            lines.append(f"    selector: {link['selector']}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_forms(forms: list[dict[str, Any]]) -> str:
    if not forms:
        return "No forms found."

    lines: list[str] = []
    for index, form in enumerate(forms, 1):
        label = _display_text(form.get("label") or form.get("name") or form.get("id"), "(unlabelled form)")
        method = _display_text(form.get("method"), "GET")
        action = _display_text(form.get("action"), "(current page)")
        lines.append(f"[{index}] {label}")
        lines.append(f"    {method} {action}")
        if form.get("selector"):
            lines.append(f"    selector: {form['selector']}")
        fields = form.get("fields") if isinstance(form.get("fields"), list) else []
        for field in fields:
            lines.append(f"    field: {_format_control(field)}")
        buttons = form.get("buttons") if isinstance(form.get("buttons"), list) else []
        for button in buttons:
            lines.append(f"    button: {_format_control(button)}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_buttons(buttons: list[dict[str, Any]]) -> str:
    if not buttons:
        return "No buttons found."

    lines: list[str] = []
    for index, button in enumerate(buttons, 1):
        lines.append(f"[{index}] {_format_control(button)}")
        if button.get("selector"):
            lines.append(f"    selector: {button['selector']}")
    return "\n".join(lines)


def format_inputs(inputs: list[dict[str, Any]]) -> str:
    if not inputs:
        return "No inputs found."

    lines: list[str] = []
    for index, input_info in enumerate(inputs, 1):
        lines.append(f"[{index}] {_format_control(input_info)}")
        if input_info.get("selector"):
            lines.append(f"    selector: {input_info['selector']}")
    return "\n".join(lines)


def format_metadata(metadata: dict[str, Any]) -> str:
    if not metadata:
        return "No page metadata found."

    preferred = [
        "title",
        "url",
        "description",
        "canonical",
        "language",
        "charset",
        "viewport",
        "robots",
        "favicon",
    ]
    lines: list[str] = []
    for key in preferred:
        value = metadata.get(key)
        if value not in (None, "", [], {}):
            lines.append(f"{key}: {value}")

    for group in ("open_graph", "twitter", "meta"):
        values = metadata.get(group)
        if not isinstance(values, dict):
            continue
        for key, value in values.items():
            if value not in (None, "", [], {}):
                lines.append(f"{key}: {value}")

    for key, value in metadata.items():
        if key in preferred or key in {"open_graph", "twitter", "meta"}:
            continue
        if value not in (None, "", [], {}):
            lines.append(f"{key}: {value}")

    return "\n".join(lines)


def format_landmarks(landmarks: list[dict[str, Any]]) -> str:
    if not landmarks:
        return "No landmarks found."

    lines: list[str] = []
    for index, landmark in enumerate(landmarks, 1):
        role = _display_text(landmark.get("role"), "landmark")
        label = _display_text(landmark.get("label"), "(unlabelled)")
        tag = _display_text(landmark.get("tag"), "")
        suffix = f" <{tag}>" if tag else ""
        lines.append(f"[{index}] {role} {label}{suffix}")
        if landmark.get("selector"):
            lines.append(f"    selector: {landmark['selector']}")
        if landmark.get("text"):
            lines.append(f"    text: {_display_text(landmark['text'], '')}")
    return "\n".join(lines)


def _format_control(control: dict[str, Any]) -> str:
    control_type = _display_text(control.get("type") or control.get("tag"), "control")
    label = _display_text(
        control.get("text")
        or control.get("label")
        or control.get("placeholder")
        or control.get("name")
        or control.get("id"),
        "(unlabelled)",
    )
    parts = [control_type, label]
    for key in ("name", "placeholder", "autocomplete"):
        value = control.get(key)
        if value:
            parts.append(f"{key}={value}")
    if control.get("required"):
        parts.append("required")
    if control.get("disabled"):
        parts.append("disabled")
    if control.get("checked"):
        parts.append("checked")
    return " ".join(str(part) for part in parts if part)


def _list_result(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _display_text(value: Any, fallback: str) -> str:
    if value is None:
        return fallback
    text = " ".join(str(value).split())
    return text if text else fallback


def _int_value(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


_COMMON_JS = r"""
const limit = Number(arguments[arguments.length - 1]) || 100;
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
    if (node.classList && node.classList.length) {
      part += `.${CSS.escape(node.classList[0])}`;
    }
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
  const idrefs = attr(el, 'aria-labelledby');
  if (!idrefs) return '';
  return cleanText(idrefs.split(/\s+/).map((id) => {
    const label = document.getElementById(id);
    return label ? label.textContent : '';
  }).join(' '));
};
const labelFor = (el) => {
  if (!el) return '';
  const aria = attr(el, 'aria-label') || labelledBy(el);
  if (aria) return aria;
  if (el.id) {
    const label = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
    if (label) return cleanText(label.textContent);
  }
  const wrapped = el.closest('label');
  if (wrapped) return cleanText(wrapped.textContent);
  const title = attr(el, 'title');
  if (title) return title;
  return '';
};
const controlType = (el) => {
  const tag = el.tagName.toLowerCase();
  if (tag === 'input') return (attr(el, 'type') || 'text').toLowerCase();
  return tag;
};
const controlInfo = (el) => ({
  tag: el.tagName.toLowerCase(),
  type: controlType(el),
  label: labelFor(el),
  text: cleanText(el.innerText || el.value),
  name: attr(el, 'name'),
  id: attr(el, 'id'),
  placeholder: attr(el, 'placeholder'),
  autocomplete: attr(el, 'autocomplete'),
  required: !!el.required,
  disabled: !!el.disabled || attr(el, 'aria-disabled') === 'true',
  checked: !!el.checked,
  selector: cssPath(el),
});
"""


_OUTLINE_SCRIPT = _COMMON_JS + r"""
return Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6'))
  .filter(visible)
  .slice(0, limit)
  .map((heading) => ({
    level: Number(heading.tagName.slice(1)),
    text: cleanText(heading.innerText || heading.textContent),
    id: attr(heading, 'id'),
    selector: cssPath(heading),
  }));
"""


_LINKS_SCRIPT = _COMMON_JS + r"""
const filter = arguments[0] || 'all';
const pageUrl = new URL(window.location.href);
return Array.from(document.querySelectorAll('a[href], area[href]'))
  .filter(visible)
  .map((link) => {
    const href = new URL(link.getAttribute('href'), pageUrl.href).href;
    const url = new URL(href);
    return {
      text: cleanText(link.innerText || link.textContent || attr(link, 'aria-label') || href),
      href,
      title: attr(link, 'title'),
      rel: attr(link, 'rel'),
      target: attr(link, 'target'),
      is_internal: url.origin === pageUrl.origin,
      selector: cssPath(link),
    };
  })
  .filter((link) => filter === 'all' || (filter === 'internal' ? link.is_internal : !link.is_internal))
  .slice(0, limit);
"""


_FORMS_SCRIPT = _COMMON_JS + r"""
return Array.from(document.querySelectorAll('form'))
  .slice(0, limit)
  .map((form) => {
    const legend = form.querySelector('legend');
    const controls = Array.from(form.querySelectorAll('input, select, textarea'));
    const buttons = Array.from(form.querySelectorAll('button, input[type="button"], input[type="submit"], input[type="reset"], [role="button"]'));
    return {
      label: labelFor(form) || attr(form, 'name') || attr(form, 'id') || (legend ? cleanText(legend.textContent) : ''),
      method: (attr(form, 'method') || 'get').toUpperCase(),
      action: attr(form, 'action') || form.getAttribute('action') || '',
      name: attr(form, 'name'),
      id: attr(form, 'id'),
      selector: cssPath(form),
      fields: controls.filter((el) => controlType(el) !== 'hidden').filter(visible).map(controlInfo),
      buttons: buttons.filter(visible).map(controlInfo),
    };
  });
"""


_BUTTONS_SCRIPT = _COMMON_JS + r"""
const seen = new Set();
return Array.from(document.querySelectorAll('button, input[type="button"], input[type="submit"], input[type="reset"], [role="button"]'))
  .filter((button) => {
    if (!visible(button) || seen.has(button)) return false;
    seen.add(button);
    return true;
  })
  .slice(0, limit)
  .map(controlInfo);
"""


_INPUTS_SCRIPT = _COMMON_JS + r"""
return Array.from(document.querySelectorAll('input, select, textarea'))
  .filter((input) => controlType(input) !== 'hidden')
  .filter(visible)
  .slice(0, limit)
  .map(controlInfo);
"""


_METADATA_SCRIPT = _COMMON_JS + r"""
const meta = {};
const openGraph = {};
const twitter = {};
for (const node of Array.from(document.querySelectorAll('meta'))) {
  const key = attr(node, 'name') || attr(node, 'property') || attr(node, 'itemprop');
  const value = attr(node, 'content');
  if (!key || !value) continue;
  if (key.startsWith('og:')) openGraph[key] = value;
  else if (key.startsWith('twitter:')) twitter[key] = value;
  else meta[key] = value;
}
const canonical = document.querySelector('link[rel~="canonical"]');
const favicon = document.querySelector('link[rel~="icon"], link[rel="shortcut icon"]');
return {
  title: cleanText(document.title),
  url: window.location.href,
  description: meta.description || '',
  canonical: canonical ? canonical.href : '',
  language: attr(document.documentElement, 'lang'),
  charset: document.characterSet || '',
  viewport: meta.viewport || '',
  robots: meta.robots || '',
  favicon: favicon ? favicon.href : '',
  open_graph: openGraph,
  twitter,
  meta,
};
"""


_LANDMARKS_SCRIPT = _COMMON_JS + r"""
const roleFor = (el) => {
  const explicit = attr(el, 'role').toLowerCase();
  const landmarkRoles = new Set(['banner', 'navigation', 'main', 'complementary', 'contentinfo', 'search', 'form', 'region']);
  if (landmarkRoles.has(explicit)) return explicit;
  const tag = el.tagName.toLowerCase();
  if (tag === 'nav') return 'navigation';
  if (tag === 'main') return 'main';
  if (tag === 'aside') return 'complementary';
  if (tag === 'header' && !el.closest('article, aside, main, nav, section')) return 'banner';
  if (tag === 'footer' && !el.closest('article, aside, main, nav, section')) return 'contentinfo';
  if (tag === 'form' && labelFor(el)) return 'form';
  if (tag === 'section' && labelFor(el)) return 'region';
  return '';
};
const candidates = Array.from(document.querySelectorAll('[role], main, nav, aside, header, footer, form, section[aria-label], section[aria-labelledby]'));
return candidates
  .map((el) => ({ el, role: roleFor(el) }))
  .filter((item) => item.role && visible(item.el))
  .slice(0, limit)
  .map((item) => ({
    role: item.role,
    label: labelFor(item.el),
    tag: item.el.tagName.toLowerCase(),
    id: attr(item.el, 'id'),
    selector: cssPath(item.el),
    text: cleanText(item.el.innerText || item.el.textContent).slice(0, 160),
  }));
"""
