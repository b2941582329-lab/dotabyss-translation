#!/usr/bin/env python3
"""Rebuild novels/<id>/zh_Hans.json from an AssetStudio TextAsset dump.

Use this after a game update:

    python tools/rebuild_from_dump.py --root . --dump-dir "D:/导出/TextAsset" \
        --cache-dir "D:/game/BepInEx/plugins/AbyssMod/cache"

Existing translations in this repository are kept. New source lines are added
with an empty value and listed in <root>/new-lines.json so they can be
translated (blank values are reported by tools/build_manifest.py).
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

NAME_RE = re.compile(r'string m_Name = "([^"]+)"')
STORY_RE = re.compile(r"[a-z]+_\d+")
TEXT_COMMANDS = ("message", "l2dmessage", "dotmessage", "messageTextCenter", "messageTextUnder")
TRAILER_RE = re.compile(
    r"(?:(?:,\d{6,}[A-Za-z0-9]*)|(?:,vc_[A-Za-z0-9_]+)|(?:,mcv_[A-Za-z0-9_]+)"
    r"|(?:,mca_[A-Za-z0-9_]+)|(?:,,?chara_\d+(?:/chara_\d+)*)|(?:,\d/chara_\d+)"
    r"|(?:,on)|(?:,off))+$"
)


def strip_trailer(text: str) -> str:
    previous = None
    while previous != text:
        previous = text
        text = TRAILER_RE.sub("", text)
    return text


def load_map(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items() if isinstance(v, str) and v.strip()}


def pool_from(directory: Path, recursive: bool) -> dict[str, str]:
    pool: dict[str, str] = {}
    if not directory.is_dir():
        return pool
    paths = directory.rglob("zh_Hans.json") if recursive else directory.glob("*.json")
    for path in sorted(paths):
        for key, value in load_map(path).items():
            pool.setdefault(key, value)
    return pool


def parse_dump(dump: Path) -> dict[str, list[str]]:
    stories: dict[str, list[str]] = {}
    for path in sorted(dump.glob("*.txt")):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        name = NAME_RE.search(text)
        story_id = name.group(1) if name else path.stem
        if not STORY_RE.fullmatch(story_id):
            continue
        table = stories.setdefault(story_id, [])
        seen = set(table)
        for line in text.splitlines():
            if line.split(",", 1)[0] not in TEXT_COMMANDS:
                continue
            fields = line.split(",")
            if len(fields) < 3:
                continue
            body = strip_trailer(fields[2]).strip()
            if body and body not in seen:
                seen.add(body)
                table.append(body)
    return stories


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dump-dir", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--cache-dir", type=Path, default=None,
                        help="optional BepInEx/plugins/AbyssMod/cache for reusing published translations")
    args = parser.parse_args()

    novels_root = args.root.resolve() / "translations" / "novels"
    novels_root.mkdir(parents=True, exist_ok=True)

    pool: dict[str, str] = {}
    if args.cache_dir:
        cache = args.cache_dir.resolve()
        pool.update(pool_from(cache / "translations" / "novels", True))
        pool.update({k: v for k, v in pool_from(cache / "zh_Hans" / "novels", False).items() if k not in pool})
    pool.update(pool_from(novels_root, True))

    stories = parse_dump(args.dump_dir)
    new_lines = []
    added = 0
    for story_id, bodies in sorted(stories.items()):
        target = novels_root / story_id / "zh_Hans.json"
        existing = load_map(target)
        merged = dict(existing)
        for body in bodies:
            if body in merged:
                continue
            value = pool.get(body, "")
            merged[body] = value
            added += 1
            if not value:
                new_lines.append({"story": story_id, "source": body})
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(merged, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    (args.root / "new-lines.json").write_text(
        json.dumps(new_lines, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"stories: {len(stories)}, new keys: {added}, still untranslated: {len(new_lines)}")
    print(f"next: fill new-lines.json, then run tools/build_manifest.py --root .")


if __name__ == "__main__":
    main()
