"""SIP maths. Every number the investor sees comes from here, never from the AI."""
import json
from datetime import date
from pathlib import Path

NAVS = json.loads((Path(__file__).parent / "data" / "navs.json").read_text())


def _xirr(flows):
    """Yearly return rate for dated cash flows [(date, amount)], by bisection."""
    t0 = flows[0][0]

    def npv(rate):
        return sum(a / (1 + rate) ** ((d - t0).days / 365.0) for d, a in flows)

    lo, hi = -0.99, 10.0
    if npv(lo) * npv(hi) > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        if npv(lo) * npv(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return round(mid * 100, 1)


def inr(n) -> str:
    """Rupees in Indian grouping: 221253 -> Rs 2,21,253."""
    n = int(round(abs(n)))
    s = str(n)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    return "₹" + s


def funds():
    return [{"key": k, "label": v["label"], "first_month": v["monthly"][0]["month"]}
            for k, v in NAVS.items()]


def simulate(fund_key: str, amount: int, start_month: str, as_of_month: str | None = None) -> dict:
    """Replay a monthly SIP on real NAVs from start_month to the latest NAV.

    as_of_month lets a tester see the SIP as it looked in a past month
    (valued at that month's debit-day NAV), e.g. to replay a red month.
    """
    f = NAVS[fund_key]
    rows = [r for r in f["monthly"] if r["month"] >= start_month]
    latest = f["latest"]
    if as_of_month:
        past = [r for r in f["monthly"] if r["month"] == as_of_month]
        if past:
            latest = {"date": past[0]["date"], "nav": past[0]["nav"]}
            rows = [r for r in rows if r["month"] <= as_of_month]
    # Skip a debit on the same day as the 'today' valuation.
    rows = [r for r in rows if r["date"] < latest["date"]]
    if not rows:
        raise ValueError("Start month is too recent; pick an earlier month.")

    units = invested = 0.0
    history, flows, red_months = [], [], 0
    for r in rows:
        u = amount / r["nav"]
        units += u
        invested += amount
        value = units * r["nav"]
        if value < invested:
            red_months += 1
        history.append({"month": r["month"], "nav": r["nav"], "units": round(u, 3),
                        "invested": round(invested), "value": round(value)})
        flows.append((date.fromisoformat(r["date"]), -amount))

    value = units * latest["nav"]
    flows.append((date.fromisoformat(latest["date"]), value))
    avg_cost = invested / units
    navs = [r["nav"] for r in rows]
    low_buys = [h for h in history if h["nav"] < avg_cost]
    worst = min(history, key=lambda h: h["value"] - h["invested"])
    gain = value - invested

    # Daily series (like the app's portfolio chart): units and money grow on each debit day.
    debits = {r["date"]: amount / r["nav"] for r in rows}
    daily, u_run, inv_run = [], 0.0, 0.0
    for d, nav in f.get("daily", []):
        if d < rows[0]["date"] or d > latest["date"]:
            continue
        if d in debits:
            u_run += debits[d]
            inv_run += amount
        daily.append([d, round(inv_run), round(u_run * nav)])
    one_day = (daily[-1][2] - daily[-2][2]) if len(daily) > 1 and daily[-1][1] == daily[-2][1] else 0
    prev_value = daily[-2][2] if len(daily) > 1 else value

    # Next debit: first trading day of the following month (shown as an estimate).
    ny, nm = divmod(int(latest["date"][:4]) * 12 + int(latest["date"][5:7]), 12)
    next_due = date(ny, nm + 1, 1).isoformat()

    return {
        "daily": daily,
        "one_day": one_day,
        "one_day_pct": round(one_day / prev_value * 100, 2) if prev_value else 0.0,
        "instalment_dates": [r["date"] for r in rows],
        "next_due": next_due,
        "fund": f["label"],
        "amount": amount,
        "start_month": rows[0]["month"],
        "as_of": latest["date"],
        "instalments": len(rows),
        "invested": round(invested),
        "value": round(value),
        "gain": round(gain),
        "gain_pct": round(gain / invested * 100, 1),
        "xirr_pct": _xirr(flows),
        "units": round(units, 3),
        "avg_cost": round(avg_cost, 2),
        "latest_nav": round(latest["nav"], 2),
        "red_months": red_months,
        "low_price_buys": len(low_buys),
        "most_units_month": max(history, key=lambda h: h["units"])["month"],
        "most_units": max(h["units"] for h in history),
        "fewest_units": min(h["units"] for h in history),
        "lowest_nav": round(min(navs), 2),
        "highest_nav": round(max(navs), 2),
        "worst_month": worst["month"],
        "worst_gap": round(worst["value"] - worst["invested"]),
        "history": history,
    }


def manual(amount: int, instalments: int, current_value: int) -> dict:
    """For investors who type the numbers from their own app (no NAV history)."""
    invested = amount * instalments
    gain = current_value - invested
    today = date.today()
    flows = []
    for i in range(instalments):
        m = today.month - (instalments - i)
        y = today.year + (m - 1) // 12
        flows.append((date(y, (m - 1) % 12 + 1, 1), -amount))
    flows.append((today, current_value))
    return {
        "fund": "Your SIP",
        "amount": amount,
        "instalments": instalments,
        "invested": invested,
        "value": current_value,
        "gain": gain,
        "gain_pct": round(gain / invested * 100, 1) if invested else 0.0,
        "xirr_pct": _xirr(flows) if invested else None,
        "as_of": today.isoformat(),
        "history": [],
    }


def stage(s: dict) -> str:
    """Which plain-words story fits this SIP. Drives the card and the AI's context."""
    months = s["instalments"]
    if s["gain"] < 0 and months <= 12:
        return "early_red"
    if s["gain"] < 0:
        return "long_red"
    if s["gain_pct"] < 5 and months <= 24:
        return "flat"
    return "green"


def card(s: dict) -> dict:
    """The fixed, non-AI explanation. Same words for everyone in a stage."""
    st = stage(s)
    rs = inr
    headline = {
        "early_red": f"Your SIP is {rs(s['gain'])} below what you put in. That is common in the first year.",
        "long_red": f"Your SIP is {rs(s['gain'])} below what you put in after {s['instalments']} months.",
        "flat": f"Your SIP is up {rs(s['gain'])}. Early on, returns often look small.",
        "green": f"Your SIP is up {rs(s['gain'])} on the {rs(s['invested'])} you put in.",
    }[st]
    points = [
        f"You have paid {s['instalments']} instalments of {rs(s['amount'])}, so {rs(s['invested'])} in total.",
        f"Today it is worth {rs(s['value'])}.",
    ]
    if s.get("history"):
        points.append(
            f"When prices were low your {rs(s['amount'])} bought up to {s['most_units']} units; "
            f"when high, as few as {s['fewest_units']}. Buying more when prices are low is how a SIP works."
        )
    if s.get("xirr_pct") is not None and s["instalments"] >= 12:
        points.append(f"Your yearly return rate (XIRR) is {s['xirr_pct']}%.")
    elif s.get("xirr_pct") is not None:
        points.append("A yearly return rate is not meaningful yet: most of your money has been in for only a few months.")
    return {"stage": st, "headline": headline, "points": points}
