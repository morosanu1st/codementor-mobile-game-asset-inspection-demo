# Mobile Game Remote Asset Inspection — Learning Demo

A compact, hands-on toolkit + learning path for understanding **how mobile games download
their assets from servers/CDNs** and how to **inspect** what arrives on the device.

> **Ethics & scope.** Use this only on games/apps you own, built yourself, or are explicitly
> permitted to analyse (learning, modding research, debugging your own pipeline). Respect each
> game's Terms of Service and copyright: extracted art/audio belongs to its owners. This repo
> does **not** cover — and you should not attempt — piracy, cheating, account abuse, or
> bypassing DRM/encryption/certificate pinning on software you are not authorised to test.
> All samples here are synthetic.

---

## 1. The typical pipeline

```
 ┌─────────── APK / IPA (installed) ───────────┐
 │ code (dex / libil2cpp.so / Mach-O)           │
 │ bundled config / manifest / catalog.json ────┼──┐  base URL, version, hashes
 │ "starter" assets (StreamingAssets, assets/) │  │
 └──────────────────────────────────────────────┘  │
                                                   ▼
   HTTPS GET  https://cdn.game.com/android/1.4.2/catalog_2024.09.01.hash   (has it changed?)
   HTTPS GET  https://cdn.game.com/android/1.4.2/catalog_2024.09.01.json   (list of bundles)
   HTTPS GET  https://cdn.game.com/android/1.4.2/bundles/ui_9b8e7d6c.bundle (content)
                                                   │
                                                   ▼
   On-device cache (e.g. .../files/UnityCache, OBB, app-private files) keyed by hash/version
```

| Engine / style | What you'll usually see |
|---|---|
| **Unity AssetBundles / Addressables** | `assets/aa/settings.json` + `catalog*.json`/`.hash`; `*.bundle` files starting with `UnityFS`; placeholders like `{RemoteLoadPath}`; names with content hashes |
| **Unreal Engine** | `.pak` (+ `.utoc/.ucas` IoStore) chunks; magic `0x5A6F12E1` in the footer; often AES-encrypted (stop there) |
| **Cocos Creator / custom** | `remote/` folders, `config.<md5>.json`, plain PNG/JPEG/WebP, JSON, texture atlases (`.plist`/`.atlas`), KTX/ASTC/ETC textures, OGG audio |

Common traits: **versioned paths** (`/1.4.2/`), **content hashes in filenames** (cache-busting),
a small **manifest/catalog** fetched first, and **on-device caching** so files download once.

---

## 2. Hands-on learning path

### (1) Static analysis — what does the app *know* before it runs?
```bash
adb shell pm path com.example.mygame          # your own / permitted app
adb pull /data/app/.../base.apk game.apk      # (split APKs: pull every split_*.apk too)
unzip -q game.apk -d game_unzipped
python -m asset_inspector.extract_urls game_unzipped      # URLs, CDN hosts, .bundle/.pak/catalog refs
python -m asset_inspector.extract_urls game.apk --json    # also works directly on the archive
strings -n 8 game_unzipped/classes*.dex | grep -Ei 'https?://|cdn|bundle|catalog'
```
- Open the APK in **jadx-gui** to read the Java/Kotlin layer (search for `http`, `cdn`, `manifest`).
- Unity: Mono builds ship `Assembly-CSharp.dll` (ILSpy); IL2CPP builds ship `libil2cpp.so` +
  `global-metadata.dat`. Addressables config lives in `assets/aa/`.

### (2) Dynamic analysis — what does it *request* at runtime?
1. Run the game in an **Android emulator** (AVD image *without* Google Play is easiest) or on a test device.
2. Proxy it through **mitmproxy** or **HTTP Toolkit** (HTTP Toolkit can auto-configure via ADB).
3. Install the proxy's CA certificate. iOS: install the profile, then enable it under
   *Settings → General → About → Certificate Trust Settings*.
4. **Android 7+ limitation:** apps ignore *user-installed* CAs unless their
   `network_security_config.xml` opts in. For your **own** builds, add a debug-only config that
   trusts user CAs; on a rootable emulator you can place the CA in the system store.
   Apps using **certificate pinning** will refuse the proxy — for apps you don't own, treat that as
   the boundary, not a puzzle.
5. Log and save everything that looks like an asset:
```bash
pip install mitmproxy
mitmdump -s asset_inspector/mitm_asset_logger.py --set asset_dir=captured_assets \
         --set asset_host_filter=cdn.example-game.com      # filter optional
# -> captured_assets/<host>/<sha256-prefix>_<file> + captured_assets/manifest.csv
```

### (3) Identify formats by magic bytes (don't trust extensions)
```bash
python -m asset_inspector.identify captured_assets/
# unityfs  ... png  ... ogg  ... ktx  ... astc  ... gzip  ... unreal_pak  ... json  ... unknown
```
Detects UnityFS/UnityWeb, PNG, JPEG, WebP, OGG, WAV, FSB5, KTX/KTX2, ASTC, PKM, DDS, ZIP/APK,
gzip, DEX, SQLite, JSON and the Unreal `.pak` footer. `unknown` with high entropy usually means
encrypted/custom-packed data.

### (4) Open Unity bundles & catalogs
```bash
python -m asset_inspector.inspect_catalog catalog.json                  # remote vs local vs templated bundles
python -m asset_inspector.inspect_catalog catalog.json --base-url https://cdn.example-game.com/aa
pip install UnityPy
python -m asset_inspector.unity_dump some.bundle --export exported/     # list objects, export textures/text
```
GUI alternative: **AssetStudio** (Windows) / AssetRipper. Binary catalogs (`catalog.bin`,
Addressables 2.x) are out of scope for this small parser.

---

## 3. How I'd teach this in sessions

| Session | Goal | Hands-on |
|---|---|---|
| **1 — Map the pipeline** (60 min) | Understand bundled vs remote content, CDNs, versioning & caching | Unzip an APK (yours or an open-source Unity sample), run `extract_urls`, read `assets/aa/` + a catalog with `inspect_catalog`, sketch the request flow |
| **2 — Watch it live** (60 min) | Intercept HTTPS traffic responsibly | Emulator + mitmproxy/HTTP Toolkit, CA install, Android 7+ trust rules & pinning limits, capture with `mitm_asset_logger`, read `manifest.csv` |
| **3 — Understand the files** (60 min) | Formats, engines, tooling | `identify` the captures, open bundles with UnityPy/AssetStudio, compare Unreal `.pak` / Cocos layouts; optional: build a tiny Unity Addressables project and host its bundles on a local server to see both sides |

Between sessions: a short checklist + a small exercise on your own build so each step is repeatable.

---

## Quick start
```bash
git clone https://github.com/morosanu1st/codementor-mobile-game-asset-inspection-demo
cd codementor-mobile-game-asset-inspection-demo
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
python scripts/make_samples.py                       # regenerate synthetic samples/
python -m asset_inspector.extract_urls samples/fake_apk
python -m asset_inspector.identify samples/
python -m asset_inspector.inspect_catalog samples/cache/catalog.json
pytest -q
```

## Layout
```
asset_inspector/
  extract_urls.py       # URLs / CDN hosts / .bundle .pak catalog refs in dirs, files or .apk/.ipa
  identify.py           # magic-byte file type detection
  mitm_asset_logger.py  # mitmproxy addon: save asset-like responses + CSV manifest
  inspect_catalog.py    # Unity Addressables catalog.json -> remote bundle URLs
  unity_dump.py         # optional UnityPy object listing / texture export
scripts/make_samples.py # builds synthetic samples (no real game data)
samples/                # fake_apk/, fake_game.apk, cache/ with magic-byte stubs
tests/                  # pytest suite
```

MIT licensed. Built by Mihai Chindris for 1:1 mentoring sessions.
