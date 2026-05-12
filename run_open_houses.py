"""
Open House Finder — Entry point.

Scrapes Redfin for listings in the configured ZIP codes that have an
upcoming open house within a user-specified window (weeks or months),
then exports them to a dedicated spreadsheet sorted chronologically.

This applies broader filters than run.py: it ignores the HOA cap and
keeps the full MAX_PRICE budget so you can scout open houses outside
your tighter "would actually buy" criteria.

Usage:
    python run_open_houses.py --w 5    # next 5 weeks
    python run_open_houses.py --m 3    # next 3 months
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

from src.config import ALLOWED_TOWNS, DATA_DIR, MAX_PRICE
from src.open_house_excel import build_open_house_workbook
from src.scraper import (
    extract_listing,
    resolve_all_zips,
    search_zip,
    _delay,
)


def setup_logging(verbose: bool = False) -> None:
    log_file = DATA_DIR / "open_houses.log"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def _parse_iso(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def find_open_houses(window_end: datetime, logger: logging.Logger) -> list[dict]:
    """Scrape every configured ZIP and return listings whose next open house
    falls between now and window_end."""
    region_cache = resolve_all_zips()
    now = datetime.now()

    zip_to_town: dict[str, str] = {}
    for town in ALLOWED_TOWNS:
        for z in town["zips"]:
            zip_to_town[z] = town["name"]

    matches: list[dict] = []
    seen_pids: set[str] = set()

    for zip_code, town_name in zip_to_town.items():
        region_info = region_cache.get(zip_code)
        if not region_info:
            logger.warning("No region_id for ZIP %s (%s), skipping", zip_code, town_name)
            continue

        label = f"{town_name} ({zip_code})"
        logger.info("Searching %s...", label)
        homes = search_zip(label, region_info["region_id"], region_info["region_type"])
        _delay(2, 5)

        for home in homes:
            listing = extract_listing(home, town_name)
            if listing is None:
                continue

            pid = listing["zpid"]
            if pid in seen_pids:
                continue
            seen_pids.add(pid)

            start = _parse_iso(listing.get("open_house_start"))
            if start is None:
                continue

            if start < now or start > window_end:
                continue

            price = listing.get("price")
            if price is None or price > MAX_PRICE:
                continue

            # Coerce ISO strings to datetimes for the excel writer
            listing["open_house_start"] = start
            listing["open_house_end"] = _parse_iso(listing.get("open_house_end"))
            matches.append(listing)

    return matches


def run(weeks: int | None, months: int | None, verbose: bool = False) -> None:
    setup_logging(verbose)
    logger = logging.getLogger("open-houses")

    if weeks is not None:
        window_days = weeks * 7
        window_label = f"{weeks} week{'s' if weeks != 1 else ''}"
    else:
        # Approximate a month as 30 days
        window_days = months * 30
        window_label = f"{months} month{'s' if months != 1 else ''}"

    now = datetime.now()
    window_end = now + timedelta(days=window_days)

    logger.info("=" * 60)
    logger.info("Open House Finder — window: next %s (until %s)",
                window_label, window_end.strftime("%Y-%m-%d"))
    logger.info("=" * 60)

    matches = find_open_houses(window_end, logger)
    logger.info("Found %d listings with open houses in window", len(matches))

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    output_path: Path = DATA_DIR / f"open_houses_{timestamp}.xlsx"
    main_path: Path = DATA_DIR / "open_houses.xlsx"

    build_open_house_workbook(matches, output_path)
    build_open_house_workbook(matches, main_path)
    logger.info("Workbook saved: %s", output_path)
    logger.info("Updated main workbook: %s", main_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Open House Finder — find upcoming Redfin open houses in your ZIPs",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--w", type=int, metavar="N", help="Window in weeks (e.g. --w 5)")
    group.add_argument("--m", type=int, metavar="N", help="Window in months (e.g. --m 3)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    if (args.w is not None and args.w <= 0) or (args.m is not None and args.m <= 0):
        parser.error("Window must be a positive integer")

    run(weeks=args.w, months=args.m, verbose=args.verbose)


if __name__ == "__main__":
    main()
