"""
Multi-category rating engine for Zillow listings.

Scores each listing across weighted categories and assigns a
Green / Yellow / Red color rating.
"""

from __future__ import annotations

from typing import Any

from .config import (
    RATING_GREEN_MIN,
    RATING_THRESHOLDS,
    RATING_WEIGHTS,
    RATING_YELLOW_MIN,
)


def _score_lower_is_better(value: float | int | None, green_max: float, red_min: float) -> int:
    """
    Score a metric where lower values are better (price, HOA, commute time).
    Returns 3 (green), 2 (yellow), or 1 (red).
    """
    if value is None:
        return 2  # neutral if unknown
    if value <= green_max:
        return 3
    if value >= red_min:
        return 1
    return 2


def _score_boolean(value: bool | None, good_value: bool = True) -> int:
    """Score a boolean feature (laundry, parking). 3 if good, 1 if bad, 2 if unknown."""
    if value is None:
        return 2
    return 3 if value == good_value else 1


def score_listing(listing: dict[str, Any]) -> tuple[float, str, dict[str, int]]:
    """
    Compute a weighted rating score for a listing.

    Returns:
        (score, color, category_scores)
        - score: float 1.0–3.0
        - color: "Green", "Yellow", or "Red"
        - category_scores: dict of individual category scores (1–3)
    """
    scores: dict[str, int] = {}

    # Price
    thresholds = RATING_THRESHOLDS["price"]
    scores["price"] = _score_lower_is_better(listing.get("price"), thresholds[0], thresholds[1])

    # Price per bedroom
    thresholds = RATING_THRESHOLDS["price_per_bed"]
    beds = listing.get("beds")
    price_per_bed = listing.get("price", 0) / beds if beds and beds > 0 else None
    scores["price_per_bed"] = _score_lower_is_better(price_per_bed, thresholds[0], thresholds[1])

    # HOA
    thresholds = RATING_THRESHOLDS["hoa"]
    hoa = listing.get("hoa") or 0
    scores["hoa"] = _score_lower_is_better(hoa, thresholds[0], thresholds[1])

    # Net monthly cost (after roommate)
    thresholds = RATING_THRESHOLDS["net_monthly_cost"]
    net_cost = listing.get("net_monthly_cost")
    scores["net_monthly_cost"] = _score_lower_is_better(net_cost, thresholds[0], thresholds[1])

    # Commute to Seaport
    thresholds = RATING_THRESHOLDS["commute_seaport"]
    scores["commute_seaport"] = _score_lower_is_better(
        listing.get("drive_seaport_min"), thresholds[0], thresholds[1]
    )

    # Commute to Google Cambridge
    thresholds = RATING_THRESHOLDS["commute_google"]
    scores["commute_google"] = _score_lower_is_better(
        listing.get("drive_google_min"), thresholds[0], thresholds[1]
    )

    # MBTA proximity
    thresholds = RATING_THRESHOLDS["mbta_proximity"]
    scores["mbta_proximity"] = _score_lower_is_better(
        listing.get("drive_mbta_min"), thresholds[0], thresholds[1]
    )

    # In-unit laundry
    scores["in_unit_laundry"] = _score_boolean(listing.get("in_unit_laundry"))

    # Parking
    parking = listing.get("parking", "")
    has_parking = bool(parking and parking.lower() not in ("none listed", "none", ""))
    scores["parking"] = _score_boolean(has_parking)

    # Size (sqft / bedrooms)
    sqft = listing.get("sqft")
    beds = listing.get("beds")
    if sqft and sqft >= 900:
        scores["size"] = 3
    elif beds and beds >= 2:
        scores["size"] = 3
    elif sqft and sqft >= 700:
        scores["size"] = 2
    elif sqft and sqft < 700:
        scores["size"] = 1
    else:
        scores["size"] = 2  # unknown → neutral

    # Weighted total
    total = 0.0
    for category, weight in RATING_WEIGHTS.items():
        total += scores.get(category, 2) * weight

    # Determine color
    if total >= RATING_GREEN_MIN:
        color = "Green"
    elif total >= RATING_YELLOW_MIN:
        color = "Yellow"
    else:
        color = "Red"

    return round(total, 2), color, scores


def estimate_net_monthly_cost(
    price: int | float,
    hoa: int | float,
    rental_estimate: int | float,
    interest_rate: float = 0.065,
    down_payment_pct: float = 0.20,
    loan_term_years: int = 30,
    property_tax_rate: float = 0.012,
    insurance_monthly: int = 150,
    utilities_monthly: int = 250,
    internet_monthly: int = 60,
) -> float:
    """
    Estimate net monthly cost in Python (for rating purposes).
    The Excel sheet has its own formula-based version with adjustable assumptions.

    Returns: estimated net monthly cost after roommate offset.
    """
    down_payment = price * down_payment_pct
    loan_amount = price - down_payment
    monthly_rate = interest_rate / 12
    n_payments = loan_term_years * 12

    # PMT formula
    if monthly_rate > 0:
        mortgage = loan_amount * (monthly_rate * (1 + monthly_rate) ** n_payments) / (
            (1 + monthly_rate) ** n_payments - 1
        )
    else:
        mortgage = loan_amount / n_payments

    property_tax_mo = price * property_tax_rate / 12
    total = mortgage + hoa + property_tax_mo + insurance_monthly + utilities_monthly + internet_monthly
    net = total - rental_estimate

    return round(net, 2)
