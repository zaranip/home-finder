"""
Rental price estimation for roommate offset calculations.

Uses Zillow Rent Zestimate when available (scraped from listing detail),
falls back to per-town median 1BR rent from config.
"""

from __future__ import annotations

import logging

from .config import FALLBACK_RENTS

logger = logging.getLogger(__name__)


def get_rental_estimate(
    town: str | None,
    rent_zestimate: int | float | None = None,
    beds: int | None = None,
) -> int:
    """
    Estimate the monthly rental income from a roommate.

    The owner occupies one bedroom, so only units with 2+ bedrooms
    generate roommate income.  A 1BR or studio yields $0.

    Strategy:
    1. If beds < 2 → return 0 (no spare bedroom for a roommate).
    2. If Rent Zestimate is available, estimate the roommate's share
       as (zestimate / beds) * 1.05  (one room + shared-area premium).
    3. Otherwise, fall back to per-town median 1BR rent discounted to
       ~65% (reflects renting a room in a shared unit, not a full 1BR).

    Returns: estimated monthly rent a roommate would pay (int).
    """
    # Owner occupies one bedroom — no roommate income from studios / 1BRs
    if not beds or beds < 2:
        return 0

    # If we have a Rent Zestimate, use proportional per-room share
    if rent_zestimate and rent_zestimate > 0:
        rent_zestimate_int = int(rent_zestimate)
        per_room = rent_zestimate_int // beds
        # Slight premium for shared common areas
        return int(per_room * 1.05)

    # Fallback to town-level median (discounted for room-in-shared-unit)
    if town and town in FALLBACK_RENTS:
        return int(FALLBACK_RENTS[town] * 0.65)

    # Last resort: Boston metro average for a room in a shared unit
    logger.warning("No rental data for town=%s, using metro average", town)
    return int(1_800 * 0.65)
