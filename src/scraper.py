"""
Redfin scraper using the public GIS JSON endpoint.

Architecture:
1. Hit /stingray/api/gis for each town's region_id (ZIP-based)
2. Strip {}&&  prefix, parse JSON -> extract homes array
3. Map Redfin fields to the listing dict format expected by run.py
4. Deduplicate via seen_ids.json using Redfin propertyId
"""

from __future__ import annotations

import json
import logging
import random
import time
from typing import Any

import requests

from .config import (
    MAX_PRICE,
    REDFIN_REGIONS,
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


# ─── GIS Endpoint ────────────────────────────────────────────────────────────

def search_town(
    town_name: str,
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
                logger.warning("403 from Redfin GIS for %s (attempt %d/%d)", town_name, attempt + 1, MAX_RETRIES)
                _delay(5, 15)
                continue

            resp.raise_for_status()

            # Strip Redfin's JSON prefix: {}&&
            text = resp.text
            if text.startswith("{}&&"):
                text = text[4:]

            data = json.loads(text)
            homes = data.get("payload", {}).get("homes", [])
            logger.info("%s (region %s): %d homes returned", town_name, region_id, len(homes))
            return homes

        except json.JSONDecodeError:
            logger.exception("JSON parse error for %s (attempt %d)", town_name, attempt + 1)
            if attempt < MAX_RETRIES - 1:
                _delay(3, 8)
        except requests.RequestException:
            logger.exception("Request failed for %s (attempt %d)", town_name, attempt + 1)
            if attempt < MAX_RETRIES - 1:
                _delay(3, 8)

    logger.error("All %d attempts failed for %s", MAX_RETRIES, town_name)
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

def scrape_all_towns(proxy_url: str | None = None) -> list[dict[str, Any]]:
    """
    Scrape all configured towns via Redfin GIS endpoint.

    The proxy_url parameter is accepted for interface compatibility with run.py
    but is not typically needed — Redfin's GIS endpoint works without proxies.

    Returns list of listing dicts ready for filtering/enrichment.
    """
    if proxy_url:
        _session.proxies = {"http": proxy_url, "https": proxy_url}

    seen_ids = load_seen_ids()
    all_listings: list[dict[str, Any]] = []

    for town_name, region_info in REDFIN_REGIONS.items():
        region_id = region_info["region_id"]
        region_type = region_info.get("region_type", "2")

        logger.info("Searching %s (region_id=%s)...", town_name, region_id)

        homes = search_town(town_name, region_id, region_type)
        _delay(2, 5)  # polite delay between town queries

        for home in homes:
            listing = extract_listing(home, town_name)
            if listing is None:
                continue

            pid = listing["zpid"]
            if pid in seen_ids:
                logger.debug("Skipping seen listing %s", pid)
                continue

            # Fill defaults for missing fields
            if listing["hoa"] is None:
                listing["hoa"] = 0
            if listing["in_unit_laundry"] is None:
                listing["in_unit_laundry"] = False
            if listing["parking"] is None:
                listing["parking"] = "Unknown"

            all_listings.append(listing)
            seen_ids.add(pid)

    save_seen_ids(seen_ids)
    logger.info("Total new listings found: %d", len(all_listings))
    return all_listings
