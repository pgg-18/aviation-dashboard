"""
Persistence for the 'Airport Wise Data' tab.

This tab has no scraper — the numbers are entered by hand (or later, dropped in by
another internal tool/website, per the plan). So there's no fetch/arm state machine
here, just: load what was last saved, or fall back to dummy placeholder numbers, and
let 'Update Manually' overwrite fields (blank keeps the previous value).

Columns per airport: Airport, Total Passengers, Outgoing Passengers, Incoming
Passengers, International %, Domestic %. Rows are always shown sorted by Total
Passengers, highest first (top 10).
"""

from __future__ import annotations
import json
import os
from datetime import datetime

from persistence import read_json, atomic_write_json

# Point this at a persistent path in deployment, same idea as DASHBOARD_DATA_FILE:
#     export AIRPORT_DATA_FILE=/data/airport_data.json
DATA_FILE = os.environ.get(
    "AIRPORT_DATA_FILE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "airport_data.json"),
)

FIELDS = ["airport", "total_pax", "outgoing_pax", "incoming_pax", "intl_pct", "dom_pct"]

# Dummy placeholder FIGURES (passenger counts in thousands) — but the airports
# themselves and their order are real, matched to the user's own "Top 10 Airports by
# Passengers" source: Delhi, Mumbai, Bengaluru, Chennai, Kolkata, Hyderabad,
# Ahmedabad, Kochi, Goa, Pune. Sorted descending by total_pax.
DEFAULT_AIRPORTS = [
    {"airport": "Delhi (DEL)",       "total_pax": 6120, "outgoing_pax": 3070, "incoming_pax": 3050, "intl_pct": 42, "dom_pct": 58},
    {"airport": "Mumbai (BOM)",      "total_pax": 4700, "outgoing_pax": 2360, "incoming_pax": 2340, "intl_pct": 38, "dom_pct": 62},
    {"airport": "Bengaluru (BLR)",   "total_pax": 2800, "outgoing_pax": 1405, "incoming_pax": 1395, "intl_pct": 30, "dom_pct": 70},
    {"airport": "Chennai (MAA)",     "total_pax": 2200, "outgoing_pax": 1103, "incoming_pax": 1097, "intl_pct": 33, "dom_pct": 67},
    {"airport": "Kolkata (CCU)",     "total_pax": 2150, "outgoing_pax": 1078, "incoming_pax": 1072, "intl_pct": 18, "dom_pct": 82},
    {"airport": "Hyderabad (HYD)",   "total_pax": 2100, "outgoing_pax": 1053, "incoming_pax": 1047, "intl_pct": 27, "dom_pct": 73},
    {"airport": "Ahmedabad (AMD)",   "total_pax": 900,  "outgoing_pax": 452,  "incoming_pax": 448,  "intl_pct": 30, "dom_pct": 70},
    {"airport": "Kochi (COK)",       "total_pax": 800,  "outgoing_pax": 402,  "incoming_pax": 398,  "intl_pct": 35, "dom_pct": 65},
    {"airport": "Goa (GOX)",         "total_pax": 500,  "outgoing_pax": 252,  "incoming_pax": 248,  "intl_pct": 20, "dom_pct": 80},
    {"airport": "Pune (PNQ)",        "total_pax": 480,  "outgoing_pax": 242,  "incoming_pax": 238,  "intl_pct": 3,  "dom_pct": 97},
]


def _default_rows_copy() -> list[dict]:
    return json.loads(json.dumps(DEFAULT_AIRPORTS))


def load_store() -> dict | None:
    return read_json(DATA_FILE)


def save_store(store: dict) -> None:
    atomic_write_json(DATA_FILE, store)


def get_airports(store: dict | None) -> list[dict]:
    """Rows to display, always sorted by total_pax descending. Falls back to the
    dummy defaults (in-memory only, not saved) until the user saves real edits."""
    rows = store["airports"] if store and store.get("airports") else _default_rows_copy()
    return sorted(rows, key=lambda r: (r.get("total_pax") or 0), reverse=True)


def apply_manual(store: dict | None, entered_rows: list[dict]) -> tuple[dict, str]:
    """
    `entered_rows` is a list (same length/order as what was shown) of dicts with the
    same FIELDS, where any blank string means "keep the previous value for this cell".
    Saving re-sorts by total_pax descending.
    """
    current = get_airports(store)
    merged = []
    for i, row in enumerate(current):
        new_row = dict(row)
        edits = entered_rows[i] if i < len(entered_rows) else {}
        for f in FIELDS:
            raw = edits.get(f)
            if raw is None or str(raw).strip() == "":
                continue
            if f == "airport":
                new_row[f] = str(raw).strip()
            else:
                try:
                    new_row[f] = float(raw) if "." in str(raw) else int(raw)
                except ValueError:
                    pass  # ignore invalid numbers, keep old value
        merged.append(new_row)

    merged.sort(key=lambda r: (r.get("total_pax") or 0), reverse=True)
    new_store = {
        "airports": merged,
        "source": "manual",
        "last_updated": datetime.now().strftime("%d %b %Y %H:%M"),
    }
    save_store(new_store)
    return new_store, "Saved airport data."
