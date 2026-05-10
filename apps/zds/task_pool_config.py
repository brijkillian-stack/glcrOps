"""
task_pool_config.py — Static task pool for the ZDS inline task picker.

Organized into three shift-context categories:
  porter  — general grave-shift porter duties (zones, RR, aux)
  pm_ol   — PM overlap window tasks (11PM – 1AM)
  am_ol   — AM overlap window tasks (5AM – 7AM)

Edit this file to update the pool.  Future enhancement: migrate to
a DB-backed task_pool table so the pool can be managed from the UI.
"""

from typing import TypedDict


class PoolTask(TypedDict):
    name: str
    note: str   # brief description shown on hover (optional)


TASK_POOL: dict[str, list[str]] = {
    "porter": [
        # Zones
        "Slot machine tray wipe",
        "Slot top & surround wipe",
        "Vacuum zone aisle",
        "Zone sweep & mop",
        "Empty zone trash cans",
        "Sanitize high-touch surfaces",
        "Check for spills / spot clean",
        "Machine glass wipe-down",
        # Restrooms
        "Full restroom clean",
        "Restroom restock (paper / soap)",
        "Restroom spot check",
        "Urinal / toilet scrub",
        "Mirror & sink wipe",
        # General
        "Take trash to compactor",
        "Restock supply cart",
        "Sweep / mop entrance",
        "Polish entrance glass",
        "Lobby vacuum",
        "Break room clean",
        "Elevator / escalator wipe",
        # Sweepers
        "Sweeper 5 / 8 / HL",
        "Sweeper 9 / 10 / SR",
        # Trash & laundry
        "Empty Oasis trash (Fri & Sat)",
        "Empty Annex trash",
        "Pick up laundry (4AM)",
        # Poker Room
        "Vacuum carpet — Poker Room",
        "Clean black trays — Poker Room",
        "Clean table cup inserts — Poker Room",
        "Remove gum — Poker Room",
        "Clean under/behind/inside trash receptacles",
        "Deep-clean Oasis (during shutdown)",
        "Vacuum inside Table Games Pits",
    ],
    "pm_ol": [
        # Hand-off / transition
        "PM sweep before grave",
        "Confirm zone coverage with PM",
        "Spot clean high-traffic areas",
        "Restock supplies for grave",
        "Secure PM equipment",
        # Quick checks
        "Entrance / exit check",
        "Trash pull — main floor",
        "Restroom quick-check",
        "Report any open maintenance issues",
    ],
    "am_ol": [
        # Pre-opening
        "Pre-opening floor inspection",
        "Final trash run",
        "Entrance deep clean",
        "Restock restroom supplies",
        "Inspect all slot machine rows",
        "Vacuum high-traffic paths",
        "Wipe down podiums / stations",
        # Hand-off
        "Coordinate day-shift hand-off",
        "Report overnight incidents",
        "Zone sign-off checklist",
    ],
}


# Ordered list of categories with display labels
POOL_CATEGORIES: list[tuple[str, str]] = [
    ("porter", "Porter"),
    ("pm_ol",  "PM OL"),
    ("am_ol",  "AM OL"),
]
