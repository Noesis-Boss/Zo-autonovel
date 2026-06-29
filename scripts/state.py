"""
state.py — shared pipeline state.

stage managers call advance(state, phase=...) to commit progress and
load() to bootstrap at the start of a stage.

Filesystem layout per project:
  <project>/
    state.json               pipeline tracker
    seed.txt                 chosen concept
    world.md / characters.md / outline.md / canon.md / MYSTERY.md / voice.md
    chapters/ch_NN.md        prose
    briefs/*.md              revision inputs
    edit_logs/*.json         adversarial / panel results
    eval_logs/*.json         evaluate.py + forensic_eval.py output
    typeset/novel.pdf        output
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

DEFAULT_PHASES = ("foundation", "drafting", "revision", "export", "done")


@dataclass
class State:
    phase: str = "foundation"
    iteration: int = 0
    foundation_score: float = 0.0
    lore_score: float = 0.0
    chapters_total: int = 0
    chapters_drafted: int = 0
    novel_score: float = 0.0
    weakest_dimension: str = ""
    debts: list[str] = field(default_factory=list)
    log: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        data = asdict(self)
        if not data.get("meta"):
            data.pop("meta", None)
        return data


def project_root() -> Path:
    """Project root = $PROJECT_ROOT env var, else cwd."""
    env = os.environ.get("PROJECT_ROOT")
    return Path(env).resolve() if env else Path.cwd()


def load(path: Optional[Path] = None) -> State:
    path = path or project_root() / "state.json"
    if not path.exists():
        return State()
    raw = json.loads(path.read_text())
    known = {f.name for f in State.__dataclass_fields__.values()}
    data = {k: v for k, v in raw.items() if k in known}
    meta = {k: v for k, v in raw.items() if k not in known}
    state = State(**data)
    if meta:
        state.meta = meta
    return state


def save(state: State, path: Optional[Path] = None) -> Path:
    path = path or project_root() / "state.json"
    path.write_text(json.dumps(state.to_dict(), indent=2))
    return path


def advance(state: State, *, msg: str = "", **patch) -> State:
    """Apply patch, append log line, return updated state."""
    for k, v in patch.items():
        setattr(state, k, v)
    if msg:
        stamp = time.strftime("%H:%M:%S")
        state.log.append(f"[{stamp}] {msg}")
    save(state)
    return state
