from __future__ import annotations

from dataclasses import asdict, dataclass, field

# Column order for the CSV / table output.
OUTPUT_FIELDS = [
    "price", "year", "make", "model", "trim", "mileage", "days_on_lot",
    "fair_value", "gap_dollars", "gap_pct", "flag", "negotiation_note",
    "why", "baseline_source", "vin", "url", "title",
]


@dataclass
class Vehicle:
    year: int | None = None
    make: str | None = None
    model: str | None = None
    trim: str | None = None
    mileage: int | None = None
    price: int | None = None
    days_on_lot: int | None = None
    vin: str | None = None
    url: str | None = None
    title: str | None = None
    # A market value the listing site itself publishes (e.g. CarGurus "IMV"),
    # used as an external baseline when present.
    site_market_value: int | None = None
    extraction: str | None = None  # which extractor produced this record

    # Filled in by valuation.
    fair_value: int | None = None
    gap_dollars: int | None = None
    gap_pct: float | None = None
    flag: str | None = None
    negotiation_note: str | None = None
    why: str | None = None
    baseline_source: str | None = None
    extra: dict = field(default_factory=dict)

    def key(self) -> str:
        """Identity used to de-duplicate across pages and extractors."""
        if self.vin:
            return "vin:" + self.vin.upper()
        if self.url:
            return "url:" + self.url.split("#")[0]
        return "|".join(str(x) for x in (self.year, self.make, self.model, self.trim, self.mileage, self.price))

    def completeness(self) -> int:
        return sum(v is not None for v in (self.year, self.make, self.model, self.trim,
                                           self.mileage, self.price, self.days_on_lot, self.vin))

    def merge(self, other: "Vehicle") -> None:
        """Fill blanks in self from another record of the same car."""
        for name in ("year", "make", "model", "trim", "mileage", "price", "days_on_lot",
                     "vin", "url", "title", "site_market_value"):
            if getattr(self, name) is None and getattr(other, name) is not None:
                setattr(self, name, getattr(other, name))

    def to_row(self) -> dict:
        d = asdict(self)
        return {k: d.get(k) for k in OUTPUT_FIELDS}
