"""
recaption.py
Rebuilds the caption lines in a script JSON from its narration.

Lines are cut only at punctuation, so a caption never starts or ends in the
middle of a clause. Whole clauses are packed together up to a width budget.

Usage:
    python recaption.py                          # script_jagannath.json in place
    python recaption.py --script other.json
"""
import argparse
import json
import sys
from pathlib import Path

CLAUSE_END = ("।", "?", "!", ".", ",", ":", ";")
TRIM = '"\u201c\u201d\u2018\u2019()'

MIN_WORDS = 4
MAX_WORDS = 11
MAX_CHARS = 52


def clauses(text: str) -> list[str]:
    """Split on punctuation only, keeping the punctuation with its clause."""
    out: list[str] = []
    buf: list[str] = []
    for word in text.replace("—", " — ").split():
        if word == "—":
            if buf:
                out.append(" ".join(buf))
                buf = []
            continue
        buf.append(word)
        if word.rstrip(TRIM).endswith(CLAUSE_END):
            out.append(" ".join(buf))
            buf = []
    if buf:
        out.append(" ".join(buf))
    return out


def _too_long(words: list[str]) -> bool:
    return len(words) > MAX_WORDS or len(" ".join(words)) > MAX_CHARS


def _split_long(words: list[str]) -> list[str]:
    """Only reached when one clause cannot fit on a single line."""
    lines: list[str] = []
    while words:
        take = [words.pop(0)]
        while words and not _too_long(take + words[:1]):
            take.append(words.pop(0))
        lines.append(" ".join(take))
    return lines


def chunk(text: str) -> list[str]:
    lines: list[str] = []
    current: list[str] = []

    for clause in clauses(text):
        words = clause.split()
        if current and _too_long(current + words):
            lines.append(" ".join(current))
            current = []
        if _too_long(words):
            pieces = _split_long(words)
            lines.extend(pieces[:-1])
            current = pieces[-1].split()
        else:
            current += words

    if current:
        lines.append(" ".join(current))

    merged: list[str] = []
    for line in lines:
        short = len(line.split()) < MIN_WORDS
        fits = merged and len(merged[-1]) + len(line) + 1 <= MAX_CHARS + 8
        if short and fits:
            merged[-1] += " " + line
        else:
            merged.append(line)
    return [line.strip() for line in merged if line.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", default="script_jagannath.json")
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    path = Path(args.script)
    data = json.loads(path.read_text(encoding="utf-8"))
    text = data.get("narration") or data["script"]

    before = len(data.get("captions", []))
    captions = chunk(text)
    data["captions"] = captions
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    shortest = min(len(c.split()) for c in captions)
    longest = max(len(c.split()) for c in captions)
    widest = max(len(c) for c in captions)
    clean = sum(1 for c in captions if c.rstrip(TRIM).endswith(CLAUSE_END))
    print(f"{path}: {before} -> {len(captions)} captions")
    print(f"words per line: min {shortest}, max {longest}, widest {widest} chars")
    print(f"lines ending at punctuation: {clean}/{len(captions)}")
    print("sample:")
    for line in captions[:10]:
        print(f"  {line}")


if __name__ == "__main__":
    main()
