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

st.set_page_config(page_title="Civil Aviation Dashboard", page_icon=None, layout="wide")

# ------------------------------------------------------------------ CSS: compact, single-screen
st.markdown("""
<style>
    #MainMenu, header, footer,
    div[data-testid="stToolbar"],
    div[data-testid="stDecoration"],
    div[data-testid="stStatusWidget"] { display: none !important; }

    /* Fixed to allow vertical scrolling on smaller screens */
    html, body { overflow-y: auto !important; overflow-x: hidden !important; }

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
        height: calc(100vh - 105px);
        margin-top: 0.5rem;
    }
    .cards-grid {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 0.6rem;
        flex: 0 0 42%;      /* smaller boxes: top ~42% */
        min-height: 0;
    }
    .charts-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 0.6rem;
        flex: 1 1 auto;     /* charts fill the rest */
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
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------ helpers
BURGUNDY = "#7a1f2b"
BAR_BLUE = "#2f5c74"
YTD_GREY = "#9aa0a6"

# --- Monthly YTD chart data (read from the internal report screenshot) ---------
MONTHS = ["January", "February", "March", "April", "May"]
YTD_CHARTS = [
    {
        "title": "Aircraft Movement - YTD 2026", "subtitle": "",
        "bar_legend": "Total aircraft", "line_legend": "YTD aircraft",
        "bars": [253.0, 231.6, 242.9, 241.1, 254.2],
        "ytd":  [253.0, 484.8, 727.5, 968.6, 1222.8],
    },
    {
        "title": "Passenger Traffic - YTD 2026", "subtitle": "(in Thousands)",
        "bar_legend": "Total Pax", "line_legend": "YTD Pax",
        "bars": [38.6, 35.1, 34.5, 33.8, 37.0],
        "ytd":  [38.6, 73.7, 108.2, 142.1, 179.0],
    },
    {
        "title": "Air Cargo Movement - YTD 2026", "subtitle": "(in Thousand MT)",
        "bar_legend": "Total Cargo", "line_legend": "YTD Cargo",
        "bars": [324.7, 328.5, 343.2, 347.5, 364.4],
        "ytd":  [324.7, 653.2, 996.4, 1343.9, 1708.3],
    },
]


def _combo_chart_svg(title, subtitle, months, bars, ytd, bar_legend, line_legend):
    W, H = 360, 232
    left, right = 10, 10
    top = 44 if subtitle else 32
    bottom = 60                       
    base_y = H - bottom
    area_h = base_y - top
    n = len(months)
    slot = (W - left - right) / n
    scale = (max(list(ytd) + list(bars)) or 1) * 1.15   

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
        bw = slot * 0.40
        by = y_of(bars[i])
        P.append(f'<rect x="{cx-bw/2:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{base_y-by:.1f}" fill="{BAR_BLUE}"/>')
        P.append(f'<text x="{cx:.1f}" y="{by-3:.1f}" text-anchor="middle" font-size="8.5" fill="#333">{bars[i]:.1f}</text>')
        P.append(f'<text x="{cx:.1f}" y="{base_y+13:.1f}" text-anchor="middle" font-size="8" fill="#555">{months[i]}</text>')

    # YTD cumulative line + markers + labels
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
    P.append(f'<rect x="{left+4}" y="{ly-8}" width="11" height="9" fill="{BAR_BLUE}"/>')
    P.append(f'<text x="{left+19}" y="{ly}" font-size="9" fill="#444">{bar_legend}</text>')
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
        "site":   ("dot-green", "Live (site)"),
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
        f'&nbsp;&nbsp;|&nbsp;&nbsp;Last live fetch: {last_fetch}'
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
    c1, c2 = st.columns(2)
    if c1.button("Save", type="primary", use_container_width=True):
        any_value = any(
            str(v).strip() for sec in entered.values() for v in sec.values()
        )
        if any_value:
            _, msg = st_store.apply_manual(store, entered)
            _flash(msg, "success")
        else:
            _, msg = st_store.arm_refresh(store)
            _flash(msg, "warning")
        st.rerun()
    if c2.button("Cancel", use_container_width=True):
        st.rerun()


# ------------------------------------------------------------------ header row
store = st_store.load_store()

# Changed to 4 columns to accommodate the Print Button
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

# ------------------------------------------------------------------ body: one-screen board (cards + charts)
store = st_store.load_store()

if not store or not store.get("data"):
    st.info("Nothing to show yet. Press Fetch Data.")
else:
    data = store["data"]

    # ---- cards (burgundy head + white text, data values unchanged) ----
    cards_html = '<div class="cards-grid">'
    for skey, cfg in SECTIONS.items():
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
        cards_html += (
            f'<div class="card">'
            f'<div class="card-head">'
            f'<div class="card-title">{cfg["title"]}</div>'
            f'<div class="card-date">{date_txt}</div>'
            f'</div>'
            f'<div class="card-body">{rows_html}</div>'
            f'</div>'
        )
    cards_html += '</div>'

    # ---- charts: monthly YTD combo charts (bars + cumulative line) ----
    charts_html = '<div class="charts-grid">'
    for c in YTD_CHARTS:
        svg = _combo_chart_svg(
            c["title"], c["subtitle"], MONTHS, c["bars"], c["ytd"],
            c["bar_legend"], c["line_legend"],
        )
        charts_html += f'<div class="chart-card">{svg}</div>'
    charts_html += '</div>'

    st.markdown(f'<div class="board">{cards_html}{charts_html}</div>', unsafe_allow_html=True)
