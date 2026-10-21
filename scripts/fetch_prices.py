#!/usr/bin/env python3
"""
Live fare check: Singapore (SIN) to the UK (London Heathrow and Manchester), economy, round trip.

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
  RETURN_DATE            YYYY-MM-DD, default 2027-06-05
  ARRIVE_BY              the UK date you need to be in Leeds, default 2027-01-18
  PREFERRED_AIRLINE      IATA code given extra weight, default SQ
  PREFERRED_ALLOWANCE    S$ the preferred airline may cost above the cheapest and still be
                         the pick, default 150
  LHR_DEPARTURES         comma-separated dates for Heathrow, default 2027-01-16,2027-01-17
  MAN_DEPARTURES         comma-separated dates for Manchester, default 2027-01-18
  MAN_MAX_STOPS          0 = non-stop only, 1 = up to one stop (default 1; only SQ is non-stop)
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
MAX_HISTORY_ROWS = 6000
MAX_OPTIONS_PER_SEARCH = 25


def env_list(name, default):
    return [x.strip() for x in os.environ.get(name, default).split(",") if x.strip()]


def last_date(dates):
    return dates[-1] if dates else None


CONFIG = {
    "origin": "SIN",
    "returnDate": os.environ.get("RETURN_DATE", "2027-06-05"),
    "arriveBy": os.environ.get("ARRIVE_BY", "2027-01-18"),
    "preferredAirline": os.environ.get("PREFERRED_AIRLINE", "SQ"),
    "preferredAllowance": int(os.environ.get("PREFERRED_ALLOWANCE", "150")),
    "currency": "SGD",
    "cabin": "Economy",
    "adults": 1,
    "tripType": "Round trip",
}

_lhr = env_list("LHR_DEPARTURES", "2027-01-16,2027-01-17")
_man = env_list("MAN_DEPARTURES", "2027-01-18")
ROUTES = [
    {
        "id": "LHR",
        "name": "London Heathrow",
        "destination": "LHR",
        "departures": _lhr,
        "focusDate": os.environ.get("LHR_FOCUS_DATE", last_date(_lhr)),
        "maxStops": 0,
        "leedsMinutes": 275,
        "leedsNote": "75 min for immigration and bags, then the Elizabeth line or Tube to King's Cross and an LNER train to Leeds (about 4 h 35 min in total).",
    },
    {
        "id": "MAN",
        "name": "Manchester",
        "destination": "MAN",
        "departures": _man,
        "focusDate": os.environ.get("MAN_FOCUS_DATE", last_date(_man)),
        "maxStops": int(os.environ.get("MAN_MAX_STOPS", "1")),
        # Deep search matches what Google Flights shows in a browser.
        "deepSearch": True,
        # The one-stop comparison runs once a day (09:00 SGT check) to stay inside the free plan.
        "mixedDaily": True,
        "leedsMinutes": 160,
        "leedsNote": "60 min for immigration and bags, then the direct TransPennine train from Manchester Airport to Leeds (about 2 h 40 min in total).",
    },
]
MONTHLY_BUDGET = int(os.environ.get("MONTHLY_SEARCH_BUDGET", "230"))


def now_sgt():
    return dt.datetime.now(SGT).replace(microsecond=0)


def empty_data():
    return {
        "schema": 3,
        "source": "Google Flights via SerpApi",
        "config": {},
        "lastRun": {"status": "never"},
        "usage": {"month": None, "searches": 0},
        "routes": {},
        "history": [],
    }


def load_data():
    if not DATA_FILE.exists():
        return empty_data()
    with open(DATA_FILE, encoding="utf-8") as f:
        data = json.load(f)
    if data.get("schema") == 3:
        return data
    if data.get("schema") == 2:
        # Heathrow-only file from the first version: keep its real checks under the LHR route.
        migrated = empty_data()
        migrated.update(lastRun=data.get("lastRun", migrated["lastRun"]), usage=data.get("usage", migrated["usage"]))
        migrated["routes"]["LHR"] = {"latest": data.get("latest", {})}
        for row in data.get("history", []):
            row = dict(row)
            row.setdefault("route", "LHR")
            row.setdefault("r", None)
            migrated["history"].append(row)
        print("Migrated schema 2 prices.json to schema 3 (routes).")
        return migrated
    print("Existing prices.json is not a known schema; starting a clean, API-only file.")
    return empty_data()


def save_data(data):
    data["schema"] = 3
    data["config"] = CONFIG
    for route in ROUTES:
        data["routes"].setdefault(route["id"], {"latest": {}})["config"] = route
    data["history"] = data["history"][-MAX_HISTORY_ROWS:]
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = DATA_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write("\n")
    tmp.replace(DATA_FILE)


def search(route, date, api_key, nonstop_only=False):
    max_stops = 0 if nonstop_only else route["maxStops"]
    params = {
        "engine": "google_flights",
        "departure_id": CONFIG["origin"],
        "arrival_id": route["destination"],
        "outbound_date": date,
        "return_date": CONFIG["returnDate"],
        "type": "1",          # round trip
        "travel_class": "1",  # economy
        "stops": "1" if max_stops == 0 else "2",  # 1 = non-stop, 2 = up to one stop
        "adults": "1",
        "currency": CONFIG["currency"],
        "gl": "sg",
        "hl": "en",
        "api_key": api_key,
    }
    if route.get("deepSearch"):
        params["deep_search"] = "true"
    url = API_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "flight-price-tracker/3.0"})
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as e:
        body = " ".join(e.read().decode("utf-8", "replace").split())[:300]
        raise RuntimeError(f"SerpApi HTTP {e.code}: {body}") from None
    if payload.get("error"):
        raise RuntimeError(f"SerpApi error: {payload['error']}")
    status = (payload.get("search_metadata") or {}).get("status")
    if status != "Success":
        raise RuntimeError(f"SerpApi search status was {status!r}")
    return payload


def minutes(value):
    return value if isinstance(value, int) and value > 0 else None


def parse_flights(payload, max_stops, preferred):
    """Return options with a real price and at most `max_stops` stops, cheapest per itinerary."""
    best = {}
    for item in (payload.get("best_flights") or []) + (payload.get("other_flights") or []):
        legs = item.get("flights") or []
        price = item.get("price")
        if not legs or len(legs) - 1 > max_stops or not isinstance(price, (int, float)) or price <= 0:
            continue
        numbers = [(leg.get("flight_number") or "").replace(" ", "").upper() for leg in legs]
        if any(len(n) < 3 for n in numbers):
            continue
        key = "+".join(numbers)
        first, last = legs[0], legs[-1]
        dep = first.get("departure_airport") or {}
        arr = last.get("arrival_airport") or {}
        airlines = []
        for leg in legs:
            name = leg.get("airline")
            if name and name not in airlines:
                airlines.append(name)
        row = {
            "flightNumber": key,
            "airlineCode": numbers[0][:2],
            "airline": " + ".join(airlines) or None,
            "depAirport": dep.get("id"),
            "depTime": dep.get("time"),
            "arrAirport": arr.get("id"),
            "arrTime": arr.get("time"),
            "durationMin": minutes(item.get("total_duration")) or minutes(first.get("duration")),
            "aircraft": first.get("airplane"),
            "stops": len(legs) - 1,
            "layovers": [
                {"airport": lay.get("id"), "durationMin": minutes(lay.get("duration"))}
                for lay in (item.get("layovers") or [])
            ],
            "price": int(round(price)),
        }
        if key not in best or row["price"] < best[key]["price"]:
            best[key] = row
    rows = sorted(best.values(), key=lambda r: r["price"])
    keep = rows[:MAX_OPTIONS_PER_SEARCH]
    keep += [r for r in rows[MAX_OPTIONS_PER_SEARCH:] if r["airlineCode"] == preferred]
    return keep


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

    errors, fetched, notes = [], [], []
    for route in ROUTES:
        store = data["routes"].setdefault(route["id"], {"latest": {}})
        store.setdefault("latest", {})
        for date in route["departures"]:
            label = f"{route['id']} {date}"
            if usage["searches"] >= MONTHLY_BUDGET:
                errors.append(f"{label}: skipped, monthly search budget of {MONTHLY_BUDGET} reached")
                continue
            prev = store["latest"].get(date) or {}
            try:
                if route["maxStops"] == 0:
                    payload = search(route, date, api_key)
                    usage["searches"] += 1
                    flights = parse_flights(payload, 0, CONFIG["preferredAirline"])
                    mixed_meta = None
                else:
                    # Non-stop prices come from a non-stop-only search: Google's mixed view can
                    # show a different (higher) fare for the same non-stop flight.
                    payload = search(route, date, api_key, nonstop_only=True)
                    usage["searches"] += 1
                    nonstop_at = now_sgt().isoformat()
                    flights = [dict(f, fetchedAt=nonstop_at) for f in parse_flights(payload, 0, CONFIG["preferredAirline"])]
                    one_stop, mixed_meta = [], None
                    mixed_today = (prev.get("mixedFetchedAt") or "")[:10] == started.date().isoformat()
                    if (started.hour < 12 or not mixed_today) and usage["searches"] < MONTHLY_BUDGET:
                        try:
                            mixed = search(route, date, api_key)
                            usage["searches"] += 1
                            mixed_at = now_sgt().isoformat()
                            one_stop = [dict(f, fetchedAt=mixed_at) for f in parse_flights(mixed, route["maxStops"], CONFIG["preferredAirline"]) if f["stops"] > 0]
                            mixed_meta = {"id": (mixed.get("search_metadata") or {}).get("id"), "url": (mixed.get("search_metadata") or {}).get("google_flights_url"), "at": mixed_at}
                        except Exception as e:  # noqa: BLE001
                            notes.append(f"{label}: one-stop check failed ({e})")
                    if mixed_meta is None:
                        # Keep the one-stop prices from today's earlier check; each row keeps its own fetch time.
                        one_stop = [f for f in prev.get("flights", []) if f.get("stops") and f.get("returnDate", CONFIG["returnDate"]) == CONFIG["returnDate"] and prev.get("returnDate") == CONFIG["returnDate"]]
                    flights = sorted(flights + one_stop, key=lambda r: r["price"])
                if not flights:
                    raise RuntimeError("search succeeded but returned no priced flights")
            except Exception as e:  # noqa: BLE001 - record any failure, never invent data
                errors.append(f"{label}: {e}")
                continue

            meta = payload.get("search_metadata") or {}
            previous_id = (store["latest"].get(date) or {}).get("searchId")
            fetched_at = now_sgt().isoformat()
            store["latest"][date] = {
                "fetchedAt": fetched_at,
                "searchId": meta.get("id"),
                "googleFlightsUrl": meta.get("google_flights_url"),
                "mixedSearchId": (mixed_meta or {}).get("id") or prev.get("mixedSearchId"),
                "mixedGoogleFlightsUrl": (mixed_meta or {}).get("url") or prev.get("mixedGoogleFlightsUrl"),
                "mixedFetchedAt": (mixed_meta or {}).get("at") or prev.get("mixedFetchedAt"),
                "returnDate": CONFIG["returnDate"],
                "priceInsights": parse_insights(payload),
                "flights": flights,
            }
            if meta.get("id") and meta.get("id") == previous_id:
                print(f"{label}: SerpApi returned a cached result already on record; history unchanged.")
            else:
                data["history"].append({
                    "t": fetched_at,
                    "route": route["id"],
                    "d": date,
                    "r": CONFIG["returnDate"],
                    "id": meta.get("id"),
                    "p": {f["flightNumber"]: f["price"] for f in flights if f.get("fetchedAt", fetched_at) >= started.isoformat()},
                })
            fetched.append(label)
            cheapest = flights[0]
            print(f"{label}: {len(flights)} options, cheapest {cheapest['flightNumber']} S${cheapest['price']:,}")

    status = "ok" if not errors else ("partial" if fetched else "error")
    data["lastRun"] = {
        "at": started.isoformat(),
        "status": status,
        "message": "; ".join(errors + notes) if errors else "; ".join([f"Checked {', '.join(fetched)}"] + notes),
    }
    save_data(data)
    for err in errors:
        print(f"::error::{err}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
