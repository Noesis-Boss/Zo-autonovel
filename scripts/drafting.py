#!/usr/bin/env python3
"""
Phase 2: Drafting. Sequential chapter generation with retry loop.

For each chapter in outline order:
  1. Build context window: voice.md + world.md + characters.md +
     outline.md entry + prev chapter last 1k words + next chapter outline.
  2. POST to Anthropic API with chapter prompt.
  3. Run evaluate.py --chapter=ch_NN; keep if score > 6.0 else retry (max 5).
  4. Extract canon entries from prose, append to canon.md.
  5. Log to results.tsv.
  6. Mechanical slop pass after each chapter.

Usage:
  python3 scripts/drafting.py                 # draft all chapters
  python3 scripts/drafting.py --start 10      # resume from ch_10
  python3 scripts/drafting.py --end 12        # stop after ch_12
  python3 scripts/drafting.py --only ch_05    # single chapter
  python3 scripts/drafting.py --max-retries 7 # override retry cap

Environment:
  ANTHROPIC_API_KEY (required)
  ANTHROPIC_MODEL   (default: claude-sonnet-4-5)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from llm import chat  # noqa: E402
from state import load, advance  # noqa: E402

CHAPTERS_DIR = ROOT / "chapters"
OUTLINE = ROOT / "outline.md"
VOICE = ROOT / "voice.md"
WORLD = ROOT / "world.md"
CHARS = ROOT / "characters.md"
CANON = ROOT / "canon.md"
RESULTS = ROOT / "results.tsv"


def parse_outline_entries(outline_text: str) -> list[dict]:
    """Pull chapter entries from outline.md.

    Matches patterns like:
        ## Chapter 1 — Title
        ## Ch 5. The Survey Craft
        ## Chapter 12b (interstitial)

    Returns list of {num, label, beat} dicts in document order.
    """
    entries: list[dict] = []
    pattern = re.compile(
        r"^##\s+(?:Chapter|Ch\.?)\s+(\d+[a-z]?)\s*[.:)\-—–]?\s*([^\n]*)$",
        re.MULTILINE,
    )
    for m in pattern.finditer(outline_text):
        num = m.group(1).strip()
        label = m.group(2).strip()
        # Beat = section between this match and next
        start = m.end()
        next_match = pattern.search(outline_text, start)
        beat_end = next_match.start() if next_match else len(outline_text)
        beat = outline_text[start:beat_end].strip()
        entries.append({"num": num, "label": label, "beat": beat})
    return entries


def last_n_words(text: str, n: int = 1000) -> str:
    words = text.split()
    return " ".join(words[-n:]) if len(words) > n else text


def build_chapter_prompt(
    *,
    entry: dict,
    voice: str,
    world: str,
    chars: str,
    prev_tail: str,
    next_beat: str,
) -> list[dict]:
    """Compose the Anthropic messages payload for one chapter."""
    system = (
        "You are the novelist. Continue the manuscript following all "
        "house rules in voice.md (Part 1 guardrails are non-negotiable; "
        "Part 2 voice identity is the discovered style for THIS novel). "
        "Maintain continuity with world.md, characters.md, and the prior "
        "chapter's tail. Honor the chapter outline beat exactly. "
        "Do NOT use em-dashes. Do NOT restate what the prose just showed. "
        "Output ONLY the chapter prose (no headings, no metadata, no "
        "Markdown fences). Begin in media res."
    )
    user = f"""## Chapter outline entry
Number: {entry['num']}
Label: {entry['label'] or '(untitled)'}
Beat:
{entry['beat']}

## Voice guardrails + identity
{voice}

## World bible (excerpt — first 4000 chars)
{world[:4000]}

## Character registry (excerpt — first 4000 chars)
{chars[:4000]}

## Previous chapter tail (last 1000 words)
{prev_tail or '(this is the first chapter — establish scene and POV)'}

## Next chapter outline (for continuity)
{next_beat or '(this is the final chapter — land the arc)'}

Write the chapter now. Target length follows from the outline beat.
"""
    return [
        {"role": "user", "content": system + "\n\n" + user},
    ]


def extract_canon_lines(prose: str, chap_num: str) -> list[str]:
    """Heuristic canon extraction: pull sentences with proper-noun
    introductions, geography, dates. Append source chapter tag.
    """
    out: list[str] = []
    sentences = re.split(r"(?<=[.!?])\s+", prose)
    for s in sentences:
        s = s.strip()
        if len(s) < 20 or len(s) > 200:
            continue
        # Proper-noun introduction patterns
        if re.search(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\s+(?:was|is|lived|ruled|built|founded|sat)\b", s):
            out.append(f"- {s} [ch{chap_num}]")
        # Calendar / time references
        elif re.search(r"\b(?:year|fifteen|twenty|hundred|century)\b", s, re.IGNORECASE):
            out.append(f"- {s} [ch{chap_num}]")
    return out[:8]  # cap per chapter


def score_chapter(chap_path: Path) -> float | None:
    """Run evaluate.py --chapter and parse score from JSON report."""
    try:
        out = subprocess.run(
            ["python3", str(ROOT / "scripts" / "evaluate.py"),
             "--chapter", chap_path.stem, "--mode", "chapter", "--quiet"],
            check=False, capture_output=True, text=True, timeout=120,
        )
    except subprocess.TimeoutExpired:
        return None
    # Pull the latest JSON report
    eval_logs = ROOT / "eval_logs"
    if not eval_logs.exists():
        return None
    reports = sorted(eval_logs.glob("*_evaluate.json"), reverse=True)
    if not reports:
        return None
    try:
        data = json.loads(reports[0].read_text())
    except (json.JSONDecodeError, OSError):
        return None
    for r in data.get("reports", []):
        if r["chapter"] == chap_path.stem:
            return r.get("score")
    return None


def log_result(tsv_path: Path, row: list[str]) -> None:
    new = not tsv_path.exists()
    with tsv_path.open("a") as f:
        if new:
            f.write("\t".join(["timestamp", "phase", "chapter",
                               "attempt", "score", "words", "notes"]) + "\n")
        f.write("\t".join(row) + "\n")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--start", type=int, default=0,
                   help="resume from chapter N (1-indexed in outline order)")
    p.add_argument("--end", type=int, default=0,
                   help="stop after chapter N (inclusive)")
    p.add_argument("--only", default="",
                   help="draft a single chapter by num (e.g. ch_05)")
    p.add_argument("--max-retries", type=int, default=5)
    p.add_argument("--threshold", type=float, default=6.0,
                   help="minimum evaluate.py score to keep")
    args = p.parse_args()

    for path in (VOICE, WORLD, CHARS, OUTLINE):
        if not path.exists():
            print(f"missing {path.relative_to(ROOT)} — run foundation first", file=sys.stderr)
            return 2

    outline_text = OUTLINE.read_text()
    entries = parse_outline_entries(outline_text)
    if not entries:
        print("no chapter entries found in outline.md", file=sys.stderr)
        return 2

    if args.only:
        entries = [e for e in entries if e["num"] == args.only]
        if not entries:
            print(f"chapter {args.only} not in outline.md", file=sys.stderr)
            return 2

    if args.end:
        entries = entries[:args.end]

    CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)
    voice = VOICE.read_text()
    world = WORLD.read_text()
    chars = CHARS.read_text()

    state = load()

    for i, entry in enumerate(entries):
        if i < args.start:
            continue
        chap_label = f"ch_{entry['num'].rjust(2, '0')}"
        chap_path = CHAPTERS_DIR / f"{chap_label}.md"
        prev_path = CHAPTERS_DIR / f"ch_{int(entry['num']) - 1:02d}.md" if i > 0 else None
        if prev_path and prev_path.exists():
            prev_tail = last_n_words(prev_path.read_text(), 1000)
        else:
            prev_tail = ""
        next_beat = entries[i + 1]["beat"] if i + 1 < len(entries) else ""

        kept = False
        for attempt in range(1, args.max_retries + 1):
            print(f"=== drafting {chap_label} attempt {attempt}/{args.max_retries} ===")
            messages = build_chapter_prompt(
                entry=entry, voice=voice, world=world, chars=chars,
                prev_tail=prev_tail, next_beat=next_beat,
            )
            try:
                prose = chat(messages, max_tokens=8000)
            except Exception as e:
                print(f"api error: {e}", file=sys.stderr)
                time.sleep(5 * attempt)
                continue
            prose = prose.strip()
            chap_path.write_text(prose)
            words = len(prose.split())
            score = score_chapter(chap_path)
            log_result(RESULTS, [
                time.strftime("%Y-%m-%d %H:%M:%S"), "drafting",
                chap_label, str(attempt),
                f"{score:.2f}" if score is not None else "n/a",
                str(words),
                "kept" if (score is not None and score >= args.threshold) else "discard",
            ])
            if score is not None and score >= args.threshold:
                kept = True
                break
            print(f"  score {score} < {args.threshold}; retry")
            time.sleep(2)

        if not kept:
            print(f"FAILED to keep {chap_label} after {args.max_retries} attempts", file=sys.stderr)
            log_result(RESULTS, [
                time.strftime("%Y-%m-%d %H:%M:%S"), "drafting",
                chap_label, str(args.max_retries),
                "n/a", "n/a", "abandoned",
            ])
            return 1

        # Append canon lines
        if CANON.exists():
            canon_text = CANON.read_text()
        else:
            canon_text = "# Canon\n\n"
        new_lines = extract_canon_lines(chap_path.read_text(), entry["num"])
        if new_lines:
            canon_text += "\n## " + f"Chapter {entry['num']}\n" + "\n".join(new_lines) + "\n"
            CANON.write_text(canon_text)

        # Mechanical slop pass
        subprocess.run(
            ["python3", str(ROOT / "scripts" / "strip_em_dashes.py"),
             str(chap_path)],
            check=False, capture_output=True,
        )

    state["phase"] = "revision"
    advance(state, "drafting complete")
    print(f"\nDrafting complete. {len(entries)} chapters written.")
    print(f"Next: python3 scripts/revision.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())