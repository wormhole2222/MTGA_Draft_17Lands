"""
src/combo_loader.py
Loads two-card combo definitions for a given set and checks for matches
between the current pack and the player's drafted pool.
"""

import os
from typing import List, Tuple
from src.constants import COMBOS_FOLDER


def get_combo_file_path(set_code: str) -> str:
    return os.path.join(COMBOS_FOLDER, f"{set_code}_combos.txt")


def combo_file_exists(set_code: str) -> bool:
    return os.path.isfile(get_combo_file_path(set_code))


def load_combos(set_code: str) -> List[Tuple[List[str], List[str]]]:
    """
    Parses the combo file for a set and returns a list of (left_cards, right_cards) tuples.
    Each side is a list of card names — any card on a side can satisfy that half of the combo.
    """
    path = get_combo_file_path(set_code)
    if not os.path.isfile(path):
        return []

    combos = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or "/" not in line:
                continue
            parts = line.split("/", 1)
            if len(parts) != 2:
                continue
            left = [c.strip() for c in parts[0].split("|") if c.strip()]
            right = [c.strip() for c in parts[1].split("|") if c.strip()]
            if left and right:
                combos.append((left, right))
    return combos


def find_combo_alerts(
    pack_cards: List[dict],
    taken_cards: List[dict],
    combos: List[Tuple[List[str], List[str]]],
) -> List[dict]:
    """
    For each card in the pack, checks if any combo partner is already in the pool.
    Groups matches per pack card — duplicates are counted, different partners are merged.
    Returns a list of alert dicts sorted by contextual_score descending, max 5.

    Each alert dict has:
        card_name: str               - the pack card
        combo_partners: list[tuple]  - list of (partner_name, count) sorted by count desc
        score: float                 - the pack card's contextual_score (for sorting)
    """
    taken_names = [c.get("name", "") for c in taken_cards]

    # Build per-pack-card partner counts: {pack_name: {partner_name: count}}
    matches: dict = {}

    for pack_card in pack_cards:
        pack_name = pack_card.get("name", "")
        score = float(pack_card.get("contextual_score", 0.0))

        for left, right in combos:
            if pack_name in left:
                for drafted in taken_names:
                    if drafted in right:
                        if pack_name not in matches:
                            matches[pack_name] = {"score": score, "partners": {}}
                        matches[pack_name]["partners"][drafted] = (
                            matches[pack_name]["partners"].get(drafted, 0) + 1
                        )

            if pack_name in right:
                for drafted in taken_names:
                    if drafted in left:
                        if pack_name not in matches:
                            matches[pack_name] = {"score": score, "partners": {}}
                        matches[pack_name]["partners"][drafted] = (
                            matches[pack_name]["partners"].get(drafted, 0) + 1
                        )

    alerts = []
    for card_name, data in matches.items():
        partners = sorted(data["partners"].items(), key=lambda x: x[1], reverse=True)
        alerts.append({
            "card_name": card_name,
            "combo_partners": partners,  # list of (name, count)
            "score": data["score"],
        })

    alerts.sort(key=lambda x: x["score"], reverse=True)
    return alerts[:5]
