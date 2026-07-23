#!/usr/bin/env python3
"""Build an Anki .apkg of the CIPP/US Practice Exam — one card per question.

Front: scenario (if any) + question + the four options, with the question spoken
aloud (narrator voice). Back: the correct letter + its text + the official
rationale + domain, with the answer spoken aloud (second voice). Mirrors the
repo's regulations deck: fixed deck/model IDs and per-question stable GUIDs, so
re-importing an updated deck UPDATES cards in place (review scheduling survives).

Usage: python build_exam_anki.py <questions.json> <out.apkg> [--no-audio]
"""
from __future__ import annotations
import argparse, asyncio, json, re, sys, tempfile
from pathlib import Path

def _trust_proxy_ca():
    ca = Path("/root/.ccr/ca-bundle.crt")
    if ca.exists():
        try:
            import certifi; b=Path(certifi.where())
            if ca.read_text() not in b.read_text():
                with b.open("a") as fh: fh.write("\n"+ca.read_text())
        except Exception: pass
_trust_proxy_ca()
import genanki

# Fixed IDs — distinct from the regulations deck (…431/…432). Do not change.
MODEL_ID = 1841027501
DECK_ID  = 1841027502
QUESTION_VOICE = "en-US-AndrewMultilingualNeural"
ANSWER_VOICE   = "en-US-AvaMultilingualNeural"

CSS = """
.card { font-family:-apple-system,system-ui,"Segoe UI",Roboto,sans-serif;
  font-size:19px; line-height:1.5; color:#1b2333; background:#f6f4ee;
  text-align:left; padding:18px 20px; }
.nightMode.card { color:#eef1f6; background:#141821; }
.cue { font-size:12px; letter-spacing:.12em; text-transform:uppercase;
  color:#8c2f28; font-weight:700; margin-bottom:10px; }
.nightMode .cue { color:#e07a70; }
.scenario { font-size:15px; font-style:italic; color:#454f61; background:#efe9dd;
  border-left:3px solid #c9bfa9; padding:10px 12px; border-radius:4px; margin-bottom:12px; }
.nightMode .scenario { color:#b9c2d2; background:#1c222e; border-left-color:#37414f; }
.stem { font-size:20px; line-height:1.45; margin-bottom:12px; }
.opts { list-style:none; padding:0; margin:0; }
.opts li { padding:6px 10px; margin:5px 0; border:1px solid #ddd6c6; border-radius:6px; }
.nightMode .opts li { border-color:#2c3444; }
.opts .k { font-weight:700; font-family:ui-monospace,Menlo,monospace; margin-right:8px; color:#8c2f28; }
.nightMode .opts .k { color:#e07a70; }
li.correct { background:#e5efe0; border-color:#7ea36f; }
.nightMode li.correct { background:#1e2a1f; border-color:#4f6b45; }
hr { border:0; border-top:1px solid #d8d2c4; margin:16px 0; }
.nightMode hr { border-top-color:#2c3444; }
.ans { font-size:22px; font-weight:700; font-family:Georgia,serif; margin-bottom:6px; }
.ans .k { color:#8c2f28; }
.nightMode .ans .k { color:#e07a70; }
.rat { font-size:16px; line-height:1.5; margin-top:6px; }
.tag { font-family:ui-monospace,Menlo,monospace; font-size:11px; letter-spacing:.06em;
  text-transform:uppercase; color:#5d6675; margin-top:12px; }
.nightMode .tag { color:#8d97a7; }
.audio { margin-top:10px; }
.qaudio { margin:12px 0 2px; }
"""

_OPTS = """
<ul class="opts">
 <li class="{{OptACls}}"><span class="k">A</span>{{OptA}}</li>
 <li class="{{OptBCls}}"><span class="k">B</span>{{OptB}}</li>
 <li class="{{OptCCls}}"><span class="k">C</span>{{OptC}}</li>
 <li class="{{OptDCls}}"><span class="k">D</span>{{OptD}}</li>
</ul>
"""
QFMT = ('<div class="cue">CIPP/US · Domain {{Domain}} · Q{{Num}}</div>'
        '{{#Scenario}}<div class="scenario"><b>Scenario {{ScenLabel}}.</b> {{Scenario}}</div>{{/Scenario}}'
        '<div class="stem">{{Stem}}</div>' + _OPTS +
        '{{#QAudio}}<div class="qaudio">{{QAudio}}</div>{{/QAudio}}')
# On the back, re-render options with the correct one highlighted (OptXCls set).
AFMT = ('<div class="cue">CIPP/US · Domain {{Domain}} · Q{{Num}}</div>'
        '{{#Scenario}}<div class="scenario"><b>Scenario {{ScenLabel}}.</b> {{Scenario}}</div>{{/Scenario}}'
        '<div class="stem">{{Stem}}</div>' + _OPTS + '<hr>'
        '<div class="ans">Correct: <span class="k">{{Answer}}</span> — {{AnswerText}}</div>'
        '<div class="rat">{{Rationale}}</div>'
        '<div class="tag">Domain {{Domain}} ({{DomainName}}) · Subdomain {{Subdomain}}</div>'
        '{{#AAudio}}<div class="audio">{{AAudio}}</div>{{/AAudio}}')

MODEL = genanki.Model(
    MODEL_ID, "CIPP/US — Practice Exam Question",
    fields=[{"name":n} for n in
        ("Num","Domain","DomainName","Subdomain","ScenLabel","Scenario","Stem",
         "OptA","OptB","OptC","OptD","OptACls","OptBCls","OptCCls","OptDCls",
         "Answer","AnswerText","Rationale","QAudio","AAudio")],
    templates=[{"name":"Q","qfmt":QFMT,"afmt":AFMT}],
    css=CSS,
)

def norm(s): return re.sub(r"\s+"," ",s or "").replace("“",'"').replace("”",'"').replace("’","'").strip()

def q_spoken(q):
    o=q["options"]
    return (f"Question {q['num']}. {norm(q['stem'])} "
            f"A: {norm(o['A'])} B: {norm(o['B'])} C: {norm(o['C'])} D: {norm(o['D'])}")
def a_spoken(q):
    L=q["answer"]
    return f"The correct answer is {L}. {norm(q['options'][L])} {norm(q['rationale'])}"

import subprocess
import imageio_ffmpeg
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

def _ffmpeg(*a): subprocess.run([FFMPEG,"-hide_banner","-loglevel","error","-y",*a], check=True)
def _concat(parts, out):
    if len(parts)==1:
        import shutil; shutil.copy(parts[0], out); return
    lf=out.with_suffix(".txt")
    try:
        lf.write_text("".join(f"file '{Path(p).resolve().as_posix()}'\n" for p in parts))
        _ffmpeg("-f","concat","-safe","0","-i",str(lf),"-acodec","libmp3lame","-q:a","4",str(out))
    finally:
        lf.unlink(missing_ok=True)

def chunk_text(t, limit=240):
    sents=re.split(r'(?<=[.!?])\s+', t); out=[]; cur=""
    for s in sents:
        while len(s)>limit:
            cut=s.rfind(", ",0,limit)
            if cut<80: cut=s.rfind(" ",0,limit)
            if cut<0: cut=limit
            if cur: out.append(cur); cur=""
            out.append(s[:cut].strip()); s=s[cut:].strip()
        if len(cur)+len(s)+1<=limit: cur=(cur+" "+s).strip()
        else:
            if cur: out.append(cur)
            cur=s
    if cur: out.append(cur)
    return [c for c in out if c]

async def _synth_chunk(text, voice, path, timeout=12, attempts=40):
    import edge_tts
    for a in range(attempts):
        try:
            path.unlink(missing_ok=True)
            await asyncio.wait_for(edge_tts.Communicate(text,voice,rate="-4%").save(str(path)),timeout=timeout)
            if path.exists() and path.stat().st_size>0: return True
            raise RuntimeError("empty")
        except Exception:
            await asyncio.sleep(min(0.5*(a+1),6))
            if a and a%8==0: await asyncio.sleep(20)
    return False

async def synth_phase1(qs, work):
    """Sequential chunked edge-tts synth of every clip's chunks (async only)."""
    plan=[]
    for q in qs:
        plan.append((q["num"],"q",chunk_text(q_spoken(q)),QUESTION_VOICE))
        plan.append((q["num"],"a",chunk_text(a_spoken(q)),ANSWER_VOICE))
    total=sum(len(p[2]) for p in plan)
    print(f"Phase 1: synthesizing {total} chunks for {len(plan)} clips...",flush=True)
    done=0; chunkmap={}; failed=[]
    for num,kind,chunks,voice in plan:
        paths=[]
        for i,c in enumerate(chunks):
            cp=work/f"q{num:02d}_{kind}_{i:02d}.mp3"
            if not await _synth_chunk(c,voice,cp):
                failed.append(cp); print(f"    !! gave up on {cp.name}",flush=True)
            paths.append(cp); done+=1
            if done%25==0: print(f"    {done}/{total} chunks ({len(failed)} failed)",flush=True)
        chunkmap[(num,kind)]=paths
    return chunkmap, failed

def concat_phase2(chunkmap, media_dir, failed):
    """Sync ffmpeg concat, run OUTSIDE the event loop. Failed chunks -> silence."""
    print("Phase 2: concatenating clips with ffmpeg...",flush=True)
    failed=set(failed); miss=None
    if failed:
        miss=media_dir/"_w"/"_miss.mp3"; _ffmpeg("-f","lavfi","-i","anullsrc=r=24000:cl=mono",
            "-t","0.4","-q:a","9","-acodec","libmp3lame",str(miss))
    out={}
    for (num,kind),paths in chunkmap.items():
        fname=f"cippusexam_q{num:02d}_{kind}.mp3"
        _concat([(miss if p in failed else p) for p in paths], media_dir/fname)
        out.setdefault(num,{})[kind]=fname
    print(f"  {sum(len(v) for v in out.values())} clips ok",flush=True)
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("questions"); ap.add_argument("out")
    ap.add_argument("--no-audio",action="store_true")
    a=ap.parse_args()
    qs=json.loads(Path(a.questions).read_text())
    def snd(f): return f"[sound:{f}]" if f else ""
    with tempfile.TemporaryDirectory() as td:
        md=Path(td)
        if a.no_audio:
            amap={}
        else:
            work=md/"_w"; work.mkdir(exist_ok=True)
            chunkmap, failed=asyncio.run(synth_phase1(qs, work))  # network phase
            amap=concat_phase2(chunkmap, md, failed)              # ffmpeg phase (outside loop)
            for f in work.glob("*.mp3"): f.unlink()
            work.rmdir()
        deck=genanki.Deck(DECK_ID, "CIPP/US · Practice Exam (90 questions + rationales)")
        media=[]
        for q in qs:
            L=q["answer"]; cls={k:("correct" if k==L else "") for k in "ABCD"}
            clips=amap.get(q["num"],{})
            note=genanki.Note(model=MODEL, guid=genanki.guid_for(f"cippus-exam-q{q['num']}"),
                fields=[str(q["num"]), q["domain"] or "", q["domain_name"] or "", q["subdomain"] or "",
                        (q["scenario"] or {}).get("label","") if q["scenario"] else "",
                        norm((q["scenario"] or {}).get("text","")) if q["scenario"] else "",
                        norm(q["stem"]),
                        norm(q["options"]["A"]),norm(q["options"]["B"]),norm(q["options"]["C"]),norm(q["options"]["D"]),
                        cls["A"],cls["B"],cls["C"],cls["D"],
                        L, norm(q["options"][L]), norm(q["rationale"]),
                        snd(clips.get("q","")), snd(clips.get("a",""))],
                tags=[f"Domain-{q['domain']}", "CIPP-US-Practice-Exam"] +
                     ([f"Scenario-{q['scenario']['label']}"] if q["scenario"] else []))
            deck.add_note(note)
            media+=[str(md/f) for f in clips.values()]
        genanki.Package(deck, media_files=media).write_to_file(a.out)
        print(f"Wrote {a.out} ({len(qs)} notes, {len(media)} audio clips)")

if __name__=="__main__": main()
