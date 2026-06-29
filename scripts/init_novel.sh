#!/usr/bin/env bash
# Scaffold a new project directory using the Zo-autonovel templates.
# Usage: ./init_novel.sh <project-dir>
set -euo pipefail
PROJ="${1:?usage: init_novel.sh <project-dir>}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TMPL="$SCRIPT_DIR/../templates"
mkdir -p "$PROJ/chapters" "$PROJ/edit_logs" "$PROJ/eval_logs" "$PROJ/briefs" "$PROJ/typeset"
cp "$TMPL/voice.md.tmpl" "$PROJ/voice.md"
cp "$TMPL/world.md.tmpl" "$PROJ/world.md"
cp "$TMPL/characters.md.tmpl" "$PROJ/characters.md"
cp "$TMPL/outline.md.tmpl" "$PROJ/outline.md"
cp "$TMPL/canon.md.tmpl" "$PROJ/canon.md"
cp "$TMPL/MYSTERY.md.tmpl" "$PROJ/MYSTERY.md"
cp "$TMPL/state.json.tmpl" "$PROJ/state.json"
echo "Initialized: $PROJ"
echo "Templates from: $TMPL"
ls -la "$PROJ"
