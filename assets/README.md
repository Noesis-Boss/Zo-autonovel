# Project assets

This directory is for per-project media assets. The framework does not
ship any prebuilt images, audio, or fonts — those are generated per novel
by the production pipeline (or supplied by the author).

## Typical contents

- `cover/` — full-wrap print cover (PDF), front cover (PNG), back cover (PNG)
- `ornaments/` — per-chapter decorative ornaments (SVG → PDF)
- `audiobook/` — multi-voice audio chapters + assembled MP3
- `epub/` — cover image, glyph art, sidebars

## Generation

The original autonovel project generates these via:
- `gen_art.py` — visual style + cover curation
- `gen_art_directions.py` — diverse art prompts for selection
- `gen_cover_composite.py` / `gen_cover_print.py` — cover assets
- `gen_audiobook_script.py` / `gen_audiobook.py` — narration