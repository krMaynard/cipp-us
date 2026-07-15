#!/usr/bin/env python3
"""Extract memorizable U.S.-regulation facts from each chapter for an Anki deck.

Uses the headless `claude -p` CLI (same seam as generate.py) with prompts/cards.md
to turn each chapter into a list of {slug, law, acronym, year, citation, scope,
trigger, enforcer, key_facts, scenario} items — the rote hooks a candidate can't
reason their way to. Writes build/cards/chNN.json and a merged build/cards.json.

Usage:
    python pipeline/cards.py --build build            # all chapters
    python pipeline/cards.py --build build --only 1,2 # a subset
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

MODEL = "claude-opus-4-8"
PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
REQUIRED = ("slug", "law", "acronym", "scenario")


def run_claude(prompt: str, timeout: int = 600) -> str:
    proc = subprocess.run(
        ["claude", "-p", prompt, "--model", MODEL],
        capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude CLI failed ({proc.returncode}): {proc.stderr[:500]}")
    return proc.stdout.strip()


def extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n", "", text)
        text = re.sub(r"\n```$", "", text)
    text = text.strip()
    # Accept either a JSON object {...} or a bare array [...] the model may emit.
    start = min((text.find(c) for c in "{[" if c in text), default=-1)
    end = max((text.rfind(c) for c in "}]" if c in text), default=-1)
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]
    return text


def gen_cards(chapter_md: str) -> list[dict]:
    raw = extract_json(run_claude((PROMPTS / "cards.md").read_text(encoding="utf-8") + chapter_md))
    data = json.loads(raw)
    items = data.get("items") if isinstance(data, dict) else data  # accept {items:[...]} or bare [...]
    if not isinstance(items, list):
        raise ValueError("cards JSON must be an object with an items list (or a bare list)")
    clean: list[dict] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        # `it.get(k) or ""` (not a "" default) so a JSON null becomes "", never the string "None".
        if all(str(it.get(k) or "").strip() for k in REQUIRED):
            clean.append({k: str(it.get(k) or "").strip() for k in
                          ("slug", "law", "acronym", "year", "citation", "scope",
                           "trigger", "enforcer", "key_facts", "scenario")})
    return clean


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--build", default=Path("build"), type=Path)
    ap.add_argument("--only", default="")
    ap.add_argument("--skip-existing", action="store_true")
    args = ap.parse_args()

    book = json.loads((args.build / "book.json").read_text(encoding="utf-8"))
    wanted = {int(x) for x in args.only.split(",") if x.strip()} if args.only else None
    cards_dir = args.build / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)

    failures = 0
    for ch in book["chapters"]:
        if wanted and ch["num"] not in wanted:
            continue
        out = cards_dir / f"{ch['id']}.json"
        if args.skip_existing and out.exists() and out.stat().st_size > 0:
            print(f"[{ch['id']}] skip (exists)")
            continue
        try:
            print(f"[{ch['id']}] {ch['title'][:55]}: extracting...", flush=True)
            items = gen_cards((args.build / ch["file"]).read_text(encoding="utf-8"))
            for it in items:
                it["chapter"] = ch["num"]
                it["chapter_title"] = ch["title"]
            out.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"    {len(items)} regulation cards")
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"    FAILED - {e}", file=sys.stderr)

    # Merge, de-duplicating by slug (later chapters keep the first definition)
    merged: dict[str, dict] = {}
    for f in sorted(cards_dir.glob("*.json")):
        for it in json.loads(f.read_text(encoding="utf-8")):
            merged.setdefault(it["slug"], it)
    (args.build / "cards.json").write_text(
        json.dumps(list(merged.values()), indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Merged {len(merged)} unique regulation cards -> {args.build / 'cards.json'}")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
