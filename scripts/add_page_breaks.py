#!/usr/bin/env python3
"""
Insert \\newpage markers at logical chapter/section boundaries.

Rules (all targeted at lines beginning with `#` in the markdown):
  - First chapter heading -> nothing (TOC ends with \\newpage already; chapter starts on fresh page).
  - Each subsequent `# Chapter ...` or `# Chapter Twenty-One: ...` -> prepend \\newpage.
  - The manuscript title block at the top of manuscript.md -> keep (handled by title_page.md).
  - The interstitial heading "# Chapter Twenty-One: The Ley-Node Convergence"
    (which is the ch_20b file, despite its h1) is treated as a chapter break.

Input/output:
  Reads manuscript.md, writes manuscript.md in place. Idempotent (skips if a
  \\newpage immediately precedes the heading already).

Usage:
  python3 scripts/add_page_breaks.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANUSCRIPT = ROOT / "manuscript.md"

CHAPTER_RE = re.compile(r"^# Chapter\b", re.MULTILINE)
NEWPAGE_RE = re.compile(r"\\newpage\s*$")


def main() -> int:
    text = MANUSCRIPT.read_text(encoding="utf-8")
    lines = text.split("\n")
    out: list[str] = []
    chapter_count = 0
    inserted = 0

    for i, line in enumerate(lines):
        is_chapter = bool(CHAPTER_RE.match(line))
        if is_chapter:
            chapter_count += 1
            # Skip \\newpage before the first chapter (TOC/page break handles it).
            if chapter_count == 1:
                # Drop a trailing \\newpage on the previous line if present so we don't double up.
                if out and NEWPAGE_RE.match(out[-1]):
                    out.pop()
                    inserted -= 1
                out.append(line)
                continue
            # If the previous emitted line is already \\newpage, don't add another.
            if out and NEWPAGE_RE.match(out[-1]):
                out.append(line)
                continue
            out.append("\\newpage")
            inserted += 1
        out.append(line)

    new_text = "\n".join(out)
    if new_text != text:
        MANUSCRIPT.write_text(new_text, encoding="utf-8")
        print(
            f"Inserted {inserted} \\newpage markers before chapter headings "
            f"({chapter_count} chapters total)."
        )
    else:
        print(f"No change ({chapter_count} chapters, already had {inserted} markers).")
    return 0


if __name__ == "__main__":
    sys.exit(main())