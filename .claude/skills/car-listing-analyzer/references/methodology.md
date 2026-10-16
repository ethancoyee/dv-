# Methodology and limits

## Extraction

Each page is loaded in headless Chromium, allowed to settle (network idle plus
scrolling for lazy-loaded cards), then three extractors run and their results
are merged and de-duplicated (VIN → URL → year/make/model/price/mileage):

1. **JSON-LD**: schema.org `Car` / `Vehicle` / `Product` blocks. Most dealer
   platforms (Dealer.com, DealerInspire, DealerOn and others) emit these.
2. **Page JSON**: every JSON response the page fetched (XHR/fetch) plus inline
   state blobs (`__NEXT_DATA__`, `window.__X__ = {...}`), searched for objects
   that look like listings (price or mileage, plus year/make/model or VIN).
   Field-name aliases cover common schemas, including CarGurus-style keys
   (`carYear`, `makeName`, `modelName`, `trimName`, `daysOnMarket`, `expectedPrice`).
3. **Card text**: the largest page element containing exactly one
   "YEAR MAKE …" headline and a dollar amount, parsed with regexes. Monthly
   payments, "was/MSRP/save" amounts and "within N miles" are skipped.

**Pagination:** `rel=next` links, "Next" / "›" / "»" links or buttons (by
aria-label, test-id, class or text), "Load more / Show more" buttons, and as a
last resort incrementing a `page=` style URL parameter. Stops when there is no
next control, a page adds no new cars, the next URL was already visited, or
`--max-pages` is reached (reported in `log`).

Site layouts change. If a site's markup defeats all three extractors you get
`status: no_listings` and an honest message, not invented data.

## Fair value: baseline sources (priority order per car)

1. **Comps file** (`--comps`): your own lookup of comparable averages by
   year / make / model / optional trim / mileage band, e.g. figures you pulled
   from KBB, Edmunds, J.D. Power or a paid API. This is the "external
   comparable average" and wins whenever a row matches.
2. **Site's own estimate**: when the listing data includes a market value
   (CarGurus publishes an "instant market value" per listing), it is used.
   Disable with `--ignore-site-value`.
3. **Internal baseline**: computed from the other cars in the scraped set.

There is no free, public, unauthenticated API for used-car market values (KBB,
Edmunds, Black Book and J.D. Power are licensed; MarketCheck and similar are
paid and need a key). That is why external values come from a file you
control, not a hard-coded service.

### Internal baseline (default `adjusted`)

- **Peers**: other cars with the same make + model and the same year
  (leave-one-out, so a car is never compared against itself). If fewer than 3,
  widen to ±1 model year, adjusting those prices ~8% per year.
- **Fair value** = peer median price − per-mile depreciation × (this car's miles −
  peer median miles).
- **Per-mile depreciation** is fitted from the peers (median of pairwise
  slopes, robust to outliers) when there are enough mileage-spread pairs,
  otherwise a default of 0.4% of value per 1,000 miles. Clamped to a sane range.
- Fewer than 3 peers: the car is `Unrated` instead of guessed.

### Why not plain price-per-mile? (`--internal-method ppm`)

The original spec was "compare each car to the median price-per-mile of its
group". That's available as `--internal-method ppm`, but it isn't the
default because price-per-mile doesn't scale linearly. Fair value = median $/mile
× miles says a 61k-mile car is worth *more* than a 42k-mile one, and a
5k-mile car is worth almost nothing. In the test fixture it rated a 61k-mile
Civic at $25.9k fair value against $18.9k for the 38k-mile Civic. The
mileage-adjusted median keeps the same "group by model and year, compare to
the group" idea and gives sensible numbers.

## Flags

`gap = price − fair value`, `gap% = gap / fair value`.

| Flag | Rule (default `--band 6`) |
|---|---|
| Great | gap% ≤ −6% |
| Fair | within ±6% |
| High | gap% ≥ +6% |
| Unrated | no price, or no baseline available |

**Days on lot:** 60+ days adds a `negotiation_note` (extra room, because the dealer is
paying floor-plan interest). 90+ days gets a stronger note (aged units are often
wholesaled soon). For a Fair or High car the `why` text also says the ask is
likely soft. The flag itself still reflects price against value, so a
High car with 100 days on the lot reads "overpriced, but very negotiable"
rather than being relabelled.

## Caveats to pass on to the user

- An internal baseline is relative to *this inventory page*. If every car on the
  page is overpriced, the least-overpriced one can still show as "Great".
- Trim, options, accident history, title status and condition are not
  modelled. A "Great" Civic LX next to EX/Sport trims may simply be the base trim.
- Days on lot is only present when the site shows it (CarGurus usually does;
  many dealer sites don't).
- Respect each site's terms of use. Keep `--delay` polite, and don't run this at
  volume against sites that forbid automated access.
