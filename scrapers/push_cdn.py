#!/usr/bin/env python3
"""Publish the vendored assets to a self-hosted CDN over scp.

Entirely optional. Everything published here is also available locally, so a
CDN is an optimisation and a sharing point, never a dependency — the default
deployment serves every file locally and never contacts it.

Configure it in ``config.local.json`` (see ``config.local.example.json``):

    "publish": {
      "enabled": true,
      "host": "user@cdn.example.com",
      "remoteDir": "/srv/cdn",
      "namespace": "pokemon",
      "baseUrl": "https://cdn.example.com/pokemon/"
    }

Note that ``remoteDir`` is the filesystem root your web server serves from and
``baseUrl`` is where that root appears on the web — they often differ.

Run with --push to actually send; the default is a dry run.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import config

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")

_PUBLISH = config.load().get("publish", {})
HOST = _PUBLISH.get("host")
REMOTE_DIR = _PUBLISH.get("remoteDir")
NAMESPACE = _PUBLISH.get("namespace", "pokemon")
BASE_URL = _PUBLISH.get("baseUrl", "")

# (source directory, path inside the namespace)
def build_payload():
    """(source dir, path inside the namespace) for everything we publish.

    Sprite sets are discovered rather than listed, so a new game's set ships
    without touching this file.
    """
    payload = []
    sprite_root = os.path.join(SITE, "assets", "sprites")
    if os.path.isdir(sprite_root):
        for name in sorted(os.listdir(sprite_root)):
            path = os.path.join(sprite_root, name)
            if os.path.isdir(path):
                payload.append((path, f"sprites/{name}"))
    payload += [
        (os.path.join(SITE, "assets", "boxart"), "boxart"),
        (os.path.join(SITE, "data"), "data"),
        (os.path.join(ROOT, "raw", "parsed"), "data/parsed"),
    ]
    return payload


PAYLOAD = build_payload()


def collect(stage):
    files = []
    for source, target in PAYLOAD:
        if not os.path.isdir(source):
            print(f"  skip (missing): {source}")
            continue
        dest = os.path.join(stage, NAMESPACE, target)
        os.makedirs(dest, exist_ok=True)
        for name in sorted(os.listdir(source)):
            path = os.path.join(source, name)
            if not os.path.isfile(path):
                continue
            shutil.copy2(path, os.path.join(dest, name))
            files.append(
                {
                    "path": f"{target}/{name}",
                    "bytes": os.path.getsize(path),
                    "sha256": hashlib.sha256(open(path, "rb").read()).hexdigest(),
                }
            )
    return files


def write_manifest(stage, files):
    manifest = {
        "name": NAMESPACE,
        "description": "Scraped Pokémon reference assets for Regional Dex Buddy "
                       "and any other service that wants them.",
        "baseUrl": BASE_URL,
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "contents": {
            "sprites/hgss/{nationalDexId}.png":
                "Gen-4 HeartGold/SoulSilver front sprites, 80x80 RGBA PNG.",
            "boxart/{game}.jpg": "Game cover art, 360px wide JPEG.",
            "data/{game}.json":
                "Built per-version dataset: dex order, box/slot placement, "
                "locations, exclusives, notes.",
            "data/sources.json":
                "Provenance for every HTTP response behind the datasets.",
            "data/parsed/{source}.json":
                "Normalised scrape output per source, before merging.",
        },
        "sources": ["https://pokeapi.co/", "https://pokemondb.net/",
                    "https://www.serebii.net/"],
        "notice": "Pokémon and Pokémon sprites are © Nintendo / Creatures Inc. / "
                  "GAME FREAK inc. Personal, non-commercial reference use.",
        "files": sorted(files, key=lambda f: f["path"]),
    }
    with open(os.path.join(stage, NAMESPACE, "manifest.json"), "w",
              encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1)


def verify(files, sample=12):
    """Spot-check that what we sent is what the CDN serves."""
    step = max(1, len(files) // sample)
    checked = failed = 0
    for record in files[::step]:
        url = BASE_URL + record["path"]
        try:
            with urllib.request.urlopen(url, timeout=20) as response:
                served = hashlib.sha256(response.read()).hexdigest()
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL {record['path']}: {exc}")
            failed += 1
            continue
        checked += 1
        if served != record["sha256"]:
            print(f"  FAIL {record['path']}: checksum mismatch")
            failed += 1
    print(f"  verified {checked} sampled files, {failed} problem(s)")
    return failed == 0


def main():
    push = "--push" in sys.argv
    if not _PUBLISH.get("enabled"):
        print("publish.enabled is false in config.json — nothing to do.")
        print("This deployment serves assets locally; publishing is optional.")
        if push:
            raise SystemExit(1)
        return
    if not (HOST and REMOTE_DIR and BASE_URL):
        raise SystemExit("config.json: publish needs host, remoteDir and baseUrl")
    stage = tempfile.mkdtemp(prefix="rdb-cdn-")
    try:
        files = collect(stage)
        write_manifest(stage, files)
        total = sum(f["bytes"] for f in files)
        print(f"{len(files)} files, {total / 1024 / 1024:.2f} MB -> {BASE_URL}")

        if not push:
            print("\ndry run — pass --push to upload")
            return

        subprocess.run(
            ["scp", "-q", "-o", "BatchMode=yes", "-r",
             os.path.join(stage, NAMESPACE), f"{HOST}:{REMOTE_DIR}/"],
            check=True,
        )
        subprocess.run(
            ["ssh", "-o", "BatchMode=yes", HOST,
             f"chmod -R a+rX {REMOTE_DIR}/{NAMESPACE}"],
            check=True,
        )
        print("uploaded; verifying over HTTPS...")
        if not verify(files):
            raise SystemExit(1)
        print("done")
    finally:
        shutil.rmtree(stage, ignore_errors=True)


if __name__ == "__main__":
    main()
