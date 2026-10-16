"""Run with:  python -m pytest tests -q   (from the skill folder)

Unit tests need nothing but Python; the end-to-end tests need Playwright +
Chromium and serve the fixtures from a local HTTP server (no internet).
"""
import functools
import http.server
import json
import os
import sys
import threading

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

from carlist import extract, valuation  # noqa: E402
from carlist.models import Vehicle  # noqa: E402
import analyze_listings  # noqa: E402

FIX = os.path.join(HERE, "fixtures")


# ------------------------------------------------------------------ unit

def test_split_title_multiword():
    assert extract.split_title("2017 Jeep Grand Cherokee Limited 4x4") == {
        "year": 2017, "make": "Jeep", "model": "Grand Cherokee", "trim": "Limited 4x4"}
    assert extract.split_title("2021 Land Rover Range Rover Sport HSE")["model"] == "Range Rover Sport"
    assert extract.split_title("2018 Chevy Silverado 1500 LT")["make"] == "Chevrolet"


def test_price_skips_monthly_and_reference_values():
    assert extract.pick_price("Was $24,999 Sale $21,450 or $310/mo") == 21450
    assert extract.pick_price("$399/mo est. Price $18,995") == 18995
    assert extract.pick_price("Call for price") is None


def test_mileage_and_days():
    assert extract.pick_mileage("42,118 miles | AWD") == 42118
    assert extract.pick_mileage("38K mi") == 38000
    assert extract.pick_mileage("Dealer within 25 miles. 61,000 mi") == 61000
    assert extract.pick_days("74 days on market") == 74
    assert extract.pick_days("Listed 12 days ago") == 12
    assert extract.pick_days("no info") is None


def test_json_finder_handles_nested_and_cargurus_keys():
    blob = {"data": {"results": [
        {"carYear": 2019, "makeName": "Mazda", "modelName": "CX-5", "trimName": "Touring",
         "mileage": {"value": 51000}, "price": "$17,400", "expectedPrice": 18100, "daysOnMarket": 66},
        {"unrelated": True}]}}
    [v] = extract.from_json(blob)
    assert (v.year, v.make, v.model, v.trim, v.mileage, v.price, v.days_on_lot, v.site_market_value) == \
        (2019, "Mazda", "CX-5", "Touring", 51000, 17400, 66, 18100)


def test_missing_fields_stay_blank():
    v = extract.from_card("2016 Ford Focus SE\nCall for price")
    assert v.year == 2016 and v.price is None and v.mileage is None and v.days_on_lot is None


def _car(year, price, miles, days=None, model="Civic"):
    return Vehicle(year=year, make="Honda", model=model, price=price, mileage=miles, days_on_lot=days)


def test_internal_baseline_flags_and_negotiation_note():
    cars = [_car(2019, 18000, 40000), _car(2019, 17000, 50000), _car(2019, 16000, 60000),
            _car(2019, 18500, 45000), _car(2019, 14000, 50000, days=80)]
    valuation.assess(cars)
    cheap = cars[-1]
    assert cheap.flag == "Great" and cheap.gap_dollars < 0 and cheap.gap_pct < -6
    assert "floor-plan" in cheap.negotiation_note
    assert "internal" in cheap.why and cheap.baseline_source == "internal"


def test_unrated_when_no_peers():
    [v] = cars = [_car(2019, 15000, 50000)]
    valuation.assess(cars)
    assert v.flag == "Unrated" and v.fair_value is None


def test_comps_beat_site_value_beat_internal(tmp_path):
    comps = tmp_path / "c.csv"
    comps.write_text("year,make,model,mileage_min,mileage_max,avg_price\n2019,Honda,Civic,0,100000,20000\n")
    a = _car(2019, 17000, 50000)
    b = _car(2019, 17000, 50000, model="Accord")
    b.site_market_value = 16000
    valuation.assess([a, b], comps=valuation.load_comps(str(comps)))
    assert a.baseline_source == "comps" and a.fair_value == 20000 and a.flag == "Great"
    assert b.baseline_source == "site" and b.flag == "High"


def test_block_detection():
    from carlist.fetch import detect_block
    assert detect_block(200, "Pardon Our Interruption", "", 0)[0]
    assert detect_block(403, "", "", 0)[0]
    # A dealer page mentioning reCAPTCHA that still has listings is NOT blocked.
    assert not detect_block(200, "Used Inventory", "uses reCAPTCHA", 12)[0]


# ------------------------------------------------------------ end to end

@pytest.fixture(scope="module")
def server():
    pytest.importorskip("playwright")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=FIX)
    handler.log_message = lambda *a: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _run(tmp_path, *args):
    out = tmp_path / "out.csv"
    code = analyze_listings.main([*args, "--delay", "0", "--out", str(out), "--json"])
    return code, json.loads((tmp_path / "out.json").read_text()), out


def test_e2e_dealer_pagination(server, tmp_path):
    code, res, csv_path = _run(tmp_path, f"{server}/dealer_p1.html")
    assert code == 0 and res["status"] == "ok"
    assert res["pages_visited"] == 3 and res["listings_found"] == 11
    prices = [v["price"] for v in res["vehicles"] if v["price"] is not None]
    assert prices == sorted(prices) and prices[0] == 14200   # "Was $99,999" ignored
    assert res["vehicles"][-1]["price"] is None              # unpriced car sorted last
    assert csv_path.read_text().startswith("price,year,make,model,trim,mileage,days_on_lot")


def test_e2e_spa_xhr_and_button_pagination(server, tmp_path):
    code, res, _ = _run(tmp_path, f"{server}/cargurus_like.html", "--max-price", "15000")
    assert res["listings_found"] == 14 and res["pages_visited"] == 2
    assert all(v["price"] <= 15000 for v in res["vehicles"])
    assert res["baseline_sources"].get("site")


def test_e2e_blocked(server, tmp_path):
    code, res, _ = _run(tmp_path, f"{server}/blocked.html")
    assert code == 2 and res["status"] == "blocked" and res["blocked"]


def test_e2e_saved_html(tmp_path):
    pytest.importorskip("playwright")
    code, res, _ = _run(tmp_path, "--html-file", os.path.join(FIX, "dealer_p1.html"),
                        "--html-file", os.path.join(FIX, "jsonld.html"))
    assert res["status"] == "ok" and res["listings_found"] == 6
