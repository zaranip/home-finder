"""
Location and price filtering for Zillow listings.
Applies allowlist/blocklist logic using town names, ZIP codes, and address parsing.
"""

from __future__ import annotations

import re
from typing import Any

from .config import (
    ALLOWED_TOWNS,
    ALLOWED_ZIPS,
    BLOCKED_NEIGHBORHOODS,
    BLOCKED_ZIPS,
    MAX_HOA_MONTHLY,
    MAX_PRICE,
)


def normalize(text: str) -> str:
    """Lowercase, strip, collapse whitespace."""
    return re.sub(r"\s+", " ", text.strip().lower())


def extract_zip(address: str) -> str | None:
    """Pull a 5-digit ZIP code from an address string."""
    match = re.search(r"\b(\d{5})\b", address)
    return match.group(1) if match else None


def is_location_allowed(address: str, town_hint: str | None = None) -> bool:
    """
    Check whether a listing's location passes the allow/block filters.

    Strategy:
    1. If address contains a blocked neighborhood name → reject.
    2. If ZIP code is in the block-list → reject.
    3. If ZIP code is in the allow-list → accept.
    4. If town_hint matches an allowed town name → accept.
    5. If address text contains an allowed town name → accept.
    6. Otherwise → reject (conservative).
    """
    addr_lower = normalize(address)
    town_lower = normalize(town_hint) if town_hint else ""

    # Step 1: Block by neighborhood name
    for blocked in BLOCKED_NEIGHBORHOODS:
        if blocked in addr_lower or blocked in town_lower:
            return False

    # Step 2: Block by ZIP
    zip_code = extract_zip(address)
    if zip_code and zip_code in BLOCKED_ZIPS:
        return False

    # Step 3: Allow by ZIP
    if zip_code and zip_code in ALLOWED_ZIPS:
        return True

    # Step 4: Allow by town hint
    allowed_names_lower = {t["name"].lower() for t in ALLOWED_TOWNS}
    if town_lower and town_lower in allowed_names_lower:
        return True

    # Step 5: Allow by address text match
    for town in ALLOWED_TOWNS:
        name: str = town["name"]
        if name.lower() in addr_lower:
            return True

    # Step 6: Default deny
    return False


def resolve_town(address: str, town_hint: str | None = None) -> str | None:
    """
    Resolve which allowed town a listing belongs to.
    Returns the canonical town name or None if not resolvable.
    """
    addr_lower = normalize(address)
    town_lower = normalize(town_hint) if town_hint else ""
    zip_code = extract_zip(address)

    # Match by ZIP first (most reliable)
    if zip_code:
        for town in ALLOWED_TOWNS:
            if zip_code in town["zips"]:
                return town["name"]

    # Match by town hint
    for town in ALLOWED_TOWNS:
        name: str = town["name"]
        if name.lower() == town_lower:
            return name

    # Match by address text
    for town in ALLOWED_TOWNS:
        name = town["name"]
        if name.lower() in addr_lower:
            return name

    return None


def passes_price_filter(price: float | int | None) -> bool:
    """Check if listing price is within budget."""
    if price is None:
        return False
    return price <= MAX_PRICE


def passes_hoa_filter(hoa: float | int | None) -> bool:
    """Check if HOA fee is acceptable. None/0 HOA is always fine."""
    if hoa is None or hoa == 0:
        return True
    return hoa <= MAX_HOA_MONTHLY


def filter_listing(listing: dict[str, Any]) -> bool:
    """
    Apply all filters to a single listing dict.
    Returns True if listing should be KEPT, False if it should be dropped.

    Expected listing keys: address, price, hoa, town (optional)
    """
    address = listing.get("address", "")
    town_hint = listing.get("town")
    price = listing.get("price")
    hoa = listing.get("hoa")

    if not passes_price_filter(price):
        return False

    if not passes_hoa_filter(hoa):
        return False

    if not is_location_allowed(address, town_hint):
        return False

    return True
