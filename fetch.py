#!/usr/bin/env python3
"""Fetch yesterday's new Companies House incorporations for a list of places."""
import json
import os
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

API = "https://api.company-information.service.gov.uk/advanced-search/companies"
PLACES = [
    "Northwich", "Alderley Edge", "Wilmslow", "Prestbury", "Knutsford", "Poynton",
    "Bollington", "Handforth", "Mobberley", "Macclesfield", "Disley", "Tarporley",
    "Chester", "Tarvin", "Tattenhall", "Farndon", "Malpas", "Frodsham", "Nantwich",
    "Holmes Chapel", "Sandbach", "Hartford", "Sandiway", "Cuddington", "Delamere",
    "Davenham", "Hale", "Bowdon", "Bramhall",
]
PAGE = 100


def search(key, place, day):
    items, start = [], 0
    while True:
        params = {
            "location": place,
            "incorporated_from": day,
            "incorporated_to": day,
            "size": PAGE,
            "start_index": start,
        }
        for attempt in range(4):
            r = requests.get(API, params=params, auth=(key, ""), timeout=30)
            if r.status_code == 429:
                time.sleep(30)
                continue
            break
        if r.status_code == 404:
            return items
        r.raise_for_status()
        batch = r.json().get("items") or []
        items.extend(batch)
        if len(batch) < PAGE:
            return items
        start += PAGE


def main():
    key = os.environ.get("CH_API_KEY")
    if not key:
        sys.exit("CH_API_KEY is not set")
    now = datetime.now(ZoneInfo("Europe/London"))
    day = (now.date() - timedelta(days=1)).isoformat()

    companies, failed = {}, {}
    for place in PLACES:
        try:
            items = search(key, place, day)
        except Exception as exc:  # keep going; report the place as unsearched
            failed[place] = str(exc)
            continue
        for item in items:
            num = item.get("company_number")
            if not num:
                continue
            if num not in companies:
                addr = item.get("registered_office_address") or {}
                companies[num] = {
                    "name": item.get("company_name"),
                    "number": num,
                    "type": item.get("company_type"),
                    "status": item.get("company_status"),
                    "incorporated": item.get("date_of_creation"),
                    "address": ", ".join(str(v) for v in addr.values() if v),
                    "address_line_1": addr.get("address_line_1"),
                    "premises": addr.get("premises"),
                    "postcode": addr.get("postal_code"),
                    "care_of": addr.get("care_of"),
                    "po_box": addr.get("po_box"),
                    "sic_codes": item.get("sic_codes") or [],
                    "url": f"https://find-and-update.company-information.service.gov.uk/company/{num}",
                    "matched_places": [],
                }
            companies[num]["matched_places"].append(place)
        time.sleep(0.3)

    out = {
        "date": day,
        "generated_at": now.isoformat(),
        "searched_places": [p for p in PLACES if p not in failed],
        "failed_places": failed,
        "count": len(companies),
        "companies": sorted(companies.values(), key=lambda c: (c["name"] or "")),
    }
    os.makedirs("results", exist_ok=True)
    for path in (f"results/{day}.json", "results/latest.json"):
        with open(path, "w") as f:
            json.dump(out, f, indent=2)
    print(f"{day}: {len(companies)} companies, {len(failed)} places failed")
    if len(failed) == len(PLACES):
        sys.exit("Every search failed")


if __name__ == "__main__":
    main()
