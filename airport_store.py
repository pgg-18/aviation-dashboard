"""
Persistence for the 'Airport Wise Data' tab.

This tab has no scraper — the numbers are entered by hand (or later, dropped in by
another internal tool/website, per the plan). So there's no fetch/arm state machine
here, just: load what was last saved, or fall back to dummy placeholder numbers, and
let 'Update Manually' overwrite fields (blank keeps the previous value).

Column order: Airport, Departing Passengers, Arriving Passengers, Total Passengers,
Air Traffic Movements, Cargo (MT). Rows are always shown sorted by Total Passengers,
highest first (top 10), with an 11th "Total (Across 165+ Airports)" row that is its
OWN independent manually-entered figure — not a sum of the 10 rows above (the real
nationwide total includes far more than these 10 airports).
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
FIELDS = ["airport", "depart_pax", "arrive_pax", "total_pax", "atm", "cargo_mt"]
# The 11th "Total" row has all the same numeric fields but no editable airport name
# (its label is fixed) — it's independent mock data, not derived from the 10 rows.
TOTAL_FIELDS = ["depart_pax", "arrive_pax", "total_pax", "atm", "cargo_mt"]
TOTAL_ROW_LABEL = "Total (Across 165+ Airports)"

COLUMN_LABELS = {
    "airport": "Airport",
    "depart_pax": "Departing Passengers",
    "arrive_pax": "Arriving Passengers",
    "total_pax": "Total Passengers",
    "atm": "Air Traffic Movements",
    "cargo_mt": "Cargo (MT)",
}

# Dummy placeholder FIGURES — but the airports themselves and their order are real,
# matched to the user's own "Top 10 Airports by Passengers" source: Delhi, Mumbai,
# Bengaluru, Chennai, Kolkata, Hyderabad, Ahmedabad, Kochi, Goa, Pune.
# Sorted descending by total_pax. Full names only, no airport-code short forms.
DEFAULT_AIRPORTS = [
    {"airport": "Delhi",       "depart_pax": 3070, "arrive_pax": 3050, "total_pax": 6120, "atm": 45000, "cargo_mt": 95000},
    {"airport": "Mumbai",      "depart_pax": 2360, "arrive_pax": 2340, "total_pax": 4700, "atm": 34000, "cargo_mt": 72000},
    {"airport": "Bengaluru",   "depart_pax": 1405, "arrive_pax": 1395, "total_pax": 2800, "atm": 21000, "cargo_mt": 41000},
    {"airport": "Chennai",     "depart_pax": 1103, "arrive_pax": 1097, "total_pax": 2200, "atm": 16000, "cargo_mt": 33000},
    {"airport": "Kolkata",     "depart_pax": 1078, "arrive_pax": 1072, "total_pax": 2150, "atm": 15500, "cargo_mt": 30000},
    {"airport": "Hyderabad",   "depart_pax": 1053, "arrive_pax": 1047, "total_pax": 2100, "atm": 15000, "cargo_mt": 47000},
    {"airport": "Ahmedabad",   "depart_pax": 452,  "arrive_pax": 448,  "total_pax": 900,  "atm": 7000,  "cargo_mt": 14000},
    {"airport": "Kochi",       "depart_pax": 402,  "arrive_pax": 398,  "total_pax": 800,  "atm": 6000,  "cargo_mt": 11000},
    {"airport": "Goa",         "depart_pax": 252,  "arrive_pax": 248,  "total_pax": 500,  "atm": 3800,  "cargo_mt": 4000},
    {"airport": "Pune",        "depart_pax": 242,  "arrive_pax": 238,  "total_pax": 480,  "atm": 3600,  "cargo_mt": 3500},
]

# Independent mock figures for the nationwide "Total (Across 165+ Airports)" row.
# Deliberately NOT the sum of the 10 rows above — this represents all airports in
# the country, not just the top 10 shown in the table.
DEFAULT_TOTAL_ROW = {
    "depart_pax": 185000, "arrive_pax": 183500, "total_pax": 368500,
    "atm": 1250000, "cargo_mt": 3200000,
}


def _default_rows_copy() -> list[dict]:
    return json.loads(json.dumps(DEFAULT_AIRPORTS))


def _default_total_copy() -> dict:
    return json.loads(json.dumps(DEFAULT_TOTAL_ROW))


def load_store() -> dict | None:
    return read_json(DATA_FILE)


def save_store(store: dict) -> None:
    atomic_write_json(DATA_FILE, store)


def get_airports(store: dict | None) -> list[dict]:
    """Rows to display, always sorted by total_pax descending. Falls back to the
    dummy defaults (in-memory only, not saved) until the user saves real edits."""
    rows = store["airports"] if store and store.get("airports") else _default_rows_copy()
    return sorted(rows, key=lambda r: (r.get("total_pax") or 0), reverse=True)


def get_total_row(store: dict | None) -> dict:
    """The 11th row's figures — independent manually-entered mock data, falling back
    to the placeholder defaults until someone saves real numbers for it."""
    stored = (store or {}).get("total_row")
    row = dict(stored) if stored else _default_total_copy()
    row["airport"] = TOTAL_ROW_LABEL
    return row


def get_as_on_label(store: dict | None) -> str | None:
    """Label for the passenger-figure columns (Departing/Arriving/Total Passengers)
    — day-snapshot numbers, same 'On <date>' family tab 1 uses for Domestic/
    International Traffic. None if never updated."""
    date = (store or {}).get("last_updated_date")
    return f"As on {date}" if date else None


def get_till_label(store: dict | None) -> str | None:
    """Label for the cumulative-style columns (Air Traffic Movements, Cargo) — same
    'Till <date>' family tab 1 uses for Airports/Cargo. Same underlying date as the
    As-on label since both are set by the same manual save; only the wording differs
    to match each column's semantics. None if never updated."""
    date = (store or {}).get("last_updated_date")
    return f"Till {date}" if date else None


def apply_manual(store: dict | None, entered_rows: list[dict], entered_total: dict | None = None) -> tuple[dict, str]:
    """
    `entered_rows` is a list (same length/order as what was shown) of dicts with the
    same FIELDS, where any blank string means "keep the previous value for this cell".
    Saving re-sorts by total_pax descending and stamps the date labels to today.

    `entered_total` (optional) is a dict of TOTAL_FIELDS for the 11th row — edited
    completely independently of the 10 airport rows (it is never derived from them).
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

    total_row = get_total_row(store)
    del total_row["airport"]  # not a stored/editable field, re-added by get_total_row()
    if entered_total:
        for f in TOTAL_FIELDS:
            raw = entered_total.get(f)
            if raw is None or str(raw).strip() == "":
                continue
            try:
                total_row[f] = float(raw) if "." in str(raw) else int(raw)
            except ValueError:
                pass

    now = datetime.now()
    new_store = {
        "airports": merged,
        "total_row": total_row,
        "source": "manual",
        "last_updated": now.strftime("%d %b %Y %H:%M"),
        "last_updated_date": now.strftime("%d %B %Y"),
    }
    save_store(new_store)
    return new_store, "Saved airport data."
