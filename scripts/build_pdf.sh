#!/usr/bin/env bash
# Build the novel PDF from manuscript.md.
#
# Rebuilds manuscript.md from chapters/ first (compile_manuscript.py),
# then renders manuscript.md -> Bound-by-Ash-and-Thorn.pdf with pandoc/xelatex.
# Also produces the lower-case copy (bound-by-ash-and-thorn.pdf) used by the
# attachment pipelines that reference a flat filename.
#
# Layout: 1-inch margins, Latin Modern Roman 12pt, Letter paper.
#
# Usage:
#   bash scripts/build_pdf.sh                # full build
#   bash scripts/build_pdf.sh --skip-compile # assume manuscript.md is current
#
set -euo pipefail

cd "$(dirname "$0")/.."

SKIP_COMPILE=0
for arg in "$@"; do
  case "$arg" in
    --skip-compile) SKIP_COMPILE=1 ;;
    *) echo "Unknown arg: $arg" >&2; exit 2 ;;
  esac
done

if [ "$SKIP_COMPILE" -eq 0 ]; then
  python3 scripts/compile_manuscript.py
fi

# Concatenate front matter (title + copyright) with manuscript body.
{
  cat title_page.md
  cat manuscript.md
} > manuscript_full.md

pandoc manuscript_full.md \
  -o Bound-by-Ash-and-Thorn.pdf \
  --pdf-engine=xelatex \
  --toc \
  --toc-depth=2 \
  -V geometry:margin=1in \
  -V mainfont="Latin Modern Roman"

cp Bound-by-Ash-and-Thorn.pdf bound-by-ash-and-thorn.pdf

rm manuscript_full.md

WORDS=$(pdftotext Bound-by-Ash-and-Thorn.pdf - | wc -w)
PAGES=$(pdfinfo Bound-by-Ash-and-Thorn.pdf | awk '/^Pages:/ {print $2}')

echo "Built Bound-by-Ash-and-Thorn.pdf — ${PAGES} pages, ${WORDS} words"
echo "Mirrored to bound-by-ash-and-thorn.pdf"