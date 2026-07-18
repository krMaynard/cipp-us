# CIPP/US Audio-First Study Pipeline

A small pipeline that turns the IAPP **CIPP/US** study textbook (an EPUB) into
**study materials optimized for auditory learning** — spoken lectures, spoken
key-term reviews, and hands-free active-recall drills you can listen to while
walking, driving, or commuting.

The emphasis is deliberately on **listening, not reading**: every artifact is
built to be consumed with your eyes closed.

## What it produces (per chapter)

| Track | What it is | How to use it |
|-------|------------|---------------|
| **Lecture** (`chNN-lecture.mp3`) | A ~15-minute spoken walkthrough written for the ear — no bullet lists, heavy signposting, built-in "Quick recap" checkpoints, and a closing 60-second summary. | First pass. Listen once or twice per chapter. |
| **Key Terms** (`chNN-terms.mp3`) | "Term … *pause* … definition" in two voices. | Vocabulary reinforcement. |
| **Recall Drill** (`chNN-drill.mp3`) | A question in one voice, a **4-second silent gap** to answer aloud, then "The answer is…" in a second voice. | Last, and repeatedly — this is where exam recall is built. |

Plus text sources for each (`build/lectures/*.txt`, `build/studypacks/*.json`),
M3U playlists, and a listening guide with durations (`build/audio/README.md`).

Two voices are used throughout (`en-US-AndrewMultilingualNeural` for
narration/questions, `en-US-AvaMultilingualNeural` for answers/definitions) so
your ear can tell "prompt" from "answer" without looking.

## Pipeline stages

```
 EPUB ──extract.py──▶ chapters/*.md ──generate.py──▶ lectures/*.txt
                                          │            studypacks/*.json
                                          └──tts.py──▶ audio/*.mp3 ──playlist.py──▶ *.m3u + guide
```

1. **`extract.py`** — reads the EPUB as a zip, converts each `Chapter_N.xhtml`
   into clean markdown, writes `build/book.json`.
2. **`generate.py`** — for each chapter, calls the headless `claude -p` CLI with
   the prompts in `prompts/` to produce an audio-lecture script and a
   `{key_terms, qa}` study pack (JSON-validated).
3. **`tts.py`** — synthesizes narrated MP3s with `edge-tts`, assembling
   segments and silent gaps with `ffmpeg`.
4. **`playlist.py`** — writes M3U playlists and a listening guide.

## Usage

```bash
cd exam-study
make setup                       # install deps; checks ffmpeg + claude CLI

# put the textbook at source/book.epub (not committed), then:
make all EPUB=source/book.epub   # extract + generate + audio + playlists

# iterate on a single chapter while tuning prompts/voices:
make generate ONLY=1
make audio    ONLY=1 KINDS=drill
```

Outputs land in `build/` (git-ignored). A committed `samples/` folder holds a
few tracks and text artifacts so the pipeline's output is reviewable without
regenerating everything.

## One-page master sheet

`cheatsheet.html` is a self-contained, print-ready quick-reference distilled
from the generated study packs — the four analysis lenses, the core federal
sector laws (scope / trigger / enforcer each), state + international
essentials, and the commonly-confused pairs and exam traps. Open it in a
browser; `Cmd/Ctrl-P` prints a compact reference. Light/dark aware.

## Anki regulations deck (rote recall)

For the facts you can't reason your way to — exact law **names, acronyms, years,
citations, and enforcers** — a separate track builds a spaced-repetition deck:

```
chapters ──cards.py──▶ build/cards.json ──build_anki.py──▶ build/cipp-us-regulations.apkg
```

- **`cards.py`** — asks `claude -p` to pull, from each chapter, every specifically
  named U.S. law/rule/case that has a memorizable name **and** a hard fact,
  as `{law, acronym, year, citation, scope, trigger, enforcer, key_facts,
  scenario}`. Merged and de-duplicated by slug into `build/cards.json`.
- **`build_anki.py`** — builds a `.apkg` (via `genanki`) with one structured
  **"US Reg"** note per regulation. Anki generates up to **four cards** from each:

  1. **Scenario → Law** — a plain fact-pattern on the front, "which U.S. law?" —
     mirrors how the exam asks (you reason the concept; the card drills the name).
  2. **Acronym → Full name + year.**
  3. **Law → Year & Citation** (only if a citation exists — the template skips
     otherwise, so no blank cards).
  4. **Law → Enforcer** (+ private-right-of-action).

  Every card is **audio-first on both sides** (edge-tts, acronyms spelled out):
  the **question** is read aloud on the front in a narrator voice
  (`en-US-AndrewMultilingualNeural`) and the **answer** on the back in a second
  voice (`en-US-AvaMultilingualNeural`) — so you can drill hands-free, eyes
  closed, and your ear tells prompt from answer. Each of the four card types gets
  its own spoken question (the scenario, the spelled-out acronym, or the law
  name), and on flip Anki replays the question and then speaks the answer — a
  natural Q → A drill. Deck/model IDs are fixed and each note's GUID is preserved,
  so re-importing an updated deck **updates cards in place** instead of
  duplicating them — your review scheduling survives a re-generate.

Build it with `make cards && make anki` (or `make cards ONLY=8` for one chapter),
then double-click the `.apkg` to import. Cards are tagged by chapter.

A **pre-built deck is committed** at `decks/cipp-us-regulations.apkg` (175
regulations → 508 cards, every card spoken on both sides) so you can import
without running the pipeline. Because the deck/model IDs are fixed and GUIDs are
preserved, re-importing a freshly built deck updates those cards in place and
keeps your review scheduling.

**Regenerating the committed deck without the textbook.** The card facts live in
the deck itself, so you can rebuild it (e.g. after a template or audio change)
straight from the `.apkg` — no EPUB required:

```bash
make cards-from-deck    # decks/*.apkg -> build/cards.json (GUIDs preserved)
make anki               # build/cards.json -> build/cipp-us-regulations.apkg
```

## Requirements

- **Python 3.11+** with the packages in `requirements.txt`
  (`beautifulsoup4`, `lxml`, `edge-tts`, `genanki`).
- **ffmpeg** on `PATH` (audio assembly).
- The **`claude` CLI**, authenticated (generation). No API key handling lives in
  the code — it shells out to `claude -p`.
- Network access for `edge-tts` (Microsoft neural voices). Behind the agent
  proxy, `tts.py` appends the proxy CA bundle to `certifi` automatically.

## Notes

- **Model id**: generation uses `claude-opus-4-8`, set in `pipeline/generate.py`.
  Per repo policy, confirm the current model id before changing it.
- **Copyright**: the textbook is a purchased IAPP publication. Keep the source
  EPUB and full generated audio out of version control (see `.gitignore`); the
  committed `samples/` are short excerpts for demonstrating the pipeline.
- **Grounding**: prompts instruct the model to teach only from the chapter text
  and not invent statutes, dates, or thresholds. Still, verify anything
  exam-critical against the book — this is a study aid, not an authority.
