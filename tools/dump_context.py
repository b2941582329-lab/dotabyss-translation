#!/usr/bin/env python3
"""Show every line of a story in script order, marking untranslated ones.

    python tools/dump_context.py --root . hmr_11120100032

Lines already translated print as "ok | ...", missing ones as
"NEW | [speaker] ...".  Use it to translate with full scene context.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

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


def script_lines(dump: Path, story_id: str):
    path = dump / f"{story_id}.txt"
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        command = line.split(",", 1)[0]
        if command not in TEXT_COMMANDS:
            continue
        fields = line.split(",")
        if len(fields) < 3:
            continue
        body = strip_trailer(fields[2]).strip()
        if not body:
            continue
        speaker = "" if command in ("messageTextCenter", "messageTextUnder") else fields[1].strip()
        out.append((speaker, body))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ids", nargs="+")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--dump-dir", type=Path, required=True)
    args = parser.parse_args()

    for story_id in args.ids:
        path = args.root.resolve() / "translations" / "novels" / story_id / "zh_Hans.json"
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        print(f"##### {story_id} ({len(data)} keys)")
        for speaker, body in script_lines(args.dump_dir, story_id):
            value = str(data.get(body, ""))
            if value.strip():
                print(f"   ok | {value}")
            else:
                print(f"NEW    | [{speaker}] {body}")
        print()


if __name__ == "__main__":
    main()
