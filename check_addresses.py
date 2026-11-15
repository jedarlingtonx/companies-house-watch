#!/usr/bin/env python3
"""Flag registered offices that look like an accountant, formation agent or virtual office.

Adds an "address_check" field to every company in the daily results files
(only for companies that don't have one yet) and refreshes results/latest.json.
"""
import glob
import json
import os
import re
import time

import requests

API = "https://api.company-information.service.gov.uk/advanced-search/companies"
OTHERS_THRESHOLD = 3  # this many other companies at the same address = shared address

STRONG = [
    (r"\bc/o\b|\bcare of\b", "c/o (care of) address"),
    (r"\bp\.?\s?o\.?\s?box\b", "PO box"),
    (r"accountan|accounting|bookkeep", "address mentions accountancy"),
    (r"chartered|solicitor|\bllp\b", "address mentions a professional firm"),
    (r"&\s*co\b|\band co\b", "address contains '& Co'"),
    (r"business cent(re|er)|serviced office|virtual office", "business centre / serviced office"),
    (r"formations|company secretar|registered office", "company formation / registered office service"),
]
WEAK = [
    (r"\bsuite\b", "suite"),
    (r"\bfloor\b", "floor"),
    (r"\bunit\b", "unit"),
    (r"\boffices?\b", "office"),
    (r"\bcent(re|er)\b", "centre"),
    (r"workspace|innovation|enterprise|\bhub\b", "shared-workspace wording"),
]
POSTCODE = re.compile(r"[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}", re.I)


def norm(text):
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def postcode_of(c):
    if c.get("postcode"):
        return c["postcode"]
    m = POSTCODE.search(c.get("address") or "")
    return m.group(0) if m else None


def line_keys(c):
    keys = set()
    first = (c.get("address") or "").split(",")[0]
    keys.add(norm(first))
    if c.get("address_line_1"):
        keys.add(norm(c["address_line_1"]))
        keys.add(norm(f"{c.get('premises') or ''} {c['address_line_1']}"))
    keys.discard("")
    return keys


def count_others(c, key):
    """How many OTHER companies are registered at the same address (None if unknown)."""
    pc, mine = postcode_of(c), line_keys(c)
    if not key or not pc or not mine:
        return None
    r = None
    for _ in range(2):
        try:
            r = requests.get(API, params={"location": pc, "size": 100},
                             auth=(key, ""), timeout=30)
        except Exception:
            return None
        if r.status_code == 429:
            time.sleep(30)
            continue
        break
    if r is None or r.status_code == 404:
        return 0 if r is not None else None
    if not r.ok:
        return None
    n = 0
    for item in r.json().get("items") or []:
        if item.get("company_number") == c.get("number"):
            continue
        a = item.get("registered_office_address") or {}
        if norm(a.get("postal_code")) != norm(pc):
            continue
        theirs = {norm(a.get("address_line_1")),
                  norm(f"{a.get('premises') or ''} {a.get('address_line_1') or ''}")}
        if mine & theirs:
            n += 1
    return n


def check(c, key):
    text = (c.get("address") or "").lower()
    strong, weak = [], []
    if c.get("care_of"):
        strong.append("c/o (care of) address")
    if c.get("po_box"):
        strong.append("PO box")
    for pattern, label in STRONG:
        if re.search(pattern, text) and label not in strong:
            strong.append(label)
    for pattern, label in WEAK:
        if re.search(pattern, text):
            weak.append(label)
    others = count_others(c, key)
    if others is not None and others >= OTHERS_THRESHOLD:
        strong.append(f"{others} other companies registered at this address")
    third_party = bool(strong) or len(weak) >= 2
    return {
        "third_party": third_party,
        "reasons": (strong + weak) if third_party else [],
        "others_at_address": others,
    }


def main():
    key = os.environ.get("CH_API_KEY")
    files = sorted(glob.glob("results/20*.json"))
    if not files:
        raise SystemExit("No daily result files found")
    newest = None
    for path in files:
        with open(path) as f:
            data = json.load(f)
        changed = False
        for c in data["companies"]:
            if "address_check" not in c:
                c["address_check"] = check(c, key)
                changed = True
                time.sleep(0.3)
        if changed:
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
        newest = data
    with open("results/latest.json", "w") as f:
        json.dump(newest, f, indent=2)
    flagged = sum(1 for c in newest["companies"] if c["address_check"]["third_party"])
    print(f"{newest['date']}: {flagged} of {len(newest['companies'])} flagged as third-party addresses")


if __name__ == "__main__":
    main()
