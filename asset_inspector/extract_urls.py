"""Find http(s) URLs, CDN hosts and asset-bundle references in files.

Point it at an unzipped APK/IPA, a raw .apk/.ipa/.zip, or any folder of files.

Usage:
    python -m asset_inspector.extract_urls unzipped_apk/ [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from urllib.parse import urlparse

URL_RE = re.compile(rb"https?://[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%{}]+")
ASSET_REF_RE = re.compile(
    rb"[A-Za-z0-9_\-./{}]+?\.(?:bundle|assetbundle|unity3d|pak|ab|bytes|catalog|hash|obb|atlas|plist)\b"
    rb"|[A-Za-z0-9_\-./{}]*catalog[A-Za-z0-9_\-.]*\.json"
)
CDN_HINTS = (
    "cdn", "cloudfront.net", "akamai", "akamaihd.net", "fastly", "edgesuite.net",
    "storage.googleapis.com", "firebasestorage", "blob.core.windows.net",
    "s3.amazonaws.com", "amazonaws.com", "cloudflare", "r2.dev", "b-cdn.net",
    "aliyuncs.com", "myqcloud.com", "unity3d.com", "unitycdn",
)
ASSET_EXTS = (".bundle", ".assetbundle", ".unity3d", ".pak", ".ab", ".hash", ".png",
              ".jpg", ".ogg", ".ktx", ".astc", ".json", ".atlas", ".zip", ".obb")
MAX_FILE = 64 * 1024 * 1024


@dataclass
class ScanResult:
    urls: dict[str, set[str]] = field(default_factory=dict)        # url -> sources
    asset_refs: dict[str, set[str]] = field(default_factory=dict)  # ref -> sources

    def hosts(self) -> Counter:
        return Counter(urlparse(u).hostname or "" for u in self.urls)

    def cdn_hosts(self) -> list[str]:
        return sorted(h for h in self.hosts() if is_cdn_host(h))

    def asset_urls(self) -> list[str]:
        return sorted(u for u in self.urls if looks_like_asset_url(u))

    def to_dict(self) -> dict:
        return {
            "urls": {u: sorted(s) for u, s in sorted(self.urls.items())},
            "hosts": dict(self.hosts().most_common()),
            "cdn_hosts": self.cdn_hosts(),
            "asset_urls": self.asset_urls(),
            "asset_refs": {r: sorted(s) for r, s in sorted(self.asset_refs.items())},
        }


def is_cdn_host(host: str) -> bool:
    host = (host or "").lower()
    return any(h in host for h in CDN_HINTS)


def looks_like_asset_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return path.endswith(ASSET_EXTS) or "/bundles/" in path or "assetbundle" in path or "catalog" in path


def _clean_url(raw: str) -> str:
    return raw.rstrip(".,;:'\")]}>")


UTF16_RE = re.compile(rb"(?:[\x20-\x7e]\x00){6,}")


def _strings(data: bytes) -> list[bytes]:
    """Return the raw blob plus any UTF-16LE strings (common in .NET/Java/iOS binaries)."""
    blobs = [data]
    if b"h\x00t\x00t\x00p\x00" in data or b".\x00b\x00u\x00n\x00d\x00l\x00e\x00" in data:
        blobs.extend(m.group().decode("utf-16-le").encode() for m in UTF16_RE.finditer(data))
    return blobs


def scan_bytes(data: bytes, source: str, result: ScanResult) -> None:
    """Scan raw bytes (ASCII/UTF-8 and UTF-16LE strings) for URLs and asset refs."""
    for blob in _strings(data):
        for m in URL_RE.finditer(blob):
            url = _clean_url(m.group().decode("ascii", "ignore"))
            if urlparse(url).hostname:
                result.urls.setdefault(url, set()).add(source)
        # blank out URLs so their path segments aren't reported twice as bare refs
        rest = URL_RE.sub(lambda m: b" " * len(m.group()), blob)
        for m in ASSET_REF_RE.finditer(rest):
            ref = m.group().decode("ascii", "ignore").lstrip("./")
            if ref:
                result.asset_refs.setdefault(ref, set()).add(source)


def scan_path(path: str, result: ScanResult | None = None) -> ScanResult:
    """Scan a file, a directory tree, or a zip-like archive (.apk/.ipa/.zip/.obb)."""
    result = result or ScanResult()
    if os.path.isdir(path):
        for root, _, files in os.walk(path):
            for name in sorted(files):
                scan_path(os.path.join(root, name), result)
        return result
    if os.path.getsize(path) > MAX_FILE:
        return result
    if zipfile.is_zipfile(path) and path.lower().endswith((".apk", ".ipa", ".zip", ".obb", ".xapk")):
        with zipfile.ZipFile(path) as zf:
            for info in zf.infolist():
                if not info.is_dir() and info.file_size <= MAX_FILE:
                    scan_bytes(zf.read(info), f"{path}!{info.filename}", result)
        return result
    with open(path, "rb") as fh:
        scan_bytes(fh.read(), path, result)
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Extract URLs / CDN hosts / asset references")
    ap.add_argument("paths", nargs="+", help="files, folders, or .apk/.ipa/.zip archives")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    result = ScanResult()
    for p in args.paths:
        scan_path(p, result)
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
        return 0
    print(f"== {len(result.urls)} URLs across {len(result.hosts())} hosts")
    for host, n in result.hosts().most_common():
        print(f"  {'[CDN] ' if is_cdn_host(host) else '      '}{host}  ({n})")
    print("\n== URLs that look like remote assets")
    for u in result.asset_urls():
        print("  " + u)
    print(f"\n== {len(result.asset_refs)} asset-file references (bundles, paks, catalogs)")
    for r in sorted(result.asset_refs):
        print("  " + r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
