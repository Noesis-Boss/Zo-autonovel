#!/usr/bin/env python3
"""
Novel manuscript evaluator.

Operationalizes the humanizer skill patterns for this novel. Scans every
chapter in chapters/ for AI tells, scores each finding, and writes a JSON
report to eval_logs/. Designed to run before every revision pass.

Categories (mirrors Skills/humanizer/SKILL.md pattern numbers):
  - duplicated_drafts     (#27)
  - ocr_artifacts         (#28)
  - numbering_drift       (#29)
  - rule_of_three         (#11, incl. anaphora triples)
  - em_dash_density       (#7)
  - ai_vocab              (#8)
  - banned_phrases        (voice.md specific)
  - copula_avoidance      (#9)

Usage:
  python3 scripts/evaluate.py              # scan all chapters
  python3 scripts/evaluate.py --chapter ch_01   # single file
  python3 scripts/evaluate.py --strict     # warn at lower thresholds
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict

ROOT = Path(__file__).resolve().parent.parent
CHAPTERS_DIR = ROOT / "chapters"
EVAL_LOGS_DIR = ROOT / "eval_logs"

# ---------------------------------------------------------------------------
# Pattern definitions
# ---------------------------------------------------------------------------

# AI vocabulary from humanizer #8, extended with the romance-fantasy
# words that recurred in v4 passes.
AI_VOCAB = [
    r"\bpivotal\b", r"\btestament\b", r"\bdelve[s]?\b", r"\bfoster[s]?\b",
    r"\bgarner[s]?\b", r"\binterplay\b", r"\bintricate\b",
    r"\bunderscore[s]?\b", r"\bshowcase[s]?\b", r"\bvibrant\b",
    r"\bbreath-taking\b", r"\bbreath taking\b", r"\benduring\b",
    r"\bIn the heart of\b", r"\blandscape\b(?=.*(?:abstract|emotional|narrative))",
    r"\bAdditionally\b", r"\bMoreover\b", r"\bFurthermore\b",
    r"\bever[\s-]evolving\b", r"\bnestled\b", r"\bcommitment to\b",
]

# Phrases voice.md flags as banned for this novel specifically.
BANNED_PHRASES = [
    r"\bweight of being seen\b",
    r"\bverges on creation\b",
    r"\bhorrifying weight\b",
    r"\bhonesty of it is a stark line\b",
    r"\bAwe is a physical thing\b",
    r"\bmap is never the territory\b",
    r"\bVegetative entities\b",
    r"\bprevious consort collapsed\b",
    r"\bI cannot lie to you\b",  # canon-violation: should be "have never managed to"
]

# Patterns specific to this novel's canon — these are flagged if they
# appear out of permitted context.
CANON_VIOLATIONS = [
    (r"\bI cannot lie to you\b",
     "Use: 'I have never managed to lie to you'"),
    (r"\bI have seen it there\b",
     "He never read her journal — use binding-sensed warm coordinate"),
]


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
    em_dash_count: int
    em_dash_per_kw: float
    findings: list[Finding] = field(default_factory=list)
    score: float = 10.0  # 10 = clean, decremented per finding


# ---------------------------------------------------------------------------
# Scanners
# ---------------------------------------------------------------------------

# Pattern for an anaphora triple: same 2-4 word opener at the start of
# three consecutive sentences.
ANAPHORA_OPEN = re.compile(r"^([A-Z][a-zA-Z']{1,5}(?:\s+[a-zA-Z']{1,5}){0,3})\b")
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE_SPLIT.split(text) if s.strip()]


def scan_duplicated_drafts(text: str, chapter: str) -> list[Finding]:
    """#27 — duplicated paragraphs or repeated sentence runs."""
    findings: list[Finding] = []
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    # Duplicate paragraphs (ignoring whitespace and trailing punctuation)
    seen: dict[str, int] = {}
    for i, p in enumerate(paragraphs):
        norm = re.sub(r"\s+", " ", p).rstrip(".!?")
        if len(norm) < 40:
            continue
        if norm in seen:
            findings.append(Finding(
                pattern="duplicated_drafts",
                severity="error",
                location=f"{chapter}:¶{seen[norm] + 1} & ¶{i + 1}",
                excerpt=norm[:120] + ("..." if len(norm) > 120 else ""),
                note="Duplicate paragraph — likely a leftover draft fragment.",
            ))
        else:
            seen[norm] = i

    # Consecutive identical or near-identical sentences
    sents = _split_sentences(text)
    for i in range(2, len(sents)):
        a = re.sub(r"\W+", "", sents[i - 2]).lower()
        b = re.sub(r"\W+", "", sents[i - 1]).lower()
        c = re.sub(r"\W+", "", sents[i]).lower()
        if a and a == b == c:
            findings.append(Finding(
                pattern="duplicated_drafts",
                severity="error",
                location=f"{chapter}:sent[{i - 2}:{i + 1}]",
                excerpt=sents[i][:120],
                note="Three identical sentences in a row.",
            ))
        elif a and a == c and len(a) > 20:
            findings.append(Finding(
                pattern="duplicated_drafts",
                severity="warn",
                location=f"{chapter}:sent[{i - 2}] == sent[{i}]",
                excerpt=sents[i][:120],
                note="Repeated sentence with one sentence between (echo pattern).",
            ))
    return findings


def scan_ocr_artifacts(text: str, chapter: str) -> list[Finding]:
    """#28 — OCR-like transcription artifacts.

    Delegates to scripts/ocr_detector.py — a high-precision detector
    that matches the specific OCR signature found in the v4 pass
    (split words connected by a comma: 'nothin, ot', 'the, ot',
    'joinin, an') which is distinct from normal prose.
    """
    findings: list[Finding] = []
    try:
        # When invoked as a module: `python3 -m scripts.evaluate`
        from scripts.ocr_detector import find_ocr_artifacts as _find
    except ImportError:
        # When invoked directly: `python3 scripts/evaluate.py`
        sys.path.insert(0, str(Path(__file__).parent))
        from ocr_detector import find_ocr_artifacts as _find
    _results = _find(text)
    for d in _results:
        findings.append(Finding(
            pattern="ocr_artifacts",
            severity="error",
            location=f"{chapter}:offset {d['offset']}",
            excerpt=d['excerpt'],
            note=d['note'],
        ))
    return findings


def scan_numbering_drift(text: str, chapter: str, all_chapter_files: list[str]) -> list[Finding]:
    """#29 — chapter numbering drift."""
    findings: list[Finding] = []
    headers = re.findall(r"(?im)^#\s*Chapter\s+(\d+)\b", text)
    if len(headers) > 1:
        findings.append(Finding(
            pattern="numbering_drift",
            severity="error",
            location=chapter,
            excerpt=", ".join(f"Chapter {n}" for n in headers),
            note="Multiple Chapter headers in one file.",
        ))
    elif len(headers) == 1:
        # File is named ch_NN — verify it matches
        file_match = re.search(r"ch_(\d+)", chapter)
        if file_match:
            file_n = int(file_match.group(1))
            header_n = int(headers[0])
            if file_n != header_n:
                findings.append(Finding(
                    pattern="numbering_drift",
                    severity="error",
                    location=chapter,
                    excerpt=f"File=ch_{file_n:02d}, Header=Chapter {header_n}",
                    note="File name and chapter header disagree.",
                ))
    return findings


def scan_rule_of_three(text: str, chapter: str) -> list[Finding]:
    """#11 + anaphora triples."""
    findings: list[Finding] = []
    sents = _split_sentences(text)

    # Anaphora triples
    i = 0
    while i < len(sents) - 2:
        a = ANAPHORA_OPEN.match(sents[i])
        b = ANAPHORA_OPEN.match(sents[i + 1])
        c = ANAPHORA_OPEN.match(sents[i + 2])
        if a and b and c:
            opener = a.group(1)
            if a.group(1) == b.group(1) == c.group(1) and len(opener) >= 3:
                findings.append(Finding(
                    pattern="rule_of_three",
                    severity="warn",
                    location=f"{chapter}:sent[{i}:{i + 3}]",
                    excerpt=f"{sents[i][:60]} | {sents[i + 1][:60]} | {sents[i + 2][:60]}",
                    note=f"Anaphora triple starting '{opener}'.",
                ))
                i += 3
                continue
        i += 1

    # Not-just-it's-also negative parallelisms
    for m in re.finditer(r"\bIt'?s not (?:just|merely|only) [^,.!?]+,?\s+it'?s\b",
                          text, flags=re.IGNORECASE):
        findings.append(Finding(
            pattern="rule_of_three",
            severity="warn",
            location=f"{chapter}:offset {m.start()}",
            excerpt=m.group(0),
            note="Negative parallelism ('It's not X, it's Y').",
        ))
    return findings


def scan_em_dashes(text: str) -> tuple[int, float]:
    """#7 — em-dash density."""
    count = len(re.findall(r"—", text))
    words = len(text.split())
    density = (count / max(words, 1)) * 1000
    return count, density


def scan_ai_vocab(text: str, chapter: str) -> list[Finding]:
    """#8 — AI vocabulary density."""
    findings: list[Finding] = []
    for pat in AI_VOCAB:
        for m in re.finditer(pat, text, flags=re.IGNORECASE):
            ctx = text[max(0, m.start() - 30):m.end() + 30].replace("\n", " ")
            findings.append(Finding(
                pattern="ai_vocab",
                severity="warn",
                location=f"{chapter}:offset {m.start()}",
                excerpt=ctx,
                note=f"AI vocabulary: /{pat}/",
            ))
    return findings


def scan_banned(text: str, chapter: str) -> list[Finding]:
    findings: list[Finding] = []
    for pat in BANNED_PHRASES:
        for m in re.finditer(pat, text):
            findings.append(Finding(
                pattern="banned",
                severity="error",
                location=f"{chapter}:offset {m.start()}",
                excerpt=text[max(0, m.start() - 30):m.end() + 30].replace("\n", " "),
                note="Banned by voice.md.",
            ))
    for pat, fix in CANON_VIOLATIONS:
        for m in re.finditer(pat, text):
            findings.append(Finding(
                pattern="canon_violation",
                severity="error",
                location=f"{chapter}:offset {m.start()}",
                excerpt=text[max(0, m.start() - 30):m.end() + 30].replace("\n", " "),
                note=fix,
            ))
    return findings


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def evaluate_chapter(path: Path, all_chapter_files: list[str],
                     strict: bool = False) -> ChapterReport:
    text = path.read_text(encoding="utf-8")
    chapter = path.name
    words = len(text.split())

    em_count, em_density = scan_em_dashes(text)
    findings: list[Finding] = []
    findings += scan_duplicated_drafts(text, chapter)
    findings += scan_ocr_artifacts(text, chapter)
    findings += scan_numbering_drift(text, chapter, all_chapter_files)
    findings += scan_rule_of_three(text, chapter)
    findings += scan_ai_vocab(text, chapter)
    findings += scan_banned(text, chapter)

    # Em-dash threshold: 2 per kw is the humanizer #7 ceiling.
    if em_density > 2.0:
        findings.append(Finding(
            pattern="em_dash_density",
            severity="warn" if not strict else "error",
            location=chapter,
            excerpt=f"{em_count} em dashes / {words} words = {em_density:.2f} per kw",
            note="Em-dash density exceeds 2.0/kw threshold.",
        ))

    # Score: start at 10, deduct per finding
    score = 10.0
    for f in findings:
        score -= 0.5 if f.severity == "error" else 0.15
    score = max(0.0, round(score, 2))

    return ChapterReport(
        chapter=chapter,
        word_count=words,
        em_dash_count=em_count,
        em_dash_per_kw=round(em_density, 3),
        findings=findings,
        score=score,
    )


# ---------------------------------------------------------------------------
# Foundation / full-novel scoring (LLM judge)
# ---------------------------------------------------------------------------

FOUNDATION_FILES = ["world.md", "characters.md", "outline.md",
                    "voice.md", "canon.md", "MYSTERY.md"]


def evaluate_foundation(strict: bool = False) -> Dict:
    """Score the foundation layer (world, characters, outline, voice, canon, mystery)
    via Claude Opus as literary judge.

    Returns dict with foundation_score, lore_score, weakest_dimension, report_path.
    """
    from anthropic import Anthropic

    materials = []
    for name in FOUNDATION_FILES:
        p = ROOT / name
        if p.exists():
            materials.append((name, p.read_text()[:8000]))  # 8k cap per file
        else:
            materials.append((name, ""))
    if not any(c for _, c in materials):
        return {"foundation_score": 0.0, "lore_score": 0.0,
                "weakest_dimension": "presence",
                "report": "no foundation files"}

    system = (
        "You are a literary fiction editor evaluating the foundation "
        "documents (world bible, character registry, outline, voice, "
        "canon, central mystery) of an in-progress fantasy novel. Score "
        "the foundation on a 0-10 scale across these dimensions, then "
        "identify the single weakest dimension.\n\n"
        "Dimensions (each 0-10):\n"
        "  lore_interconnection — magic affects politics, history explains "
        "factions, geography shapes culture. The deeper the cross-layer "
        "links, the higher the score.\n"
        "  character_specificity — wounds/wants/needs/lies are concrete, "
        "speech patterns distinct, arcs are non-generic.\n"
        "  outline_tension — central tension is clear, cost/constraint "
        "is real, foreshadowing ledger is plausible, beats escalate.\n"
        "  voice_consistency — guardrails in voice.md part 1 are present, "
        "and there is enough in part 2 (or a foundation of trial passages) "
        "to steer prose away from AI defaults.\n"
        "  canon_coverage — hard-facts database cross-references world, "
        "characters, and outline so the prose cannot contradict itself.\n"
        "  mystery_clarity — there is a clear central secret the reader "
        "discovers at climax and it recontextualizes earlier events.\n\n"
        "Output strictly as JSON:\n"
        '{"lore": <num>, "characters": <num>, "outline": <num>, '
        '"voice": <num>, "canon": <num>, "mystery": <num>, '
        '"comments": "<one paragraph>", '
        '"weakest_dimension": "<one of lore/characters/outline/voice/canon/mystery>", '
        '"top_suggestion": "<single concrete next-iteration fix>"}'
    )
    user = "Foundation materials:\n\n"
    for name, text in materials:
        user += f"=== {name} ===\n{text}\n\n"

    client = Anthropic()
    resp = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=2000,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    raw = resp.content[0].text.strip()
    # extract json
    import re as _re
    m = _re.search(r"\{.*\}", raw, _re.S)
    if not m:
        return {"foundation_score": 0.0, "lore_score": 0.0,
                "weakest_dimension": "parse", "raw": raw}
    data = json.loads(m.group(0))
    dims = ["lore", "characters", "outline", "voice", "canon", "mystery"]
    scores = [float(data.get(d, 0)) for d in dims]
    foundation_score = round(sum(scores) / len(scores), 3)
    lore_score = float(data.get("lore", 0))
    EVAL_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = EVAL_LOGS_DIR / f"{stamp}_foundation.json"
    report_path.write_text(json.dumps({
        "generated_at": datetime.now().isoformat(),
        "mode": "foundation",
        "foundation_score": foundation_score,
        "lore_score": lore_score,
        "weakest_dimension": data.get("weakest_dimension"),
        "top_suggestion": data.get("top_suggestion"),
        "comments": data.get("comments"),
        "dimensions": dict(zip(dims, scores)),
    }, indent=2))
    return {
        "foundation_score": foundation_score,
        "lore_score": lore_score,
        "weakest_dimension": data.get("weakest_dimension"),
        "top_suggestion": data.get("top_suggestion"),
        "report": report_path,
    }


def evaluate_full(strict: bool = False) -> Dict:
    """Novel-level score after all chapters drafted + revised.

    Sends the arc summary + sample paragraphs to Opus for a holistic read.
    """
    from anthropic import Anthropic
    summary_p = ROOT / "arc_summary.md"
    if not summary_p.exists():
        return {"novel_score": 0.0, "note": "no arc_summary.md"}
    # Concatenate chapter excerpts
    chapter_files = sorted(
        f for f in (ROOT / "chapters").iterdir()
        if f.suffix == ".md" and f.name.startswith("ch_")
    )
    if not chapter_files:
        return {"novel_score": 0.0, "note": "no chapters drafted"}
    samples = []
    for cf in chapter_files:
        # Take first 400 + last 200 words of each chapter
        words = cf.read_text().split()
        if len(words) > 600:
            excerpt = " ".join(words[:400] + ["..."] + words[-200:])
        else:
            excerpt = " ".join(words)
        samples.append(f"=== {cf.name} ===\n{excerpt}")
    system = (
        "You are a literary fiction editor reading an entire fantasy "
        "novel in progress. Score it 0-10 on these dimensions, then "
        "identify the single weakest:\n"
        "  theme_coherence, voice_consistency, foreshadowing_payoff, "
        "  character_life, pacing_curve, prose_quality.\n\n"
        "Output strictly as JSON:\n"
        '{"theme": <num>, "voice": <num>, "foreshadowing": <num>, '
        '"character": <num>, "pacing": <num>, "prose": <num>, '
        '"comments": "<paragraph>", '
        '"weakest_chapter": "ch_NN", '
        '"top_suggestion": "<one fix>", '
        '"would_recommend": true/false}'
    )
    user = f"=== ARC SUMMARY ===\n{summary_p.read_text()}\n\n" + \
        "\n\n".join(samples)
    client = Anthropic()
    resp = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=2500,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    raw = resp.content[0].text.strip()
    import re as _re
    m = _re.search(r"\{.*\}", raw, _re.S)
    if not m:
        return {"novel_score": 0.0, "raw": raw}
    data = json.loads(m.group(0))
    dims = ["theme", "voice", "foreshadowing", "character", "pacing", "prose"]
    scores = [float(data.get(d, 0)) for d in dims]
    novel_score = round(sum(scores) / len(scores), 3)
    EVAL_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = EVAL_LOGS_DIR / f"{stamp}_full.json"
    report_path.write_text(json.dumps({
        "generated_at": datetime.now().isoformat(),
        "mode": "full",
        "novel_score": novel_score,
        "weakest_chapter": data.get("weakest_chapter"),
        "top_suggestion": data.get("top_suggestion"),
        "would_recommend": data.get("would_recommend"),
        "comments": data.get("comments"),
        "dimensions": dict(zip(dims, scores)),
    }, indent=2))
    return {
        "novel_score": novel_score,
        "weakest_chapter": data.get("weakest_chapter"),
        "top_suggestion": data.get("top_suggestion"),
        "report": report_path,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--chapter", help="single chapter file (e.g. ch_01)")
    p.add_argument("--mode", choices=["chapter", "foundation", "full"],
                   default="chapter",
                   help="chapter=per-file scan (default); foundation=LLM-judge foundation docs; "
                        "full=novel-level LLM read")
    p.add_argument("--strict", action="store_true",
                   help="warn-promotions to errors")
    p.add_argument("--quiet", action="store_true",
                   help="suppress per-finding output")
    args = p.parse_args()

    EVAL_LOGS_DIR.mkdir(parents=True, exist_ok=True)

    if args.mode == "foundation":
        result = evaluate_foundation(strict=args.strict)
        print(json.dumps({k: str(v) if hasattr(v, "name") else v
                          for k, v in result.items()}, indent=2))
        return 0

    if args.mode == "full":
        result = evaluate_full(strict=args.strict)
        print(json.dumps({k: str(v) if hasattr(v, "name") else v
                          for k, v in result.items()}, indent=2))
        return 0

    if not CHAPTERS_DIR.exists():
        print(f"chapters/ not found at {CHAPTERS_DIR}", file=sys.stderr)
        return 2

    chapter_files = sorted(
        f for f in CHAPTERS_DIR.iterdir()
        if f.suffix == ".md" and f.name.startswith("ch_")
    )
    if args.chapter:
        chapter_files = [f for f in chapter_files if f.name.startswith(args.chapter)]
        if not chapter_files:
            print(f"No chapter matches {args.chapter}", file=sys.stderr)
            return 2

    all_files = [f.name for f in chapter_files]
    reports = [evaluate_chapter(f, all_files, strict=args.strict)
               for f in chapter_files]

    # Console output
    if not args.quiet:
        total_findings = sum(len(r.findings) for r in reports)
        print(f"Evaluated {len(reports)} chapters, {total_findings} findings")
        print()
        print(f"{'Chapter':<12} {'Words':>6} {'Em/kw':>7} {'Score':>6}  Findings")
        print("-" * 60)
        for r in reports:
            errors = sum(1 for f in r.findings if f.severity == "error")
            warns = sum(1 for f in r.findings if f.severity == "warn")
            print(f"{r.chapter:<12} {r.word_count:>6} "
                  f"{r.em_dash_per_kw:>7.3f} {r.score:>6.2f}  "
                  f"{errors}E + {warns}W")
        print()

        # Detail
        for r in reports:
            for f in r.findings:
                marker = "❌" if f.severity == "error" else "⚠️ "
                print(f"{marker} [{f.pattern}] {f.location}")
                print(f"   {f.excerpt}")
                if f.note:
                    print(f"   → {f.note}")

    # Write report
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = EVAL_LOGS_DIR / f"{stamp}_evaluate.json"
    report_path.write_text(json.dumps(
        {
            "generated_at": datetime.now().isoformat(),
            "chapters_evaluated": len(reports),
            "total_findings": sum(len(r.findings) for r in reports),
            "novel_score": round(
                sum(r.score for r in reports) / max(len(reports), 1), 3),
            "reports": [asdict(r) for r in reports],
        },
        indent=2,
    ))
    print(f"\nReport written: {report_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
