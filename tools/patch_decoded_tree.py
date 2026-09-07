#!/usr/bin/env python3
"""Patch an apktool-decoded Kasa tree for side-by-side Dimmer Tools research builds.

This intentionally edits only UTF-8 text files. apktool rebuilds the binary XML/resource
structures afterward. Java/Kotlin class packages are not renamed unless they literally
contain the application-id string (Kasa 3.4.602 does not define classes under
com.tplink.kasa_android).
"""
from __future__ import annotations
import argparse
from pathlib import Path

TEXT_SUFFIXES = {
    '.xml', '.smali', '.yml', '.yaml', '.json', '.txt', '.properties', '.pro', '.cfg',
    '.ini', '.gradle', '.kts', '.md'
}


def patch_tree(root: Path, old: str, new: str) -> tuple[int, int]:
    files_changed = replacements = 0
    for path in root.rglob('*'):
        if not path.is_file():
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name != 'AndroidManifest.xml':
            continue
        try:
            text = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue
        n = text.count(old)
        if not n:
            continue
        path.write_text(text.replace(old, new), encoding='utf-8')
        files_changed += 1
        replacements += n
    return files_changed, replacements


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('decoded_dir', type=Path)
    p.add_argument('--from-package', dest='old', default='com.tplink.kasa_android')
    p.add_argument('--to-package', dest='new', default='com.mekromn.dimmertools')
    args = p.parse_args()
    manifest = args.decoded_dir / 'AndroidManifest.xml'
    if not manifest.exists():
        raise SystemExit(f'AndroidManifest.xml not found under {args.decoded_dir}')
    files, count = patch_tree(args.decoded_dir, args.old, args.new)
    manifest_text = manifest.read_text(encoding='utf-8', errors='replace')
    if f'package="{args.new}"' not in manifest_text:
        raise SystemExit(f'package rename failed: {args.new!r} not present in decoded manifest')
    if f'package="{args.old}"' in manifest_text:
        raise SystemExit(f'package rename incomplete: old package still owns manifest')
    marker = args.decoded_dir / 'DIMMER_TOOLS_PACKAGE.txt'
    marker.write_text(
        f'original={args.old}\nmod={args.new}\nfiles_changed={files}\nreplacements={count}\n',
        encoding='utf-8',
    )
    print(f'package: {args.old} -> {args.new}')
    print(f'patched {count} occurrence(s) in {files} text file(s)')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
