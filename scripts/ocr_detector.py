"""OCR artifact detector — standalone, testable.

Conservative detector for the specific OCR signature found in the v4 pass.
Returns findings as a list of dicts with keys: excerpt, note, offset.
"""
import re

# Words that legitimately follow a comma — exclude these from "fragment" detection
COMMON_POST_COMMA = frozenset({
    'a', 'an', 'the', 'and', 'but', 'or', 'for', 'nor', 'yet', 'so',
    'of', 'in', 'on', 'at', 'to', 'as', 'is', 'was', 'be', 'by',
    'it', 'its', 'my', 'no', 'up', 'if', 'he', 'we', 'then',
    'when', 'who', 'this', 'that', 'these', 'those',
    'i', 'you', 'they', 'she', 'her', 'his', 'their', 'our',
    'one', 'two', 'first', 'second', 'not', 'with', 'from', 'into',
    'about', 'between', 'through', 'over', 'under', 'after', 'before',
    'where', 'while', 'because', 'since', 'than',
})

# Common words that end in TRUNCATED_ENDINGS but are NOT truncated forms
REAL_ENDING_IN = frozenset({
    'main', 'certain', 'captain', 'mountain', 'villa',
    'thin', 'skin', 'spin', 'win', 'tin', 'kin', 'fin', 'pin', 'bin',
    'din', 'gin', 'lin', 'min', 'sin', 'gain', 'pain', 'rain',
    'lain', 'rein', 'vein', 'coin', 'loin', 'join', 'boil', 'soil',
    'toil', 'foil', 'coil', 'spoil', 'broil', 'twin', 'swing', 'sting',
    'ring', 'bring', 'king', 'thing', 'spring', 'string', 'fling',
    'begin', 'within', 'skin', 'begin', 'origin', 'margin', 'pigeon',
    'religion', 'companion', 'opinion', 'onion', 'union', 'billion',
    'million', 'cushion', 'fashion', 'passion', 'session', 'mission',
    'vision', 'prison', 'poison', 'reason', 'season', 'treason',
    'pigeon', 'dragon', 'wagon', 'beacon', 'deacon', 'melon', 'felon',
    'salon', 'galleon', 'champion', 'scorpion', 'clarion', 'minion',
    'siren', 'specimen', 'cairn', 'bairn', 'vern', 'kern',
    'precision',
})

TRUNCATED_ENDINGS = ('in', 'an', 'en', 'on', 'un')


def find_ocr_artifacts(text: str) -> list[dict]:
    """Find OCR-like split-word artifacts.

    Returns list of dicts with: offset, excerpt, note.
    """
    findings = []
    # Pattern: any word, comma, then 1-3 char word. We post-filter.
    for m in re.finditer(r'(\b[A-Za-z]+\b)\s*,\s+(\b[A-Za-z]+\b)', text):
        word_before = m.group(1).lower()
        word_after = m.group(2).lower()

        # Word after comma must be 1-3 chars (the "ot", "an", "ta" pattern)
        if len(word_after) > 3:
            continue
        # Word after comma must NOT be in common list
        if word_after in COMMON_POST_COMMA:
            continue

        # Word before comma must look truncated:
        #   (a) ends in a stripped ending like 'in', 'an' AND is NOT a real word
        #   (b) is itself 1-3 chars (like 'the' before 'ot' — short word + tiny frag)
        is_truncated_real = word_before in REAL_ENDING_IN
        ends_in_truncated = (
            word_before.endswith(TRUNCATED_ENDINGS)
            and len(word_before) >= 4
            and not is_truncated_real
        )
        is_short_word = len(word_before) <= 3

        if not (ends_in_truncated or is_short_word):
            continue

        # Intentional prose-rhythm allow-list: phrases like
        # "out, raw", "me, wet", "yes, yes", "now, too", "us, too",
        # "see, now", "in, too", "low, dry", "old, dry", "pen, dip",
        # "map, let", "jaw, are", "red, are", "eiran, me", "eye, hot",
        # "it, set", "map, are", "map, all", "he, too".
        # These are authorial rhythm — comma + sensory/descriptive fragment
        # where word_before is a complete real word, not a truncated verb form.
        INTENTIONAL_RHYTHM_BEFORE = frozenset({
            'out', 'me', 'yes', 'now', 'us', 'see', 'in', 'no', 'old',
            'dry', 'low', 'pen', 'map', 'air', 'jaw', 'eiran', 'red',
            'precision', 'eye', 'it', 'he', 'man', 'time', 'door',
            'room', 'today', 'way', 'place', 'side', 'mind', 'end', 'part',
            'rest', 'back', 'face', 'case', 'sort', 'kind', 'thing', 'half',
            'hour', 'moment', 'morning', 'evening', 'night', 'day', 'week',
            'month', 'year', 'too',
        })
        # Only suppress when word_before is INTENTIONAL and NOT truncated.
        # If it ends in a truncated ending (mov, lik, fo, etc.), still flag.
        if word_before in INTENTIONAL_RHYTHM_BEFORE and not ends_in_truncated:
            continue

        # Found a candidate — record it
        snippet = text[max(0, m.start() - 25):m.end() + 25].replace('\n', ' ')
        findings.append({
            'offset': m.start(),
            'excerpt': snippet,
            'note': f"Split-word candidate: '{word_before}, {word_after}'",
        })
    return findings


def scan_ocr_artifacts(text: str) -> list[dict]:
    """Scan text for OCR artifacts and return findings.

    Returns list of dicts with: offset, excerpt, note, severity.
    """
    findings = find_ocr_artifacts(text)
    result = []
    for f in findings:
        result.append({
            'offset': f['offset'],
            'excerpt': f['excerpt'],
            'note': f['note'],
            'severity': 'medium',
        })
    return result


if __name__ == '__main__':
    import sys
    import argparse
    parser = argparse.ArgumentParser(description='OCR artifact detector for novel chapters')
    parser.add_argument('files', nargs='*', help='Files to scan (default: all chapters/*.md)')
    parser.add_argument('--check', action='store_true', help='Exit 1 if artifacts found (for CI/pre-commit)')
    parser.add_argument('--json', action='store_true', help='Emit JSON output instead of human-readable')
    args = parser.parse_args()

    if args.files:
        files = args.files
    else:
        import glob
        files = sorted(glob.glob('chapters/*.md'))

    all_findings = []
    for f in files:
        with open(f) as fh:
            text = fh.read()
        for finding in find_ocr_artifacts(text):
            finding['file'] = f
            all_findings.append(finding)

    if args.json:
        import json
        print(json.dumps(all_findings, indent=2))
    else:
        for finding in all_findings:
            print(f"{finding['file']}:{finding['offset']}: {finding['note']}")
            print(f"  {finding['excerpt']}")
        print(f"\n{len(all_findings)} findings across {len(files)} files")

    if args.check and all_findings:
        sys.exit(1)
    sys.exit(0)