"""Explain My Returns: answer an investor's question about their own SIP.

Flow:  question -> guard.classify_question
         advice / support / off_topic / personal -> fixed safe reply (no AI)
         ok -> Groq LLM with the investor's computed numbers
              -> guard.check_reply -> pass: show  |  fail: checked answer or "not sure"
If no GROQ_API_KEY is set, ok questions get the checked answer bank.
"""
import json
import os
import re
import urllib.request

import guard
from returns import inr

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

KNOWLEDGE = """Facts you may use (general, not advice):
- A SIP invests the same amount every month. When the price (NAV) is low, that amount buys more units; when high, fewer units. Over time this averages the cost per unit.
- Equity fund values move up and down every day. In the first months, most of the money has been invested only briefly, so a small market fall can make the whole SIP show red.
- Returns that look small or negative early are common and say little about the long run. Nobody can predict what markets will do next.
- XIRR is a yearly return rate that accounts for each instalment's timing. With under 12 months of instalments it swings a lot and is not meaningful.
- The value shown in the app uses the latest NAV. When you redeem, you get the NAV of the processing day, which can differ from what you saw.
- On Groww you can change your SIP amount or date anytime (about 2 working days before the debit date), or skip one instalment at a time. Three missed or skipped instalments in a row cancel the SIP.
- Compounding means gains start earning gains; it needs time to become visible.
"""

SYSTEM = """You are "Explain My Returns", a helper inside an investing app for first-time SIP investors in India.
Your job: explain the investor's OWN SIP numbers in plain, warm, simple English (Class 8 reading level).

Hard rules:
1. Never give investment advice. Never say whether to stop, continue, buy, sell, switch, increase or reduce. Never name or rate a fund or fund house. Never predict markets or promise returns.
2. Use ONLY the numbers in INVESTOR_NUMBERS. Never calculate new rupee amounts or percentages. If a number you need is not there, don't use one.
3. Keep it under 90 words. No lists, no markdown, no emoji.
4. If you are not sure, or the question needs information you don't have, set "sure" to false.

Reply only as JSON: {"answer": "<text>", "sure": true|false}
"""


def _facts(sip: dict) -> dict:
    keep = ["fund", "amount", "start_month", "as_of", "instalments", "invested", "value", "gain",
            "gain_pct", "xirr_pct", "units", "avg_cost", "latest_nav", "red_months",
            "low_price_buys", "most_units", "fewest_units", "most_units_month", "lowest_nav", "highest_nav"]
    f = {k: sip[k] for k in keep if k in sip}
    if f.get("instalments", 0) < 12:
        f.pop("xirr_pct", None)  # too early to be meaningful
    return f


def call_groq(question: str, sip: dict) -> dict | None:
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        return None
    body = {
        "model": MODEL,
        "temperature": 0.2,
        "max_tokens": 300,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM + "\n" + KNOWLEDGE},
            {"role": "user", "content": "INVESTOR_NUMBERS: " + json.dumps(_facts(sip))
             + "\nQUESTION: " + question},
        ],
    }
    req = urllib.request.Request(GROQ_URL, data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json",
                                          "User-Agent": "explain-my-returns/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            content = json.load(r)["choices"][0]["message"]["content"]
        out = json.loads(content)
        return {"answer": str(out.get("answer", "")).strip(), "sure": bool(out.get("sure", False))}
    except Exception as e:  # network, quota, bad JSON: fall back safely
        print("groq error:", repr(e)[:200])
        return None


# ---------- checked answers (no AI) ----------

def _checked(q: str, s: dict) -> str | None:
    low = q.lower()
    gain_word = "below" if s["gain"] < 0 else "above"
    rules = [
        (r"total|how much (have i|did i)|invested|worth|value",
         f"You have put in {inr(s['invested'])} over {s['instalments']} instalments. "
         f"Today it is worth {inr(s['value'])}, which is {inr(s['gain'])} {gain_word} what you put in."),
        (r"chart|graph|line",
         "The purple line is what your SIP is worth each day. The dotted line is the money you have put in; it steps up "
         "on each instalment. When purple is above dotted you are up; below, you are down. The gap moves daily with prices."),
        (r"xirr",
         "XIRR is a yearly return rate that counts when each instalment went in. "
         "In the first year or two it swings a lot, because most of your money has been invested only briefly. "
         "A high or low XIRR early on says little about the long run."),
        (r"redeem|got less|got only|less than (it )?show",
         "The app shows your value at the latest price (NAV). When you redeem, you get the NAV of the day the request is processed, "
         "and prices move every day. So the amount can be a little different from what you saw."),
        (r"skip|pause|change (the )?(amount|date)",
         "On Groww you can change your SIP amount or date anytime, about 2 working days before the debit date, "
         "or skip one instalment at a time. Three missed or skipped instalments in a row cancel the SIP."),
        (r"units?|nav|price",
         f"Each month your {inr(s['amount'])} buys units at that day's price. When prices were low it bought up to "
         f"{s.get('most_units', '-')} units; when high, as few as {s.get('fewest_units', '-')}. "
         "Buying more units when prices are low is how a SIP averages your cost."
         if s.get("most_units") else
         f"Each month your {inr(s['amount'])} buys units at that day's price (NAV). Low prices buy more units, high prices fewer."),
        (r"red|loss|negative|down|fall|minus",
         f"Your SIP is {inr(s['gain'])} {gain_word} the {inr(s['invested'])} you put in. "
         "Early on this is common: most of your money went in recently, so a market dip shows up across the whole SIP. "
         "While prices are low, each instalment buys more units."),
        (r"zero|no returns?|nothing|working|compound|small|flat|low returns?",
         f"After {s['instalments']} instalments your SIP is worth {inr(s['value'])} on {inr(s['invested'])} put in. "
         "Compounding means gains start earning gains, and that needs time to show. "
         "Small returns in the early months are common and say little about the long run."),
        (r"how long|wait|years|when will",
         "Nobody can say when markets will rise. Equity funds are usually meant for goals five or more years away, "
         "because values move a lot in any single year."),
        (r"what is (a )?sip|manual|differen|by hand",
         "A SIP invests the same amount automatically every month. Investing by hand works the same way if you do it "
         "every month; the SIP just makes it automatic so you don't have to remember or time it."),
    ]
    for pattern, text in rules:
        if re.search(pattern, low):
            return text
    return None


NOT_SURE = ("I'm not sure I can answer that well, and I'd rather not guess. "
            "The official investor pages below explain how SIPs and returns work.")

DECLINE = ("I can't tell you what to do with your money. That's your decision, and nothing here is investment advice. "
           "I can explain what your numbers mean. For personal advice, you can speak to a SEBI-registered investment adviser.")

MONEY_TIGHT = (" If money is tight, Groww lets you change your SIP amount or date, or skip one instalment.")

REPLIES = {
    "support": "That sounds like an account or payment issue, which I can't see or fix. Please contact the app's help and support team.",
    "off_topic": "I can only help with questions about your SIP and its returns.",
    "personal": "Please don't share personal details like PAN, Aadhaar, phone numbers or passwords here. I don't need them to explain your SIP.",
}


def answer(question: str, sip: dict) -> dict:
    """Return {answer, source, checks, links}. source: ai | checked | declined | redirected | not_sure."""
    q = question.strip()[:300]
    kind = guard.classify_question(q)
    if kind == "advice":
        text = DECLINE + (MONEY_TIGHT if re.search(r"stop|job|money|afford|tight|pause", q.lower()) else "")
        return {"answer": text, "source": "declined", "checks": ["advice question: declined"], "links": guard.OFFICIAL}
    if kind in REPLIES:
        return {"answer": REPLIES[kind], "source": "redirected", "checks": [f"{kind}: not answered by AI"], "links": []}

    ai = call_groq(q, sip)
    if ai and ai["sure"] and ai["answer"]:
        problems = guard.check_reply(ai["answer"], sip)
        if not problems:
            return {"answer": ai["answer"], "source": "ai",
                    "checks": ["no advice", "no fund names", "numbers match your account"], "links": []}
        checks = [f"AI reply blocked: {p}" for p in problems]
    elif ai:
        checks = ["AI was not sure"]
    else:
        checks = ["AI unavailable"]

    fixed = _checked(q, sip)
    if fixed:
        return {"answer": fixed, "source": "checked", "checks": checks + ["showing a checked answer"], "links": []}
    return {"answer": NOT_SURE, "source": "not_sure", "checks": checks, "links": guard.OFFICIAL}
