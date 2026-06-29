---
name: Zo-autonovel
description: Project-agnostic scaffold for the autonomous novel-writing pipeline. Drop-in templates, framework docs (CRAFT, ANTI-SLOP, ANTI-PATTERNS), LaTeX typeset templates, prose-quality scripts, and the canonical five-layer architecture (voice, world, characters, outline, chapters + canon cross-cutting). Use when the user wants to start, continue, or publish a long-form novel, or when they ask for "autonovel"-style scaffolding.
created-by: Zo Computer (jaknyfe)
---

# Zo-autonovel

A complete, project-agnostic scaffold for producing long-form novels,
portable from any starting seed. Based on the
[NousResearch/autonovel](https://github.com/NousResearch/autonovel)
architecture and integrated into the Zo Computer platform.

## What this is

A reusable framework, not a finished novel. The original autonovel repo
shipped alongside a specific production ("The Second Son of the House of Bells").
This skill is the framework extracted — every project-specific artifact
(story content, hardcoded paths, "Bells" references) has been stripped.
What remains is the **scaffold** that any new novel can be built on.

## The five-layer architecture

```
  Layer 5:  voice.md          — HOW we write (style, tone, vocabulary)
  Layer 4:  world.md          — WHAT exists (lore, magic, geography)
  Layer 3:  characters.md     — WHO acts (registry, arcs, relationships)
  Layer 2:  outline.md        — WHAT HAPPENS (beats, foreshadowing map)
  Layer 1:  chapters/ch_NN.md — THE ACTUAL PROSE
  Cross-cutting: canon.md     — WHAT IS TRUE (hard facts database)
```

Changes propagate both down (lore → outline → chapter) and up
(prose reveals gap → update lore → check downstream). Track these
propagation debts in `state.json`.

## Layout

```
Skills/Zo-autonovel/
├── SKILL.md                    — this file
├── framework/                  — reusable education + automation spec
│   ├── CRAFT.md                — plot/character/world/prose education
│   ├── ANTI-SLOP.md            — word-level AI tells
│   ├── ANTI-PATTERNS.md        — structural AI patterns
│   ├── PIPELINE.md             — full automation spec (4 phases)
│   ├── WORKFLOW.md             — step-by-step human guide
│   └── program.md              — agent instructions per phase
├── templates/                  — empty shells for a new project
│   ├── world.md.tmpl
│   ├── characters.md.tmpl
│   ├── outline.md.tmpl
│   ├── voice.md.tmpl
│   ├── canon.md.tmpl
│   ├── MYSTERY.md.tmpl
│   └── state.json.tmpl
├── scripts/                    — pipeline machinery
│   ├── compile_manuscript.py
│   ├── evaluate.py
│   ├── forensic_eval.py
│   ├── motif_fix.py
│   ├── batch_motif_fix.py
│   ├── prose_pass_v6.py
│   ├── add_page_breaks.py
│   ├── ocr_detector.py
│   ├── strip_em_dashes.py
│   ├── build_pdf.sh            — generic: manuscript.md → manuscript.pdf
│   └── init_novel.sh           — bootstrap a new project with templates
├── typeset/                    — LaTeX + ePub templates
│   ├── novel.tex               — parameterized (\renewcommand{\booktitle}{...})
│   ├── build_tex.py            — ENV-driven (CHAPTERS_DIR, OUT_DIR)
│   ├── epub_metadata.yaml
│   ├── epub_style.css
│   ├── epub_front_matter.md
│   ├── epub_back_cover.md
│   └── epub_colophon.md
├── assets/                     — per-project media (cover, ornaments, audio)
│   └── README.md
└── examples/                   — usage patterns
    └── README.md
```

## Quick start (bootstrapping a new novel)

```bash
# 1. Initialize a new project directory
bash ~/workspace/Skills/Zo-autonovel/scripts/init_novel.sh ~/my-novel
cd ~/my-novel

# 2. Edit seed.txt with your concept, then fill templates
$EDITOR templates/seed.txt
cp ../Skills/Zo-autonovel/templates/world.md.tmpl world.md
cp ../Skills/Zo-autonovel/templates/characters.md.tmpl characters.md
# … etc for outline, voice, canon, MYSTERY, state.json
$EDITOR world.md characters.md outline.md voice.md canon.md MYSTERY.md

# 3. Phase 1: Foundation (loop until foundation_score > 7.5)
# Read framework/PIPELINE.md Phase 1, then iterate

# 4. Phase 2: Drafting (sequential chapters)
mkdir chapters
# Write each chapter using framework/program.md guidance

# 5. Phase 3: Revision cycles
python3 ../Skills/Zo-autonovel/scripts/evaluate.py --chapter=NN
python3 ../Skills/Zo-autonovel/scripts/evaluate.py --adversarial chapters/ch_NN.md
python3 ../Skills/Zo-autonovel/scripts/motif_fix.py chapters/ch_NN.md

# 6. Compile and typeset
python3 ../Skills/Zo-autonovel/scripts/compile_manuscript.py
cd typeset
CHAPTERS_DIR=../chapters OUT_DIR=. python3 ../Skills/Zo-autonovel/typeset/build_tex.py
# Edit novel.tex to set \renewcommand{\booktitle}{Your Title} etc.
tectonic novel.tex   # or: xelatex novel.tex
```

## Phase model

| Phase | Output | Exit criterion |
|-------|--------|----------------|
| 1. Foundation | world/characters/outline/voice/canon/MYSTERY filled | foundation_score > 7.5 AND lore_score > 7.0 |
| 2. First Draft | chapters/ch_01.md … ch_NN.md | every chapter score > 6.0 |
| 3a. Auto Revision | cut logs, panel results, rewritten chapters | score plateau (Δ < 0.5 across 2 cycles) |
| 3b. Opus Review | deep prose-level review + targeted fixes | no major unqualified items remain |
| 4. Export | typeset/novel.pdf, ePub | — |

Full specification: `framework/PIPELINE.md`.

## Provenance

Based on https://github.com/NousResearch/autonovel and integrated into
the Zo Computer platform. Check out
[Zo Computer](https://www.zo.computer/?productId=www.zo.computer&ucc=3PhIcfyf8Vm&celloN=RC5FLg).

Extracted and generalized from a completed long-form novel production
pipeline into a reusable scaffold.

## Requirements

- Python 3.10+
- `pandoc` ≥ 2.17
- `xelatex` (TeX Live) or `tectonic`
- No network, no API keys (scoring is mechanical)
