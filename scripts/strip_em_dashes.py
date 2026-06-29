#!/usr/bin/env python3
"""Strip excess em-dashes from chapter prose.

Goal: ≤2 em-dashes per 1000 words per chapter.
"""
import re, glob, sys

PATTERNS = [
    # "— phrase —" parenthetical aside (em-dash pair)
    (re.compile(r'(\w[\w\.\,\;\']*?)\s—\s([^\n—]+?)\s—\s(\w)'),
     r'\1, \2, \3'),
    # "word — Aside" trailing appositive (capital next, end with punct)
    (re.compile(r'(\w[\w\.\,\;\']*?)\s—\s([A-Z][^\n]+?)([\.\!\?\,\;\:]|$)'),
     r'\1: \2\3'),
    # "word — aside" trailing appositive (lowercase next)
    (re.compile(r'(\w[\w\.\,\;\']*?)\s—\s([a-z][^\n]+?)([\.\!\?\,\;\:]|$)'),
     r'\1, \2\3'),
    # Em-dash at sentence start, capital next
    (re.compile(r'(^|\n)\s*—\s*([A-Z])'),
     r'\1\2'),
    # Em-dash at sentence start, lowercase next
    (re.compile(r'(^|\n)\s*—\s*([a-z])'),
     r'\1\2'),
    # Lone beat: " — " → ", "
    (re.compile(r'\s—\s'),
     r', '),
]

def strip(text, max_per_kw=1.8):
    for pat, repl in PATTERNS:
        text = pat.sub(repl, text)
    # Hard cap remaining em-dashes per chapter
    em_positions = [m.start() for m in re.finditer('—', text)]
    words_now = len(text.split())
    budget = max(1, int(words_now / 1000 * max_per_kw))
    over = len(em_positions) - budget
    if over > 0:
        skip = 2  # rhythm allowance
        to_convert = em_positions[skip:skip+over]
        for pos in reversed(to_convert):
            text = text[:pos] + ',' + text[pos+1:]
    return text

def main():
    files = sorted(glob.glob('chapters/ch_*.md'))
    if len(sys.argv) > 1:
        files = [f for f in files if any(s in f for s in sys.argv[1:])]
    for f in files:
        text = open(f).read()
        new = strip(text)
        if new != text:
            open(f, 'w').write(new)
            print(f"  rewrote {f.split('/')[-1]}")
        else:
            print(f"  unchanged {f.split('/')[-1]}")

if __name__ == '__main__':
    main()