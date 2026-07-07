"""
Persistence for the 'Airport Wise Data' tab.

This tab has no scraper — the numbers are entered by hand (or later, dropped in by
another internal tool/website, per the plan). So there's no fetch/arm state machine
here, just: load what was last saved, or fall back to dummy placeholder numbers, and
let 'Update Manually' overwrite fields (blank keeps the previous value).

Column order: Airport, Departing Passengers, Arriving Passengers, Total Passengers,
Percentage of International Passengers, Percentage of Domestic Passengers,
Air Traffic Movements, Cargo (Metric Tonnes). Rows are always shown sorted by Total
Passengers, highest first (top 10), with an 11th computed "Total" summary row.
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

# Order here drives both the manual-entry popup field order and (with "airport"
# prepended) the table's column order.
FIELDS = ["airport", "depart_pax", "arrive_pax", "total_pax", "intl_pct", "dom_pct", "atm", "cargo_mt"]

COLUMN_LABELS = {
    "airport": "Airport",
    "depart_pax": "Departing Passengers",
    "arrive_pax": "Arriving Passengers",
    "total_pax": "Total Passengers",
    "intl_pct": "Percentage of International Passengers",
    "dom_pct": "Percentage of Domestic Passengers",
    "atm": "Air Traffic Movements",
    "cargo_mt": "Cargo (Metric Tonnes)",
}

# Dummy placeholder FIGURES — but the airports themselves and their order are real,
# matched to the user's own "Top 10 Airports by Passengers" source: Delhi, Mumbai,
# Bengaluru, Chennai, Kolkata, Hyderabad, Ahmedabad, Kochi, Goa, Pune.
# Sorted descending by total_pax. depart_pax/arrive_pax replace the old
# outgoing_pax/incoming_pax names per the manager's requested renaming.
DEFAULT_AIRPORTS = [
    {"airport": "Delhi (DEL)",       "depart_pax": 3070, "arrive_pax": 3050, "total_pax": 6120, "intl_pct": 42, "dom_pct": 58, "atm": 45000, "cargo_mt": 95000},
    {"airport": "Mumbai (BOM)",      "depart_pax": 2360, "arrive_pax": 2340, "total_pax": 4700, "intl_pct": 38, "dom_pct": 62, "atm": 34000, "cargo_mt": 72000},
    {"airport": "Bengaluru (BLR)",   "depart_pax": 1405, "arrive_pax": 1395, "total_pax": 2800, "intl_pct": 30, "dom_pct": 70, "atm": 21000, "cargo_mt": 41000},
    {"airport": "Chennai (MAA)",     "depart_pax": 1103, "arrive_pax": 1097, "total_pax": 2200, "intl_pct": 33, "dom_pct": 67, "atm": 16000, "cargo_mt": 33000},
    {"airport": "Kolkata (CCU)",     "depart_pax": 1078, "arrive_pax": 1072, "total_pax": 2150, "intl_pct": 18, "dom_pct": 82, "atm": 15500, "cargo_mt": 30000},
    {"airport": "Hyderabad (HYD)",   "depart_pax": 1053, "arrive_pax": 1047, "total_pax": 2100, "intl_pct": 27, "dom_pct": 73, "atm": 15000, "cargo_mt": 47000},
    {"airport": "Ahmedabad (AMD)",   "depart_pax": 452,  "arrive_pax": 448,  "total_pax": 900,  "intl_pct": 30, "dom_pct": 70, "atm": 7000,  "cargo_mt": 14000},
    {"airport": "Kochi (COK)",       "depart_pax": 402,  "arrive_pax": 398,  "total_pax": 800,  "intl_pct": 35, "dom_pct": 65, "atm": 6000,  "cargo_mt": 11000},
    {"airport": "Goa (GOX)",         "depart_pax": 252,  "arrive_pax": 248,  "total_pax": 500,  "intl_pct": 20, "dom_pct": 80, "atm": 3800,  "cargo_mt": 4000},
    {"airport": "Pune (PNQ)",        "depart_pax": 242,  "arrive_pax": 238,  "total_pax": 480,  "intl_pct": 3,  "dom_pct": 97, "atm": 3600,  "cargo_mt": 3500},
]

SUMMABLE_FIELDS = ["depart_pax", "arrive_pax", "total_pax", "atm", "cargo_mt"]


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


def get_as_on_label(store: dict | None) -> str | None:
    """Label for the passenger-figure columns (Departing/Arriving/Total Passengers,
    the two percentages) — these are day-snapshot numbers, same 'On <date>' family
    tab 1 uses for Domestic/International Traffic. None if never updated."""
    date = (store or {}).get("last_updated_date")
    return f"As on {date}" if date else None


def get_till_label(store: dict | None) -> str | None:
    """Label for the cumulative-style columns (Air Traffic Movements, Cargo) — same
    'Till <date>' family tab 1 uses for Airports/Cargo. Same underlying date as the
    As-on label since both are set by the same manual save; only the wording differs
    to match each column's semantics. None if never updated."""
    date = (store or {}).get("last_updated_date")
    return f"Till {date}" if date else None


def compute_total_row(rows: list[dict]) -> dict:
    """An 11th summary row: numeric columns summed; the two percentage columns are
    a total-passenger-weighted average (a plain average would misrepresent an
    airport with 6M passengers the same as one with 500K)."""
    total = {"airport": "Total"}
    for f in SUMMABLE_FIELDS:
        total[f] = sum((r.get(f) or 0) for r in rows)

    weight_sum = total["total_pax"] or 0
    if weight_sum > 0:
        intl_weighted = sum((r.get("total_pax") or 0) * (r.get("intl_pct") or 0) for r in rows)
        dom_weighted = sum((r.get("total_pax") or 0) * (r.get("dom_pct") or 0) for r in rows)
        total["intl_pct"] = round(intl_weighted / weight_sum, 1)
        total["dom_pct"] = round(dom_weighted / weight_sum, 1)
    else:
        total["intl_pct"] = 0
        total["dom_pct"] = 0
    return total


def apply_manual(store: dict | None, entered_rows: list[dict]) -> tuple[dict, str]:
    """
    `entered_rows` is a list (same length/order as what was shown) of dicts with the
    same FIELDS, where any blank string means "keep the previous value for this cell".
    Saving re-sorts by total_pax descending and stamps the 'as on' date to today.
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
    now = datetime.now()
    new_store = {
        "airports": merged,
        "source": "manual",
        "last_updated": now.strftime("%d %b %Y %H:%M"),
        "last_updated_date": now.strftime("%d %B %Y"),
    }
    save_store(new_store)
    return new_store, "Saved airport data."
