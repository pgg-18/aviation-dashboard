"""
Scraper for the Ministry of Civil Aviation homepage (https://www.civilaviation.gov.in/).

The homepage renders all the figures server-side, so a plain HTTP GET + HTML parse
is enough. We work off the document-ordered list of visible text strings
(BeautifulSoup's stripped_strings) so the parser does NOT depend on CSS class names,
which government sites change often. It anchors on the stable English labels instead.
"""

from __future__ import annotations
import requests
from bs4 import BeautifulSoup

URL = "https://www.civilaviation.gov.in/"

HEADERS = {
    # Some gov sites reject the default python-requests UA, so send a browser-like one.
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# The five sections the dashboard cares about, in the order they appear on the page.
# Each has the English text of its <h2> heading and the ordered English metric labels.
SECTIONS = {
    "domestic_traffic": {
        "title": "Domestic Traffic",
        "heading": "Domestic traffic",
        "metrics": [
            "Departing flights", "Departing Pax", "Arriving flights",
            "Arriving Pax", "Aircraft movements", "Airport footfalls",
        ],
    },
    "international_traffic": {
        "title": "International Traffic",
        "heading": "International traffic",
        "metrics": [
            "Departing flights", "Departing Pax", "Arriving flights",
            "Arriving Pax", "Aircraft movements", "Airport footfalls",
        ],
    },
    "udan": {
        "title": "UDAN (RCS)",
        "heading": "UDAN (RCS)",
        "metrics": [
            "Airports*", "Routes", "Operators", "Flights",
            "Passengers", "Viability Gap Funding",
        ],
    },
    "airports": {
        "title": "Airports",
        "heading": "Airports",
        "metrics": [
            "Operational", "International*", "Custom", "Domestic*",
            "Joint venture International", "State Govt./ Private",
        ],
    },
    "cargo": {
        "title": "Cargo (In MT)",
        "heading": "Cargo (In MT)",
        "metrics": [
            "Inbound (Int)", "Inbound (Dom)", "Outbound (Int)",
            "Outbound (Dom)", "Total (Int)", "Total (Dom)",
        ],
    },
}

# Full ordered list of ALL section headings on the page. We need the ones that come
# *after* each target section so we know where a section's content ends.
ALL_HEADINGS_IN_ORDER = [
    "Domestic traffic",
    "International traffic",
    "On Time Performance",
    "Passenger Load Factor",
    "UDAN (RCS)",
    "Air Sewa Grievances (by volume)",
    "Air Sewa Grievances (by type)",
    "Air Sewa Grievances (by entity)",
    "Airports",
    "Drones",
    "Cargo (In MT)",
    "Skilling by AASSC",
    "Skilling by IGRUA",
    "Skilling by RGNAU",
    "Flying Training Organizations",
]


def _has_digit(s: str) -> bool:
    return any(c.isdigit() for c in s)


def _find_heading_indices(lines: list[str]) -> dict[str, int]:
    """
    Walk the ordered lines once, matching each heading in order with a moving cursor.
    A line is a heading if (case-insensitively) it ENDS WITH the English heading text
    — headings render as 'Hindi English', so the English part is at the end. Matching in
    order with an advancing cursor prevents nav links / metric labels (e.g. 'Airports*')
    from being mistaken for the real section heading.
    """
    indices: dict[str, int] = {}
    cursor = 0
    for heading in ALL_HEADINGS_IN_ORDER:
        needle = heading.lower()
        for i in range(cursor, len(lines)):
            if lines[i].strip().lower().endswith(needle):
                indices[heading] = i
                cursor = i + 1
                break
    return indices


def _extract_section(lines: list[str], start: int, end: int, metric_labels: list[str]):
    """Within lines[start:end], pull the date line and each label's value."""
    section_slice = lines[start:end]

    # Section date is the first 'On ...' / 'Till ...' / 'Up to ...' line after the heading.
    date_text = None
    for ln in section_slice:
        low = ln.strip().lower()
        if low.startswith(("on ", "till ", "up to ")):
            date_text = ln.strip()
            break

    metrics: dict[str, str] = {}
    for label in metric_labels:
        needle = label.lower()
        val = None
        # locate the label line
        for i, ln in enumerate(section_slice):
            if ln.strip().lower().endswith(needle):
                # value = first following line that contains a digit
                for j in range(i + 1, len(section_slice)):
                    if _has_digit(section_slice[j]):
                        val = section_slice[j].strip()
                        break
                break
        metrics[label] = val
    return date_text, metrics


def parse_lines(lines: list[str]) -> dict:
    """Turn the ordered visible-text lines into the structured dashboard dict."""
    heading_idx = _find_heading_indices(lines)
    n = len(lines)

    result: dict[str, dict] = {}
    for key, cfg in SECTIONS.items():
        h = cfg["heading"]
        start = heading_idx.get(h)
        if start is None:
            # heading not found — record empty so the UI can show a gap gracefully
            result[key] = {"title": cfg["title"], "date": None,
                           "metrics": {m: None for m in cfg["metrics"]}}
            continue
        # end = index of the next heading (any) that appears after this one
        later = [idx for idx in heading_idx.values() if idx > start]
        end = min(later) if later else n
        date_text, metrics = _extract_section(lines, start, end, cfg["metrics"])
        result[key] = {"title": cfg["title"], "date": date_text, "metrics": metrics}
    return result


def scrape(timeout: int = 20) -> dict:
    """Fetch the live page and return the structured data. Runs on the user's machine."""
    resp = requests.get(URL, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    lines = [s.strip() for s in soup.stripped_strings if s.strip()]
    return parse_lines(lines)


if __name__ == "__main__":
    import json
    print(json.dumps(scrape(), indent=2, ensure_ascii=False))
