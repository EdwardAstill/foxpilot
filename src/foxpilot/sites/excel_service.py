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
    with _excel_frame(driver):
        return _extract_sheet_tabs_inner(driver)


def _extract_sheet_tabs_inner(driver) -> list[dict[str, Any]]:
    """List sheet tabs at bottom of workbook. Names + active flag.

    Excel Online's sheet-tab strip lives in `#WACSheetTabs` and renders each
    tab as `[data-automationid='SheetTab']` (modern build) or `.sheet-tab`
    (legacy). Each tab carries the sheet name on `aria-label` and signals
    selection via `aria-selected="true"` or class `.selected`. We try a
    short list of selectors in priority order and fall back to a JS sweep
    of any element whose ancestor matches the tab strip.
    """
    by = "css selector"
    selector_priority = [
        "#WACSheetTabs [data-automationid='SheetTab']",
        "[data-automationid='SheetTab']",
        "#WACSheetTabs [role='tab']",
        "[role='tab'][aria-label][data-id*='Sheet']",
        ".sheet-tab",
        ".ewa-stss-tab",
        "[role='tab'][aria-label]",
    ]

    tab_nodes = []
    for selector in selector_priority:
        tab_nodes = _find_all(driver, by, selector)
        if tab_nodes:
            break

    sheets: list[dict[str, Any]] = []
    for node in tab_nodes:
        name = (
            node.get_attribute("aria-label")
            or node.get_attribute("title")
            or (node.text or "")
        ).strip()
        if not name:
            continue
        selected_attr = (node.get_attribute("aria-selected") or "").lower()
        class_attr = (node.get_attribute("class") or "").lower()
        active = selected_attr == "true" or " selected" in f" {class_attr}"
        sheets.append({"name": name, "active": active})

    if sheets:
        return sheets

    # JS fallback: scrape #WACSheetTabs descendants directly.
    try:
        raw = driver.execute_script(
            """
            const strip = document.querySelector('#WACSheetTabs') ||
                          document.querySelector('[id*="SheetTab"]');
            if (!strip) return [];
            const tabs = strip.querySelectorAll(
                "[data-automationid='SheetTab'], [role='tab'], .sheet-tab"
            );
            const out = [];
            tabs.forEach(t => {
                const name = (t.getAttribute('aria-label') ||
                              t.getAttribute('title') ||
                              (t.innerText || '').trim());
                if (!name) return;
                const cls = (t.className || '').toString().toLowerCase();
                const active = (t.getAttribute('aria-selected') || '').toLowerCase() === 'true' ||
                               cls.indexOf('selected') !== -1;
                out.push({name: name, active: active});
            });
            return out;
            """
        )
        if isinstance(raw, list):
            for entry in raw:
                if isinstance(entry, dict) and entry.get("name"):
                    sheets.append({"name": str(entry["name"]).strip(), "active": bool(entry.get("active"))})
    except Exception:
        pass
    return sheets


def extract_active_cell(driver) -> dict[str, Any]:
    """Read the active cell reference + formula-bar value."""
    with _excel_frame(driver):
        cell = _read_name_box_value(driver)
        value = _read_formula_bar_value(driver)
        sheet = _read_active_sheet_name(driver)
    return {"cell": cell, "value": value, "sheet": sheet}


from contextlib import contextmanager


@contextmanager
def _excel_frame(driver):
    """Switch into the Excel Online workbook iframe if present.

    SharePoint-hosted workbooks embed Excel Online in an iframe whose name
    starts with `WacFrame_Excel_` or whose src points at officeapps.live.com.
    Inside the iframe live the sheet-tab strip, formula bar, Name Box, and
    keyboard-focused cell. Top-frame queries miss them all.
    """
    switched = False
    try:
        from selenium.webdriver.common.by import By

        candidates = [
            "iframe[name^='WacFrame_Excel']",
            "iframe[name*='WacFrame_Excel']",
            "iframe[id^='WacFrame_Excel']",
            "iframe[src*='officeapps.live.com']",
            "iframe[src*='/_layouts/15/Doc']",
        ]
        for css in candidates:
            try:
                frame = driver.find_element(By.CSS_SELECTOR, css)
            except Exception:
                continue
            try:
                driver.switch_to.frame(frame)
                switched = True
                break
            except Exception:
                continue
        yield
    finally:
        if switched:
            try:
                driver.switch_to.default_content()
            except Exception:
                pass


def goto_cell(driver, cell: str) -> None:
    """Type a cell reference into the Name Box and press Enter."""
    with _excel_frame(driver):
        _goto_cell_inner(driver, cell)


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


def upload_workbook(driver, file_path: str) -> dict[str, Any]:
    """Upload a local .xlsx to Excel Online via the hidden file input.

    Navigates to Excel home, clicks the 'Upload a file' tile to expose the
    `<input type=file>`, then sends the absolute path to it. Excel Online
    redirects to the freshly-opened workbook URL once the upload completes.
    """
    import os
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    abs_path = os.path.abspath(os.path.expanduser(file_path))
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(f"file not found: {abs_path}")
    if not abs_path.lower().endswith((".xlsx", ".xls", ".xlsm", ".csv")):
        raise ValueError(
            f"unsupported file type: {abs_path} (expected .xlsx/.xls/.xlsm/.csv)"
        )

    driver.get(EXCEL_HOME)

    def _has_upload_tile(d) -> bool:
        try:
            return d.execute_script(
                "return /upload\\s+a\\s+file/i.test(document.body.innerText || '');"
            )
        except Exception:
            return False

    try:
        WebDriverWait(driver, 12).until(_has_upload_tile)
    except Exception:
        pass

    # Click the upload tile so Excel mounts the hidden <input type=file>.
    try:
        driver.execute_script(
            """
            const labels = ['Upload a file', 'Upload'];
            const candidates = Array.from(document.querySelectorAll('button, a, [role="button"]'));
            for (const el of candidates) {
                const text = (el.innerText || '').trim();
                if (labels.some(l => text === l || text.indexOf(l) === 0)) {
                    el.scrollIntoView({block: 'center'});
                    el.click();
                    return true;
                }
            }
            return false;
            """
        )
    except Exception:
        pass

    # Some builds expose <input type=file> immediately on home; if not, the
    # tile-click above mounts it. Force it visible so send_keys is accepted.
    try:
        driver.execute_script(
            """
            const inp = document.querySelector('input[type=file]');
            if (!inp) return false;
            inp.style.display = 'block';
            inp.style.visibility = 'visible';
            inp.style.opacity = '1';
            inp.style.position = 'fixed';
            inp.style.left = '0px';
            inp.style.top = '0px';
            inp.style.width = '500px';
            inp.style.height = '40px';
            inp.style.zIndex = '2147483647';
            return true;
            """
        )
    except Exception:
        pass

    try:
        file_input = driver.find_element(By.CSS_SELECTOR, "input[type=file]")
    except Exception:
        raise RuntimeError(
            "could not locate the Excel upload input — UI may have changed; "
            "fall back to opening Excel home manually and dragging the file in"
        )

    file_input.send_keys(abs_path)

    # Excel routes to /edit.aspx or officeapps.live.com after upload.
    try:
        WebDriverWait(driver, 60).until(
            lambda d: "officeapps.live.com" in (d.current_url or "")
            or "/edit.aspx" in (d.current_url or "")
            or "/view.aspx" in (d.current_url or "")
        )
    except Exception:
        pass

    return {
        "url": driver.current_url,
        "title": driver.title,
        "uploaded": abs_path,
    }


def create_blank_workbook(driver) -> dict[str, Any]:
    """Navigate to Excel home and click the Blank workbook tile."""
    driver.get(EXCEL_HOME)
    from selenium.webdriver.support.ui import WebDriverWait

    def _has_tile(d) -> bool:
        try:
            return d.execute_script(
                "return /create\\s+blank\\s+workbook|blank workbook/i.test("
                "document.body.innerText || '');"
            )
        except Exception:
            return False

    try:
        WebDriverWait(driver, 12).until(_has_tile)
    except Exception:
        pass

    clicked = False
    try:
        clicked = bool(driver.execute_script(
            """
            const labels = ['Create blank workbook', 'Blank workbook'];
            const candidates = Array.from(document.querySelectorAll('button, a, [role="button"]'));
            for (const el of candidates) {
                const text = (el.innerText || el.textContent || '').trim();
                const aria = (el.getAttribute('aria-label') || '').trim();
                if (labels.some(l => text === l || aria === l || text.indexOf(l) === 0 || aria.indexOf(l) === 0)) {
                    el.scrollIntoView({block: 'center'});
                    el.click();
                    return true;
                }
            }
            return false;
            """
        ))
    except Exception:
        clicked = False

    if not clicked:
        raise RuntimeError("could not find 'Blank workbook' tile on Excel home")

    try:
        WebDriverWait(driver, 20).until(
            lambda d: "officeapps.live.com" in (d.current_url or "")
            or "/edit.aspx" in (d.current_url or "")
            or "/view.aspx" in (d.current_url or "")
        )
    except Exception:
        pass
    return {"url": driver.current_url, "title": driver.title}


def write_cell(driver, cell: str, value: str) -> dict[str, Any]:
    """Navigate to a cell and type a value, finishing with Enter."""
    with _excel_frame(driver):
        _goto_cell_inner(driver, cell)
        from selenium.webdriver.common.action_chains import ActionChains
        from selenium.webdriver.common.keys import Keys
        actions = ActionChains(driver)
        actions.send_keys(value)
        actions.send_keys(Keys.ENTER)
        actions.perform()
    return {"cell": normalize_cell_ref(cell), "value": value}


def _goto_cell_inner(driver, cell: str) -> None:
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
    "upload_workbook",
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
