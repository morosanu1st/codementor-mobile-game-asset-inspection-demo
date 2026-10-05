import csv
import json
import os

from asset_inspector.inspect_catalog import analyse
from asset_inspector.mitm_asset_logger import AssetLogger, looks_like_asset


def test_catalog_prefix_expansion(samples):
    with open(os.path.join(samples, "cache", "catalog.json")) as fh:
        rep = analyse(json.load(fh))
    assert rep["bundle_count"] == 4
    assert len(rep["remote_bundles"]) == 2
    assert rep["remote_bundles"][0].endswith("/bundles/characters_assets_all_3f2a9c1d.bundle")
    assert rep["templated_bundles"] == ["{RemoteLoadPath}/levels_assets_all_5e6f7a8b.bundle"]
    rep2 = analyse(json.load(open(os.path.join(samples, "cache", "catalog.json"))), "https://cdn.x/aa/")
    assert "https://cdn.x/aa/levels_assets_all_5e6f7a8b.bundle" in rep2["remote_bundles"]


def test_logger_record_without_mitmproxy(tmp_path):
    assert looks_like_asset("/bundles/hero.bundle", "")
    assert looks_like_asset("/x", "image/png")
    assert not looks_like_asset("/api/login", "application/json")
    log = AssetLogger()
    log.out_dir = str(tmp_path)
    path = log.record("GET", 200, "https://cdn.example.com/b/hero.bundle", "application/octet-stream",
                      b"UnityFS\x00" + b"\x00" * 16)
    assert os.path.exists(path)
    rows = list(csv.DictReader(open(tmp_path / "manifest.csv")))
    assert rows[0]["detected_type"] == "unityfs"
    assert rows[0]["host"] == "cdn.example.com"
