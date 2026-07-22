#!/usr/bin/env python3
"""Generate study materials from extracted chapters using the Claude CLI.

For each chapter this produces:
  - build/lectures/chNN.txt      spoken audio-lecture script
  - build/studypacks/chNN.json   {key_terms, qa} drill material

The generator shells out to the headless `claude -p` CLI (already
authenticated in this environment), so no API key handling lives here.
Model id is confirmed current per the repo's LLM-schema policy.

Usage:
    python pipeline/generate.py --build build            # all chapters
    python pipeline/generate.py --build build --only 1,2 # a subset
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


def run_claude(prompt: str, timeout: int = 600) -> str:
    """Call the headless Claude CLI and return its stdout text."""
    proc = subprocess.run(
        ["claude", "-p", prompt, "--model", MODEL],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude CLI failed ({proc.returncode}): {proc.stderr[:500]}")
    return proc.stdout.strip()


def strip_fences(text: str) -> str:
    """Return just the JSON object from a model reply.

    Strips ```json fences and any conversational preamble/postamble by taking
    the span from the first '{' to the last '}'.
    """
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n", "", text)
        text = re.sub(r"\n```$", "", text)
    text = text.strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]
    return text


def load_prompt(name: str) -> str:
    return (PROMPTS / name).read_text(encoding="utf-8")


def gen_lecture(chapter_md: str, out_path: Path) -> None:
    text = run_claude(load_prompt("lecture.md") + chapter_md)
    out_path.write_text(text + "\n", encoding="utf-8")


def gen_studypack(chapter_md: str, out_path: Path) -> None:
    raw = strip_fences(run_claude(load_prompt("studypack.md") + chapter_md))
    data = json.loads(raw)  # validate before writing
    if (not isinstance(data, dict)
            or not isinstance(data.get("key_terms"), list)
            or not isinstance(data.get("qa"), list)):
        raise ValueError("studypack JSON must be an object with key_terms/qa lists")
    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--build", default=Path("build"), type=Path)
    ap.add_argument("--only", default="", help="comma-separated chapter numbers")
    ap.add_argument("--skip-existing", action="store_true",
                    help="skip a chapter if its output already exists")
    args = ap.parse_args()

    book = json.loads((args.build / "book.json").read_text(encoding="utf-8"))
    wanted = {int(x) for x in args.only.split(",") if x.strip()} if args.only else None

    lectures = args.build / "lectures"
    studypacks = args.build / "studypacks"
    lectures.mkdir(parents=True, exist_ok=True)
    studypacks.mkdir(parents=True, exist_ok=True)

    failures = 0
    for ch in book["chapters"]:
        if wanted and ch["num"] not in wanted:
            continue
        chapter_md = (args.build / ch["file"]).read_text(encoding="utf-8")
        cid = ch["id"]
        print(f"[{cid}] {ch['title'][:60]}")

        lec_path = lectures / f"{cid}.txt"
        pack_path = studypacks / f"{cid}.json"
        for label, path, fn in (
            ("lecture", lec_path, gen_lecture),
            ("studypack", pack_path, gen_studypack),
        ):
            if args.skip_existing and path.exists() and path.stat().st_size > 0:
                print(f"    {label}: skip (exists)")
                continue
            try:
                print(f"    {label}: generating...", flush=True)
                fn(chapter_md, path)
                print(f"    {label}: {path.stat().st_size:,} bytes")
            except Exception as e:  # noqa: BLE001 - keep going on one bad chapter
                failures += 1
                print(f"    {label}: FAILED - {e}", file=sys.stderr)

    if failures:
        print(f"Done with {failures} failure(s).", file=sys.stderr)
        sys.exit(1)
    print("All study materials generated.")


if __name__ == "__main__":
    main()
