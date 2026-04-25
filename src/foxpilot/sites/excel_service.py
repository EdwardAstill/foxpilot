"""Service layer for Excel Online (excel.cloud.microsoft) browser workflows.

Excel Online renders the cell grid on a canvas, so cell values are not
available via DOM scraping. This module instead routes reads/writes through
the Name Box (cell-reference jump) and the Formula Bar (visible value of the
active cell). Sheet tabs and the file-name input are real DOM and can be
queried directly.
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Any


EXCEL_HOST = "excel.cloud.microsoft"
EXCEL_HOME = f"https://{EXCEL_HOST}/"

CELL_REF_RE = re.compile(r"^[A-Za-z]{1,3}[0-9]{1,7}(?::[A-Za-z]{1,3}[0-9]{1,7})?$")
DEFINED_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]{0,254}$")


def is_excel_url(value: str) -> bool:
    if not value:
        return False
    parsed = urllib.parse.urlparse(value)
    host = (parsed.netloc or "").lower()
    return host.endswith("excel.cloud.microsoft") or "excel.officeapps.live.com" in host or "office.com" in host


def normalize_cell_ref(value: str) -> str:
    cleaned = (value or "").strip().replace(" ", "").upper()
    if not CELL_REF_RE.match(cleaned):
        raise ValueError(f"invalid cell reference: {value!r} (expected like A1 or A1:C5)")
    return cleaned


def home_url() -> str:
    return EXCEL_HOME


def format_open_result(data: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"title: {data.get('title', '')}",
            f"url: {data.get('url', '')}",
            f"workbook: {data.get('workbook', '')}",
        ]
    )


def format_sheets(sheets: list[dict[str, Any]]) -> str:
    if not sheets:
        return "(no sheet tabs detected)"
    return "\n".join(
        f"{'*' if s.get('active') else ' '} {s.get('name', '')}"
        for s in sheets
    )


def format_cell(data: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"cell: {data.get('cell', '')}",
            f"value: {data.get('value', '')}",
            f"sheet: {data.get('sheet', '')}",
        ]
    )


def extract_workbook_title(driver) -> str:
    """Read the workbook name from the title input near the top-left."""
    candidates = [
        "input[aria-label='File name']",
        "input[aria-label*='File name']",
        "input.fui-Input__input[type='text']",
    ]
    for selector in candidates:
        elem = _find_one(driver, "css selector", selector)
        if elem is not None:
            value = elem.get_attribute("value")
            if value:
                return value
    return ""


def extract_sheet_tabs(driver) -> list[dict[str, Any]]:
    """List sheet tabs at bottom of workbook. Names + active flag."""
    by = "css selector"
    tab_nodes = _find_all(driver, by, "[role='tab'][aria-label]")
    if not tab_nodes:
        tab_nodes = _find_all(driver, by, ".sheet-tab, .ewa-stss-tab")
    sheets: list[dict[str, Any]] = []
    for node in tab_nodes:
        name = (node.get_attribute("aria-label") or node.text or "").strip()
        if not name:
            continue
        active = (node.get_attribute("aria-selected") or "").lower() == "true"
        sheets.append({"name": name, "active": active})
    return sheets


def extract_active_cell(driver) -> dict[str, Any]:
    """Read the active cell reference + formula-bar value."""
    cell = _read_name_box_value(driver)
    value = _read_formula_bar_value(driver)
    sheet = _read_active_sheet_name(driver)
    return {"cell": cell, "value": value, "sheet": sheet}


def goto_cell(driver, cell: str) -> None:
    """Type a cell reference into the Name Box and press Enter."""
    ref = normalize_cell_ref(cell)
    name_box = _find_name_box(driver)
    if name_box is None:
        raise RuntimeError("could not find the Name Box (cell reference input)")
    name_box.click()
    try:
        name_box.clear()
    except Exception:
        pass
    name_box.send_keys(ref)
    from selenium.webdriver.common.keys import Keys
    name_box.send_keys(Keys.ENTER)


NUMBER_FORMAT_SHORTCUTS = {
    "general": "~",
    "number": "1",
    "time": "2",
    "date": "3",
    "currency": "4",
    "percent": "5",
}

ALIGN_SHORTCUTS = {
    "left": "l",
    "center": "e",
    "right": "r",
}


def normalize_number_format(kind: str) -> str:
    cleaned = (kind or "").strip().lower()
    if cleaned not in NUMBER_FORMAT_SHORTCUTS:
        raise ValueError(
            f"unknown number format: {kind!r} "
            f"(expected one of: {', '.join(sorted(NUMBER_FORMAT_SHORTCUTS))})"
        )
    return cleaned


def normalize_alignment(value: str) -> str:
    cleaned = (value or "").strip().lower()
    if cleaned not in ALIGN_SHORTCUTS:
        raise ValueError(
            f"unknown alignment: {value!r} (expected: left, center, right)"
        )
    return cleaned


def apply_toggle_format(driver, range_ref: str, key: str) -> dict[str, Any]:
    """Select a range and fire a Ctrl+<key> keystroke (e.g. b/i/u)."""
    ref = normalize_cell_ref(range_ref)
    goto_cell(driver, ref)
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.common.keys import Keys
    ActionChains(driver).key_down(Keys.CONTROL).send_keys(key).key_up(Keys.CONTROL).perform()
    return {"range": ref, "format": _format_label_for(key)}


def apply_number_format(driver, range_ref: str, kind: str) -> dict[str, Any]:
    """Select a range and fire Ctrl+Shift+<key> for the requested number format."""
    cleaned = normalize_number_format(kind)
    ref = normalize_cell_ref(range_ref)
    goto_cell(driver, ref)
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.common.keys import Keys
    key = NUMBER_FORMAT_SHORTCUTS[cleaned]
    actions = ActionChains(driver)
    actions.key_down(Keys.CONTROL).key_down(Keys.SHIFT).send_keys(key)
    actions.key_up(Keys.SHIFT).key_up(Keys.CONTROL).perform()
    return {"range": ref, "format": cleaned}


def apply_alignment(driver, range_ref: str, alignment: str) -> dict[str, Any]:
    """Select a range and click the matching ribbon alignment button (best effort)."""
    cleaned = normalize_alignment(alignment)
    ref = normalize_cell_ref(range_ref)
    goto_cell(driver, ref)
    if not _click_ribbon_button(driver, [
        f"button[aria-label='Align {cleaned.capitalize()}']",
        f"button[aria-label*='Align {cleaned.capitalize()}']",
        f"[role='menuitemradio'][aria-label*='Align {cleaned.capitalize()}']",
        f"[data-icon-name='Align{cleaned.capitalize()}']",
    ]):
        raise RuntimeError(
            f"could not find the {cleaned!r} alignment ribbon button "
            "(Excel Online ribbon DOM may have changed)"
        )
    return {"range": ref, "alignment": cleaned}


def clear_format(driver, range_ref: str) -> dict[str, Any]:
    """Select a range and click ribbon Clear > Clear Formats (best effort)."""
    ref = normalize_cell_ref(range_ref)
    goto_cell(driver, ref)
    if not _click_ribbon_button(driver, [
        "button[aria-label='Clear Formats']",
        "button[aria-label*='Clear Formats']",
        "[role='menuitem'][aria-label*='Clear Formats']",
    ]):
        raise RuntimeError(
            "could not find the 'Clear Formats' ribbon button "
            "(may need to open Home > Clear menu first)"
        )
    return {"range": ref}


def _format_label_for(key: str) -> str:
    return {"b": "bold", "i": "italic", "u": "underline"}.get(key.lower(), key)


def _click_ribbon_button(driver, selectors: list[str]) -> bool:
    from selenium.webdriver.common.by import By
    for selector in selectors:
        try:
            elem = driver.find_element(By.CSS_SELECTOR, selector)
        except Exception:
            continue
        try:
            elem.click()
            return True
        except Exception:
            continue
    return False


def select_range(driver, cells: str) -> str:
    """Select a cell or range via the Name Box. Returns normalized ref."""
    ref = normalize_cell_ref(cells)
    goto_cell(driver, ref)
    return ref


def normalize_defined_name(value: str) -> str:
    cleaned = (value or "").strip()
    if not DEFINED_NAME_RE.match(cleaned):
        raise ValueError(
            f"invalid defined name: {value!r} "
            "(must start with letter or underscore; letters/digits/_/. only; no spaces)"
        )
    if CELL_REF_RE.match(cleaned.upper()):
        raise ValueError(f"defined name {value!r} collides with a cell reference")
    return cleaned


def define_name(driver, range_ref: str, name: str) -> dict[str, Any]:
    """Select a range, then type a name into the Name Box and press Enter.

    Excel Online treats this as 'create defined name' when the typed value
    is not a valid cell reference.
    """
    ref = normalize_cell_ref(range_ref)
    defined = normalize_defined_name(name)
    goto_cell(driver, ref)
    box = _find_name_box(driver)
    if box is None:
        raise RuntimeError("could not find the Name Box")
    box.click()
    try:
        box.clear()
    except Exception:
        pass
    box.send_keys(defined)
    from selenium.webdriver.common.keys import Keys
    box.send_keys(Keys.ENTER)
    return {"range": ref, "name": defined}


def list_defined_names(driver) -> list[dict[str, Any]]:
    """Open the Name Box dropdown and read out defined names. Best effort."""
    by = "css selector"
    arrow = _find_one(driver, by, "[aria-label*='Name Box dropdown'], .namebox-dropdown, button[aria-label*='Name Box']")
    if arrow is None:
        return []
    try:
        arrow.click()
    except Exception:
        return []
    items = _find_all(driver, by, "[role='menuitem'], [role='option'], .namebox-list-item")
    names: list[dict[str, Any]] = []
    for node in items:
        text = (node.get_attribute("aria-label") or node.text or "").strip()
        if text:
            names.append({"name": text})
    try:
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.common.action_chains import ActionChains
        ActionChains(driver).send_keys(Keys.ESCAPE).perform()
    except Exception:
        pass
    return names


def fill_direction(driver, range_ref: str, direction: str) -> dict[str, Any]:
    """Select a range and apply the keyboard fill shortcut (down or right)."""
    if direction not in {"down", "right"}:
        raise ValueError(f"unknown fill direction: {direction!r}")
    ref = normalize_cell_ref(range_ref)
    goto_cell(driver, ref)
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.common.keys import Keys
    key = "d" if direction == "down" else "r"
    ActionChains(driver).key_down(Keys.CONTROL).send_keys(key).key_up(Keys.CONTROL).perform()
    return {"range": ref, "direction": direction}


def create_blank_workbook(driver) -> dict[str, Any]:
    """Navigate to Excel home and click the Blank workbook tile."""
    driver.get(EXCEL_HOME)
    from selenium.webdriver.common.by import By
    selectors = [
        "//*[@aria-label='Blank workbook' or normalize-space()='Blank workbook']",
        "//button[.//*[normalize-space()='Blank workbook']]",
        "//a[.//*[normalize-space()='Blank workbook']]",
    ]
    for xpath in selectors:
        try:
            elem = driver.find_element(By.XPATH, xpath)
        except Exception:
            continue
        try:
            elem.click()
            return {"url": driver.current_url, "title": driver.title}
        except Exception:
            continue
    raise RuntimeError("could not find 'Blank workbook' tile on Excel home")


def write_cell(driver, cell: str, value: str) -> dict[str, Any]:
    """Navigate to a cell and type a value, finishing with Enter."""
    goto_cell(driver, cell)
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.common.keys import Keys
    actions = ActionChains(driver)
    actions.send_keys(value)
    actions.send_keys(Keys.ENTER)
    actions.perform()
    return {"cell": normalize_cell_ref(cell), "value": value}


def _read_name_box_value(driver) -> str:
    box = _find_name_box(driver)
    if box is None:
        return ""
    return box.get_attribute("value") or ""


def _read_formula_bar_value(driver) -> str:
    selectors = [
        "input[aria-label='Formula Bar']",
        "[aria-label='formula bar']",
        "#formulaBarTextEditor",
        "div.ewr-fbicre",
    ]
    for selector in selectors:
        elem = _find_one(driver, "css selector", selector)
        if elem is None:
            continue
        value = elem.get_attribute("value") or elem.text
        if value is not None:
            return value
    return ""


def _read_active_sheet_name(driver) -> str:
    for tab in extract_sheet_tabs(driver):
        if tab.get("active"):
            return str(tab.get("name", ""))
    return ""


def _find_name_box(driver):
    selectors = [
        "input[aria-label='Name Box']",
        "input[aria-label*='Name Box']",
        "#NameBoxBox",
        ".namebox input",
    ]
    for selector in selectors:
        elem = _find_one(driver, "css selector", selector)
        if elem is not None:
            return elem
    return None


def _find_one(driver, by, selector):
    from selenium.webdriver.common.by import By
    by_obj = By.CSS_SELECTOR if by == "css selector" else by
    try:
        return driver.find_element(by_obj, selector)
    except Exception:
        return None


def _find_all(driver, by, selector):
    from selenium.webdriver.common.by import By
    by_obj = By.CSS_SELECTOR if by == "css selector" else by
    try:
        return driver.find_elements(by_obj, selector)
    except Exception:
        return []


__all__ = [
    "ALIGN_SHORTCUTS",
    "EXCEL_HOME",
    "EXCEL_HOST",
    "NUMBER_FORMAT_SHORTCUTS",
    "apply_alignment",
    "apply_number_format",
    "apply_toggle_format",
    "clear_format",
    "create_blank_workbook",
    "define_name",
    "extract_active_cell",
    "extract_sheet_tabs",
    "extract_workbook_title",
    "fill_direction",
    "format_cell",
    "format_open_result",
    "format_sheets",
    "goto_cell",
    "home_url",
    "is_excel_url",
    "list_defined_names",
    "normalize_alignment",
    "normalize_cell_ref",
    "normalize_defined_name",
    "normalize_number_format",
    "select_range",
    "write_cell",
]
