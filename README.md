# IAPP Certification Study — Audio-First Study Pipelines

Study materials for IAPP certifications, optimized for **auditory learning** —
spoken lectures, key-term reviews, and hands-free active-recall drills you can
listen to while walking, driving, or commuting. Two neural voices are used
throughout so your ear can tell "prompt" from "answer" without looking.

Each certification lives in its own subdirectory with its own pipeline, build
tree, and prebuilt decks.

| Cert | Directory | What's there |
|------|-----------|--------------|
| **CIPP/US** — Certified Information Privacy Professional / US | [`cipp-us/`](cipp-us/) | Textbook lecture/terms/drill audio, a US-regulations Anki deck, a practice-exam Anki deck, a two-day cram pack, and a 90-item practice-exam audio drill. |
| **AIGP** — Artificial Intelligence Governance Professional | [`aigp/`](aigp/) | A 100-item practice-exam audio drill (two-voice), built from the IAPP AIGP Practice Exam. |

## Shared conventions

- **Two voices**: `en-US-AndrewMultilingualNeural` narrates/asks,
  `en-US-AvaMultilingualNeural` answers/defines.
- **Audio drill**: narrator asks a question + its options, a silent gap to
  answer aloud, then the second voice gives the answer + rationale.
- **edge-tts** synthesizes the audio (sequential, chunked, with retries — the
  neural endpoint stalls intermittently); **ffmpeg** assembles the clips.
- **Copyright**: the source materials are purchased IAPP publications. Extracted
  exam text, the derived `questions.json`, and the full generated audio stay out
  of git (`build/` is git-ignored). These pipelines are study aids — verify
  anything exam-critical against the official IAPP materials.

## Requirements

Python 3.11+ with the packages in each cert's `requirements.txt`
(`edge-tts`, `imageio-ffmpeg`, `genanki`, plus extraction deps), and the
authenticated `claude` CLI for the text-generation stages. `ffmpeg` is bundled
via `imageio-ffmpeg`; no system install needed for the audio drills.
