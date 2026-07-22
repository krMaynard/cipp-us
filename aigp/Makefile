# AIGP practice-exam audio-first study pipeline
#
#   make exam-extract   exam text -> build/exam/questions.json
#   make exam-audio      questions.json -> two-voice drill MP3s + m3u
#   make exam-anki       questions.json -> Anki .apkg (audio both sides)
#   make exam            extract + audio + anki
#
# ffmpeg is bundled via imageio-ffmpeg; only edge-tts needs network.

PY      ?= python3
RAW     ?= build/exam/exam-raw.txt
QS      ?= build/exam/questions.json
AUDIO   ?= build/exam/audio
DECK    ?= decks/aigp-practice-exam.apkg

.PHONY: exam exam-extract exam-audio exam-anki setup

setup:
	$(PY) -m pip install -r requirements.txt

exam-extract:
	$(PY) pipeline/exam_extract.py $(RAW) $(QS)

exam-audio:
	$(PY) pipeline/exam_audio.py $(AUDIO)

exam-anki:
	$(PY) pipeline/exam_anki.py $(QS) $(DECK)

exam: exam-extract exam-audio exam-anki
