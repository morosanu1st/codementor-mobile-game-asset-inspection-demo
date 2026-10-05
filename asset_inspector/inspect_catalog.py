"""List remote bundle URLs from a Unity Addressables catalog.json.

Handles the classic JSON catalog layout (``m_InternalIds``, ``m_ProviderIds``)
including the prefix-compressed form (``m_InternalIdPrefixes`` + ``"3#/file.bundle"``).
Binary catalogs (catalog.bin, Addressables 2.x option) are not parsed here.

Usage:
    python -m asset_inspector.inspect_catalog catalog.json [--base-url https://cdn/...] [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys

PLACEHOLDER_RE = re.compile(r"\{[^}]+\}")


def expand_ids(catalog: dict) -> list[str]:
    ids = catalog.get("m_InternalIds", [])
    prefixes = catalog.get("m_InternalIdPrefixes") or []
    out = []
    for raw in ids:
        if prefixes and "#" in raw:
            idx, _, rest = raw.partition("#")
            if idx.isdigit() and int(idx) < len(prefixes):
                raw = prefixes[int(idx)] + rest
        out.append(raw)
    return out


def _is_local(entry: str) -> bool:
    return "RuntimePath" in entry or "StreamingAssets" in entry or "LocalLoadPath" in entry


def analyse(catalog: dict, base_url: str | None = None) -> dict:
    """Summarise a catalog. ``base_url`` replaces *remote* placeholders like {RemoteLoadPath}."""
    ids = expand_ids(catalog)
    placeholders = sorted({p for i in ids for p in PLACEHOLDER_RE.findall(i)})
    if base_url:
        ids = [PLACEHOLDER_RE.sub(lambda m: base_url.rstrip("/") if "remote" in m.group().lower() else m.group(), i)
               for i in ids]
    bundles = [i for i in ids if i.lower().endswith((".bundle", ".assetbundle", ".unity3d"))]
    remote = [b for b in bundles if b.startswith(("http://", "https://"))]
    local = [b for b in bundles if b not in remote and (_is_local(b) or not PLACEHOLDER_RE.search(b))]
    templated = [b for b in bundles if b not in remote and b not in local]
    return {
        "locator_id": catalog.get("m_LocatorId"),
        "providers": catalog.get("m_ProviderIds", []),
        "internal_id_count": len(ids),
        "bundle_count": len(bundles),
        "remote_bundles": remote,
        "templated_bundles": templated,
        "local_bundles": local,
        "placeholders": placeholders,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Inspect a Unity Addressables catalog.json")
    ap.add_argument("catalog")
    ap.add_argument("--base-url", help="value to substitute for {RemoteLoadPath}-style placeholders")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    with open(args.catalog, encoding="utf-8-sig") as fh:
        report = analyse(json.load(fh), args.base_url)
    if args.json:
        print(json.dumps(report, indent=2))
        return 0
    print(f"locator: {report['locator_id']}  ids: {report['internal_id_count']}  bundles: {report['bundle_count']}")
    print("providers:\n  " + "\n  ".join(report["providers"] or ["-"]))
    if report["placeholders"]:
        print("placeholders (resolved at runtime by the game):", ", ".join(report["placeholders"]))
    for key in ("remote_bundles", "templated_bundles", "local_bundles"):
        print(f"\n{key} ({len(report[key])}):")
        for b in report[key]:
            print("  " + b)
    return 0


if __name__ == "__main__":
    sys.exit(main())
