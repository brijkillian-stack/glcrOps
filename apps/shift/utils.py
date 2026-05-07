"""
apps/shift/utils.py — Shared formatting helpers for the Shift HUD.
"""
from __future__ import annotations

import datetime


def fmt_time(t: "datetime.time | datetime.datetime | str") -> str:
    """12-hour, no leading zero, lowercase am/pm.

    Examples: '1:10am', '11:59pm', '12:02am'.

    Accepts:
      - datetime.time
      - datetime.datetime  (only the time portion is used)
      - str in "HH:MM" or "HH:MM:SS" form
    """
    if isinstance(t, str):
        try:
            parts = t.split(":")
            h, m = int(parts[0]), int(parts[1])
            t = datetime.time(h, m)
        except (ValueError, IndexError):
            return t  # return as-is if unparseable
    if isinstance(t, datetime.datetime):
        t = t.time()
    # t is now datetime.time
    hour   = t.hour
    minute = t.minute
    suffix = "am" if hour < 12 else "pm"
    display_hour = hour % 12 or 12  # 0 → 12, 13 → 1, etc.
    return f"{display_hour}:{minute:02d}{suffix}"
