# Sample output — Chapter 1

These are committed so the pipeline's output is reviewable without regenerating
everything (the full `build/` tree is git-ignored). All of it was produced by
the pipeline in this folder from the IAPP CIPP/US textbook.

| File | Stage | What it is |
|------|-------|------------|
| `ch01-lecture.txt` | `generate.py` | The ~2,500-word spoken lecture script (Claude). |
| `ch01-studypack.json` | `generate.py` | `{key_terms, qa}` — 20 terms + 31 recall Q&A. |
| `audio/ch01-lecture.mp3` | `tts.py` | 19:27 narrated lecture. |
| `audio/ch01-terms.mp3` | `tts.py` | 5:51 "term … definition" glossary. |
| `audio/ch01-drill.mp3` | `tts.py` | Recall drill: question → 4-second gap → answer, two voices. |

To regenerate for every chapter, see the top-level `README.md` and run `make all`.
