"""Explain My Returns: web server.

Run locally:  uvicorn server:app --port 8600
The browser never sends numbers to trust: the server recomputes the SIP from
its inputs, so the AI only ever sees numbers the system calculated.
"""
import json
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import ai
import returns

ROOT = Path(__file__).parent
app = FastAPI(title="Explain My Returns")


class SipInput(BaseModel):
    mode: str = "sample"                      # sample | manual
    fund: str = "nifty50"
    amount: int = Field(1000, ge=100, le=1_000_000)
    start: str = "2025-11"
    as_of: str | None = None
    instalments: int = Field(6, ge=1, le=480)
    current_value: int = Field(0, ge=0, le=100_000_000)


class AskInput(BaseModel):
    question: str = Field(..., min_length=2, max_length=300)
    sip: SipInput


def build(s: SipInput) -> dict:
    try:
        if s.mode == "manual":
            sip = returns.manual(s.amount, s.instalments, s.current_value)
        else:
            if s.fund not in returns.NAVS:
                raise ValueError("Unknown sample fund.")
            sip = returns.simulate(s.fund, s.amount, s.start, s.as_of)
    except ValueError as e:
        raise HTTPException(400, str(e))
    sip["card"] = returns.card(sip)
    sip["display"] = {k: returns.inr(sip[k]) for k in ("invested", "value", "gain", "amount")}
    return sip


# Small per-visitor limit so the free AI quota isn't used up by one person.
HITS: dict[str, deque] = defaultdict(deque)
LIMIT, WINDOW = 20, 600


def allowed(ip: str) -> bool:
    now, q = time.time(), HITS[ip]
    while q and now - q[0] > WINDOW:
        q.popleft()
    if len(q) >= LIMIT:
        return False
    q.append(now)
    return True


@app.get("/api/funds")
def funds():
    return {"funds": returns.funds(), "months": {k: [m["month"] for m in v["monthly"]] for k, v in returns.NAVS.items()},
            "latest": next(iter(returns.NAVS.values()))["latest"]["date"]}


@app.post("/api/sip")
def sip(s: SipInput):
    return build(s)


@app.post("/api/ask")
def ask(body: AskInput, request: Request):
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0]
    if not allowed(ip):
        raise HTTPException(429, "You've asked a lot of questions. Please wait a few minutes.")
    sip = build(body.sip)
    return ai.answer(body.question, sip)


@app.get("/api/quality")
def quality():
    p = ROOT / "eval" / "results.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"summary": None, "rows": []}


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
