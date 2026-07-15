# CIPP/US audio-first study pipeline
#
#   make setup      install Python deps + check for ffmpeg/claude
#   make extract    EPUB -> per-chapter markdown  (needs EPUB=path)
#   make combine    per-chapter markdown -> one full-book markdown
#   make generate   chapters -> lecture scripts + study packs (Claude CLI)
#   make audio      scripts/packs -> narrated MP3s + playlists (edge-tts)
#   make cards      chapters -> US-regulation fact cards (Claude CLI)
#   make cards-from-deck  recover cards.json from the committed .apkg (no EPUB)
#   make anki       cards -> Anki .apkg deck with Q&A TTS audio (genanki + edge-tts)
#   make all        extract + combine + generate + audio + playlist
#   make ONLY=1 ...  restrict generate/audio/cards to chapter 1 (comma-sep list)
#
# System deps: ffmpeg (audio assembly) and the `claude` CLI (generation).

EPUB   ?= source/book.epub
BUILD  ?= build
KINDS  ?= lecture,drill,terms
ONLY   ?=
TITLE  ?= U.S. Private-Sector Privacy (4th ed.)
PY     ?= python3

ONLYFLAG := $(if $(ONLY),--only $(ONLY),)

DECK   ?= decks/cipp-us-regulations.apkg

.PHONY: all setup extract combine generate audio playlist cards cards-from-deck anki clean distclean

all: extract combine generate audio playlist

setup:
	$(PY) -m pip install -r requirements.txt
	@command -v ffmpeg >/dev/null || { echo "ERROR: ffmpeg not found"; exit 1; }
	@command -v ffprobe >/dev/null || { echo "ERROR: ffprobe not found (needed by playlist.py)"; exit 1; }
	@command -v claude >/dev/null || { echo "ERROR: claude CLI not found"; exit 1; }
	@echo "setup ok"

extract:
	$(PY) pipeline/extract.py --epub $(EPUB) --out $(BUILD)

combine:
	$(PY) pipeline/combine.py --build $(BUILD) --title "$(TITLE)"

generate:
	$(PY) pipeline/generate.py --build $(BUILD) $(ONLYFLAG) --skip-existing

audio:
	$(PY) pipeline/tts.py --build $(BUILD) --kinds $(KINDS) $(ONLYFLAG) --skip-existing

playlist:
	$(PY) pipeline/playlist.py --build $(BUILD)

cards:
	$(PY) pipeline/cards.py --build $(BUILD) $(ONLYFLAG) --skip-existing

cards-from-deck:
	$(PY) pipeline/apkg_to_cards.py --apkg $(DECK) --build $(BUILD)

anki:
	$(PY) pipeline/build_anki.py --build $(BUILD)

clean:          ## remove generated audio only
	rm -rf $(BUILD)/audio

distclean:      ## remove the whole build tree
	rm -rf $(BUILD)
