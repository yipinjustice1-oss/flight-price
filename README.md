# SIN → Leeds fare watch

Live economy round-trip fares from Singapore (SIN) to the UK, aimed at being in Leeds on
**Mon 18 Jan 2027** and returning **Sat 5 Jun 2027**:

- **London Heathrow (LHR):** non-stop, departing Sat 16 or Sun 17 Jan 2027.
- **Manchester (MAN):** non-stop (only Singapore Airlines, SQ302 at 02:10) plus one-stop options,
  departing Mon 18 Jan 2027, which is the night of Sun 17 Jan.

- **Real numbers only.** Every price comes from a Google Flights search made through
  [SerpApi](https://serpapi.com/google-flights-api). Nothing is estimated or typed in. Each
  check stores its search id and a Google Flights link so you can verify any figure.
- **Runs itself.** GitHub Actions checks twice a day (about 09:00 and 21:00 SGT)
  and commits the results to `data/prices.json`.
- **Singapore Airlines weighted.** Across both airports, the recommended flight is the best
  non-stop flight landing on the Leeds day, and SQ wins unless another airline is more than
  S$150 cheaper (change `PREFERRED_ALLOWANCE` in the workflow). Cheaper one-stop options are
  listed and called out, but don't become the pick.
- **Executive summary first.** The page opens with a Book now / Keep watching / Hold off call,
  the recommended flight and its live fare.

## Setup (about 10 minutes)

1. **Get a SerpApi key.** Sign up at serpapi.com. The free plan gives 250 searches a month;
   this tracker uses about 186 (2 checks × 3 searches × 31 days).
2. **Upload these files** to the root of `yipinjustice1-oss/flight-price`.
   If an older `.github/workflows/daily-flight-tracker.yml` is there, delete it.
3. **Add the key as a secret.** Repo → Settings → Secrets and variables → Actions →
   New repository secret. Name: `SERPAPI_KEY`. Value: your key.
4. **Run it once.** Actions tab → "Track SIN-LHR fares" → Run workflow. It should go green in
   under a minute, and a new commit "Fare check …" will update `data/prices.json`.
5. **Publish the page.** Settings → Pages → Deploy from a branch → `main` / root. The site
   appears at `https://yipinjustice1-oss.github.io/flight-price/`.
6. **Google Sites.** Insert → Embed → By URL → paste the Pages address above. (Pasting the
   HTML into "Embed code" also works; it reads the data from GitHub directly.)

The repository must be **public** for steps 5 and 6 on a free GitHub plan.

## Changing the search

Edit the `env:` block in `.github/workflows/track-prices.yml`:

| Setting | Default | Meaning |
|---|---|---|
| `RETURN_DATE` | `2027-06-05` | Return date used for round-trip prices |
| `ARRIVE_BY` | `2027-01-18` | UK date you need to reach Leeds |
| `LHR_DEPARTURES` | `2027-01-16,2027-01-17` | Heathrow outbound dates (the last one is the focus) |
| `MAN_DEPARTURES` | `2027-01-18` | Manchester outbound dates (SQ302 leaves 02:10) |
| `MAN_MAX_STOPS` | `1` | 0 = non-stop only, 1 = include one-stop options |
| `PREFERRED_AIRLINE` | `SQ` | Airline given extra weight |
| `PREFERRED_ALLOWANCE` | `150` | S$ it may cost above the cheapest and still be picked |

Each extra date adds about 62 searches a month at 2 checks a day. The script stops searching
once 230 searches are used in a month, so it never runs past the free plan.

## What it can't do

- Google Flights shows the **cheapest fare type** (e.g. SQ Economy Lite), which usually can't
  change dates. Changeable fares cost more. Price them on the airline's site before booking.
- The Leeds arrival times are a rail-transfer estimate (about 4 h 35 min from landing).
- The Book / Watch / Hold call is a rule of thumb from Google's price rating and this
  tracker's history, not a forecast.

## Files

- `index.html`: the dashboard; reads `data/prices.json`
- `scripts/fetch_prices.py`: the fetcher (standard library only)
- `.github/workflows/track-prices.yml`: the schedule
- `data/prices.json`: starts empty and fills with real checks
- `server.py`: optional local preview (`python3 server.py`)
