#!/usr/bin/env python3
"""Parse the IAPP CIPP/US Practice Exam into structured JSON (build/exam/questions.json).

Input is the exam's text - either a JSON dump {"fileContent": "..."} (as produced
when the PDF is read from Drive) or a plain .txt of the same content.

    python pipeline/exam_extract.py <exam-dump.json|.txt> [out.json]

The exam is a purchased IAPP publication; keep the source and questions.json out
of version control (build/ is gitignored), same as the textbook EPUB.
"""
import json, re, sys
from pathlib import Path

SRC = sys.argv[1] if len(sys.argv) > 1 else "build/exam/exam-dump.json"
OUT = sys.argv[2] if len(sys.argv) > 2 else "build/exam/questions.json"
_raw = Path(SRC).read_text()
try:
    c = json.loads(_raw)["fileContent"]
except (json.JSONDecodeError, TypeError, KeyError):
    c = _raw

DOMAIN_NAMES = {
    "I":   "Introduction to the U.S. Privacy Environment",
    "II":  "Limits on Private-Sector Collection and Use of Data",
    "III": "Government and Court Access to Private-Sector Information",
    "IV":  "Workplace Privacy",
    "V":   "State Privacy Laws",
}

def clean(t: str) -> str:
    # collapse the PDF's hard-wrapped lines and page furniture into clean prose
    t = re.sub(r"©\s*20\d\d IAPP\..*?republication\.", " ", t)
    t = re.sub(r"©?20?\d\d,?\s*International Association of Privacy Professionals.*?\(IAPP\)", " ", t)
    t = t.replace("CIPP/US Practice Exam v2.1", " ")
    t = re.sub(r"\|\s*\|", " ", t)
    t = re.sub(r"\|\s*:-:\s*\|", " ", t)
    t = re.sub(r"\[\*\*Page \d+\*\*\]\(\)", " ", t)
    t = t.replace("-----", " ")
    t = re.sub(r"\\([.\#])", r"\1", t)     # unescape \. \#
    t = t.replace("**", "").replace("*", "")
    t = re.sub(r"[ \t]*\n[ \t]*", " ", t)  # join wrapped lines
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip()

# ---- 1. exam body: from "CIPP/US Practice Exam\n\n1\." to "Answer Key" ----
body_start = c.index("CIPP/US Practice Exam\n\n1\\.")
body_end = c.index("Answer Key\n\nFor each correct response")
body = c[body_start:body_end]

# ---- 2. rationales: after the SUMMARY, "Item Rationales" ----
rat_start = c.index("Item Rationales", c.index("SUMMARY"))
rat = c[rat_start:]

# --- parse rationales: "N. The correct answer is X. ... Body of Knowledge Domain D, Subdomain S" ---
rat_clean = clean(rat)
rat_items = {}
# split on "  N. The correct answer is"
for m in re.finditer(r"(?:^|\s)(\d{1,2})\.\s+The correct answer is\s+([A-D])\.\s*(.*?)(?=\s+\d{1,2}\.\s+The correct answer is\s+[A-D]\.|$)", rat_clean):
    n = int(m.group(1)); ans = m.group(2); expl = m.group(3).strip()
    dm = re.search(r"Body of Knowledge Domain\s+([IVX]+),?\s+Subdomain\s+([A-Z])", expl)
    domain = subdomain = None
    if dm:
        domain, subdomain = dm.group(1), dm.group(2)
        expl = expl[:dm.start()].strip()
    rat_items[n] = {"answer": ans, "rationale": expl, "domain": domain, "subdomain": subdomain}

# ---- 3. parse questions + options + scenarios from body ----
body_clean = clean(body)
# Scenarios: "SCENARIO X Please use the following scenario to answer the next N questions. <text> N. <first q>"
scenarios = {}  # question_number -> scenario text
for sm in re.finditer(r"SCENARIO\s+([IVX]+)\s+Please use the following scenario to answer the next\s+(\w+)\s+questions?\.\s*(.*?)(?=\s+\d{1,2}\.\s)", body_clean):
    scen_text = sm.group(3).strip()
    # attach to the block of questions until "END SCENARIO"
    scenarios[sm.end()] = (sm.group(1), scen_text)

# Question splitting: "N. <stem> A. <..> B. <..> C. <..> D. <..>"
q_pat = re.compile(r"(?:^|\s)(\d{1,2})\.\s+(.*?)\s+A\.\s+(.*?)\s+B\.\s+(.*?)\s+C\.\s+(.*?)\s+D\.\s+(.*?)(?=(?:\s+SCENARIO\s)|(?:\s+END SCENARIO)|(?:\s+\d{1,2}\.\s+.+?\s+A\.\s)|$)", re.DOTALL)

questions = {}
for m in q_pat.finditer(body_clean):
    n = int(m.group(1))
    if n < 1 or n > 90 or n in questions:
        continue
    stem = m.group(2).strip()
    opts = {L: m.group(i).strip() for L, i in zip("ABCD", (3,4,5,6))}
    # trim trailing scenario/END markers from option D
    opts["D"] = re.sub(r"\s+(END SCENARIO.*|SCENARIO .*)$", "", opts["D"]).strip()
    questions[n] = {"num": n, "stem": stem, "options": opts}

# attach scenarios: map by scanning body for SCENARIO...END SCENARIO ranges and the q numbers inside
for sm in re.finditer(r"SCENARIO\s+([IVX]+)\s+Please use the following scenario to answer the next\s+(\w+)\s+questions?\.\s*(.*?)END SCENARIO", body_clean, re.DOTALL):
    label, _, block = sm.group(1), sm.group(2), sm.group(3)
    # scenario text = up to first "N." question marker
    fm = re.search(r"\s\d{1,2}\.\s", block)
    scen_text = clean(block[:fm.start()]) if fm else ""
    qnums = [int(x) for x in re.findall(r"(?:^|\s)(\d{1,2})\.\s", block)]
    for qn in qnums:
        if qn in questions:
            questions[qn]["scenario"] = {"label": label, "text": scen_text}

# ---- merge ----
out = []
missing = []
for n in range(1, 91):
    q = questions.get(n)
    r = rat_items.get(n)
    if not q:
        missing.append(("Q", n)); continue
    if not r:
        missing.append(("R", n))
    rec = {
        "num": n,
        "stem": q["stem"],
        "options": q["options"],
        "answer": r["answer"] if r else None,
        "rationale": r["rationale"] if r else None,
        "domain": r["domain"] if r else None,
        "domain_name": DOMAIN_NAMES.get(r["domain"]) if r and r["domain"] else None,
        "subdomain": r["subdomain"] if r else None,
        "scenario": q.get("scenario"),
    }
    out.append(rec)

Path(OUT).parent.mkdir(parents=True, exist_ok=True)
Path(OUT).write_text(json.dumps(out, indent=2))
print("parsed questions:", len(out))
print("missing:", missing)
# sanity: print a few
for n in (1, 12, 35, 67, 90):
    q = next(x for x in out if x["num"]==n)
    print(f"\n--- Q{n} [{q['domain']}/{q['subdomain']}] ans={q['answer']} scen={q['scenario']['label'] if q['scenario'] else None}")
    print("stem:", q["stem"][:120])
    print("D:", q["options"]["D"][:90])
    print("rat:", (q["rationale"] or "")[:100])
