#!/usr/bin/env python3
"""Build results/new-companies.xlsx from the daily JSON files."""
import glob
import json

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

HEADERS = [
    "Incorporated", "Company name", "Company number", "Type", "Status",
    "Matched place(s)", "Registered office address", "SIC codes", "Companies House link",
]
WIDTHS = [14, 40, 16, 22, 12, 24, 60, 16, 22]


def load_rows(path):
    with open(path) as f:
        data = json.load(f)
    return data["companies"]


def write_sheet(ws, companies):
    ws.append(HEADERS)
    for c in companies:
        ws.append([
            c.get("incorporated"),
            c.get("name"),
            c.get("number"),
            c.get("type"),
            c.get("status"),
            ", ".join(c.get("matched_places", [])),
            c.get("address"),
            ", ".join(c.get("sic_codes", [])),
            "Open",
        ])
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
    write_sheet(ws, latest)
    write_sheet(wb.create_sheet("All"), everything)
    wb.save("results/new-companies.xlsx")
    print(f"Saved {len(latest)} latest, {len(everything)} total")


if __name__ == "__main__":
    main()
