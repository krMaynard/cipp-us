#!/usr/bin/env python3
"""Two-voice audio drill of the IAPP AIGP Practice Exam.

Repo drill convention: a narrator voice asks a question + its options, a silent
gap to answer aloud, then a second voice gives the answer + rationale. Scenario
prompts are spoken once before their question group. Output is split into parts,
with an M3U playlist and a listening guide.

Robustness notes learned the hard way in this runtime:
  * edge-tts is synthesized SEQUENTIALLY with a hard per-call timeout. Parallel
    synthesis deadlocks: when one socket stalls, cancelling its siblings hangs.
  * Every spoken clip is split into <=240-char sentence CHUNKS. Long single
    utterances (~800 chars) make the multilingual voices hang indefinitely;
    sentence chunks synthesize reliably and read better.
  * All ffmpeg assembly happens AFTER the asyncio phase — mixing blocking
    subprocess calls into the loop also deadlocks here.
"""
from __future__ import annotations
import asyncio, json, re, subprocess, sys
from pathlib import Path

import imageio_ffmpeg
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

def _trust_proxy_ca() -> None:
    ca = Path("/root/.ccr/ca-bundle.crt")
    if ca.exists():
        try:
            import certifi; b = Path(certifi.where())
            if ca.read_text() not in b.read_text():
                with b.open("a") as fh: fh.write("\n"+ca.read_text())
        except Exception: pass
_trust_proxy_ca()
import edge_tts

NARRATOR = "en-US-AndrewMultilingualNeural"
ANSWERER = "en-US-AvaMultilingualNeural"
RATE = "-4%"
ANSWER_GAP = 6.0
CHUNK_LIMIT = 240
QUESTIONS = "build/exam/questions.json"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("build/exam/audio")
WORK = OUT / "_clips"
PART_SIZE = 15

def ffmpeg(*a): subprocess.run([FFMPEG,"-hide_banner","-loglevel","error","-y",*a], check=True)
def silence(path, sec):
    ffmpeg("-f","lavfi","-i","anullsrc=r=24000:cl=mono","-t",f"{sec:.2f}",
           "-q:a","9","-acodec","libmp3lame",str(path))
def concat(parts, out):
    lf = out.with_suffix(".txt")
    try:
        lf.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in parts))
        ffmpeg("-f","concat","-safe","0","-i",str(lf),"-acodec","libmp3lame","-q:a","4",str(out))
    finally:
        lf.unlink(missing_ok=True)

def norm(s): return re.sub(r"\s+"," ",s or "").replace("“",'"').replace("”",'"').replace("’","'").strip()
def q_script(q):
    o=q["options"]
    opts=" ".join(f"{L}: {norm(o[L])}" for L in ("A","B","C","D","E") if L in o)
    tail=" Select all that apply." if q.get("multi") else ""
    return f"Question {q['num']}.{tail} {norm(q['stem'])} {opts}"
def a_script(q):
    letters=[x for x in re.split(r"[,\s]+", str(q["answer"])) if x]
    if q.get("multi"):
        head=f"The correct answers are {', '.join(letters)}."
    else:
        L=letters[0]; head=f"The correct answer is {L}. {norm(q['options'].get(L,''))}"
    return f"{head} {norm(q['rationale'])}"

def chunk_text(t, limit=CHUNK_LIMIT):
    """Split into <=limit-char pieces on sentence boundaries (hard-split any
    single sentence that still exceeds the limit, on clause punctuation)."""
    sents=re.split(r'(?<=[.!?])\s+', t); out=[]; cur=""
    for s in sents:
        while len(s)>limit:                      # a lone over-long sentence
            cut=s.rfind(", ",0,limit)
            if cut<80: cut=s.rfind(" ",0,limit)
            if cut<0: cut=limit
            piece=s[:cut].strip()
            if cur: out.append(cur); cur=""
            out.append(piece); s=s[cut:].strip()
        if len(cur)+len(s)+1<=limit: cur=(cur+" "+s).strip()
        else:
            if cur: out.append(cur)
            cur=s
    if cur: out.append(cur)
    return [c for c in out if c]

# silence files (created in phase 2, referenced at plan time)
GAP=WORK/"_gap.mp3"; BTW=WORK/"_btw.mp3"; PREQ=WORK/"_preq.mp3"

def spoken_chunks(base, text, voice, synth_plan):
    """Register chunk clips for one spoken unit; return ordered chunk paths."""
    paths=[]
    for i,c in enumerate(chunk_text(text)):
        p=WORK/f"{base}_{i:02d}.mp3"; paths.append(p); synth_plan.append((p,c,voice))
    return paths

def plan_parts(qs):
    n_parts=(len(qs)+PART_SIZE-1)//PART_SIZE
    parts=[]; synth_plan=[]
    for pi in range(n_parts):
        chunk=qs[pi*PART_SIZE:(pi+1)*PART_SIZE]
        lo,hi=chunk[0]["num"],chunk[-1]["num"]
        seq=[]  # ordered list of file paths for assembly
        seq += spoken_chunks(f"intro{pi}",
            f"A I G P practice exam. Audio drill, part {pi+1} of {n_parts}. "
            f"Questions {lo} through {hi}. After each question, pause and answer aloud, then check yourself.",
            NARRATOR, synth_plan)
        seq.append(BTW)
        last=None
        for q in chunk:
            scen=q.get("scenario")
            if scen and scen["label"]!=last:
                seq += spoken_chunks(f"scen{q['num']}", f"Scenario {scen['label']}. {norm(scen['text'])}", NARRATOR, synth_plan)
                seq.append(BTW); last=scen["label"]
            if not scen: last=None
            seq += spoken_chunks(f"q{q['num']}", q_script(q), NARRATOR, synth_plan)
            seq += [PREQ, GAP]
            seq += spoken_chunks(f"a{q['num']}", a_script(q), ANSWERER, synth_plan)
            seq.append(BTW)
        parts.append((pi+1,lo,hi,seq))
    return parts, synth_plan

async def synth_one(path, text, voice, timeout=12, attempts=40):
    """Synth one chunk. Stalls are intermittent full hangs (healthy responses
    arrive in ~2-4s): short timeout abandons a stall fast, many fresh retries
    catch a healthy window, and a periodic cooldown lets an overloaded endpoint
    recover. Returns True on success, False if it ultimately couldn't."""
    for a in range(attempts):
        try:
            path.unlink(missing_ok=True)
            await asyncio.wait_for(
                edge_tts.Communicate(text, voice, rate=RATE).save(str(path)), timeout=timeout)
            if path.exists() and path.stat().st_size>0: return True
            raise RuntimeError("empty")
        except Exception:
            await asyncio.sleep(min(0.5*(a+1), 6))
            if a and a%8==0: await asyncio.sleep(20)   # cooldown: let endpoint recover
    return False

async def synth(plan):
    """Sequential synth. A chunk that can't be produced after all retries is
    recorded as failed (its path stays missing) rather than aborting the whole
    build; phase 2 substitutes a short silence so assembly still succeeds."""
    failed=[]
    for n,(path,text,voice) in enumerate(plan,1):
        if not await synth_one(path, text, voice):
            failed.append(path); print(f"    !! gave up on {path.name}", flush=True)
        if n%25==0: print(f"    {n}/{len(plan)} chunks ({len(failed)} failed)", flush=True)
    return failed

MISS=None  # silence placeholder for any chunk that failed to synth
def assemble(parts, failed):
    global MISS
    silence(GAP, ANSWER_GAP); silence(BTW, 1.2); silence(PREQ, 0.6)
    failed=set(failed)
    if failed:
        MISS=WORK/"_miss.mp3"; silence(MISS, 0.4)
    def resolve(p):
        return MISS if p in failed else p
    meta=[]
    for (pnum,lo,hi,seq) in parts:
        outf=OUT/f"exam-drill-part{pnum:02d}-q{lo:02d}-{hi:02d}.mp3"
        concat([resolve(p) for p in seq], outf)
        meta.append((outf.name,lo,hi,outf.stat().st_size))
        print(f"[part {pnum}] {outf.name} {outf.stat().st_size:,} bytes", flush=True)
    return meta

def main():
    qs=json.load(open(QUESTIONS))
    OUT.mkdir(parents=True, exist_ok=True); WORK.mkdir(parents=True, exist_ok=True)
    parts, synth_plan = plan_parts(qs)
    print(f"Phase 1: synthesizing {len(synth_plan)} chunks ({len(parts)} parts)...", flush=True)
    failed=asyncio.run(synth(synth_plan))
    print(f"Phase 2: assembling with ffmpeg... ({len(failed)} chunks substituted with silence)", flush=True)
    meta=assemble(parts, failed)
    (OUT/"exam-drill.m3u").write_text("#EXTM3U\n"+"".join(f"{n}\n" for n,_,_,_ in meta))
    guide=["# AIGP Practice Exam — Audio Drill\n",
           "Two voices: **Andrew** asks each question + options, **Ava** gives the answer + rationale.",
           f"6-second silent gap after every question for you to answer aloud. {len(meta)} parts, "
           f"~{sum(s for *_,s in meta)//1_000_000} MB total.\n",
           "| Part | Questions | File | Size |","|---|---|---|---|"]
    for n,lo,hi,s in meta:
        guide.append(f"| {n.split('part')[1][:2]} | {lo}–{hi} | `{n}` | {s/1_000_000:.1f} MB |")
    (OUT/"README.md").write_text("\n".join(guide)+"\n")
    for f in WORK.glob("*.mp3"): f.unlink()
    WORK.rmdir()
    print("DONE", len(meta), "parts", flush=True)

if __name__=="__main__":
    main()
