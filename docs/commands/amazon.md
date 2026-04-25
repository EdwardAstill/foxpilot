# `foxpilot amazon`

Amazon helpers: open the home page or a section, search products, dump product
details, list order history, track packages, and inspect the cart. Region-aware
URL construction (default `com.au`).

## Status

`foxpilot amazon` is a built-in Typer command branch backed by
`src/foxpilot/sites/amazon.py` and `src/foxpilot/sites/amazon_service.py`,
registered as the built-in `amazon` plugin under
`src/foxpilot/plugins/builtin/amazon/`.

## Authentication

Amazon is hostile to new-device sessions: it aggressively challenges fresh
profiles with CAPTCHAs, OTP, and "verify it's you" prompts. The recommended
mode is `--zen`, which reuses the user's already signed-in Zen browser
session.

For a `claude` profile flow:

```bash
foxpilot login https://www.amazon.com.au/
```

…and accept any verification challenges in the visible window. Cookies will
persist for subsequent hidden runs, but Amazon may still re-challenge.

Read-only commands (`search`, `product`) generally work without login.

## Region

All commands accept `--region` with values `com`, `com.au`, or `co.uk`. The
default is `com.au` (the user is Australia-based). The service layer builds
the correct host (`www.amazon.<region>`) from this flag.

## Mode Support

| Command | claude | visible | zen | headless |
|---|---:|---:|---:|---:|
| `help` | yes | yes | yes | yes |
| `open` | yes | yes | **default** | unlikely |
| `search` | yes | yes | **default** | best effort |
| `product` | yes | yes | **default** | best effort |
| `orders` | yes (after login) | yes | **default** | no |
| `track` | yes (after login) | yes | **default** | no |
| `cart` | yes (after login) | yes | **default** | no |

## Commands

### `foxpilot amazon help`
Print examples and usage.

### `foxpilot amazon open [SECTION] [--region R] [--json]`
Open a known section: `home`, `orders`, `wishlist`, `cart`. Or pass a full
Amazon URL to navigate directly.

```bash
foxpilot amazon open
foxpilot amazon open orders
foxpilot amazon open https://www.amazon.com.au/dp/B0ABC12345
```

### `foxpilot amazon search "<query>" [--limit N] [--region R] [--json]`
Search Amazon and return product cards: title, ASIN, URL, price, rating,
reviews, prime flag.

### `foxpilot amazon product <ASIN-or-URL> [--region R] [--json]`
Open a product page and dump title, ASIN, price, rating, reviews,
availability, prime flag, and feature-bullet list.

### `foxpilot amazon orders [--limit N] [--year YYYY] [--region R] [--json]`
List order history. With `--year`, filter to that year via
`?orderFilter=year-YYYY`.

### `foxpilot amazon track <order-id> [--region R] [--json]`
Open the order-details / tracking page and dump status, ETA, and carrier.

### `foxpilot amazon cart [--region R] [--json]`
Open and dump cart contents.

## JSON Shapes

`open`:
```json
{ "title": "...", "url": "https://www.amazon.com.au/", "section": "home", "region": "com.au" }
```

`search` (list):
```json
[
  {
    "title": "...",
    "asin": "B0ABC12345",
    "url": "https://www.amazon.com.au/dp/B0ABC12345",
    "price": "$29.99",
    "rating": "4.5 out of 5 stars",
    "reviews": "1,234",
    "prime": true
  }
]
```

`product`:
```json
{
  "title": "...",
  "asin": "B0ABC12345",
  "url": "...",
  "price": "$29.99",
  "rating": "...",
  "reviews": "...",
  "availability": "In stock",
  "prime": true,
  "bullets": ["...", "..."]
}
```

`orders` (list):
```json
[
  { "order_id": "123-4567890-1234567", "placed": "12 March 2025", "total": "$59.98", "items": [{"title": "..."}] }
]
```

`cart`:
```json
{ "items": [{ "title": "...", "price": "$29.99", "qty": "1" }], "subtotal": "$29.99" }
```

`track`:
```json
{ "order_id": "...", "status": "...", "eta": "...", "carrier": "...", "url": "..." }
```

## Failure Modes & Next Actions

| Failure | Likely cause | Next step |
|---|---|---|
| `unsupported region` | bad `--region` value | use `com`, `com.au`, or `co.uk` |
| `invalid ASIN` | ASIN not 10 alphanumerics | pass a 10-char ASIN or `/dp/<ASIN>` URL |
| sign-in redirect on `orders` / `cart` / `track` | session expired or claude profile fresh | rerun with `--zen`, or `foxpilot login https://www.amazon.com.au/` |
| empty search results | bot-check / CAPTCHA wall | try `--zen --visible` to solve once and retry |

## Limitations

- Selectors target known Amazon DOM hooks; markup churn is frequent. Adjust
  the helpers in `amazon_service.py` (`_find_search_cards`, `extract_product`,
  `extract_orders`, `extract_cart`, `extract_tracking`) when something stops
  working.
- No write commands yet: no add-to-cart, no buy-now, no review submission.
- Region inference from current URL is exposed via
  `parse_region_from_url` but not yet auto-wired into each command.
- `track` only consumes the order-details URL; per-shipment track pages are
  not yet drilled into.
