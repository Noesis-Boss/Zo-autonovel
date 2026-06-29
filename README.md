# autonovel-pipeline

Operational pipeline for AI-generated long-form novels — eval, repair, assemble, and render.

## What it does

Takes a folder of `chapters/ch_*.md` files and runs four stages:

1. **Evaluate** — score each chapter for AI tells (duplicate drafts, OCR artifacts, em-dash density, AI vocab, banned phrases, canon violations)
2. **Repair** — apply targeted fixes (em-dash cap, OCR cleanup, motif drift)
3. **Assemble** — concatenate chapters in canonical order into a single `manuscript.md`
4. **Render** — Pandoc + xelatex → print-ready PDF (letter / a4 / 6x9 book trim)

**Key-clean.** No API keys, no LLM calls, no network. Deterministic, reproducible, CI-friendly.

## Quick start

```bash
# 1. Score
python3 scripts/evaluate.py
python3 scripts/evaluate.py --chapter ch_13
python3 scripts/evaluate.py --strict

# 2. Repair
python3 scripts/strip_em_dashes.py chapters/ 0.5
python3 scripts/ocr_detector.py chapters/
python3 scripts/prose_pass_v6.py chapters/
python3 scripts/motif_fix.py chapters/
python3 scripts/batch_motif_fix.py

# 3. Assemble
python3 scripts/compile_manuscript.py
python3 scripts/compile_manuscript.py --check    # CI gate

# 4. Render
bash scripts/build_pdf.sh
bash scripts/build_pdf.sh --skip-compile
python3 scripts/add_page_breaks.py
```

## Project layout convention

```
my-novel/
├── chapters/                # ch_01.md, ch_02.md, …
├── manuscript.md            # generated
├── voice.md                 # banned phrases + canon rules (manual)
├── canon.md                 # world facts (manual)
├── eval_logs/               # timestamped JSON reports
└── my-novel.pdf             # generated
```

## Scoring model

Each chapter starts at **10.0**. Errors deduct 0.5, warnings 0.15. Novel score = chapter average.

| Pattern | Type | Source |
|---|---|---|
| duplicated_drafts | error | humanizer #27 — duplicate paragraphs, three identical sentences |
| ocr_artifacts | error | humanizer #28 — `nothin, ot`-style comma artifacts, doubled words |
| numbering_drift | error | humanizer #29 — multiple Chapter headers, file/header mismatch |
| rule_of_three | warn | humanizer #11 — anaphora triples, "It's not X, it's Y" |
| em_dash_density | warn | humanizer #7 — >2 em dashes per 1000 words |
| ai_vocab | warn | humanizer #8 — delve, foster, testament, … |
| banned | error | `voice.md` |
| canon_violation | error | `voice.md` / `canon.md` |

## Dependencies

- Python 3.10+
- `pandoc` ≥ 2.17
- `xelatex` (TeX Live)
- No network, no API keys.

## Provenance

Extracted from the `Bound by Ash and Thorn` project after successful publication of a 27-chapter, 99,772-word romantasy novel (eval score 9.626/10, 307-page PDF, clean TOC). Refactored for general use. Supersedes `romantasy-autonovel` (the generator scaffold that lives on top of this pipeline).

## License

MIT.
