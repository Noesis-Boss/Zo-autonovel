#!/usr/bin/env python3
"""
Phase 1: Foundation. Loop until foundation_score > threshold.

Sequence per iteration:
  1. weakest = empty (or last eval callout)
  2. regen the weakest layer with seed+canon as context
  3. cross-reference: append any new hard facts to canon.md
  4. score: run Scripts/Zo-autonovel/scripts/evaluate.py --phase=foundation
  5. commit if improved; revert otherwise

Usage:
  python3 scripts/foundation.py                # full loop to threshold
  python3 scripts/foundation.py --max 5        # at most 5 iterations
  PROJECT_ROOT=/path/to/novel python3 scripts/foundation.py
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from state import State, advance, load, project_root

SKILL_DIR = Path(__file__).resolve().parent.parent
EVAL_SCRIPT = SKILL_DIR / "scripts" / "evaluate.py"
TEMPLATES = SKILL_DIR / "templates"


# Foundation layer targets (label, file, template)
LAYERS = [
    ("world", "world.md", "world.md.tmpl"),
    ("characters", "characters.md", "characters.md.tmpl"),
    ("outline", "outline.md", "outline.md.tmpl"),
    ("voice", "voice.md", "voice.md.tmpl"),
    ("canon", "canon.md", "canon.md.tmpl"),
    ("MYSTERY", "MYSTERY.md", "MYSTERY.md.tmpl"),
]


def call_claude(prompt: str, system: str) -> str:
    from llm import chat
    return chat([{"role": "user", "content": prompt}],
                system=system, max_tokens=8000, timeout=180)


def init_from_seed(seed_text: str, root: Path) -> None:
    """First iteration: build all six layers from seed."""
    canon = (root / "canon.md").read_text() if (root / "canon.md").exists() else ""
    for label, target, tmpl in LAYERS:
        dst = root / target
        if dst.exists():
            continue
        template = (TEMPLATES / tmpl).read_text()
        sysmsg = (f"You expand a fiction seed into the {label} layer "
                  f"({target}). Cross-reference canon.md when present.\n\n"
                  f"Template structure:\n{template}\n\n"
                  f"Seed:\n{seed_text}\n\n"
                  f"Existing canon:\n{canon}")
        out = call_claude(
            f"Produce {target}. Keep canon-linked facts consistent. "
            f"Only output the file content, no preamble.",
            sysmsg,
        )
        # strip leading code-fence wrapper if model emits one
        if out.startswith("```"):
            out = out.strip("`").split("\n", 1)[1].rsplit("```", 1)[0]
        dst.write_text(out)
        print(f"  wrote {target}")


def regenerate(target: str, root: Path, weakness: str, seed_text: str) -> None:
    canon = (root / "canon.md").read_text() if (root / "canon.md").exists() else ""
    others = "\n\n".join(
        (root / t[1]).read_text() for t in LAYERS if t[1] != target and (root / t[1]).exists()
    )
    template = (TEMPLATES / f"{Path(target).name}.tmpl").read_text()
    out = call_claude(
        f"Strengthen {target}. Weakness to address: {weakness}. "
        f"Maintain canon consistency.\n\n"
        f"Template:\n{template}\n\nOther layers:\n{others}\n\n"
        f"Seed:\n{seed_text}\n\nCanon:\n{canon}\n\n"
        f"Output the full {target}.",
        f"You revise a fiction {target} layer while keeping the others intact.",
    )
    if out.startswith("```"):
        out = out.strip("`").split("\n", 1)[1].rsplit("```", 1)[0]
    (root / target).write_text(out)


def score_foundation(root: Path) -> tuple[float, float, str]:
    """Run evaluate.py --phase=foundation. Parse last JSON stdout."""
    proc = subprocess.run(
        [sys.executable, str(EVAL_SCRIPT), "--phase=foundation", "--json"],
        cwd=root, capture_output=True, text=True,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return 0.0, 0.0, ""
    last = proc.stdout.strip().splitlines()[-1]
    import json
    try:
        data = json.loads(last)
    except json.JSONDecodeError:
        return 0.0, 0.0, ""
    return (
        float(data.get("foundation_score", 0.0)),
        float(data.get("lore_score", 0.0)),
        str(data.get("weakest_dimension", "")),
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=15)
    ap.add_argument("--threshold", type=float, default=7.5)
    ap.add_argument("--lore-threshold", type=float, default=7.0)
    args = ap.parse_args()

    root = project_root()
    seed_path = root / "seed.txt"
    if not seed_path.exists():
        sys.exit(f"missing seed.txt in {root}")
    seed_text = seed_path.read_text()

    state = load()
    state.chapters_total = 0
    advance(state, msg=f"foundation started (max {args.max})")

    print("== Phase 1: Foundation ==")
    init_from_seed(seed_text, root)
    state.iteration = 1

    while state.iteration <= args.max:
        fs, ls, weak = score_foundation(root)
        state.foundation_score = fs
        state.lore_score = ls
        state.weakest_dimension = weak
        advance(state, msg=f"iter {state.iteration}: f={fs:.2f} lore={ls:.2f} weak={weak}")

        if fs >= args.threshold and ls >= args.lore_threshold:
            print(f"foundation ok: f={fs:.2f} lore={ls:.2f} iter={state.iteration}")
            break

        print(f"iter {state.iteration}: f={fs:.2f} weak={weak} → regen weakest layer")
        target_map = {
            "world": "world.md", "characters": "characters.md",
            "outline": "outline.md", "voice": "voice.md",
            "mystery": "MYSTERY.md", "canon": "canon.md",
        }
        target = target_map.get(weak, "outline.md")
        regenerate(target, root, weak or "thinness", seed_text)
        state.iteration += 1

    advance(state, phase="drafting", msg=f"foundation done at iter {state.iteration}")
    return 0 if state.foundation_score >= args.threshold else 1


if __name__ == "__main__":
    raise SystemExit(main())
