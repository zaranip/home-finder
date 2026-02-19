"""
Driving time calculations using OSRM (free, no API key) and Nominatim geocoding.

Computes driving minutes from each listing to:
  - Nearest MBTA rapid transit station
  - 200 Pier 4 Blvd, Boston (Seaport)
  - Google Cambridge (325 Main St)
"""

from __future__ import annotations

import logging
import math
import time
from functools import lru_cache
from typing import Any

import requests

from .config import (
    DESTINATIONS,
    MBTA_STATIONS,
    NOMINATIM_BASE_URL,
    OSRM_BASE_URL,
    OSRM_DELAY,
)

logger = logging.getLogger(__name__)

# ─── Geocoding ──────────────────────────────────────────────────────────────

_geocode_session = requests.Session()
_geocode_session.headers.update({
    "User-Agent": "zillow-finder-boston/1.0 (real-estate-search-tool)"
})


@lru_cache(maxsize=1024)
def geocode_address(address: str) -> tuple[float, float] | None:
    """
    Convert an address string to (lat, lng) using Nominatim.
    Returns None if geocoding fails. Results are cached.
    """
    try:
        resp = _geocode_session.get(
            NOMINATIM_BASE_URL,
            params={
                "q": address,
                "format": "json",
                "limit": 1,
                "countrycodes": "us",
            },
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json()

        if not results:
            logger.warning("Nominatim returned no results for: %s", address)
            return None

        lat = float(results[0]["lat"])
        lng = float(results[0]["lon"])
        time.sleep(1.1)  # Nominatim rate limit: 1 req/sec
        return lat, lng

    except Exception:
        logger.exception("Geocoding failed for: %s", address)
        return None


# ─── OSRM Routing ───────────────────────────────────────────────────────────

def _osrm_table(
    origin_lat: float,
    origin_lng: float,
    destinations: list[tuple[float, float]],
) -> list[float | None]:
    """
    Use OSRM Table service to get driving durations from one origin to N destinations.
    Returns list of durations in seconds (or None if no route found).
    Coordinates: (lat, lng) — converted to OSRM's lng,lat format internally.
    """
    # OSRM wants lng,lat
    coords_parts = [f"{origin_lng},{origin_lat}"]
    for dlat, dlng in destinations:
        coords_parts.append(f"{dlng},{dlat}")

    coords_str = ";".join(coords_parts)
    dest_indices = ";".join(str(i + 1) for i in range(len(destinations)))

    try:
        table_url = OSRM_BASE_URL.replace("route/v1/driving", "table/v1/driving")
        resp = requests.get(
            f"{table_url}/{coords_str}",
            params={
                "sources": "0",
                "destinations": dest_indices,
                "annotations": "duration",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != "Ok":
            logger.warning("OSRM error: %s", data.get("code"))
            return [None] * len(destinations)

        return data["durations"][0]

    except Exception:
        logger.exception("OSRM table request failed")
        return [None] * len(destinations)


def _osrm_route(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
) -> float | None:
    """
    Single route query. Returns duration in seconds or None.
    """
    coords = f"{origin_lng},{origin_lat};{dest_lng},{dest_lat}"

    try:
        resp = requests.get(
            f"{OSRM_BASE_URL}/{coords}",
            params={"overview": "false"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != "Ok":
            return None

        return data["routes"][0]["duration"]

    except Exception:
        logger.exception("OSRM route request failed")
        return None


# ─── MBTA Station Finder ────────────────────────────────────────────────────

def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Haversine distance in kilometers."""
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return r * 2 * math.asin(math.sqrt(a))


def find_nearest_mbta(lat: float, lng: float) -> tuple[str, float, float]:
    """
    Find the nearest MBTA rapid transit station by straight-line distance.
    Returns (station_name, station_lat, station_lng).
    """
    best_name = ""
    best_dist = float("inf")
    best_lat = 0.0
    best_lng = 0.0

    for station in MBTA_STATIONS:
        slat = float(station["lat"])
        slng = float(station["lng"])
        dist = _haversine_km(lat, lng, slat, slng)
        if dist < best_dist:
            best_dist = dist
            best_name = str(station["name"])
            best_lat = slat
            best_lng = slng

    return best_name, best_lat, best_lng


# ─── Main Interface ─────────────────────────────────────────────────────────

def compute_driving_times(
    address: str,
    lat: float | None = None,
    lng: float | None = None,
) -> dict[str, Any]:
    """
    Compute driving times for a listing address.

    If lat/lng are provided (from Zillow search results), skips geocoding.
    Otherwise falls back to Nominatim geocoding.

    Returns:
    {
        "drive_mbta_min": float | None,
        "nearest_mbta_station": str,
        "drive_seaport_min": float | None,
        "drive_google_min": float | None,
    }
    """
    if lat is None or lng is None:
        coords = geocode_address(address)
        if coords is None:
            return {
                "drive_mbta_min": None,
                "nearest_mbta_station": "Unknown",
                "drive_seaport_min": None,
                "drive_google_min": None,
            }
        lat, lng = coords

    # Find nearest MBTA station
    station_name, station_lat, station_lng = find_nearest_mbta(lat, lng)

    # Build destination list: MBTA station, Seaport, Google Cambridge
    seaport = DESTINATIONS["seaport"]
    google = DESTINATIONS["google_cambridge"]

    dest_list: list[tuple[float, float]] = [
        (station_lat, station_lng),
        (float(seaport["lat"]), float(seaport["lng"])),
        (float(google["lat"]), float(google["lng"])),
    ]

    # Single OSRM table request for all 3 destinations
    durations = _osrm_table(lat, lng, dest_list)
    time.sleep(OSRM_DELAY)

    def to_minutes(seconds: float | None) -> float | None:
        if seconds is None:
            return None
        return round(seconds / 60.0, 1)

    return {
        "drive_mbta_min": to_minutes(durations[0]),
        "nearest_mbta_station": station_name,
        "drive_seaport_min": to_minutes(durations[1]),
        "drive_google_min": to_minutes(durations[2]),
    }
