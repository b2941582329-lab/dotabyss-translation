#!/usr/bin/env python3
"""Build, check or verify the AbyssMod zh_Hans manifest.

The AbyssMod plugin verifies every downloaded file against the MD5 hashes in
translations/manifest/zh_Hans.json.  Editing a novel JSON without refreshing
the manifest makes the plugin re-download it forever, so this tool is the only
supported way to touch the manifest.

Hash algorithm (must match the plugin):
    * object hash: sort keys, walk nested objects depth first,
      feed "key\\0value\\0" into MD5, join nested keys with "\\x01".
    * replacement images: MD5 of the raw file bytes.
    * the manifest "hash" field is the object hash of the manifest without it.

Usage:
    python tools/build_manifest.py --root .           # write manifest
    python tools/build_manifest.py --root . --check   # fail if stale
    python tools/build_manifest.py --root . --verify  # verify file hashes
    python tools/build_manifest.py --root . --strict  # treat warnings as errors
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SECTIONS = ("names", "static", "ui_texts")
IMAGE_EXT = {".png", ".jpg", ".jpeg"}
META_SUFFIX = re.compile(
    r"(?:,\d{6,}[A-Za-z0-9]*|,vc_[A-Za-z0-9_]+|,mcv_[A-Za-z0-9_]+|,mca_[A-Za-z0-9_]+"
    r"|,,?chara_\d+(?:/chara_\d+)*|,\d/chara_\d+|,on|,off)+$"
)
RUBY = re.compile(r"<ruby=[^>]*>.*?</ruby>|<ruby=[^>]*>.*?</>", re.S)
# Hiragana/katakana minus the punctuation marks ・(U+30FB) and ー(U+30FC),
# which legitimately survive in Chinese translations.
KANA = re.compile(r"[\u3041-\u30fa\u30fd-\u30ff]")


def object_hash(obj) -> str:
    md5 = hashlib.md5()

    def walk(node):
        for key in sorted(node):
            value = node[key]
            if isinstance(value, dict):
                for sub_key, sub_value in walk(value):
                    yield f"{key}\x01{sub_key}", sub_value
            else:
                yield key, str(value)

    for key, value in walk(obj):
        md5.update(key.encode("utf-8"))
        md5.update(b"\x00")
        md5.update(value.encode("utf-8"))
        md5.update(b"\x00")
    return md5.hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def collect(trans: Path, warnings: list[str]) -> tuple[dict, dict, dict]:
    novels: dict[str, str] = {}
    files: dict[str, Path] = {}
    for path in sorted((trans / "novels").glob("*/zh_Hans.json")):
        story_id = path.parent.name
        if path.read_bytes()[:3] == b"\xef\xbb\xbf":
            warnings.append(f"{story_id}: UTF-8 BOM in novel JSON (game may fail to parse it)")
        try:
            data = load_json(path)
        except json.JSONDecodeError as error:
            raise SystemExit(f"{story_id}: invalid JSON: {error}")
        if not isinstance(data, dict) or not data:
            warnings.append(f"{story_id}: empty or invalid novel JSON")
            continue
        for key, value in data.items():
            if not isinstance(key, str) or not key.strip():
                warnings.append(f"{story_id}: empty source key")
                continue
            if not isinstance(value, str) or not value.strip():
                warnings.append(f"{story_id}: blank translation for {key[:40]!r}")
                continue
            if META_SUFFIX.search(key):
                warnings.append(f"{story_id}: key keeps voice/chara metadata: {key[-40:]!r}")
            if key.count("<br>") != value.count("<br>"):
                warnings.append(f"{story_id}: <br> count differs for {key[:40]!r}")
            if key.count("<user>") != value.count("<user>"):
                warnings.append(f"{story_id}: <user> count differs for {key[:40]!r}")
            if KANA.search(RUBY.sub("", value)):
                warnings.append(f"{story_id}: kana left in translation of {key[:40]!r}")
        novels[story_id] = object_hash(data)
        files[story_id] = path

    sections = {}
    for section in SECTIONS:
        path = trans / section / "zh_Hans.json"
        if not path.is_file():
            warnings.append(f"missing section {section}/zh_Hans.json")
            continue
        sections[section] = object_hash(load_json(path))

    replacements: dict[str, str] = {}
    rep_dir = trans / "replacements"
    if rep_dir.is_dir():
        for path in sorted(rep_dir.iterdir()):
            if not path.is_file():
                continue
            if path.suffix.lower() not in IMAGE_EXT and path.name != "manifest.json":
                warnings.append(f"unsupported replacement file {path.name}")
                continue
            replacements[path.name] = hashlib.md5(path.read_bytes()).hexdigest()

    return novels, sections, replacements


def build(trans: Path, warnings: list[str]) -> dict:
    novels, sections, replacements = collect(trans, warnings)
    manifest = {
        "names": sections.get("names", ""),
        "novels": novels,
        "replacements": replacements,
        "static": sections.get("static", ""),
        "ui_texts": sections.get("ui_texts", ""),
    }
    manifest["hash"] = object_hash(manifest)
    return manifest


def serialize(manifest: dict) -> str:
    return json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=4) + "\n"


def describe_diff(old: dict, new: dict) -> list[str]:
    out = []
    for key in sorted(set(old) | set(new)):
        if key == "novels" and isinstance(old.get(key), dict) and isinstance(new.get(key), dict):
            added = sorted(set(new[key]) - set(old[key]))
            removed = sorted(set(old[key]) - set(new[key]))
            changed = sorted(k for k in set(old[key]) & set(new[key]) if old[key][k] != new[key][k])
            if added:
                out.append(f"  +{len(added)} novels (e.g. {added[:3]})")
            if removed:
                out.append(f"  -{len(removed)} novels (e.g. {removed[:3]})")
            if changed:
                out.append(f"  ~{len(changed)} novel hashes changed (e.g. {changed[:3]})")
        elif old.get(key) != new.get(key):
            out.append(f"  {key}: {str(old.get(key))[:16]} -> {str(new.get(key))[:16]}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path("."), help="repository root (contains translations/)")
    parser.add_argument("--check", action="store_true", help="fail if the manifest is missing or stale")
    parser.add_argument("--verify", action="store_true", help="verify every file hash against the manifest")
    parser.add_argument("--strict", action="store_true", help="treat validation warnings as errors")
    args = parser.parse_args()

    trans = args.root.resolve() / "translations"
    if not trans.is_dir():
        raise SystemExit(f"translations/ not found under {args.root.resolve()}")
    manifest_path = trans / "manifest" / "zh_Hans.json"

    warnings: list[str] = []
    manifest = build(trans, warnings)
    for warning in warnings[:40]:
        print(f"[warn] {warning}")
    if len(warnings) > 40:
        print(f"[warn] ... and {len(warnings) - 40} more")
    if warnings and args.strict:
        raise SystemExit(f"strict mode: {len(warnings)} warnings")

    if args.verify:
        if not manifest_path.is_file():
            raise SystemExit("manifest missing")
        disk = load_json(manifest_path)
        problems = []
        for section in SECTIONS:
            if disk.get(section) != manifest[section]:
                problems.append(f"section {section} hash mismatch")
        for story_id, digest in disk.get("novels", {}).items():
            if manifest["novels"].get(story_id) != digest:
                problems.append(f"novel {story_id} hash mismatch")
        for name, digest in disk.get("replacements", {}).items():
            if manifest["replacements"].get(name) != digest:
                problems.append(f"replacement {name} hash mismatch")
        for problem in problems[:30]:
            print(f"[bad] {problem}")
        print(f"verify: {len(manifest['novels'])} novels, {len(manifest['replacements'])} replacements, "
              f"{len(problems)} problems")
        sys.exit(1 if problems else 0)

    if args.check:
        if not manifest_path.is_file():
            raise SystemExit("manifest missing; run without --check to create it")
        disk = load_json(manifest_path)
        if disk == manifest:
            print(f"manifest up to date: {len(manifest['novels'])} novels, hash {manifest['hash']}")
            return
        print("manifest is stale:")
        for line in describe_diff(disk, manifest):
            print(line)
        raise SystemExit("run 'python tools/build_manifest.py --root .' to regenerate")

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    old_text = manifest_path.read_text(encoding="utf-8") if manifest_path.is_file() else ""
    text = serialize(manifest)
    if old_text == text:
        print(f"unchanged: {len(manifest['novels'])} novels, hash {manifest['hash']}")
        return
    manifest_path.write_text(text, encoding="utf-8")
    print(f"wrote {manifest_path}")
    print(f"  novels: {len(manifest['novels'])}")
    print(f"  replacements: {len(manifest['replacements'])}")
    print(f"  manifest hash: {manifest['hash']}")


if __name__ == "__main__":
    main()
