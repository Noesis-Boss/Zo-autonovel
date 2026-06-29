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
Cross-cutting: canon.md     — WHAT IS TRUE (hard facts database)
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
├── scripts/                    — pipeline machinery
├── typeset/                    — LaTeX + ePub templates
├── assets/                     — per-project media
└── examples/                   — usage patterns
```

## Quick start

```bash
bash Skills/Zo-autonovel/scripts/init_novel.sh ~/my-novel
```

## Scoring

Each chapter starts at **10.0**. Errors deduct 0.5, warnings 0.15.

## Requirements

- Python 3.10+
- pandoc ≥ 2.17
- xelatex (TeX Live) or tectonic

## License

MIT.