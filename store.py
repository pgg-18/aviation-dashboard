"""
Persistence + the caching state machine for the main dashboard tab (cards + charts).

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
  * The monthly YTD chart numbers (bars + cumulative line) live in this SAME store
    under "charts", so they persist and are editable from the Update Manually popup
    too. They are never touched by Fetch Data / arm_refresh — only by chart edits.
"""

from __future__ import annotations
import json
import os
from datetime import datetime

from moca_scraper import SECTIONS
from persistence import read_json, atomic_write_json

# Where the saved data lives. By default it sits next to this script (fine for local
# use). For deployment, point it at a PERSISTENT location so it survives restarts:
#     export DASHBOARD_DATA_FILE=/data/dashboard_data.json      (Linux/VM/Docker)
# On hosts with a persistent disk/volume this makes the "static across days" behaviour
# hold. On fully ephemeral hosts (e.g. Streamlit Community Cloud) no local path
# persists across restarts — you'd need an external store instead.
DATA_FILE = os.environ.get(
    "DASHBOARD_DATA_FILE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard_data.json"),
)

MONTHS = ["January", "February", "March", "April", "May"]
DEFAULT_MONTHS = list(MONTHS)

# Default monthly chart numbers (originally read off the manager's report screenshot).
# Only the numeric arrays live here / are editable; titles, subtitles and legend text
# are cosmetic and stay as constants in app.py.
DEFAULT_CHARTS = {
    "aircraft": {
        "bars": [253.0, 231.6, 242.9, 241.1, 254.2],
        "ytd":  [253.0, 484.6, 727.5, 968.6, 1222.8],
    },
    "passengers": {
        "bars": [38.6, 35.1, 34.5, 33.8, 37.0],
        "ytd":  [38.6, 73.7, 108.2, 142.0, 179.0],
    },
    "cargo": {
        "bars": [324.7, 328.5, 343.2, 347.5, 364.4],
        "ytd":  [324.7, 653.2, 996.4, 1343.9, 1708.3],
    },
}


def _default_charts_copy() -> dict:
    return json.loads(json.dumps(DEFAULT_CHARTS))


def empty_skeleton() -> dict:
    """A blank data structure matching the five sections, for manual-first entry."""
    return {
        key: {"title": cfg["title"], "date": None,
              "metrics": {m: None for m in cfg["metrics"]}}
        for key, cfg in SECTIONS.items()
    }


def load_store() -> dict | None:
    return read_json(DATA_FILE)


def save_store(store: dict) -> None:
    atomic_write_json(DATA_FILE, store)


def get_charts(store: dict | None) -> dict:
    """Charts, always present even for a store saved before charts existed."""
    if store and store.get("charts"):
        return store["charts"]
    return _default_charts_copy()


def get_months(store: dict | None) -> list[str]:
    """The chart month axis, always present even for a store saved before this existed."""
    if store and store.get("months"):
        return list(store["months"])
    return list(DEFAULT_MONTHS)


def add_month(store: dict | None, month_name: str) -> tuple[dict, str]:
    """
    Add a new month column to every chart (e.g. 'June'). The new slot starts as a
    placeholder — bar = 0, YTD line = carried flat from the previous month's YTD, so
    the chart doesn't visually break before real numbers are typed in via
    'Update Manually'. Everything else in the store (card data, source, fetch state)
    is left exactly as it was.
    """
    month_name = (month_name or "").strip()
    if not month_name:
        return store, "Type a month name first."

    months = get_months(store)
    if month_name in months:
        return store, f'"{month_name}" is already on the chart.'

    charts = get_charts(store)
    for series in charts.values():
        series["bars"] = list(series.get("bars", [])) + [0.0]
        last_ytd = series.get("ytd", [])
        carry = last_ytd[-1] if last_ytd else 0.0
        series["ytd"] = list(last_ytd) + [carry]

    months = months + [month_name]

    if store is None:
        new_store = {"data": empty_skeleton(), "source": "none", "as_of": None,
                     "last_fetched_at": None, "fetch_armed": False}
    else:
        new_store = dict(store)
    new_store["months"] = months
    new_store["charts"] = charts
    save_store(new_store)
    return new_store, f'Added "{month_name}". Reopen Update Manually to fill in its values.'


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
    Chart data is carried forward unchanged — Fetch Data never touches charts.
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
            "charts": get_charts(store),  # preserve existing chart edits
            "months": get_months(store),  # preserve any added months
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
                 "last_fetched_at": None, "fetch_armed": True,
                 "charts": _default_charts_copy(), "months": list(DEFAULT_MONTHS)}
    else:
        store = dict(store)
        store["fetch_armed"] = True
        store.setdefault("charts", get_charts(store))
        store.setdefault("months", get_months(store))
    save_store(store)
    return store, "Refresh armed. Close this and press Fetch Data to pull live numbers."


def apply_manual(store: dict | None, entered: dict, entered_charts: dict | None = None) -> tuple[dict, str]:
    """
    'Update Manually' submitted WITH values.
    `entered` = {section_key: {metric_label: value_string}} containing only non-blank
    fields. Blank fields keep their previous value. Saving by hand disarms fetch.

    `entered_charts` (optional) = {chart_key: {"bars": [str-or-""...], "ytd": [str-or-""...]}}
    Same blank-keeps-previous rule, applied per data point.

    Important: the "source"/"as_of"/"fetch_armed" status describes the CARD data
    (top boxes), not the charts. If only chart numbers were edited (no card field
    touched), that status is left exactly as it was — otherwise editing a chart
    would wrongly make the dashboard claim its live site data had become "manual".
    """
    base = store["data"] if store and "data" in store else empty_skeleton()
    # deep-ish copy
    data = json.loads(json.dumps(base))
    card_changed = False
    for skey, metrics in entered.items():
        if skey not in data:
            continue
        for label, val in metrics.items():
            if val is not None and str(val).strip() != "":
                data[skey]["metrics"][label] = str(val).strip()
                card_changed = True

    charts = get_charts(store)
    if entered_charts:
        for ckey, series in entered_charts.items():
            if ckey not in charts:
                continue
            for series_name in ("bars", "ytd"):
                values = series.get(series_name)
                if not values:
                    continue
                for i, raw in enumerate(values):
                    if raw is None or str(raw).strip() == "":
                        continue
                    try:
                        charts[ckey][series_name][i] = float(str(raw).strip())
                    except ValueError:
                        pass  # ignore anything that isn't a number, keep old value

    if card_changed:
        source = "manual"
        as_of = datetime.now().strftime("%d %b %Y") + " (manual)"
        fetch_armed = False  # an explicit manual override of card data disarms any pending fetch
    else:
        # chart-only edit: leave the card status exactly as it was
        source = (store or {}).get("source", "none")
        as_of = (store or {}).get("as_of")
        fetch_armed = bool((store or {}).get("fetch_armed", False))

    new_store = {
        "data": data,
        "source": source,
        "as_of": as_of,
        "last_fetched_at": (store or {}).get("last_fetched_at"),
        "fetch_armed": fetch_armed,
        "charts": charts,
        "months": get_months(store),
    }
    save_store(new_store)
    msg = "Saved your manual values." if card_changed else "Saved chart values."
    return new_store, msg


def _fmt_site_date(data: dict) -> str:
    """Use the domestic-traffic 'On <date>' line as the headline as-of date."""
    dt = (data.get("domestic_traffic") or {}).get("date")
    return dt or datetime.now().strftime("%d %b %Y")
