#!/usr/bin/env python3
"""Batch-reduce motif density across chapters that exceed threshold.

Strategy: replace highest-frequency tics in non-identity contexts.
Keep: character self-identification ("I am a cartographer"), proper nouns, dialogue that defines character.
Replace: narrative voice uses, descriptive passages, repeated metaphors.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAPTERS = ROOT / "chapters"

# Per-chapter replacement rules: (find, replace, count_limit)
# Only the first `count_limit` non-overlapping occurrences are replaced.
RULES = {
    "ch_02.md": [
        # cartographer → surveyor in narrative voice
        (r"\bthe cartographer\b(?!'s)", "the surveyor", 5),
        (r"\bI am a cartographer\b", "I am a mapmaker", 1),
    ],
    "ch_06.md": [
        (r"\bthe cartographer\b(?!'s)", "the surveyor", 2),
        (r"\bcartography\b", "the survey craft", 1),
        (r"\ba cartographer\b", "a surveyor", 1),
    ],
    "ch_09.md": [
        (r"\bthe cartographer\b(?!'s)", "the surveyor", 4),
        (r"\bcartography\b", "the survey craft", 1),
        (r"\ba cartographer\b", "a surveyor", 2),
    ],
    "ch_11.md": [
        (r"\bthe map\b(?! room)", "the chart", 2),
    ],
    "ch_12.md": [
        (r"\bthe map\b(?! room)", "the chart", 3),
        (r"\bthe cartographer\b(?!'s)", "the surveyor", 5),
        (r"\ba cartographer\b", "a surveyor", 3),
        (r"\bcartography\b", "the survey craft", 1),
    ],
    "ch_13.md": [
        (r"\bthe map\b(?! room)", "the chart", 2),
    ],
    "ch_14.md": [
        (r"\bthe map\b(?! room)", "the chart", 1),
    ],
    "ch_16.md": [
        (r"\bthe map\b(?! room)", "the chart", 1),
    ],
    "ch_19.md": [
        (r"\bthe cartographer\b(?!'s)", "the surveyor", 4),
        (r"\ba cartographer\b", "a surveyor", 2),
        (r"\bcartography\b", "the survey craft", 1),
    ],
    "ch_20.md": [
        (r"\bthe map\b(?! room)", "the chart", 4),
    ],
    "ch_20b.md": [
        (r"\bthe cartographer\b(?!'s)", "the surveyor", 3),
        (r"\ba cartographer\b", "a surveyor", 2),
        (r"\bcartography\b", "the craft", 1),
    ],
    "ch_22.md": [
        (r"\bthe cartographer\b(?!'s)", "the surveyor", 5),
        (r"\ba cartographer\b", "a surveyor", 3),
        (r"\bcartography\b", "the survey craft", 2),
    ],
    "ch_24.md": [
        (r"\bthe cartographer\b(?!'s)", "the surveyor", 4),
        (r"\ba cartographer\b", "a surveyor", 2),
        (r"\bcartography\b", "the survey craft", 1),
        (r"\bthe silence\b", "the quiet", 3),
    ],
    "ch_25.md": [
        (r"\bthe cartographer\b(?!'s)", "the surveyor", 2),
        (r"\ba cartographer\b", "a surveyor", 1),
        (r"\bcartography\b", "the craft", 1),
    ],
    "ch_26.md": [
        (r"\bthe map\b(?! room)", "the chart", 3),
        (r"\bthe cartographer\b(?!'s)", "the surveyor", 2),
    ],
}


def apply_rules(filepath: Path, rules: list[tuple[str, str, int]]) -> int:
    """Apply replacement rules to a file. Returns total replacements made."""
    text = filepath.read_text(encoding="utf-8")
    total = 0
    for pattern, replacement, limit in rules:
        # Case-insensitive replace, but preserve case of first letter
        def replacer(m):
            matched = m.group()
            if matched[0].isupper():
                return replacement[0].upper() + replacement[1:]
            return replacement

        new_text, n = re.subn(pattern, replacer, text, count=limit, flags=re.IGNORECASE)
        if n > 0:
            text = new_text
            total += n
    if total > 0:
        filepath.write_text(text, encoding="utf-8")
    return total


def main():
    grand_total = 0
    for chapter, rules in RULES.items():
        fp = CHAPTERS / chapter
        if not fp.exists():
            print(f"  SKIP {chapter} (not found)")
            continue
        n = apply_rules(fp, rules)
        print(f"  {chapter}: {n} replacements")
        grand_total += n
    print(f"\nTotal: {grand_total} replacements across {len(RULES)} chapters")


if __name__ == "__main__":
    main()
