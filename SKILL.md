---
name: Zo-autonovel
description: Operational pipeline for AI-generated long-form novels — eval, repair, assemble, and render. Scans chapter .md files for AI tells (duplicate drafts, OCR artifacts, em-dash density, AI vocab, canon/banned phrases), applies targeted prose repairs, concatenates into a single manuscript, and produces a print-ready PDF via Pandoc + xelatex. Use when the user wants to QC, polish, or publish an existing chapter-based novel draft, or when they ask to "evaluate my chapters", "fix the AI tells", "compile the manuscript", or "build the novel PDF".
---

## What it does

Takes a folder of chapter `.md` files and runs four stages:

1. **Evaluate** — score each chapter against a rule set (AI tells, canon, banned phrases)
2. **Repair** — apply targeted fixes for OCR artifacts, em-dash density, motif drift
3. **Assemble** — concatenate chapters (with placeholders stripped) into one manuscript
4. **Render** — Pandoc + xelatex → PDF (letter / a4 / 6x9 book trim)

The pipeline is **key-clean**: no API keys, no LLM calls, no network. Deterministic, reproducible, CI-friendly.

## Quick start

From a project root that has `chapters/ch_*.md`:

```bash
# 1. Score
python3 scripts/evaluate.py                # full pass → eval_logs/*.json
python3 scripts/evaluate.py --chapter ch_13
python3 scripts/evaluate.py --strict       # promote warnings → errors

# 2. Repair
python3 scripts/strip_em_dashes.py chapters/ 0.5   # cap em-dash density
python3 scripts/ocr_detector.py chapters/        # OCR-artifact repair pass
python3 scripts/prose_pass_v6.py chapters/        # targeted prose polish
python3 scripts/motif_fix.py chapters/            # motif consistency
python3 scripts/batch_motif_fix.py                # batch motif fix across all chapters

# 3. Assemble
python3 scripts/compile_manuscript.py            # write manuscript.md
python3 scripts/compile_manuscript.py --check    # CI: exit 1 if out of date

# 4. Render
bash scripts/build_pdf.sh                        # full rebuild + PDF
bash scripts/build_pdf.sh --skip-compile         # render only
python3 scripts/add_page_breaks.py               # ensure chapter starts land on new pages
```

## Scripts

| Script | Purpose |
|---|---|
| `evaluate.py` | Per-chapter AI-tell scorer (errors -0.5, warnings -0.15) |
| `forensic_eval.py` | Deep forensic pass: duplicate drafts, rule-of-three, numbering drift |
| `ocr_detector.py` | Repair OCR artifacts (`nothin,ot`-style, doubled words) |
| `prose_pass_v6.py` | Targeted prose-level polish |
| `motif_fix.py` | Motif consistency repairs |
| `batch_motif_fix.py` | Motif-batch runner |
| `strip_em_dashes.py` | Cap em-dash density (default: 2 per 1000 words) |
| `compile_manuscript.py` | Canonical-order chapter → manuscript.md |
| `add_page_breaks.py` | Ensure chapter sections start on new pages |
| `build_pdf.sh` | manuscript.md → PDF via pandoc + xelatex |

## Scoring model

Each chapter starts at **10.0**. Deductions:

| Pattern | Type | Source |
|---|---|---|
| duplicated_drafts | error (-0.5) | three identical sentences, echo paragraphs |
| ocr_artifacts | error (-0.5) | `nothin, ot`-style comma artifacts, doubled words |
| numbering_drift | error (-0.5) | multiple Chapter headers, file/header mismatch |
| rule_of_three | warn (-0.15) | anaphora triples, "It's not X, it's Y" |
| em_dash_density | warn (-0.15) | >2 em dashes per 1000 words |
| ai_vocab | warn (-0.15) | delve, foster, testament, … |
| banned | error (-0.5) | `voice.md` banned phrases |
| canon_violation | error (-0.5) | `voice.md` / `canon.md` contradictions |

Novel score = chapter average. Floor 0.

## Project layout convention

```
my-novel/
├── chapters/                # ch_01.md, ch_02.md, … (alphanumeric sort)
├── manuscript.md            # generated
├── voice.md                 # banned phrases + canon rules (manual)
├── canon.md                 # world facts (manual)
├── eval_logs/               # timestamped JSON reports
└── my-novel.pdf             # generated
```

## Dependencies

- Python 3.10+
- `pandoc` ≥ 2.17
- `xelatex` (TeX Live)
- No network, no API keys.

## Provenance

Based on https://github.com/NousResearch/autonovel and integrated into the Zo Computer platform. Check out [Zo Computer](https://www.zo.computer/?productId=www.zo.computer&ucc=3PhIcfyf8Vm&celloN=RC5FLg).

Extracted and generalized from a completed long-form novel production pipeline. Project-agnostic: no embedded novel-specific identifiers, chapter counts, word counts, or scoring baselines.
