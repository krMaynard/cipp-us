#!/usr/bin/env python3
"""Synthesize study audio (MP3) from generated lectures and study packs.

Audio-first design — three kinds of track per chapter:
  - lecture:   the spoken lecture, one narrator voice.
  - drill:     active-recall Q&A. Each question is spoken, then a silent
               gap for the listener to answer aloud, then "The answer is..."
               in a second voice. Built for hands-free review.
  - terms:     "term ... short pause ... definition" glossary run-through.

Uses edge-tts (Microsoft neural voices) over the network. The proxy's CA
bundle is appended to certifi once, at import, so the WSS call validates.
ffmpeg concatenates the per-segment MP3s and injects the silent gaps.

Usage:
    python pipeline/tts.py --build build --kinds lecture,drill,terms
    python pipeline/tts.py --build build --only 1 --kinds drill
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# --- make edge-tts trust the agent proxy's TLS interception ------------------
def _trust_proxy_ca() -> None:
    ca = Path("/root/.ccr/ca-bundle.crt")
    if not ca.exists():
        return
    try:
        import certifi
        bundle = Path(certifi.where())
        ca_text = ca.read_text()
        if ca_text not in bundle.read_text():
            with bundle.open("a") as fh:
                fh.write("\n" + ca_text)
    except Exception:  # noqa: BLE001 - best effort; only needed behind the proxy
        pass


_trust_proxy_ca()
import edge_tts  # noqa: E402  (import after CA fix)

NARRATOR = "en-US-AndrewMultilingualNeural"   # lecture + questions
ANSWERER = "en-US-AvaMultilingualNeural"      # answers + definitions
LECTURE_RATE = "-4%"                          # a touch slower for studying


def ffmpeg(*args: str) -> None:
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
        check=True,
    )


async def say(text: str, path: Path, voice: str, rate: str = "+0%",
              attempts: int = 4) -> None:
    """Synthesize one segment, retrying transient edge-tts failures.

    The Microsoft endpoint intermittently returns 503 / drops the socket under
    load; a full book is hundreds of segments, so a single blip must not lose a
    track. Retry with exponential backoff, then surface the last error.
    """
    last: Exception | None = None
    for i in range(attempts):
        try:
            await edge_tts.Communicate(text, voice, rate=rate).save(str(path))
            if path.stat().st_size > 0:
                return
            raise RuntimeError("edge-tts produced an empty audio file")
        except Exception as e:  # noqa: BLE001 - retry any transient synth error
            last = e
            if i < attempts - 1:
                await asyncio.sleep(2 ** i)
    raise RuntimeError(f"TTS failed after {attempts} attempts: {last}")


def silence(path: Path, seconds: float) -> None:
    ffmpeg(
        "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
        "-t", f"{seconds:.2f}", "-q:a", "9", "-acodec", "libmp3lame", str(path),
    )


def concat(parts: list[Path], out: Path) -> None:
    """Concatenate MP3 parts by re-encoding (robust across sample sizes)."""
    listfile = out.with_suffix(".txt")
    # .as_posix() keeps forward slashes so the concat demuxer parses the list
    # correctly on Windows too (backslashes would break it).
    listfile.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in parts))
    ffmpeg("-f", "concat", "-safe", "0", "-i", str(listfile),
           "-acodec", "libmp3lame", "-q:a", "4", str(out))
    listfile.unlink(missing_ok=True)


def split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


async def build_lecture(cid: str, title: str, lecture_txt: Path, out: Path) -> None:
    paras = split_paragraphs(lecture_txt.read_text(encoding="utf-8"))
    intro = f"Chapter study lecture. {title}."
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        parts: list[Path] = []
        seg = tmp / "intro.mp3"
        await say(intro, seg, NARRATOR, LECTURE_RATE)
        parts.append(seg)
        gap = tmp / "gap.mp3"          # one fixed-length silence, reused between paragraphs
        silence(gap, 0.6)
        for i, para in enumerate(paras):
            seg = tmp / f"p{i:03d}.mp3"
            await say(para, seg, NARRATOR, LECTURE_RATE)
            parts.append(seg)
            parts.append(gap)
        concat(parts, out)


async def build_drill(cid: str, title: str, pack_json: Path, out: Path,
                      answer_gap: float = 4.0) -> None:
    data = json.loads(pack_json.read_text(encoding="utf-8"))
    qa = data.get("qa", [])
    intro = (f"Active recall drill. {title}. "
             f"After each question, pause and answer aloud, then check yourself.")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        parts: list[Path] = []
        seg = tmp / "intro.mp3"
        await say(intro, seg, NARRATOR, LECTURE_RATE)
        parts.append(seg)
        pre = tmp / "pre.mp3"
        silence(pre, 0.8)
        parts.append(pre)
        gap = tmp / "gap.mp3"          # the answer-thinking gap, reused each question
        silence(gap, answer_gap)
        between = tmp / "between.mp3"  # spacer before the next question
        silence(between, 1.0)
        for i, item in enumerate(qa):
            if not isinstance(item, dict):
                continue
            q, a = item.get("q", "").strip(), item.get("a", "").strip()
            if not q or not a:
                continue
            qseg = tmp / f"q{i:03d}.mp3"
            await say(f"Question {i + 1}. {q}", qseg, NARRATOR, LECTURE_RATE)
            parts.append(qseg)
            parts.append(gap)
            aseg = tmp / f"a{i:03d}.mp3"
            await say(f"The answer is: {a}", aseg, ANSWERER, LECTURE_RATE)
            parts.append(aseg)
            parts.append(between)
        concat(parts, out)


async def build_terms(cid: str, title: str, pack_json: Path, out: Path) -> None:
    data = json.loads(pack_json.read_text(encoding="utf-8"))
    terms = data.get("key_terms", [])
    intro = f"Key terms review. {title}."
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        parts: list[Path] = []
        seg = tmp / "intro.mp3"
        await say(intro, seg, NARRATOR, LECTURE_RATE)
        parts.append(seg)
        gap = tmp / "gap.mp3"          # term -> definition pause, reused
        silence(gap, 1.5)
        between = tmp / "between.mp3"  # spacer before the next term
        silence(between, 0.9)
        for i, item in enumerate(terms):
            if not isinstance(item, dict):
                continue
            term, defn = item.get("term", "").strip(), item.get("definition", "").strip()
            if not term or not defn:
                continue
            tseg = tmp / f"t{i:03d}.mp3"
            await say(f"{term}.", tseg, NARRATOR, LECTURE_RATE)
            parts.append(tseg)
            parts.append(gap)
            dseg = tmp / f"d{i:03d}.mp3"
            await say(defn, dseg, ANSWERER, LECTURE_RATE)
            parts.append(dseg)
            parts.append(between)
        concat(parts, out)


BUILDERS = {"lecture": build_lecture, "drill": build_drill, "terms": build_terms}
SOURCE = {  # which generated artifact each kind needs
    "lecture": ("lectures", ".txt"),
    "drill": ("studypacks", ".json"),
    "terms": ("studypacks", ".json"),
}


async def main_async(args: argparse.Namespace) -> int:
    book = json.loads((args.build / "book.json").read_text(encoding="utf-8"))
    wanted = {int(x) for x in args.only.split(",") if x.strip()} if args.only else None
    kinds = [k.strip() for k in args.kinds.split(",") if k.strip()]
    audio_dir = args.build / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    failures = 0
    for ch in book["chapters"]:
        if wanted and ch["num"] not in wanted:
            continue
        cid, title = ch["id"], ch["title"]
        for kind in kinds:
            subdir, ext = SOURCE[kind]
            src = args.build / subdir / f"{cid}{ext}"
            if not src.exists():
                print(f"[{cid}] {kind}: source missing ({src.name}), skip", file=sys.stderr)
                continue
            out = audio_dir / f"{cid}-{kind}.mp3"
            if args.skip_existing and out.exists() and out.stat().st_size > 0:
                print(f"[{cid}] {kind}: skip (exists)")
                continue
            try:
                print(f"[{cid}] {kind}: synthesizing...", flush=True)
                await BUILDERS[kind](cid, title, src, out)
                print(f"[{cid}] {kind}: {out.stat().st_size:,} bytes")
            except Exception as e:  # noqa: BLE001
                failures += 1
                print(f"[{cid}] {kind}: FAILED - {e}", file=sys.stderr)
    return 1 if failures else 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--build", default=Path("build"), type=Path)
    ap.add_argument("--only", default="", help="comma-separated chapter numbers")
    ap.add_argument("--kinds", default="lecture,drill,terms")
    ap.add_argument("--skip-existing", action="store_true")
    args = ap.parse_args()
    sys.exit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
