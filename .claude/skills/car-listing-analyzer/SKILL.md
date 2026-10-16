---
name: car-listing-analyzer
description: Fetches a used-car inventory page (a dealer website or a CarGurus search-results URL) with headless Chromium, extracts every vehicle across all pages (year, make, model, trim, mileage, price, days on lot), estimates a fair market value for each car, and flags it Great / Fair / High with the dollar and percent gap and a negotiation note for cars 60+ days on the lot. Outputs a price-sorted table, a CSV and structured JSON. Use when the user shares a car-dealer or CarGurus listing URL (or a saved listing page) and wants the inventory pulled, filtered by price or make/model, compared, or checked for good deals.
---

# Car Listing Analyzer

Turns a used-car inventory URL into a clean, price-sorted list with a deal
rating for every car and the reasoning behind it.

## When to use

- The user gives a dealer inventory URL or a CarGurus search URL and asks what's
  there, what's cheapest, or which cars are good deals.
- The user wants listings filtered (max price, make, model) or exported to CSV.
- The user saved a listing page from their browser (`.html`) because the site
  blocks bots, and wants it analyzed.

Don't use it for a single-car detail page valuation with no inventory, or for
new-car pricing.

## Inputs

| Input | Flag | Required |
|---|---|---|
| Inventory / search-results URL | positional `url` | yes, unless `--html-file` |
| Max price | `--max-price 25000` | no |
| Make filter (exact, case-insensitive) | `--make Honda` | no |
| Model filter (substring of model/trim/title) | `--model "CR-V"` | no |
| Comparable-price lookup CSV | `--comps file.csv` | no |
| Saved HTML page(s) instead of fetching | `--html-file page.html` (repeatable) | no |

Other knobs: `--max-pages` (20), `--band` (±% counted as Fair, default 6),
`--internal-method adjusted|ppm`, `--ignore-site-value`, `--delay`, `--timeout`, `--out`.

## How to run

First run only, install dependencies (from this skill's folder):

```bash
pip install -r requirements.txt && python -m playwright install chromium
```

Then:

```bash
python scripts/analyze_listings.py "<URL>" [--max-price N] [--make X] [--model Y] --json
```

Use `--json` when you (Claude) need to read the result; omit it to get a
readable summary + markdown table. Either way a CSV and a JSON file are
written (paths are in the output: `csv_path`, `json_path`).

## Reading the result

Top-level JSON fields:

- `status`: `ok` | `partial` (stopped mid-way, data so far is kept) | `blocked` |
  `unreachable` | `no_listings` | `error`
- `message`: plain-English explanation when status isn't `ok`
- `blocked`, `block_vendor`: set when the site served a bot challenge
- `listings_found`, `listings_after_filters`, `pages_visited`, `filtered_out`
- `flag_counts`, `baseline_sources`
- `vehicles`: sorted by price low-to-high (unpriced cars last). Each has
  `price, year, make, model, trim, mileage, days_on_lot, fair_value,
  gap_dollars, gap_pct, flag, negotiation_note, why, baseline_source, vin, url, title`.
  Missing values are `null` (blank in the CSV).

## What to tell the user

1. Always state how many listings were found and how many pages were read.
2. If `status` is `blocked`: say plainly that the site blocked automated access
   (name `block_vendor`), that this tool does not bypass bot protection, and offer
   the workaround: open the page in their own browser, *Save Page As → Webpage,
   Complete* for each results page, then rerun with `--html-file`.
3. If `unreachable`: the host could not be reached from this environment (often a
   network allow-list in sandboxed/cloud runtimes). Suggest running locally.
4. Present the table sorted by price with fair value, gap $ / %, and flag. Quote
   the `why` text for the cars worth attention so the rating is explainable, and
   mention every `negotiation_note` (60+ days on lot).
5. Be clear about which baseline was used. `internal` means "relative to the other
   cars on this page", not true market value. Recommend a `--comps` file when the
   user wants real market comparisons. See `references/methodology.md`.

## Files

- `scripts/analyze_listings.py`: CLI entry point
- `scripts/carlist/fetch.py`: Playwright loading, pagination, block detection
- `scripts/carlist/extract.py`: JSON-LD / page-JSON / card-text extraction
- `scripts/carlist/valuation.py`: fair value + flags
- `references/methodology.md`: how values and flags are computed, limits
- `references/comps_template.csv`: format for the optional lookup file
- `tests/`: offline fixtures + pytest suite (`python -m pytest tests -q`)
