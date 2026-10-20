[README.md](https://github.com/user-attachments/files/33698433/README.md)
# SIN → LHR Non-Stop Flight Price Tracker (Leeds Arrival: 18 Jan 2027)

Interactive web dashboard and automated daily 11:00 AM SGT tracker for **non-stop Economy flights from Singapore Changi (SIN) to London Heathrow (LHR)** departing **Saturday, 16 Jan 2027** or **Sunday, 17 Jan 2027**, specifically designed to coordinate onward travel to **Leeds on Monday, 18 Jan 2027** and filter for **changeable return Economy fare tiers**.

## Quick Start (Localhost or GitHub Pages)

### Option 1: Host on GitHub Pages (Recommended)
1. Create a new GitHub repository and push this folder:
   ```bash
   git init
   git add .
   git commit -m "Initial commit: SIN-LHR flight tracker dashboard"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<your-repo>.git
   git push -u origin main
   ```
2. In your GitHub repository, go to **Settings → Pages** and set **Source** to `Deploy from a branch` (`main` / `/ (root)`).
3. Your live website will be available at `https://<your-username>.github.io/<your-repo>/`.
4. The included GitHub Action (`.github/workflows/daily-flight-tracker.yml`) is pre-configured for `0 3 * * *` UTC (**11:00 AM SGT daily**).

### Option 2: Run on Localhost
```bash
python3 server.py
# Opens http://localhost:8080
```
Or simply open `index.html` directly in any browser.

## Key Route & Fare Rules Summary
- **Non-Stop Carriers on SIN–LHR**: Singapore Airlines (`SQ306`, `SQ308`, `SQ318`, `SQ322`), British Airways (`BA16`, `BA12`), and Qantas (`QF1`, `QF209`).
- **Best Flights for Arriving in Leeds on Mon, 18 Jan 2027**:
  - **Depart Sun, 17 Jan 2027 Late Night**: `BA16` (23:05 → 05:25 LHR T5), `QF209` (23:10 → 05:30 LHR T3), `BA12` (23:15 → 05:45 LHR T5), `SQ322` (23:25 → 05:55 LHR T2), and `QF1` (23:35 → 06:15 LHR T3) all land at Heathrow early morning on **Monday, 18 Jan 2027**, enabling a same-day connecting flight (`LHR–LBA`) or LNER rail transfer (`King's Cross → Leeds`) arriving before noon with zero London hotel nights required.
- **Changeable Return Economy Fare Tiers**:
  - **Singapore Airlines**: Avoid *Economy Lite (V, K)* (no changes allowed). Book **Economy Value (Q, N)** or **Economy Standard (M, H, W)** (date changes allowed for a fee + fare difference) or **Economy Flexi (Y, B, E)** (free date changes).
  - **British Airways**: Avoid *Economy Basic*. Book **Economy Plus (Standard)** (~£150–£200 change fee + fare difference, includes 23kg bag + seat selection) or **Economy Plus Flexible** (free date changes).
  - **Qantas**: **Economy Saver / Sale** permits online date/time changes (even on partially travelled return legs) for a change fee + fare difference; **Economy Flex** has no change fee.
