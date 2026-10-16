"""Turn page content (HTML, JSON-LD, captured JSON, card text) into Vehicle records.

Three extractors, tried together and merged:
  1. JSON-LD (schema.org Car/Vehicle/Product) - common on dealer sites.
  2. Any JSON the page loaded or embedded (XHR responses, __NEXT_DATA__ etc.),
     searched for dicts that look like a listing. This is how CarGurus-style
     single-page apps are handled.
  3. Visible card text parsed with regexes - the fallback for plain HTML.
"""
from __future__ import annotations

import json
import re
from html import unescape

from .models import Vehicle

# Multi-word makes must come before their single-word prefixes.
MAKES = [
    "Alfa Romeo", "Aston Martin", "Land Rover", "Mercedes-Benz", "Mercedes Benz", "Rolls-Royce",
    "Acura", "Audi", "BMW", "Buick", "Cadillac", "Chevrolet", "Chevy", "Chrysler", "Dodge",
    "Fiat", "FIAT", "Ford", "Genesis", "GMC", "Honda", "Hyundai", "INFINITI", "Infiniti", "Jaguar",
    "Jeep", "Kia", "Lexus", "Lincoln", "Lucid", "Maserati", "Mazda", "MINI", "Mini", "Mitsubishi",
    "Nissan", "Polestar", "Porsche", "Ram", "RAM", "Rivian", "Scion", "Subaru", "Tesla", "Toyota",
    "Volkswagen", "VW", "Volvo", "Bentley", "Ferrari", "Lamborghini", "McLaren", "Saab", "Pontiac",
    "Saturn", "Mercury", "Hummer", "Smart", "Suzuki", "Isuzu",
]
# Models whose name is more than one token; everything else is assumed one token.
MULTIWORD_MODELS = [
    "Grand Cherokee L", "Grand Cherokee", "Grand Caravan", "Grand Wagoneer", "Town & Country",
    "Range Rover Sport", "Range Rover Velar", "Range Rover Evoque", "Range Rover", "Santa Fe",
    "Santa Cruz", "Model 3", "Model S", "Model X", "Model Y", "Crown Victoria", "Monte Carlo",
    "Grand Prix", "Grand Marquis", "PT Cruiser", "Land Cruiser", "Sierra 1500", "Sierra 2500HD",
    "Silverado 1500", "Silverado 2500HD", "Ram 1500", "1500 Classic", "Super Duty", "Transit Connect",
    "Mustang Mach-E", "Bronco Sport", "Corolla Cross", "Grand Highlander", "C-HR", "Outlander Sport",
    "Eclipse Cross", "Rogue Sport", "Wrangler Unlimited", "Discovery Sport", "Ioniq 5", "Ioniq 6",
    "3 Series", "4 Series", "5 Series", "7 Series", "2 Series", "8 Series", "X5 M", "Mazda3", "Mazda6",
    "CX-5", "CX-30", "CX-50", "CX-9", "CX-90", "Sportage Hybrid", "Prius Prime", "Express 2500",
]
MAKE_CANON = {"chevy": "Chevrolet", "vw": "Volkswagen", "mercedes benz": "Mercedes-Benz",
              "fiat": "FIAT", "infiniti": "INFINITI", "mini": "MINI", "ram": "Ram"}

YEAR_RE = re.compile(r"\b(19[89]\d|20[0-4]\d)\b")
TITLE_RE = re.compile(r"\b((?:19[89]|20[0-4])\d)\s+(" + "|".join(re.escape(m) for m in MAKES) + r")\b\s*(.*)", re.I)
MONEY_RE = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})+|\d{3,7})(?:\.\d{2})?(?!\d)")
MILES_RE = re.compile(r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(k)?\s*(?:mi\b|mi\.|miles\b|mileage\b)", re.I)
MILES_LABEL_RE = re.compile(r"(?:mileage|odometer|miles)\s*[:\-]?\s*(\d{1,3}(?:,\d{3})+|\d+)", re.I)
DAYS_RES = [
    re.compile(r"(\d{1,4})\s*\+?\s*days?\s+(?:on\s+(?:market|lot|cargurus|site)|at\s+(?:this\s+)?dealer(?:ship)?|in\s+(?:stock|inventory)|listed)", re.I),
    re.compile(r"(?:listed|posted|added|in stock|on lot)\s+(?:for\s+)?(\d{1,4})\s*days?(?:\s+ago)?", re.I),
    re.compile(r"days?\s+(?:on\s+(?:market|lot)|in\s+(?:stock|inventory))\s*[:\-]?\s*(\d{1,4})", re.I),
]
VIN_RE = re.compile(r"\b([A-HJ-NPR-Z0-9]{17})\b")
MONTHLY_RE = re.compile(r"^\s*(?:/\s*mo|per\s+month|/month|mo\b|a month|est\.?\s*/mo)", re.I)
NON_PRICE_AFTER_RE = re.compile(r"^\s*(?:below|above|off|savings|less|under|over|cash back|rebate|down)", re.I)
NON_PRICE_BEFORE_RE = re.compile(r"(?:save|savings|you save|discount|rebate|down payment|msrp|was|retail|imv|market value|est\.?|estimated|below|above)\W*$", re.I)


# ---------------------------------------------------------------- normalizers

def to_int(value) -> int | None:
    """Parse '$18,995', '18995.00', 45000, {'value': 1}, '45K' -> int; else None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, dict):
        for k in ("value", "amount", "price", "raw", "number"):
            if k in value:
                return to_int(value[k])
        return None
    if isinstance(value, (int, float)):
        return int(round(value)) if value == value else None  # NaN guard
    s = str(value).strip().replace(" ", " ")
    m = re.search(r"(\d[\d,]*(?:\.\d+)?)\s*([kK])?\b", s)
    if not m:
        return None
    try:
        n = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    if m.group(2):
        n *= 1000
    return int(round(n))


def clean_str(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        value = value.get("name") or value.get("value") or value.get("label")
        if value is None:
            return None
    s = re.sub(r"\s+", " ", unescape(str(value))).strip()
    return s or None


def canon_make(make: str | None) -> str | None:
    if not make:
        return None
    return MAKE_CANON.get(make.lower(), make if not make.islower() else make.title())


def plausible(v: Vehicle) -> bool:
    if v.price is not None and not (500 <= v.price <= 2_000_000):
        v.price = None
    if v.mileage is not None and not (0 <= v.mileage <= 1_000_000):
        v.mileage = None
    if v.year is not None and not (1980 <= v.year <= 2049):
        v.year = None
    if v.days_on_lot is not None and not (0 <= v.days_on_lot <= 3650):
        v.days_on_lot = None
    # Need at least something identifying plus a number to be worth keeping.
    has_identity = v.make or v.model or v.title
    return bool(has_identity and (v.price is not None or v.mileage is not None or v.year is not None))


def split_title(title: str) -> dict:
    """'2019 Honda Civic EX Sedan' -> {year, make, model, trim}."""
    out: dict = {}
    if not title:
        return out
    m = TITLE_RE.search(title)
    if not m:
        y = YEAR_RE.search(title)
        if y:
            out["year"] = int(y.group(1))
        return out
    out["year"] = int(m.group(1))
    out["make"] = canon_make(next(mk for mk in MAKES if mk.lower() == m.group(2).lower()))
    rest = m.group(3).strip()
    # Stop the title at the first line break / separator so card noise isn't swallowed as trim.
    rest = re.split(r"\s*(?:\n|\||•|·| - |\$)", rest)[0].strip()
    if not rest:
        return out
    for mm in MULTIWORD_MODELS:
        if rest.lower().startswith(mm.lower()) and (len(rest) == len(mm) or not rest[len(mm)].isalnum()):
            out["model"] = rest[:len(mm)]
            trim = rest[len(mm):].strip(" ,-")
            break
    else:
        parts = rest.split(None, 1)
        out["model"] = parts[0]
        trim = parts[1].strip(" ,-") if len(parts) > 1 else ""
    if trim:
        out["trim"] = trim[:80]
    return out


def pick_price(text: str) -> int | None:
    """First dollar amount that isn't a monthly payment, discount or reference value."""
    for m in MONEY_RE.finditer(text):
        n = to_int(m.group(1))
        if n is None or n < 500:
            continue
        after = text[m.end():m.end() + 20]
        before = text[max(0, m.start() - 25):m.start()]
        if MONTHLY_RE.match(after) or NON_PRICE_AFTER_RE.match(after) or NON_PRICE_BEFORE_RE.search(before):
            continue
        return n
    return None


def pick_mileage(text: str) -> int | None:
    for m in MILES_RE.finditer(text):
        # Skip "mpg"-ish or range phrases like "within 50 miles"
        before = text[max(0, m.start() - 12):m.start()].lower()
        if "within" in before or "away" in text[m.end():m.end() + 6].lower():
            continue
        n = float(m.group(1).replace(",", ""))
        if m.group(2):
            n *= 1000
        return int(n)
    m = MILES_LABEL_RE.search(text)
    return to_int(m.group(1)) if m else None


def pick_days(text: str) -> int | None:
    for rx in DAYS_RES:
        m = rx.search(text)
        if m:
            return int(m.group(1))
    if re.search(r"\b(?:listed|added)\s+today\b|\bnew arrival\b|\bjust arrived\b", text, re.I):
        return 0
    return None


# ------------------------------------------------------------- JSON extractor

ALIASES = {
    "price": ["price", "listPrice", "askingPrice", "internetPrice", "salePrice", "sellingPrice",
              "finalPrice", "displayPrice", "priceValue", "currentPrice", "retailPrice", "offerPrice"],
    "mileage": ["mileage", "odometer", "miles", "mileageValue", "odometerReading", "mileageFromOdometer"],
    "year": ["year", "carYear", "modelYear", "vehicleModelDate", "modelDate"],
    "make": ["make", "makeName", "brand", "manufacturer", "makeDisplayName"],
    "model": ["model", "modelName", "modelDisplayName"],
    "trim": ["trim", "trimName", "trimLevel", "vehicleConfiguration", "series", "style"],
    "days_on_lot": ["daysOnMarket", "daysOnLot", "daysInInventory", "daysInStock", "dom",
                    "daysListed", "daysAtDealership", "daysOnSite", "ageInDays", "inventoryAge"],
    "vin": ["vin", "VIN", "vehicleIdentificationNumber"],
    "url": ["url", "vdpUrl", "detailUrl", "listingUrl", "link", "href", "permalink"],
    "title": ["title", "name", "listingTitle", "heading", "displayName"],
    "site_market_value": ["expectedPrice", "marketValue", "imv", "instantMarketValue", "marketPrice",
                          "fairMarketValue", "estimatedMarketValue", "priceEstimate"],
}
_ALIAS_LOOKUP = {a.lower(): f for f, names in ALIASES.items() for a in names}


def _fields_of(d: dict) -> dict:
    found: dict = {}
    for k, val in d.items():
        f = _ALIAS_LOOKUP.get(str(k).lower())
        if f and f not in found and val not in (None, "", [], {}):
            found[f] = val
    return found


def _looks_like_listing(found: dict) -> bool:
    has_num = "price" in found or "mileage" in found
    has_car = ("year" in found and ("make" in found or "model" in found or "title" in found)) or \
              ("make" in found and "model" in found) or "vin" in found
    return has_num and has_car


def _vehicle_from_fields(found: dict, how: str, base_url: str | None) -> Vehicle:
    v = Vehicle(extraction=how)
    v.price = to_int(found.get("price"))
    if isinstance(found.get("price"), dict) and v.price is None:
        v.price = to_int(found["price"].get("amount"))
    v.mileage = to_int(found.get("mileage"))
    v.year = to_int(found.get("year"))
    v.make = canon_make(clean_str(found.get("make")))
    v.model = clean_str(found.get("model"))
    v.trim = clean_str(found.get("trim"))
    v.days_on_lot = to_int(found.get("days_on_lot"))
    v.vin = clean_str(found.get("vin"))
    if v.vin and not VIN_RE.fullmatch(v.vin.upper()):
        v.vin = None
    v.title = clean_str(found.get("title"))
    v.site_market_value = to_int(found.get("site_market_value"))
    url = clean_str(found.get("url"))
    if url and base_url and not url.startswith("http"):
        from urllib.parse import urljoin
        url = urljoin(base_url, url)
    v.url = url if url and url.startswith("http") else None
    if v.title and None in (v.year, v.make, v.model, v.trim):
        for k, val in split_title(v.title).items():
            if getattr(v, k) is None:
                setattr(v, k, val)
    return v


def from_json(obj, how: str = "json", base_url: str | None = None, _depth: int = 0) -> list[Vehicle]:
    """Recursively find listing-like dicts anywhere inside a JSON value."""
    out: list[Vehicle] = []
    if _depth > 40:
        return out
    if isinstance(obj, dict):
        found = _fields_of(obj)
        if _looks_like_listing(found):
            out.append(_vehicle_from_fields(found, how, base_url))
            return out  # don't descend into a matched listing's sub-objects
        for val in obj.values():
            out.extend(from_json(val, how, base_url, _depth + 1))
    elif isinstance(obj, list):
        for item in obj:
            out.extend(from_json(item, how, base_url, _depth + 1))
    return out


# ---------------------------------------------------------- JSON-LD extractor

LD_TYPES = {"car", "vehicle", "product", "motorizedbicycle", "individualproduct"}


def _ld_vehicle(node: dict, base_url: str | None) -> Vehicle | None:
    offers = node.get("offers")
    if isinstance(offers, list):
        offers = offers[0] if offers else None
    found = {
        "price": (offers or {}).get("price") if isinstance(offers, dict) else None,
        "mileage": node.get("mileageFromOdometer"),
        "year": node.get("vehicleModelDate") or node.get("modelDate") or node.get("productionDate"),
        "make": node.get("brand") or node.get("manufacturer"),
        "model": node.get("model"),
        "trim": node.get("vehicleConfiguration") or node.get("trim"),
        "vin": node.get("vehicleIdentificationNumber") or node.get("sku"),
        "url": node.get("url") or ((offers or {}).get("url") if isinstance(offers, dict) else None),
        "title": node.get("name"),
    }
    found = {k: v for k, v in found.items() if v not in (None, "")}
    if not _looks_like_listing(found) and not ("title" in found and ("price" in found or "mileage" in found)):
        return None
    return _vehicle_from_fields(found, "json-ld", base_url)


def _walk_ld(node, base_url, out):
    if isinstance(node, list):
        for n in node:
            _walk_ld(n, base_url, out)
        return
    if not isinstance(node, dict):
        return
    types = node.get("@type")
    types = [types] if isinstance(types, str) else (types or [])
    if any(str(t).lower() in LD_TYPES for t in types):
        v = _ld_vehicle(node, base_url)
        if v:
            out.append(v)
            return
    for key in ("@graph", "itemListElement", "item", "mainEntity", "offers", "itemOffered"):
        if key in node:
            _walk_ld(node[key], base_url, out)


def from_jsonld_blocks(blocks: list[str], base_url: str | None = None) -> list[Vehicle]:
    out: list[Vehicle] = []
    for raw in blocks:
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            continue
        _walk_ld(data, base_url, out)
    return out


# ------------------------------------------------------- card-text extractor

def from_card(text: str, href: str | None = None) -> Vehicle | None:
    if not text:
        return None
    text = unescape(text)
    v = Vehicle(extraction="card-text")
    # Title: the first line that reads like "YEAR MAKE MODEL ..."
    for line in text.splitlines():
        parts = split_title(line.strip())
        if "make" in parts:
            v.title = line.strip()[:160]
            for k, val in parts.items():
                setattr(v, k, val)
            break
    if v.make is None:
        return None
    flat = " ".join(text.split())
    v.price = pick_price(flat)
    v.mileage = pick_mileage(flat)
    v.days_on_lot = pick_days(flat)
    m = VIN_RE.search(flat.upper())
    if m and re.search(r"\d", m.group(1)) and re.search(r"[A-Z]", m.group(1)):
        v.vin = m.group(1)
    v.url = href if href and href.startswith("http") else None
    return v


# --------------------------------------------------------------------- merge

def merge_all(groups: list[list[Vehicle]]) -> list[Vehicle]:
    """De-duplicate across extractors; richer records win, blanks get filled."""
    by_key: dict[str, Vehicle] = {}
    loose: dict[tuple, str] = {}
    for vehicles in groups:
        for v in vehicles:
            if not plausible(v):
                continue
            k = v.key()
            # Also match on (year, make, model, price, mileage) so a JSON record
            # with a VIN merges with the card-text record without one.
            lk = (v.year, (v.make or "").lower(), (v.model or "").lower(), v.price, v.mileage)
            target = by_key.get(k) or (by_key.get(loose[lk]) if lk in loose and None not in (v.price, v.mileage) else None)
            if target is None:
                by_key[k] = v
                if None not in (v.price, v.mileage):
                    loose[lk] = k
            elif v.completeness() > target.completeness():
                v.merge(target)
                by_key[[kk for kk, vv in by_key.items() if vv is target][0]] = v
            else:
                target.merge(v)
    return list(by_key.values())
