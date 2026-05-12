"""
Redfin Multi-Family Listing Finder — Entry point.

Mirrors run.py but targets only multi-family (duplex, triplex, 2–4 unit) listings
and writes to listings_mfh.xlsx with per-unit bedroom breakdowns.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime

from src.config import (
    DATA_DIR,
    EXCEL_DEFAULTS,
    LISTINGS_STORE_MFH,
    LISTINGS_XLSX_MFH,
    SEEN_IDS_FILE_MFH,
)
from src.driving_times import compute_driving_times
from src.excel_builder_mfh import build_workbook
from src.filters import filter_listing, resolve_town
from src.rating import estimate_net_monthly_cost, score_listing
from src.rental_estimate import get_rental_estimate
from src.scraper import fetch_listing_details, scrape_all_towns
from src.store import load_store, save_store


REDFIN_MFH_UIPT = "4"  # Redfin property-type code for Multi-Family


def setup_logging(verbose: bool = False) -> None:
    log_file = DATA_DIR / "redfin_finder_mfh.log"
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    logging.basicConfig(
        level=level,
        format=fmt,
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def _is_multi_family(listing: dict) -> bool:
    """Client-side MFH check — tolerant of unknown property_type codes."""
    pt = listing.get("property_type")
    ui_pt = listing.get("ui_property_type")
    # Redfin MFH is typically property_type=5 or uiPropertyType=4.
    # Accept either, and also any listing with parsed unit data.
    if pt in (5, "5"):
        return True
    if ui_pt in (4, "4"):
        return True
    if listing.get("num_units") and listing["num_units"] >= 2:
        return True
    return False


def run(proxy_url: str | None = None, verbose: bool = False) -> None:
    """Full MFH scrape-and-analyze cycle."""
    setup_logging(verbose)
    logger = logging.getLogger("redfin-finder-mfh")

    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("Redfin MFH Finder run started at %s", start_time.strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 60)

    store = load_store(LISTINGS_STORE_MFH)
    logger.info("Loaded %d existing MFH listings from store", len(store))

    logger.info("Step 2/6: Scraping Redfin for new multi-family listings...")
    raw_listings, active_ids = scrape_all_towns(
        proxy_url=proxy_url,
        uipt=REDFIN_MFH_UIPT,
        seen_ids_path=SEEN_IDS_FILE_MFH,
    )
    logger.info("New listings from scraper: %d | Active on Redfin: %d",
                len(raw_listings), len(active_ids))

    stale_ids = set(store.keys()) - active_ids
    if stale_ids:
        logger.info("Step 3/6: Removing %d stale MFH listings...", len(stale_ids))
        for sid in stale_ids:
            del store[sid]
    else:
        logger.info("Step 3/6: No stale listings to remove")

    if not raw_listings and not stale_ids:
        logger.info("No new listings and nothing to prune. Store unchanged.")
        if store:
            all_listings = sorted(store.values(), key=lambda x: x.get("rating_score", 0), reverse=True)
            _export(all_listings, start_time, logger)
        return

    logger.info("Step 4/6: Filtering new listings...")
    filtered: list[dict] = []
    for listing in raw_listings:
        if not listing.get("town"):
            listing["town"] = resolve_town(listing.get("address", ""))

        if not filter_listing(listing):
            continue

        filtered.append(listing)

    logger.info("New listings after location/price filter: %d", len(filtered))

    if filtered:
        logger.info("Step 5/6: Enriching %d new listings...", len(filtered))

        for i, listing in enumerate(filtered, 1):
            address = listing.get("address", "")
            logger.info("  [%d/%d] Driving times + details for: %s", i, len(filtered), address)

            try:
                times = compute_driving_times(
                    address,
                    lat=listing.get("latitude"),
                    lng=listing.get("longitude"),
                )
                listing.update(times)
            except Exception:
                logger.exception("  Failed to compute driving times for %s", address)
                listing["drive_mbta_min"] = None
                listing["nearest_mbta_station"] = "Error"
                listing["drive_seaport_min"] = None
                listing["drive_google_min"] = None

            try:
                details = fetch_listing_details(listing["zpid"])
            except Exception:
                logger.exception("  Failed to fetch details for %s", address)
                details = None

            if details is not None:
                if listing.get("in_unit_laundry") is None:
                    listing["in_unit_laundry"] = details["in_unit_laundry"]

                features = details.get("parking_features") or []
                if features:
                    existing = listing.get("parking")
                    if existing and existing != "Unknown" and "space" in str(existing).lower():
                        listing["parking"] = f"{existing} ({', '.join(features)})"
                    else:
                        listing["parking"] = ", ".join(features)

                listing["num_units"] = details.get("num_units")
                listing["unit_bedrooms"] = details.get("unit_bedrooms") or []

        # Drop listings that don't look multi-family (server filter can be noisy)
        mfh_filtered = [l for l in filtered if _is_multi_family(l)]
        dropped = len(filtered) - len(mfh_filtered)
        if dropped:
            logger.info("  Dropped %d non-MFH listings after enrichment", dropped)
        filtered = mfh_filtered

        for listing in filtered:
            rental_est = get_rental_estimate(
                town=listing.get("town"),
                rent_zestimate=listing.get("rent_zestimate"),
                beds=listing.get("beds"),
            )
            listing["rental_estimate"] = rental_est

            # For MFH net cost, the owner occupies one bedroom of the building
            # and rents every other bedroom across all units.
            unit_beds = listing.get("unit_bedrooms") or []
            if isinstance(unit_beds, list) and unit_beds:
                total_beds = sum(int(b) for b in unit_beds)
            else:
                total_beds = listing.get("beds") or 0

            net_cost = estimate_net_monthly_cost(
                price=listing.get("price", 0),
                hoa=listing.get("hoa", 0),
                rental_estimate=rental_est,
                beds=total_beds,
                **EXCEL_DEFAULTS,
            )
            listing["net_monthly_cost"] = net_cost

            # Score uses total_beds in place of beds so price-per-bed reflects
            # the full building, not just the owner's unit.
            score_view = dict(listing)
            score_view["beds"] = total_beds
            score, color, category_scores = score_listing(score_view)
            listing["rating_score"] = score
            listing["rating_color"] = color
            listing["category_scores"] = category_scores

            if listing.get("parking") is None:
                listing["parking"] = "Unknown"
            elif isinstance(listing["parking"], list):
                listing["parking"] = ", ".join(listing["parking"])

            if listing.get("in_unit_laundry") is None:
                listing["in_unit_laundry"] = False

            store[listing["zpid"]] = listing
    else:
        logger.info("Step 5/6: No new listings to enrich")

    all_listings = sorted(store.values(), key=lambda x: x.get("rating_score", 0), reverse=True)
    _export(all_listings, start_time, logger)

    save_store(store, LISTINGS_STORE_MFH)
    logger.info("Store saved: %d MFH listings", len(store))

    elapsed = (datetime.now() - start_time).total_seconds()
    green_count = sum(1 for l in all_listings if l.get("rating_color") == "Green")
    yellow_count = sum(1 for l in all_listings if l.get("rating_color") == "Yellow")
    red_count = sum(1 for l in all_listings if l.get("rating_color") == "Red")

    logger.info("=" * 60)
    logger.info("MFH run complete in %.1f seconds", elapsed)
    logger.info("Total listings in workbook: %d (new: %d, removed: %d)",
                len(all_listings), len(filtered), len(stale_ids))
    logger.info("  Green: %d | Yellow: %d | Red: %d", green_count, yellow_count, red_count)
    logger.info("=" * 60)


def _export(listings: list[dict], start_time: datetime, logger: logging.Logger) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = start_time.strftime("%Y%m%d_%H%M%S")
    output_path = DATA_DIR / f"listings_mfh_{timestamp}.xlsx"

    logger.info("Step 6/6: Building MFH Excel workbook (%d listings)...", len(listings))
    build_workbook(listings, output_path)
    logger.info("Workbook saved: %s", output_path)

    build_workbook(listings, LISTINGS_XLSX_MFH)
    logger.info("Updated main MFH workbook: %s", LISTINGS_XLSX_MFH)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Redfin MFH Finder — Scrape and analyze multi-family listings"
    )
    parser.add_argument("--proxy", type=str, default=None)
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()
    run(proxy_url=args.proxy, verbose=args.verbose)


if __name__ == "__main__":
    main()
