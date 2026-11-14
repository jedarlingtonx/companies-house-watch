#!/usr/bin/env python3
"""Email the day's results, with the Excel file attached."""
import json
import os
import smtplib
import ssl
from datetime import date
from email.message import EmailMessage

TO = "james@pixel-north.co.uk"
XLSX = "results/new-companies.xlsx"


def main():
    user = "".join(os.environ["GMAIL_USER"].split())
    password = "".join(os.environ["GMAIL_APP_PASSWORD"].split())

    with open("results/latest.json") as f:
        data = json.load(f)
    day = date.fromisoformat(data["date"]).strftime("%A %d %B %Y")
    n = data["count"]

    lines = [f"New incorporations on {day}: {n} found (unchecked).", ""]
    if n:
        for c in data["companies"]:
            places = ", ".join(c["matched_places"])
            lines.append(f"- {c['name']} ({c['number']}) - {c['address']} [{places}]")
            lines.append(f"  {c['url']}")
    else:
        lines.append("No new incorporations found.")
    if data["failed_places"]:
        lines += ["", "Places that could not be searched: "
                  + ", ".join(data["failed_places"])]
    lines += ["", "These results are raw: a place name can match a street or another "
              "county, so check the addresses. The attached workbook has a 'Latest' "
              "sheet for this day and an 'All' sheet for every day collected so far."]

    msg = EmailMessage()
    msg["From"] = user
    msg["To"] = TO
    msg["Subject"] = f"Cheshire new companies - {data['date']} - Excel attached ({n} found)"
    msg.set_content("\n".join(lines))
    with open(XLSX, "rb") as f:
        msg.add_attachment(
            f.read(),
            maintype="application",
            subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=f"new-companies-{data['date']}.xlsx",
        )

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
        s.login(user, password)
        s.send_message(msg)
    print("Email sent")


if __name__ == "__main__":
    main()
