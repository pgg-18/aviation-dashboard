"""
Ministry of Civil Aviation — static, single-screen dashboard.

Run with:  streamlit run app.py

Behaviour:
  - The dashboard is STATIC. It shows the last saved numbers, even after you close
    and reopen it tomorrow.
  - "Fetch Data" only truly pulls from the website on the very first run, or after a
    refresh has been armed. Otherwise it just keeps showing the saved numbers.
  - "Update Manually" opens a popup.
        - Leave every box BLANK and Save  -> arms the next Fetch Data.
        - Type values and Save            -> overwrites the numbers by hand.
  - Layout is a dense CSS grid designed to fit on one screen without scrolling.
"""

import html
import streamlit as st
import streamlit.components.v1 as components

from moca_scraper import SECTIONS, scrape
import store as st_store
import airport_store as apt_store

st.set_page_config(page_title="Civil Aviation Dashboard", page_icon=None, layout="wide")

# ------------------------------------------------------------------ CSS: compact, single-screen
st.markdown("""
<style>
    #MainMenu, header, footer,
    div[data-testid="stToolbar"],
    div[data-testid="stDecoration"],
    div[data-testid="stStatusWidget"] { display: none !important; }

    html, body { overflow: hidden !important; height: 100vh !important; }

    /* Streamlit wraps the page in its own scrollable containers — html/body alone
       isn't enough to stop scrolling, these need it too. */
    div[data-testid="stAppViewContainer"],
    div[data-testid="stMain"],
    div[data-testid="stAppViewBlockContainer"],
    section.main {
        overflow: hidden !important;
        height: 100vh !important;
    }

    .block-container {
        padding-top: 0.6rem !important;
        padding-bottom: 0.3rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        max-width: 100% !important;
    }

    div[data-testid="stVerticalBlock"] { gap: 0.35rem !important; }
    div[data-testid="stMarkdownContainer"] > p { margin: 0 !important; padding: 0 !important; }

    .dash-header { display: block; }
    .dash-title {
        font-size: 1.7rem; font-weight: 700; margin: 0 !important;
        line-height: 1.3; display: block;
    }
    .dash-status {
        font-size: 1rem; color: #555; margin: 0.2rem 0 0 0 !important;
        line-height: 1.3; display: block;
    }

    .dot { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:5px; }
    .dot-green  { background:#2e7d32; }
    .dot-orange { background:#e65100; }
    .dot-grey   { background:#9e9e9e; }
    .dot-red    { background:#c62828; }

    div.stButton > button {
        padding: 0.4rem 0.9rem;
        font-size: 1rem;
        min-height: 0;
        height: 2.6rem;
    }

    /* Whole board fills the viewport under the header; split into cards + charts. */
    .board {
        display: flex;
        flex-direction: column;
        gap: 0.6rem;
        height: calc(100vh - 150px);
        margin-top: 0.5rem;
    }
    /* Row 1: the 5 main KPI cards. Row 2: the 3 charts on the left, Grievances
       card on the right — same row, side by side, not stacked. */
    .kpi-row {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 0.6rem;
        flex: 0 0 46%;
        min-height: 0;
    }
    .lower-row {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 0.6rem;
        flex: 1 1 auto;     /* fills whatever height is left under the KPI row */
        min-height: 0;
    }
    .charts-wrap {
        grid-column: 1 / span 4;
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 0.6rem;
        min-height: 0;
    }
    .card {
        border: 1px solid #e2e2e2;
        border-radius: 10px;
        background: #fff;
        display: flex;
        flex-direction: column;
        overflow: hidden;
        min-height: 0;
    }
    .card-head {
        background: #7a1f2b;          /* burgundy */
        color: #ffffff;
        padding: 0.35rem 0.6rem;
        flex: 0 0 auto;
    }
    .card-title { font-size: 0.92rem; font-weight: 700; line-height: 1.15; }
    .card-date  { font-size: 0.66rem; color: #f0dcdf; line-height: 1.15; }
    .card-body {
        padding: 0.1rem 0.6rem 0.35rem;
        display: flex;
        flex-direction: column;
        flex: 1 1 auto;
        min-height: 0;
    }
    .metric-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-top: 1px solid #eee;
        gap: 0.4rem;
        flex: 1 1 0;
    }
    .metric-row:first-of-type { border-top: none; }
    .metric-label { font-size: 0.76rem; color: #444; line-height: 1.15; }
    .metric-value {
        font-size: 0.86rem; font-weight: 700; color: #111;
        white-space: nowrap; text-align: right;
    }
    .chart-card {
        border: 1px solid #e2e2e2;
        border-radius: 10px;
        background: #fff;
        padding: 0.3rem 0.4rem 0.2rem;
        display: flex;
        min-height: 0;
    }
    .chart-card svg { width: 100%; height: 100%; }
    .source-note {
        font-size: 0.72rem; color: #999; text-align: center;
        line-height: 1.2; margin: 0.25rem 0 0 0 !important;
    }

    /* Tabs */
    button[data-baseweb="tab"] { font-size: 1rem; font-weight: 600; padding: 0.5rem 1rem; }
    div[data-baseweb="tab-highlight"] { background-color: #7a1f2b !important; }

    /* Airport table */
    .airport-table-wrap { margin-top: 0.6rem; overflow-x: auto; }
    table.airport-table { width: 100%; border-collapse: collapse; font-size: 0.86rem; }
    table.airport-table th {
        background: #7a1f2b; color: #ffffff; text-align: right;
        padding: 0.5rem 0.7rem; font-weight: 700; white-space: nowrap;
    }
    table.airport-table th:first-child, table.airport-table td:first-child { text-align: left; }
    table.airport-table td {
        padding: 0.45rem 0.7rem; text-align: right; border-bottom: 1px solid #eee;
    }
    table.airport-table tr:nth-child(even) td { background: #faf5f6; }
    table.airport-table td:first-child { font-weight: 700; color: #222; }
    table.airport-table tr.total-row td {
        font-weight: 700; background: #f1e4e6 !important;
        border-top: 2px solid #7a1f2b;
    }
    table.airport-table tr.group-row th {
        background: #fff; text-align: left; font-weight: 700;
        padding: 0.3rem 0.7rem 0.15rem; border-bottom: none;
    }
    .as-on-red { color: #c62828; }
    .as-on-grey { color: #999; font-weight: 400; }
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------ helpers
BURGUNDY = "#7a1f2b"
YTD_GREY = "#9aa0a6"

# --- Chart cosmetics only (titles/subtitles/legend labels). The actual monthly
# numbers AND the month list itself live in store.py / the saved store, and are
# editable from the Update Manually popup (including adding new months). Keys must
# match store.DEFAULT_CHARTS keys.
CHART_META = {
    "aircraft":   {"title": "Aircraft Movements", "subtitle": "",
                   "bar_legend": "Total Air Traffic Movements", "line_legend": "YTD aircraft"},
    "passengers": {"title": "Passenger Traffic - YTD 2026", "subtitle": "(in Thousands)",
                   "bar_legend": "Total Passengers", "line_legend": "YTD Passengers"},
    "cargo":      {"title": "Air Cargo Movement - YTD 2026", "subtitle": "(in Thousand MT)",
                   "bar_legend": "Total Cargo", "line_legend": "YTD Cargo"},
}


def _combo_chart_svg(title, subtitle, months, bars, ytd, bar_legend, line_legend, show_line=True, bar_width_ratio=0.40):
    W, H = 360, 232
    left, right = 10, 10
    top = 44 if subtitle else 32
    bottom = 60                       
    base_y = H - bottom
    area_h = base_y - top
    n = len(months)
    slot = (W - left - right) / n
    # When the line is hidden, don't let its (much larger, cumulative) values shrink
    # the bars — scale against the bars alone so they fill the available height.
    scale_values = (list(ytd) + list(bars)) if show_line else list(bars)
    scale = (max(scale_values) if scale_values else 1) * 1.15

    def y_of(v):
        return base_y - (v / scale) * area_h

    P = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">']
    P.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="white"/>')
    P.append(f'<text x="{W/2}" y="16" text-anchor="middle" font-size="14" font-weight="700" fill="#222">{title}</text>')
    if subtitle:
        P.append(f'<text x="{W/2}" y="30" text-anchor="middle" font-size="10" fill="#666">{subtitle}</text>')
    P.append(f'<line x1="{left}" y1="{base_y}" x2="{W-right}" y2="{base_y}" stroke="#ccc"/>')

    # bars + bar labels + month labels
    for i in range(n):
        cx = left + slot * i + slot / 2
        bw = slot * bar_width_ratio
        by = y_of(bars[i])
        P.append(f'<rect x="{cx-bw/2:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{base_y-by:.1f}" fill="{BURGUNDY}"/>')
        P.append(f'<text x="{cx:.1f}" y="{by-3:.1f}" text-anchor="middle" font-size="8.5" fill="#333">{bars[i]:.1f}</text>')
        P.append(f'<text x="{cx:.1f}" y="{base_y+13:.1f}" text-anchor="middle" font-size="8" fill="#555">{months[i]}</text>')

    # YTD cumulative line + markers + labels (omitted entirely when show_line=False)
    if show_line:
        pts = [(left + slot * i + slot / 2, y_of(ytd[i])) for i in range(n)]
        poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        P.append(f'<polyline points="{poly}" fill="none" stroke="{YTD_GREY}" stroke-width="2.2"/>')
        for i, (x, y) in enumerate(pts):
            P.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.4" fill="{YTD_GREY}"/>')
            if i == 0:
                continue
            P.append(f'<text x="{x:.1f}" y="{y-5:.1f}" text-anchor="middle" font-size="8.5" font-weight="700" fill="#555">{ytd[i]:.1f}</text>')

    # legend
    ly = H - 10
    P.append(f'<rect x="{left+4}" y="{ly-8}" width="11" height="9" fill="{BURGUNDY}"/>')
    P.append(f'<text x="{left+19}" y="{ly}" font-size="9" fill="#444">{bar_legend}</text>')
    if show_line:
        lx2 = W * 0.55
        P.append(f'<line x1="{lx2:.1f}" y1="{ly-4}" x2="{lx2+16:.1f}" y2="{ly-4}" stroke="{YTD_GREY}" stroke-width="2.2"/>')
        P.append(f'<text x="{lx2+20:.1f}" y="{ly}" font-size="9" fill="#444">{line_legend}</text>')
    P.append('</svg>')
    return "".join(P)


def _flash(msg: str, kind: str = "info"):
    st.session_state["_flash"] = (kind, msg)


def _show_flash():
    if "_flash" in st.session_state:
        kind, msg = st.session_state.pop("_flash")
        {"info": st.info, "success": st.success,
         "warning": st.warning, "error": st.error}.get(kind, st.info)(msg)


def _status_badge(store):
    if not store:
        return '<span class="dot dot-grey"></span>No data saved yet'
    src = store.get("source", "none")
    dot, label = {
        "site":   ("dot-green", "Latest (site)"),
        "manual": ("dot-orange", "Manual"),
        "none":   ("dot-grey", "Empty"),
    }.get(src, ("dot-grey", src))
    armed = store.get("fetch_armed")
    armed_dot, armed_label = ("dot-red", "refresh armed") if armed else ("dot-grey", "static / locked")
    as_of = store.get("as_of") or "\u2014"
    last_fetch = store.get("last_fetched_at") or "never"
    return (
        f'<span class="dot {dot}"></span>{label}'
        f'&nbsp;&nbsp;|&nbsp;&nbsp;<span class="dot {armed_dot}"></span>{armed_label}'
        f'&nbsp;&nbsp;|&nbsp;&nbsp;As of: {as_of}'
        f'&nbsp;&nbsp;|&nbsp;&nbsp;Latest fetch: {last_fetch}'
    )


# ------------------------------------------------------------------ popup
@st.dialog("Update Manually")
def manual_dialog(store):
    st.caption(
        "Leave everything blank and press Save to arm the next Fetch Data "
        "(it will then pull live numbers from the site). "
        "Or type new values into any boxes to set those numbers by hand."
    )

    current = (store or {}).get("data") or st_store.empty_skeleton()
    entered: dict[str, dict] = {}
    nonce = st.session_state.get("_dlg_nonce", 0)

    for skey, cfg in SECTIONS.items():
        with st.expander(cfg["title"], expanded=(skey == "domestic_traffic")):
            entered[skey] = {}
            cur_metrics = current.get(skey, {}).get("metrics", {})
            for label in cfg["metrics"]:
                cur = cur_metrics.get(label)
                placeholder = f"current: {cur}" if cur not in (None, "") else "blank"
                entered[skey][label] = st.text_input(
                    label,
                    value="",
                    placeholder=placeholder,
                    key=f"manual__{nonce}__{skey}__{label}",
                )

    st.divider()
    months = st_store.get_months(store)
    st.caption(f"Monthly chart figures ({months[0]}\u2013{months[-1]}). "
               "Leave a box blank to keep its current number.")

    # --- Add a month (e.g. June) ---
    ac1, ac2 = st.columns([3, 1])
    with ac1:
        new_month = st.text_input(
            "Add a month to the charts", value="", placeholder="e.g. June",
            key=f"add_month__{nonce}",
        )
    with ac2:
        st.write("")  # small vertical spacer so the button lines up with the input
        st.write("")
        if st.button("Add Month", use_container_width=True, key=f"add_month_btn__{nonce}"):
            if new_month.strip():
                _, msg = st_store.add_month(store, new_month.strip())
                _flash(msg, "success")
                st.rerun()
            else:
                st.warning("Type a month name first (e.g. June).")

    current_charts = st_store.get_charts(store)
    entered_charts: dict[str, dict] = {}
    for ckey, meta in CHART_META.items():
        with st.expander(meta["title"]):
            entered_charts[ckey] = {"bars": [], "ytd": []}
            cur_series = current_charts.get(ckey, {})
            cb1, cb2 = st.columns(2)
            with cb1:
                st.caption(meta["bar_legend"])
                for i, mon in enumerate(months):
                    cur_v = (cur_series.get("bars") or [None] * len(months))[i]
                    val = st.text_input(
                        mon, value="", placeholder=f"current: {cur_v}",
                        key=f"chart__{nonce}__{ckey}__bar__{i}",
                    )
                    entered_charts[ckey]["bars"].append(val)
            with cb2:
                st.caption(meta["line_legend"])
                for i, mon in enumerate(months):
                    cur_v = (cur_series.get("ytd") or [None] * len(months))[i]
                    val = st.text_input(
                        mon, value="", placeholder=f"current: {cur_v}",
                        key=f"chart__{nonce}__{ckey}__ytd__{i}",
                    )
                    entered_charts[ckey]["ytd"].append(val)

    st.divider()
    c1, c2 = st.columns(2)
    if c1.button("Save", type="primary", use_container_width=True):
        any_value = (
            any(str(v).strip() for sec in entered.values() for v in sec.values())
            or any(
                str(v).strip()
                for series in entered_charts.values()
                for vals in series.values()
                for v in vals
            )
        )
        if any_value:
            _, msg = st_store.apply_manual(store, entered, entered_charts)
            _flash(msg, "success")
        else:
            _, msg = st_store.arm_refresh(store)
            _flash(msg, "warning")
        st.rerun()
    if c2.button("Cancel", use_container_width=True):
        st.rerun()


# ------------------------------------------------------------------ Airport tab popup
@st.dialog("Update Manually \u2014 Airport Data")
def airport_manual_dialog(apt_store_data):
    st.caption(
        "Leave a box blank to keep its current value. Rows are always shown sorted "
        "by Total Passengers, highest first \u2014 editing a value may reorder rows "
        "the next time you open this."
    )
    rows = apt_store.get_airports(apt_store_data)
    nonce = st.session_state.get("_apt_dlg_nonce", 0)
    entered_rows = []

    col_labels = apt_store.COLUMN_LABELS
    for i, row in enumerate(rows):
        with st.expander(f"{i+1}. {row['airport']}"):
            entry = {}
            for f in apt_store.FIELDS:
                entry[f] = st.text_input(
                    col_labels[f], value="", placeholder=f"current: {row.get(f)}",
                    key=f"apt__{nonce}__{i}__{f}",
                )
            entered_rows.append(entry)

    st.divider()
    st.caption(
        f'"{apt_store.TOTAL_ROW_LABEL}" is entered independently \u2014 it is NOT '
        "the sum of the 10 airports above, since the real nationwide total covers "
        "many more airports than just these top 10."
    )
    total_row = apt_store.get_total_row(apt_store_data)
    entered_total = {}
    with st.expander(f"11. {apt_store.TOTAL_ROW_LABEL}"):
        for f in apt_store.TOTAL_FIELDS:
            entered_total[f] = st.text_input(
                col_labels[f], value="", placeholder=f"current: {total_row.get(f)}",
                key=f"apt_total__{nonce}__{f}",
            )

    st.divider()
    c1, c2 = st.columns(2)
    if c1.button("Save", type="primary", use_container_width=True, key="apt_save"):
        _, msg = apt_store.apply_manual(apt_store_data, entered_rows, entered_total)
        _flash(msg, "success")
        st.rerun()
    if c2.button("Cancel", use_container_width=True, key="apt_cancel"):
        st.rerun()


# ------------------------------------------------------------------ tabs
tab1, tab2 = st.tabs(["Dashboard", "Airport Wise Data"])

with tab1:
    # ---- header row ----
    store = st_store.load_store()

    hcol1, hcol2, hcol3, hcol4 = st.columns([3.4, 1, 1, 1])
    with hcol1:
        st.markdown(
            '<div class="dash-header">'
            '<p class="dash-title">Ministry of Civil Aviation &mdash; Dashboard</p>'
            f'<p class="dash-status">{_status_badge(store)}</p>'
            '</div>',
            unsafe_allow_html=True,
        )
    with hcol2:
        if st.button("Fetch Data", use_container_width=True):
            with st.spinner("Checking..."):
                _, status, msg = st_store.do_fetch(scrape)
            _flash(msg, {"fetched": "success", "locked": "info", "error": "error"}.get(status, "info"))
            st.rerun()
        st.markdown(
            '<p class="source-note">(Data source: civilaviation.gov.in)</p>',
            unsafe_allow_html=True,
        )
    with hcol3:
        if st.button("Update Manually", use_container_width=True):
            st.session_state["_dlg_nonce"] = st.session_state.get("_dlg_nonce", 0) + 1
            manual_dialog(store)
    with hcol4:
        # Trigger JS window.parent.print() when clicked
        if st.button("Print Dashboard", use_container_width=True):
            components.html("<script>window.parent.print();</script>", height=0)

    _show_flash()

    # ---- body: cards + charts ----
    store = st_store.load_store()

    if not store or not store.get("data"):
        st.info("Nothing to show yet. Press Fetch Data.")
    else:
        data = store["data"]
        charts_data = st_store.get_charts(store)

        # ---- cards (burgundy head + white text, data values unchanged) ----
        def _card_html(skey, cfg, extra_class=""):
            section = data.get(skey, {})
            metrics = section.get("metrics", {})
            date_txt = html.escape(section.get("date") or "")
            rows_html = ""
            for label in cfg["metrics"]:
                val = metrics.get(label)
                val_txt = html.escape(str(val)) if val not in (None, "") else "\u2014"
                rows_html += (
                    f'<div class="metric-row">'
                    f'<span class="metric-label">{label}</span>'
                    f'<span class="metric-value">{val_txt}</span>'
                    f'</div>'
                )
            cls = f"card {extra_class}".strip()
            return (
                f'<div class="{cls}">'
                f'<div class="card-head">'
                f'<div class="card-title">{cfg["title"]}</div>'
                f'<div class="card-date">{date_txt}</div>'
                f'</div>'
                f'<div class="card-body">{rows_html}</div>'
                f'</div>'
            )

        # ---- top KPI row: Domestic, International, UDAN, Airports, Cargo ----
        ordinary_keys = ["domestic_traffic", "international_traffic", "udan", "airports", "cargo"]
        kpi_row_html = '<div class="kpi-row">'
        for skey in ordinary_keys:
            kpi_row_html += _card_html(skey, SECTIONS[skey])
        kpi_row_html += '</div>'

        # ---- lower row: 3 charts on the left, Grievances card on the right ----
        chart_months = st_store.get_months(store)
        charts_html = '<div class="charts-wrap">'
        for ckey, meta in CHART_META.items():
            series = charts_data.get(ckey, {})
            svg = _combo_chart_svg(
                meta["title"], meta["subtitle"], chart_months,
                series.get("bars", []), series.get("ytd", []),
                meta["bar_legend"], meta["line_legend"],
                show_line=(ckey != "aircraft"),
                bar_width_ratio=(0.62 if ckey == "aircraft" else 0.40),
            )
            charts_html += f'<div class="chart-card">{svg}</div>'
        charts_html += '</div>'

        lower_row_html = (
            '<div class="lower-row">'
            + charts_html
            + _card_html("grievances_volume", SECTIONS["grievances_volume"])
            + '</div>'
        )

        st.markdown(f'<div class="board">{kpi_row_html}{lower_row_html}</div>', unsafe_allow_html=True)

with tab2:
    apt_data = apt_store.load_store()
    airports = apt_store.get_airports(apt_data)
    as_on_label = apt_store.get_as_on_label(apt_data)
    till_label = apt_store.get_till_label(apt_data)

    acol1, acol2, acol3 = st.columns([4.4, 1, 1])
    with acol1:
        st.markdown(
            '<div class="dash-header">'
            '<p class="dash-title">Airport Wise Data</p>'
            '<p class="dash-status">Top 10 airports</p>'
            '</div>',
            unsafe_allow_html=True,
        )
    with acol2:
        if st.button("Update Manually", use_container_width=True, key="apt_update_btn"):
            st.session_state["_apt_dlg_nonce"] = st.session_state.get("_apt_dlg_nonce", 0) + 1
            airport_manual_dialog(apt_data)
    with acol3:
        if st.button("Print Dashboard", use_container_width=True, key="apt_print_btn"):
            components.html("<script>window.parent.print();</script>", height=0)

    _show_flash()

    rows_html = ""
    for r in airports:
        rows_html += (
            "<tr>"
            f"<td>{html.escape(str(r['airport']))}</td>"
            f"<td>{r['depart_pax']:,}</td>"
            f"<td>{r['arrive_pax']:,}</td>"
            f"<td>{r['total_pax']:,}</td>"
            f"<td>{r['atm']:,}</td>"
            f"<td>{r['cargo_mt']:,}</td>"
            "</tr>"
        )

    total_row = apt_store.get_total_row(apt_data)  # independent mock data, NOT a sum
    rows_html += (
        '<tr class="total-row">'
        f"<td>{html.escape(str(total_row['airport']))}</td>"
        f"<td>{total_row['depart_pax']:,}</td>"
        f"<td>{total_row['arrive_pax']:,}</td>"
        f"<td>{total_row['total_pax']:,}</td>"
        f"<td>{total_row['atm']:,}</td>"
        f"<td>{total_row['cargo_mt']:,}</td>"
        "</tr>"
    )

    # Passenger columns (Airport..Total Passengers) are day-snapshot figures ->
    # "As on", same family tab 1 uses for Domestic/International Traffic. Air
    # Traffic Movements + Cargo are cumulative-style -> "Till", same family tab 1
    # uses for Airports/Cargo. Each group shows its own label, individually.
    as_on_html = (
        f'<span class="as-on-red">{html.escape(as_on_label)}</span>' if as_on_label
        else '<span class="as-on-grey">Not yet updated</span>'
    )
    till_html = (
        f'<span class="as-on-red">{html.escape(till_label)}</span>' if till_label
        else '<span class="as-on-grey">Not yet updated</span>'
    )
    group_row_html = (
        '<tr class="group-row">'
        f'<th colspan="4">{as_on_html}</th>'
        f'<th colspan="2">{till_html}</th>'
        '</tr>'
    )

    table_html = (
        '<div class="airport-table-wrap">'
        '<table class="airport-table">'
        '<thead>'
        f'{group_row_html}'
        '<tr>'
        '<th>Airport</th><th>Departing Passengers</th><th>Arriving Passengers</th>'
        '<th>Total Passengers</th><th>Air Traffic Movements</th>'
        '<th>Cargo (MT)</th>'
        '</tr>'
        '</thead>'
        f'<tbody>{rows_html}</tbody>'
        '</table></div>'
    )
    st.markdown(table_html, unsafe_allow_html=True)
