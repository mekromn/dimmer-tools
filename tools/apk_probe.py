#!/usr/bin/env python3
"""Static, dependency-free APK probe focused on TP-Link/Kasa firmware-update surfaces."""
from __future__ import annotations
import argparse, json, re, struct, zipfile
from pathlib import Path

FW_PATTERNS = [
    re.compile(r"firmware", re.I),
    re.compile(r"(?:^|[_./])fw(?:[_./]|$)", re.I),
    re.compile(r"get_cloud_firmware_info", re.I),
    re.compile(r"start_firmware_upgrade", re.I),
    re.compile(r"get_firmware_upgrade_status", re.I),
    re.compile(r"fw_url", re.I),
    re.compile(r"fw_ver", re.I),
    re.compile(r"oem_id", re.I),
    re.compile(r"hw_id", re.I),
]


def _u16(buf: bytes, off: int) -> int:
    return struct.unpack_from("<H", buf, off)[0]


def _u32(buf: bytes, off: int) -> int:
    return struct.unpack_from("<I", buf, off)[0]


def _read_len8(buf: bytes, p: int):
    b = buf[p]
    if b & 0x80:
        return ((b & 0x7F) << 8) | buf[p + 1], p + 2
    return b, p + 1


def _read_len16(buf: bytes, p: int):
    x = _u16(buf, p)
    if x & 0x8000:
        return ((x & 0x7FFF) << 16) | _u16(buf, p + 2), p + 4
    return x, p + 2


def parse_axml_manifest(buf: bytes) -> dict:
    strings: list[str] = []
    out: dict[str, object] = {}
    pos = 8
    while pos + 8 <= len(buf):
        typ, header_size, size = _u16(buf, pos), _u16(buf, pos + 2), _u32(buf, pos + 4)
        if size < 8 or pos + size > len(buf):
            break
        if typ == 0x0001:
            count = _u32(buf, pos + 8)
            flags = _u32(buf, pos + 16)
            strings_start = _u32(buf, pos + 20)
            utf8 = bool(flags & 0x100)
            offsets = [_u32(buf, pos + header_size + 4 * i) for i in range(count)]
            base = pos + strings_start
            strings = []
            for rel in offsets:
                p = base + rel
                if utf8:
                    _, p = _read_len8(buf, p)
                    n, p = _read_len8(buf, p)
                    s = buf[p:p+n].decode("utf-8", "replace")
                else:
                    n, p = _read_len16(buf, p)
                    s = buf[p:p+2*n].decode("utf-16le", "replace")
                strings.append(s)
        elif typ == 0x0102 and strings:
            name_idx = _u32(buf, pos + 20)
            if name_idx >= len(strings):
                pos += size
                continue
            tag = strings[name_idx]
            attr_start, attr_size, attr_count = _u16(buf, pos + 24), _u16(buf, pos + 26), _u16(buf, pos + 28)
            ap = pos + 16 + attr_start
            attrs = {}
            for i in range(attr_count):
                q = ap + i * attr_size
                if q + 20 > pos + size:
                    break
                _, name_i, raw_i = struct.unpack_from("<III", buf, q)
                vtype = buf[q + 15]
                vdata = _u32(buf, q + 16)
                if name_i == 0xFFFFFFFF or name_i >= len(strings):
                    continue
                name = strings[name_i]
                if raw_i != 0xFFFFFFFF and raw_i < len(strings):
                    value: object = strings[raw_i]
                elif vtype == 0x03 and vdata < len(strings):
                    value = strings[vdata]
                elif vtype in (0x10, 0x11, 0x12):
                    value = vdata
                else:
                    value = {"type": vtype, "data": vdata}
                attrs[name] = value
            if tag == "manifest":
                out.update({k: attrs[k] for k in ("package", "versionName", "versionCode") if k in attrs})
            elif tag == "uses-sdk":
                out.update({k: attrs[k] for k in ("minSdkVersion", "targetSdkVersion") if k in attrs})
            elif tag == "application":
                out["applicationName"] = attrs.get("name")
        pos += size
    return out


def _uleb128(buf: bytes, off: int):
    value = 0
    shift = 0
    for i in range(5):
        b = buf[off + i]
        value |= (b & 0x7F) << shift
        if b < 0x80:
            return value, off + i + 1
        shift += 7
    return value, off + 5


def dex_strings(buf: bytes):
    if len(buf) < 0x70 or not buf.startswith(b"dex\n"):
        return
    count, table_off = struct.unpack_from("<II", buf, 0x38)
    for idx in range(count):
        data_off = _u32(buf, table_off + 4 * idx)
        _, p = _uleb128(buf, data_off)
        end = buf.find(b"\0", p)
        if end < 0:
            continue
        yield idx, buf[p:end].decode("utf-8", "replace")


def probe(apk: Path) -> dict:
    result = {"apk": str(apk), "manifest": {}, "dex": {}, "ota_markers": []}
    with zipfile.ZipFile(apk) as zf:
        result["manifest"] = parse_axml_manifest(zf.read("AndroidManifest.xml"))
        dex_names = sorted(
            (n for n in zf.namelist() if re.fullmatch(r"classes\d*\.dex", n)),
            key=lambda n: (len(n), n),
        )
        result["dex"]["files"] = dex_names
        seen = set()
        for dex_name in dex_names:
            buf = zf.read(dex_name)
            for idx, s in dex_strings(buf):
                if len(s) > 500:
                    continue
                if any(p.search(s) for p in FW_PATTERNS):
                    key = (dex_name, idx, s)
                    if key not in seen:
                        seen.add(key)
                        result["ota_markers"].append({"dex": dex_name, "string_id": idx, "value": s})
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("apk", type=Path)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--limit", type=int, default=250)
    args = ap.parse_args()
    r = probe(args.apk)
    if args.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
        return 0
    print("Manifest")
    for k, v in r["manifest"].items():
        print(f"  {k}: {v}")
    print(f"DEX files: {len(r['dex']['files'])}")
    print("Firmware/OTA markers")
    for row in r["ota_markers"][:args.limit]:
        print(f"  {row['dex']}:{row['string_id']}: {row['value']}")
    if len(r["ota_markers"]) > args.limit:
        print(f"  ... {len(r['ota_markers'])-args.limit} more (use --json or --limit)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
