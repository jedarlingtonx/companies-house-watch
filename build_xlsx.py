#!/usr/bin/env python3
"""Build results/new-companies.xlsx from the daily JSON files."""
import csv
import glob
import io
import json
import os
import urllib.request

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

SIC_URL = ("https://assets.publishing.service.gov.uk/media/"
           "5a7f8639e5274a2e87db65e1/SIC07_CH_condensed_list_en.csv")
SIC_CACHE = "data/sic07.csv"

HEADERS = [
    "Incorporated", "Company name", "Company number", "Type", "Status",
    "Matched place(s)", "Registered office address", "SIC codes",
    "What the business does", "Companies House link",
]
WIDTHS = [14, 40, 16, 22, 12, 24, 60, 16, 50, 22]


def load_sic():
    """Download the official SIC list (keeping a cached copy) and return {code: description}."""
    try:
        req = urllib.request.Request(SIC_URL, headers={"User-Agent": "companies-house-watch"})
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
        os.makedirs("data", exist_ok=True)
        with open(SIC_CACHE, "wb") as f:
            f.write(raw)
    except Exception as exc:
        print(f"Could not download the SIC list ({exc}); using the cached copy if there is one")

    lookup = {}
    if os.path.exists(SIC_CACHE):
        with open(SIC_CACHE, "rb") as f:
            raw = f.read()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("cp1252", errors="replace")
        for row in csv.reader(io.StringIO(text)):
            if len(row) >= 2 and row[0].strip().isdigit():
                lookup[row[0].strip().zfill(5)] = row[1].strip()
    print(f"SIC descriptions loaded: {len(lookup)}")
    return lookup


def describe(codes, sic):
    if not codes:
        return "Not yet provided"
    return "; ".join(sic.get(str(c).strip().zfill(5), "description not found") for c in codes)


def add_descriptions(path, sic):
    """Save the plain-English business description into the JSON file."""
    with open(path) as f:
        data = json.load(f)
    for c in data["companies"]:
        c["business_description"] = describe(c.get("sic_codes", []), sic)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load_rows(path):
    with open(path) as f:
        return json.load(f)["companies"]


def write_sheet(ws, companies, sic):
    ws.append(HEADERS)
    for c in companies:
        codes = c.get("sic_codes", [])
        ws.append([
            c.get("incorporated"),
            c.get("name"),
            c.get("number"),
            c.get("type"),
            c.get("status"),
            ", ".join(c.get("matched_places", [])),
            c.get("address"),
            ", ".join(codes),
            describe(codes, sic),
            "Open",
        ])
        ws.cell(row=ws.max_row, column=9).alignment = Alignment(wrap_text=True, vertical="top")
        cell = ws.cell(row=ws.max_row, column=len(HEADERS))
        cell.hyperlink = c.get("url")
        cell.font = Font(color="0563C1", underline="single")
    header_fill = PatternFill("solid", fgColor="1F3864")
    for col, width in enumerate(WIDTHS, start=1):
        cell = ws.cell(row=1, column=col)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = header_fill
        cell.alignment = Alignment(vertical="center")
        ws.column_dimensions[get_column_letter(col)].width = width
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions


def main():
    files = sorted(glob.glob("results/20*.json"))
    if not files:
        raise SystemExit("No daily result files found")

    sic = load_sic()
    add_descriptions(files[-1], sic)
    add_descriptions("results/latest.json", sic)
    latest = load_rows(files[-1])

    seen, everything = set(), []
    for path in files:
        for c in load_rows(path):
            if c["number"] not in seen:
                seen.add(c["number"])
                everything.append(c)
    everything.sort(key=lambda c: (c.get("incorporated") or "", c.get("name") or ""),
                    reverse=True)

    wb = Workbook()
    ws = wb.active
    ws.title = "Latest"
    write_sheet(ws, latest, sic)
    write_sheet(wb.create_sheet("All"), everything, sic)
    wb.save("results/new-companies.xlsx")
    print(f"Saved {len(latest)} latest, {len(everything)} total")


if __name__ == "__main__":
    main()
