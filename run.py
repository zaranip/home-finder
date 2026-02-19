"""
Redfin Listing Finder — Entry point.

Orchestrates: scrape → filter → enrich (driving times, rental estimates) → rate → export to Excel.
Can run as a one-shot script or scheduled via Windows Task Scheduler.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime

from src.config import DATA_DIR, EXCEL_DEFAULTS, LISTINGS_XLSX
from src.driving_times import compute_driving_times
from src.excel_builder import build_workbook
from src.filters import filter_listing, resolve_town
from src.rating import estimate_net_monthly_cost, score_listing
from src.rental_estimate import get_rental_estimate
from src.scraper import scrape_all_towns


def setup_logging(verbose: bool = False) -> None:
    """Configure logging to file and console."""
    log_file = DATA_DIR / "redfin_finder.log"
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


def run(proxy_url: str | None = None, verbose: bool = False) -> None:
    """Execute a full scrape-and-analyze cycle."""
    setup_logging(verbose)
    logger = logging.getLogger("redfin-finder")

    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("Redfin Finder run started at %s", start_time.strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 60)

    # ── Step 1: Scrape ──────────────────────────────────────────────────────
    logger.info("Step 1/5: Scraping Redfin for new listings...")
    raw_listings = scrape_all_towns(proxy_url=proxy_url)
    logger.info("Raw listings from scraper: %d", len(raw_listings))

    if not raw_listings:
        logger.warning("No new listings found. Exiting.")
        return

    # ── Step 2: Filter ──────────────────────────────────────────────────────
    logger.info("Step 2/5: Applying location and price filters...")
    filtered = []
    for listing in raw_listings:
        # Resolve town from address/ZIP
        if not listing.get("town"):
            listing["town"] = resolve_town(listing.get("address", ""))

        if filter_listing(listing):
            filtered.append(listing)
        else:
            logger.debug("Filtered out: %s (price=%s, hoa=%s)",
                         listing.get("address"), listing.get("price"), listing.get("hoa"))

    logger.info("After filtering: %d listings", len(filtered))

    if not filtered:
        logger.warning("All listings filtered out. Exiting.")
        return

    # ── Step 3: Enrich with driving times ───────────────────────────────────
    logger.info("Step 3/5: Computing driving times (OSRM + Nominatim)...")
    for i, listing in enumerate(filtered, 1):
        address = listing.get("address", "")
        logger.info("  [%d/%d] Driving times for: %s", i, len(filtered), address)

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

    # ── Step 4: Rental estimates + rating ───────────────────────────────────
    logger.info("Step 4/5: Estimating rentals and computing ratings...")
    enriched = []
    for listing in filtered:
        # Rental estimate for roommate offset
        rental_est = get_rental_estimate(
            town=listing.get("town"),
            rent_zestimate=listing.get("rent_zestimate"),
            beds=listing.get("beds"),
        )
        listing["rental_estimate"] = rental_est

        # Estimate net monthly cost (for rating — Excel has its own formula)
        net_cost = estimate_net_monthly_cost(
            price=listing.get("price", 0),
            hoa=listing.get("hoa", 0),
            rental_estimate=rental_est,
            **EXCEL_DEFAULTS,
        )
        listing["net_monthly_cost"] = net_cost

        # Rating
        score, color, category_scores = score_listing(listing)
        listing["rating_score"] = score
        listing["rating_color"] = color
        listing["category_scores"] = category_scores

        # Ensure parking is a string
        if listing.get("parking") is None:
            listing["parking"] = "Unknown"
        elif isinstance(listing["parking"], list):
            listing["parking"] = ", ".join(listing["parking"])

        # Ensure in_unit_laundry is bool
        if listing.get("in_unit_laundry") is None:
            listing["in_unit_laundry"] = False

        enriched.append(listing)

    # Sort by rating score (best first)
    enriched.sort(key=lambda x: x.get("rating_score", 0), reverse=True)

    # ── Step 5: Export to Excel ─────────────────────────────────────────────
    logger.info("Step 5/5: Building Excel workbook...")
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Use timestamped filename to preserve history
    timestamp = start_time.strftime("%Y%m%d_%H%M%S")
    output_path = DATA_DIR / f"listings_{timestamp}.xlsx"

    build_workbook(enriched, output_path)
    logger.info("Workbook saved: %s", output_path)

    # Also save/update the main listings file
    build_workbook(enriched, LISTINGS_XLSX)
    logger.info("Updated main workbook: %s", LISTINGS_XLSX)

    # ── Summary ─────────────────────────────────────────────────────────────
    elapsed = (datetime.now() - start_time).total_seconds()
    green_count = sum(1 for l in enriched if l["rating_color"] == "Green")
    yellow_count = sum(1 for l in enriched if l["rating_color"] == "Yellow")
    red_count = sum(1 for l in enriched if l["rating_color"] == "Red")

    logger.info("=" * 60)
    logger.info("Run complete in %.1f seconds", elapsed)
    logger.info("Total listings: %d", len(enriched))
    logger.info("  Green: %d | Yellow: %d | Red: %d", green_count, yellow_count, red_count)
    logger.info("Output: %s", output_path)
    logger.info("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Redfin Finder — Scrape and analyze Boston-area listings"
    )
    parser.add_argument(
        "--proxy",
        type=str,
        default=None,
        help="Proxy URL (e.g., http://user:pass@host:port). Recommended for reliability.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()
    run(proxy_url=args.proxy, verbose=args.verbose)


if __name__ == "__main__":
    main()
