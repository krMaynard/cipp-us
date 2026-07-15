#!/usr/bin/env python3
"""Write a listening guide + M3U playlists over the generated audio.

Emits, under build/audio/:
  - playlist-all.m3u        every track, chapter order (lecture, terms, drill)
  - playlist-lectures.m3u   just the lectures
  - playlist-drills.m3u     just the recall drills
  - README.md               human listening guide with durations

Durations are read from each MP3 via ffprobe.

Usage:
    python pipeline/playlist.py --build build
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

ORDER = ["lecture", "terms", "drill"]
LABEL = {"lecture": "Lecture", "terms": "Key Terms", "drill": "Recall Drill"}


def duration(path: Path) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nokey=1:noprint_wrappers=1", str(path)],
            capture_output=True, text=True, check=True,
        )
        return float(out.stdout.strip())
    except Exception:  # noqa: BLE001
        return 0.0


def hhmmss(seconds: float) -> str:
    s = int(round(seconds))
    return f"{s // 60}:{s % 60:02d}"


def m3u(tracks: list[tuple[str, float, Path]], out: Path) -> None:
    lines = ["#EXTM3U"]
    for title, dur, path in tracks:
        lines.append(f"#EXTINF:{int(round(dur))},{title}")
        lines.append(path.name)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--build", default=Path("build"), type=Path)
    args = ap.parse_args()

    book = json.loads((args.build / "book.json").read_text(encoding="utf-8"))
    audio = args.build / "audio"
    audio.mkdir(parents=True, exist_ok=True)  # self-contained if run before/without audio

    all_tracks: list[tuple[str, float, Path]] = []
    by_kind: dict[str, list[tuple[str, float, Path]]] = {k: [] for k in ORDER}
    rows: list[str] = []
    grand = 0.0

    for ch in book["chapters"]:
        cid, title = ch["id"], ch["title"]
        for kind in ORDER:
            path = audio / f"{cid}-{kind}.mp3"
            if not path.exists():
                continue
            dur = duration(path)
            grand += dur
            label = f"{title} — {LABEL[kind]}"
            all_tracks.append((label, dur, path))
            by_kind[kind].append((label, dur, path))
            rows.append(f"| {ch['num']} | {title} | {LABEL[kind]} | {hhmmss(dur)} | `{path.name}` |")

    m3u(all_tracks, audio / "playlist-all.m3u")
    m3u(by_kind["lecture"], audio / "playlist-lectures.m3u")
    m3u(by_kind["drill"], audio / "playlist-drills.m3u")

    guide = [
        "# CIPP/US Audio Study — Listening Guide",
        "",
        f"Generated from **{book['source']}** — {len(book['chapters'])} chapters, "
        f"**{hhmmss(grand)}** of audio total.",
        "",
        "Three track types per chapter, designed for hands-free (auditory) study:",
        "",
        "- **Lecture** — a spoken walkthrough of the chapter. Listen first.",
        "- **Key Terms** — term, pause, definition. Reinforces vocabulary.",
        "- **Recall Drill** — a question, a 4-second gap to answer aloud, then the answer. Do this last, repeatedly.",
        "",
        "Playlists (open in any audio player): `playlist-all.m3u`, "
        "`playlist-lectures.m3u`, `playlist-drills.m3u`.",
        "",
        "| Ch | Title | Track | Length | File |",
        "|----|-------|-------|--------|------|",
        *rows,
        "",
    ]
    (audio / "README.md").write_text("\n".join(guide), encoding="utf-8")
    print(f"Playlists + guide written to {audio}  ({hhmmss(grand)} total)")


if __name__ == "__main__":
    main()
