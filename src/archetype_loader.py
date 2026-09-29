"""
src/archetype_loader.py
Loads set-specific archetype definitions and counts matching cards in the draft pool.
"""

import json
import os
import logging
from typing import Any, Optional

from src import constants

logger = logging.getLogger(__name__)


def get_archetype_file_path(set_code: str) -> str:
    name = f"{set_code}_archetypes.json"
    path = os.path.join(constants.ARCHETYPES_FOLDER, name)
    # Mac/Linux builds have no Archetypes folder beside the app; use the bundled copy.
    return path if os.path.isfile(path) else os.path.join(constants.RESOURCE_DIR, "Archetypes", name)


def archetype_file_exists(set_code: str) -> bool:
    """Returns True if an archetypes file exists for the given set code."""
    return os.path.isfile(get_archetype_file_path(set_code))


def load_archetypes(set_code: str) -> Optional[dict]:
    """Loads and returns the archetypes data for a given set code, or None on failure."""
    path = get_archetype_file_path(set_code)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load archetypes for {set_code}: {e}")
        return None


def get_archetype_counts(
    archetype_key: str,
    pool_cards: list[str],
    archetypes_data: dict,
) -> list[dict]:
    """
    Given a selected archetype key and the list of card names in the draft pool,
    returns a list of category result dicts:
        [{"name": "Removal", "count": 3}, ...]

    Duplicates in pool_cards count multiple times.
    """
    archetype = archetypes_data.get(archetype_key)
    if not archetype:
        return []

    results = []
    for category in archetype.get("categories", []):
        card_set = category.get("cards", [])
        repeatable_set = set(category.get("repeatable_cards", []))

        # Count non-repeatable cards + repeatable cards for total
        all_cards = set(card_set) | repeatable_set

        # Build matched card counts (preserving duplicates)
        matched_counts: dict[str, int] = {}
        for card in pool_cards:
            if card in all_cards:
                matched_counts[card] = matched_counts.get(card, 0) + 1

        total = sum(matched_counts.values())
        repeatable_count = sum(1 for card in pool_cards if card in repeatable_set)

        entry = {"name": category["name"], "count": total, "matched_cards": matched_counts}
        if repeatable_set:
            entry["repeatable_count"] = repeatable_count
        results.append(entry)

    return results
