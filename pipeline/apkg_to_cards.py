#!/usr/bin/env python3
"""Recover build/cards.json from a committed .apkg deck (no EPUB needed).

The normal source of the Anki deck is build/cards.json, produced by cards.py from
the (copyrighted, un-committed) textbook. When you only have the committed deck —
e.g. to REBUILD it with new templates or audio while keeping every card's
scheduling — this reads the note fields straight back out of the .apkg's SQLite
collection and reconstructs cards.json, including each note's GUID so a rebuilt
deck updates cards in place instead of duplicating them.

Usage:
    python pipeline/apkg_to_cards.py --apkg decks/cipp-us-regulations.apkg --build build
    make cards-from-deck        # same thing, wired in the Makefile
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import tempfile
import zipfile
from pathlib import Path

# Field order of the "CIPP/US — US Regulation" note type (see build_anki.py MODEL).
# The trailing QAudio* fields are audio the rebuild regenerates, so we don't read
# them back — only the source facts, plus the recovered slug/guid.
FIELDS = ["law", "acronym", "year", "citation", "scope", "trigger",
          "enforcer", "key_facts", "scenario", "audio", "chapter"]

# cards.json key order cards.py emits, so a recovered file diffs cleanly against a
# freshly generated one.
OUT_KEYS = ["slug", "guid", "law", "acronym", "year", "citation", "scope",
            "trigger", "enforcer", "key_facts", "scenario", "chapter"]


def recover(apkg: Path) -> list[dict]:
    with zipfile.ZipFile(apkg) as z:
        names = z.namelist()
        # Prefer the newer schema if both are present.
        db = next((n for n in ("collection.anki21", "collection.anki2") if n in names), None)
        if not db:
            raise SystemExit(f"{apkg}: no collection database inside the .apkg")
        with tempfile.TemporaryDirectory() as td:
            z.extract(db, td)
            con = sqlite3.connect(Path(td) / db)
            rows = con.execute("select guid, flds from notes").fetchall()
            con.close()

    cards: list[dict] = []
    for guid, flds in rows:
        parts = flds.split("\x1f")
        d = dict(zip(FIELDS, parts))
        # Recover the slug from the answer clip name (usreg_<slug>.mp3); fall back
        # to the acronym/law so a slug always exists even for a note without audio.
        m = re.search(r"usreg_(.+?)\.mp3", d.get("audio", ""))
        slug = m.group(1) if m else re.sub(
            r"[^A-Za-z0-9_]", "_", (d.get("acronym") or d.get("law") or "card"))
        card = {"slug": slug, "guid": guid}
        card.update({k: (d.get(k) or "").strip() for k in OUT_KEYS if k not in ("slug", "guid")})
        cards.append(card)
    return cards


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apkg", required=True, type=Path)
    ap.add_argument("--build", default=Path("build"), type=Path)
    ap.add_argument("--out", default="", help="override output path (default <build>/cards.json)")
    args = ap.parse_args()

    cards = recover(args.apkg)
    slugs, guids = {c["slug"] for c in cards}, {c["guid"] for c in cards}
    if len(slugs) != len(cards):
        print(f"WARNING: {len(cards) - len(slugs)} duplicate slug(s) — audio filenames may collide")
    if len(guids) != len(cards):
        print(f"WARNING: {len(cards) - len(guids)} duplicate GUID(s) — cards would merge on import")

    args.build.mkdir(parents=True, exist_ok=True)
    out = Path(args.out) if args.out else args.build / "cards.json"
    out.write_text(json.dumps(cards, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Recovered {len(cards)} cards -> {out}")


if __name__ == "__main__":
    main()
