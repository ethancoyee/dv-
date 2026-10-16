#!/usr/bin/env python3
"""Fetch a dealer / CarGurus inventory page, extract every vehicle, and rate each deal.

Examples:
  python analyze_listings.py "https://dealer.example.com/used-inventory/" --max-price 25000
  python analyze_listings.py "<cargurus search url>" --make Honda --model Civic --comps comps.csv
  python analyze_listings.py --html-file saved_page1.html --html-file saved_page2.html

Always prints a human-readable summary + markdown table, writes a CSV and a
JSON file, and (with --json) prints the JSON result to stdout instead.
It never raises: failures are reported in the "status" / "message" fields.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from carlist import fetch as fetcher  # noqa: E402
from carlist import valuation  # noqa: E402
from carlist.models import OUTPUT_FIELDS, Vehicle  # noqa: E402


def apply_filters(vehicles: list[Vehicle], max_price, make, model) -> tuple[list[Vehicle], dict]:
    dropped = {"over_max_price": 0, "no_price_with_max_price": 0, "make_mismatch": 0, "model_mismatch": 0}
    out = []
    for v in vehicles:
        if max_price is not None:
            if v.price is None:
                dropped["no_price_with_max_price"] += 1
                continue
            if v.price > max_price:
                dropped["over_max_price"] += 1
                continue
        if make and (v.make or "").lower().replace("-", " ") != make.lower().replace("-", " "):
            dropped["make_mismatch"] += 1
            continue
        if model and model.lower() not in f"{v.model or ''} {v.trim or ''} {v.title or ''}".lower():
            dropped["model_mismatch"] += 1
            continue
        out.append(v)
    return out, {k: n for k, n in dropped.items() if n}


def markdown_table(vehicles: list[Vehicle]) -> str:
    cols = ["#", "Price", "Year", "Make", "Model", "Trim", "Miles", "Days", "Fair value", "Gap $", "Gap %", "Flag", "Note"]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    money = lambda n: f"${n:,}" if n is not None else ""  # noqa: E731
    for i, v in enumerate(vehicles, 1):
        gap = "" if v.gap_dollars is None else f"{'+' if v.gap_dollars > 0 else '-'}${abs(v.gap_dollars):,}"
        pct = "" if v.gap_pct is None else f"{v.gap_pct:+.1f}%"
        note = "60+ days: negotiate" if v.negotiation_note else ""
        row = [str(i), money(v.price), str(v.year or ""), v.make or "", v.model or "", (v.trim or "")[:28],
               f"{v.mileage:,}" if v.mileage is not None else "", "" if v.days_on_lot is None else str(v.days_on_lot),
               money(v.fair_value), gap, pct, v.flag or "", note]
        lines.append("| " + " | ".join(c.replace("|", "/") for c in row) + " |")
    return "\n".join(lines)


def default_out(url: str | None) -> str:
    host = urlparse(url).hostname if url else "saved-html"
    host = re.sub(r"[^A-Za-z0-9.-]", "_", host or "listings")
    return f"car_listings_{host}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"


def run(args) -> tuple[dict, list[Vehicle]]:
    if args.html_file:
        fr = fetcher.parse_saved_html(args.html_file)
    else:
        fr = fetcher.fetch(args.url, max_pages=args.max_pages, timeout_ms=args.timeout * 1000,
                           delay_s=args.delay, headless=not args.headful)

    comps, comps_error = [], None
    if args.comps:
        try:
            comps = valuation.load_comps(args.comps)
        except OSError as e:
            comps_error = f"could not read comps file: {e}"

    # Value against the whole scraped set (more comparables), then filter.
    valuation.assess(fr.vehicles, comps=comps, method=args.internal_method, band=args.band / 100,
                     use_site_value=not args.ignore_site_value)
    kept, dropped = apply_filters(fr.vehicles, args.max_price, args.make, args.model)
    kept.sort(key=lambda v: (v.price is None, v.price or 0, v.mileage or 0))

    out_csv = args.out or default_out(args.url)
    out_json = os.path.splitext(out_csv)[0] + ".json"
    files_error = None
    try:
        os.makedirs(os.path.dirname(os.path.abspath(out_csv)), exist_ok=True)
        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
            w.writeheader()
            for v in kept:
                w.writerow({k: ("" if val is None else val) for k, val in v.to_row().items()})
    except OSError as e:
        files_error, out_csv = f"could not write CSV: {e}", None

    flags: dict = {}
    for v in kept:
        flags[v.flag] = flags.get(v.flag, 0) + 1
    sources: dict = {}
    for v in kept:
        sources[v.baseline_source or "none"] = sources.get(v.baseline_source or "none", 0) + 1

    result = {
        "status": fr.status,
        "message": fr.message,
        "blocked": fr.status in ("blocked", "partial") and fr.block_vendor is not None,
        "block_vendor": fr.block_vendor,
        "source": args.url or args.html_file,
        "pages_visited": fr.pages_visited,
        "listings_found": len(fr.vehicles),
        "listings_after_filters": len(kept),
        "filtered_out": dropped,
        "filters": {"max_price": args.max_price, "make": args.make, "model": args.model},
        "flag_counts": flags,
        "baseline_sources": sources,
        "comps_rows_loaded": len(comps),
        "warnings": [w for w in (comps_error, files_error) if w],
        "csv_path": os.path.abspath(out_csv) if out_csv else None,
        "json_path": None,
        "log": fr.log,
        "vehicles": [v.to_row() for v in kept],
    }
    try:
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        result["json_path"] = os.path.abspath(out_json)
    except OSError as e:
        result["warnings"].append(f"could not write JSON: {e}")
    return result, kept


def human_report(result: dict, kept: list[Vehicle]) -> str:
    lines = [f"Status: {result['status']}" + (f" - {result['message']}" if result["message"] else "")]
    if result["blocked"]:
        lines.append(f"BLOCKED: the site refused automated access ({result['block_vendor']}).")
    lines.append(f"Listings found: {result['listings_found']} across {result['pages_visited']} page(s); "
                 f"{result['listings_after_filters']} after filters {result['filtered_out'] or ''}".rstrip())
    if result["flag_counts"]:
        lines.append("Flags: " + ", ".join(f"{k} {n}" for k, n in sorted(result["flag_counts"].items())))
        lines.append("Baselines: " + ", ".join(f"{k} {n}" for k, n in result["baseline_sources"].items()))
    for w in result["warnings"]:
        lines.append("Warning: " + w)
    if kept:
        lines += ["", markdown_table(kept), "", "Why each car got its flag:"]
        for i, v in enumerate(kept, 1):
            lines.append(f"{i}. {v.year or ''} {v.make or ''} {v.model or ''} {v.trim or ''}".replace("  ", " ")
                         + f" - {v.flag}: {v.why}" + (f" NOTE: {v.negotiation_note}" if v.negotiation_note else ""))
    lines += ["", f"CSV:  {result['csv_path']}", f"JSON: {result['json_path']}"]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url", nargs="?", help="dealer or CarGurus inventory / search-results URL")
    ap.add_argument("--max-price", type=lambda s: int(float(s.replace("$", "").replace(",", ""))))
    ap.add_argument("--make")
    ap.add_argument("--model", help="substring match against model/trim/title, e.g. 'Civic' or 'CR-V'")
    ap.add_argument("--comps", help="CSV of comparable averages (see references/comps_template.csv)")
    ap.add_argument("--internal-method", choices=["adjusted", "ppm"], default="adjusted",
                    help="adjusted = mileage-adjusted group median (default); ppm = group median price-per-mile (literal, but over-values high-mileage cars - see references/methodology.md)")
    ap.add_argument("--band", type=float, default=6.0, help="+/- percent around fair value counted as 'Fair' (default 6)")
    ap.add_argument("--ignore-site-value", action="store_true", help="don't use the site's own market-value estimate")
    ap.add_argument("--max-pages", type=int, default=20)
    ap.add_argument("--timeout", type=int, default=45, help="per-page load timeout, seconds")
    ap.add_argument("--delay", type=float, default=1.5, help="pause between pages, seconds (be polite)")
    ap.add_argument("--headful", action="store_true", help="show the browser window (local machines only)")
    ap.add_argument("--html-file", action="append", help="analyze a saved HTML page instead of fetching (repeatable)")
    ap.add_argument("--out", help="CSV output path (JSON is written alongside)")
    ap.add_argument("--json", action="store_true", help="print the JSON result to stdout instead of the report")
    args = ap.parse_args(argv)

    if not args.url and not args.html_file:
        result, kept = {"status": "error", "message": "Provide a URL or --html-file.", "vehicles": []}, []
        print(json.dumps(result) if args.json else result["message"])
        return 2
    try:
        result, kept = run(args)
    except Exception as e:  # last-resort guard: report, never crash
        result, kept = {"status": "error", "message": f"{type(e).__name__}: {e}", "vehicles": []}, []
        print(json.dumps(result, indent=2) if args.json else f"Status: error - {result['message']}")
        return 1
    print(json.dumps(result, indent=2) if args.json else human_report(result, kept))
    return 0 if result["status"] in ("ok", "partial") else 2


if __name__ == "__main__":
    sys.exit(main())
