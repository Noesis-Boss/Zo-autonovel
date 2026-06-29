#!/usr/bin/env python3
"""
Motif-deduplication fixer — applies a moderate, voice-preserving pass to
reduce motif over-repetition flagged by forensic_eval.py.

Strategy (revised):
  - Skip headers (lines starting with # or containing only the title).
  - For each motif, classify each occurrence as LOAD-BEARING (protected)
    or FILLER (rewritable) using contextual signals.
  - Cap retained count at MAX_PER_CHAPTER (default 3 for prose, but
    identity phrases like "I am a cartographer" always load-bearing).
  - LOAD-BEARING signals:
      * Simile/core metaphor ("as if X were a Y")
      * Identity statement ("I am a X", "a X who ...")
      * Proper noun ("Cartographers' Quarter")
      * Direct noun-of-address / chapter title
  - FILLER signals:
      * Mid-paragraph reference when a recent load-bearing instance is
        already within the prior 400 chars.
      * "the X" in subject position with no possessive/qualifier.

Usage:
  python3 scripts/motif_fix.py              # dry-run
  python3 scripts/motif_fix.py --apply       # write changes
  python3 scripts/motif_fix.py --chapter ch_01
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAPTERS_DIR = ROOT / "chapters"
EVAL_LOGS_DIR = ROOT / "eval_logs"

MAX_PER_CHAPTER = 3

# Motifs with the substitutions applied to FILLER instances.
# Order matters: longer/more-specific patterns first.
MOTIF_RULES = [
    # 'I am a cartographer who ...' / 'I am a cartographer' -> protected
    # 'cartographers' as profession -> surveyor / cartograph-* rewrite is too
    # destructive; use minimal-synonym rotation that preserves context.
    {
        "name": "cartograph",
        "regex": re.compile(r"\bcartograph(?:y|er|ers)\b", re.I),
        # IMPORTANT: skip identity / simile / title / proper noun contexts.
        "skip_patterns": [
            re.compile(r"as if cartograph\w*\b", re.I),     # simile opener
            re.compile(r"\bI am a cartograph\w*\b", re.I),  # identity statement
            re.compile(r"^#\s.*cartograph\w*\b", re.I),     # heading
            re.compile(r"Cartographers' Quarter", re.I),    # proper noun
            re.compile(r"^cartograph\w*\b", re.I | re.M),   # line-start emphasis
            re.compile(r"\bevery other cartograph\w*\b", re.I),  # uniqueness comparison
            re.compile(r"\b(?:two|three|both) cartograph\w*\b", re.I),  # rhetorical plural
        ],
        # Rotation for filler instances. Order = priority (first occurrence of
        # the motif that fails the "load-bearing" test gets the first rewrite).
        "rewrites": [
            (re.compile(r"\bcartographers\b", re.I), "surveyors"),
            (re.compile(r"\bcartographer\b", re.I),  "surveyor"),
            (re.compile(r"\bcartography\b", re.I),   "the work"),
            (re.compile(r"\bcartography\b", re.I),   "the trade"),
            (re.compile(r"\bcartography\b", re.I),   "the craft"),
        ],
    },
    {
        "name": "the_map",
        "regex": re.compile(r"\bthe map\b", re.I),
        "skip_patterns": [
            re.compile(r"^#\s", re.I),                                    # heading
            re.compile(r"\bthe map[-\s]room\b", re.I),                    # proper noun "map-room"
            re.compile(r"\bthe map is (?:wrong|never|not|always|of|a|the)\b", re.I),  # philosophical core
            re.compile(r"\bwhat if the map\b", re.I),                     # rhetorical Q
            re.compile(r"\bmap of\b", re.I),                              # usually necessary
        ],
        "rewrites": [
            (re.compile(r"\bthe map\b", re.I), "the page"),
            (re.compile(r"\bthe map\b", re.I), "the chart"),
            (re.compile(r"\bthe map\b", re.I), "it"),
            (re.compile(r"\bthe map\b", re.I), "this"),
        ],
    },
    {
        "name": "frost",
        "regex": re.compile(r"\bfrost (?:prick|prickle|pricks|behind)\b", re.I),
        "skip_patterns": [
            re.compile(r"^#\s", re.I),
            re.compile(r"\bno frost\b", re.I),                            # negation
            re.compile(r"\bnot (?:a |an )?frost\b", re.I),               # negation
            re.compile(r"\bwithout (?:a |an )?frost\b", re.I),
            re.compile(r"\bfrost (?:prick|prickle) is (?:immediate|silent)\b", re.I),
        ],
        "rewrites": [
            (re.compile(r"\bthe frost pricks?\b", re.I), "the cold moves"),
            (re.compile(r"\bfrost pricks?\b", re.I),     "the cold moves"),
            (re.compile(r"\bthe frost prickles?\b", re.I), "the chill spreads"),
            (re.compile(r"\bfrost prickles?\b", re.I),     "the chill spreads"),
            (re.compile(r"\bfrost behind my eye\b", re.I),  "the ice behind my eye"),
        ],
    },
    {
        "name": "the_silence",
        "regex": re.compile(r"\bthe silence\b", re.I),
        "skip_patterns": [
            re.compile(r"^#\s", re.I),
            re.compile(r"\bthe silence (?:is|was|stretches?|hangs|deepens|holds|spreads)\b", re.I),
            re.compile(r"\bbreak the silence\b", re.I),
            re.compile(r"\bthe silence\b\s+(?:of|between|inside|after)", re.I),
        ],
        "rewrites": [
            (re.compile(r"\bthe silence\b", re.I), "the quiet"),
            (re.compile(r"\bthe silence\b", re.I), "the hush"),
            (re.compile(r"\bthe silence\b", re.I), "the stillness"),
        ],
    },
    {
        "name": "the_truth",
        "regex": re.compile(r"\bthe truth\b", re.I),
        "skip_patterns": [
            re.compile(r"^#\s", re.I),
            re.compile(r"\bthe truth (?:inside|of|is|was|value)\b", re.I),
            re.compile(r"\btruth[-\s]value\b", re.I),    # compound noun
        ],
        "rewrites": [
            (re.compile(r"\bthe truth\b", re.I), "the fact"),
            (re.compile(r"\bthe truth\b", re.I), "what's real"),
            (re.compile(r"\bthe truth\b", re.I), "the actual"),
        ],
    },
    {
        "name": "the_territory",
        "regex": re.compile(r"\bthe territory\b", re.I),
        "skip_patterns": [
            re.compile(r"^#\s", re.I),
            re.compile(r"\bthe territory (?:of|I'm|is|was)\b", re.I),
            re.compile(r"\bmap is never the territory\b", re.I),
        ],
        "rewrites": [
            (re.compile(r"\bthe territory\b", re.I), "the ground"),
            (re.compile(r"\bthe territory\b", re.I), "the place"),
            (re.compile(r"\bthe territory\b", re.I), "it"),
        ],
    },
    {
        "name": "binding_hums",
        "regex": re.compile(r"\bthe binding (?:hums|sings|pulses|answers|wakes|warm)\b", re.I),
        "skip_patterns": [
            re.compile(r"^#\s", re.I),
        ],
        "rewrites": [
            (re.compile(r"\bthe binding hums\b", re.I), "the bond vibrates"),
            (re.compile(r"\bthe binding hums\b", re.I), "the link hums"),
            (re.compile(r"\bthe binding hums\b", re.I), "it hums"),
        ],
    },
    {
        "name": "frost_eye",
        "regex": re.compile(r"\bthe frost (?:behind|in|at) (?:my|her|his|their) eye\b", re.I),
        "skip_patterns": [
            re.compile(r"^#\s", re.I),
            re.compile(r"\bno frost\b", re.I),
            re.compile(r"\bnot (?:a |an )?frost\b", re.I),
        ],
        "rewrites": [
            (re.compile(r"\bthe frost behind my eye\b", re.I), "the ice behind my eye"),
            (re.compile(r"\bthe frost behind my eye\b", re.I), "the cold behind my eye"),
            (re.compile(r"\bthe frost behind her eye\b", re.I), "the ice behind her eye"),
        ],
    },
]

# Metaphor-saturation fix: per paragraph, if it has 3+ metaphor markers,
# convert the 3rd-and-onward "like Y" pattern to "as Y".
# This is intentionally minimal — only flattens the most formulaic structure.
METAPHOR_MARKER = re.compile(
    r"\b(?:like|as if|as though|was a|was like|were a|were like)\b", re.I
)


@dataclass
class Change:
    motif: str
    rule: str
    before: str
    after: str
    pos: int


def is_load_bearing(match_start: int, match_end: int, motif: dict, text: str) -> bool:
    """Check whether a motif occurrence is load-bearing and should be protected."""
    for pat in motif["skip_patterns"]:
        # Skip patterns are designed to match in a ±80-char window around the
        # motif occurrence. The motif word itself (e.g. "cartography") is
        # usually part of the skip pattern (e.g. "as if cartograph\\w*\\b"),
        # so we widen the window to ±120 chars to give the pattern room.
        win_start = max(0, match_start - 120)
        win_end = min(len(text), match_end + 120)
        if pat.search(text, win_start, win_end):
            return True
    return False


def rewrite_match(text: str, match_start: int, match_end: int, motif: dict,
                  rewrite_idx: int) -> tuple[str, str, str, bool]:
    """Apply the rewrite at the given index. Returns (new_text, rule, success)."""
    if rewrite_idx >= len(motif["rewrites"]):
        return text, "", "", False
    rule_pattern, replacement = motif["rewrites"][rewrite_idx]
    original = text[match_start:match_end]
    if rule_pattern.match(original):
        # Apply replace at this position
        new_text = (text[:match_start]
                    + rule_pattern.sub(replacement, original, count=1)
                    + text[match_end:])
        return new_text, rule_pattern.pattern, True
    return text, rule_pattern.pattern, False


def fix_chapter(path: Path, dry_run: bool = True, max_per: int = MAX_PER_CHAPTER
                ) -> tuple[list[Change], int, str, str]:
    """Fix one chapter. Returns (changes, metaphor_trims, original_text, new_text)."""
    text = path.read_text(encoding="utf-8")
    original = text
    changes: list[Change] = []

    # Per-motif occurrence count + state.
    for motif in MOTIF_RULES:
        occurrences = list(motif["regex"].finditer(text))
        # Walk backwards so positions don't shift as we rewrite.
        rewrite_idx_counter = [0]
        kept = 0
        # Collect matches to rewrite: every occurrence after the first `max_per`
        # load-bearing ones, AND only if it's NOT load-bearing.
        load_bearing_indices = []
        filler_indices = []
        for m in occurrences:
            if is_load_bearing(m.start(), m.end(), motif, text):
                load_bearing_indices.append(m)
            else:
                filler_indices.append(m)
        # Keep up to max_per load-bearing occurrences as-is (they all count).
        # Filler occurrences: keep first 0, rewrite the rest.
        # Determine how many fillers to keep.
        remaining = max_per - len(load_bearing_indices)
        if remaining > 0:
            kept_fillers = filler_indices[:remaining]
            rewrite_fillers = filler_indices[remaining:]
        else:
            kept_fillers = []
            rewrite_fillers = filler_indices
        # Rewrite in reverse position order to preserve offsets.
        for m in sorted(rewrite_fillers, key=lambda x: -x.start()):
            new_text, rule, ok = rewrite_match(
                text, m.start(), m.end(), motif,
                rewrite_idx_counter[0] % len(motif["rewrites"])
            )
            if ok:
                before = text[m.start():m.end()]
                after_text = new_text[m.start():m.start() + len(before)]
                # Recompute the actual replaced substring.
                if new_text != text:
                    # Find what changed
                    delta_start = m.start()
                    delta_end_old = m.end()
                    # Find where the rewritten text ends: count char length diff.
                    length_diff = len(new_text) - len(text)
                    delta_end_new = delta_end_old + length_diff
                    after_text = new_text[delta_start:delta_end_new]
                    changes.append(Change(
                        motif=motif["name"],
                        rule=rule,
                        before=before,
                        after=after_text,
                        pos=m.start(),
                    ))
                    rewrite_idx_counter[0] += 1
                    text = new_text

    # Metaphor-saturation trim: for any paragraph with 3+ markers, demote the
    # last "like X" to "as X" — minimal, surgical, no narrative surgery.
    para_trims = 0
    paragraphs = re.split(r"\n\s*\n", text)
    new_paragraphs = []
    for para in paragraphs:
        markers = list(METAPHOR_MARKER.finditer(para))
        if len(markers) >= 3:
            # Demote the last marker that's a plain "like"
            demoted = False
            for m in reversed(markers):
                word = para[m.start():m.end()].lower()
                if word == "like":
                    # Convert "like Y" -> "as Y" only if preceded by noun phrase
                    # — heuristic: convert if the next 30 chars look like a
                    # noun phrase (no verb after).
                    after = para[m.end():m.end() + 50]
                    # Skip if next token is "a" or "the" and there's no verb
                    # in the immediate vicinity (rough heuristic).
                    if re.match(r"\s+(?:a |an |the )?[a-z][a-z\-]+", after):
                        new_para = para[:m.start()] + "as" + para[m.end():]
                        # Capitalize "as" if it's at sentence start
                        if m.start() == 0 or para[m.start() - 1] in ".!?":
                            new_para = new_para[:m.start()] + "As" + new_para[m.start()+2:]
                        para = new_para
                        para_trims += 1
                        demoted = True
                        break
        new_paragraphs.append(para)
    if para_trims > 0:
        text = "\n\n".join(new_paragraphs)

    if not dry_run and text != original:
        path.write_text(text, encoding="utf-8")

    return changes, para_trims, original, text


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true",
                   help="write changes (default: dry-run)")
    p.add_argument("--chapter", help="single chapter file")
    p.add_argument("--max-per", type=int, default=MAX_PER_CHAPTER,
                   help=f"max motif instances per chapter (default {MAX_PER_CHAPTER})")
    args = p.parse_args()

    if not CHAPTERS_DIR.exists():
        print(f"chapters/ not found at {CHAPTERS_DIR}", file=sys.stderr)
        return 2

    chapter_files = sorted(
        f for f in CHAPTERS_DIR.iterdir()
        if f.suffix == ".md" and f.name.startswith("ch_")
    )
    if args.chapter:
        chapter_files = [f for f in chapter_files
                         if f.name.startswith(args.chapter)]
        if not chapter_files:
            print(f"No chapter matches {args.chapter}", file=sys.stderr)
            return 2

    print(f"{'Chapter':<12} {'Status':<8} {'Motif rewrites':>16} {'Metaphor trims':>16}")
    print("-" * 60)

    all_logs = []
    total_changes = 0
    total_trims = 0
    for f in chapter_files:
        changes, trims, _, _ = fix_chapter(f, dry_run=not args.apply,
                                           max_per=args.max_per)
        status = "applied" if args.apply else "preview"
        print(f"{f.name:<12} {status:<8} {len(changes):>16} {trims:>16}")
        total_changes += len(changes)
        total_trims += trims
        all_logs.append({
            "chapter": f.name,
            "rewrites": [
                {"motif": c.motif, "rule": c.rule,
                 "before": c.before, "after": c.after, "pos": c.pos}
                for c in changes
            ],
            "metaphor_trims": trims,
        })

    print("-" * 60)
    print(f"{'TOTAL':<12} {'':<8} {total_changes:>16} {total_trims:>16}")

    # Persist log.
    EVAL_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = EVAL_LOGS_DIR / f"{stamp}_motif_fix_log.json"
    log_path.write_text(json.dumps({
        "generated_at": datetime.now().isoformat(),
        "mode": "applied" if args.apply else "dry_run",
        "max_per_chapter": args.max_per,
        "chapters": all_logs,
    }, indent=2))
    print(f"\nLog: {log_path.relative_to(ROOT)}")

    if not args.apply:
        print("\nDRY-RUN. Use --apply to write changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())