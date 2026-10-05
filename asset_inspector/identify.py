"""Identify game-asset file types by magic bytes (stdlib only).

Usage:
    python -m asset_inspector.identify path/to/file_or_dir [...] [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Iterable

# (label, offset, magic bytes, short description)
SIGNATURES: list[tuple[str, int, bytes, str]] = [
    ("unityfs", 0, b"UnityFS\x00", "Unity AssetBundle (UnityFS container)"),
    ("unityweb", 0, b"UnityWeb\x00", "Unity legacy web bundle"),
    ("unityraw", 0, b"UnityRaw\x00", "Unity legacy raw bundle"),
    ("png", 0, b"\x89PNG\r\n\x1a\n", "PNG image"),
    ("jpeg", 0, b"\xff\xd8\xff", "JPEG image"),
    ("ogg", 0, b"OggS", "Ogg container (Vorbis/Opus audio)"),
    ("fsb5", 0, b"FSB5", "FMOD sound bank"),
    ("ktx", 0, b"\xabKTX 11\xbb\r\n\x1a\n", "KTX texture (v1)"),
    ("ktx2", 0, b"\xabKTX 20\xbb\r\n\x1a\n", "KTX2 texture"),
    ("astc", 0, b"\x13\xab\xa1\x5c", "ASTC compressed texture"),
    ("pkm", 0, b"PKM ", "ETC1/ETC2 texture (PKM)"),
    ("dds", 0, b"DDS ", "DirectDraw Surface texture"),
    ("zip", 0, b"PK\x03\x04", "ZIP archive (also APK/IPA/OBB/AAB)"),
    ("gzip", 0, b"\x1f\x8b", "gzip-compressed data"),
    ("dex", 0, b"dex\n", "Android Dalvik bytecode"),
    ("sqlite", 0, b"SQLite format 3\x00", "SQLite database (often a local cache index)"),
]

# Unreal Engine .pak files carry their magic in a footer near the end of the file.
UE_PAK_MAGIC = b"\xe1\x12\x6f\x5a"  # 0x5A6F12E1 little-endian
UE_PAK_FOOTER_SCAN = 512


def _looks_like_json(data: bytes) -> bool:
    text = data.lstrip(b"\xef\xbb\xbf \t\r\n")
    if not text or text[:1] not in (b"{", b"["):
        return False
    try:
        json.loads(text.decode("utf-8"))
        return True
    except (UnicodeDecodeError, ValueError):
        return False


def identify_bytes(head: bytes, tail: bytes = b"", full: bytes | None = None) -> str:
    """Return a short type label for a blob.

    ``head`` is the start of the file, ``tail`` its last bytes (used for the
    Unreal .pak footer) and ``full`` optionally the whole content (used for JSON).
    """
    for label, offset, magic, _ in SIGNATURES:
        if head[offset:offset + len(magic)] == magic:
            return label
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "wav"
    if UE_PAK_MAGIC in (tail or head[-UE_PAK_FOOTER_SCAN:]):
        return "unreal_pak"
    if _looks_like_json(full if full is not None else head):
        return "json"
    return "unknown"


def describe(label: str) -> str:
    extra = {
        "webp": "WebP image",
        "wav": "WAV audio",
        "unreal_pak": "Unreal Engine .pak archive (footer magic)",
        "json": "JSON document (manifest/config/catalog?)",
        "unknown": "unknown / possibly encrypted or custom format",
    }
    for label_, _, _, desc in SIGNATURES:
        if label_ == label:
            return desc
    return extra.get(label, label)


def identify_file(path: str, max_json: int = 5 * 1024 * 1024) -> str:
    size = os.path.getsize(path)
    with open(path, "rb") as fh:
        head = fh.read(64)
        tail = b""
        if size > 64:
            fh.seek(max(0, size - UE_PAK_FOOTER_SCAN))
            tail = fh.read()
        full = None
        if size <= max_json and head.lstrip()[:1] in (b"{", b"[", b"\xef"):
            fh.seek(0)
            full = fh.read()
    return identify_bytes(head, tail, full)


def iter_files(paths: Iterable[str]) -> Iterable[str]:
    for p in paths:
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for name in sorted(files):
                    yield os.path.join(root, name)
        else:
            yield p


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Identify asset files by magic bytes")
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--json", action="store_true", help="print JSON lines")
    args = ap.parse_args(argv)
    for path in iter_files(args.paths):
        label = identify_file(path)
        if args.json:
            print(json.dumps({"path": path, "type": label, "description": describe(label)}))
        else:
            print(f"{label:12} {os.path.getsize(path):>10}  {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
