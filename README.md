# Home Finder

A Python tool that scrapes Redfin for real estate listings in the Boston metro area, filters and scores them based on your criteria, and exports a clean Excel workbook so you can find your next home without doom-scrolling Zillow every night.

## What It Does

1. **Scrapes** Redfin's public API for active listings across 12 configurable towns
2. **Filters** by price, HOA, and location (allowlist + blocklist)
3. **Computes driving times** to your key destinations (workplace, MBTA stations) using free routing APIs
4. **Estimates roommate income** to calculate your real net monthly cost
5. **Rates every listing** Green / Yellow / Red based on a weighted scoring system
6. **Exports to Excel** with live formulas, conditional formatting, and an adjustable assumptions sheet

No API keys required. All external services used (Redfin, OSRM, Nominatim) are free and public.

## Quick Start

### Prerequisites

- Python 3.11 or newer

### Installation

```bash
git clone https://github.com/YOUR_USERNAME/home-finder.git
cd home-finder
pip install -r requirements.txt
```

### Run It

```bash
python run.py
```

That's it. Results land in `data/listings.xlsx` (plus a timestamped copy for history).

### Options

```bash
python run.py --verbose          # Debug-level logging
python run.py --proxy http://user:pass@host:port   # Route requests through a proxy
```

## Output

The Excel workbook has two sheets:

### Assumptions Sheet

Financial parameters used in the cost calculations. Edit these cells directly in Excel to see how your numbers change:

| Parameter | Default |
|---|---|
| Interest Rate | 6.5% |
| Down Payment | 20% |
| Loan Term | 30 years |
| Property Tax Rate | 1.2% |
| Insurance | $150/mo |
| Utilities | $250/mo |
| Internet | $60/mo |

### Listings Sheet

Each row is a listing, sorted best-first, with:

- **Address, town, and a clickable Redfin link**
- **Price and HOA**
- **Beds, baths, square footage, laundry, parking**
- **Calculated monthly costs** (mortgage, taxes, insurance, utilities) with live Excel formulas tied to the Assumptions sheet
- **Roommate rental estimate** based on town-level median rents
- **Net monthly cost** = total cost minus roommate income
- **Driving times** to the nearest MBTA station, Seaport, and Google Cambridge
- **Rating score and color** (Green / Yellow / Red)

Ratings are color-coded with conditional formatting so you can scan at a glance.

## Customize It for Your Search

All configuration lives in [`src/config.py`](src/config.py). Here's what to change:

### Search Area

Edit `REDFIN_REGIONS` to add or remove towns. Each entry needs a Redfin `region_id` (you can find these by inspecting Redfin's network requests when searching a town):

```python
REDFIN_REGIONS = {
    "Allston":    {"region_id": "639",  "region_type": "2"},
    "Cambridge":  {"region_id": "643",  "region_type": "2"},
    # Add your towns here...
}
```

Update `ALLOWED_TOWNS` with the corresponding ZIP codes so the filter knows which listings to keep.

### Price Limits

```python
MAX_PRICE = 600_000       # Maximum listing price
MAX_HOA_MONTHLY = 500     # Maximum monthly HOA fee
```

### Commute Destinations

Change where driving times are calculated to:

```python
DESTINATIONS = {
    "seaport":          {"label": "200 Pier 4 Blvd (Seaport)", "lat": 42.3519, "lng": -71.0446},
    "google_cambridge": {"label": "Google Cambridge",           "lat": 42.3625, "lng": -71.0847},
}
```

Replace these with your own workplace coordinates.

### Rating Weights

Control how much each factor matters in the final score:

```python
RATING_WEIGHTS = {
    "price":            0.20,   # How cheap is it?
    "hoa":              0.10,   # Low HOA?
    "net_monthly_cost": 0.20,   # Affordable after roommate?
    "commute_seaport":  0.15,   # Short drive to Seaport?
    "commute_google":   0.10,   # Short drive to Google?
    "mbta_proximity":   0.10,   # Close to the T?
    "in_unit_laundry":  0.05,   # Has washer/dryer?
    "parking":          0.05,   # Has parking?
    "size":             0.05,   # Big enough?
}
```

Weights must sum to 1.0. Bump up what matters most to you.

### Rating Thresholds

Define what "good" and "bad" means for each metric:

```python
RATING_THRESHOLDS = {
    "price":            (400_000, 500_000),   # < 400K = green, > 500K = red
    "hoa":              (200, 400),            # < $200/mo = green, > $400/mo = red
    "net_monthly_cost": (2_000, 3_000),        # After roommate offset
    "commute_seaport":  (15, 30),              # Minutes
    "commute_google":   (15, 25),              # Minutes
    "mbta_proximity":   (5, 15),               # Minutes driving
}
```

## Automate It (Windows)

The included `scheduler_setup.bat` creates a Windows Task Scheduler job that runs the scraper every morning at 8 AM.

1. Open `scheduler_setup.bat` in a text editor
2. Update `PYTHON_PATH` to point to your Python installation
3. Right-click the `.bat` file and select **Run as administrator**

To verify it's scheduled:

```
schtasks /query /tn "RedfinFinder_Daily"
```

To run it manually right now:

```
schtasks /run /tn "RedfinFinder_Daily"
```

To remove the scheduled task:

```
schtasks /delete /tn "RedfinFinder_Daily" /f
```

## How It Works Under the Hood

```
run.py                    # Entry point — orchestrates the 5-step pipeline
src/
  config.py               # All configuration (towns, filters, destinations, weights)
  scraper.py              # Hits Redfin's GIS API, extracts listing data, deduplicates
  filters.py              # Applies price, HOA, and location filters
  driving_times.py        # OSRM routing + Nominatim geocoding (both free, no keys)
  rental_estimate.py      # Estimates roommate rental income per town
  rating.py               # Weighted multi-factor scoring → Green/Yellow/Red
  excel_builder.py        # Builds the Excel workbook with formulas + formatting
data/
  listings.xlsx           # Latest output
  listings_YYYYMMDD.xlsx  # Timestamped history
  seen_ids.json           # Tracks previously seen listings to avoid duplicates
  redfin_finder.log       # Run log
```

The pipeline runs in five steps:

1. **Scrape** — Queries Redfin's `/stingray/api/gis` endpoint for each configured town. Deduplicates against `seen_ids.json` so you only see new listings.
2. **Filter** — Drops listings outside your price range, HOA budget, or geographic area.
3. **Driving times** — Geocodes each address (or uses lat/lng from Redfin), then calls OSRM to get driving durations to the nearest MBTA station and your configured destinations.
4. **Rate** — Scores each listing across 9 weighted categories and assigns a Green/Yellow/Red color.
5. **Export** — Writes a formatted Excel workbook with live formulas so you can tweak assumptions and see costs update in real time.

## Troubleshooting

**"No new listings found"** — The scraper only shows listings it hasn't seen before. Delete `data/seen_ids.json` to reset and re-fetch everything.

**403 errors from Redfin** — The scraper includes random delays and user-agent rotation, but Redfin may still rate-limit you. Try again later, use the `--proxy` flag, or increase `SCRAPE_DELAY_MIN` / `SCRAPE_DELAY_MAX` in `config.py`.

**Driving times showing as None** — OSRM and Nominatim are free public services with rate limits. The scraper respects these (~1 request/second), but if the services are overloaded, some lookups may fail. Re-running usually picks them up.

## License

MIT
