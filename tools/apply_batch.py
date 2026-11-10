#!/usr/bin/env python3
"""Apply an ordered list of translations to the blank entries of one story.

    python tools/apply_batch.py --root . hmr_11120100032 my_batch.txt

The text file holds one translation per blank line, in the same order as
tools/dump_context.py prints them.  The count must match exactly, which makes
misalignment impossible to commit by accident.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("story_id")
    parser.add_argument("batch", type=Path)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()

    target = args.root.resolve() / "translations" / "novels" / args.story_id / "zh_Hans.json"
    data = json.loads(target.read_text(encoding="utf-8"))
    blanks = [key for key, value in data.items() if not str(value).strip()]
    lines = [line.strip() for line in args.batch.read_text(encoding="utf-8-sig").splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    if len(lines) != len(blanks):
        raise SystemExit(f"{args.story_id}: {len(lines)} translations vs {len(blanks)} blanks")
    for key, value in zip(blanks, lines):
        if not value:
            raise SystemExit(f"{args.story_id}: empty translation for {key[:60]!r}")
        data[key] = value
    target.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{args.story_id}: filled {len(lines)} entries")


if __name__ == "__main__":
    main()
