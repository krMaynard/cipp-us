#!/usr/bin/env python3
"""Build an Anki .apkg deck of U.S.-regulation facts, with TTS audio embedded.

Reads build/cards.json (from cards.py) and produces build/cipp-us-regulations.apkg:
one structured "US Reg" note per regulation, from which Anki generates up to four
targeted cards — Scenario -> Law, Acronym -> Name+Year, Law -> Year+Citation,
Law -> Enforcer.

Audio-first, both sides. Each card autoplays the QUESTION aloud on the front
(a narrator voice) and the ANSWER aloud on the back (a second voice) — so the
deck can be drilled hands-free, eyes closed, the same way the lecture/drill
tracks are. Acronyms are spelled out both times so the name/date cements
aurally. The two voices (narrator = question, answerer = answer) let your ear
tell prompt from answer without looking.

Deck + model IDs are fixed. Each note's GUID comes from its cards.json "guid"
field if present, else is derived from its slug — so re-importing an updated
deck UPDATES cards in place instead of duplicating them (your review scheduling
is preserved).

Usage:
    python pipeline/build_anki.py --build build
    python pipeline/build_anki.py --build build --no-audio   # skip all TTS
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import tempfile
from pathlib import Path


# --- edge-tts must trust the agent proxy's TLS interception (see tts.py) ------
def _trust_proxy_ca() -> None:
    ca = Path("/root/.ccr/ca-bundle.crt")
    if not ca.exists():
        return
    try:
        import certifi
        bundle = Path(certifi.where())
        if ca.read_text() not in bundle.read_text():
            with bundle.open("a") as fh:
                fh.write("\n" + ca.read_text())
    except Exception:  # noqa: BLE001
        pass


_trust_proxy_ca()

import genanki  # noqa: E402

# Fixed IDs — do NOT change once the deck is in use (Anki keys scheduling to them).
MODEL_ID = 1841027431
DECK_ID = 1841027432
# Two voices, matching the lecture/drill tracks (see tts.py): the narrator asks
# (front), the answerer answers (back), so your ear tells prompt from answer.
QUESTION_VOICE = "en-US-AndrewMultilingualNeural"   # spoken question (front)
ANSWER_VOICE = "en-US-AvaMultilingualNeural"        # spoken answer   (back)
VOICE = ANSWER_VOICE  # back-compat alias

CSS = """
.card { font-family: -apple-system, system-ui, "Segoe UI", Roboto, sans-serif;
  font-size: 19px; line-height: 1.5; color: #1b2333; background: #f6f4ee;
  text-align: left; padding: 18px 20px; }
.nightMode.card { color: #eef1f6; background: #141821; }
.cue { font-size: 12px; letter-spacing: .12em; text-transform: uppercase;
  color: #8c2f28; font-weight: 700; margin-bottom: 10px; }
.nightMode .cue { color: #e07a70; }
.scenario { font-size: 21px; line-height: 1.45; }
.acr { font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 34px;
  font-weight: 700; letter-spacing: .04em; }
.law { font-size: 24px; font-weight: 700; font-family: Georgia, "Times New Roman", serif; }
hr { border: 0; border-top: 1px solid #d8d2c4; margin: 16px 0; }
.nightMode hr { border-top-color: #2c3444; }
.ans { font-size: 26px; font-weight: 700; font-family: Georgia, serif; margin-bottom: 4px; }
.ans .yr { color: #8c2f28; }
.nightMode .ans .yr { color: #e07a70; }
.cite { font-family: ui-monospace, Menlo, monospace; font-size: 15px;
  background: #f0e2df; color: #8c2f28; padding: 2px 7px; border-radius: 4px;
  display: inline-block; margin: 4px 0; }
.nightMode .cite { background: #3a2422; color: #e07a70; }
.facts { margin-top: 12px; font-size: 15px; }
.facts b { font-family: ui-monospace, Menlo, monospace; font-size: 11px;
  letter-spacing: .06em; text-transform: uppercase; color: #5d6675;
  display: inline-block; min-width: 74px; }
.nightMode .facts b { color: #8d97a7; }
.audio { margin-top: 10px; }
.qaudio { margin: 14px 0 2px; }
"""

# Shared answer detail shown on every card back.
_FACTS = """
<div class="facts">
  {{#Scope}}<div><b>Covers</b> {{Scope}}</div>{{/Scope}}
  {{#Trigger}}<div><b>Trigger</b> {{Trigger}}</div>{{/Trigger}}
  {{#Enforcer}}<div><b>Enforcer</b> {{Enforcer}}</div>{{/Enforcer}}
  {{#KeyFacts}}<div><b>Key fact</b> {{KeyFacts}}</div>{{/KeyFacts}}
</div>
{{#Audio}}<div class="audio">{{Audio}}</div>{{/Audio}}
<div class="facts"><b>Chapter</b> {{Chapter}}</div>
"""

_ANS_HEAD = (
    '<div class="ans">{{Law}} <span style="color:#5d6675">({{Acronym}})</span>'
    ' &middot; <span class="yr">{{Year}}</span></div>'
    '{{#Citation}}<div class="cite">{{Citation}}</div>{{/Citation}}'
)

MODEL = genanki.Model(
    MODEL_ID,
    "CIPP/US — US Regulation",
    fields=[
        {"name": "Law"}, {"name": "Acronym"}, {"name": "Year"}, {"name": "Citation"},
        {"name": "Scope"}, {"name": "Trigger"}, {"name": "Enforcer"},
        {"name": "KeyFacts"}, {"name": "Scenario"}, {"name": "Audio"}, {"name": "Chapter"},
        # Per-template spoken-question clips (front), one voice each (see synth_all).
        {"name": "QAudioScenario"}, {"name": "QAudioAcronym"},
        {"name": "QAudioCite"}, {"name": "QAudioEnf"},
    ],
    templates=[
        {
            "name": "1. Scenario -> Law",
            "qfmt": '{{#Scenario}}<div class="cue">Which U.S. regulation applies?</div>'
                    '<div class="scenario">{{Scenario}}</div>'
                    '{{#QAudioScenario}}<div class="qaudio">{{QAudioScenario}}</div>{{/QAudioScenario}}'
                    '{{/Scenario}}',
            "afmt": '{{FrontSide}}<hr>' + _ANS_HEAD + _FACTS,
        },
        {
            "name": "2. Acronym -> Name & Year",
            "qfmt": '{{#Acronym}}<div class="cue">Full name &amp; year enacted?</div>'
                    '<div class="acr">{{Acronym}}</div>'
                    '{{#QAudioAcronym}}<div class="qaudio">{{QAudioAcronym}}</div>{{/QAudioAcronym}}'
                    '{{/Acronym}}',
            "afmt": '{{FrontSide}}<hr>' + _ANS_HEAD + _FACTS,
        },
        {
            "name": "3. Law -> Year & Citation",
            "qfmt": '{{#Citation}}<div class="cue">Year enacted &amp; citation?</div>'
                    '<div class="law">{{Law}} ({{Acronym}})</div>'
                    '{{#QAudioCite}}<div class="qaudio">{{QAudioCite}}</div>{{/QAudioCite}}'
                    '{{/Citation}}',
            "afmt": '{{FrontSide}}<hr>'
                    '<div class="ans"><span class="yr">{{Year}}</span></div>'
                    '<div class="cite">{{Citation}}</div>' + _FACTS,
        },
        {
            "name": "4. Law -> Enforcer",
            "qfmt": '{{#Enforcer}}<div class="cue">Who enforces it?</div>'
                    '<div class="law">{{Law}} ({{Acronym}})</div>'
                    '{{#QAudioEnf}}<div class="qaudio">{{QAudioEnf}}</div>{{/QAudioEnf}}'
                    '{{/Enforcer}}',
            "afmt": '{{FrontSide}}<hr><div class="ans">{{Enforcer}}</div>' + _FACTS,
        },
    ],
    css=CSS,
)


def _g(it: dict, key: str) -> str:
    """Coerce a card field to a clean string. `it.get(k) or ""` (not a ""
    default) so a missing key, a JSON null, or a non-string can't raise or leak
    the literal "None"."""
    return str(it.get(key) or "").strip()


def _spell(acr: str, law: str = "") -> str:
    """Spell an acronym as letters ("F. C. R. A.") so it cements aurally; leave a
    genuine short word alone. Returns "" if the acronym just echoes the law name."""
    acr = acr.strip()
    if not acr or acr.upper() == law.strip().upper():
        return ""
    bare = acr.replace(".", "")
    return ". ".join(bare) if bare.isupper() or len(bare) <= 6 else acr


def spoken(it: dict) -> str:
    """Build the spoken-ANSWER line; spell acronyms so the name cements aurally."""
    law = _g(it, "law")
    parts = [law + "."] if law else []
    letters = _spell(_g(it, "acronym"), law)
    if letters:
        parts.append(letters + ".")
    year = _g(it, "year")
    if year:
        parts.append(f"Enacted {year}.")
    citation = _g(it, "citation")
    if citation:
        cite = citation.replace("§§", "Sections ").replace("§", "Section ")
        parts.append(cite + ".")
    enforcer = _g(it, "enforcer")
    if enforcer:
        parts.append("Enforced by " + enforcer)
    return " ".join(parts)


def spoken_questions(it: dict) -> dict[str, str]:
    """Build the spoken-QUESTION line for each card this note will generate.

    Keyed by the same suffixes as the QAudio* fields. A key is present only when
    its card renders (mirrors the {{#Scenario}}/{{#Acronym}}/{{#Citation}}/
    {{#Enforcer}} template conditionals) so we never synthesize an orphan clip.
    Questions are self-contained — you can answer with your eyes closed."""
    q: dict[str, str] = {}
    law = _g(it, "law")
    letters = _spell(_g(it, "acronym"), law)
    spoken_law = f"{law}, {letters}" if (law and letters) else (law or letters)

    scenario = _g(it, "scenario")
    if scenario:
        q["scenario"] = f"Which U.S. regulation applies? {scenario}"
    if letters:
        q["acronym"] = f"What is the full name, and year enacted, of the law abbreviated {letters}?"
    if _g(it, "citation") and spoken_law:
        q["cite"] = f"For the {spoken_law}, what year was it enacted, and what is its statutory citation?"
    if _g(it, "enforcer") and spoken_law:
        q["enf"] = f"Who enforces the {spoken_law}?"
    return q


async def synth_all(items: list[dict], media_dir: Path,
                    concurrency: int = 6) -> dict[str, dict[str, str]]:
    """Synthesize every clip (one answer + up to four questions per note)
    concurrently but bounded, retrying transient failures. Returns
    {slug: {"answer": fname, "scenario": fname, ...}} with only the clips that
    succeeded. A semaphore keeps the edge-tts endpoint from being hammered while
    still overlapping the waits."""
    import edge_tts
    audio: dict[str, dict[str, str]] = {}
    sem = asyncio.Semaphore(concurrency)

    async def synth_clip(slug: str, kind: str, text: str, voice: str) -> None:
        # kind is "answer" or a question suffix; keep the answer filename exactly
        # as before (usreg_<slug>.mp3) so re-imports reuse media unchanged.
        base = "usreg_" + re.sub(r"[^A-Za-z0-9_]", "_", slug)
        fname = f"{base}.mp3" if kind == "answer" else f"{base}_q_{kind}.mp3"
        path = media_dir / fname
        async with sem:
            for attempt in range(4):
                try:
                    path.unlink(missing_ok=True)  # never treat a stale/partial file as success
                    await edge_tts.Communicate(text, voice, rate="-4%").save(str(path))
                    if path.exists() and path.stat().st_size > 0:
                        audio.setdefault(slug, {})[kind] = fname
                        return
                    raise RuntimeError("empty audio")
                except Exception as e:  # noqa: BLE001
                    if attempt == 3:
                        print(f"    audio FAILED for {slug} [{kind}]: {e}", file=sys.stderr)
                        return
                    await asyncio.sleep(2 ** attempt)

    tasks = []
    for it in items:
        slug = it["slug"]
        tasks.append(synth_clip(slug, "answer", spoken(it), ANSWER_VOICE))
        for kind, text in spoken_questions(it).items():
            tasks.append(synth_clip(slug, kind, text, QUESTION_VOICE))
    await asyncio.gather(*tasks)
    return audio


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--build", default=Path("build"), type=Path)
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    items = json.loads((args.build / "cards.json").read_text(encoding="utf-8"))
    if not items:
        raise SystemExit("no cards in build/cards.json — run cards.py first")

    def snd(fname: str) -> str:
        return f"[sound:{fname}]" if fname else ""

    with tempfile.TemporaryDirectory() as td:
        media_dir = Path(td)
        audio_map: dict[str, dict[str, str]] = {}
        if not args.no_audio:
            nq = sum(len(spoken_questions(it)) for it in items)
            print(f"Synthesizing {len(items)} answer + {nq} question clips...", flush=True)
            audio_map = asyncio.run(synth_all(items, media_dir))
            print(f"    {sum(len(v) for v in audio_map.values())} clips ok")

        deck = genanki.Deck(DECK_ID, "CIPP/US · U.S. Regulations (names, dates, citations)")
        media_files: list[str] = []
        for it in items:
            clips = audio_map.get(it["slug"], {})
            # Preserve an existing GUID verbatim (keeps scheduling stable on
            # re-import); fall back to slug-derived when cards.json has none.
            guid = it.get("guid") or genanki.guid_for(it["slug"])
            deck.add_note(genanki.Note(
                model=MODEL,
                guid=guid,
                fields=[
                    it.get("law", ""), it.get("acronym", ""), it.get("year", ""),
                    it.get("citation", ""), it.get("scope", ""), it.get("trigger", ""),
                    it.get("enforcer", ""), it.get("key_facts", ""), it.get("scenario", ""),
                    snd(clips.get("answer", "")), str(it.get("chapter", "")),
                    snd(clips.get("scenario", "")), snd(clips.get("acronym", "")),
                    snd(clips.get("cite", "")), snd(clips.get("enf", "")),
                ],
            ))
            media_files.extend(str(media_dir / f) for f in clips.values())

        out = Path(args.out) if args.out else args.build / "cipp-us-regulations.apkg"
        genanki.Package(deck, media_files=media_files).write_to_file(str(out))
        print(f"Wrote {out}  ({len(items)} notes, {len(media_files)} audio clips)")


if __name__ == "__main__":
    main()
