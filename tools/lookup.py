#!/usr/bin/env python3
"""Search the whole translation tree for a Japanese or Chinese string.

    python tools/lookup.py --root . 聖騎士
    python tools/lookup.py --root . 星界爆能枪

Prints where the string lives (story id, or static table/field) and its
translation, so you can tell whether an in-game text is covered by this pack.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

MAX_LEN = 100


def short(text: str, limit: int = MAX_LEN) -> str:
    text = text.replace("\n", "\\n")
    return text if len(text) <= limit else text[:limit] + "…"


def iter_leaves(node, path=""):
    if isinstance(node, dict):
        for key, value in node.items():
            yield from iter_leaves(value, f"{path}/{key}" if path else str(key))
    else:
        yield path, node


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("query")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--limit", type=int, default=40)
    args = parser.parse_args()

    root = args.root.resolve() / "translations"
    q = args.query
    hits = 0

    def report(where: str, source: str, target: str) -> None:
        nonlocal hits
        hits += 1
        if hits > args.limit:
            return
        print(f"[{where}]")
        print(f"  日: {short(source)}")
        print(f"  中: {short(target)}")

    # novels: {"日文": "中文"}
    for path in sorted((root / "novels").glob("*/zh_Hans.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for source, target in data.items():
            if q in source or q in str(target):
                report(f"novels/{path.parent.name}", source, str(target))
        if hits > args.limit:
            break

    # static: table -> field -> {日文: 中文}
    static = root / "static" / "zh_Hans.json"
    if static.is_file():
        for path, value in iter_leaves(json.loads(static.read_text(encoding="utf-8"))):
            if not isinstance(value, str):
                continue
            parts = path.split("/")
            if len(parts) == 3 and (q in parts[2] or q in value):
                report(f"static/{parts[0]}/{parts[1]}", parts[2], value)
            elif not path.count("/") and (q in value or q in path):
                report("static", path, value)

    # flat maps: names / ui_texts
    for section in ("names", "ui_texts"):
        path = root / section / "zh_Hans.json"
        if not path.is_file():
            continue
        for source, target in json.loads(path.read_text(encoding="utf-8")).items():
            if q in source or q in str(target):
                report(f"{section}", source, str(target))

    print(f"\n{hits} hit(s)" + (f", showing first {args.limit}" if hits > args.limit else ""))
    if hits == 0:
        print("没有找到：这句可能不在当前翻译包里（新增内容 / 内部字段）。")


if __name__ == "__main__":
    main()
