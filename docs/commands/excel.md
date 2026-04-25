# `foxpilot excel`

Excel Online (`excel.cloud.microsoft`) helpers: open workbooks, list sheet tabs, navigate cells, and read or write values via the Name Box and Formula Bar.

## Status

`foxpilot excel` is a built-in Typer command branch backed by `src/foxpilot/sites/excel.py` and `src/foxpilot/sites/excel_service.py`, registered as the built-in `excel` plugin under `src/foxpilot/plugins/builtin/excel/`.

## Why this works the way it does

Excel Online renders the cell grid on an HTML `<canvas>`. Cell values are not available in the DOM. The plugin reads and writes values by driving the elements that *are* DOM-backed:

- The **Name Box** (top-left cell-reference input) — used to jump to any cell.
- The **Formula Bar** — shows the value of the active cell.
- The **sheet tabs** at the bottom of the workbook.
- The **file-name input** at the top of the workbook.

This means reads return whatever the formula bar shows for the active cell after navigating to it via the Name Box. Formulas come back in their entered form (`=SUM(A1:A5)`), not their evaluated number; the displayed cell value is on canvas.

## Authentication

Sign into `https://excel.cloud.microsoft/` once in the foxpilot browser. Session cookies persist in the claude profile across runs.

```bash
foxpilot login https://excel.cloud.microsoft/
```

`--zen` reuses the user's real Zen browser session if you already have Excel signed-in there.

## Mode Support

| Command | claude | visible | zen | headless |
|---|---:|---:|---:|---:|
| `help` | yes | yes | yes | yes |
| `open` | yes | yes | yes | unlikely (auth) |
| `sheets` | yes | yes | yes | unlikely |
| `active` | yes | yes | yes | unlikely |
| `goto` | yes | yes | yes | unlikely |
| `read` | yes | yes | yes | unlikely |
| `write` | yes | yes | yes | unlikely |

## Commands

### `foxpilot excel help`
Shows command examples.

### `foxpilot excel open [URL]`
Opens Excel home, or a specific workbook URL if provided.

```bash
foxpilot excel open
foxpilot excel open "https://excel.cloud.microsoft/x/..."
```

### `foxpilot excel sheets [--json]`
List sheet tabs in the currently open workbook with the active tab marked.

### `foxpilot excel active [--json]`
Report the currently active cell reference + formula-bar value + sheet name.

### `foxpilot excel goto <CELL> [--json]`
Type a cell reference into the Name Box and press Enter.

```bash
foxpilot excel goto B7
foxpilot excel goto A1:C5
```

### `foxpilot excel read <CELL> [--json]`
Navigate to `<CELL>` and return the formula-bar value.

### `foxpilot excel write <CELL> <VALUE> [--json]`
Navigate to `<CELL>`, type `<VALUE>`, and press Enter. Formulas may be passed verbatim:

```bash
foxpilot excel write B7 "hello"
foxpilot excel write D2 "=SUM(A2:C2)"
```

### `foxpilot excel new [--json]`
Open Excel home and click the **Blank workbook** tile.

### `foxpilot excel select <RANGE> [--json]`
Select a single cell or a range via the Name Box. Same as `goto` but intended for ranges.

### `foxpilot excel fill-down <RANGE> [--json]`
Select `<RANGE>` and apply `Ctrl+D` — Excel copies the top cell of the range down with relative refs.

```bash
foxpilot excel write A1 "=B1*2"
foxpilot excel fill-down A1:A20
```

### `foxpilot excel fill-right <RANGE> [--json]`
Select `<RANGE>` and apply `Ctrl+R` — Excel copies the leftmost cell across.

### `foxpilot excel name <RANGE> <NAME> [--json]`
Select `<RANGE>` then type `<NAME>` into the Name Box and press Enter. Excel treats this as **define a named range** because `<NAME>` is not a valid cell reference.

```bash
foxpilot excel name B2:B20 Revenue
foxpilot excel write D2 "=SUM(Revenue)"
```

Name rules: must start with letter or underscore, no spaces, only letters/digits/`_`/`.`, must not collide with a cell reference (`A1`, `R1C1`, etc.).

### `foxpilot excel names [--json]`
Open the Name Box dropdown and list defined names. Best effort — selectors may need tuning if Excel changes the dropdown markup.

## JSON Shapes

`open`:
```json
{ "title": "...", "url": "https://...", "workbook": "Book 1" }
```

`sheets`:
```json
[ { "name": "Sheet1", "active": true }, { "name": "Sheet2", "active": false } ]
```

`active` / `read` / `goto`:
```json
{ "cell": "B7", "value": "hello", "sheet": "Sheet1" }
```

`write`:
```json
{ "cell": "B7", "value": "hello" }
```

## Failure Modes & Next Actions

| Failure | Likely cause | Next step |
|---|---|---|
| `could not find the Name Box` | No workbook open, or Excel still loading | run `foxpilot excel open <url>` and retry; try `--visible` |
| `invalid cell reference` | Bad input | use `A1` / `B7` / `A1:C5` form |
| Empty `value` from `read` | Cell is empty, or formula bar not yet rendered | retry after a short delay; check the active sheet |
| Sheet tabs empty | Workbook still loading | wait, then re-run `sheets` |

## Limitations

- Cannot read evaluated formula results — only what the formula bar shows.
- Bulk range read is not yet implemented; loop over single cells if needed.
- `names` reads the Name Box dropdown; the official Name Manager dialog is not driven yet.
- The "drag" cell-fill handle on canvas is not used — `fill-down` / `fill-right` use the keyboard equivalents instead.
- Selectors target known DOM hooks; if Excel Online changes its markup, update `extract_sheet_tabs`, `_find_name_box`, `_read_formula_bar_value`, and `create_blank_workbook` in `excel_service.py`.
