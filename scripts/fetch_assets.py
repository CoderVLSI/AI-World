"""Download the third-party character models listed in godot/assets/manifest.json (not stored in git).

Needs your own Sketchfab API token in the environment (never written anywhere):
    SKETCHFAB_API_TOKEN=... python scripts/fetch_assets.py [--force] [--check]

Writes godot/assets/characters/*.glb, godot/assets/manifest.lock.json (sha256 of each file) and
godot/assets/ATTRIBUTIONS.md (the credit lines the CC-BY licenses require). After fetching, open the
project once in Godot (or run `godot --headless --import --path godot`) so the models are imported.
"""
import argparse
import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "godot" / "assets"
API = "https://api.sketchfab.com/v3/models/{uid}/download"
PAGE = "https://sketchfab.com/3d-models/{uid}"


def load_manifest(path=ASSETS / "manifest.json"):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def attributions(manifest):
    """The credit text for every model in the manifest (what CC-BY requires)."""
    lines = ["# Third-party model credits", "",
             "These models are downloaded on demand by `scripts/fetch_assets.py` and are not part of this repository.",
             "Each is used under the license shown; follow the linked page for the full terms.", ""]
    for key, c in sorted(manifest["characters"].items()):
        lines.append(f"- **{c['title']}** by {c['author']} — {c['license']} — {PAGE.format(uid=c['sketchfab_uid'])}")
    return "\n".join(lines) + "\n"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_one(uid, destination, token):
    request = urllib.request.Request(API.format(uid=uid), headers={"Authorization": f"Token {token}"})
    links = json.load(urllib.request.urlopen(request, timeout=30))
    if "glb" not in links:
        raise RuntimeError(f"model {uid} offers no glb download (formats: {sorted(links)})")
    data = urllib.request.urlopen(links["glb"]["url"], timeout=180).read()   # signed CDN link: no token sent
    if data[:4] != b"glTF":
        raise RuntimeError(f"model {uid}: downloaded file is not a binary glTF")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--force", action="store_true", help="re-download files that already exist")
    p.add_argument("--check", action="store_true", help="only verify existing files against manifest.lock.json")
    args = p.parse_args(argv)
    manifest = load_manifest()
    lock_path = ASSETS / "manifest.lock.json"
    lock = json.loads(lock_path.read_text()) if lock_path.exists() else {}
    if args.check:
        bad = [k for k, c in manifest["characters"].items()
               if not (ASSETS / c["file"]).exists() or lock.get(k) != sha256(ASSETS / c["file"])]
        print("OK" if not bad else "missing or changed: " + ", ".join(bad))
        return 1 if bad else 0
    token = os.environ.get("SKETCHFAB_API_TOKEN")
    if not token:
        print("Set SKETCHFAB_API_TOKEN (your own Sketchfab API token) to download the models.", file=sys.stderr)
        return 2
    for key, c in manifest["characters"].items():
        target = ASSETS / c["file"]
        if target.exists() and not args.force:
            print(f"{key}: already present")
        else:
            print(f"{key}: downloading {c['title']} by {c['author']} ...")
            fetch_one(c["sketchfab_uid"], target, token)
        lock[key] = sha256(target)
    lock_path.write_text(json.dumps(lock, indent=2) + "\n")
    (ASSETS / "ATTRIBUTIONS.md").write_text(attributions(manifest), encoding="utf-8")
    print("done; credits written to godot/assets/ATTRIBUTIONS.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
