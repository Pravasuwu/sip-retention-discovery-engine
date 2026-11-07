# Online user research: 20 first-hand SIP stories

Date: 5 Nov 2026. Method: reflexive thematic analysis (Braun and Clarke) on public, first-hand posts. This is desk research on the internet (netnography), not interviews or a survey.

## 1. Sample

| | |
|---|---|
| People | 20, each a different author telling their own SIP story |
| Sources | TradingQnA forum 14, Substack 3, personal blogs 3 |
| Years | 2019 (3), 2022 (1), 2023 (4), 2024 (1), 2025 (2), 2026 (9) |
| First-time investor at the time | Yes 6, no 8, unclear 6 |
| Where they ended up | Kept going 8, paused or stopped 5, never started or avoids SIPs 3, undecided 4 |
| Overlap with the discovery engine | None (checked by author name against all 468 engine records) |

**Inclusion rule:** the person describes their own SIP or monthly investing decision. Excluded: general opinions, hypothetical or fictional investors (FundsIndia "investor diary", Value Research "Rohit", Abhinav Mishra's "Amit"), support staff replies, and one self-published story that contradicts itself (investmentsutras.com).

**Tried and not usable:** Reddit (blocks automated access), Medium, Value Research and Business Standard (block page fetches), and YouTube (comments are not visible to the fetch tool). These were not worked around.

Full list with links: `participants.csv`. Codebook: `codebook.csv`. Script that builds both: `code_sample.py`.

## 2. Coding

- 97 coded segments across 20 accounts, 76 codes.
- Code types: in vivo (each person's own words, max 8 words), descriptive (topic), process (action), value (the belief underneath).
- Code labels are in English so they can be compared across sources.
- Summaries in `participants.csv` are paraphrased, not copied.

## 3. Themes (built, not found)

Each theme is an argument. Participant IDs show where it comes from.

### Theme 1. A fixed amount feels like a promise that income can break, so people want control over the amount, not a way out.
Freelancers and people hit by a cash crunch describe the monthly commitment itself as the source of stress (P01, P02, P03, P19). What they ask for is to pause or change the amount without cancelling (P01, P13). Two people who "stopped their SIP" kept investing by hand or in lump sums (P03, P16). They quit the commitment, not investing.
- Latent reading: the SIP is felt as a debt-like obligation, not a choice.
- Codes: irregular income · fear of fixed commitment · wants amount flexibility · wants pause instead of cancel · pausing in a cash crunch · control over amount keeps them investing · stopping SIP form, keeps investing.

### Theme 2. Numbers people cannot read turn into distrust of the whole idea.
A wrong third-party calculator (P10), a WhatsApp article (P09), flat index returns (P04), press stories that FDs beat SIPs (P15) and inflation-adjusted projections (P18) all produce the same move: from "my number looks bad" to "SIPs don't work" or "I was misled".
- Latent reading: when the number is confusing, people blame the product, not the period.
- Codes: return numbers they cannot interpret · misleading return comparisons · flat or negative returns · comparing with FD returns · shock turns into distrust · feels misled by advertising.

### Theme 3. People who stay lean on something other than returns: a goal, a money rule, or a past regret.
Stayers describe a reason that outlasts a bad month: a child's education (P20), family debt they never want to repeat (P16), fixed money buckets and allocation rules (P02, P08), or the memory of missing a rally while waiting for a dip (P06, P07, P20). Even a professional says the urge to act never goes away (P17). What changes is having something to hold on to.
- Latent reading: staying is not calm, it is anchored fear.
- Codes: goal bigger than returns · regret after waiting · rules replace feelings · keeps SIP running in falls · knowledge does not remove fear.

### Theme 4. Doubt is settled outside the app, by whoever is loudest at that moment.
People take their doubts to forums (P01, P05, P12), WhatsApp forwards (P09), the press (P15) or a friend's SIP amount (P19). None mention the app helping them decide. Outside voices pull both ways: towards quitting (P09) and towards staying (P15's books).
- Codes: asking a forum to validate the plan · outside content shapes the decision · matching a friend's SIP amount · social comparison sets the amount.

### Surprise (negative cases)
- **Some SIPs end without the investor choosing.** A fund house paused an SIP with a day's notice (P12). A first-time investor cancelled their first SIP the next day because they could not tell when the next debit was due (P14).
- **Stopping a SIP is not always leaving.** P03 and P16 stopped the SIP but kept investing. A metric that counts only the first SIP would call them churn.

## 4. Triangulation with the discovery engine

| | Online sample | Engine (212 comments) |
|---|---|---|
| Can't pause → stop | Agrees (Theme 1) | Agrees: "can't pause or skip" most linked to stopping |
| Low or confusing returns | Agrees (Theme 2) | Agrees: most-mentioned topic |
| Advice outside the app | Agrees (Theme 4) | Agrees: outside reassurance topic |
| Stayers talk habit and goals | Agrees (Theme 3) | Agrees: stayers mention habit far more |
| Irregular-income earners as a group | **New:** 3 freelancers | Weak: 5 comments on unstable income |
| SIPs ending without a choice | **New:** P12, P14 | Not seen; supports metric-tree branches A and B |
| Goals as a reason to stay | Strong here | Engine grades this evidence weak |

## 5. Positionality and limits

- The researcher is an AI reading public text. There were no interviews, no follow-up questions and no member checks.
- People who post on investing forums and blogs are more engaged and more experienced than a typical first-time investor. Only 6 of 20 were clearly first-time investors at the time.
- All posts are in English and most are written for a finance-savvy audience, so Hindi- or regional-language investors are missing.
- Use these themes to write the interview guide for real first-time investors, not to size problems.
