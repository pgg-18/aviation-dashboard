"""
Persistence + the caching state machine.

Kept free of Streamlit so it can be unit-tested on its own. The whole point of the
manager's design lives here:

  * The dashboard reads its numbers from a JSON file on disk, so whatever you last
    saved is what shows up — even if you close the app and reopen it tomorrow. It is
    STATIC by default.
  * "Fetch Data" only actually hits the website when the store is "armed"
    (fetch_armed == True) or when there is no data at all yet (first ever run).
    Otherwise it just re-shows the saved numbers and changes nothing.
  * "Update Manually" left completely BLANK is what arms the next fetch.
  * "Update Manually" with values typed in overwrites the saved numbers by hand
    (and disarms — no fetch needed).
"""

from __future__ import annotations
import json
import os
from datetime import datetime

from moca_scraper import SECTIONS

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard_data.json")


def empty_skeleton() -> dict:
    """A blank data structure matching the five sections, for manual-first entry."""
    return {
        key: {"title": cfg["title"], "date": None,
              "metrics": {m: None for m in cfg["metrics"]}}
        for key, cfg in SECTIONS.items()
    }


def load_store() -> dict | None:
    if not os.path.exists(DATA_FILE):
        return None
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def save_store(store: dict) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2, ensure_ascii=False)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def do_fetch(scrape_fn) -> tuple[dict, str, str]:
    """
    Handle the 'Fetch Data' button.

    Returns (store, status, message) where status is one of:
      'fetched' - actually pulled fresh data from the site
      'locked'  - did nothing on purpose; showing saved static data
      'error'   - the site fetch was armed but failed
    scrape_fn is injected so this can be tested without network access.
    """
    store = load_store()

    first_run = store is None
    armed = bool(store and store.get("fetch_armed", False))

    if first_run or armed:
        try:
            data = scrape_fn()
        except Exception as exc:  # network / parse failure
            msg = f"Tried to fetch live data but it failed: {exc}"
            if store is not None:
                # keep whatever we had; leave it armed so they can retry
                return store, "error", msg
            return None, "error", msg

        new_store = {
            "data": data,
            "source": "site",
            "as_of": _fmt_site_date(data),
            "last_fetched_at": _now(),
            "fetch_armed": False,  # spend the arming — next fetch is a no-op again
        }
        save_store(new_store)
        reason = "first run" if first_run else "refresh was armed"
        return new_store, "fetched", f"Pulled fresh data from the Ministry site ({reason})."

    # not armed and data exists -> stay static, change nothing
    return store, "locked", (
        "Showing saved data — it stays frozen until you arm a refresh. "
        "To pull today's live numbers: Update Manually → leave everything blank → "
        "Save → then press Fetch Data."
    )


def arm_refresh(store: dict | None) -> tuple[dict, str]:
    """'Update Manually' submitted BLANK -> arm the next fetch, keep data unchanged."""
    if store is None:
        store = {"data": empty_skeleton(), "source": "none", "as_of": None,
                 "last_fetched_at": None, "fetch_armed": True}
    else:
        store = dict(store)
        store["fetch_armed"] = True
    save_store(store)
    return store, "Refresh armed. Close this and press Fetch Data to pull live numbers."


def apply_manual(store: dict | None, entered: dict) -> tuple[dict, str]:
    """
    'Update Manually' submitted WITH values.
    `entered` = {section_key: {metric_label: value_string}} containing only non-blank
    fields. Blank fields keep their previous value. Saving by hand disarms fetch.
    """
    base = store["data"] if store and "data" in store else empty_skeleton()
    # deep-ish copy
    data = json.loads(json.dumps(base))
    for skey, metrics in entered.items():
        if skey not in data:
            continue
        for label, val in metrics.items():
            if val is not None and str(val).strip() != "":
                data[skey]["metrics"][label] = str(val).strip()

    new_store = {
        "data": data,
        "source": "manual",
        "as_of": datetime.now().strftime("%d %b %Y") + " (manual)",
        "last_fetched_at": (store or {}).get("last_fetched_at"),
        "fetch_armed": False,
    }
    save_store(new_store)
    return new_store, "Saved your manual values."


def _fmt_site_date(data: dict) -> str:
    """Use the domestic-traffic 'On <date>' line as the headline as-of date."""
    dt = (data.get("domestic_traffic") or {}).get("date")
    return dt or datetime.now().strftime("%d %b %Y")
