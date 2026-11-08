"""Safety checks on both sides of the AI.

Before: classify the question (fine / advice / support / off-topic / personal data).
After:  check the AI's reply (no advice words, no fund names, every number real).
"""
import re

OFFICIAL = [
    {"name": "AMFI investor corner", "url": "https://www.amfiindia.com/investor-corner"},
    {"name": "SEBI investor website", "url": "https://investor.sebi.gov.in/"},
]

# ---------- before the AI ----------

PERSONAL = [
    r"\b[A-Z]{5}\d{4}[A-Z]\b",          # PAN
    r"\b\d{4}\s?\d{4}\s?\d{4}\b",       # Aadhaar
    r"\b[6-9]\d{9}\b",                  # Indian mobile
    r"\S+@\S+\.\S+",                    # email
    r"\b(otp|password|pin|cvv)\b",
]

SUPPORT = r"\b(blocked|withdraw\w*|refund|kyc|login|log in|customer care|support|weekend|holiday|credited|debited twice|account (is )?(blocked|frozen))\b"

SIP_WORDS = r"\b(sip|sips|return\w*|xirr|nav|units?|fund\w*|invest\w*|market\w*|red|loss\w*|profit|gain\w*|value|worth|instal+ments?|skip\w*|pause\w*|stop\w*|money|compound\w*|grow\w*|portfolio|amount|mutual|equity|fd|fds|price\w*|redeem\w*|sell|buy|negative|down|fall\w*|working|earn\w*|percent|chart|graph|line|dotted|purple|%)\b"


def is_advice_request(q: str) -> bool:
    """True when the investor asks us to decide for them.

    Examples that must be True:
      "Should I stop my SIP?", "Which small cap fund should I buy?",
      "Is this a good time to invest more?", "Is an FD better than my SIP?",
      "Will the market go up next month?", "Guarantee me 12% returns?"
    Examples that must be False (we explain these):
      "Why is my SIP red?", "What is XIRR?", "How do I skip one instalment?",
      "Do I really buy more units when the price is low?"
    """
    return any(re.search(p, q) for p in ADVICE_ASKS)


# Questions that ask us to decide or predict. "should i stop" is advice;
# "how do i skip" is not, so verbs only count after "should i".
ADVICE_ASKS = [
    r"\bshould (i|we)\b.*\b(stop|continue|keep|sell|buy|redeem|switch|exit|pause|cancel|skip|invest|increase|reduce|hold|break|withdraw|start|move|put|add|wait)\b",
    r"\b(which|what|best|top|good) (mutual )?(fund|funds|scheme|schemes|stock|stocks)\b",
    r"\b(good|right|best|bad|wrong) time to\b",
    r"\bbetter (than|option|choice|for me)\b|\bis (an? |the )?\w+ better\b",
    r"\bwill (the )?(market|markets|nifty|sensex|fund|price|prices|nav|it|my sip)\b.*\b(go up|rise|recover|fall|crash|grow|come back|go down|improve)\b",
    r"\bguarantee",
    r"\b(recommend|suggest|advise)\b",
    r"\bis it (safe|wise|smart|worth)\b",
    r"\bwhere (should|do|can) i (invest|put)\b",
    r"\b(stop|sell|redeem|exit|cancel) or (continue|keep|hold)\b",
    r"\bwhat (would|should) (you|i) do\b",
]


def classify_question(q: str) -> str:
    """One of: ok, advice, support, off_topic, personal."""
    text = q.strip()
    low = text.lower()
    if any(re.search(p, text if p.startswith(r"\b[A-Z]") else low) for p in PERSONAL):
        return "personal"
    if is_advice_request(low):
        return "advice"
    if re.search(SUPPORT, low):
        return "support"
    if not re.search(SIP_WORDS, low):
        return "off_topic"
    return "ok"


# ---------- after the AI ----------

ADVICE_IN_REPLY = [
    r"\byou should (stop|continue|keep|sell|buy|redeem|switch|invest|exit|pause|increase|reduce|decrease|hold)",
    r"\b(i|we) (would )?(recommend|suggest|advise)\b",
    r"\bmy advice\b",
    r"\b(buy|sell|redeem|exit|switch) (now|it|this fund|your sip)\b",
    r"\b(is|are|returns?) guaranteed\b|\bi guarantee\b",
    r"\bwill (definitely|surely|certainly)\b",
    r"\b(good|right|best) time to (buy|invest|sell|stop)\b",
    r"\bbest fund\b",
]

FUND_HOUSES = r"\b(uti|parag parikh|ppfas|motilal|hdfc|sbi|icici|axis|nippon|kotak|mirae|quant|tata|dsp|aditya birla|franklin|edelweiss|invesco|bandhan|canara robeco|hsbc|groww mutual)\b"


def _close(x: float, allowed: list[float], tol: float) -> bool:
    return any(abs(x - a) <= tol for a in allowed)


def check_reply(reply: str, sip: dict) -> list[str]:
    """Return the list of problems found. Empty list = safe to show."""
    problems = []
    low = reply.lower()
    for p in ADVICE_IN_REPLY:
        if re.search(p, low):
            problems.append("sounds like advice")
            break
    if re.search(FUND_HOUSES, low):
        problems.append("names a fund house")

    rupees = [sip.get(k) for k in ("invested", "value", "amount", "avg_cost", "latest_nav", "lowest_nav", "highest_nav")]
    rupees = [abs(float(v)) for v in rupees if v is not None] + [abs(float(sip.get("gain", 0)))]
    for m in re.findall(r"(?:₹|rs\.?|inr)\s?([\d,]+(?:\.\d+)?)", low):
        if not _close(float(m.replace(",", "")), rupees, 1.0):
            problems.append(f"₹{m} is not in your account")
            break

    pcts = [abs(float(sip[k])) for k in ("gain_pct", "xirr_pct") if sip.get(k) is not None]
    for m in re.findall(r"(\d+(?:\.\d+)?)\s?%", low):
        if not _close(float(m), pcts, 0.15):
            problems.append(f"{m}% is not your number")
            break

    if len(reply.split()) > 130:
        problems.append("too long")
    return problems
