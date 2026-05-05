"""
GLCR Engine — shared configuration constants (5/3/26)

Single source of truth for slot categorization, area mapping, zone adjacency.
Imported by both fill_engine.py and glcr_engine/scorecard.py to prevent the
two-source drift that existed in the post-Phase-1 layout.
"""

# Slot category map — used by preference/accommodation targets like "category:sweeper"
SLOT_CATEGORY = {}
for s in ("Trash1", "Trash2"):
    SLOT_CATEGORY[s] = "trash"
for s in ("MRR1", "MRR6", "MRR7", "MRR8", "MRR10",
          "WRR1", "WRR6", "WRR7", "WRR8", "WRR10"):
    SLOT_CATEGORY[s] = "restroom"
for s in ("MP1", "MP2", "Support1", "Support2", "Support3"):
    SLOT_CATEGORY[s] = "support"
for s in ("Zone1", "Zone2", "Zone3", "Zone4", "Zone5",
          "Zone6", "Zone7", "Zone8", "Zone9", "Zone10"):
    SLOT_CATEGORY[s] = "zone"
SLOT_CATEGORY["Admin"]      = "admin"
SLOT_CATEGORY["Zone9SR"]    = "smoke_room"
SLOT_CATEGORY["Z9SRBuddy"]  = "smoke_room"

# Sweeper-tagged slots — accommodations targeting "category:sweeper" cover these
SWEEPER_TAGGED_SLOTS = {"Trash1", "Trash2", "Zone7", "Zone8", "Zone9", "Zone10"}

# Slot → floor area map. Used for area-diversity scoring + same-area pair affinity.
SLOT_TO_AREA = {
    "Zone1": "Lobby", "Zone2": "Lobby", "MRR1": "Lobby", "WRR1": "Lobby",
    "Zone3": "C3", "Zone4": "C4", "Zone5": "C5",
    "Zone6": "Z6", "MRR6": "Z6", "WRR6": "Z6",
    "Zone7": "Z7", "MRR7": "Z7", "WRR7": "Z7",
    "Zone8": "Z8", "MRR8": "Z8", "WRR8": "Z8",
    "Zone9": "Z9", "Zone9SR": "Z9", "Z9SRBuddy": "Z9",
    "Zone10": "Z10", "MRR10": "Z10", "WRR10": "Z10",
}

# Zone adjacency. Auto-symmetrized at engine startup via ensure_symmetric_adjacency().
ZONE_ADJACENCY_RAW = {
    "Zone1": ["Zone2"],
    "Zone2": ["Zone1", "Zone3"],
    "Zone3": ["Zone2", "Zone4"],
    "Zone4": ["Zone3"],
    "Zone6": ["Zone7"],
    "Zone7": ["Zone6"],
}


def ensure_symmetric_adjacency(adj_map):
    """Return a defensively-symmetric copy of the zone adjacency map.
    If A→B exists but B→A doesn't, this adds B→A. Prevents asymmetric
    pair-affinity scoring if someone edits the map without thinking about
    the inverse."""
    out = {k: set(v) for k, v in adj_map.items()}
    for z, neighbors in list(out.items()):
        for n in list(neighbors):
            out.setdefault(n, set()).add(z)
    # Convert back to sorted lists for stable output
    return {k: sorted(v) for k, v in out.items()}


# Pre-computed symmetric adjacency for engine + scorecard use
ZONE_ADJACENCY = ensure_symmetric_adjacency(ZONE_ADJACENCY_RAW)
