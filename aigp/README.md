# AIGP Practice-Exam Audio Drill

An audio-first study track for the IAPP **AIGP** (Artificial Intelligence
Governance Professional) certification, built from the purchased **IAPP AIGP
Practice Exam** (v2.0, body of knowledge 2.1 — 100 items). Same audio-first
style as the CIPP/US track: a two-voice drill you can run hands-free, eyes
closed.

```
AIGP Practice Exam (PDF text) ──exam_extract.py──▶ build/exam/questions.json
                                                       └─exam_audio.py─▶ build/exam/audio/*.mp3  (two-voice drill, 7 parts + m3u)
                                                       └─exam_anki.py──▶ decks/aigp-practice-exam.apkg  (1 card/question, audio both sides)
```

## Pipeline

- **`exam_extract.py`** — parses the exam's plain-text dump
  (`build/exam/exam-raw.txt`, kept out of git) into
  `build/exam/questions.json`: stem, options, correct answer, official
  rationale, domain and competency for all 100 items. Answers come from the item
  rationales and are cross-checked against the answer-key table. Handles the two
  special items — the ordering question (Q22) and the select-all question (Q82),
  which carry a 5th option.
- **`exam_audio.py`** — a two-voice drill of all 100 questions: Andrew asks the
  question + options, a **6-second silent gap** to answer aloud, then Ava gives
  the answer + rationale. Split into parts (15 questions each) with an M3U
  playlist and a listening guide. ~2.5 hours total.
- **`exam_anki.py`** — an `.apkg` with one card per question (stem + options on
  the front, correct answer + rationale on the back), audio on both sides.
  Fixed deck/model IDs and per-question stable GUIDs, so re-import updates cards
  in place.

## Usage

```bash
# 1. Put the exam text at build/exam/exam-raw.txt (from the purchased PDF; not committed)
python3 pipeline/exam_extract.py build/exam/exam-raw.txt build/exam/questions.json

# 2. Two-voice audio drill -> build/exam/audio/
python3 pipeline/exam_audio.py build/exam/audio

# 3. (optional) Anki deck with audio both sides
python3 pipeline/exam_anki.py build/exam/questions.json decks/aigp-practice-exam.apkg
```

## Notes

- The 4 answer-key domains (I–IV, weighted 22/27/24/27 of the 100 items) are
  recorded per question as `domain` + `subdomain` (competency). The practice
  exam does not spell out domain names, so only the roman numeral + competency
  letter are stored.
- **edge-tts** stalls intermittently on the neural-voice endpoint; the audio
  scripts synthesize sequentially with short per-call timeouts, split every clip
  into ≤240-char sentence chunks, and retry with a cooldown, assembling with
  ffmpeg only after the network phase. This drill built with **0 failures**.
- **Copyright**: the AIGP Practice Exam is a purchased IAPP publication. The
  extracted text, `questions.json`, and full audio stay out of git — this is a
  study aid, not an authority. Verify anything exam-critical against IAPP's
  materials.
