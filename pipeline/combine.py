#!/usr/bin/env python3
"""Combine the per-chapter markdown into one full-book markdown file.

Produces build/<slug>.md — every chapter in order, with a clickable table of
contents. Citation endnotes were already dropped at the extract stage.

Usage:
    python pipeline/combine.py --build build --title "U.S. Private-Sector Privacy (4th ed.)"
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text).strip().replace(" ", "_")
    return re.sub(r"_+", "_", text) or "book"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--build", default=Path("build"), type=Path)
    ap.add_argument("--title", default="Full Text")
    ap.add_argument("--out", default="", help="output path (default build/<slug>.md)")
    args = ap.parse_args()

    book = json.loads((args.build / "book.json").read_text(encoding="utf-8"))
    chapters = book["chapters"]

    parts: list[str] = [
        f"# {args.title} — Full Text (Markdown)\n",
        f"_Converted from `{book['source']}`. Endnotes/citation apparatus omitted. "
        f"{len(chapters)} chapters._\n",
        "## Contents\n",
    ]
    for ch in chapters:
        parts.append(f"- [Chapter {ch['num']}: {ch['title']}](#chapter-{ch['num']})")
    parts.append("")

    for ch in chapters:
        md = (args.build / ch["file"]).read_text(encoding="utf-8").strip()
        md = re.sub(r"^#\s+.*(\n|$)", "", md, count=1).strip()  # drop the raw H1
        parts.append("\n---\n")
        parts.append(f'<a id="chapter-{ch["num"]}"></a>')
        parts.append(f"\n# Chapter {ch['num']}: {ch['title']}\n")
        parts.append(md)

    full = "\n".join(parts) + "\n"
    dest = Path(args.out) if args.out else args.build / f"{slugify(args.title)}.md"
    dest.write_text(full, encoding="utf-8")
    print(f"Wrote {dest}  ({len(full):,} chars)")


if __name__ == "__main__":
    main()
