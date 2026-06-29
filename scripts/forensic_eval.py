#!/usr/bin/env python3
"""
Forensic AI-detection scanner — implements the reviewer checklist from the
independent AI-detection review that scored Bound by Ash and Thorn 80-95%
AI-assisted.

Five highest-signal checks (per Skills/humanizer/SKILL.md #30-34 + the
forensic-reviewer checklist):

  1. motif_density         — flag motifs appearing >3x per chapter
  2. metaphor_saturation   — flag paragraphs with 3+ metaphors
  3. four_beat_rhythm      — flag short → metaphorical → restated → emotional
                             paragraph template
  4. recursive_emphasis    — flag paragraphs whose last sentence restates
                             the first
  5. voice_uniformity      — compare sentence-length distributions across
                             dialogue, action, and introspection scenes

Usage:
  python3 scripts/forensic_eval.py                  # all chapters
  python3 scripts/forensic_eval.py --chapter ch_01  # single chapter
  python3 scripts/forensic_eval.py --strict          # warn -> error
  python3 scripts/forensic_eval.py --json            # machine-readable

Outputs:
  eval_logs/<timestamp>_forensic.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import statistics
from collections import Counter
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAPTERS_DIR = ROOT / "chapters"
EVAL_LOGS_DIR = ROOT / "eval_logs"

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------

# Motifs the AI-detection reviewer flagged. Extend per project.
# Each is a case-insensitive regex (substring match).
DEFAULT_MOTIFS = [
    r"the frost (?:behind|in|at) (?:my|her|his|their) eye",
    r"frost (?:prick|behind|prickle)",
    r"the binding hums",
    r"the binding (?:sings|pulses|answers|wakes|warm)",
    r"\bthe map\b",
    r"\bthe territory\b",
    r"\bcartograph(?:y|er|ers)\b",
    r"\bthe silence\b",
    r"\bthe truth\b",
    r"\bverges on creation\b",
    r"\bterritory is a kind of sentence\b",
    r"\bmap is never the territory\b",
    r"\ba kind of (?:border|sentence|threshold|door|map|punctuation)\b",
    r"\blike a (?:held )?breath\b",
    r"\bAwe is a physical thing\b",
    r"\bweight of being seen\b",
    r"\bhorrifying weight\b",
]

# Per-chapter thresholds. If a motif appears > MAX_PER_CHAPTER times
# in one chapter, it's flagged as a tic.
MAX_PER_CHAPTER = 3
# If a motif appears > TOTAL_MAX times across the entire novel, flagged as
# a global tic.
TOTAL_MAX = 25

# Metaphor markers — sentence-level heuristic.
METAPHOR_MARKERS = re.compile(
    r"\b(?:like|as if|as though|was a|was like|were a|were like|"
    r"is a kind of|was a kind of|is the shape of|had the shape of|"
    r"smelled like|tasted like|felt like|looked like)\b",
    re.IGNORECASE,
)

# Sentence splitter.
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'])")
PARA_SPLIT = re.compile(r"\n\s*\n")

# Voice-uniformity: dialogue detection (rough).
DIALOGUE_PARA = re.compile(r"""["\u201c].{6,}?["\u201d]""")
# Voice-uniformity: action detection (rough). Heuristic: paragraph starts
# with a past-tense verb or imperative.
ACTION_OPEN = re.compile(
    r"^(?:[A-Z][a-z]+ed|[A-Z][a-z]+ ?[a-z]+ed|[A-Z][a-z]+ing)\s+"
)
# Voice-uniformity: introspection (first-person).
INTROSPECTION_PARA = re.compile(
    r"\b(?:^|\.\s+)(?:I|Me|My|Mine)\b"
)


# ----------------------------------------------------------------------
# Data structures
# ----------------------------------------------------------------------

@dataclass
class Finding:
    pattern: str
    severity: str  # "error" | "warn" | "info"
    location: str
    excerpt: str
    note: str = ""


@dataclass
class ChapterReport:
    chapter: str
    word_count: int
    findings: list[Finding] = field(default_factory=list)
    score: float = 10.0
    motif_counts: dict = field(default_factory=dict)
    metaphor_heavy_paras: int = 0
    four_beat_paras: int = 0
    recursive_paras: int = 0
    sentence_lengths: dict = field(default_factory=dict)  # by scene type


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in SENT_SPLIT.split(text) if s.strip()]


def split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in PARA_SPLIT.split(text) if p.strip()]


def count_metaphors(text: str) -> int:
    return len(METAPHOR_MARKERS.findall(text))


def classify_paragraph(para: str) -> str:
    """Classify a paragraph as dialogue, action, or introspection.

    Returns "dialogue" | "action" | "introspection" | "mixed".
    Priority: dialogue > action > introspection > mixed.
    """
    if DIALOGUE_PARA.search(para):
        return "dialogue"
    if ACTION_OPEN.match(para):
        return "action"
    if INTROSPECTION_PARA.search(para):
        return "introspection"
    return "mixed"


def is_four_beat(sentences: list[str]) -> tuple[bool, str]:
    """Detect the 4-beat paragraph template.

    Template (from AI-detection review):
      1. Short declarative (<=8 words, no metaphor marker)
      2. Metaphorical elaboration (>=12 words, has metaphor marker)
      3. Restatement (>=6 words, fewer metaphors than beat 2)
      4. Emotional close (often ends "...and that was the X of it" / "of it.")
    """
    if len(sentences) != 4:
        return False, ""

    s1, s2, s3, s4 = sentences
    w1, w2, w3, w4 = (len(s.split()) for s in sentences)
    m1, m2, m3, m4 = (count_metaphors(s) for s in sentences)

    beat1 = w1 <= 8 and m1 == 0
    beat2 = w2 >= 12 and m2 >= 1
    beat3 = w3 >= 6 and m3 < m2

    beat4 = bool(re.search(
        r"\b(?:and that (?:was|is) (?:the )?(?:truth|whole|point|"
        r"long and short|end|of it)|that was (?:enough|the truth|"
        r"the point|the whole)|in the end,? (?:it (?:was|is)|that)|"
        r"which was (?:enough|the truth|the point)|of it\.?$)\b",
        s4, re.IGNORECASE,
    ))

    if beat1 and beat2 and beat3 and beat4:
        return True, "short → metaphor → restatement → 'of it' close"
    return False, ""


def is_recursive(sentences: list[str]) -> tuple[bool, str]:
    """Detect paragraphs whose last sentence restates the first."""
    if len(sentences) < 2:
        return False, ""

    def norm(s: str) -> str:
        s = re.sub(r"[^\w\s]", "", s).lower()
        return re.sub(r"\s+", " ", s).strip()

    a, b = norm(sentences[0]), norm(sentences[-1])
    if not a or not b:
        return False, ""

    # Method 1: high word overlap (Jaccard >= 0.55 with >= 6 word tokens).
    aw, bw = set(a.split()), set(b.split())
    if len(aw) >= 6 and len(bw) >= 6:
        union = aw | bw
        inter = aw & bw
        if union and len(inter) / len(union) >= 0.55:
            return True, f"Jaccard {len(inter)}/{len(union)}"

    # Method 2: last sentence is a recursion-marker restatement.
    recursion_markers = [
        r"\band that (?:was|is) (?:the )?(?:truth|whole|point|long|end)\b",
        r"\bthat was (?:the )?(?:truth|whole|point)\b",
        r"\bin the end,? (?:it (?:was|is)|that)\b",
        r"\bwhich was (?:enough|the truth|the point)\b",
    ]
    last = sentences[-1]
    if any(re.search(p, last, re.IGNORECASE) for p in recursion_markers):
        return True, "recursion marker in last sentence"

    return False, ""


# ----------------------------------------------------------------------
# Scanners
# ----------------------------------------------------------------------

def scan_motif_density(
    text: str, chapter: str, motifs: list[str],
) -> tuple[list[Finding], dict]:
    """Check 1 — motif over-repetition."""
    findings: list[Finding] = []
    counts: dict[str, int] = {}
    text_lower = text.lower()
    for pat in motifs:
        n = len(re.findall(pat, text_lower, re.IGNORECASE))
        if n > 0:
            counts[pat] = n
            if n > MAX_PER_CHAPTER:
                findings.append(Finding(
                    pattern="motif_density",
                    severity="error",
                    location=f"{chapter} ({n} occurrences)",
                    excerpt=pat,
                    note=f"Motif appears {n}x in one chapter (max {MAX_PER_CHAPTER}).",
                ))
    return findings, counts


def scan_metaphor_saturation(
    text: str, chapter: str,
) -> tuple[list[Finding], int]:
    """Check 2 — metaphor-heavy paragraphs."""
    findings: list[Finding] = []
    paragraphs = split_paragraphs(text)
    heavy = 0
    for i, para in enumerate(paragraphs):
        m = count_metaphors(para)
        if m >= 3:
            heavy += 1
            findings.append(Finding(
                pattern="metaphor_saturation",
                severity="warn",
                location=f"{chapter}:¶{i + 1} ({m} metaphors)",
                excerpt=para[:120] + ("..." if len(para) > 120 else ""),
                note=f"Paragraph has {m} metaphor markers (max 2 recommended).",
            ))
    return findings, heavy


def scan_four_beat(
    text: str, chapter: str,
) -> tuple[list[Finding], int]:
    """Check 3 — formulaic 4-beat paragraph rhythm."""
    findings: list[Finding] = []
    paragraphs = split_paragraphs(text)
    flagged = 0
    for i, para in enumerate(paragraphs):
        sents = split_sentences(para)
        hit, reason = is_four_beat(sents)
        if hit:
            flagged += 1
            findings.append(Finding(
                pattern="four_beat_rhythm",
                severity="warn",
                location=f"{chapter}:¶{i + 1}",
                excerpt=" | ".join(s[:40] for s in sents),
                note=f"4-beat template: {reason}.",
            ))
    return findings, flagged


def scan_recursive_emphasis(
    text: str, chapter: str,
) -> tuple[list[Finding], int]:
    """Check 4 — recursive emotional emphasis."""
    findings: list[Finding] = []
    paragraphs = split_paragraphs(text)
    flagged = 0
    for i, para in enumerate(paragraphs):
        sents = split_sentences(para)
        hit, reason = is_recursive(sents)
        if hit:
            flagged += 1
            findings.append(Finding(
                pattern="recursive_emphasis",
                severity="warn",
                location=f"{chapter}:¶{i + 1}",
                excerpt=sents[0][:60] + " ... " + sents[-1][:60],
                note=f"Last sentence restates first ({reason}).",
            ))
    return findings, flagged


def scan_voice_uniformity(
    text: str, chapter: str,
) -> tuple[list[Finding], dict]:
    """Check 5 — sentence-length distribution by scene type."""
    findings: list[Finding] = []
    paragraphs = split_paragraphs(text)

    by_type: dict[str, list[int]] = {
        "dialogue": [], "action": [], "introspection": [], "mixed": [],
    }
    for para in paragraphs:
        kind = classify_paragraph(para)
        sents = split_sentences(para)
        for s in sents:
            by_type[kind].append(len(s.split()))

    # Voice uniformity heuristic: if introspection, action, and dialogue all
    # have std-dev < 4, the prose reads as uniform.
    present = {k: v for k, v in by_type.items() if len(v) >= 4}
    if len(present) >= 2:
        sds = {k: statistics.pstdev(v) for k, v in present.items()}
        if all(sd < 4.0 for sd in sds.values()):
            findings.append(Finding(
                pattern="voice_uniformity",
                severity="warn",
                location=chapter,
                excerpt=", ".join(f"{k}=σ{sds[k]:.1f}" for k in sds),
                note="Sentence-length std-dev is uniform across scene types — "
                     "human prose usually varies.",
            ))

    # Dialogue scenes should average <= 14 words.
    if by_type["dialogue"] and statistics.mean(by_type["dialogue"]) > 14:
        findings.append(Finding(
            pattern="voice_uniformity",
            severity="info",
            location=f"{chapter}:dialogue avg "
                     f"{statistics.mean(by_type['dialogue']):.1f}w",
            excerpt="",
            note="Dialogue scenes average >14 words/sentence — "
                 "may be too literary for speech.",
        ))

    summary = {
        k: {
            "n": len(v),
            "avg": round(statistics.mean(v), 1) if v else 0,
            "sd": round(statistics.pstdev(v), 2) if len(v) >= 2 else 0,
        }
        for k, v in by_type.items()
    }
    return findings, summary


# ----------------------------------------------------------------------
# Per-chapter evaluation
# ----------------------------------------------------------------------

def evaluate_chapter(path: Path, motifs: list[str], strict: bool = False
                     ) -> ChapterReport:
    text = path.read_text(encoding="utf-8")
    chapter = path.name
    words = len(text.split())

    findings: list[Finding] = []
    f1, motif_counts = scan_motif_density(text, chapter, motifs)
    f2, heavy = scan_metaphor_saturation(text, chapter)
    f3, four_beat = scan_four_beat(text, chapter)
    f4, recursive = scan_recursive_emphasis(text, chapter)
    f5, voice = scan_voice_uniformity(text, chapter)

    findings += f1 + f2 + f3 + f4 + f5

    # Score: start at 10, deduct per finding.
    score = 10.0
    for f in findings:
        if f.severity == "error":
            score -= 0.6
        elif f.severity == "warn":
            score -= 0.2
        else:
            score -= 0.05
    score = max(0.0, round(score, 2))

    return ChapterReport(
        chapter=chapter,
        word_count=words,
        findings=findings,
        score=score,
        motif_counts=motif_counts,
        metaphor_heavy_paras=heavy,
        four_beat_paras=four_beat,
        recursive_paras=recursive,
        sentence_lengths=voice,
    )


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--chapter", help="single chapter file (e.g. ch_01)")
    p.add_argument("--strict", action="store_true",
                   help="warn-promotions to errors")
    p.add_argument("--quiet", action="store_true",
                   help="suppress per-finding output")
    p.add_argument("--json", action="store_true",
                   help="machine-readable summary to stdout")
    p.add_argument("--motifs-file",
                   help="path to a JSON list of additional motifs")
    args = p.parse_args()

    if not CHAPTERS_DIR.exists():
        print(f"chapters/ not found at {CHAPTERS_DIR}", file=sys.stderr)
        return 2

    motifs = list(DEFAULT_MOTIFS)
    if args.motifs_file:
        with open(args.motifs_file) as f:
            motifs += json.load(f)

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

    reports = [evaluate_chapter(f, motifs, strict=args.strict)
               for f in chapter_files]

    # Aggregate motif totals across the novel.
    motif_totals: Counter[str] = Counter()
    for r in reports:
        for pat, n in r.motif_counts.items():
            motif_totals[pat] += n
    global_tics = {pat: n for pat, n in motif_totals.items() if n > TOTAL_MAX}

    # Console output.
    if not args.quiet and not args.json:
        total_findings = sum(len(r.findings) for r in reports)
        print(f"Forensic scan: {len(reports)} chapters, {total_findings} findings")
        print()
        print(f"{'Chapter':<12} {'Words':>6} {'Metaphor':>8} {'4Beat':>6} "
              f"{'Recur':>6} {'Score':>6}")
        print("-" * 60)
        for r in reports:
            print(f"{r.chapter:<12} {r.word_count:>6} "
                  f"{r.metaphor_heavy_paras:>8} {r.four_beat_paras:>6} "
                  f"{r.recursive_paras:>6} {r.score:>6.2f}")
        print()
        for r in reports:
            for f in r.findings:
                marker = ("❌" if f.severity == "error" else
                          "⚠️ " if f.severity == "warn" else "ℹ️ ")
                print(f"{marker} [{f.pattern}] {f.location}")
                if f.excerpt:
                    print(f"   {f.excerpt}")
                if f.note:
                    print(f"   → {f.note}")
        if global_tics:
            print()
            print(f"🌐 Global tics (>{TOTAL_MAX}× across the novel):")
            for pat, n in sorted(global_tics.items(),
                                 key=lambda kv: -kv[1]):
                print(f"   {n:>3}×  {pat}")

    # JSON summary.
    summary = {
        "generated_at": datetime.now().isoformat(),
        "chapters_evaluated": len(reports),
        "total_findings": sum(len(r.findings) for r in reports),
        "novel_score": round(
            sum(r.score for r in reports) / max(len(reports), 1), 3),
        "global_tics": global_tics,
        "motif_totals": dict(motif_totals.most_common()),
        "reports": [asdict(r) for r in reports],
    }

    if args.json:
        print(json.dumps(summary, indent=2))

    # Persist report.
    EVAL_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = EVAL_LOGS_DIR / f"{stamp}_forensic.json"
    report_path.write_text(json.dumps(summary, indent=2))
    if not args.json:
        print(f"\nReport written: {report_path.relative_to(ROOT)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())