# Zo-autonovel

Project-agnostic scaffold for AI-generated long-form novels on the Zo Computer platform.

## What this is

A reusable framework, not a finished novel. Extracted from a completed production pipeline and generalized for any new novel.

## The five-layer architecture

```
Layer 5:  voice.md          — HOW we write (style, tone, vocabulary)
Layer 4:  world.md          — WHAT exists (lore, magic, geography)
Layer 3:  characters.md     — WHO acts (registry, arcs, relationships)
Layer 2:  outline.md        — WHAT HAPPENS (beats, foreshadowing map)
Layer 1:  chapters/ch_NN.md — THE ACTUAL PROSE
Cross-cutting: canon.md      — WHAT IS TRUE (hard facts database)
```

## Layout

```
Skills/Zo-autonovel/
├── SKILL.md                    — skill specification
├── framework/                  — education + automation spec
│   ├── CRAFT.md                — plot/character/world/prose education
│   ├── ANTI-SLOP.md            — word-level AI tells
│   ├── ANTI-PATTERNS.md        — structural AI patterns
│   ├── PIPELINE.md             — full automation spec (4 phases)
│   ├── WORKFLOW.md             — step-by-step human guide
│   └── program.md              — agent instructions per phase
├── templates/                  — empty shells for new projects
│   ├── world.md.tmpl
│   ├── characters.md.tmpl
│   ├── outline.md.tmpl
│   ├── voice.md.tmpl
│   ├── canon.md.tmpl
│   ├── MYSTERY.md.tmpl
│   └── state.json.tmpl
├── scripts/                    — pipeline machinery
│   ├── evaluate.py             — mechanical slop scorer
│   ├── forensic_eval.py        — deep evaluation
│   ├── motif_fix.py            — AI pattern repairs
│   ├── batch_motif_fix.py      — batch repairs
│   ├── prose_pass_v6.py        — prose refinements
│   ├── compile_manuscript.py   — assemble chapters
│   ├── add_page_breaks.py      — PDF pagination
│   ├── ocr_detector.py         — OCR artifact cleanup
│   ├── strip_em_dashes.py      — em-dash normalization
│   ├── build_pdf.sh            — pandoc → PDF
│   ├── init_novel.sh           — bootstrap new project
│   ├── pipeline.py             — orchestrator
│   ├── foundation.py           — Phase 1 foundation
│   ├── drafting.py             — Phase 2 drafting
│   ├── seed.py                 — seed generation
│   ├── state.py                — state management
│   ├── llm.py                  — LLM interface
│   └── claude_api.py           — Claude API helpers
├── typeset/                    — LaTeX + ePub templates
│   ├── novel.tex               — parameterized template
│   ├── build_tex.py            — chapters → LaTeX
│   ├── epub_metadata.yaml
│   ├── epub_style.css
│   ├── epub_front_matter.md
│   ├── epub_back_cover.md
│   └── epub_colophon.md
├── assets/                     — per-project media
│   └── README.md
└── examples/                   — usage patterns
    └── README.md
```

## Phase model

| Phase | Output | Exit criterion |
|-------|--------|----------------|
| 1. Foundation | world.md, characters.md, outline.md, voice.md, canon.md, MYSTERY.md | foundation_score > 7.5 AND lore_score > 7.0 |
| 2. First Draft | chapters/ch_01.md … ch_NN.md | every chapter score > 6.0 |
| 3a. Auto Revision | cut logs, panel results, rewritten chapters | score plateau (Δ < 0.5 across 2 cycles) |
| 3b. Opus Review | deep prose-level review + targeted fixes | no major unqualified items remain |
| 4. Export | typeset/novel.pdf, ePub | — |

Full specification: `framework/PIPELINE.md`

## Quick start

```bash
bash Skills/Zo-autonovel/scripts/init_novel.sh ~/my-novel
```

## Scoring model

Each chapter starts at **10.0**. Errors deduct 0.5, warnings 0.15. Novel score = chapter average.

| Pattern | Type |
|---|---|
| duplicated_drafts | error |
| ocr_artifacts | error |
| numbering_drift | error |
| rule_of_three | warn |
| em_dash_density | warn |
| ai_vocab | warn |
| banned | error |
| canon_violation | error |

## Requirements

- Python 3.10+
- pandoc ≥ 2.17
- xelatex (TeX Live) or tectonic

## Provenance

Based on https://github.com/NousResearch/autonovel and integrated into the Zo Computer platform.