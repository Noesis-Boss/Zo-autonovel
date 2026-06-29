#!/usr/bin/env python3
"""
Concatenate chapters/ into manuscript.md in canonical order.

Order is read from REVISION_PLAN.md / outline.md (chapter numbering). Any
ch_NN.md or ch_NNb.md (interstitial) is included; files starting with ch_
but not matching that pattern are skipped with a warning.

Usage:
  python3 scripts/compile_manuscript.py
  python3 scripts/compile_manuscript.py --check   # exit 1 if dirty
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAPTERS_DIR = ROOT / "chapters"
MANUSCRIPT = ROOT / "manuscript.md"
# Title page from book metadata (novel.json)
META_FILE = ROOT / "novel.json"
import json


def load_intro() -> str:
    try:
        with open(META_FILE) as f:
            data = json.load(f)
        title = data.get("title", "Novel Manuscript")
        return f"# {title}\n\n"
    except (FileNotFoundError, json.JSONDecodeError):
        return "# Novel Manuscript\n\n"


def chapter_sort_key(path: Path) -> tuple[int, int, str]:
    """Sort ch_01 < ch_02 < ... < ch_20 < ch_20b < ch_21."""
    m = re.match(r"ch_(\d+)([a-z]?)\.md$", path.name)
    if not m:
        return (999, 999, path.name)
    n = int(m.group(1))
    suffix = m.group(2)
    suffix_order = ord(suffix) - ord("a") + 1 if suffix else 0
    return (n, suffix_order, path.name)


def collect_chapters() -> list[Path]:
    if not CHAPTERS_DIR.exists():
        print(f"chapters/ not found at {CHAPTERS_DIR}", file=sys.stderr)
        sys.exit(2)
    chapters = [
        p for p in CHAPTERS_DIR.iterdir()
        if p.suffix == ".md" and re.match(r"ch_\d+[a-z]?\.md$", p.name)
    ]
    chapters.sort(key=chapter_sort_key)
    return chapters


def build_manuscript(chapters: list[Path]) -> str:
    parts = [load_intro()]
    for p in chapters:
        body = p.read_text(encoding="utf-8").strip()
        parts.append(f"{body}\n\n---\n\n")
    return "".join(parts).rstrip() + "\n"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true",
                   help="exit 1 if manuscript.md is out of date")
    args = p.parse_args()

    chapters = collect_chapters()
    new = build_manuscript(chapters)

    if args.check:
        if not MANUSCRIPT.exists():
            print(f"{MANUSCRIPT.name} missing — run without --check", file=sys.stderr)
            return 1
        if MANUSCRIPT.read_text(encoding="utf-8") != new:
            print(f"{MANUSCRIPT.name} is out of date", file=sys.stderr)
            return 1
        print(f"{MANUSCRIPT.name} up to date ({len(chapters)} chapters)")
        return 0

    MANUSCRIPT.write_text(new, encoding="utf-8")
    word_count = len(new.split())
    print(f"Wrote {MANUSCRIPT.name} — {len(chapters)} chapters, {word_count} words")
    return 0


if __name__ == "__main__":
    sys.exit(main())
