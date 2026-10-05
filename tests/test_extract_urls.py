import os

from asset_inspector.extract_urls import (ScanResult, is_cdn_host, looks_like_asset_url,
                                          scan_bytes, scan_path)

CDN = "https://d111111abcdef8.cloudfront.net/mygame/android/1.4.2"


def test_scan_unzipped_apk_dir(samples):
    res = scan_path(os.path.join(samples, "fake_apk"))
    assert CDN + "/catalog_2024.09.01.json" in res.urls
    assert "https://api.example-game.com/v2/session" in res.urls
    # UTF-16LE string hidden in the fake dex is recovered
    assert "https://storage.googleapis.com/example-game-assets/audio/theme.ogg" in res.urls
    assert "d111111abcdef8.cloudfront.net" in res.cdn_hosts()
    assert "api.example-game.com" not in res.cdn_hosts()
    assert "levels/level_01.pak" in res.asset_refs
    assert "{RemoteLoadPath}/catalog_2024.09.01.hash" in res.asset_refs


def test_scan_apk_archive_directly(samples):
    res = scan_path(os.path.join(samples, "fake_game.apk"))
    assert CDN in res.urls
    assert any("!assets/config/remote_config.json" in s for s in res.urls[CDN])


def test_urls_not_duplicated_as_bare_refs():
    res = ScanResult()
    scan_bytes(b'x "https://cdn.example.com/b/hero.bundle" y', "mem", res)
    assert list(res.urls) == ["https://cdn.example.com/b/hero.bundle"]
    assert res.asset_refs == {}


def test_trailing_punctuation_trimmed():
    res = ScanResult()
    scan_bytes(b"see (https://example.com/a.json), ok", "mem", res)
    assert "https://example.com/a.json" in res.urls


def test_heuristics():
    assert is_cdn_host("abc.cloudfront.net")
    assert is_cdn_host("cdn.example.com")
    assert not is_cdn_host("api.example.com")
    assert looks_like_asset_url("https://x.com/bundles/a.bundle?v=3")
    assert not looks_like_asset_url("https://x.com/login")
