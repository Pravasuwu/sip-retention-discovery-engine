---
title: Explain My Returns
emoji: 📈
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
short_description: Plain-words SIP returns explainer (prototype, not advice)
---

# Explain My Returns (MVP)

A prototype for first-time SIP investors: a Groww-style SIP screen with a plain-words
card and an AI that answers "is my SIP working?" in the investor's own words.
**Not investment advice. Not affiliated with Groww.**

## How it stays safe
1. **Numbers come from code** (`returns.py`), replaying real NAV history. The AI never calculates.
2. **Before the AI** (`guard.classify_question`): advice, prediction, support, off-topic and personal-data
   questions get a fixed reply, with official links where useful.
3. **After the AI** (`guard.check_reply`): replies with advice words, fund-house names, or any ₹ or % not
   in the investor's account are blocked and replaced by a checked answer, or "not sure" + official links.
4. **No key / AI down** → checked answers only. The app always works.

## Quality check
`eval/test_questions.csv` has 25 questions built from the Evidence Log golden set (each row names its golden-set item).
`python eval/run_eval.py` scores behaviour, content and safety, and writes `eval/results.json`, which the app shows
behind the shield icon.

## Run locally
```
pip install -r requirements.txt
set GROQ_API_KEY=...        # optional
uvicorn server:app --port 8600
```

Files: `server.py` (API + static), `returns.py` (SIP maths), `guard.py` (checks), `ai.py` (Groq + fallbacks),
`static/` (frontend), `data/navs.json` (from `fetch_navs.py`, source api.mfapi.in).
