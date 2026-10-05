"""Optional: list (and export textures/text) from a Unity bundle with UnityPy.

    pip install UnityPy
    python -m asset_inspector.unity_dump some.bundle --export out/

Only open bundles from games you own or are permitted to analyse; exported
art/audio stays the copyright of its owner.
"""
from __future__ import annotations

import argparse
import os
import sys


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="List objects in a Unity AssetBundle (needs UnityPy)")
    ap.add_argument("bundle")
    ap.add_argument("--export", help="folder to export Texture2D/Sprite PNGs and TextAssets into")
    args = ap.parse_args(argv)
    try:
        import UnityPy  # type: ignore
    except ImportError:
        print("UnityPy is not installed: pip install UnityPy", file=sys.stderr)
        return 2
    env = UnityPy.load(args.bundle)
    if args.export:
        os.makedirs(args.export, exist_ok=True)
    for obj in env.objects:
        kind = obj.type.name
        data = obj.read()
        name = getattr(data, "m_Name", "") or getattr(data, "name", "") or f"{obj.path_id}"
        print(f"{kind:16} {obj.path_id:>20}  {name}")
        if not args.export:
            continue
        if kind in ("Texture2D", "Sprite"):
            data.image.save(os.path.join(args.export, f"{name}_{obj.path_id}.png"))
        elif kind == "TextAsset":
            script = data.m_Script
            raw = script.encode("utf-8", "surrogateescape") if isinstance(script, str) else bytes(script)
            with open(os.path.join(args.export, f"{name}_{obj.path_id}.txt"), "wb") as fh:
                fh.write(raw)
    return 0


if __name__ == "__main__":
    sys.exit(main())
