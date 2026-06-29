# Examples

This directory contains worked examples and references for the Zo-autonovel
scaffold. The framework is project-agnostic; use these as templates when
setting up your own novel project.

## Suggested project layout

```
my-novel/
├── manuscript.md           # compiled from chapters/ for PDF build
├── chapters/
│   ├── 01-prologue.md
│   ├── 02-chapter-one.md
│   └── ...
├── world.md                # layer 4
├── characters.md           # layer 3
├── outline.md              # layer 2 (with foreshadowing ledger)
├── voice.md                # layer 5 (guardrails + identity)
├── canon.md                # cross-cutting hard facts
├── MYSTERY.md              # central mystery (author-only)
├── state.json              # pipeline state tracker
├── results.tsv             # experiment log
├── arc_summary.md          # chapter summaries
├── edit_logs/              # adversarial cuts, panel results, tournament
├── eval_logs/              # full evaluation results
├── briefs/                 # revision briefs
├── art/                    # cover, ornaments (see assets/README.md)
├── audiobook/              # generated audio
└── typeset/
    ├── novel.tex           # parameterize with \renewcommand{\booktitle}{...}
    └── build_tex.py        # CHAPTERS_DIR=./chapters OUT_DIR=./typeset
```

## Common usage

```bash
# 1. Compile manuscript from chapters
python3 scripts/compile_manuscript.py

# 2. Score the manuscript
python3 scripts/evaluate.py --full

# 3. Find adversarial cuts
python3 scripts/evaluate.py --adversarial chapters/*.md

# 4. Strip mechanical AI tells (em-dashes, banned words)
python3 scripts/strip_em_dashes.py chapters/*.md
python3 scripts/motif_fix.py chapters/*.md

# 5. Build