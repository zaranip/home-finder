"""
Configuration constants for the Redfin-based Boston listing finder.
All tunable parameters live here — towns, exclusions, destinations, thresholds.
"""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict


class TownEntry(TypedDict):
    name: str
    zillow_slug: str   # kept for reference; not used by Redfin scraper
    zips: list[str]

# ─── Redfin Region IDs (verified working) ────────────────────────────────────
# region_type "2" = ZIP code search. All IDs confirmed returning correct MA cities.
REDFIN_REGIONS: dict[str, dict[str, str]] = {
    "Allston":    {"region_id": "639",  "region_type": "2"},
    "Arlington":  {"region_id": "769",  "region_type": "2"},
    "Belmont":    {"region_id": "773",  "region_type": "2"},
    "Brighton":   {"region_id": "640",  "region_type": "2"},
    "Brookline":  {"region_id": "747",  "region_type": "2"},
    "Cambridge":  {"region_id": "643",  "region_type": "2"},
    "Medford":    {"region_id": "657",  "region_type": "2"},
    "Newton":     {"region_id": "757",  "region_type": "2"},
    "Quincy":     {"region_id": "660",  "region_type": "2"},
    "Somerville": {"region_id": "648",  "region_type": "2"},
    "Waltham":    {"region_id": "750",  "region_type": "2"},
    "Watertown":  {"region_id": "767",  "region_type": "2"},
}

# ─── Paths ───────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LISTINGS_XLSX = DATA_DIR / "listings.xlsx"
SEEN_IDS_FILE = DATA_DIR / "seen_ids.json"

# ─── Price / HOA Filters ────────────────────────────────────────────────────
MAX_PRICE = 600_000
MAX_HOA_MONTHLY = 500

# ─── Location Allow-list ────────────────────────────────────────────────────
# Each entry: {"name": display name, "zillow_slug": Zillow URL slug, "zips": known ZIP codes}
ALLOWED_TOWNS: list[TownEntry] = [
    {"name": "Quincy",      "zillow_slug": "quincy-ma",      "zips": ["02169", "02170", "02171"]},
    {"name": "Waltham",     "zillow_slug": "waltham-ma",     "zips": ["02451", "02452", "02453", "02454"]},
    {"name": "Newton",      "zillow_slug": "newton-ma",      "zips": ["02458", "02459", "02460", "02461", "02462", "02464", "02465", "02466", "02467", "02468"]},
    {"name": "Watertown",   "zillow_slug": "watertown-ma",   "zips": ["02471", "02472"]},
    {"name": "Brighton",    "zillow_slug": "brighton-boston-ma", "zips": ["02135"]},
    {"name": "Allston",     "zillow_slug": "allston-boston-ma",  "zips": ["02134"]},
    {"name": "Somerville",  "zillow_slug": "somerville-ma",  "zips": ["02143", "02144", "02145"]},
    {"name": "Cambridge",   "zillow_slug": "cambridge-ma",   "zips": ["02138", "02139", "02140", "02141", "02142"]},
    {"name": "Brookline",   "zillow_slug": "brookline-ma",   "zips": ["02445", "02446", "02447"]},
    {"name": "Medford",     "zillow_slug": "medford-ma",     "zips": ["02155", "02156"]},
    {"name": "Arlington",   "zillow_slug": "arlington-ma",   "zips": ["02474", "02476"]},
    {"name": "Belmont",     "zillow_slug": "belmont-ma",     "zips": ["02478"]},
]

# Flat set of all allowed ZIP codes for fast lookup
ALLOWED_ZIPS = {z for town in ALLOWED_TOWNS for z in town["zips"]}

# ─── Location Block-list ────────────────────────────────────────────────────
BLOCKED_NEIGHBORHOODS = [
    "dorchester",
    "jamaica plain",
    "east boston",
    "revere",
    "roxbury",
    "mattapan",
    "hyde park",
]

BLOCKED_ZIPS = {
    # Dorchester
    "02121", "02122", "02124", "02125",
    # Jamaica Plain
    "02130",
    # East Boston
    "02128",
    # Revere
    "02151",
    # Roxbury
    "02119", "02120",
    # Mattapan
    "02126",
    # Hyde Park
    "02136",
}

# ─── Driving Time Destinations (lat, lng) ───────────────────────────────────
DESTINATIONS = {
    "seaport":        {"label": "200 Pier 4 Blvd (Seaport)", "lat": 42.3519, "lng": -71.0446},
    "google_cambridge": {"label": "Google Cambridge",          "lat": 42.3625, "lng": -71.0847},
}

# ─── MBTA Rapid Transit Stations ────────────────────────────────────────────
# Red, Orange, Blue, Green lines — core stations in the greater Boston area.
# Coordinates are approximate station centroids.
MBTA_STATIONS = [
    # Red Line
    {"name": "Alewife",            "lat": 42.3954, "lng": -71.1425, "line": "Red"},
    {"name": "Davis",              "lat": 42.3967, "lng": -71.1218, "line": "Red"},
    {"name": "Porter",             "lat": 42.3884, "lng": -71.1191, "line": "Red"},
    {"name": "Harvard",            "lat": 42.3734, "lng": -71.1189, "line": "Red"},
    {"name": "Central",            "lat": 42.3653, "lng": -71.1037, "line": "Red"},
    {"name": "Kendall/MIT",        "lat": 42.3625, "lng": -71.0862, "line": "Red"},
    {"name": "Charles/MGH",        "lat": 42.3613, "lng": -71.0707, "line": "Red"},
    {"name": "Park Street",        "lat": 42.3564, "lng": -71.0624, "line": "Red"},
    {"name": "Downtown Crossing",  "lat": 42.3555, "lng": -71.0602, "line": "Red"},
    {"name": "South Station",      "lat": 42.3523, "lng": -71.0553, "line": "Red"},
    {"name": "Broadway",           "lat": 42.3426, "lng": -71.0569, "line": "Red"},
    {"name": "Andrew",             "lat": 42.3302, "lng": -71.0570, "line": "Red"},
    {"name": "JFK/UMass",          "lat": 42.3209, "lng": -71.0524, "line": "Red"},
    {"name": "North Quincy",       "lat": 42.2754, "lng": -71.0300, "line": "Red"},
    {"name": "Wollaston",          "lat": 42.2665, "lng": -71.0198, "line": "Red"},
    {"name": "Quincy Center",      "lat": 42.2516, "lng": -71.0052, "line": "Red"},
    {"name": "Quincy Adams",       "lat": 42.2330, "lng": -71.0073, "line": "Red"},
    {"name": "Braintree",          "lat": 42.2078, "lng": -71.0011, "line": "Red"},
    # Red Line Ashmont branch
    {"name": "Savin Hill",         "lat": 42.3112, "lng": -71.0534, "line": "Red"},
    {"name": "Fields Corner",      "lat": 42.3000, "lng": -71.0616, "line": "Red"},
    {"name": "Shawmut",            "lat": 42.2932, "lng": -71.0658, "line": "Red"},
    {"name": "Ashmont",            "lat": 42.2840, "lng": -71.0637, "line": "Red"},
    # Orange Line
    {"name": "Oak Grove",          "lat": 42.4367, "lng": -71.0710, "line": "Orange"},
    {"name": "Malden Center",      "lat": 42.4268, "lng": -71.0740, "line": "Orange"},
    {"name": "Wellington",         "lat": 42.4046, "lng": -71.0770, "line": "Orange"},
    {"name": "Assembly",           "lat": 42.3924, "lng": -71.0770, "line": "Orange"},
    {"name": "Sullivan Square",    "lat": 42.3840, "lng": -71.0770, "line": "Orange"},
    {"name": "Community College",  "lat": 42.3736, "lng": -71.0695, "line": "Orange"},
    {"name": "North Station",      "lat": 42.3655, "lng": -71.0614, "line": "Orange"},
    {"name": "Haymarket",          "lat": 42.3630, "lng": -71.0583, "line": "Orange"},
    {"name": "State",              "lat": 42.3587, "lng": -71.0576, "line": "Orange"},
    {"name": "Downtown Crossing",  "lat": 42.3555, "lng": -71.0602, "line": "Orange"},
    {"name": "Chinatown",          "lat": 42.3524, "lng": -71.0625, "line": "Orange"},
    {"name": "Tufts Medical Center","lat": 42.3497, "lng": -71.0638, "line": "Orange"},
    {"name": "Back Bay",           "lat": 42.3474, "lng": -71.0753, "line": "Orange"},
    {"name": "Massachusetts Ave",  "lat": 42.3414, "lng": -71.0835, "line": "Orange"},
    {"name": "Ruggles",            "lat": 42.3365, "lng": -71.0890, "line": "Orange"},
    {"name": "Roxbury Crossing",   "lat": 42.3313, "lng": -71.0954, "line": "Orange"},
    {"name": "Jackson Square",     "lat": 42.3233, "lng": -71.0998, "line": "Orange"},
    {"name": "Stony Brook",        "lat": 42.3170, "lng": -71.1042, "line": "Orange"},
    {"name": "Green Street",       "lat": 42.3104, "lng": -71.1074, "line": "Orange"},
    {"name": "Forest Hills",       "lat": 42.3006, "lng": -71.1139, "line": "Orange"},
    # Blue Line
    {"name": "Wonderland",         "lat": 42.4135, "lng": -70.9917, "line": "Blue"},
    {"name": "Revere Beach",       "lat": 42.4077, "lng": -70.9925, "line": "Blue"},
    {"name": "Beachmont",          "lat": 42.3975, "lng": -70.9923, "line": "Blue"},
    {"name": "Suffolk Downs",      "lat": 42.3903, "lng": -70.9972, "line": "Blue"},
    {"name": "Orient Heights",     "lat": 42.3867, "lng": -71.0046, "line": "Blue"},
    {"name": "Wood Island",        "lat": 42.3796, "lng": -71.0230, "line": "Blue"},
    {"name": "Airport",            "lat": 42.3742, "lng": -71.0302, "line": "Blue"},
    {"name": "Maverick",           "lat": 42.3691, "lng": -71.0396, "line": "Blue"},
    {"name": "Aquarium",           "lat": 42.3597, "lng": -71.0517, "line": "Blue"},
    {"name": "Government Center",  "lat": 42.3594, "lng": -71.0592, "line": "Blue"},
    {"name": "Bowdoin",            "lat": 42.3614, "lng": -71.0620, "line": "Blue"},
    # Green Line (B, C, D, E branches — key stations)
    {"name": "Lechmere",           "lat": 42.3708, "lng": -71.0769, "line": "Green"},
    {"name": "Science Park",       "lat": 42.3665, "lng": -71.0681, "line": "Green"},
    {"name": "North Station",      "lat": 42.3655, "lng": -71.0614, "line": "Green"},
    {"name": "Haymarket",          "lat": 42.3630, "lng": -71.0583, "line": "Green"},
    {"name": "Government Center",  "lat": 42.3594, "lng": -71.0592, "line": "Green"},
    {"name": "Park Street",        "lat": 42.3564, "lng": -71.0624, "line": "Green"},
    {"name": "Boylston",           "lat": 42.3529, "lng": -71.0646, "line": "Green"},
    {"name": "Arlington",          "lat": 42.3519, "lng": -71.0707, "line": "Green"},
    {"name": "Copley",             "lat": 42.3500, "lng": -71.0774, "line": "Green"},
    {"name": "Hynes Convention Center", "lat": 42.3479, "lng": -71.0874, "line": "Green"},
    {"name": "Kenmore",            "lat": 42.3487, "lng": -71.0952, "line": "Green"},
    # Green B Branch (to Boston College)
    {"name": "Blandford Street",   "lat": 42.3492, "lng": -71.1003, "line": "Green-B"},
    {"name": "Boston University East", "lat": 42.3500, "lng": -71.1040, "line": "Green-B"},
    {"name": "Boston University Central", "lat": 42.3503, "lng": -71.1068, "line": "Green-B"},
    {"name": "Boston University West", "lat": 42.3508, "lng": -71.1132, "line": "Green-B"},
    {"name": "Packards Corner",    "lat": 42.3515, "lng": -71.1161, "line": "Green-B"},
    {"name": "Harvard Avenue",     "lat": 42.3504, "lng": -71.1312, "line": "Green-B"},
    {"name": "Allston Street",     "lat": 42.3487, "lng": -71.1372, "line": "Green-B"},
    {"name": "Warren Street",      "lat": 42.3484, "lng": -71.1404, "line": "Green-B"},
    {"name": "Washington Street",  "lat": 42.3434, "lng": -71.1498, "line": "Green-B"},
    {"name": "Sutherland Road",    "lat": 42.3418, "lng": -71.1462, "line": "Green-B"},
    {"name": "Chiswick Road",      "lat": 42.3407, "lng": -71.1528, "line": "Green-B"},
    {"name": "Chestnut Hill Avenue","lat": 42.3386, "lng": -71.1534, "line": "Green-B"},
    {"name": "South Street",       "lat": 42.3398, "lng": -71.1575, "line": "Green-B"},
    {"name": "Boston College",     "lat": 42.3396, "lng": -71.1664, "line": "Green-B"},
    # Green C Branch (to Cleveland Circle)
    {"name": "Saint Marys Street",   "lat": 42.3459, "lng": -71.1049, "line": "Green-C"},
    {"name": "Hawes Street",         "lat": 42.3442, "lng": -71.1111, "line": "Green-C"},
    {"name": "Kent Street",          "lat": 42.3424, "lng": -71.1146, "line": "Green-C"},
    {"name": "Saint Paul Street",    "lat": 42.3404, "lng": -71.1165, "line": "Green-C"},
    {"name": "Coolidge Corner",      "lat": 42.3387, "lng": -71.1209, "line": "Green-C"},
    {"name": "Summit Avenue",        "lat": 42.3400, "lng": -71.1274, "line": "Green-C"},
    {"name": "Brandon Hall",         "lat": 42.3397, "lng": -71.1310, "line": "Green-C"},
    {"name": "Fairbanks Street",     "lat": 42.3391, "lng": -71.1345, "line": "Green-C"},
    {"name": "Washington Square",    "lat": 42.3393, "lng": -71.1386, "line": "Green-C"},
    {"name": "Tappan Street",        "lat": 42.3383, "lng": -71.1418, "line": "Green-C"},
    {"name": "Dean Road",            "lat": 42.3373, "lng": -71.1445, "line": "Green-C"},
    {"name": "Englewood Avenue",     "lat": 42.3365, "lng": -71.1481, "line": "Green-C"},
    {"name": "Cleveland Circle",     "lat": 42.3362, "lng": -71.1511, "line": "Green-C"},
    # Green D Branch (to Riverside) — key stops
    {"name": "Fenway",              "lat": 42.3450, "lng": -71.1004, "line": "Green-D"},
    {"name": "Longwood",            "lat": 42.3416, "lng": -71.1097, "line": "Green-D"},
    {"name": "Brookline Village",   "lat": 42.3326, "lng": -71.1168, "line": "Green-D"},
    {"name": "Brookline Hills",     "lat": 42.3312, "lng": -71.1264, "line": "Green-D"},
    {"name": "Beaconsfield",        "lat": 42.3310, "lng": -71.1410, "line": "Green-D"},
    {"name": "Reservoir",           "lat": 42.3352, "lng": -71.1488, "line": "Green-D"},
    {"name": "Chestnut Hill",       "lat": 42.3268, "lng": -71.1646, "line": "Green-D"},
    {"name": "Newton Centre",       "lat": 42.3293, "lng": -71.1921, "line": "Green-D"},
    {"name": "Newton Highlands",    "lat": 42.3219, "lng": -71.2060, "line": "Green-D"},
    {"name": "Eliot",               "lat": 42.3190, "lng": -71.2163, "line": "Green-D"},
    {"name": "Waban",               "lat": 42.3260, "lng": -71.2305, "line": "Green-D"},
    {"name": "Woodland",            "lat": 42.3330, "lng": -71.2430, "line": "Green-D"},
    {"name": "Riverside",           "lat": 42.3372, "lng": -71.2523, "line": "Green-D"},
    # Green E Branch (to Heath Street)
    {"name": "Prudential",          "lat": 42.3458, "lng": -71.0819, "line": "Green-E"},
    {"name": "Symphony",            "lat": 42.3425, "lng": -71.0854, "line": "Green-E"},
    {"name": "Northeastern University", "lat": 42.3400, "lng": -71.0888, "line": "Green-E"},
    {"name": "Museum of Fine Arts", "lat": 42.3375, "lng": -71.0958, "line": "Green-E"},
    {"name": "Longwood Medical Area","lat": 42.3354, "lng": -71.0993, "line": "Green-E"},
    {"name": "Brigham Circle",      "lat": 42.3343, "lng": -71.1044, "line": "Green-E"},
    {"name": "Fenwood Road",        "lat": 42.3333, "lng": -71.1056, "line": "Green-E"},
    {"name": "Mission Park",        "lat": 42.3319, "lng": -71.1089, "line": "Green-E"},
    {"name": "Riverway",            "lat": 42.3319, "lng": -71.1089, "line": "Green-E"},
    {"name": "Back of the Hill",    "lat": 42.3299, "lng": -71.1107, "line": "Green-E"},
    {"name": "Heath Street",        "lat": 42.3285, "lng": -71.1111, "line": "Green-E"},
    # Green Line Extension (Medford/Tufts)
    {"name": "East Somerville",     "lat": 42.3793, "lng": -71.0870, "line": "Green-Ext"},
    {"name": "Gilman Square",       "lat": 42.3880, "lng": -71.0960, "line": "Green-Ext"},
    {"name": "Magoun Square",       "lat": 42.3934, "lng": -71.1061, "line": "Green-Ext"},
    {"name": "Ball Square",         "lat": 42.3987, "lng": -71.1107, "line": "Green-Ext"},
    {"name": "Medford/Tufts",       "lat": 42.4074, "lng": -71.1166, "line": "Green-Ext"},
    {"name": "Union Square",        "lat": 42.3770, "lng": -71.0930, "line": "Green-Ext"},
]

# ─── Rating Thresholds ──────────────────────────────────────────────────────
RATING_WEIGHTS = {
    "price":            0.20,
    "hoa":              0.10,
    "net_monthly_cost": 0.20,
    "commute_seaport":  0.15,
    "commute_google":   0.10,
    "mbta_proximity":   0.10,
    "in_unit_laundry":  0.05,
    "parking":          0.05,
    "size":             0.05,
}

# Score thresholds: (green_threshold, yellow_threshold) — above green = 3, between = 2, below yellow = 1
RATING_THRESHOLDS = {
    "price":            (400_000, 500_000),       # < 400K = green, > 500K = red
    "hoa":              (200, 400),               # < $200 = green, > $400 = red
    "net_monthly_cost": (2_000, 3_000),           # after roommate offset
    "commute_seaport":  (15, 30),                 # minutes
    "commute_google":   (15, 25),                 # minutes
    "mbta_proximity":   (5, 15),                  # minutes driving
}

# Overall rating color thresholds
RATING_GREEN_MIN = 2.3    # weighted score >= 2.3 → Green
RATING_YELLOW_MIN = 1.7   # weighted score >= 1.7 → Yellow, below → Red

# ─── Excel Defaults (Assumptions sheet) ─────────────────────────────────────
EXCEL_DEFAULTS = {
    "interest_rate":     0.065,   # 6.5%
    "down_payment_pct":  0.20,    # 20%
    "loan_term_years":   30,
    "property_tax_rate": 0.012,   # 1.2%
    "insurance_monthly": 150,
    "utilities_monthly": 250,
    "internet_monthly":  60,
}

# ─── Rental Estimates by Town (fallback, $/mo for standalone 1BR) ────────────
# Updated periodically from Zillow Rental Manager / Rentometer.
# rental_estimate.py applies a 0.65 discount when used for roommate pricing
# (renting a room in a shared unit is cheaper than a full 1BR).
FALLBACK_RENTS = {
    "Quincy":     1_800,
    "Waltham":    1_900,
    "Newton":     2_200,
    "Watertown":  2_100,
    "Brighton":   2_000,
    "Allston":    1_900,
    "Somerville": 2_300,
    "Cambridge":  2_500,
    "Brookline":  2_400,
    "Medford":    1_900,
    "Arlington":  2_000,
    "Belmont":    2_100,
}

# ─── Scraper Settings ───────────────────────────────────────────────────────
SCRAPE_DELAY_MIN = 3      # seconds between page loads (min)
SCRAPE_DELAY_MAX = 8      # seconds between page loads (max)
REQUEST_TIMEOUT = 30_000  # milliseconds for Playwright page timeout
MAX_RETRIES = 3
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
]

# ─── OSRM Settings ──────────────────────────────────────────────────────────
OSRM_BASE_URL = "https://router.project-osrm.org/route/v1/driving"
NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org/search"
OSRM_DELAY = 1.1  # seconds between requests (public server rate limit ~1 req/s)
