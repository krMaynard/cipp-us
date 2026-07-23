#!/usr/bin/env python3
"""Parse the IAPP AIGP Practice Exam (v2.0) plain-text dump into questions.json.

Source is the natural-language text of the purchased IAPP AIGP Practice Exam PDF
(Google Drive), saved to build/exam/exam-raw.txt. It has three sections:
  * the exam body  — "N. <stem> A. <a> B. <b> C. <c> D. <d>" (some items add E.)
  * the answer key table — "N <letter(s)> <comp>"
  * item rationales — "N. The correct answer is X. <text> Body of Knowledge
    Domain <roman>, Competency <letter>"

Answer + domain + rationale come from the rationales section (most reliable);
stem + options from the body. Correct letters are cross-checked against the
answer-key table. Output schema matches the CIPP/US pipeline so exam_audio.py /
exam_anki.py / exam_cram.py work unchanged.
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path

RAW = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("build/exam/exam-raw.txt")
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("build/exam/questions.json")

FOOTER = re.compile(
    r"©\s*2024 IAPP\..*?AIGP Practice Exam v2\.0", re.S)
NOISE = [
    re.compile(r"Answer Key tally\. The Answer Sheet has been left blank to allow you to enter your selections\.", re.I),
    re.compile(r"For the next question ONLY:\s*Select all that apply\.", re.I),
    re.compile(r"This is a multi-select question\..*?(?=\n|$)", re.I),
    re.compile(r"Only one order is correct and this question is marked.*?in order[,\.]?", re.I | re.S),
    re.compile(r"All \d+ options will need to be included in your response\.?", re.I),
    re.compile(r"The Answer Sheet has been left blank to allow you to enter your (?:response|selections?)[^.]*\.", re.I),
    re.compile(r"^AIGP Practice Exam\s*$", re.M),
]

DOMAIN_NAME = {  # AIGP BoK v2.0 answer-key groups items into four domains
    "I": "Domain I", "II": "Domain II", "III": "Domain III", "IV": "Domain IV",
}

def clean(s: str) -> str:
    s = FOOTER.sub(" ", s)
    for n in NOISE:
        s = n.sub(" ", s)
    s = (s.replace("\\.", ".").replace("\\#", "#").replace("\\_", "_")
           .replace("“", '"').replace("”", '"').replace("’", "'"))
    return re.sub(r"\s+", " ", s).strip()


def parse_rationales(text: str) -> dict:
    """num -> {answer:[letters], rationale, domain, subdomain}."""
    start = text.rfind("Item Rationales")
    body = text[start:]
    # split on "\nN\. " boundaries (rationale items)
    parts = re.split(r"(?:^|\n)\s*(\d{1,3})\\?\.\s+", body)
    out = {}
    # parts = ['Item Rationales...', '1', 'text', '2', 'text', ...]
    for i in range(1, len(parts) - 1, 2):
        num = int(parts[i]); chunk = parts[i + 1]
        m = re.search(r"[Tt]he correct answers? (?:is|are)\s+([A-E](?:\s*(?:,|and)\s*[A-E])*)", chunk)
        letters = re.findall(r"[A-E]", m.group(1)) if m else []
        dm = re.search(r"Domain\s+([IV]+),\s*Competency\s+([A-E])", chunk)
        domain = dm.group(1) if dm else None
        comp = dm.group(2) if dm else None
        # rationale text: drop the trailing "Body of Knowledge Domain..." tag
        rat = re.split(r"Body of Knowledge Domain", chunk)[0]
        out[num] = {
            "answer": letters,
            "rationale": clean(rat),
            "domain": domain,
            "subdomain": comp,
        }
    return out


def parse_answer_key(text: str) -> dict:
    """num -> [letters] from the tally table (cross-check)."""
    s = text.rfind("Answer Key\n\nFor each correct response")
    if s < 0:
        s = text.rfind("Answer Key")
    e = text.rfind("Item Rationales")
    tbl = text[s:e]
    out = {}
    for m in re.finditer(r"(?<!\d)(\d{1,3})\s+([A-E](?:,[A-E])*)\b", tbl):
        num = int(m.group(1))
        if 1 <= num <= 100:
            out.setdefault(num, [x for x in m.group(2).split(",") if x])
    return out


def parse_body(text: str, rats: dict) -> dict:
    """num -> {stem, options{A..}}."""
    start = text.find("AIGP Practice Exam", text.find("Instructions"))
    start = text.find("1\\.", start)
    end = text.rfind("Answer Key\n\nFor each correct response")
    if end < 0:
        end = text.find("Item Rationales")
    body = text[start:end]
    parts = re.split(r"(?:^|\n)\s*(\d{1,3})\\?\.\s+", body)
    out = {}
    for i in range(1, len(parts) - 1, 2):
        num = int(parts[i]); chunk = parts[i + 1]
        if not (1 <= num <= 100):
            continue
        chunk = clean(chunk)
        # option letters present for this item (D always; E for multi-select)
        letters = ["A", "B", "C", "D"]
        if re.search(r"\bE\.\s", chunk):
            letters.append("E")
        # find each "X. " boundary
        opts = {}
        stem = chunk
        idxs = []
        for L in letters:
            m = re.search(rf"(?<![A-Za-z]){L}\.\s", chunk)
            if m:
                idxs.append((L, m.start(), m.end()))
        idxs.sort(key=lambda x: x[1])
        if idxs:
            stem = chunk[:idxs[0][1]].strip()
            for j, (L, s0, s1) in enumerate(idxs):
                e0 = idxs[j + 1][1] if j + 1 < len(idxs) else len(chunk)
                opts[L] = chunk[s1:e0].strip().rstrip(".").strip()
        out[num] = {"stem": stem, "options": opts}
    return out


def main():
    text = RAW.read_text()
    rats = parse_rationales(text)
    key = parse_answer_key(text)
    body = parse_body(text, rats)

    questions = []
    problems = []
    for num in range(1, 101):
        b = body.get(num); r = rats.get(num, {})
        if not b or not b.get("options"):
            problems.append(f"q{num}: no body/options"); continue
        ans = r.get("answer") or key.get(num) or []
        kans = key.get(num)
        if kans and ans and set(ans) != set(kans):
            problems.append(f"q{num}: rationale ans {ans} != key {kans}")
        multi = len(ans) > 1
        q = {
            "num": num,
            "stem": b["stem"],
            "options": b["options"],
            "answer": ",".join(ans) if multi else (ans[0] if ans else None),
            "multi": multi,
            "rationale": r.get("rationale", ""),
            "domain": r.get("domain"),
            "domain_name": DOMAIN_NAME.get(r.get("domain"), None),
            "subdomain": r.get("subdomain"),
            "scenario": None,
        }
        questions.append(q)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(questions, indent=2, ensure_ascii=False))
    print(f"wrote {len(questions)} questions -> {OUT}")
    miss_ans = [q["num"] for q in questions if not q["answer"]]
    miss_rat = [q["num"] for q in questions if not q["rationale"]]
    print(f"missing answer: {miss_ans or 'none'}")
    print(f"missing rationale: {miss_rat or 'none'}")
    print(f"option-count histogram: "
          + str({k: sum(1 for q in questions if len(q['options']) == k) for k in (2,3,4,5)}))
    if problems:
        print("PROBLEMS:")
        for p in problems: print("  ", p)


if __name__ == "__main__":
    main()
