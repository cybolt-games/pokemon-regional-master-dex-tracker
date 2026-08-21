#!/usr/bin/env python3
"""Scrape PokemonDB for dex-order cross-checks, locations and exclusives.

PokeAPI is the primary source; this corroborates it and fills its gaps. Three
things only PokemonDB gives us:

* An independent rendering of each game's regional dex order, which the build
  compares against PokeAPI's and refuses to ship on mismatch.
* Plain-English "Where to find" text for every game — including the ones where
  PokeAPI has no encounter data at all (BDSP, Legends Arceus, Scarlet/Violet,
  Legends Z-A), where this becomes the *only* location source.
* Version-exclusive lists per game pair.

One species page carries the location table for every game it appears in, so
the per-species crawl is done once and serves the whole registry.

robots.txt permits every path used here and publishes Crawl-delay: 2, which
lib.http_cache honours. It also bans a wget User-Agent, so the real UA matters.
"""

import json
import os
import re
import sys

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import config, http_cache

BASE = "https://pokemondb.net"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "raw", "parsed")
OUT_PATH = os.path.join(OUT_DIR, "pokemondb.json")


def parse_dex(game_slug):
    """A game's regional dex grid: number, name, slug, types, sprite URL."""
    soup = BeautifulSoup(http_cache.fetch(f"{BASE}/pokedex/game/{game_slug}"),
                         "html.parser")
    container = soup.select_one("div.infocard-list-pkmn-lg")
    if container is None:
        return None

    entries = []
    for card in container.select("div.infocard"):
        link = card.select_one("a.ent-name")
        number = card.select_one("span.infocard-lg-data small")
        image = card.select_one("span.infocard-lg-img img")
        if not (link and number):
            continue
        entries.append({
            "dex": int(number.get_text(strip=True).lstrip("#")),
            "name": link.get_text(strip=True),
            "slug": link["href"].rsplit("/", 1)[-1],
            "types": [t.get_text(strip=True).lower() for t in card.select("a.itype")],
            "spriteUrl": image["src"] if image else None,
        })
    entries.sort(key=lambda e: e["dex"])
    return entries


def parse_exclusives(path, versions):
    """Version-exclusive lists from a /<game>/exclusive page."""
    try:
        html = http_cache.fetch(f"{BASE}/{path}")
    except Exception:
        return None
    soup = BeautifulSoup(html, "html.parser")
    out = {v: [] for v in versions}
    for heading in soup.find_all(["h2", "h3"]):
        text = heading.get_text(" ", strip=True).lower().replace(" ", "")
        match = next((v for v in versions if v.replace("-", "") in text), None)
        if match is None:
            continue
        for sibling in heading.find_next_siblings():
            if sibling.name in ("h2", "h3"):
                break
            for link in sibling.select("a.ent-name"):
                slug = link["href"].rsplit("/", 1)[-1]
                if slug not in out[match]:
                    out[match].append(slug)
    return out if any(out.values()) else None


def parse_locations(slug):
    """Every game row of a species' "Where to find" table.

    The table is keyed by <span class="igame <game>"> markers, so one row can
    cover several versions. Returns {version_slug: text} for all games.
    """
    soup = BeautifulSoup(http_cache.fetch(f"{BASE}/pokedex/{slug}"), "html.parser")
    anchor = soup.find(id="dex-locations")
    if anchor is None:
        return {}

    rows = {}
    for table in anchor.find_all_next("table", class_="vitals-table", limit=2):
        for row in table.select("tr"):
            header, cell = row.find("th"), row.find("td")
            if not (header and cell):
                continue
            games = []
            for span in header.select("span.igame"):
                classes = [c for c in span.get("class", []) if c != "igame"]
                if classes:
                    games.append(classes[0])
            if not games:
                continue
            # get_text with a separator leaves " ," before each comma.
            text = re.sub(r"\s+([,;])", r"\1", cell.get_text(" ", strip=True))
            for game in games:
                rows[game] = text
        if rows:
            break
    return rows


def main():
    only = None
    if "--games" in sys.argv:
        only = set(sys.argv[sys.argv.index("--games") + 1].split(","))

    games = [g for g in config.games() if only is None or g["id"] in only]
    print(f"registry: {len(games)} game(s)")

    # --- dex grids, one per distinct PokemonDB game slug
    dexes = {}
    wanted_slugs = {}
    for game in games:
        for dex in game.get("dexes", []):
            slug = dex.get("pokemondbDex")
            if not slug or slug in dexes:
                continue
            entries = parse_dex(slug)
            if entries is None:
                print(f"  dex {slug}: NOT FOUND (page has no grid)")
                continue
            dexes[slug] = entries
            print(f"  dex {slug}: {len(entries)} entries")
    for entries in dexes.values():
        for entry in entries:
            wanted_slugs[entry["slug"]] = True

    # Species we need location text for: every entry of every registered dex.
    pokeapi_path = os.path.join(OUT_DIR, "pokeapi.json")
    if os.path.exists(pokeapi_path):
        with open(pokeapi_path, encoding="utf-8") as fh:
            api = json.load(fh)
        for dex in api["pokedexes"].values():
            for entry in dex["entries"]:
                wanted_slugs[entry["slug"]] = True

    # --- exclusives, one per version group that declares a page
    exclusives = {}
    for game in games:
        vg = game["versionGroup"]
        path = game.get("sources", {}).get("pokemondbExclusivesPath")
        if not path or vg in exclusives:
            continue
        versions = [g["pokeapiVersion"] for g in config.games()
                    if g["versionGroup"] == vg]
        parsed = parse_exclusives(path, versions)
        if parsed:
            exclusives[vg] = parsed
            print(f"  exclusives {vg}: "
                  + ", ".join(f"{v}={len(s)}" for v, s in parsed.items()))
        else:
            print(f"  exclusives {vg}: none found at /{path}")

    # --- location text, one page per species, reused by every game
    slugs = sorted(wanted_slugs)
    print(f"fetching {len(slugs)} species location tables "
          f"(2s crawl-delay on a cold cache)...")
    locations = {}
    for index, slug in enumerate(slugs, start=1):
        try:
            locations[slug] = parse_locations(slug)
        except Exception as exc:  # noqa: BLE001
            print(f"    {slug}: {exc}")
            locations[slug] = {}
        if index % 64 == 0 or index == len(slugs):
            print(f"  {index}/{len(slugs)}")

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump({"source": "pokemondb", "dexes": dexes,
                   "exclusives": exclusives, "locations": locations},
                  fh, separators=(",", ":"), sort_keys=True)
    http_cache.save_manifest()

    covered = sum(1 for v in locations.values() if v)
    print(f"\nwrote {OUT_PATH}")
    print(f"  {covered}/{len(slugs)} species have location text")
    seen_games = {}
    for rows in locations.values():
        for game in rows:
            seen_games[game] = seen_games.get(game, 0) + 1
    print(f"  game keys seen: {len(seen_games)}")
    for game in sorted(seen_games, key=lambda g: -seen_games[g])[:60]:
        print(f"    {game:26s} {seen_games[game]}")


if __name__ == "__main__":
    main()
