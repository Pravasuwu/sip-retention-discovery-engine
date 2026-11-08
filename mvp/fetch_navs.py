"""Download real NAV history for the sample SIPs and keep one NAV per month.

Run once: python fetch_navs.py  ->  data/navs.json
Source: api.mfapi.in (public AMFI NAV mirror).
"""
import json, urllib.request
from datetime import datetime

# Shown in the app by category only, so nothing reads as a fund tip.
FUNDS = {
    "nifty50": {"label": "Nifty 50 index fund", "code": 120716},
    "flexicap": {"label": "Flexi cap fund", "code": 122639},
    "midcap": {"label": "Mid cap fund", "code": 127042},
}

out = {}
for key, f in FUNDS.items():
    with urllib.request.urlopen(f"https://api.mfapi.in/mf/{f['code']}", timeout=30) as r:
        raw = json.load(r)
    rows = sorted(
        (datetime.strptime(d["date"], "%d-%m-%Y").date(), float(d["nav"]))
        for d in raw["data"] if float(d["nav"]) > 0
    )
    monthly = {}
    for day, nav in rows:  # first NAV of each month = SIP debit day
        monthly.setdefault(day.strftime("%Y-%m"), (day.isoformat(), nav))
    last_day, last_nav = rows[-1]
    out[key] = {
        "label": f["label"],
        "source_scheme": raw["meta"]["scheme_name"],
        # Daily NAVs from 2015 power the Groww-style chart and the 1D returns row.
        "daily": [[d.isoformat(), n] for d, n in rows if d.year >= 2015],
        "monthly": [{"month": m, "date": d, "nav": n} for m, (d, n) in sorted(monthly.items())],
        "latest": {"date": last_day.isoformat(), "nav": last_nav},
    }
    print(key, raw["meta"]["scheme_name"], len(monthly), "months, latest", last_day, last_nav)

with open("data/navs.json", "w") as fh:
    json.dump(out, fh)
