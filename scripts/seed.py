#!/usr/bin/env python3
"""
Seed concept generator. Proposes novel concepts ready to drop into seed.txt.

Usage:
  python3 scripts/seed.py                 # 5 new concepts
  python3 scripts/seed.py --n 10          # 10 concepts
  python3 scripts/seed.py --print-1       # print single best
  python3 scripts/seed.py --genre fantasy # constrained genre
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


SYSTEM = """You generate raw seeds for long-form fiction. A seed is four
compact paragraphs:

1. World-differentiator  (the one conceit that makes this world not-any-other)
2. Central tension      (the conflict that drives the protagonist)
3. Cost/constraint      (the price the magic / world exacts)
4. Sensory hook         (one image the opening chapter can lean into)

Output JSON: {"seeds": [{"title": str, "world": str, "tension": str,
  "cost": str, "sensory": str}, ...]}. No commentary."""


def call_claude(prompt: str, model: str = "claude-sonnet-4-5") -> str:
    import httpx
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        sys.exit("ANTHROPIC_API_KEY not set")
    r = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 4096,
            "system": SYSTEM,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["content"][0]["text"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--genre", default="")
    ap.add_argument("--print-1", action="store_true")
    ap.add_argument("--out", type=Path, default=ROOT / "seed_proposals.json")
    args = ap.parse_args()

    genre_clause = f" Genre: {args.genre}." if args.genre else ""
    prompt = (
        f"Propose {args.n} novel seeds.{genre_clause} Vary the conceits "
        "(high-magic, low-magic, science-fantasy, secondary-world, urban-"
        "contemporary, historical, portal-quest, political). Vary stakes."
    )
    raw = call_claude(prompt)
    if raw.startswith("```"):
        raw = raw.strip("`").split("\n", 1)[1].rsplit("```", 1)[0]
    data = json.loads(raw)

    if args.print_1:
        s = data["seeds"][0]
        print(f"# {s['title']}\n")
        print(f"**World:** {s['world']}\n")
        print(f"**Tension:** {s['tension']}\n")
        print(f"**Cost:** {s['cost']}\n")
        print(f"**Sensory:** {s['sensory']}")
    else:
        args.out.write_text(json.dumps(data, indent=2))
        print(f"Wrote {len(data['seeds'])} proposals to {args.out}")
        for i, s in enumerate(data["seeds"], 1):
            print(f"  {i}. {s['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
