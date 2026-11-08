// Explain My Returns: frontend. Every number comes from the server.
const $ = (id) => document.getElementById(id);
const SCENARIOS = {
  red:   { mode: "sample", fund: "nifty50",  amount: 1000, start: "2025-11", as_of: "2026-04" },
  flat:  { mode: "sample", fund: "nifty50",  amount: 1000, start: "2025-12", as_of: null },
  green: { mode: "sample", fund: "flexicap", amount: 1000, start: "2016-01", as_of: null },
};
const CHIPS = {
  early_red: ["Why is my SIP red?", "Is my SIP working?", "Do I buy more units when prices fall?", "Should I stop my SIP?"],
  long_red:  ["Why is my SIP still red?", "What is XIRR?", "How do I skip one instalment?", "Should I sell?"],
  flat:      ["Why are my returns so small?", "Is compounding happening?", "What is XIRR?", "Is this a good time to invest more?"],
  green:     ["What does my XIRR mean?", "How much have I invested?", "Why did I get less when I redeemed?", "Which fund should I buy?"],
};
const state = { sip: SCENARIOS.red, d: null, meta: null, hide: false, period: "all", stack: ["vHome"], showAll: false };

// ---------- helpers ----------
const inr = (n, dp = 0) => "₹" + Math.abs(n).toLocaleString("en-IN", { minimumFractionDigits: dp, maximumFractionDigits: dp });
const sgn = (n) => (n < 0 ? "-" : "+");
const money = (txt) => (state.hide ? "₹••••" : txt);
const dShort = (iso) => { const d = new Date(iso); return `${d.getDate()} ${d.toLocaleString("en-IN", { month: "short" })} '${String(d.getFullYear()).slice(2)}`; };
const monthName = (m) => { const [y, mo] = m.split("-"); return new Date(+y, +mo - 1, 1).toLocaleString("en-IN", { month: "short", year: "numeric" }); };
const ordinal = (n) => n + (["th", "st", "nd", "rd"][(n % 100 - 20) % 10] || ["th", "st", "nd", "rd"][n % 100] || "th");
function toast(msg) { const t = $("toast"); t.textContent = msg; t.classList.add("on"); clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("on"), 2600); }

async function api(path, body) {
  const r = await fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  if (!r.ok) { let m = "Something went wrong."; try { m = (await r.json()).detail || m; } catch {} throw new Error(m); }
  return r.json();
}

// ---------- navigation ----------
function go(id) {
  const cur = state.stack[state.stack.length - 1];
  if (cur === id) return;
  $(cur).classList.remove("on"); $(cur).classList.add("left");
  $(id).classList.add("on"); state.stack.push(id);
  if (id === "vAnalysis") drawChart();
}
function back() {
  if (state.stack.length < 2) return;
  const cur = state.stack.pop(), prev = state.stack[state.stack.length - 1];
  $(cur).classList.remove("on"); $(prev).classList.remove("left"); $(prev).classList.add("on");
}
document.querySelectorAll("[data-go]").forEach((b) => (b.onclick = () => go(b.dataset.go)));
document.querySelectorAll("[data-back]").forEach((b) => (b.onclick = back));
document.querySelectorAll("[data-toast]").forEach((b) => (b.onclick = () => toast(b.dataset.toast)));
document.querySelectorAll("[data-tab]").forEach((b) => (b.onclick = () => {
  document.querySelectorAll("[data-tab]").forEach((x) => x.classList.toggle("on", x === b));
  $("tabDash").classList.toggle("hidden", b.dataset.tab !== "dash");
  $("tabSips").classList.toggle("hidden", b.dataset.tab !== "sips");
}));

// ---------- load + render ----------
async function load(sip) {
  state.sip = sip;
  state.d = await api("/api/sip", sip);
  state.showAll = false;
  render();
  renderCard(state.d.card);
  resetChat(state.d.card.stage);
}

function render() {
  const d = state.d, red = d.gain < 0;
  const fund = d.fund === "Your SIP" ? "Your SIP (numbers you entered)" : `${d.fund} (sample)`;
  const gainTxt = `${sgn(d.gain)}${inr(d.gain)} (${Math.abs(d.gain_pct)}%)`;

  // dashboard
  $("hValue").textContent = money(inr(d.value));
  const one = d.one_day || 0;
  $("h1d").textContent = d.daily && d.daily.length ? money(`${sgn(one)}${inr(one, 2)} (${Math.abs(d.one_day_pct || 0)}%)`) : "—";
  $("h1d").className = one < 0 ? "neg" : one > 0 ? "pos" : "";
  $("hGain").textContent = money(gainTxt); $("hGain").className = red ? "neg" : "pos";
  $("hInv").textContent = money(inr(d.invested));
  $("hXirr").textContent = d.xirr_pct == null ? "—" : d.instalments < 12 ? "Too early" : `${d.xirr_pct}%`;
  $("lFund").textContent = fund;
  $("lValue").textContent = money(inr(d.value)); $("lValue").className = red ? "neg" : "pos";
  $("lInv").textContent = money(`(${inr(d.invested)})`);

  // feature entry points change with the investor's situation
  document.querySelectorAll(".explain-strip,#vDetails .explain-card").forEach((e) => e.classList.toggle("alert", red));
  document.querySelector(".explain-strip .es-title").textContent = red ? "Why is my SIP red?" : "Explain my returns";
  document.querySelector(".explain-strip .es-sub").textContent = red ? "See what this means, in plain words" : "What do these numbers mean?";
  $("dExplainTitle").textContent = red ? "Why is my SIP red?" : "Explain my returns";
  $("dExplainSub").textContent = red ? `${inr(d.gain)} below what you put in. See what that means.` : `Up ${inr(d.gain)} on ${inr(d.invested)}. Ask anything about it.`;

  // SIPs tab
  $("sAmount").textContent = inr(d.amount);
  $("sFund").textContent = fund; $("sAmt2").textContent = inr(d.amount);
  if (d.next_due) { const n = new Date(d.next_due); $("sDay").textContent = n.getDate(); $("sMon").textContent = n.toLocaleString("en-IN", { month: "short" }); }
  else { $("sDay").textContent = "—"; $("sMon").textContent = ""; }

  // SIP details
  $("dFund").textContent = fund;
  $("dNextN").textContent = `${ordinal(d.instalments + 1)} instalment`;
  $("dNextD").textContent = d.next_due ? dShort(d.next_due) + " (estimated)" : "Next month";
  renderTimeline();
  const rows = [["Monthly amount", inr(d.amount)], ["Instalments paid", d.instalments], ["Started", d.start_month ? monthName(d.start_month) : "—"],
    ["Units held", d.units ?? "—"], ["Average cost per unit", d.avg_cost ? inr(d.avg_cost, 2) : "—"], ["Latest NAV", d.latest_nav ? inr(d.latest_nav, 2) : "—"],
    ["Value as of", dShort(d.as_of)]];
  $("dDetails").innerHTML = rows.map(([k, v]) => `<div class="row"><span>${k}</span><b>${v}</b></div>`).join("");

  // analysis header
  $("aValue").textContent = money(inr(d.value));
  $("aInv").textContent = money(inr(d.invested));
  if (state.stack.includes("vAnalysis")) drawChart();
}

function renderTimeline() {
  const d = state.d, ol = $("dPrev");
  const dates = d.instalment_dates || [];
  const items = dates.map((dt, i) => ({ n: i + 1, dt, h: (d.history || [])[i] })).reverse();
  const shown = state.showAll ? items : items.slice(0, 2);
  ol.innerHTML = "";
  shown.forEach((it) => {
    const li = document.createElement("li");
    li.innerHTML = `<span>${ordinal(it.n)} instalment</span><small>${dShort(it.dt)}</small>` +
      (it.h ? `<em>Bought ${it.h.units} units at ${inr(it.h.nav, 2)}</em>` : "");
    ol.appendChild(li);
  });
  if (!items.length) ol.innerHTML = `<li><span>${d.instalments} instalments paid</span><small>Dates not available for numbers you typed</small></li>`;
  $("btnMore").classList.toggle("hidden", items.length <= 2);
  $("btnMore").textContent = state.showAll ? "View less" : "View more";
}
$("btnMore").onclick = () => { state.showAll = !state.showAll; renderTimeline(); };
$("btnDetails").onclick = () => $("dDetails").classList.toggle("hidden");
$("btnEye").onclick = () => { state.hide = !state.hide; render(); };

// ---------- chart (purple value line, dotted stepped invested line) ----------
function drawChart() {
  const el = $("chart"), d = state.d;
  let s = d.daily || [];
  if (s.length < 2) { el.innerHTML = `<p class="foot" style="text-align:center;padding-top:90px">The chart needs daily prices. Pick one of the sample SIPs.</p>`; $("aGain").textContent = ""; return; }
  if (state.period !== "all") {
    const cut = new Date(s[s.length - 1][0]); cut.setDate(cut.getDate() - +state.period);
    const iso = cut.toISOString().slice(0, 10);
    const f = s.filter((p) => p[0] >= iso); s = f.length > 1 ? f : s.slice(-2);
  }
  if (s.length > 360) { // thin out, but keep every step in invested
    const step = Math.ceil(s.length / 360);
    s = s.filter((p, i) => i % step === 0 || i === s.length - 1 || (i > 0 && s[i - 1][1] !== p[1]));
  }
  const first = s[0], last = s[s.length - 1];
  const gNow = last[2] - last[1], gThen = state.period === "all" ? 0 : first[2] - first[1];
  const ch = gNow - gThen, base = state.period === "all" ? last[1] : first[2];
  const label = { 30: "1M", 91: "3M", 182: "6M", all: "All Time" }[state.period];
  $("aGain").innerHTML = `<span class="${ch < 0 ? "neg" : "pos"}">${money(`${sgn(ch)}${inr(ch, 2)} (${Math.abs(ch / base * 100).toFixed(2)}%)`)}</span> <span class="muted">${label}</span>`;

  const W = 400, H = 240, P = 8;
  const vals = s.flatMap((p) => [p[1], p[2]]);
  const max = Math.max(...vals), min = Math.min(...vals);
  const pad = (max - min) * 0.08 || 1;
  const X = (i) => P + (i * (W - 2 * P)) / (s.length - 1);
  const Y = (v) => P + (H - 2 * P) * (1 - (v - (min - pad)) / (max - min + 2 * pad));
  let inv = `M${X(0)},${Y(s[0][1])}`;
  for (let i = 1; i < s.length; i++) inv += `H${X(i).toFixed(1)}V${Y(s[i][1]).toFixed(1)}`;
  const val = s.map((p, i) => `${i ? "L" : "M"}${X(i).toFixed(1)},${Y(p[2]).toFixed(1)}`).join("");
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Value and invested over ${label}">
    <path d="${inv}" fill="none" stroke="#6B6E75" stroke-width="2" stroke-dasharray="2 4" vector-effect="non-scaling-stroke"/>
    <path d="${val}" fill="none" stroke="#8587E6" stroke-width="2.2" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>
  </svg>`;
}
document.querySelectorAll("#pills button").forEach((b) => (b.onclick = () => {
  document.querySelectorAll("#pills button").forEach((x) => x.classList.toggle("on", x === b));
  state.period = b.dataset.p; drawChart();
}));

// ---------- explain sheet ----------
function renderCard(c) {
  const el = $("plainCard");
  el.className = "plain-card" + (c.stage.endsWith("red") ? " redcard" : "");
  el.innerHTML = `<h3></h3><ul></ul><div class="tag">Fixed explanation · calculated from your account · no AI</div>`;
  el.querySelector("h3").textContent = c.headline;
  const ul = el.querySelector("ul");
  c.points.forEach((p) => { const li = document.createElement("li"); li.textContent = p; ul.appendChild(li); });
}
function resetChat(stage) {
  document.querySelectorAll("#chat .msg, #chat .typing").forEach((n) => n.remove());
  const chips = $("chips"); chips.innerHTML = "";
  (CHIPS[stage] || CHIPS.green).forEach((q) => { const b = document.createElement("button"); b.type = "button"; b.textContent = q; b.onclick = () => ask(q); chips.appendChild(b); });
}
const BADGE = {
  ai: ["ok", "✓ AI answer · checked: no advice, numbers match"],
  checked: ["warn", "Checked answer · AI reply not used"],
  declined: ["ok", "✓ Not advice · we don't decide for you"],
  redirected: ["warn", "Outside what I can help with"],
  not_sure: ["warn", "Not sure · see official sources"],
};
function addMsg(who, text, out) {
  const chat = $("chat");
  const m = document.createElement("div"); m.className = `msg ${who}`; m.textContent = text;
  if (out) {
    if (out.links && out.links.length) {
      const l = document.createElement("div"); l.className = "links";
      out.links.forEach((x) => { const a = document.createElement("a"); a.href = x.url; a.target = "_blank"; a.rel = "noopener"; a.textContent = "↗ " + x.name; l.appendChild(a); });
      m.appendChild(l);
    }
    const [cls, label] = BADGE[out.source] || ["warn", out.source];
    const b = document.createElement("div"); b.className = `badge ${cls}`; b.textContent = label; b.title = (out.checks || []).join(" · ");
    m.appendChild(document.createElement("br")); m.appendChild(b);
  }
  chat.appendChild(m); chat.scrollTop = chat.scrollHeight;
}
async function ask(q) {
  q = q.trim(); if (!q) return;
  addMsg("me", q); $("askInput").value = "";
  const btn = document.querySelector(".ask button"); btn.disabled = true;
  const t = document.createElement("div"); t.className = "typing"; t.textContent = "Checking your numbers…"; $("chat").appendChild(t);
  try { const out = await api("/api/ask", { question: q, sip: state.sip }); t.remove(); addMsg("bot", out.answer, out); }
  catch (e) { t.remove(); addMsg("bot", e.message, { source: "not_sure", links: [] }); }
  btn.disabled = false;
}

// ---------- sheets ----------
function openSheet(id) { closeSheets(); $("scrim").classList.add("on"); $(id).classList.add("on"); }
function closeSheets() { $("scrim").classList.remove("on"); document.querySelectorAll(".sheet").forEach((s) => s.classList.remove("on")); }
$("scrim").onclick = closeSheets;
document.querySelectorAll("[data-close]").forEach((b) => (b.onclick = closeSheets));
document.querySelectorAll("[data-explain]").forEach((b) => (b.onclick = () => {
  openSheet("sheetExplain");
  if (b.dataset.q) ask(b.dataset.q);
}));
$("btnSetup").onclick = $("btnSetup2").onclick = () => openSheet("sheetSetup");
$("btnQuality").onclick = () => { openSheet("sheetQuality"); loadQuality(); };
$("askForm").onsubmit = (e) => { e.preventDefault(); ask($("askInput").value); };

$("btnSkip").onclick = () => toast("You can skip one instalment at a time, about 2 working days before the date. Prototype: nothing changes.");
$("btnChange").onclick = () => toast("You can change the amount or date any time, about 2 working days before the debit. Prototype: nothing changes.");
$("btnCancel").onclick = () => {
  const d = state.d, red = d.gain < 0;
  $("cancelExplain").classList.toggle("hidden", !red);
  $("cancelExplainText").textContent = `Your SIP is ${inr(d.gain)} below what you put in right now. Want a plain-words explanation before you decide?`;
  openSheet("sheetCancel");
};
$("btnConfirmCancel").onclick = () => { closeSheets(); toast("Prototype: nothing was cancelled."); };

// setup
document.querySelectorAll("[data-scn]").forEach((b) => (b.onclick = async () => { closeSheets(); await load(SCENARIOS[b.dataset.scn]); toast("Showing: " + b.querySelector("b").textContent); }));
document.querySelectorAll("[data-mode]").forEach((b) => (b.onclick = () => {
  document.querySelectorAll("[data-mode]").forEach((x) => x.classList.toggle("on", x === b));
  $("formSample").classList.toggle("hidden", b.dataset.mode !== "sample");
  $("formManual").classList.toggle("hidden", b.dataset.mode !== "manual");
}));
function fillMonths() {
  const months = state.meta.months[$("fFund").value].slice(-60);
  const opt = (m, label) => `<option value="${m}">${label || monthName(m)}</option>`;
  $("fStart").innerHTML = months.slice(0, -1).map((m) => opt(m)).reverse().join("");
  $("fAsOf").innerHTML = opt("", "Today") + months.slice(1).map((m) => opt(m)).reverse().join("");
}
$("formSample").onsubmit = async (e) => {
  e.preventDefault();
  const f = new FormData(e.target), start = f.get("start"), asOf = f.get("as_of") || null;
  if (asOf && asOf <= start) { toast("'See it as of' must be after the first instalment."); return; }
  try { await load({ mode: "sample", fund: f.get("fund"), amount: +f.get("amount"), start, as_of: asOf }); closeSheets(); } catch (err) { toast(err.message); }
};
$("formManual").onsubmit = async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  try { await load({ mode: "manual", amount: +f.get("amount"), instalments: +f.get("instalments"), current_value: +f.get("current_value") }); closeSheets(); } catch (err) { toast(err.message); }
};

// ---------- quality sheet ----------
async function loadQuality() {
  const body = $("qualityBody");
  const { summary: s, rows } = await api("/api/quality");
  if (!s) { body.textContent = "No test run yet."; return; }
  body.innerHTML = `
    <p style="font-size:14px;color:#D6D7DA">Every answer passes three checks before you see it. We test the whole system on ${s.total} questions
    taken from real investor worries in our research (the Evidence Log's golden set).</p>
    <div class="q-score">
      <div><b>${s.passed}/${s.total}</b><small>test questions passed</small></div>
      <div><b>${s.declined_advice}/${s.advice_questions}</b><small>advice questions declined</small></div>
      <div><b>${s.safety}/${s.total}</b><small>answers passed safety</small></div>
    </div>
    <ol class="q-steps">
      <li><b>Before the AI:</b> questions asking what to buy, sell, stop or predict are declined, with official links.</li>
      <li><b>The AI</b> only sees numbers the system calculated, and must say when it is not sure.</li>
      <li><b>After the AI:</b> replies with advice words, fund names, or any number not in your account are blocked and replaced by a checked answer.</li>
    </ol>
    <p style="font-size:12px;color:var(--txt3)">Last run: ${s.run_at} · mode: ${s.mode}${s.model ? " · " + s.model : ""}</p>
    <div id="qRows"></div>`;
  rows.forEach((r) => {
    const d = document.createElement("div"); d.className = "q-row " + (r.pass ? "pass" : "fail");
    d.innerHTML = `<div class="q"></div><div class="meta"></div><div class="a"></div>`;
    d.querySelector(".q").textContent = r.question;
    d.querySelector(".meta").textContent = `expected: ${r.expected} · got: ${r.got}${r.golden_item ? " · golden-set item " + r.golden_item : ""}`;
    d.querySelector(".a").textContent = r.answer;
    $("qRows").appendChild(d);
  });
}

// ---------- start ----------
(async () => {
  state.meta = await api("/api/funds");
  $("fFund").innerHTML = state.meta.funds.map((f) => `<option value="${f.key}">${f.label}</option>`).join("");
  $("fFund").onchange = fillMonths; fillMonths();
  const scn = new URLSearchParams(location.search).get("scenario");
  await load(SCENARIOS[scn] || SCENARIOS.red);
  // Deep links for user tests, e.g. /?scenario=flat#details
  const h = location.hash.slice(1);
  if (h === "sips") document.querySelector('[data-tab="sips"]').click();
  if (h === "details" || h === "cancel") go("vDetails");
  if (h === "analysis") go("vAnalysis");
  if (h === "explain") openSheet("sheetExplain");
  if (h === "cancel") $("btnCancel").click();
})();
