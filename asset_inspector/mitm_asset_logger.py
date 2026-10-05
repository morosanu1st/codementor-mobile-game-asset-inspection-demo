"""mitmproxy addon: save responses that look like game assets + write a CSV manifest.

Run (only against devices/apps you own or are permitted to test):
    mitmdump -s asset_inspector/mitm_asset_logger.py --set asset_dir=captured_assets

Optional filter to a single host:
    mitmdump -s asset_inspector/mitm_asset_logger.py --set asset_host_filter=cdn.example-game.com
"""
from __future__ import annotations

import csv
import hashlib
import os
import re
import sys
import time
from urllib.parse import urlparse

try:  # works both as a package module and when loaded by path via `mitmdump -s`
    from asset_inspector.identify import identify_bytes
except ImportError:  # pragma: no cover
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from asset_inspector.identify import identify_bytes

ASSET_CONTENT_TYPES = (
    "application/octet-stream", "image/", "audio/", "video/", "application/zip",
    "application/x-gzip", "application/gzip", "application/vnd.unity", "binary/octet-stream",
)
ASSET_PATH_RE = re.compile(
    r"\.(bundle|assetbundle|unity3d|pak|ab|hash|png|jpe?g|webp|ogg|wav|mp3|ktx2?|astc|pkm|atlas|zip|obb|bin)$"
    r"|catalog[^/]*\.(json|hash|bin)$|/(bundles?|assets?|addressables|patch|cdn)/",
    re.IGNORECASE,
)
CSV_FIELDS = ["time", "method", "status", "url", "host", "content_type", "size",
              "sha256", "detected_type", "saved_as"]


def looks_like_asset(path: str, content_type: str) -> bool:
    ct = (content_type or "").lower()
    return bool(ASSET_PATH_RE.search(path or "")) or any(ct.startswith(t) for t in ASSET_CONTENT_TYPES)


def safe_name(url: str, digest: str) -> str:
    parsed = urlparse(url)
    base = os.path.basename(parsed.path) or "index"
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base)[:80]
    return os.path.join(re.sub(r"[^A-Za-z0-9.-]", "_", parsed.hostname or "unknown"), f"{digest[:12]}_{base}")


class AssetLogger:
    def __init__(self) -> None:
        self.out_dir = os.environ.get("ASSET_DIR", "captured_assets")
        self.host_filter = os.environ.get("ASSET_HOST_FILTER", "")
        self.seen: set[str] = set()

    # --- mitmproxy hooks -------------------------------------------------
    def load(self, loader) -> None:  # pragma: no cover - needs mitmproxy
        loader.add_option("asset_dir", str, self.out_dir, "Folder for captured assets")
        loader.add_option("asset_host_filter", str, self.host_filter, "Only log hosts containing this")

    def configure(self, updates) -> None:  # pragma: no cover - needs mitmproxy
        from mitmproxy import ctx
        self.out_dir = ctx.options.asset_dir
        self.host_filter = ctx.options.asset_host_filter

    def response(self, flow) -> None:
        req, resp = flow.request, flow.response
        if resp is None:
            return
        url = req.pretty_url
        host = urlparse(url).hostname or ""
        if self.host_filter and self.host_filter not in host:
            return
        content_type = resp.headers.get("content-type", "")
        if not looks_like_asset(urlparse(url).path, content_type):
            return
        body = resp.get_content(strict=False) or b""  # decoded (gzip/br removed)
        self.record(req.method, resp.status_code, url, content_type, body)

    # --- plain-Python core (unit-testable without mitmproxy) --------------
    def record(self, method: str, status: int, url: str, content_type: str, body: bytes) -> str | None:
        digest = hashlib.sha256(body).hexdigest()
        rel = safe_name(url, digest)
        path = os.path.join(self.out_dir, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if digest not in self.seen and body:
            with open(path, "wb") as fh:
                fh.write(body)
            self.seen.add(digest)
        manifest = os.path.join(self.out_dir, "manifest.csv")
        new = not os.path.exists(manifest)
        with open(manifest, "a", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
            if new:
                w.writeheader()
            w.writerow({
                "time": time.strftime("%Y-%m-%dT%H:%M:%S"), "method": method, "status": status,
                "url": url, "host": urlparse(url).hostname, "content_type": content_type,
                "size": len(body), "sha256": digest,
                "detected_type": identify_bytes(body[:64], body[-512:], body if len(body) < 2_000_000 else None),
                "saved_as": rel if body else "",
            })
        return path


addons = [AssetLogger()]
