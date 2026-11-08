"""SIP Retention Discovery Engine - Streamlit app.

Reads the engine's saved output (engine/output) and shows it in the style of the original report:
white page, black text, one indigo highlight, orange for "stopped".
Run:  streamlit run app.py
Every number on every page is computed from engine/output, so re-running engine.py updates the app.
"""
import json
import math
import re
from collections import Counter
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).parent
OUT = ROOT / "engine" / "output"

st.set_page_config(page_title="SIP Retention Discovery Engine", page_icon="◉", layout="wide",
                   initial_sidebar_state="collapsed")

# ---------------------------------------------------------------- palette (same as the original report)
INK, MUTED, MIST, TRACK = "#000000", "#595959", "#e2e2e2", "#f1f1f3"
SPOT, STOP, BAR = "#4d49fc", "#ff7237", "#cfcfcf"
LIME, LILAC, BLUSH, AQUA = "#e4ff97", "#c4baff", "#ffc9c1", "#c7f8fb"
GRADE_COLOR = {"Strong": SPOT, "Moderate": "#8a87ff", "Weak": STOP, "Insufficient": "#c0392b"}

# ---------------------------------------------------------------- plain-language labels
TOPIC = {
    "T01": "Returns below expectation", "T02": "No visible progress", "T03": "Fear of market falls",
    "T04": "Income or life shock", "T05": "Can't pause or skip", "T06": "Auto-debit failures",
    "T07": "Unclear fees and charges", "T08": "Confusing return numbers", "T09": "Checking too often",
    "T10": "Seeks advice outside the app", "T11": "Distrust of market or funds", "T12": "Habit and long-term view",
    "T13": "Clear goal for the money", "T14": "Unsure about lump sums", "T15": "Choosing or switching funds",
    "T16": "Money access and support problems", "T17": "Too much SIP admin", "T18": "Moving money elsewhere",
}
POSITIVE_TOPICS = {"T12", "T13"}  # how stayers talk, not problems
STANCE = {
    "self: continuing": "Own story: still investing",
    "self: paused / stopped / at-risk": "Own story: paused or stopped",
    "self: stopped then resumed / mixed": "Own story: stopped, then restarted",
    "opinion: pro-continuation": "Opinion: keep going",
    "opinion: sceptical": "Opinion: doubts SIPs",
    "unclear": "Not clear",
}
TYPE_COLOR = {
    "Not clear": MIST, "Opinion: doubts SIPs": BLUSH, "Opinion: keep going": LILAC,
    "Own story: still investing": SPOT, "Own story: paused or stopped": STOP, "Own story: stopped, then restarted": "#ffb38f",
}
TIER = {"SIP-relevant": "About SIPs", "Out of scope (trading)": "Removed: trading", "App-general": "Removed: general app issue"}
SRC_COLORS = [SPOT, INK, LILAC, STOP, AQUA, LIME, BLUSH, BAR, "#8a87ff", "#7a7a7a"]


# ---------------------------------------------------------------- data
def _clean(s):
    return s.replace("�", "'") if isinstance(s, str) else s


@st.cache_data
def load(suffix=""):
    """suffix "" = keyword-rule labels, "_ai" = Claude labels (engine.py --labels ai). Same format either way."""
    out = json.loads((OUT / f"engine_output{suffix}.json").read_text(encoding="utf-8"))
    df = pd.read_csv(OUT / f"coded_records{suffix}.csv", encoding="utf-8-sig")
    df["text"] = df["text"].map(_clean)
    df["topics"] = df["themes"].fillna("").map(lambda s: [t for t in s.split(";") if t])
    df["Topic list"] = df["topics"].map(lambda ts: ", ".join(TOPIC.get(t, t) for t in ts))
    df["Comment type"] = df["stance"].map(STANCE).fillna("—")
    df["Group"] = df["tier"].map(TIER).fillna(df["tier"])
    # extra columns from the engine's input workbook: auto-collected flag, which app a Play review is about, date, link
    df["Auto-collected"] = df["sentiment"].eq("not coded")
    df["App"], df["Date"], df["Link"] = "", "", ""
    if INPUT.exists():
        src = pd.read_excel(INPUT, sheet_name="Reviews", usecols=["record_id", "platform", "source_date", "coding_notes", "source_url"])
        notes = src["coding_notes"].fillna("").astype(str)
        app = notes.str.extract(r"Play Store: ([^)]+)")[0]
        app = app.where(app.notna(), src["platform"].eq("Google Play").map({True: "Groww", False: None}))
        extra = pd.DataFrame({"record_id": src["record_id"], "Auto-collected": notes.str.contains("auto-collected"),
                              "App": app.fillna(""), "Date": src["source_date"].astype(str).str[:10].replace({"nan": "", "NaT": ""}),
                              "Link": src["source_url"].fillna("").astype(str)})
        df = df.drop(columns=["Auto-collected", "App", "Date", "Link"]).merge(extra, on="record_id", how="left")
        df["Auto-collected"] = df["Auto-collected"].fillna(False).astype(bool)
        df[["App", "Date", "Link"]] = df[["App", "Date", "Link"]].fillna("")
    return out, df


@st.cache_data
def load_extra():
    ur = ROOT / "user-research"
    people = pd.read_csv(ur / "participants.csv", encoding="utf-8-sig") if (ur / "participants.csv").exists() else None
    codes = pd.read_csv(ur / "codebook.csv", encoding="utf-8-sig") if (ur / "codebook.csv").exists() else None
    themes = []
    if (ur / "themes.md").exists():
        md = (ur / "themes.md").read_text(encoding="utf-8")
        for m in re.finditer(r"### Theme \d+\. (.+?)\n(.+?)(?=\n- |\n###|\Z)", md, flags=re.S):
            themes.append((m.group(1).strip(), " ".join(m.group(2).split())))
    surveys = pd.read_csv(SURVEYS, encoding="utf-8-sig") if SURVEYS.exists() else None
    return people, codes, themes, surveys


INPUT = ROOT / "engine" / "data" / "SIP_Reviews_With_Public.xlsx"
SURVEYS = ROOT / "engine" / "sources" / "published_surveys.csv"
LOG_URL = "https://claude.ai/artifact/7F8wcFQH29EzcvNJRnNsPa"
AI_EVAL = json.loads((OUT / "ai_eval.json").read_text(encoding="utf-8")) if (OUT / "ai_eval.json").exists() else None
LABEL_SETS = {"Keyword rules": ""}
if (OUT / "engine_output_ai.json").exists() and (OUT / "coded_records_ai.csv").exists():
    LABEL_SETS["Claude"] = "_ai"
# Rules stay the default: the deck's numbers come from them. Claude's labels are one click away.
LABELS = "Keyword rules"
if len(LABEL_SETS) > 1:
    LABELS = st.segmented_control("Labels", list(LABEL_SETS), default="Keyword rules", key="labels",
                                  help="Which labeller sorted the comments. Every number on every page follows this choice. "
                                       "See the Appendix for how each one scored against blind human labels.") or "Keyword rules"
D, DF = load(LABEL_SETS[LABELS])
PEOPLE, CODES, UR_THEMES, SURVEY_FIGS = load_extra()
META = D["meta"]
CORE = DF[DF["tier"] == "SIP-relevant"].copy()
SOURCES = list(META["core_platforms"])
SRC_COLOR = {s: SRC_COLORS[i % len(SRC_COLORS)] for i, s in enumerate(META["platforms"])}
N_AUTO = int(CORE["Auto-collected"].sum())
AUTO_NOTE = (f"{N_AUTO:,} of the {META['n_core']:,} SIP comments were collected automatically (forums, blogs, newsletters, "
             "Reddit, YouTube and Play Store). They count towards topics. Play Store reviews count as first-hand, because a review "
             "describes the writer's own use. No auto-collected comment counts as a stop until someone checks it by hand.")


def k_of(share, n):
    return int(round(share * n))


# ---------------------------------------------------------------- styling
st.markdown(
    """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300..700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
html, body, .stApp, .stMarkdown, p, li, label, h1, h2, h3, h4, input, textarea, select, button, a,
[data-testid="stNavigation"] span:not([data-testid="stIconMaterial"]) {font-family: "Inter", ui-sans-serif, system-ui, sans-serif !important;}
[data-testid="stIconMaterial"] {font-family: "Material Symbols Rounded" !important;}
.stApp {background: #ffffff;}
.block-container {padding-top: 4.2rem; max-width: 1200px;}
[data-testid="stSidebar"] {background: #ffffff; border-right: 1px solid #e2e2e2;}
h1, h2, h3 {font-weight: 320 !important; letter-spacing: -.015em; color: #000;}
h2 {font-size: clamp(30px, 4vw, 46px) !important; line-height: 1.1 !important; margin-top: 1.2rem !important;}
h3 {font-size: 24px !important; font-weight: 450 !important;}
p, li {color: #000;}
.eyebrow {font: 400 12px/1.3 "JetBrains Mono", monospace; letter-spacing: .05em; text-transform: uppercase; color: #595959; margin-bottom: 6px;}
.lede {font-size: 18px; line-height: 1.45; color: #595959; max-width: 68ch; margin: 6px 0 18px 0;}
.note {font-size: 14px; color: #595959;}
/* hero: quote collage with a floating card */
.hero {position: relative; padding: 56px 0; isolation: isolate; margin-bottom: 24px;}
.collage {position: absolute; inset: 0; z-index: -1; display: grid; grid-template-columns: repeat(4, minmax(0,1fr));
  grid-auto-rows: minmax(120px, auto); gap: 24px; padding: 8px 0; overflow: hidden;}
.tile {border-radius: 16px; padding: 16px; color: #111; font-size: 14px; line-height: 1.35; display: grid; gap: 8px;
  align-content: space-between; transform: rotate(var(--rot,0deg)); opacity: .95;}
.tile .src {font: 400 11px "JetBrains Mono", monospace; letter-spacing: .04em; opacity: .7;}
.hero-card {position: relative; max-width: 760px; margin: 0 auto; background: #fff; border-radius: 16px;
  box-shadow: 0 24px 70px rgba(0,0,0,.12); padding: 40px 44px; display: grid; gap: 16px;}
.hero-card h1 {font-size: clamp(34px, 5vw, 58px) !important; line-height: 1.08 !important; margin: 0 !important; padding: 0 !important;}
.hero-card .goal {font-size: 18px; color: #595959;}
.pill {display: inline-block; border-radius: 50px; padding: 8px 18px; font-weight: 480; font-size: 15px; margin-right: 8px;}
.pill.spot {background: #4d49fc; color: #fff;} .pill.ghost {border: 1px solid #000; color: #000;}
@media (max-width: 760px) {.collage {grid-template-columns: repeat(2, minmax(0,1fr));} .hero-card {padding: 28px 22px;}}
/* stats and cards */
.stat {border-top: 1px solid #000; padding-top: 12px; height: 100%;}
.stat .v {font-size: 40px; font-weight: 320; letter-spacing: -.02em; line-height: 1.05; font-variant-numeric: tabular-nums;}
.stat .l {font-size: 15px; font-weight: 520; margin-top: 6px;}
.stat .s {font-size: 13px; color: #595959; margin-top: 2px;}
.card {background: #fff; border: 1px solid #e2e2e2; border-radius: 16px; padding: 20px 22px; margin-bottom: 14px;}
.card h4 {margin: 0 0 8px 0; font-size: 18px; font-weight: 520;}
.card p {color: #333; margin: 0; font-size: 15px; line-height: 1.5;}
.card .meta {color: #595959; font-size: 13px; margin-top: 10px;}
.spotcard {background: #4d49fc; color: #fff; border-radius: 16px; padding: 24px 26px; margin: 10px 0 18px 0;}
.spotcard p, .spotcard b {color: #fff; font-size: 17px; line-height: 1.5; margin: 0;}
.spotcard .eyebrow {color: #d9d8ff;}
.quote {border-left: 3px solid #4d49fc; padding: 4px 0 4px 16px; margin: 0 0 18px 0;}
.quote.stop {border-left-color: #ff7237;}
.quote .q {font-size: 16px; line-height: 1.45; color: #000;}
.quote .m {font: 400 11px "JetBrains Mono", monospace; letter-spacing: .04em; color: #595959; margin-top: 6px; text-transform: uppercase;}
.chip {display: inline-block; font-size: 12px; padding: 3px 10px; border-radius: 50px; border: 1px solid #e2e2e2;
  color: #333; margin: 6px 6px 0 0; background: #fff;}
.rank {display: inline-block; font: 500 12px "JetBrains Mono", monospace; padding: 3px 10px; border-radius: 50px;
  background: #000; color: #fff; margin-right: 10px; vertical-align: middle;}
.rank.p0 {background: #4d49fc;}
.grade {display: inline-block; font: 500 11px "JetBrains Mono", monospace; letter-spacing: .05em; text-transform: uppercase;
  padding: 3px 10px; border-radius: 50px; color: #fff;}
.step {border-top: 1px solid #000; padding-top: 12px; height: 100%;}
.step .n {font: 400 12px "JetBrains Mono", monospace; color: #595959;}
.step .t {font-size: 18px; font-weight: 520; margin: 4px 0;}
.step .d {font-size: 14px; color: #595959;}
hr {border-color: #e2e2e2 !important;}
[data-testid="stExpander"] {border: 1px solid #e2e2e2 !important; border-radius: 12px !important;}
.stButton button {border-radius: 50px; border: 1px solid #000; background: #fff; color: #000;}
.stButton button:hover {border-color: #4d49fc; color: #4d49fc;}
footer {visibility: hidden;}
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------- small helpers
def head(eyebrow, title, lede=""):
    st.markdown(f'<div class="eyebrow">{eyebrow}</div>', unsafe_allow_html=True)
    st.markdown(f"## {title}")
    if lede:
        st.markdown(f'<div class="lede">{lede}</div>', unsafe_allow_html=True)


def stat(col, value, label, sub=""):
    col.markdown(f'<div class="stat"><div class="v">{value}</div><div class="l">{label}</div><div class="s">{sub}</div></div>',
                 unsafe_allow_html=True)


def card(title, body, meta="", chips=()):
    ch = "".join(f'<span class="chip">{c}</span>' for c in chips)
    m = f'<div class="meta">{meta}</div>' if meta else ""
    st.markdown(f'<div class="card"><h4>{title}</h4><p>{body}</p>{m}{ch}</div>', unsafe_allow_html=True)


def quote(row):
    stop = str(row.get("stance", "")).startswith(("self: paused", "self: stopped"))
    hand = "first-hand" if row["firsthand"] else ("auto-collected" if row["Auto-collected"] else "second-hand")
    text = row["text"] if len(row["text"]) < 420 else row["text"][:417].rsplit(" ", 1)[0] + "…"
    st.markdown(f'<div class="quote{" stop" if stop else ""}"><div class="q">“{text}”</div>'
                f'<div class="m">{row["platform"]}{" (" + row["App"] + ")" if row.get("App") else ""} · {hand} · '
                f'{row["Comment type"]} · {row["record_id"]}{" · " + row["Date"] if row.get("Date") else ""}</div></div>',
                unsafe_allow_html=True)


def style(fig, h=360):
    fig.update_layout(template="plotly_white", height=h, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      margin=dict(l=10, r=10, t=30, b=10), font=dict(family="Inter, sans-serif", color=INK, size=13),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0), bargap=0.35)
    fig.update_xaxes(gridcolor=TRACK, zeroline=False, linecolor=MIST)
    fig.update_yaxes(gridcolor=TRACK, zeroline=False, linecolor=MIST)
    return fig


def show(fig, container=st):
    container.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def donut(container, counts, title, colors, h=320):
    container.markdown(f"**{title}**")
    fig = go.Figure(go.Pie(
        labels=counts.index, values=counts.values, hole=.62, sort=False, direction="clockwise",
        domain=dict(x=[0, 0.52], y=[0, 1]),
        marker=dict(colors=[colors.get(k, BAR) for k in counts.index], line=dict(color="#fff", width=2)),
        textinfo="none", hovertemplate="%{label}<br>%{value} comments (%{percent:.1%})<extra></extra>",
    ))
    style(fig, h)
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=10),
                      legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=0.56, font=dict(size=13)),
                      annotations=[dict(text=f"{int(counts.sum()):,}<br><span style='font-size:12px;color:{MUTED}'>comments</span>",
                                        x=0.26, y=0.5, xref="paper", yref="paper", showarrow=False, font=dict(size=24))])
    # put percentages in the legend so they're readable without hover
    fig.data[0].labels = [f"{k}  {v / counts.sum():.0%}" for k, v in counts.items()]
    show(fig, container)


def hbar(labels, values, color=INK, h=None, text=None, xtitle=""):
    fig = go.Figure(go.Bar(y=labels, x=values, orientation="h", marker_color=color,
                           text=text if text is not None else values, textposition="outside", cliponaxis=False))
    fig.update_layout(xaxis_title=xtitle, yaxis=dict(autorange="reversed"))
    return style(fig, h or max(220, 34 * len(labels) + 60))


def topic_counts(frame):
    c = Counter(t for ts in frame["topics"] for t in ts)
    fh = Counter(t for ts, f in zip(frame["topics"], frame["firsthand"]) if f for t in ts)
    return pd.DataFrame([{"id": t, "topic": TOPIC[t], "n": c.get(t, 0), "firsthand": fh.get(t, 0)} for t in TOPIC]) \
        .sort_values("n", ascending=False)


def strongest_stop_link():
    th = D["themes"]
    cands = [(t, v) for t, v in th.items() if v["n"] >= 5 and t not in POSITIVE_TOPICS]
    t, v = max(cands, key=lambda x: x[1]["at_risk_share"])
    return t, v["n"], k_of(v["at_risk_share"], v["n"])


# ================================================================ pages
def page_summary():
    # collage of short first-hand quotes behind the hero card
    own = CORE[CORE["firsthand"] & CORE["text"].str.len().between(50, 150)]
    own = own.sort_values("stance", key=lambda s: ~s.fillna("").str.startswith("self")).head(8)
    tints, rots = [LIME, LILAC, BLUSH, AQUA], ["-2deg", "1.5deg", "-1deg", "2deg"]
    tiles = "".join(f'<div class="tile" style="background:{tints[i % 4]};--rot:{rots[i % 4]}"><div>“{r.text}”</div>'
                    f'<div class="src">{r.platform}</div></div>' for i, r in enumerate(own.itertuples()))
    st.markdown(
        f"""<div class="hero"><div class="collage">{tiles}</div>
        <div class="hero-card"><div class="eyebrow">First-time mutual fund investors · Groww</div>
        <h1>Why first SIPs stop, and what would keep them running</h1>
        <div class="goal">Goal: more first-time investors still have their first SIP running 12 months after they start it.</div>
        <div><span class="pill spot">{META['n_core']:,} SIP comments</span><span class="pill ghost">{len(SOURCES)} public sources</span></div>
        </div></div>""", unsafe_allow_html=True)

    head("The short version", "What we found",
         f"{META['n_total']:,} public comments were collected. {META['n_total'] - META['n_core']} about trading or general app bugs were "
         f"removed, leaving {META['n_core']:,} about SIPs from {META['n_authors_core']:,} different people.")
    t = META["tiers"]
    c = st.columns(4)
    stat(c[0], f"{META['n_total']:,}", "Comments collected", f"{len(META['platforms'])} sources")
    stat(c[1], f"{t['Out of scope (trading)'] + t['App-general']}", "Removed", f"{t['Out of scope (trading)']} trading · {t['App-general']} app bugs")
    stat(c[2], f"{META['n_core']:,}", "About SIPs", f"{META['n_core'] / META['n_total']:.0%} of everything collected")
    stat(c[3], f"{META['firsthand_core']}", "First-hand stories", "people describing their own SIP")
    st.write("")

    tc = topic_counts(CORE).set_index("id")
    problems = tc.drop(index=list(POSITIVE_TOPICS)).sort_values("n", ascending=False)
    by_fh = tc.drop(index=list(POSITIVE_TOPICS)).sort_values(["firsthand", "n"], ascending=False)
    sid, sn, sk = strongest_stop_link()
    lens = D["stance"]["lenses"]["behaviour"]
    rows = lens["rows"]
    stop_more = [r for r in sorted(rows, key=lambda r: -r["diff"]) if r["diff"] > 0][:2]
    stay_more = [r for r in sorted(rows, key=lambda r: r["diff"]) if r["diff"] < 0][:2]
    needs = D["needs"][:3]
    opps = D["opportunities"]

    findings = [
        ("What do people raise most?",
         "The biggest problems are " + ", ".join(f"<b>{TOPIC[i].lower()}</b> ({int(problems.loc[i, 'n'])})" for i in problems.index[:3])
         + f". The most-discussed topic overall is how stayers talk: <b>habit and a long-term view</b> ({int(tc.loc['T12', 'n'])})."),
        ("Which problems come up in people's own stories?",
         "Most first-hand stories are about " + ", ".join(f"<b>{TOPIC[i].lower()}</b> ({int(by_fh.loc[i, 'firsthand'])})" for i in by_fh.index[:3])
         + f". {META['firsthand_core']} of {META['n_core']:,} SIP comments are first-hand, most of them Play Store reviews."),
        ("What is most linked to stopping?",
         f"<b>{TOPIC[sid]}</b>: {sk} of {sn} comments come from people who stopped or paused, the highest share of any problem."),
        ("What separates stayers from leavers?",
         f"In {lens['na']} own stories of a SIP still running and {lens['nb']} of stopping, the stoppers talk more about "
         + " and ".join(f"<b>{TOPIC[r['theme']].lower()}</b>" for r in stop_more)
         + "; the stayers talk more about " + " and ".join(f"<b>{TOPIC[r['theme']].lower()}</b>" for r in stay_more) + "."),
        ("What do people need?", "Most often: " + "; ".join(f"<b>{n['need'].lower()}</b> ({n['n']})" for n in needs)
         + ". Counted from the hand-tagged comments only."),
        ("What to do first?", "; ".join(f"<b>{o['name']}</b>" for o in opps[:3]) + ". See the ranked list under What to do."),
    ]
    cols = st.columns(2)
    for i, (q, a) in enumerate(findings):
        with cols[i % 2]:
            card(q, a)

    fix = next((o for o in opps if sid in o["themes"]), None)
    also = f" The idea that targets it, <b>{fix['name']}</b>, ranks #{opps.index(fix) + 1}." if fix and fix is not opps[0] else ""
    st.markdown(f"""<div class="spotcard"><div class="eyebrow">Key finding</div><p>
        The top idea is <b>{opps[0]['name']}</b> (priority 100). The strongest link to stopping is
        <b>{TOPIC[sid].lower()}</b>: {sk} of {sn} comments come from people who stopped or paused.{also}</p></div>""",
                unsafe_allow_html=True)

    head("Where this comes from", "Who is talking")
    if N_AUTO:
        st.markdown(f'<div class="note">{AUTO_NOTE}</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    donut(c1, CORE["platform"].value_counts(), "SIP comments by source", SRC_COLOR)
    sc = CORE["Comment type"].value_counts().reindex(TYPE_COLOR).dropna()
    donut(c2, sc, "Comment type", TYPE_COLOR)

    st.markdown("### Every topic")
    st.markdown('<div class="note">Number of SIP comments per topic. Indigo is first-hand stories.</div>', unsafe_allow_html=True)
    tca = topic_counts(CORE)
    fig = go.Figure()
    fig.add_bar(y=tca["topic"], x=tca["firsthand"], orientation="h", name="First-hand", marker_color=SPOT)
    fig.add_bar(y=tca["topic"], x=tca["n"] - tca["firsthand"], orientation="h", name="Other comments", marker_color=BAR)
    fig.update_layout(barmode="stack", yaxis=dict(autorange="reversed"), xaxis_title="Comments")
    show(style(fig, 600))

    with st.expander("Words used in this app"):
        st.markdown(
            "- **SIP**: systematic investment plan, a fixed amount invested in a mutual fund every month.\n"
            "- **Comment**: one review, post or reply about SIPs or mutual funds. The app counts comments, not people.\n"
            "- **First-hand story**: someone describing their own SIP, not an opinion about SIPs in general.\n"
            "- **Stopped or at risk**: the person says they stopped, paused, skipped or are about to stop.\n"
            "- **Priority score**: how often a problem comes up, how strongly it links to stopping, how much the app can fix it, "
            "and how much evidence there is. The top idea scores 100.")


def page_todo():
    head("What to do", "Eight ideas, ranked by priority",
         "Each idea is a product change Groww could test. Higher priority means the problem comes up often, "
         "is linked to people stopping, and is something the app can fix.")
    opps = D["opportunities"]
    fig = hbar([o["name"] for o in opps], [o["score_norm"] for o in opps],
               color=[SPOT if i < 3 else BAR for i in range(len(opps))], xtitle="Priority (top = 100)")
    fig.update_xaxes(range=[0, 112])
    show(fig)

    for i, o in enumerate(opps):
        cls = "rank p0" if i < 3 else "rank"
        st.markdown(
            f"""<div class="card"><h4><span class="{cls}">#{i + 1} · {o['score_norm']}</span>{o['name']}</h4>
            <p>{_clean(o['idea'])}</p>
            <div class="meta"><b style="color:#000">How to measure:</b> {_clean(o['metric'])}</div>
            <div class="meta">{o['n']} comments · {o['platforms']} sources · covers {o['risk_cover']:.0%} of stop stories</div>
            {''.join(f'<span class="chip">{TOPIC[t]}</span>' for t in o['themes'])}</div>""",
            unsafe_allow_html=True)

    st.markdown("### Estimate the impact on 12-month retention")
    st.markdown('<div class="note">"Share of stops it addresses" comes from the stop and pause stories in the data. '
                "The baseline and save rate are placeholders: replace them with Groww's real numbers before quoting the result.</div>",
                unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    base = c1.slider("Today's 12-month active rate (%)", 10, 95, 50)
    save = c2.slider("Share of those stops each idea saves (%)", 0, 100, 20)
    stops = 100 - base
    rows, keep = [], 1.0
    for o in opps:
        gain = stops * o["risk_cover"] * save / 100
        keep *= 1 - o["risk_cover"] * save / 100
        rows.append({"Idea": o["name"], "Share of stops addressed": o["risk_cover"], "Gain (points)": round(gain, 1)})
    total = stops * (1 - keep)
    c = st.columns(3)
    stat(c[0], f"{base}%", "Active at 12 months today")
    stat(c[1], f"+{total:.1f}", "Points gained, all ideas", "same person never counted twice")
    stat(c[2], f"{base + total:.1f}%", "Active at 12 months after")
    st.write("")
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch",
                 column_config={"Share of stops addressed": st.column_config.ProgressColumn(min_value=0, max_value=1, format="percent")})


def page_questions():
    head("Research questions", "Answers to the eight questions",
         "Pick a question. The label shows how well the data supports the answer.")
    qs = D["questions"]
    pick = st.radio("Question", list(qs), format_func=lambda q: qs[q], label_visibility="collapsed")
    cv = D["coverage"][pick]
    g = cv["grade"]
    st.markdown(f'<span class="grade" style="background:{GRADE_COLOR.get(g, INK)}">{g} evidence</span>', unsafe_allow_html=True)
    st.markdown(f"### {qs[pick]}")
    c = st.columns(3)
    stat(c[0], f"{cv['n']:,}", "Comments")
    stat(c[1], cv["firsthand"], "First-hand")
    stat(c[2], cv["platforms"], "Sources")
    st.write("")

    th = [t for t in cv["themes"] if t in D["themes"]]
    th = sorted(th, key=lambda t: -D["themes"][t]["n"])
    left, right = st.columns([1, 1])
    with left:
        st.markdown("**Topics behind the answer**")
        show(hbar([TOPIC[t] for t in th], [D["themes"][t]["n"] for t in th], color=SPOT,
                  text=[f"{D['themes'][t]['n']} · {D['themes'][t]['firsthand']} first-hand" for t in th]))
        top = D["themes"][th[0]] if th else None
        if top:
            lo, hi = top["ci"]
            st.markdown(f'<div class="note">The biggest topic, {TOPIC[th[0]].lower()}, appears in {top["share"]:.0%} of SIP comments '
                        f"(likely range {lo:.0%}–{hi:.0%}), from {top['n_authors']} people across {top['n_platforms']} sources.</div>",
                        unsafe_allow_html=True)
    with right:
        st.markdown("**In their words**")
        sub = CORE[CORE["topics"].map(lambda ts: bool(set(th) & set(ts)))]
        sub = sub.sort_values(["firsthand", "Auto-collected"], ascending=[False, True])
        for _, r in sub.head(4).iterrows():
            quote(r)

    st.markdown("### All questions at a glance")
    st.dataframe(pd.DataFrame([{"Question": qs[q], "Evidence": D["coverage"][q]["grade"], "Comments": D["coverage"][q]["n"],
                                "First-hand": D["coverage"][q]["firsthand"], "Sources": D["coverage"][q]["platforms"]} for q in qs]),
                 hide_index=True, width="stretch")


def page_stay_stop():
    lens = D["stance"]["lenses"]["behaviour"]
    head("Stay vs stop", "Why some people keep going and others stop",
         f"Compares {lens['na']} first-person comments about a SIP still running with {lens['nb']} about pausing or stopping. "
         "Bars show the share of each group that raised a topic. The stop group is small, so read this as direction, not proof.")
    own = CORE[CORE["stance"].fillna("").str.startswith("self")]
    auto_cont = int((own["Auto-collected"] & own["stance"].eq("self: continuing")).sum())
    if auto_cont:
        st.warning(f"{auto_cont} of the {lens['na']} 'still investing' comments were labelled automatically, but every 'stopped' "
                   "comment is hand-checked. Until the automatic ones are checked, the two groups are not like for like.")
    rows = sorted(lens["rows"], key=lambda r: r["diff"], reverse=True)
    fig = go.Figure()
    fig.add_bar(y=[TOPIC[r["theme"]] for r in rows], x=[r["b"] for r in rows], orientation="h", name="Paused or stopped", marker_color=STOP)
    fig.add_bar(y=[TOPIC[r["theme"]] for r in rows], x=[r["a"] for r in rows], orientation="h", name="Still investing", marker_color=SPOT)
    fig.update_layout(barmode="group", xaxis=dict(tickformat=".0%"), yaxis=dict(autorange="reversed"))
    show(style(fig, 40 * len(rows) + 120))

    st.markdown("### What people need")
    needs = D["needs"]
    show(hbar([n["need"] for n in needs], [n["n"] for n in needs], color=[INK if n["consistent"] else BAR for n in needs],
              text=[f"{n['n']} · {n['platforms']} sources" for n in needs]))
    st.markdown('<div class="note">Grey means fewer than 2 sources, so not yet a consistent need.</div>', unsafe_allow_html=True)

    st.markdown("### In their own words")
    own = CORE[CORE["stance"].str.startswith("self", na=False)]
    cols = st.columns(3)
    for col, label in zip(cols, ["Own story: paused or stopped", "Own story: stopped, then restarted", "Own story: still investing"]):
        sub = own[own["Comment type"] == label]
        with col:
            st.markdown(f"**{label.split(': ')[1].capitalize()}** ({len(sub)})")
            for _, r in sub.head(3).iterrows():
                quote(r)


def page_journey():
    head("First-year journey", "Where in the first year people stop",
         "Comments placed on the 12 stages of a first SIP. Orange marks stages where people describe stopping.")
    stages = D["journey"]["stages"]
    fig = go.Figure()
    fig.add_bar(x=[s["label"] for s in stages], y=[s["n"] for s in stages], name="Comments", marker_color=BAR)
    fig.add_bar(x=[s["label"] for s in stages], y=[s["at_risk"] for s in stages], name="Stopped or at risk", marker_color=STOP)
    fig.add_bar(x=[s["label"] for s in stages], y=[s["continuing"] for s in stages], name="Still investing", marker_color=SPOT)
    fig.update_layout(barmode="group", xaxis_tickangle=-30)
    show(style(fig, 420))
    for i, s in enumerate(stages, 1):
        ref = s.get("reference") or {}
        with st.expander(f"{i:02d} · {s['label']} — {s['n']} comments"):
            if ref:
                st.markdown(f"**What happens:** {_clean(ref.get('behaviour', ''))}  \n**Friction:** {_clean(ref.get('friction', ''))}")
            for ex in s.get("examples", [])[:3]:
                st.markdown(f'<div class="quote"><div class="q">“{_clean(ex["text"])}”</div><div class="m">{ex["platform"]} · {ex["record_id"]}</div></div>',
                            unsafe_allow_html=True)


def page_apps():
    head("Apps compared", "What Play Store reviewers say, app by app",
         "SIP-related Play Store reviews of five investing apps. Compare which problems each app's users raise most.")
    play = CORE[CORE["App"].ne("")]
    if play.empty:
        st.info("No Play Store reviews with an app name in this data.")
        return
    counts = play["App"].value_counts()
    cols = st.columns(len(counts))
    for col, (a, n) in zip(cols, counts.items()):
        stat(col, n, a, "SIP reviews")
    st.write("")
    tc = Counter(t for ts in play["topics"] for t in ts)
    top = [t for t, _ in tc.most_common(10)]
    apps = list(counts.index)
    z = [[sum(t in ts for ts in play.loc[play["App"] == a, "topics"]) / counts[a] for a in apps] for t in top]
    fig = go.Figure(go.Heatmap(z=z, x=apps, y=[TOPIC[t] for t in top], colorscale=[[0, "#ffffff"], [1, SPOT]],
                               text=[[f"{v:.0%}" for v in row] for row in z], texttemplate="%{text}", showscale=False,
                               hovertemplate="%{x}: %{z:.0%} of SIP reviews mention %{y}<extra></extra>"))
    fig.update_layout(yaxis=dict(autorange="reversed"), xaxis=dict(side="top"))
    st.markdown("**Share of each app's SIP reviews that mention a topic**")
    show(style(fig, 40 * len(top) + 90))
    stars = play.groupby("App")["sentiment"].value_counts(normalize=True).unstack(fill_value=0)
    if "negative" in stars:
        st.markdown("**Tone of SIP reviews**")
        fig = go.Figure()
        for s_, col in [("negative", STOP), ("neutral", BAR), ("positive", SPOT)]:
            if s_ in stars:
                fig.add_bar(y=stars.index, x=stars[s_], orientation="h", name=s_.capitalize(), marker_color=col)
        fig.update_layout(barmode="stack", xaxis=dict(tickformat=".0%"))
        show(style(fig, 60 * len(stars) + 90))
    pick = st.selectbox("Read reviews from", apps)
    for _, r in play[play["App"] == pick].head(6).iterrows():
        quote(r)


def page_research():
    head("Other research", "What other research says",
         "Two sources that sit beside the comment data: 20 first-hand SIP stories read in depth, and published investor surveys. "
         "They never change the numbers or the ranking elsewhere in this app.")
    if PEOPLE is not None:
        st.markdown("### 20 first-hand SIP stories")
        st.markdown('<div class="note">Public forum, blog and newsletter posts, each from a different person describing their own SIP. '
                    "Desk research, not interviews; most writers are more experienced than a typical first-time investor.</div>",
                    unsafe_allow_html=True)
        outc = PEOPLE["outcome"].map({"kept_going": "Kept going", "paused_or_stopped": "Paused or stopped",
                                      "undecided": "Undecided", "never_or_avoids": "Never started or avoids"}).value_counts()
        c = st.columns(4)
        stat(c[0], len(PEOPLE), "People")
        stat(c[1], int((PEOPLE["first_time"] == "yes").sum()), "First-time investors")
        stat(c[2], int(outc.get("Kept going", 0)), "Kept going")
        stat(c[3], int(outc.get("Paused or stopped", 0)), "Paused or stopped")
        st.write("")
        for i, (t, body) in enumerate(UR_THEMES, 1):
            card(f"Theme {i}. {t}", body)
        if CODES is not None:
            top = CODES.sort_values("n_participants", ascending=False).head(10)
            st.markdown("**Most common codes** (number of people)")
            show(hbar(top["code"].str.capitalize(), top["n_participants"], color=SPOT))
        with st.expander("All 20 people"):
            st.dataframe(PEOPLE[["pid", "source", "date", "profile", "first_time", "outcome", "in_vivo_code", "summary_paraphrased", "url"]]
                         .rename(columns={"pid": "ID", "source": "Source", "date": "Date", "profile": "Who", "first_time": "First-time",
                                          "outcome": "Outcome", "in_vivo_code": "In their words", "summary_paraphrased": "Summary", "url": "Link"}),
                         hide_index=True, width="stretch", column_config={"Link": st.column_config.LinkColumn()})

    if SURVEY_FIGS is not None:
        st.markdown("### Published investor surveys")
        st.markdown('<div class="note">From the SIP Investor Research Report (4 Nov 2026). Different surveys, different groups of '
                    "investors: compare within a chart, not across charts.</div>", unsafe_allow_html=True)
        secs = list(dict.fromkeys(SURVEY_FIGS["section"]))
        cols = st.columns(2)
        for i, sec in enumerate(secs):
            sub = SURVEY_FIGS[SURVEY_FIGS["section"] == sec]
            with cols[i % 2]:
                st.markdown(f"**{sec}**")
                show(hbar(sub["measure"], sub["share"], color=SPOT if i % 2 == 0 else INK,
                          text=[f"{v:.0%}" for v in sub["share"]]).update_xaxes(range=[0, 0.75], tickformat=".0%"))
                st.markdown(f'<div class="note">{sub["base"].iloc[0]} · {sub["source"].iloc[0]} · {sub["note"].iloc[0]}</div>',
                            unsafe_allow_html=True)
                st.write("")


def page_competitor():
    c = D["competitor"]
    head("Competitor", "What we can learn from Zerodha Coin users",
         f"{c['n_included']} comparison comments from {c['n_sources']} sources. Shown for context: they never change the ranking.")
    dirs = c["directions"]
    cols = st.columns(len(dirs))
    for col, (k, v) in zip(cols, dirs.items()):
        stat(col, v, k)
    st.write("")
    feats = c["features"]
    order = ["Pro Coin", "Against Coin", "Pro Groww", "Against Groww", "Mixed"]
    colors = {"Pro Coin": INK, "Against Coin": BAR, "Pro Groww": SPOT, "Against Groww": STOP, "Mixed": LILAC}
    fig = go.Figure()
    for d_ in order:
        fig.add_bar(y=[f["label"] for f in feats], x=[f["directions"].get(d_, 0) for f in feats], orientation="h", name=d_, marker_color=colors[d_])
    fig.update_layout(barmode="stack", yaxis=dict(autorange="reversed"), xaxis_title="Comments")
    show(style(fig, 40 * len(feats) + 120))

    st.markdown("### Two ideas to test before ranking")
    st.markdown('<div class="note">These come from competitor feedback, so they stay out of the ranked list until Groww\'s own users ask for them.</div>',
                unsafe_allow_html=True)
    for cd in c["candidates"]:
        card(cd["name"], _clean(cd["idea"]),
             f"<b style='color:#000'>Why:</b> {_clean(cd['hypothesis'])}<br><b style='color:#000'>Test:</b> {_clean(cd['test'])}<br>"
             f"{cd['competitor_rows']} competitor comments · {cd['groww_support']} Groww-side comments agree")


def page_search():
    head("Evidence", "Search comments", "Browse, filter and read every comment with the topics and comment type the engine gave it.")
    f1, f2, f3 = st.columns([2, 1, 1])
    q = f1.text_input("Search text", placeholder="e.g. pause, XIRR, job loss")
    group = f2.multiselect("Group", list(TIER.values()), default=["About SIPs"])
    plat = f3.multiselect("Source", sorted(DF["platform"].unique()))
    f4, f5, f6, f7 = st.columns([2, 1, 1, 1])
    topics = f4.multiselect("Topic", list(TOPIC.values()))
    ctype = f5.multiselect("Comment type", list(STANCE.values()))
    apps = f6.multiselect("App (Play Store)", sorted(a for a in DF["App"].unique() if a))
    only_fh = f7.toggle("First-hand only")
    hide_auto = f7.toggle("Hand-coded only")

    v = DF
    if group:
        v = v[v["Group"].isin(group)]
    if plat:
        v = v[v["platform"].isin(plat)]
    if topics:
        ids = {k for k, lab in TOPIC.items() if lab in topics}
        v = v[v["topics"].map(lambda ts: bool(ids & set(ts)))]
    if ctype:
        v = v[v["Comment type"].isin(ctype)]
    if apps:
        v = v[v["App"].isin(apps)]
    if only_fh:
        v = v[v["firsthand"]]
    if hide_auto:
        v = v[~v["Auto-collected"]]
    if q:
        v = v[v["text"].str.contains(re.escape(q), case=False, na=False)]

    st.markdown(f"**{len(v):,} of {len(DF):,} comments**")
    tbl = v[["record_id", "platform", "App", "Date", "Comment type", "firsthand", "Topic list", "text", "Link"]].rename(
        columns={"record_id": "ID", "platform": "Source", "firsthand": "First-hand", "Topic list": "Topics", "text": "Comment"})
    st.dataframe(tbl, width="stretch", hide_index=True, height=440,
                 column_config={"Comment": st.column_config.TextColumn(width="large"), "Link": st.column_config.LinkColumn(display_text="open")})
    st.download_button("Download these rows (CSV)", tbl.to_csv(index=False).encode("utf-8"), "sip_comments_filtered.csv", "text/csv")
    if len(v):
        st.markdown("### Read them")
        for _, r in v.sort_values("firsthand", ascending=False).head(12).iterrows():
            quote(r)


# ---------------------------------------------------------------- ask
STOPWORDS = set("a an the and or of to in on for is are was were be been do does did what why how who which when where "
                "people investors investor users user say says about with that this they their them it its from as at by "
                "my i me you your so if not no can could would should sip sips".split())
SYN = {
    "stop": ["stopped", "stopping", "cancel", "quit", "discontinue", "halt"],
    "pause": ["skip", "paused", "pausing", "break", "hold"],
    "return": ["returns", "xirr", "profit", "gain", "loss", "negative", "fd"],
    "fall": ["crash", "dip", "correction", "bear", "down", "red"],
    "debit": ["mandate", "autopay", "auto-debit", "payment", "bank", "failed"],
    "fee": ["fees", "charges", "exit", "load", "expense", "ratio"],
    "advice": ["youtube", "reddit", "advisor", "friend", "finfluencer", "suggest"],
    "job": ["salary", "income", "layoff", "medical", "emergency", "wedding"],
}
SYN_TOPICS = {"stop": ["T05", "T04", "T01", "T02", "T18"], "pause": ["T05", "T04"], "return": ["T01", "T02", "T08"],
              "fall": ["T03"], "debit": ["T06"], "fee": ["T07"], "advice": ["T10", "T15"], "job": ["T04"]}


def tokens(s):
    return [w for w in re.findall(r"[a-z][a-z\-]+", s.lower()) if w not in STOPWORDS and len(w) > 2]


@st.cache_data
def doc_index(texts):
    toks = [set(tokens(t)) for t in texts]
    dfreq = Counter(w for ts in toks for w in ts)
    return toks, {w: math.log((len(toks) + 1) / (c + 0.5)) for w, c in dfreq.items()}


def search(question, frame):
    toks, idf = doc_index(tuple(frame["text"]))
    q = tokens(question)
    terms = {w: 1.0 for w in q}
    roots = {r for w in q for r, alts in SYN.items() if w.startswith(r) or w in alts}
    for r in roots:
        for a in [r] + SYN[r]:
            terms.setdefault(a, 0.5)
    qtopics = {t for t, lab in TOPIC.items() if set(tokens(lab)) & set(q)} | {t for r in roots for t in SYN_TOPICS.get(r, [])}
    want_stop = bool(roots & {"stop", "pause"})
    scores = []
    for dt, ts, stance, fh in zip(toks, frame["topics"], frame["stance"].fillna(""), frame["firsthand"]):
        s = sum(wt * idf.get(w, 0) for w, wt in terms.items() if w in dt or (len(w) > 4 and any(d.startswith(w) for d in dt)))
        s += 2.0 * len(qtopics & set(ts)) + (0.5 if fh else 0)
        if want_stop and stance.startswith(("self: paused", "self: stopped")):
            s += 4.0
        scores.append(s)
    out = frame.assign(score=scores)
    return out[out["score"] > 0.5].sort_values("score", ascending=False)


def page_ask():
    head("Ask a question", "Ask the evidence",
         f"Ask in plain words. The engine finds the most relevant of the {META['n_core']:,} SIP comments and sums up what they say. "
         "It matches words and related words, and does not invent answers: every line comes from counted comments.")
    examples = ["Why do people stop their SIP?", "What do people say about pausing or skipping?", "How do people feel about XIRR and returns?",
                "What happens when markets fall?", "Where do investors go for advice?", "What goes wrong with auto-debit payments?"]
    cols = st.columns(3)
    for i, e in enumerate(examples):
        if cols[i % 3].button(e, key=f"ex{i}", width="stretch"):
            st.session_state.ask_q = e
    question = st.text_input("Your question", key="ask_q")
    include_all = st.toggle("Also search removed comments (trading and app bugs)")
    if not question:
        return
    hits = search(question, DF if include_all else CORE)
    if hits.empty:
        st.warning("No matching comments. Try words like 'stop', 'returns', 'pause' or 'fees'.")
        return
    top = hits.head(40)
    tc = Counter(t for ts in top["topics"] for t in ts).most_common(4)
    types = top["Comment type"].value_counts()
    own = {k: v for k, v in types.items() if k.startswith("Own")}
    linked = [o for o in D["opportunities"] if {t for t, _ in tc[:3]} & set(o["themes"])][:2]
    lines = [f"<b>{len(hits):,}</b> comments match. In the closest {len(top)}, <b>{int(top['firsthand'].sum())}</b> are first-hand."]
    if tc:
        lines.append("Most common topics: " + ", ".join(f"<b>{TOPIC[t]}</b> ({n})" for t, n in tc) + ".")
    if own:
        lines.append(f"{sum(own.values())} describe their own SIP: " + ", ".join(f"{k.split(': ')[1]} ({v})" for k, v in own.items()) + ".")
    if linked:
        lines.append("Related ideas: " + "; ".join(f"<b>{o['name']}</b>" for o in linked) + ".")
    st.markdown('<div class="spotcard"><div class="eyebrow">Summary</div><p>' + "<br>".join(lines) + "</p></div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if tc:
        with c1:
            st.markdown("**Topics in matching comments**")
            show(hbar([TOPIC[t] for t, _ in tc], [n for _, n in tc], color=SPOT, h=240))
    donut(c2, top["platform"].value_counts(), "Sources", SRC_COLOR, h=240)
    st.markdown("### Most relevant comments")
    for _, r in hits.head(8).iterrows():
        quote(r)


def page_method():
    head("Appendix · for analysts", "How this was built and checked", "The method, the quality checks and what is still missing.")
    steps = [("Gather", f"{len(META['platforms'])} public sources, {META['n_total']:,} comments in one format."),
             ("Filter & weigh", "Keep SIP and mutual fund comments; drop trading. First-hand counts more; repeated text less."),
             ("Find topics", "Sort each comment into 18 topics, each tied to a research question."),
             ("Label", "Own SIP (still going, stopped, mixed) or opinion? Which journey stage?"),
             ("Count & rank", "A topic becomes a finding only if 5+ people across 2+ sources mention it. Findings roll up into 8 ideas."),
             ("Check", "Compare with analyst tags and blind human labels; test if the ranking holds when data is removed.")]
    cols = st.columns(3)
    for i, (t, d_) in enumerate(steps):
        cols[i % 3].markdown(f'<div class="step"><div class="n">0{i + 1}</div><div class="t">{t}</div><div class="d">{d_}</div></div>',
                             unsafe_allow_html=True)
        if i == 2:
            st.write("")
            cols = st.columns(3)
    st.write("")

    st.markdown("### Sources")
    allp, corep = META["platforms"], META["core_platforms"]
    fig = go.Figure()
    fig.add_bar(x=list(allp), y=list(allp.values()), name="Collected", marker_color=BAR)
    fig.add_bar(x=list(allp), y=[corep.get(p, 0) for p in allp], name="About SIPs", marker_color=SPOT)
    fig.update_layout(barmode="overlay")
    show(style(fig, 320))
    if N_AUTO:
        st.markdown(f'<div class="note">{AUTO_NOTE}</div>', unsafe_allow_html=True)

    st.markdown("### Quality checks")
    gold = D["validation"]["golden"]
    c = st.columns(4)
    stat(c[0], f"{gold['type_agree']}/{gold['n']}", "Exact comment type", "matches blind human labels")
    stat(c[1], f"{gold['coarse_agree']}/{gold['n']}", "Own story vs opinion", "matches blind human labels")
    stat(c[2], f"{gold['topic_precision']:.0%}", "Topic tags right", "when the engine tags one")
    stat(c[3], f"{gold['topic_recall']:.0%}", "Topics found", "of those a human found")
    st.write("")
    rob = D["validation"]["robustness"]
    st.markdown("**Does the ranking hold?** How similar the topic ranking stays when part of the data is removed (1.0 = unchanged).")
    show(hbar(list(rob), list(rob.values()), color=[SPOT if v >= .8 else STOP for v in rob.values()],
              text=[f"{v:.2f}" for v in rob.values()]).update_xaxes(range=[0, 1.1]))
    agr = pd.DataFrame(D["validation"]["agreement"])
    agr["Topic"] = agr["pair"].str.slice(0, 3).map(TOPIC)
    agr = agr[["Topic", "precision", "recall", "kappa"]].rename(columns={"precision": "Right when tagged", "recall": "Found", "kappa": "Agreement"})
    st.markdown("**Engine vs analyst tags**")
    st.dataframe(agr, hide_index=True, width="stretch",
                 column_config={k: st.column_config.ProgressColumn(k, min_value=0, max_value=1, format="%.2f") for k in agr.columns[1:]})
    st.markdown('<div class="note">Main limit: topics are found by keywords, so reworded comments can be missed.</div>', unsafe_allow_html=True)

    if AI_EVAL:
        S, A2, info = AI_EVAL["golden"]["side_by_side"], AI_EVAL["stance_audit"], AI_EVAL["info"]
        st.markdown("### Claude labelling")
        st.markdown(f'<div class="lede">Claude labelled all {info["n_ai_labelled"]:,} comments in Claude Code with a fixed prompt '
                    f'({AI_EVAL["prompt_version"]}). Code checked every label, and each quote had to be words copied from the comment. '
                    "Claude never saw a human label. Switch <b>Labels</b> at the top of the page to see every number with Claude's labels.</div>",
                    unsafe_allow_html=True)
        cmp = pd.DataFrame([
            ("Same comment type (blind, 20)", f"{S['type_agree']['rules']}/20", f"{S['type_agree']['ai']}/20"),
            ("Agreement beyond chance (kappa)", S["type_kappa"]["rules"], S["type_kappa"]["ai"]),
            ("Same broad type (blind, 20)", f"{S['coarse_agree']['rules']}/20", f"{S['coarse_agree']['ai']}/20"),
            ("Topic tags right", f"{S['topic_precision']['rules']:.0%}", f"{S['topic_precision']['ai']:.0%}"),
            ("Topics found", f"{S['topic_recall']['rules']:.0%}", f"{S['topic_recall']['ai']:.0%}"),
            ("Hand-checked stances (not blind for rules)", f"{A2['rules']['agree']}/{A2['rules']['n']}", f"{A2['ai']['agree']}/{A2['ai']['n']}"),
        ], columns=["Check", "Keyword rules", "Claude"])
        st.dataframe(cmp.astype(str), hide_index=True, width="stretch")
        two = AI_EVAL["two_humans"]["golden_vs_audit"]
        st.markdown(f'<div class="note">Two human label sets agree on only {two["exact"]} of {AI_EVAL["two_humans"]["n"]} shared comments, '
                    f'so no labeller can score far above that. {info["own_story_candidates"]["n"]:,} of Claude\'s own-story calls on '
                    f'scraped comments stay "Not clear" until a person checks them; {info["n_corrections"]} labels were corrected by hand. '
                    f'<a href="{LOG_URL}" target="_blank">Read the evidence log</a>.</div>', unsafe_allow_html=True)

    st.markdown("### What's missing")
    st.markdown('<div class="lede">Today\'s evidence shows which problems exist and why. It cannot say how many investors stop, '
                "when, or which groups are most at risk. These sources would, in order of value:</div>", unsafe_allow_html=True)
    for t, d_ in [("Groww's own data", "12-month active rate, cancels by month, cancels after a failed debit or a skip attempt."),
                  ("A survey of first-year investors", "The 29-question SIP Investor Experience Survey is ready to run; the engine already reads it."),
                  ("About 20 interviews", "First-time, first-year investors, including people who stopped."),
                  ("More hand-checked labels", "Grow the human check from 20 to 60–100 comments, with a second reviewer.")]:
        card(t, d_)


# ---------------------------------------------------------------- navigation (top bar, like the original report)
nav = st.navigation(
    [
        st.Page(page_summary, title="Summary", url_path="summary", default=True),
        st.Page(page_todo, title="What to do", url_path="what-to-do"),
        st.Page(page_questions, title="Research questions", url_path="questions"),
        st.Page(page_stay_stop, title="Stay vs stop", url_path="stay-vs-stop"),
        st.Page(page_journey, title="First-year journey", url_path="journey"),
        st.Page(page_competitor, title="Competitor", url_path="competitor"),
        st.Page(page_apps, title="Apps compared", url_path="apps"),
        st.Page(page_research, title="Other research", url_path="research"),
        st.Page(page_search, title="Search comments", url_path="search"),
        st.Page(page_ask, title="Ask a question", url_path="ask"),
        st.Page(page_method, title="Appendix", url_path="appendix"),
    ],
    position="top",
)
nav.run()
st.markdown(f'<div class="note" style="margin-top:60px;border-top:1px solid #e2e2e2;padding-top:14px">SIP Retention Discovery Engine · '
            f'{META["n_total"]:,} comments · {META["n_core"]:,} about SIPs · labels: {LABELS} · '
            f'<a href="{LOG_URL}" target="_blank">evidence log</a></div>', unsafe_allow_html=True)
