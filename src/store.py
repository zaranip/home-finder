"""
JSON-backed persistence for enriched listings.

The store keeps all enriched listing dicts keyed by zpid so that
subsequent pipeline runs can merge new listings in and prune stale ones
without losing previously computed data (driving times, ratings, etc.).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .config import LISTINGS_STORE

logger = logging.getLogger(__name__)


def load_store(path: Path = LISTINGS_STORE) -> dict[str, dict[str, Any]]:
    """Load existing enriched listings from disk, keyed by zpid."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return {item["zpid"]: item for item in data if "zpid" in item}
        return data
    except (json.JSONDecodeError, TypeError, KeyError):
        logger.warning("Corrupt listings store — starting fresh")
        return {}


def save_store(listings: dict[str, dict[str, Any]], path: Path = LISTINGS_STORE) -> None:
    """Persist enriched listings to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(listings, indent=2), encoding="utf-8")
