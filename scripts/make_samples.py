"""Generate tiny SYNTHETIC samples (no real game data) used by the demo and tests.

    python scripts/make_samples.py            # writes ./samples
"""
from __future__ import annotations

import gzip
import json
import os
import struct
import sys
import zipfile
import zlib

CDN = "https://d111111abcdef8.cloudfront.net/mygame/android/1.4.2"


def tiny_png() -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\xff\x80\x00")
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def catalog() -> dict:
    return {
        "m_LocatorId": "AddressablesMainContentCatalog",
        "m_ProviderIds": [
            "UnityEngine.ResourceManagement.ResourceProviders.AssetBundleProvider",
            "UnityEngine.ResourceManagement.ResourceProviders.BundledAssetProvider",
        ],
        "m_InternalIdPrefixes": [CDN + "/bundles", "{UnityEngine.AddressableAssets.Addressables.RuntimePath}/Android"],
        "m_InternalIds": [
            "0#/characters_assets_all_3f2a9c1d.bundle",
            "0#/ui_atlas_assets_all_9b8e7d6c.bundle",
            "1#/defaultlocalgroup_assets_all_1a2b3c4d.bundle",
            "{RemoteLoadPath}/levels_assets_all_5e6f7a8b.bundle",
            "Assets/Art/Characters/Hero.prefab",
        ],
    }


def build(out: str) -> str:
    apk = os.path.join(out, "fake_apk")
    files = {
        # --- what you'd see after `unzip game.apk -d fake_apk` -------------
        "fake_apk/assets/config/remote_config.json": json.dumps({
            "api": "https://api.example-game.com/v2/session",
            "assetBaseUrl": CDN,
            "catalog": CDN + "/catalog_2024.09.01.json",
            "patchManifest": "https://cdn.example-game.com/patch/manifest_142.json",
        }, indent=2).encode(),
        "fake_apk/assets/aa/settings.json": json.dumps({
            "m_CatalogLocations": [{"m_InternalId": "{RemoteLoadPath}/catalog_2024.09.01.hash"}],
        }).encode(),
        # A fake 'classes.dex' with strings embedded among binary noise (+ one UTF-16LE string)
        "fake_apk/classes.dex": b"dex\n035\x00" + b"\x00\x01\x02"
            + b"\x10https://telemetry.example-game.com/collect\x00\x07\x08"
            + "https://storage.googleapis.com/example-game-assets/audio/theme.ogg".encode("utf-16-le")
            + b"\x00\x00levels/level_01.pak\x00",
        # --- 'downloaded' cache files with realistic magic bytes ------------
        "cache/3f2a9c1d": b"UnityFS\x00\x00\x00\x00\x08" + b"5.x.x\x002021.3.0f1\x00" + b"\x00" * 32,
        "cache/ui_icon.png": tiny_png(),
        "cache/photo.jpg": b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 16 + b"\xff\xd9",
        "cache/theme.ogg": b"OggS\x00\x02" + b"\x00" * 22,
        "cache/hero.ktx": b"\xabKTX 11\xbb\r\n\x1a\n" + b"\x01\x02\x03\x04" + b"\x00" * 48,
        "cache/hero.astc": b"\x13\xab\xa1\x5c" + bytes([4, 4, 1]) + b"\x00" * 9,
        "cache/level_01.pak": b"\x00" * 64 + struct.pack("<IIQQ", 0x5A6F12E1, 11, 0, 64) + b"\x00" * 20,
        "cache/manifest.json.gz": gzip.compress(b'{"version": 142}', mtime=0),
        "cache/catalog.json": json.dumps(catalog(), indent=2).encode(),
        "cache/encrypted.bin": bytes((i * 37 + 11) % 256 for i in range(64)),
    }
    for rel, data in files.items():
        path = os.path.join(out, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)
    # Also a zipped copy so you can scan an ".apk" directly
    with zipfile.ZipFile(os.path.join(out, "fake_game.apk"), "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, names in os.walk(apk):
            for name in sorted(names):
                full = os.path.join(root, name)
                info = zipfile.ZipInfo(os.path.relpath(full, apk), date_time=(2024, 1, 1, 0, 0, 0))
                with open(full, "rb") as fh:
                    zf.writestr(info, fh.read(), zipfile.ZIP_DEFLATED)
    return out


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "samples")
    print("samples written to", os.path.abspath(build(target)))
