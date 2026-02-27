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
from src.store import load_store, save_store


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
    
    # ── Step 1: Load existing listings from store ─────────────────────────
    store = load_store()
    logger.info("Loaded %d existing listings from store", len(store))
    
    # ── Step 2: Scrape ─────────────────────────────────────────────────────
    logger.info("Step 2/6: Scraping Redfin for new listings...")
    raw_listings, active_ids = scrape_all_towns(proxy_url=proxy_url)
    logger.info("New listings from scraper: %d | Active on Redfin: %d", len(raw_listings), len(active_ids))
    
    # ── Step 3: Prune stale listings ───────────────────────────────────────
    stale_ids = set(store.keys()) - active_ids
    if stale_ids:
        logger.info("Step 3/6: Removing %d stale listings no longer on Redfin...", len(stale_ids))
        for sid in stale_ids:
            logger.debug("  Removed stale: %s — %s", sid, store[sid].get("address", "?"))
            del store[sid]
    else:
        logger.info("Step 3/6: No stale listings to remove")
    
    if not raw_listings and not stale_ids:
        logger.info("No new listings and nothing to prune. Store unchanged.")
        # Still export in case this is the first run with existing store
        if store:
            all_listings = sorted(store.values(), key=lambda x: x.get("rating_score", 0), reverse=True)
            _export(all_listings, start_time, logger)
        return
    
    # ── Step 4: Filter new listings ─────────────────────────────────────────
    logger.info("Step 4/6: Filtering new listings...")
    filtered = []
    for listing in raw_listings:
        if not listing.get("town"):
            listing["town"] = resolve_town(listing.get("address", ""))
    
        if filter_listing(listing):
            filtered.append(listing)
        else:
            logger.debug("Filtered out: %s (price=%s, hoa=%s)",
                         listing.get("address"), listing.get("price"), listing.get("hoa"))
    
    logger.info("New listings after filtering: %d", len(filtered))
    
    # ── Step 5: Enrich new listings ─────────────────────────────────────────
    if filtered:
        logger.info("Step 5/6: Enriching %d new listings...", len(filtered))
    
        # 5a: Driving times
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
    
        # 5b: Rental estimates + rating
        for listing in filtered:
            rental_est = get_rental_estimate(
                town=listing.get("town"),
                rent_zestimate=listing.get("rent_zestimate"),
                beds=listing.get("beds"),
            )
            listing["rental_estimate"] = rental_est
    
            net_cost = estimate_net_monthly_cost(
                price=listing.get("price", 0),
                hoa=listing.get("hoa", 0),
                rental_estimate=rental_est,
                **EXCEL_DEFAULTS,
            )
            listing["net_monthly_cost"] = net_cost
    
            score, color, category_scores = score_listing(listing)
            listing["rating_score"] = score
            listing["rating_color"] = color
            listing["category_scores"] = category_scores
    
            if listing.get("parking") is None:
                listing["parking"] = "Unknown"
            elif isinstance(listing["parking"], list):
                listing["parking"] = ", ".join(listing["parking"])
    
            if listing.get("in_unit_laundry") is None:
                listing["in_unit_laundry"] = False
    
            # Merge into store
            store[listing["zpid"]] = listing
    else:
        logger.info("Step 5/6: No new listings to enrich")
    
    # ── Step 6: Export to Excel ────────────────────────────────────────────
    all_listings = sorted(store.values(), key=lambda x: x.get("rating_score", 0), reverse=True)
    _export(all_listings, start_time, logger)
    
    # Persist store
    save_store(store)
    logger.info("Store saved: %d listings", len(store))
    
    # ── Summary ─────────────────────────────────────────────────────────────
    elapsed = (datetime.now() - start_time).total_seconds()
    green_count = sum(1 for l in all_listings if l.get("rating_color") == "Green")
    yellow_count = sum(1 for l in all_listings if l.get("rating_color") == "Yellow")
    red_count = sum(1 for l in all_listings if l.get("rating_color") == "Red")
    
    logger.info("=" * 60)
    logger.info("Run complete in %.1f seconds", elapsed)
    logger.info("Total listings in workbook: %d (new: %d, removed: %d)",
                len(all_listings), len(filtered), len(stale_ids))
    logger.info("  Green: %d | Yellow: %d | Red: %d", green_count, yellow_count, red_count)
    logger.info("=" * 60)


def _export(listings: list[dict], start_time: datetime, logger: logging.Logger) -> None:
    """Write listings to both timestamped and main Excel workbooks."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    timestamp = start_time.strftime("%Y%m%d_%H%M%S")
    output_path = DATA_DIR / f"listings_{timestamp}.xlsx"
    
    logger.info("Step 6/6: Building Excel workbook (%d listings)...", len(listings))
    build_workbook(listings, output_path)
    logger.info("Workbook saved: %s", output_path)
    
    build_workbook(listings, LISTINGS_XLSX)
    logger.info("Updated main workbook: %s", LISTINGS_XLSX)


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
