#!/usr/bin/env python3
"""Scrape Legends: Z-A locations from Serebii's species pages.

Neither PokeAPI nor PokemonDB has any Z-A location data — PokeAPI has no
encounter tables for the version at all, and PokemonDB answers "Location data
not yet available" for all 1025 species. Serebii does have it, filed on the
pages it already serves for Scarlet/Violet:

    <td class="fooza">Legends: Z-A</td>
    <td class="fooinfo"><a href="/pokearth/lumiosecity/wildzone20.shtml">Wild Zone 20</a></td>
    <td class="foozamd">Legends: Z-A Mega Dimension</td>
    <td class="fooinfo">Hyperspace Lumiose - Grass (2 Star), ...</td>

Only species in the Lumiose and Hyperspace dexes are fetched, so this is ~364
requests rather than the full national dex.
"""

import json
import os
import re
import sys

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import config, http_cache

BASE = "https://www.serebii.net/pokedex-sv/{slug}/"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "raw", "parsed")
OUT_PATH = os.path.join(OUT_DIR, "serebii_za.json")

# The class on the label cell tells us which dex the row belongs to.
ROW_CLASSES = {"fooza": "lumiose", "foozamd": "hyperspace"}

# Serebii keeps the punctuation PokeAPI strips out of its slugs. Verified by
# fetching each; there is no derivable rule (an apostrophe survives, a space
# does not, and the full stop lands in different places).
SLUG_ALIASES = {
    "farfetchd": "farfetch'd",
    "sirfetchd": "sirfetch'd",
    "mr-mime": "mr.mime",
    "mr-rime": "mr.rime",
    "mime-jr": "mimejr.",
}


def parse_species(slug):
    """Z-A location text for one species, keyed by dex."""
    html = http_cache.fetch(
        BASE.format(slug=SLUG_ALIASES.get(slug, slug)), encoding="latin-1")
    soup = BeautifulSoup(html, "html.parser")
    out = {}
    for cell in soup.find_all("td"):
        classes = cell.get("class") or []
        key = next((ROW_CLASSES[c] for c in classes if c in ROW_CLASSES), None)
        if not key:
            continue
        value = cell.find_next_sibling("td")
        if value is None:
            continue
        # The same class labels a "Legends: Z-A" row in the flavour-text table
        # too, and colspan is not consistent between pages (Pikachu's flavour
        # row spans two columns, Mewtwo's location row does not). What always
        # holds is that a location links somewhere and a Pokedex entry never
        # does.
        if not value.find("a", href=True):
            continue
        if key in out:
            continue  # first linked row wins
        text = re.sub(r"\s+", " ", value.get_text(" ", strip=True)).strip()
        if text and text.lower() not in ("", "-"):
            out[key] = text
    return out


def main():
    with open(os.path.join(OUT_DIR, "pokeapi.json"), encoding="utf-8") as fh:
        api = json.load(fh)

    wanted = {}
    for game in config.games():
        if game.get("pokeapiVersion") != "legends-za":
            continue
        for dex in game["dexes"]:
            for entry in api["pokedexes"][dex["pokeapiPokedex"]]["entries"]:
                wanted[entry["slug"]] = entry["natdex"]

    slugs = sorted(wanted)
    print(f"{len(slugs)} species in the Z-A dexes (2s crawl-delay on a cold cache)")

    locations, misses = {}, []
    for index, slug in enumerate(slugs, start=1):
        try:
            found = parse_species(slug)
        except Exception as exc:  # noqa: BLE001
            misses.append((slug, str(exc)[:50]))
            continue
        if found:
            locations[slug] = found
        if index % 48 == 0 or index == len(slugs):
            print(f"  {index}/{len(slugs)}  ({len(locations)} with data)")

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump({"source": "serebii", "urlPattern": BASE,
                   "locations": locations}, fh, indent=1, ensure_ascii=False,
                  sort_keys=True)
    http_cache.save_manifest()

    by_dex = {}
    for rows in locations.values():
        for key in rows:
            by_dex[key] = by_dex.get(key, 0) + 1
    print(f"\nwrote {OUT_PATH}")
    print(f"  {len(locations)}/{len(slugs)} species have Z-A location text")
    for key, count in sorted(by_dex.items()):
        print(f"    {key:12s} {count}")
    if misses:
        print(f"  {len(misses)} fetch failure(s): "
              + ", ".join(s for s, _ in misses[:8]))


if __name__ == "__main__":
    main()
