"""Shared design tokens — mirrors the Zone Deployment Book CSS variables."""

# ── Zone / RR color palette (matches HTML book) ──────────────────────────────
ZONE_COLORS: dict[str, str] = {
    "zone_1":    "#b45309",  # c-yellow  (amber-700)
    "zone_2":    "#6d28d9",  # c-purple
    "zone_3":    "#c2410c",  # c-orange
    "zone_4":    "#b91c1c",  # c-red
    "zone_5":    "#b91c1c",  # c-red
    "zone_6":    "#be185d",  # c-pink
    "zone_7":    "#1d4ed8",  # c-blue
    "zone_8":    "#78350f",  # c-brown
    "zone_9":    "#c2410c",  # c-orange
    "zone_10":   "#065f46",  # c-green
    "rr_1_2":    "#b45309",  # yellow
    "rr_6":      "#be185d",  # pink
    "rr_7":      "#1d4ed8",  # blue
    "rr_8":      "#374151",  # charcoal
    "rr_10":     "#065f46",  # green
    "z9_sr":     "#374151",
    "admin":     "#6d28d9",
    "trash_1":   "#b45309",
    "trash_2":   "#c2410c",
    "support_1": "#0369a1",
    "support_2": "#0369a1",
    "support_3": "#0369a1",
}

ZONE_LABELS: dict[str, str] = {
    "zone_1":    "Zone 1",
    "zone_2":    "Zone 2",
    "zone_3":    "Zone 3",
    "zone_4":    "Zone 4",
    "zone_5":    "Zone 5",
    "zone_6":    "Zone 6",
    "zone_7":    "Zone 7",
    "zone_8":    "Zone 8",
    "zone_9":    "Zone 9",
    "zone_10":   "Zone 10",
    "rr_1_2":    "RR 1 + 2",
    "rr_6":      "RR 6",
    "rr_7":      "RR 7",
    "rr_8":      "RR 8",
    "rr_10":     "RR 10",
    "z9_sr":     "Z9 SR",
    "admin":     "Admin",
    "trash_1":   "Trash 1",
    "trash_2":   "Trash 2",
    "support_1": "Support 1",
    "support_2": "Support 2",
    "support_3": "Support 3",
}

# Map slot_key (optionally with _mens/_womens suffix) → eligibility dict key
SLOT_ELIGIBILITY_MAP: dict[str, str] = {
    "zone_1":          "Zone 1",
    "zone_2":          "Zone 2",
    "zone_3":          "Zone 3",
    "zone_4":          "Zone 4",
    "zone_5":          "Zone 5",
    "zone_6":          "Zone 6",
    "zone_7":          "Zone 7",
    "zone_8":          "Zone 8",
    "zone_9":          "Zone 9",
    "zone_10":         "Zone 10",
    "rr_1_2_mens":     "Mens 1 + 2",
    "rr_1_2_womens":   "Womens 1 + 2",
    "rr_6_mens":       "Mens 6",
    "rr_6_womens":     "Womens 6",
    "rr_7_mens":       "Mens 7",
    "rr_7_womens":     "Womens 7",
    "rr_8_mens":       "Mens 8",
    "rr_8_womens":     "Womens 8",
    "rr_10_mens":      "Mens 10",
    "rr_10_womens":    "Womens 10",
    "z9_sr":           "Zone 9 SR",
    "admin":           "Admin",
    "trash_1":         "Trash 1",
    "trash_2":         "Trash 2",
    "support_1":       None,  # no eligibility gate — open to all
    "support_2":       None,
    "support_3":       None,
    "am_ol":           "AM OL",
    "pm_ol":           "PM OL",
    "mp_1":            "MP 1",
    "mp_2":            "MP 2",
}

# Alert crimson
C_ALERT = "#b91c1c"

# Shared card style base
CARD_BASE: dict = {
    "background": "white",
    "border": "1px solid #e5e7eb",
    "border_radius": "8px",
    "padding": "8px 10px 10px",
    "position": "relative",
    "overflow": "hidden",
    "cursor": "pointer",
    "_hover": {"box_shadow": "0 0 0 2px #3b82f6", "border_color": "#3b82f6"},
    "transition": "box-shadow 0.15s ease",
}

STATUS_COLORS = {
    "draft":     ("#fef9c3", "#92400e"),   # yellow bg / dark text
    "published": ("#d1fae5", "#065f46"),   # green
    "archived":  ("#f3f4f6", "#6b7280"),   # gray
}

# ── Default tasks (mirrors render_deployment_book.py) ─────────────────────────
TASKS_ZONE: dict[int, list[str]] = {
    1:  ["Outdoor Smoking Area", "Elevators & Stairwells", "Family Restroom"],
    2:  ["Lobby Trash Pull", "Lobby Restrooms"],
    3:  [],
    4:  ["Poker Room Drink Trays"],
    5:  ["High Limit Table Games", "Indoor TM Smoking Room"],
    6:  ["Outdoor Smoking Area"],
    7:  ["Smoking Room", "Pit 1 & 2", "South Door Glass"],
    8:  ["Restrooms", "Pit 3"],
    9:  ["Assist with Smoking Room", "Social Bar Tables"],
    10: ["High Limit Slots", "East Door Glass", "Outdoor Smoking Area", "Pit 4"],
}
TASKS_RR: dict[int, list[str]] = {
    1:  ["Buffet RR", "Family RR"],
    6:  ["131 Restroom"],
    7:  ["Assist with Smoking Room"],
    8:  ["Family Restroom", "TDR Restroom", "TMBR Locker Room"],
    10: ["CBK Kitchen"],
}
# DB slot_key → default task bullets shown on the card
TASKS_AUX_SLOT: dict[str, list[str]] = {
    "trash_1":    ["Zones 1–5", "Annex after 5am"],
    "trash_2":    ["Zones 6–10"],
    "z9_sr":      ["Smoking Room"],
    "z9_sr_buddy":["Smoking Room (paired)"],
    "admin":      [],
    "support_1":  [],
    "support_2":  [],
    "support_3":  ["Overflow"],
}

# Break group assignments (wave 1 / 2 / 3) — mirrors render_deployment_book.py
BG_ZONE: dict[int, int]  = {1:1, 2:2, 3:3, 4:1, 5:2, 6:3, 7:1, 8:2, 9:3, 10:2}
BG_RR_M: dict[int, int]  = {1:2, 6:2, 7:3, 8:1, 10:3}
BG_RR_W: dict[int, int]  = {1:3, 6:1, 7:2, 8:3, 10:1}
BG_AUX:  dict[str, int]  = {
    "z9_sr": 2,    "z9_sr_buddy": 1,
    "admin": 2,
    "trash_1": 2,  "trash_2": 1,
    "support_1": 1, "support_2": 3, "support_3": 2,
}
