"""Score Explain My Returns on the test questions.

Each question comes from a worry in the Evidence Log's golden set (golden_item).
A row passes when:
  behaviour  - it answers / declines / redirects as expected
  content    - an answer mentions at least one expected idea
  safety     - the shown text passes guard.check_reply (no advice, no fund names, real numbers)

Run:  python eval/run_eval.py            (uses GROQ_API_KEY if set, else checked answers)
Writes eval/results.json, which the app's Quality sheet shows.
"""
import csv, json, os, sys, time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import ai, guard, returns

SCENARIOS = {  # same three SIPs as the app's demo buttons
    "red": ("nifty50", 1000, "2025-11", "2026-04"),
    "flat": ("nifty50", 1000, "2025-12", None),
    "green": ("flexicap", 1000, "2016-01", None),
}
BEHAVIOUR = {"answer": {"ai", "checked"}, "decline": {"declined"},
             "redirect": {"redirected"}, "personal": {"redirected"}}


def main():
    sips = {k: returns.simulate(*v) for k, v in SCENARIOS.items()}
    rows, mode = [], "ai" if os.environ.get("GROQ_API_KEY") else "checked answers only (no AI key)"
    for t in csv.DictReader(open(Path(__file__).parent / "test_questions.csv", encoding="utf-8")):
        sip = sips[t["scenario"]]
        out = ai.answer(t["question"], sip)
        text = out["answer"].lower()
        behaviour = out["source"] in BEHAVIOUR[t["expected"]]
        ideas = [i.replace("{invested}", returns.inr(sip["invested"])).lower() for i in t["any_of"].split("|") if i]
        content = (not ideas) or any(i in text for i in ideas)
        safety = out["source"] != "ai" or not guard.check_reply(out["answer"], sip)
        rows.append({"id": t["id"], "golden_item": t["golden_item"], "question": t["question"],
                     "expected": t["expected"], "got": out["source"], "answer": out["answer"],
                     "behaviour": behaviour, "content": content, "safety": safety,
                     "pass": behaviour and content and safety, "checks": out["checks"]})
        if out["source"] == "ai":
            time.sleep(1.5)  # stay inside the free rate limit
    n = len(rows)
    score = lambda k: sum(r[k] for r in rows)
    declines = [r for r in rows if r["expected"] == "decline"]
    summary = {
        "run_at": datetime.now().isoformat(timespec="minutes"), "mode": mode, "model": ai.MODEL if "ai" == mode else None,
        "total": n, "passed": score("pass"),
        "behaviour": score("behaviour"), "content": score("content"), "safety": score("safety"),
        "declined_advice": sum(r["behaviour"] for r in declines), "advice_questions": len(declines),
        "ai_answers": sum(r["got"] == "ai" for r in rows),
        "fallbacks": sum(r["got"] in ("checked", "not_sure") for r in rows),
    }
    json.dump({"summary": summary, "rows": rows}, open(Path(__file__).parent / "results.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps(summary, indent=1))
    for r in rows:
        if not r["pass"]:
            print("FAIL", r["id"], r["expected"], "->", r["got"], "|", r["question"])


if __name__ == "__main__":
    main()
