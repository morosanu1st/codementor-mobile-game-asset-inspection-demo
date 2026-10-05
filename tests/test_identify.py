import os

import pytest

from asset_inspector.identify import describe, identify_bytes, identify_file


@pytest.mark.parametrize("name,expected", [
    ("cache/3f2a9c1d", "unityfs"),
    ("cache/ui_icon.png", "png"),
    ("cache/photo.jpg", "jpeg"),
    ("cache/theme.ogg", "ogg"),
    ("cache/hero.ktx", "ktx"),
    ("cache/hero.astc", "astc"),
    ("cache/level_01.pak", "unreal_pak"),
    ("cache/manifest.json.gz", "gzip"),
    ("cache/catalog.json", "json"),
    ("cache/encrypted.bin", "unknown"),
    ("fake_game.apk", "zip"),
    ("fake_apk/classes.dex", "dex"),
])
def test_identify_samples(samples, name, expected):
    assert identify_file(os.path.join(samples, name)) == expected


def test_identify_bytes_misc():
    assert identify_bytes(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "webp"
    assert identify_bytes(b"\xabKTX 20\xbb\r\n\x1a\n") == "ktx2"
    assert identify_bytes(b'  {"a": 1}') == "json"
    assert identify_bytes(b"{not json") == "unknown"


def test_describe_is_human_readable():
    assert "Unity" in describe("unityfs")
    assert "Unreal" in describe("unreal_pak")
