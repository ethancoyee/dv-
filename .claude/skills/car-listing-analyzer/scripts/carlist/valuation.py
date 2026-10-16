"""Fair-value estimation and Great / Fair / High deal flags.

Baseline sources, in priority order for each car:
  1. comps file   - a CSV of comparable averages you supply (year/make/model/mileage band)
  2. site value   - a market value the listing site itself published (e.g. CarGurus IMV)
  3. internal     - computed from the other cars in the scraped set
"""
from __future__ import annotations

import csv
from statistics import median

from .models import Vehicle

YEAR_ADJ = 0.08              # ~8%/model-year depreciation when borrowing neighbouring years
DEFAULT_PER_MILE = 0.004     # fallback: 0.4% of value per 1,000 miles
MIN_PEERS = 3


def _norm(s: str | None) -> str:
    return (s or "").strip().lower().replace("-", " ")


# ------------------------------------------------------------ comps (external)

def load_comps(path: str) -> list[dict]:
    """CSV columns: year,make,model,mileage_min,mileage_max,avg_price[,trim][,source]."""
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            try:
                rows.append({
                    "year": int(r["year"]), "make": _norm(r["make"]), "model": _norm(r["model"]),
                    "trim": _norm(r.get("trim")),
                    "lo": int(float(r.get("mileage_min") or 0)),
                    "hi": int(float(r.get("mileage_max") or 10_000_000)),
                    "avg": int(float(r["avg_price"])),
                    "source": (r.get("source") or "comps file").strip(),
                })
            except (KeyError, ValueError, TypeError):
                continue
    return rows


def comps_value(v: Vehicle, comps: list[dict]) -> tuple[int, str] | None:
    if not comps or v.year is None or not v.model:
        return None
    cands = [c for c in comps if c["year"] == v.year and c["model"] == _norm(v.model)
             and (not c["make"] or c["make"] == _norm(v.make))
             and (v.mileage is None or c["lo"] <= v.mileage <= c["hi"])]
    if not cands:
        return None
    exact = [c for c in cands if c["trim"] and v.trim and c["trim"] in _norm(v.trim)]
    c = (exact or [c for c in cands if not c["trim"]] or cands)[0]
    band = f"{c['lo']:,}-{c['hi']:,} mi" if c["hi"] < 10_000_000 else "any mileage"
    return c["avg"], f"{c['source']}: avg for {v.year} {v.make or ''} {v.model} {c['trim'] or ''} ({band})".replace("  ", " ")


# ----------------------------------------------------------- internal baseline

def _peers(v: Vehicle, pool: list[Vehicle]) -> tuple[list[tuple[float, int | None]], str]:
    """Other cars of the same make/model. Same year first, then +/-1 year (year-adjusted)."""
    same = [o for o in pool if o is not v and o.price and _norm(o.model) == _norm(v.model)
            and _norm(o.make) == _norm(v.make)]
    exact = [(float(o.price), o.mileage) for o in same if o.year == v.year]
    if len(exact) >= MIN_PEERS:
        return exact, f"{len(exact)} other {v.year} {v.make} {v.model}"
    if v.year is None:
        return [], ""
    near = exact + [(o.price * (1 + YEAR_ADJ) ** (v.year - o.year), o.mileage)
                    for o in same if o.year is not None and abs(o.year - v.year) == 1]
    if len(near) >= MIN_PEERS:
        return near, f"{len(near)} other {v.year - 1}-{v.year + 1} {v.make} {v.model} (year-adjusted)"
    return [], ""


def _per_mile_slope(peers: list[tuple[float, int | None]], ref_price: float) -> tuple[float, bool]:
    """Robust $/mile depreciation: median of pairwise slopes (Theil-Sen)."""
    pts = [(m, p) for p, m in peers if m is not None]
    slopes = [(p2 - p1) / (m2 - m1) for i, (m1, p1) in enumerate(pts) for (m2, p2) in pts[i + 1:]
              if abs(m2 - m1) >= 5000]
    if len(slopes) >= 3:
        s = -median(slopes)
        # Keep it in a sane range: 1%..25% of value per 10k miles.
        lo, hi = ref_price * 0.01 / 10_000, ref_price * 0.25 / 10_000
        return min(max(s, lo), hi), True
    return ref_price * DEFAULT_PER_MILE / 1000, False


def internal_value(v: Vehicle, pool: list[Vehicle], method: str) -> tuple[int, str] | None:
    if not v.model:
        return None
    peers, desc = _peers(v, pool)
    if not peers:
        return None
    if method == "ppm":
        ppm = [p / m for p, m in peers if m and m >= 1000]
        if len(ppm) < MIN_PEERS or not v.mileage or v.mileage < 1000:
            return None
        med = median(ppm)
        return int(round(med * v.mileage)), f"internal: median ${med:.3f}/mile of {desc} x {v.mileage:,} mi"
    med_price = median(p for p, _ in peers)
    miles = [m for _, m in peers if m is not None]
    if v.mileage is None or not miles:
        return int(round(med_price)), f"internal: median price of {desc} (no mileage adjustment)"
    med_miles = median(miles)
    slope, fitted = _per_mile_slope(peers, med_price)
    fair = max(med_price - slope * (v.mileage - med_miles), med_price * 0.3)
    how = "fitted" if fitted else "default"
    return int(round(fair)), (f"internal: median ${med_price:,.0f} @ {med_miles:,.0f} mi of {desc}, "
                              f"adjusted ${slope * 1000:,.0f}/1k mi ({how})")


# -------------------------------------------------------------------- flags

def negotiation_note(days: int | None) -> str | None:
    if days is None:
        return None
    if days >= 90:
        return (f"{days} days on lot: strong negotiating room - aged inventory is costing the dealer "
                "floor-plan interest and is often wholesaled soon.")
    if days >= 60:
        return f"{days} days on lot: extra negotiating room - the dealer is paying floor-plan interest on it."
    return None


def assess(vehicles: list[Vehicle], comps: list[dict] | None = None, method: str = "adjusted",
           band: float = 0.06, use_site_value: bool = True) -> None:
    """Fill fair_value, gap, flag, why, negotiation_note on each vehicle in place."""
    for v in vehicles:
        est = comps_value(v, comps or [])
        source = "comps"
        if est is None and use_site_value and v.site_market_value:
            est, source = (v.site_market_value, "listing site's own market value estimate"), "site"
        if est is None:
            est, source = internal_value(v, vehicles, method), "internal"
        v.negotiation_note = negotiation_note(v.days_on_lot)

        if est is None or v.price is None:
            v.flag = "Unrated"
            v.baseline_source = None
            v.why = ("no price listed" if v.price is None else
                     f"fewer than {MIN_PEERS} comparable cars in this set and no external baseline")
            continue
        fair, detail = est
        v.fair_value, v.baseline_source = fair, source
        v.gap_dollars = v.price - fair
        v.gap_pct = round(100 * v.gap_dollars / fair, 1) if fair else None
        pct = (v.gap_pct or 0) / 100
        v.flag = "Great" if pct <= -band else "High" if pct >= band else "Fair"
        direction = "below" if v.gap_dollars < 0 else "above"
        v.why = (f"${v.price:,} is ${abs(v.gap_dollars):,} ({abs(v.gap_pct):.1f}%) {direction} est. fair value "
                 f"${fair:,} [{detail}]")
        if v.negotiation_note and v.flag != "Great":
            v.why += "; long time on lot means the ask is likely soft"


# --------------------------------------------------------- bang-for-buck

def _pct_rank(values: list[float], x: float, higher_is_better: bool) -> float:
    """Share of the set this value beats (0..100); ties count half."""
    if len(values) < 2:
        return 50.0
    better = sum(1 for y in values if (x > y if higher_is_better else x < y))
    ties = sum(1 for y in values if y == x) - 1
    return 100.0 * (better + 0.5 * ties) / (len(values) - 1)


def value_scores(vehicles: list[Vehicle], w_price: float = 1.0, w_miles: float = 1.0,
                 w_year: float = 1.0, current_year: int | None = None) -> None:
    """Score each car 0-100 on cheap + low-mileage + newer, relative to the others.

    Each factor is a percentile rank within the set, so a 50 means "middle of
    this pack" and 90 means "better than ~90% of these cars" on the weighted mix.
    Cars missing price, mileage or year get no score.
    """
    from datetime import date
    yr = current_year or date.today().year
    rated = [v for v in vehicles if None not in (v.price, v.mileage, v.year)]
    prices = [float(v.price) for v in rated]
    miles = [float(v.mileage) for v in rated]
    years = [float(v.year) for v in rated]
    total = (w_price + w_miles + w_year) or 1.0
    for v in vehicles:
        if v.mileage is not None and v.year is not None:
            v.miles_per_year = int(round(v.mileage / max(yr - v.year + 0.5, 0.5)))
    for v in rated:
        score = (w_price * _pct_rank(prices, v.price, False)
                 + w_miles * _pct_rank(miles, v.mileage, False)
                 + w_year * _pct_rank(years, v.year, True)) / total
        v.value_score = round(score, 1)
