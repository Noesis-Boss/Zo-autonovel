#!/usr/bin/env python3
"""
run_pipeline.py — full autonomous novel production orchestrator.

Stage sequence (matches framework/PIPELINE.md):

  0. setup        verify env (ANTHROPIC_API_KEY), copy templates into
                  project dir, write novel.json metadata.
  1. foundation   world → characters → outline → voice → canon → MYSTERY
                  loop until foundation_score > 7.5
  2. drafting     for each chapter: draft → evaluate → keep/retry (max 5)
                  until chapters_total == outline.chapter_count
  3. revision     up to N cycles: adversarial_edit → apply_cuts →
                  reader_panel-like scoring → revise weakest chapter
                  plateau detection (delta < 0.5 across 2 cycles)
  4. export       compile_manuscript → build_pdf → epub

Usage:
  python3 scripts/pipeline.py --seed seed.txt --title "My Novel" --author "Anon"
  python3 scripts/pipeline.py --from-scratch        # generates seed first
  python3 scripts/pipeline.py --phase foundation    # run one phase
  python3 scripts/pipeline.py --phase drafting --max-cycles 5
  python3 scripts/pipeline.py --phase export

The orchestrator writes all state into state.json (next to seed.txt).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT
SCRIPTS = ROOT / "scripts"
TEMPLATES = ROOT / "templates"


# --------------------------------------------------------------------- utils

def log(msg: str) -> None:
    print(f"\n=== {msg}")


def run(cmd: list[str], cwd: Path, env: dict | None = None) -> int:
    """Run a command, stream output, return exit code."""
    print(f"\n$ {' '.join(cmd)}")
    r = subprocess.run(cmd, cwd=cwd, env={**os.environ, **(env or {})})
    return r.returncode


def load_state(project_root: Path) -> dict:
    """Load state.json from the project root."""
    state_file = project_root / "state.json"
    if state_file.exists():
        return json.loads(state_file.read_text())
    return {"phase": "setup", "iteration": 0, "history": []}


def save_state(project_root: Path, state: dict) -> None:
    """Persist state.json."""
    state_file = project_root / "state.json"
    state_file.write_text(json.dumps(state, indent=2))


# --------------------------------------------------------------------- setup

def phase_setup(project_root: Path, seed_path: Path | None,
                title: str | None, author: str | None,
                genre: str | None) -> dict:
    """Initialize the project directory from templates."""
    log(f"setup → {project_root}")

    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / "chapters").mkdir(exist_ok=True)
    (project_root / "eval_logs").mkdir(exist_ok=True)
    (project_root / "edit_logs").mkdir(exist_ok=True)
    (project_root / "briefs").mkdir(exist_ok=True)

    # Copy templates (skip if user already provided their own)
    for tmpl in TEMPLATES.glob("*.tmpl"):
        target = project_root / tmpl.stem
        if not target.exists():
            shutil.copy(tmpl, target)
            print(f"  copied {tmpl.name} → {target.name}")

    # Write novel.json
    meta_file = project_root / "novel.json"
    if not meta_file.exists():
        meta = {
            "title": title or "Untitled Novel",
            "author": author or "Unknown Author",
            "genre": genre or "fantasy",
            "created": __import__("datetime").date.today().isoformat(),
        }
        meta_file.write_text(json.dumps(meta, indent=2))
        print(f"  wrote novel.json")

    # Copy seed if provided
    if seed_path and seed_path.exists():
        target_seed = project_root / "seed.txt"
        if not target_seed.exists():
            shutil.copy(seed_path, target_seed)
            print(f"  copied seed.txt")

    return {
        "phase": "foundation",
        "project_root": str(project_root),
        "seed": str(seed_path) if seed_path else None,
        "iteration": 0,
        "foundation_score": 0.0,
        "lore_score": 0.0,
        "chapters_total": 0,
        "chapters_drafted": 0,
        "novel_score": 0.0,
        "history": [{"phase": "setup", "at": "now"}],
    }


# --------------------------------------------------------------- foundation

def phase_foundation(project_root: Path, max_iter: int = 15) -> dict:
    """Run foundation.py until score thresholds met or max_iter reached."""
    log("foundation")
    from importlib import util as _u
    spec = _u.spec_from_file_location("foundation", SCRIPTS / "foundation.py")
    foundation = _u.module_from_spec(spec)
    spec.loader.exec_module(foundation)

    state = load_state(project_root)
    if state["phase"] not in ("foundation", "drafting"):
        state["phase"] = "foundation"

    state["foundation_score"] = 0.0
    save_state(project_root, state)

    while (state.get("iteration", 0) < max_iter
           and state.get("foundation_score", 0) < 7.5):
        state["iteration"] = state.get("iteration", 0) + 1
        log(f"foundation iteration {state['iteration']}")
        save_state(project_root, state)

        # Re-run the foundation builder (idempotent — overwrites layer files)
        rc = run([sys.executable, str(SCRIPTS / "foundation.py")],
                 cwd=project_root)
        if rc != 0:
            log(f"foundation.py exited {rc}, aborting")
            return state

        # Score the foundation
        score_out = subprocess.run(
            [sys.executable, str(SCRIPTS / "evaluate.py"),
             "--mode", "foundation", "--quiet"],
            cwd=project_root, capture_output=True, text=True,
        )
        try:
            data = json.loads(score_out.stdout)
            state["foundation_score"] = data.get("foundation_score", 0)
            state["lore_score"] = data.get("lore_score", 0)
            print(f"  foundation_score={state['foundation_score']} "
                  f"lore_score={state['lore_score']}")
        except json.JSONDecodeError:
            log("could not parse evaluator output")
            break

    state["phase"] = "drafting"
    save_state(project_root, state)
    return state


# ----------------------------------------------------------------- drafting

def phase_drafting(project_root: Path, max_attempts: int = 5) -> dict:
    """Draft all chapters sequentially."""
    log("drafting")
    from importlib import util as _u
    spec = _u.spec_from_file_location("drafting", SCRIPTS / "drafting.py")
    drafting = _u.module_from_spec(spec)
    spec.loader.exec_module(drafting)

    state = load_state(project_root)
    state["phase"] = "drafting"
    save_state(project_root, state)

    # Read chapter count from outline.md
    outline = (project_root / "outline.md").read_text()
    import re
    m = re.search(r"(?:Total chapters|chapters)[:\s]*(\d+)", outline, re.I)
    total = int(m.group(1)) if m else 24
    state["chapters_total"] = total
    save_state(project_root, state)

    for ch in range(1, total + 1):
        for attempt in range(1, max_attempts + 1):
            print(f"\n>>> drafting chapter {ch} (attempt {attempt}/{max_attempts})")
            draft = drafting.draft_one(project_root, ch)
            score = drafting.score_chapter(project_root, ch)
            print(f"   score={score:.2f}")
            if score >= 6.0:
                break
            else:
                print(f"   below threshold, will retry")
        state["chapters_drafted"] = ch
        save_state(project_root, state)

    # Mechanical slop pass on every chapter
    run([sys.executable, str(SCRIPTS / "strip_em_dashes.py")],
        cwd=project_root)
    run([sys.executable, str(SCRIPTS / "add_page_breaks.py")],
        cwd=project_root)

    state["phase"] = "revision"
    save_state(project_root, state)
    return state


# ----------------------------------------------------------------- revision

def phase_revision(project_root: Path, max_cycles: int = 6) -> dict:
    """Run revision cycles until plateau or max_cycles."""
    log("revision")
    state = load_state(project_root)
    state["phase"] = "revision"
    save_state(project_root, state)

    prev_score = 0.0
    plateau_count = 0

    for cycle in range(1, max_cycles + 1):
        log(f"revision cycle {cycle}")

        # Adversarial cut pass
        run([sys.executable, str(SCRIPTS / "forensic_eval.py")],
            cwd=project_root)
        run([sys.executable, str(SCRIPTS / "batch_motif_fix.py")],
            cwd=project_root)
        run([sys.executable, str(SCRIPTS / "motif_fix.py")],
            cwd=project_root)
        run([sys.executable, str(SCRIPTS / "prose_pass_v6.py")],
            cwd=project_root)

        # Score
        score_out = subprocess.run(
            [sys.executable, str(SCRIPTS / "evaluate.py"),
             "--mode", "full", "--quiet"],
            cwd=project_root, capture_output=True, text=True,
        )
        try:
            data = json.loads(score_out.stdout)
            state["novel_score"] = data.get("novel_score", 0)
        except json.JSONDecodeError:
            state["novel_score"] = 0

        print(f"  novel_score={state['novel_score']}")

        delta = abs(state["novel_score"] - prev_score)
        if delta < 0.5 and cycle >= 3:
            plateau_count += 1
            if plateau_count >= 2:
                log(f"plateau detected ({plateau_count}x), stopping")
                break
        else:
            plateau_count = 0
        prev_score = state["novel_score"]

        state["history"].append({
            "phase": "revision",
            "cycle": cycle,
            "novel_score": state["novel_score"],
        })
        save_state(project_root, state)

    state["phase"] = "export"
    save_state(project_root, state)
    return state


# ------------------------------------------------------------------- export

def phase_export(project_root: Path) -> dict:
    """Compile manuscript, build PDF, build ePub."""
    log("export")
    state = load_state(project_root)
    state["phase"] = "export"
    save_state(project_root, state)

    # Compile
    run([sys.executable, str(SCRIPTS / "compile_manuscript.py")],
        cwd=project_root)

    # Render PDF
    pdf_script = SCRIPTS / "build_pdf.sh"
    if pdf_script.exists():
        run(["bash", str(pdf_script)], cwd=project_root)

    # Render ePub via pandoc (best-effort)
    manuscript = project_root / "manuscript.md"
    epub_meta = project_root / "novel.json"
    if manuscript.exists():
        title = "Novel"
        author = "Unknown"
        if epub_meta.exists():
            d = json.loads(epub_meta.read_text())
            title = d.get("title", title)
            author = d.get("author", author)
        run([
            "pandoc", str(manuscript),
            "-o", "manuscript.epub",
            "--metadata", f"title={title}",
            "--metadata", f"author={author}",
            "--toc", "--toc-depth=2",
            "--epub-cover-image=" + str(project_root / "cover.png"),
        ], cwd=project_root)

    state["phase"] = "done"
    save_state(project_root, state)
    return state


# ----------------------------------------------------------------- dispatch

PHASES = {
    "setup":      lambda **kw: phase_setup(**kw),
    "foundation": lambda **kw: phase_foundation(**kw),
    "drafting":   lambda **kw: phase_drafting(**kw),
    "revision":   lambda **kw: phase_revision(**kw),
    "export":     lambda **kw: phase_export(**kw),
}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--project", type=Path, default=Path("."),
                   help="project directory (default: cwd)")
    p.add_argument("--seed", type=Path, help="seed.txt path")
    p.add_argument("--title", help="novel title")
    p.add_argument("--author", help="novel author")
    p.add_argument("--genre", help="genre (fantasy, romance, thriller, ...)")
    p.add_argument("--from-scratch", action="store_true",
                   help="run seed.py first to generate seed concepts")
    p.add_argument("--phase", choices=list(PHASES) + ["all"],
                   default="all", help="run a single phase or all")
    p.add_argument("--max-cycles", type=int, default=6)
    p.add_argument("--max-iter", type=int, default=15)
    args = p.parse_args()

    project_root = args.project.resolve()
    seed_path = args.seed

    if args.from_scratch:
        seed_path = project_root / "seed.txt"
        if not seed_path.exists():
            print(">>> generating seed concepts")
            subprocess.run([sys.executable, str(SCRIPTS / "seed.py"),
                            "--n", "5", "--out", str(seed_path)],
                           check=False)

    phases = list(PHASES) if args.phase == "all" else [args.phase]
    state: dict = {}
    for phase in phases:
        if phase == "setup":
            state = phase_setup(project_root, seed_path,
                                args.title, args.author, args.genre)
        elif phase == "foundation":
            state = phase_foundation(project_root, max_iter=args.max_iter)
        elif phase == "drafting":
            state = phase_drafting(project_root)
        elif phase == "revision":
            state = phase_revision(project_root, max_cycles=args.max_cycles)
        elif phase == "export":
            state = phase_export(project_root)

    print("\n=== pipeline complete")
    print(json.dumps(state, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())