#!/usr/bin/env python3
"""v6 Perfect Prose Pass - scans chapters for AI-tell patterns."""

import os, re, json
from collections import defaultdict

CHAPTER_DIR = "/home/workspace/Bound-by-Ash-and-Thorn/chapters"
OUTPUT_FILE = "/home/workspace/Bound-by-Ash-and-Thorn/prose_pass_v6_report.md"

BANNED_WORDS = {
    "delve": "dig into, examine", "utilize": "use", "leverage": "use",
    "facilitate": "help, enable", "elucidate": "explain, clarify",
    "embark": "start, begin", "endeavor": "effort, try",
    "encompass": "include, cover", "multifaceted": "complex, varied",
    "tapestry": "(describe the thing)", "testament to": "shows, proves",
    "paradigm": "model, approach", "synergy": "(delete sentence)",
    "holistic": "whole, complete", "catalyze": "trigger, cause, spark",
    "juxtapose": "compare, contrast", "nuanced": "(cut it)",
    "realm": "area, field", "myriad": "many", "plethora": "many",
}

SUSPICIOUS_WORDS = [
    "robust", "comprehensive", "seamless", "cutting-edge", "innovative",
    "streamline", "empower", "foster", "enhance", "elevate", "optimize",
    "pivotal", "intricate", "profound", "resonate", "underscore", "harness",
    "navigate", "cultivate", "bolster", "galvanize", "cornerstone",
    "game-changer", "scalable"
]

FILLER_PATTERNS = [
    r"\bIt's worth noting that\b", r"\bIt's important to note that\b",
    r"\bImportantly,\b", r"\bNotably,\b", r"\bInterestingly,\b",
    r"\bLet's dive into\b", r"\bLet's explore\b", r"\bAs we can see\b",
    r"\bFurthermore,\b", r"\bMoreover,\b", r"\bAdditionally,\b",
    r"\bIn today's (?:fast-paced|digital|modern) world\b",
    r"\bAt the end of the day\b", r"\bIt goes without saying\b",
    r"\bWhen it comes to\b", r"\bOne might argue that\b",
]

EM_DASH = re.compile(r"—")
SENT_SPLIT = re.compile(r'(?<=[.!?])\s+')

def get_paragraphs(text):
    return [p.strip() for p in text.split("\n\n") if p.strip()]

def get_sentences(text):
    return SENT_SPLIT.split(text)

def scan_file(filepath):
    with open(filepath) as f:
        content = f.read()
    name = os.path.basename(filepath)
    results = {"file": name, "issues": [], "stats": {}}
    
    lines = content.split('\n')
    paragraphs = get_paragraphs(content)
    
    # Stats
    total_words = len(content.split())
    total_sentences = len(get_sentences(content))
    total_em_dashes = len(EM_DASH.findall(content))
    
    results["stats"] = {
        "words": total_words,
        "lines": len(lines),
        "paragraphs": len(paragraphs),
        "sentences": total_sentences,
        "em_dashes": total_em_dashes,
        "em_dash_rate": f"{total_em_dashes/total_words*100:.2f}%" if total_words else "0%"
    }
    
    # Check banned words
    for i, line in enumerate(lines, 1):
        for word, replacement in BANNED_WORDS.items():
            if re.search(r'\b' + re.escape(word) + r'\b', line, re.IGNORECASE):
                results["issues"].append({
                    "type": "BANNED_WORD", "severity": "HIGH", "line": i,
                    "word": word, "replacement": replacement,
                    "context": line.strip()[:120]
                })
    
    # Check suspicious words
    for i, line in enumerate(lines, 1):
        for word in SUSPICIOUS_WORDS:
            if re.search(r'\b' + re.escape(word) + r'\b', line, re.IGNORECASE):
                results["issues"].append({
                    "type": "SUSPICIOUS_WORD", "severity": "MEDIUM", "line": i,
                    "word": word, "context": line.strip()[:120]
                })
    
    # Check filler phrases
    for i, line in enumerate(lines, 1):
        for pattern in FILLER_PATTERNS:
            m = re.search(pattern, line, re.IGNORECASE)
            if m:
                results["issues"].append({
                    "type": "FILLER", "severity": "HIGH", "line": i,
                    "phrase": m.group(), "context": line.strip()[:120]
                })
    
    # Check em-dash density per paragraph
    for i, para in enumerate(paragraphs):
        count = len(EM_DASH.findall(para))
        words = len(para.split())
        if words > 0 and count / words > 0.04:
            results["issues"].append({
                "type": "EM_DASH_DENSITY", "severity": "MEDIUM",
                "paragraph": i+1, "em_dashes": count, "words": words,
                "context": para[:200]
            })
    
    # Check sentence length uniformity
    for i, para in enumerate(paragraphs):
        sentences = get_sentences(para)
        if len(sentences) < 4:
            continue
        lengths = [len(s.split()) for s in sentences]
        avg_len = sum(lengths) / len(lengths)
        variance = sum((l - avg_len) ** 2 for l in lengths) / len(lengths)
        std_dev = variance ** 0.5
        if std_dev < 3 and len(sentences) > 5:
            results["issues"].append({
                "type": "UNIFORM_SENTENCES", "severity": "LOW",
                "paragraph": i+1, "sentences": len(sentences),
                "avg": f"{avg_len:.1f}", "std_dev": f"{std_dev:.1f}",
                "context": para[:200]
            })
    
    # Check transition word addiction at paragraph starts
    transition_words = ["However,", "Furthermore,", "Additionally,", "More,",
                        "Nevertheless,", "Consequently,", "Similarly,", "Meanwhile,"]
    consecutive = 0
    for i, para in enumerate(paragraphs):
        first = " ".join(para.split()[:3])
        found = None
        for tw in transition_words:
            if first.startswith(tw):
                found = tw
                break
        if found:
            consecutive += 1
            if consecutive >= 2:
                results["issues"].append({
                    "type": "TRANSITION_CHAIN", "severity": "MEDIUM",
                    "paragraph": i+1, "word": found,
                    "consecutive": consecutive, "context": para[:150]
                })
        else:
            consecutive = 0
    
    # Check "seemed" overuse
    for i, line in enumerate(lines, 1):
        count = len(re.findall(r'\bseemed\b', line, re.IGNORECASE))
        if count >= 2:
            results["issues"].append({
                "type": "SEEMED_OVERUSE", "severity": "LOW", "line": i,
                "count": count, "context": line.strip()[:120]
            })
    
    # Check "not just X but Y" pattern
    for i, line in enumerate(lines, 1):
        if re.search(r'\bnot just\b.+\bbut\b', line, re.IGNORECASE):
            results["issues"].append({
                "type": "NOT_JUST_BUT", "severity": "HIGH", "line": i,
                "context": line.strip()[:120]
            })
    
    return results

def main():
    chapters = sorted([f for f in os.listdir(CHAPTER_DIR) if f.endswith('.md')])
    all_results = []
    
    for ch in chapters:
        filepath = os.path.join(CHAPTER_DIR, ch)
        result = scan_file(filepath)
        all_results.append(result)
    
    # Generate report
    report = []
    report.append("# v6 Perfect Prose Pass Report")
    report.append(f"**Novel: {title}**")
    report.append(f"**Date: 2026-06-27**")
    report.append(f"**Chapters scanned: {len(all_results)}")
    report.append("")
    
    # Summary stats
    total_words = sum(r["stats"]["words"] for r in all_results)
    total_issues = sum(len(r["issues"]) for r in all_results)
    high_issues = sum(1 for r in all_results for i in r["issues"] if i["severity"] == "HIGH")
    med_issues = sum(1 for r in all_results for i in r["issues"] if i["severity"] == "MEDIUM")
    low_issues = sum(1 for r in all_results for i in r["issues"] if i["severity"] == "LOW")
    
    report.append("## Summary")
    report.append(f"- **Total words:** {total_words:,}")
    report.append(f"- **Total issues found:** {total_issues}")
    report.append(f"- 🔴 HIGH severity: {high_issues}")
    report.append(f"- 🟡 MEDIUM severity: {med_issues}")
    report.append(f"- 🟢 LOW severity: {low_issues}")
    report.append("")
    
    # Per-chapter stats
    report.append("## Per-Chapter Statistics")
    report.append("")
    report.append("| Chapter | Words | Lines | Issues | Em-dashes | Em-dash rate |")
    report.append("|---------|-------|-------|--------|-----------|-------------|")
    for r in all_results:
        s = r["stats"]
        issues = len(r["issues"])
        report.append(f"| {r['file']} | {s['words']:,} | {s['lines']} | {issues} | {s['em_dashes']} | {s['em_dash_rate']} |")
    report.append("")
    
    # HIGH severity issues
    if high_issues > 0:
        report.append("## 🔴 HIGH Severity Issues")
        report.append("")
        for r in all_results:
            high = [i for i in r["issues"] if i["severity"] == "HIGH"]
            if high:
                report.append(f"### {r['file']}")
                for issue in high:
                    if issue["type"] == "BANNED_WORD":
                        report.append(f"- **Line {issue['line']}:** Banned word `{issue['word']}` → use `{issue['replacement']}`")
                        report.append(f"  > {issue['context']}")
                    elif issue["type"] == "FILLER":
                        report.append(f"- **Line {issue['line']}:** Filler phrase `{issue['phrase']}` → delete it")
                        report.append(f"  > {issue['context']}")
                    elif issue["type"] == "NOT_JUST_BUT":
                        report.append(f"- **Line {issue['line']}:** LLM crutch pattern `not just X but Y` → restructure")
                        report.append(f"  > {issue['context']}")
                report.append("")
    
    # MEDIUM severity issues
    if med_issues > 0:
        report.append("## 🟡 MEDIUM Severity Issues")
        report.append("")
        for r in all_results:
            med = [i for i in r["issues"] if i["severity"] == "MEDIUM"]
            if med:
                report.append(f"### {r['file']}")
                for issue in med:
                    if issue["type"] == "SUSPICIOUS_WORD":
                        report.append(f"- **Line {issue['line']}:** Suspicious word `{issue['word']}` (check context)")
                        report.append(f"  > {issue['context']}")
                    elif issue["type"] == "EM_DASH_DENSITY":
                        report.append(f"- **Paragraph {issue['paragraph']}:** {issue['em_dashes']} em-dashes in {issue['words']} words (rate: {issue['em_dashes']/issue['words']*100:.1f}%)")
                        report.append(f"  > {issue['context'][:150]}...")
                    elif issue["type"] == "TRANSITION_CHAIN":
                        report.append(f"- **Paragraph {issue['paragraph']}:** {issue['consecutive']} consecutive paragraphs starting with transition word `{issue['word']}`")
                        report.append(f"  > {issue['context'][:100]}...")
                report.append("")
    
    # LOW severity issues
    if low_issues > 0:
        report.append("## 🟢 LOW Severity Issues")
        report.append("")
        for r in all_results:
            low = [i for i in r["issues"] if i["severity"] == "LOW"]
            if low:
                report.append(f"### {r['file']}")
                for issue in low:
                    if issue["type"] == "UNIFORM_SENTENCES":
                        report.append(f"- **Paragraph {issue['paragraph']}:** Sentences suspiciously uniform (avg {issue['avg']}w, σ={issue['std_dev']})")
                    elif issue["type"] == "SEEMED_OVERUSE":
                        report.append(f"- **Line {issue['line']}:** `seemed` appears {issue['count']} times in one line")
                        report.append(f"  > {issue['context']}")
                report.append("")
    
    # Write report
    report_text = "\n".join(report)
    with open(OUTPUT_FILE, 'w') as f:
        f.write(report_text)
    
    print(f"Report written to {OUTPUT_FILE}")
    print(f"Total: {total_words:,} words, {total_issues} issues ({high_issues}H/{med_issues}M/{low_issues}L)")

if __name__ == "__main__":
    main()
