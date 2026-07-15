#!/usr/bin/env python3
"""Extract chapters from an EPUB textbook into clean per-chapter markdown.

Reads the EPUB directly as a zip (no ebooklib dependency), walks each
chapter's XHTML in document order, and emits headings/paragraphs/lists as
markdown plus a book.json manifest the later stages consume.

Usage:
    python pipeline/extract.py --epub source/book.epub --out build
"""
from __future__ import annotations

import argparse
import json
import re
import warnings
import zipfile
from pathlib import Path

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

CHAPTER_RE = re.compile(r"Chapter_(\d+)\.xhtml$", re.IGNORECASE)
BLOCK_TAGS = {"h1", "h2", "h3", "h4", "h5", "p", "li", "td", "th"}

# This textbook is InDesign-exported: structure lives in <p class="..."> names,
# not in <h*> tags. Map the class prefixes to markdown roles. Anything matching
# ENDNOTE_RE is citation apparatus and is dropped — it is pure noise for an
# audio study aid and would otherwise dominate the chapter text.
TITLE_CLASS = "_02-Chap-Title"
HEADING_CLASSES = {"_11-A-Head": "## ", "_12-B-Head": "### ", "_13-C-Head": "#### "}
LIST_CLASSES = ("_10-Bull-List", "_44-Extract-Num-List")
QUOTE_CLASSES = ("_41-Extract",)
DROP_CLASS_RE = re.compile(r"Endnotes|End-?NOTES|Chap-Num", re.IGNORECASE)


# Superscript endnote reference markers, e.g.
#   <span class="_99-endnote-number"><a class="_idEndnoteLink">1</a></span>
# These are stripped structurally (below) rather than by regex, so a genuine
# sentence-leading number is never mistaken for a footnote marker.
ENDNOTE_REF_RE = re.compile(r"endnote-number|_idEndnoteLink|_idEndnoteAnchor", re.IGNORECASE)


def strip_endnote_refs(soup: BeautifulSoup) -> None:
    doomed = []
    for el in soup.find_all(["span", "a", "sup"]):
        classes = " ".join(el.get("class") or [])
        href = el.get("href") or ""
        if ENDNOTE_REF_RE.search(classes) or "endnote" in href.lower():
            doomed.append(el)
    for el in doomed:  # decompose after collecting to avoid mutating during iteration
        el.decompose()


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def role_for(classes: list[str]) -> str:
    """Classify a <p> by its InDesign class into a markdown role."""
    cls = " ".join(classes)
    if DROP_CLASS_RE.search(cls):
        return "drop"
    if TITLE_CLASS in classes:
        return "title"
    for name, _ in HEADING_CLASSES.items():
        if name in classes:
            return name
    if any(c.startswith(p) for c in classes for p in LIST_CLASSES):
        return "list"
    if any(c.startswith(p) for c in classes for p in QUOTE_CLASSES):
        return "quote"
    return "body"


def chapter_to_markdown(html: str) -> tuple[str, str]:
    """Return (title, markdown) for one chapter document, dropping endnotes."""
    soup = BeautifulSoup(html, "lxml")
    strip_endnote_refs(soup)
    lines: list[str] = []
    title = ""
    seen: set[int] = set()
    body = soup.body or soup
    for tag in body.find_all(list(BLOCK_TAGS)):
        if any(id(parent) in seen for parent in tag.parents):
            continue
        seen.add(id(tag))

        if tag.name in ("td", "th"):
            text = clean_text(tag.get_text(" ", strip=True))
            if text:
                lines.append(f"  | {text}")
            continue

        role = role_for(tag.get("class", []))
        if role == "drop":
            continue
        text = clean_text(tag.get_text(" ", strip=True))
        if not text:
            continue

        if role == "title":
            title = title or text
            lines.append(f"\n# {text}\n")
        elif role in HEADING_CLASSES:
            lines.append(f"\n{HEADING_CLASSES[role]}{text}\n")
        elif role == "list":
            lines.append(f"- {text}")
        elif role == "quote":
            lines.append(f"> {text}")
        else:
            lines.append(f"{text}\n")
    return title, "\n".join(lines).strip() + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--epub", required=True, type=Path)
    ap.add_argument("--out", default=Path("build"), type=Path)
    args = ap.parse_args()

    chapters_dir = args.out / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)

    manifest: list[dict] = []
    with zipfile.ZipFile(args.epub) as zf:
        chapter_files = sorted(
            (int(m.group(1)), name)
            for name in zf.namelist()
            if (m := CHAPTER_RE.search(name))
        )
        if not chapter_files:
            raise SystemExit("No Chapter_N.xhtml files found in the EPUB spine.")
        for num, name in chapter_files:
            title, md = chapter_to_markdown(zf.read(name).decode("utf-8"))
            out_path = chapters_dir / f"ch{num:02d}.md"
            out_path.write_text(md, encoding="utf-8")
            manifest.append(
                {
                    "num": num,
                    "id": f"ch{num:02d}",
                    "title": title or f"Chapter {num}",
                    "file": str(out_path.relative_to(args.out)),
                    "chars": len(md),
                }
            )
            print(f"  ch{num:02d}: {title[:70]}  ({len(md):,} chars)")

    (args.out / "book.json").write_text(
        json.dumps({"source": args.epub.name, "chapters": manifest}, indent=2),
        encoding="utf-8",
    )
    print(f"Extracted {len(manifest)} chapters -> {chapters_dir}")


if __name__ == "__main__":
    main()
