#!/usr/bin/env python3
"""
Live fare check: Singapore (SIN) -> London Heathrow (LHR), non-stop, economy, round trip.

Source: Google Flights, queried through SerpApi (https://serpapi.com/google-flights-api).

Rules this script follows:
  * Only numbers returned by the API are written to data/prices.json. Nothing is estimated,
    interpolated or carried forward.
  * If a search fails, the existing data is left untouched and the failure is recorded in
    `lastRun`, then the script exits non-zero so GitHub flags the run.
  * Every stored search keeps its SerpApi search id and Google Flights link so any number on
    the dashboard can be checked against the source.

Settings (environment variables, all optional except SERPAPI_KEY):
  SERPAPI_KEY            your SerpApi key (store it as a GitHub Actions secret)
  DEPARTURE_DATES        comma-separated YYYY-MM-DD, default 2027-01-16,2027-01-17
  RETURN_DATE            YYYY-MM-DD, default 2027-06-05
  FOCUS_DATE             the departure date the summary is about, default 2027-01-17
  ARRIVE_BY              the UK date you need to be in Leeds, default 2027-01-18
  PREFERRED_AIRLINE      IATA code given extra weight, default SQ
  PREFERRED_ALLOWANCE    S$ the preferred airline may cost above the cheapest and still be
                         the pick, default 150
  MONTHLY_SEARCH_BUDGET  stop searching once this many searches were made this month,
                         default 230 (SerpApi free plan is 250)
"""

import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "prices.json"
API_URL = "https://serpapi.com/search.json"
SGT = dt.timezone(dt.timedelta(hours=8))
MAX_HISTORY_ROWS = 4000


def env_list(name, default):
    return [x.strip() for x in os.environ.get(name, default).split(",") if x.strip()]


CONFIG = {
    "origin": os.environ.get("ORIGIN", "SIN"),
    "destination": os.environ.get("DESTINATION", "LHR"),
    "departures": env_list("DEPARTURE_DATES", "2027-01-16,2027-01-17"),
    "returnDate": os.environ.get("RETURN_DATE", "2027-06-05"),
    "focusDate": os.environ.get("FOCUS_DATE", "2027-01-17"),
    "arriveBy": os.environ.get("ARRIVE_BY", "2027-01-18"),
    "preferredAirline": os.environ.get("PREFERRED_AIRLINE", "SQ"),
    "preferredAllowance": int(os.environ.get("PREFERRED_ALLOWANCE", "150")),
    "currency": "SGD",
    "cabin": "Economy",
    "adults": 1,
    "stops": "Non-stop only",
    "tripType": "Round trip",
}
MONTHLY_BUDGET = int(os.environ.get("MONTHLY_SEARCH_BUDGET", "230"))


def now_sgt():
    return dt.datetime.now(SGT).replace(microsecond=0)


def load_data():
    if DATA_FILE.exists():
        with open(DATA_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("schema") == 2:
            return data
        # Older files mixed hand-entered figures with checks; start clean rather than trust them.
        print("Existing prices.json is not schema 2; starting a clean, API-only file.")
    return {
        "schema": 2,
        "source": "Google Flights via SerpApi",
        "config": {},
        "lastRun": {"status": "never"},
        "usage": {"month": None, "searches": 0},
        "latest": {},
        "history": [],
    }


def save_data(data):
    data["config"] = CONFIG
    data["history"] = data["history"][-MAX_HISTORY_ROWS:]
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = DATA_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write("\n")
    tmp.replace(DATA_FILE)


def search(date, api_key):
    params = {
        "engine": "google_flights",
        "departure_id": CONFIG["origin"],
        "arrival_id": CONFIG["destination"],
        "outbound_date": date,
        "return_date": CONFIG["returnDate"],
        "type": "1",          # round trip
        "travel_class": "1",  # economy
        "stops": "1",         # non-stop only
        "adults": "1",
        "currency": CONFIG["currency"],
        "gl": "sg",
        "hl": "en",
        "api_key": api_key,
    }
    url = API_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "flight-price-tracker/2.0"})
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"SerpApi HTTP {e.code}: {body}") from None
    if payload.get("error"):
        raise RuntimeError(f"SerpApi error: {payload['error']}")
    status = (payload.get("search_metadata") or {}).get("status")
    if status != "Success":
        raise RuntimeError(f"SerpApi search status was {status!r}")
    return payload


def minutes(value):
    return value if isinstance(value, int) and value > 0 else None


def parse_flights(payload):
    """Return non-stop options with a real price, cheapest per flight number."""
    best = {}
    for item in (payload.get("best_flights") or []) + (payload.get("other_flights") or []):
        legs = item.get("flights") or []
        price = item.get("price")
        if len(legs) != 1 or not isinstance(price, (int, float)) or price <= 0:
            continue
        leg = legs[0]
        number = (leg.get("flight_number") or "").replace(" ", "").upper()
        if len(number) < 3:
            continue
        dep = leg.get("departure_airport") or {}
        arr = leg.get("arrival_airport") or {}
        row = {
            "flightNumber": number,
            "airlineCode": number[:2],
            "airline": leg.get("airline"),
            "depAirport": dep.get("id"),
            "depTime": dep.get("time"),
            "arrAirport": arr.get("id"),
            "arrTime": arr.get("time"),
            "durationMin": minutes(leg.get("duration")),
            "aircraft": leg.get("airplane"),
            "legroom": leg.get("legroom"),
            "price": int(round(price)),
        }
        if number not in best or row["price"] < best[number]["price"]:
            best[number] = row
    return sorted(best.values(), key=lambda r: r["price"])


def parse_insights(payload):
    pi = payload.get("price_insights") or {}
    history = [
        [int(p[0]), int(p[1])]
        for p in (pi.get("price_history") or [])
        if isinstance(p, list) and len(p) == 2 and isinstance(p[1], (int, float)) and p[1] > 0
    ]
    typical = pi.get("typical_price_range")
    return {
        "lowestPrice": pi.get("lowest_price"),
        "priceLevel": pi.get("price_level"),
        "typicalRange": typical if isinstance(typical, list) and len(typical) == 2 else None,
        "history": history,
    }


def main():
    data = load_data()
    started = now_sgt()
    month = started.strftime("%Y-%m")
    usage = data.setdefault("usage", {"month": month, "searches": 0})
    if usage.get("month") != month:
        usage.update(month=month, searches=0)

    api_key = os.environ.get("SERPAPI_KEY", "").strip()
    if not api_key:
        data["lastRun"] = {
            "at": started.isoformat(),
            "status": "error",
            "message": "SERPAPI_KEY is not set. Add it under Settings > Secrets and variables > Actions.",
        }
        save_data(data)
        print("::error::SERPAPI_KEY is not set; no prices fetched.")
        return 1

    errors, fetched = [], []
    for date in CONFIG["departures"]:
        if usage["searches"] >= MONTHLY_BUDGET:
            errors.append(f"{date}: skipped, monthly search budget of {MONTHLY_BUDGET} reached")
            continue
        try:
            payload = search(date, api_key)
            usage["searches"] += 1
            flights = parse_flights(payload)
            if not flights:
                raise RuntimeError("search succeeded but returned no priced non-stop flights")
        except Exception as e:  # noqa: BLE001 - record any failure, never invent data
            errors.append(f"{date}: {e}")
            continue

        meta = payload.get("search_metadata") or {}
        previous_id = (data["latest"].get(date) or {}).get("searchId")
        fetched_at = now_sgt().isoformat()
        data["latest"][date] = {
            "fetchedAt": fetched_at,
            "searchId": meta.get("id"),
            "googleFlightsUrl": meta.get("google_flights_url"),
            "returnDate": CONFIG["returnDate"],
            "priceInsights": parse_insights(payload),
            "flights": flights,
        }
        if meta.get("id") and meta.get("id") == previous_id:
            print(f"{date}: SerpApi returned a cached result already on record; history unchanged.")
        else:
            data["history"].append({
                "t": fetched_at,
                "d": date,
                "r": CONFIG["returnDate"],
                "id": meta.get("id"),
                "p": {f["flightNumber"]: f["price"] for f in flights},
            })
        fetched.append(date)
        cheapest = flights[0]
        print(f"{date}: {len(flights)} non-stop options, cheapest {cheapest['flightNumber']} S${cheapest['price']:,}")

    status = "ok" if not errors else ("partial" if fetched else "error")
    data["lastRun"] = {
        "at": started.isoformat(),
        "status": status,
        "message": "; ".join(errors) if errors else f"Checked {', '.join(fetched)}",
    }
    save_data(data)
    for err in errors:
        print(f"::error::{err}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
