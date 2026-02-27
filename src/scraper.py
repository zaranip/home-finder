"""
Redfin scraper using the public GIS JSON endpoint.

Architecture:
1. Resolve each ZIP code in ALLOWED_TOWNS to a Redfin region_id (via autocomplete API)
2. Hit /stingray/api/gis for each resolved ZIP region
3. Strip {}&&  prefix, parse JSON -> extract homes array
4. Map Redfin fields to the listing dict format expected by run.py
5. Deduplicate via seen_ids.json using Redfin propertyId
"""

from __future__ import annotations

import json
import logging
import random
import time
from typing import Any

import requests

from .config import (
    ALLOWED_TOWNS,
    MAX_PRICE,
    REGION_CACHE_FILE,
    SCRAPE_DELAY_MAX,
    SCRAPE_DELAY_MIN,
    SEEN_IDS_FILE,
    USER_AGENTS,
    MAX_RETRIES,
)

logger = logging.getLogger(__name__)

# ─── Helpers ─────────────────────────────────────────────────────────────────

_session = requests.Session()


def _random_ua() -> str:
    return random.choice(USER_AGENTS)


def _delay(minimum: float | None = None, maximum: float | None = None) -> None:
    """Random delay between requests."""
    lo = minimum if minimum is not None else SCRAPE_DELAY_MIN
    hi = maximum if maximum is not None else SCRAPE_DELAY_MAX
    time.sleep(random.uniform(lo, hi))


def _redfin_headers() -> dict[str, str]:
    return {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.redfin.com/",
        "User-Agent": _random_ua(),
    }


def _safe_get(d: dict | None, *keys: str, default: Any = None) -> Any:
    """Safely traverse nested dicts with 'value' wrapper pattern.

    Redfin GIS nests many fields as {"value": <actual>}.
    This helper tries d[key]["value"] first, then d[key] directly.
    """
    if d is None:
        return default
    current: Any = d
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    # Unwrap {"value": X} wrapper if present
    if isinstance(current, dict):
        if "value" in current:
            return current["value"]
        # Some Redfin fields have {"level": N} without a "value" key — treat as missing
        return default
    return current


# ─── Region ID Resolution ───────────────────────────────────────────────────

def _resolve_region_id(zip_code: str) -> dict[str, str] | None:
    """
    Resolve a ZIP code to a Redfin region_id by scraping the ZIP search page.

    Redfin embeds region metadata in each search page's ``createPreloadedMap``
    call as a URL-encoded JSON blob.  We extract the ``id`` and ``type`` fields
    from this blob.  The pattern in the raw HTML (URL-encoded) is::

        %22id%22%3A<REGION_ID>%2C%22type%22%3A2%2C%22name%22%3A%22<ZIP>%22

    Returns {"region_id": "...", "region_type": "..."} or None on failure.
    """
    import re as _re

    # URL-encoded pattern: "id":<digits>,"type":<digits>,"name":"<zip>"
    pattern = r'%22id%22%3A(\d+)%2C%22type%22%3A(\d+)%2C%22name%22%3A%22' + zip_code + r'%22'

    for attempt in range(MAX_RETRIES):
        try:
            resp = _session.get(
                f"https://www.redfin.com/zipcode/{zip_code}",
                headers=_redfin_headers(),
                timeout=20,
            )

            if resp.status_code == 403:
                logger.warning("403 from Redfin page for ZIP %s (attempt %d)", zip_code, attempt + 1)
                _delay(5, 15)
                continue

            resp.raise_for_status()

            match = _re.search(pattern, resp.text)
            if match:
                return {"region_id": match.group(1), "region_type": match.group(2)}

            logger.warning("Could not extract region_id from page for ZIP %s", zip_code)
            return None

        except requests.RequestException:
            logger.exception("Request failed resolving ZIP %s (attempt %d)", zip_code, attempt + 1)
            if attempt < MAX_RETRIES - 1:
                _delay(3, 8)

    logger.error("All %d attempts failed to resolve ZIP %s", MAX_RETRIES, zip_code)
    return None


def _load_region_cache() -> dict[str, dict[str, str]]:
    """Load cached ZIP -> region info mappings from disk."""
    if REGION_CACHE_FILE.exists():
        try:
            return json.loads(REGION_CACHE_FILE.read_text())
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _save_region_cache(cache: dict[str, dict[str, str]]) -> None:
    """Persist region cache to disk."""
    REGION_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    REGION_CACHE_FILE.write_text(json.dumps(cache, indent=2))


def resolve_all_zips() -> dict[str, dict[str, str]]:
    """
    Resolve all ZIP codes from ALLOWED_TOWNS to Redfin region IDs.

    Uses a disk cache (region_cache.json) to avoid redundant API calls.
    Only hits the autocomplete API for ZIPs not already cached.

    Returns: {zip_code: {"region_id": "...", "region_type": "..."}, ...}
    """
    cache = _load_region_cache()

    all_zips = [z for town in ALLOWED_TOWNS for z in town["zips"]]
    missing = [z for z in all_zips if z not in cache]

    if not missing:
        logger.info("All %d ZIP region IDs loaded from cache", len(all_zips))
        return cache

    logger.info("Resolving %d new ZIP codes (of %d total)...", len(missing), len(all_zips))
    updated = False

    for zip_code in missing:
        result = _resolve_region_id(zip_code)

        if result:
            cache[zip_code] = result
            updated = True
            logger.info("  ZIP %s -> region_id=%s (type=%s)",
                        zip_code, result["region_id"], result["region_type"])
        else:
            logger.warning("  ZIP %s -> could not resolve (will skip)", zip_code)

        _delay(1, 2)  # polite delay between autocomplete requests

    if updated:
        _save_region_cache(cache)

    resolved = sum(1 for z in all_zips if z in cache)
    logger.info("Region resolution complete: %d/%d ZIPs resolved", resolved, len(all_zips))
    return cache


# ─── GIS Endpoint ────────────────────────────────────────────────────────────

def search_zip(
    label: str,
    region_id: str,
    region_type: str = "2",
    max_price: int = MAX_PRICE,
) -> list[dict[str, Any]]:
    """
    Query Redfin GIS endpoint for for-sale listings in a given region.

    Returns raw home dicts from the API payload.
    """
    params = {
        "al": 1,
        "num_homes": 350,
        "region_id": region_id,
        "region_type": region_type,
        "status": 9,       # for sale
        "v": 8,
        "max_price": max_price,
    }

    for attempt in range(MAX_RETRIES):
        try:
            resp = _session.get(
                "https://www.redfin.com/stingray/api/gis",
                params=params,
                headers=_redfin_headers(),
                timeout=20,
            )

            if resp.status_code == 403:
                logger.warning("403 from Redfin GIS for %s (attempt %d/%d)", label, attempt + 1, MAX_RETRIES)
                _delay(5, 15)
                continue

            resp.raise_for_status()

            # Strip Redfin's JSON prefix: {}&&
            text = resp.text
            if text.startswith("{}&&"):
                text = text[4:]

            data = json.loads(text)
            homes = data.get("payload", {}).get("homes", [])
            logger.info("%s (region %s): %d homes returned", label, region_id, len(homes))
            return homes

        except json.JSONDecodeError:
            logger.exception("JSON parse error for %s (attempt %d)", label, attempt + 1)
            if attempt < MAX_RETRIES - 1:
                _delay(3, 8)
        except requests.RequestException:
            logger.exception("Request failed for %s (attempt %d)", label, attempt + 1)
            if attempt < MAX_RETRIES - 1:
                _delay(3, 8)

    logger.error("All %d attempts failed for %s", MAX_RETRIES, label)
    return []


# ─── Data Extraction ────────────────────────────────────────────────────────

def extract_listing(home: dict[str, Any], town_name: str) -> dict[str, Any] | None:
    """
    Map a Redfin GIS home dict to the listing format expected by run.py.

    Expected output dict keys:
        zpid, address, url, price, hoa, beds, baths, beds_baths,
        sqft, in_unit_laundry, parking, rent_zestimate,
        latitude, longitude, town
    """
    property_id = home.get("propertyId")
    if not property_id:
        return None

    # ── Price ────────────────────────────────────────────────────────────
    price = _safe_get(home, "price")
    if price is None:
        return None
    if isinstance(price, str):
        price = int(price.replace("$", "").replace(",", "").strip())

    # ── Address ──────────────────────────────────────────────────────────
    street = _safe_get(home, "streetLine") or ""
    city = _safe_get(home, "city") or ""
    state = _safe_get(home, "state") or ""
    zipcode = _safe_get(home, "zip") or ""
    address = f"{street}, {city}, {state} {zipcode}".strip().rstrip(",").strip()

    # ── URL ──────────────────────────────────────────────────────────────
    url_path = _safe_get(home, "url") or ""
    url = f"https://www.redfin.com{url_path}" if url_path else ""

    # ── Beds / Baths ─────────────────────────────────────────────────────
    beds = _safe_get(home, "beds")
    baths = _safe_get(home, "baths")
    beds_baths = f"{beds or '?'}bd/{baths or '?'}ba"

    # ── Size ─────────────────────────────────────────────────────────────
    sqft = _safe_get(home, "sqFt")

    # ── HOA ──────────────────────────────────────────────────────────────
    hoa = _safe_get(home, "hoa")
    if hoa is not None:
        try:
            hoa = int(hoa)
        except (ValueError, TypeError):
            hoa = None

    # ── Location ─────────────────────────────────────────────────────────
    lat_lng = home.get("latLong", {})
    if isinstance(lat_lng, dict) and "value" in lat_lng:
        lat_lng = lat_lng["value"]
    latitude = lat_lng.get("latitude") if isinstance(lat_lng, dict) else None
    longitude = lat_lng.get("longitude") if isinstance(lat_lng, dict) else None

    # ── Parking ──────────────────────────────────────────────────────────
    parking_spaces = home.get("skParkingSpaces")
    if parking_spaces is not None:
        try:
            parking_spaces = int(parking_spaces)
            parking = f"{parking_spaces} space{'s' if parking_spaces != 1 else ''}"
        except (ValueError, TypeError):
            parking = "Unknown"
    else:
        parking = "Unknown"

    return {
        "zpid": str(property_id),       # reuse key name for dedup compatibility
        "address": address,
        "url": url,
        "price": price,
        "hoa": hoa,
        "beds": beds,
        "baths": baths,
        "beds_baths": beds_baths,
        "sqft": sqft,
        "in_unit_laundry": None,         # not available in GIS results
        "parking": parking,
        "rent_zestimate": None,          # not in GIS; rental_estimate.py handles fallback
        "latitude": latitude,
        "longitude": longitude,
        "town": town_name,
    }


# ─── Deduplication ──────────────────────────────────────────────────────────

def load_seen_ids() -> set[str]:
    """Load previously seen listing IDs from disk."""
    if SEEN_IDS_FILE.exists():
        try:
            data = json.loads(SEEN_IDS_FILE.read_text())
            return set(str(x) for x in data)
        except (json.JSONDecodeError, TypeError):
            return set()
    return set()


def save_seen_ids(ids: set[str]) -> None:
    """Persist seen listing IDs to disk."""
    SEEN_IDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SEEN_IDS_FILE.write_text(json.dumps(sorted(ids)))


# ─── Main Scrape Orchestrator ───────────────────────────────────────────────

def scrape_all_towns(proxy_url: str | None = None) -> tuple[list[dict[str, Any]], set[str]]:
    """
    Scrape all configured ZIP codes via Redfin GIS endpoint.
    
    Resolves each ZIP in ALLOWED_TOWNS to a Redfin region_id (cached after
    first run), then queries the GIS endpoint for each ZIP individually.
    This ensures full coverage of multi-ZIP cities like Waltham and Newton.
    
    Returns:
        new_listings: listing dicts not previously seen (need enrichment).
        active_ids:   set of ALL property IDs currently on Redfin, used by
                      the caller to prune stale listings from the store.
    """
    if proxy_url:
        _session.proxies = {"http": proxy_url, "https": proxy_url}
    
    # Build ZIP -> town name mapping
    zip_to_town: dict[str, str] = {}
    for town in ALLOWED_TOWNS:
        for z in town["zips"]:
            zip_to_town[z] = town["name"]
    
    # Resolve all ZIPs to Redfin region IDs
    region_cache = resolve_all_zips()
    
    seen_ids = load_seen_ids()
    new_listings: list[dict[str, Any]] = []
    active_ids: set[str] = set()
    
    for zip_code, town_name in zip_to_town.items():
        region_info = region_cache.get(zip_code)
        if not region_info:
            logger.warning("No region_id for ZIP %s (%s), skipping", zip_code, town_name)
            continue
    
        region_id = region_info["region_id"]
        region_type = region_info["region_type"]
        label = f"{town_name} ({zip_code})"
    
        logger.info("Searching %s (region_id=%s)...", label, region_id)
    
        homes = search_zip(label, region_id, region_type)
        _delay(2, 5)  # polite delay between ZIP queries
    
        for home in homes:
            listing = extract_listing(home, town_name)
            if listing is None:
                continue
    
            pid = listing["zpid"]
            active_ids.add(pid)  # Track every listing Redfin currently shows
    
            if pid in seen_ids:
                continue  # Already processed — skip enrichment
    
            # Fill defaults for missing fields
            if listing["hoa"] is None:
                listing["hoa"] = 0
            if listing["in_unit_laundry"] is None:
                listing["in_unit_laundry"] = False
            if listing["parking"] is None:
                listing["parking"] = "Unknown"
    
            new_listings.append(listing)
            seen_ids.add(pid)
    
    # Prune seen_ids of listings no longer on Redfin
    stale_ids = seen_ids - active_ids
    if stale_ids:
        logger.info("Removing %d stale IDs from seen_ids", len(stale_ids))
        seen_ids -= stale_ids
    
    save_seen_ids(seen_ids)
    logger.info("Total new listings found: %d | Active on Redfin: %d", len(new_listings), len(active_ids))
    return new_listings, active_ids
