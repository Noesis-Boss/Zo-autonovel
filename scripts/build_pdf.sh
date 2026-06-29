#!/usr/bin/env bash
# Generic PDF builder. Builds manuscript.pdf from manuscript.md using pandoc/xelatex.
#
# Usage:
#   bash build_pdf.sh                 # builds manuscript.pdf in current dir
#   bash build_pdf.sh --out my.pdf    # custom output filename
#
# Inputs:
#   manuscript.md          -- compiled markdown (use compile_manuscript.py if
#                             chapters/ contains chapter files)
#   typeset/novel.tex      -- optional LaTeX template (preferred for trade
#                             paperback quality). If present, will use it.
#
# Outputs:
#   manuscript.pdf or <out>.pdf
#
set -euo pipefail

OUT="manuscript.pdf"
SKIP_TEX=0
for arg in "$@"; do
  case "$arg" in
    --out=*) OUT="${arg#--out=}" ;;
    --out) shift; OUT="${1:-manuscript.pdf}" ;;
    --skip-tex) SKIP_TEX=1 ;;
  esac
done

if [[ ! -f manuscript.md ]]; then
  echo "manuscript.md not found. Run compile_manuscript.py first or place manuscript.md here." >&2
  exit 1
fi

if [[ -f typeset/novel.tex && $SKIP_TEX -eq 0 ]]; then
  echo "Using LaTeX template at typeset/novel.tex"
  python3 typeset/build_tex.py
  (cd typeset && tectonic novel.tex)
  cp typeset/novel.pdf "$OUT"
else
  echo "Rendering manuscript.md -> $OUT via pandoc/xelatex"
  pandoc manuscript.md \
    --pdf-engine=xelatex \
    --toc --toc-depth=2 \
    -V geometry:margin=1in \
    -V fontsize=12pt \
    -V documentclass=article \
    -o "$OUT"
fi
echo "Built: $OUT"