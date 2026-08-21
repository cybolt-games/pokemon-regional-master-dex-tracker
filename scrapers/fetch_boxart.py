#!/usr/bin/env python3
"""Vendor game box art for the menu tiles.

PokemonDB publishes cover art at a stable, predictable path for every mainline
game, which makes adding a future generation a one-line change here. Images are
360px wide JPEGs, ~50-75 KB each.
"""

import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import config, http_cache

BOXART = "https://img.pokemondb.net/boxes/{slug}.jpg"

def alternate_sources():
    """Covers that do not come from PokemonDB, with their real URLs.

    PokemonDB has no Legends Z-A cover, and the Pokemon HOME tile is an app
    icon rather than a game. Both URLs live in games.json so this stays a data
    change, and so a fresh checkout can fetch them like everything else.
    """
    out = {}
    for game in config.games():
        url = (game.get("sources") or {}).get("boxartUrl")
        art = game.get("boxart")
        if url and art:
            out[art.split("/")[-1].rsplit(".", 1)[0]] = url

    icon = (config.games_meta() or {}).get("homeIcon") or {}
    if icon.get("url") and icon.get("path"):
        out[icon["path"].split("/")[-1].rsplit(".", 1)[0]] = icon["url"]
    return out


def wanted():
    """Cover art paths from the registry, deduplicated."""
    out = {}
    for game in config.games():
        art = game.get("boxart")
        if art:
            out[art.split("/")[-1].rsplit(".", 1)[0]] = art
    icon = (config.games_meta() or {}).get("homeIcon") or {}
    if icon.get("path"):
        out[icon["path"].split("/")[-1].rsplit(".", 1)[0]] = icon["path"]
    return out

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "site", "assets", "boxart")


def jpeg_size(data):
    """Width/height from the JPEG SOF marker, to verify what we downloaded."""
    i = 2
    while i < len(data) - 9:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3):
            height, width = struct.unpack(">HH", data[i + 5:i + 9])
            return width, height
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    return None


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    failures = []
    slugs = sorted(wanted())

    alternates = alternate_sources()
    for slug in slugs:
        url = alternates.get(slug) or BOXART.format(slug=slug)
        try:
            data = http_cache.fetch(url, binary=True)
        except Exception as exc:  # noqa: BLE001 - report and continue
            failures.append((slug, str(exc)))
            continue

        size = jpeg_size(data)
        if size is None:
            failures.append((slug, "not a JPEG"))
            continue

        with open(os.path.join(OUT_DIR, f"{slug}.jpg"), "wb") as fh:
            fh.write(data)
        print(f"  {slug:12s} {size[0]}x{size[1]}  {len(data) / 1024:.0f} KB")

    http_cache.save_manifest()
    total = sum(
        os.path.getsize(os.path.join(OUT_DIR, n)) for n in os.listdir(OUT_DIR)
    )
    print(f"\nwrote {len(slugs) - len(failures)} covers to {OUT_DIR} "
          f"({total / 1024:.0f} KB total)")
    if failures:
        for slug, reason in failures:
            print(f"  FAILED {slug}: {reason}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
