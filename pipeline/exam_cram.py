#!/usr/bin/env python3
"""Generate an exam-derived CRAM sheet from the parsed practice test.

Turns the 90 questions into a domain-by-domain rapid-review: for each item, the
correct answer + the one-line rule behind it (compressed from the official
rationale). Plus a hand-written 2-day cram plan and the highest-yield facts.
Outputs both Markdown and a self-contained, print/dark-aware HTML page.
"""
import json, re, html
from pathlib import Path

QS = json.load(open("build/exam/questions.json"))
OUT_DIR = Path("build/exam")
OUT_DIR.mkdir(parents=True, exist_ok=True)

DOMAINS = {
 "I":  "Introduction to the U.S. Privacy Environment",
 "II": "Limits on Private-Sector Collection & Use of Data",
 "III":"Government & Court Access to Private-Sector Information",
 "IV": "Workplace Privacy",
 "V":  "State Privacy Laws",
}
# exam question counts per domain (from the exam's own scoring summary)
WEIGHT = {"I":30,"II":27,"III":7,"IV":11,"V":15}

def first_sentences(t, n=2, cap=260):
    t=re.sub(r"\s+"," ",t or "").strip()
    parts=re.split(r'(?<=[.!?])\s+', t)
    out=" ".join(parts[:n])
    if len(out)>cap:
        out=out[:cap].rsplit(" ",1)[0]+"…"
    return out

def topic(stem):
    s=re.sub(r"\s+"," ",stem).strip()
    # cut at first question mark or ~90 chars
    m=re.search(r"\?", s)
    if m and m.end()<130: return s[:m.end()]
    return (s[:90].rsplit(" ",1)[0]+"…") if len(s)>90 else s

# ---- markdown ----
md=[]
md.append("# CIPP/US — Two-Day Cram Pack\n")
md.append("_Derived from your IAPP CIPP/US Practice Exam (v2.1, 90 items) + the "
          "*U.S. Private-Sector Privacy* body of knowledge. This is a study aid — "
          "verify anything exam-critical against the book._\n")

md.append("## How to cram in 2 days\n")
md.append("""**Reality:** the exam is 90 scored items, 2.5 hours, multiple-choice, one right answer,
scaled score 300 (pass ≈ 300/500). It rewards *recognizing which law/rule governs a fact pattern* far
more than deep recall. So cramming = pattern-matching drills, not re-reading.

**Domain weighting on the practice test (mirror of the real blueprint) — spend your time proportionally:**

| Domain | Topic | Practice-test items | Cram priority |
|---|---|---|---|
| I | Intro to U.S. privacy environment | 30 | ★★★ heaviest |
| II | Limits on private-sector data use (FCRA, GLBA, HIPAA, marketing) | 27 | ★★★ heaviest |
| V | State laws (CCPA/CPRA, breach, biometrics) | 15 | ★★ |
| IV | Workplace privacy | 11 | ★★ |
| III | Government & court access (ECPA, FISA, CALEA) | 7 | ★ lightest |

### Day 1 — absorb + first pass
1. **Morning (2–3h):** Open `cheatsheet.html` (your one-page master sheet). Read it top to bottom once.
   Then listen to the **chapter lecture + drill audio** for the domains you feel weakest in (I and II first).
2. **Midday (2h):** Take the **practice exam once, timed (150 min)**, closed-book. Mark every guess.
3. **Afternoon (2h):** Grade it. For every miss/guess, read the rationale (below, or in the PDF) and the
   matching cheatsheet line. Import the **practice-exam Anki deck** and do a first review pass.

### Day 2 — drill the gaps
4. **Morning (2h):** Anki: churn the deck; re-listen to the **practice-test audio drill** (hands-free) —
   answer aloud in the 6-second gaps.
5. **Midday (1–2h):** Re-read the **Rapid Review by domain** (below). Focus on the *commonly-confused pairs*
   and *exam traps* at the end — that's where most points are lost.
6. **Afternoon (1h):** Skim the two heaviest domains (I & II) one more time. Light review of III (only 7 items).
7. **Night before:** Sleep. Don't cram new material past this point — reinforce, don't overload.

### Test-taking tactics
- Read the **call of the question** first (NOT / EXCEPT / BEST / FIRST are load-bearing — watch for them).
- Eliminate two wrong answers, then decide which law/authority actually governs.
- "Scenario" sets: read the scenario once, answer all its questions before moving on.
- Don't overthink — the intended answer is the textbook rule, not a real-world edge case.
""")

md.append("\n## Rapid review — every practice item as a one-line rule\n")
md.append("_Read this like flashcards: cover the answer, recall the rule, uncover._\n")
by={}
for q in QS: by.setdefault(q["domain"],[]).append(q)
for d in ["I","II","III","IV","V"]:
    md.append(f"\n### Domain {d} — {DOMAINS[d]}  ·  {WEIGHT[d]} items\n")
    for q in sorted(by.get(d,[]), key=lambda x:x["num"]):
        L=q["answer"]; ans=re.sub(r"\s+"," ",q["options"][L]).strip().rstrip(".")
        rule=first_sentences(q["rationale"],2)
        scen=f" _(Scenario {q['scenario']['label']})_" if q.get("scenario") else ""
        md.append(f"- **Q{q['num']}** — {topic(q['stem'])}{scen}  \n  → **{L}. {ans}.** {rule}")

md.append("\n## Highest-value facts to memorize cold\n")
md.append("""These are the rote items the exam loves — you either know them or you don't:

- **FCRA (1970)** regulates consumer reporting agencies; **FACTA (2003)** amended it to fight **identity theft**
  (free annual report, truncation, Red Flags, disposal rule). Enforced by **FTC + CFPB**.
- **GLBA** = financial. **Privacy Rule** (notice + opt-out of sharing with *non-affiliated* third parties) and
  **Safeguards Rule** (3 layers: **administrative, technical, physical**). "Reasonable means" to opt out = e.g. toll-free number, form — NOT "email a teller".
- **HIPAA**: **covered entity** (provider/plan/clearinghouse) vs **business associate** (vendor handling PHI → needs a **BAA**).
  Info YOU give a random health app is not HIPAA-covered (app isn't a covered entity). **42 CFR Part 2** (substance-use records) is *stricter* — needs **consent even for treatment**.
- **FERPA**: education records; school must act on access request within **45 days**; directory info can be disclosed.
- **COPPA**: under-13, verifiable parental consent; FTC-enforced.
- **VPPA**: video rental/streaming records; exceptions include order fulfillment / debt collection / ownership transfer.
- **ECPA / SCA**: the **180-day rule** — email stored **≤180 days** needs a **warrant**; **>180 days** a subpoena may suffice (know this cold).
- **CALEA**: telephone, broadband, VoIP carriers must enable lawful intercept — **NOT search engines**.
- **FISA / FISC**: foreign-intelligence surveillance needs **FISC court** approval — no warrantless surveillance of U.S. persons.
- **FTC Act §5**: "unfair or deceptive acts or practices." **Consent decree** = settle, no admission of fault, change practices. **Wyndham**: FTC can police lax data security. **Common carriers, banks, non-profits, and USPS/government are OUTSIDE §5.**
- **CFPB**: investigate, subpoena, hold hearings, bring **civil** actions (e.g., bank opening unauthorized accounts).
- **Preemption**: a federal statute overrides a conflicting state one. **No comprehensive federal privacy/breach law exists** — sectoral federal laws generally do **not** preempt (often stricter) state breach laws.
- **Private right of action**: lets *individuals* sue (e.g., BIPA, CCPA breach).
- **Biometrics**: **Illinois BIPA** — **$1,000** per negligent / **$5,000** per willful violation, **private right of action**. Texas & Washington: **AG-only** enforcement.
- **State comprehensive laws** (CCPA/CPRA, VCDPA, CPA, CTDPA, UCPA): rights to access/delete/correct/opt-out of **sale/sharing**; **Colorado & others** add opt-out of **profiling**; most enforced by the **state Attorney General**.
- **Breach notification**: exists in **all 50 states**; "covered entity" ≈ a business subject to that state's law; notify residents of **every state** where affected people live. **~35 states** also have **data-destruction** laws.
- **Cross-border**: **Schrems II (2020)** killed **Privacy Shield**; valid EU→US transfer tools = **SCCs, BCRs, explicit consent, Data Privacy Framework** (NOT "FTP").
- **Info management program order**: **Discover → Build → Communicate → Evolve.**
- **Three branches**: legislative, executive, judicial (**"administrative" is not a branch**; agencies sit in the executive).
""")

md.append("\n## Commonly-confused pairs & classic traps\n")
md.append("""- **Covered entity vs business associate** (HIPAA) — the app/vendor is usually the *business associate* (needs a BAA).
- **GLBA Privacy Rule vs Safeguards Rule** — notice/opt-out vs the admin/technical/physical security program.
- **FCRA vs FACTA** — original consumer-report law vs the 2003 identity-theft amendment.
- **Consent decree vs private right of action** — agency settlement vs individual's right to sue.
- **Warrant vs subpoena** under ECPA — driven by the **180-day** storage line.
- **Sale vs sharing vs profiling** opt-outs — CCPA/CPRA "Do Not Sell **or Share**"; profiling opt-out is a CO/VA-style right.
- **§5 who's exempt** — common carriers, banks (mostly), non-profits, and **government/USPS**.
- **NOT / EXCEPT / BEST / FIRST** in the stem — half of misses are from misreading the call of the question.
""")

md_text="\n".join(md)
(OUT_DIR/"cram-pack.md").write_text(md_text)

# ---- HTML (self-contained, light/dark, print-friendly) ----
def md_inline(s):
    s=html.escape(s)
    s=re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s=re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", s)
    s=re.sub(r"_(.+?)_", r"<em>\1</em>", s)
    s=re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return s

# Build rapid-review HTML cards per domain
def review_html():
    out=[]
    for d in ["I","II","III","IV","V"]:
        out.append(f'<h3>Domain {d} — {html.escape(DOMAINS[d])} <span class="pill">{WEIGHT[d]} items</span></h3>')
        out.append('<div class="cards">')
        for q in sorted(by.get(d,[]), key=lambda x:x["num"]):
            L=q["answer"]; ans=html.escape(re.sub(r"\s+"," ",q["options"][L]).strip().rstrip("."))
            rule=html.escape(first_sentences(q["rationale"],2))
            scen=f' · Scenario {q["scenario"]["label"]}' if q.get("scenario") else ""
            out.append(
              f'<div class="qc"><div class="qt">Q{q["num"]}<span class="sub">{q["subdomain"] or ""}{scen}</span></div>'
              f'<div class="topic">{html.escape(topic(q["stem"]))}</div>'
              f'<div class="ans"><b>{L}.</b> {ans}.</div>'
              f'<div class="why">{rule}</div></div>')
        out.append('</div>')
    return "\n".join(out)

HEAD_HTML = md_text.split("## Rapid review")[0]
TAIL_HTML = "## Highest-value facts" + md_text.split("## Highest-value facts")[1]

def block_to_html(block):
    lines=block.split("\n"); out=[]; in_ul=False; in_tbl=False; tbl=[]
    def flush_tbl():
        nonlocal tbl,in_tbl
        if not tbl: return
        rows=[r for r in tbl if not re.match(r'^\|[\s:|-]+\|$', r)]
        out.append("<table>")
        for i,r in enumerate(rows):
            cells=[c.strip() for c in r.strip().strip("|").split("|")]
            tag="th" if i==0 else "td"
            out.append("<tr>"+"".join(f"<{tag}>{md_inline(c)}</{tag}>" for c in cells)+"</tr>")
        out.append("</table>"); tbl=[]; in_tbl=False
    for ln in lines:
        if ln.startswith("## "):
            if in_ul: out.append("</ul>"); in_ul=False
            flush_tbl(); out.append(f"<h2>{md_inline(ln[3:])}</h2>")
        elif ln.startswith("### "):
            if in_ul: out.append("</ul>"); in_ul=False
            flush_tbl(); out.append(f"<h3>{md_inline(ln[4:])}</h3>")
        elif ln.strip().startswith("|"):
            in_tbl=True; tbl.append(ln.strip())
        elif re.match(r'^\d+\.\s', ln.strip()):
            flush_tbl()
            if not in_ul: out.append("<ol>"); in_ul="ol"
            out.append(f"<li>{md_inline(re.sub(r'^\d+\.\s','',ln.strip()))}</li>")
        elif ln.strip().startswith("- "):
            flush_tbl()
            if not in_ul: out.append("<ul>"); in_ul="ul"
            out.append(f"<li>{md_inline(ln.strip()[2:])}</li>")
        elif ln.strip()=="":
            if in_ul: out.append("</ul>" if in_ul=="ul" else "</ol>"); in_ul=False
            flush_tbl()
        else:
            if in_ul: out.append("</ul>" if in_ul=="ul" else "</ol>"); in_ul=False
            flush_tbl()
            if ln.strip(): out.append(f"<p>{md_inline(ln.strip())}</p>")
    if in_ul: out.append("</ul>" if in_ul=="ul" else "</ol>")
    flush_tbl()
    return "\n".join(out)

CSS = """
:root{--bg:#f6f4ee;--fg:#1b2333;--muted:#5d6675;--accent:#8c2f28;--card:#fffdf8;--line:#ded7c6;--pill:#efe6d2}
@media(prefers-color-scheme:dark){:root{--bg:#141821;--fg:#eef1f6;--muted:#98a2b3;--accent:#e07a70;--card:#1b212c;--line:#2c3444;--pill:#26303f}}
:root[data-theme=dark]{--bg:#141821;--fg:#eef1f6;--muted:#98a2b3;--accent:#e07a70;--card:#1b212c;--line:#2c3444;--pill:#26303f}
:root[data-theme=light]{--bg:#f6f4ee;--fg:#1b2333;--muted:#5d6675;--accent:#8c2f28;--card:#fffdf8;--line:#ded7c6;--pill:#efe6d2}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 -apple-system,system-ui,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:900px;margin:0 auto;padding:32px 22px 80px}
h1{font-size:30px;margin:0 0 6px;letter-spacing:-.01em}
h2{font-size:22px;margin:34px 0 10px;padding-top:14px;border-top:2px solid var(--line);color:var(--accent)}
h3{font-size:17px;margin:22px 0 8px}
.pill{font-size:12px;background:var(--pill);color:var(--muted);padding:2px 9px;border-radius:20px;font-weight:600;margin-left:6px;white-space:nowrap}
p{margin:8px 0}
ul,ol{margin:8px 0;padding-left:22px}li{margin:5px 0}
code{font-family:ui-monospace,Menlo,monospace;font-size:.9em;background:var(--pill);padding:1px 5px;border-radius:4px}
table{border-collapse:collapse;width:100%;margin:12px 0;font-size:14.5px}
th,td{border:1px solid var(--line);padding:6px 9px;text-align:left;vertical-align:top}
th{background:var(--pill)}
.cards{display:grid;grid-template-columns:1fr;gap:8px;margin:8px 0}
.qc{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:7px;padding:9px 12px}
.qt{font-weight:700;font-family:ui-monospace,Menlo,monospace;color:var(--accent);font-size:13px}
.qt .sub{color:var(--muted);font-weight:500;margin-left:8px}
.topic{font-size:14.5px;margin:2px 0 5px}
.ans{font-size:15px;font-weight:600}
.why{font-size:13.5px;color:var(--muted);margin-top:3px}
.lead{color:var(--muted);font-size:14.5px}
.toggle{position:fixed;top:12px;right:14px;background:var(--card);border:1px solid var(--line);color:var(--fg);border-radius:20px;padding:6px 12px;font-size:13px;cursor:pointer}
@media print{:root{--bg:#fff;--fg:#1b2333;--muted:#4a5262;--accent:#8c2f28;--card:#fff;--line:#c9c2b2;--pill:#efe6d2}
 .toggle{display:none}body{background:#fff;color:#000}.qc{break-inside:avoid}h2,h3{break-after:avoid}.cards{gap:6px}}
"""

htmlpage = f"""<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CIPP/US — Two-Day Cram Pack</title><style>{CSS}</style>
<button class="toggle" onclick="var r=document.documentElement;r.dataset.theme=(r.dataset.theme==='dark'?'light':'dark')">◐ theme</button>
<div class="wrap">
<h1>CIPP/US — Two-Day Cram Pack</h1>
<p class="lead">Derived from your IAPP CIPP/US Practice Exam (v2.1, 90 items) and the <em>U.S. Private-Sector Privacy</em> body of knowledge. A study aid — verify anything exam-critical against the book.</p>
{block_to_html(HEAD_HTML.split(chr(10),2)[2] if False else HEAD_HTML)}
<h2>Rapid review — every practice item as a one-line rule</h2>
<p class="lead">Read like flashcards: cover the answer, recall the rule, uncover.</p>
{review_html()}
{block_to_html(TAIL_HTML)}
</div>
"""
(OUT_DIR/"cram-pack.html").write_text(htmlpage)
print("wrote", OUT_DIR/"cram-pack.md", "and", OUT_DIR/"cram-pack.html")
print("md chars:", len(md_text), "| html chars:", len(htmlpage))
