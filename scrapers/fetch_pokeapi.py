#!/usr/bin/env python3
"""Pull everything PokeAPI knows about the games in games.json.

Writes ``raw/parsed/pokeapi.json``: the entry order of every registered
regional dex, per-species metadata, per-version encounter tables, evolution
chains, and human-readable location names.

Scoping notes:

* Work is keyed on the *union* of species across every registered dex, so each
  species is fetched once no matter how many games include it.
* ``/encounters`` returns every version a species ever appeared in, so it is
  filtered down to the versions we actually register — Magikarp alone spans
  286 areas across 36 versions otherwise.
* ``pokemon_species.url`` ends in the national dex id, which is also the sprite
  key and the ``/pokemon/{id}/`` key, so no extra lookup is needed.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import config, http_cache

API = "https://pokeapi.co/api/v2"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "raw", "parsed")
OUT_PATH = os.path.join(OUT_DIR, "pokeapi.json")


def english(names):
    for item in names or []:
        if item.get("language", {}).get("name") == "en":
            return item.get("name") or item.get("genus")
    return None


def id_from_url(url):
    return int(url.rstrip("/").rsplit("/", 1)[-1])


def registered():
    """(pokedex slugs, version names) across every game in the registry."""
    dexes, versions = [], []
    for entry in config.games():
        for dex in entry.get("dexes", []):
            if dex["pokeapiPokedex"] not in dexes:
                dexes.append(dex["pokeapiPokedex"])
        version = entry.get("pokeapiVersion")
        if version and version not in versions:
            versions.append(version)
    return dexes, versions


def fetch_pokedex(slug):
    data = http_cache.fetch_json(f"{API}/pokedex/{slug}/")
    entries = [
        {
            "dex": e["entry_number"],
            "natdex": id_from_url(e["pokemon_species"]["url"]),
            "slug": e["pokemon_species"]["name"],
        }
        for e in data["pokemon_entries"]
    ]
    entries.sort(key=lambda e: e["dex"])
    return {
        "slug": slug,
        "name": english(data["names"]),
        "versionGroups": [vg["name"] for vg in data["version_groups"]],
        "entries": entries,
    }


def fetch_species(natdex):
    data = http_cache.fetch_json(f"{API}/pokemon-species/{natdex}/")
    evolves_from = data.get("evolves_from_species")
    return {
        "name": english(data["names"]),
        "genus": english(data.get("genera")),
        "isBaby": data.get("is_baby", False),
        "isLegendary": data.get("is_legendary", False),
        "isMythical": data.get("is_mythical", False),
        "eggGroups": [g["name"] for g in data.get("egg_groups", [])],
        "evolvesFrom": evolves_from["name"] if evolves_from else None,
        "evolutionChainUrl": (data.get("evolution_chain") or {}).get("url"),
    }


def fetch_pokemon(natdex):
    data = http_cache.fetch_json(f"{API}/pokemon/{natdex}/")
    return {"types": [t["type"]["name"]
                      for t in sorted(data["types"], key=lambda t: t["slot"])]}


def fetch_encounters(natdex, versions):
    data = http_cache.fetch_json(f"{API}/pokemon/{natdex}/encounters")
    areas = []
    for area in data:
        per_version = {}
        for detail in area["version_details"]:
            version = detail["version"]["name"]
            if version not in versions:
                continue
            rows = [
                {
                    "method": row["method"]["name"],
                    "minLevel": row["min_level"],
                    "maxLevel": row["max_level"],
                    "chance": row["chance"],
                    "conditions": [c["name"] for c in row["condition_values"]],
                }
                for row in detail["encounter_details"]
            ]
            if rows:
                per_version[version] = rows
        if per_version:
            areas.append({"area": area["location_area"]["name"], "versions": per_version})
    return areas


def flatten_chain(node, acc, parent=None):
    species = node["species"]["name"]
    for detail in node.get("evolution_details") or []:
        acc.append({
            "species": species,
            "from": parent,
            "trigger": (detail.get("trigger") or {}).get("name"),
            "minLevel": detail.get("min_level"),
            "item": (detail.get("item") or {}).get("name"),
            "heldItem": (detail.get("held_item") or {}).get("name"),
            "knownMove": (detail.get("known_move") or {}).get("name"),
            "location": (detail.get("location") or {}).get("name"),
            "timeOfDay": detail.get("time_of_day") or None,
            "minHappiness": detail.get("min_happiness"),
            "minBeauty": detail.get("min_beauty"),
            "minAffection": detail.get("min_affection"),
            "needsOverworldRain": detail.get("needs_overworld_rain"),
            "tradeSpecies": (detail.get("trade_species") or {}).get("name"),
            "gender": detail.get("gender"),
            "relativePhysicalStats": detail.get("relative_physical_stats"),
            "partySpecies": (detail.get("party_species") or {}).get("name"),
            "partyType": (detail.get("party_type") or {}).get("name"),
            "turnUpsideDown": detail.get("turn_upside_down"),
        })
    for child in node.get("evolves_to") or []:
        flatten_chain(child, acc, species)


def fetch_location_names(area_slugs):
    """Display names for encounter areas.

    Location-area English names render routes as "Road 29" where the parent
    location correctly says "Route 29", and a few ship an empty names array —
    both handled at label time, so both layers are captured here.
    """
    out, parents = {}, {}
    for index, slug in enumerate(sorted(area_slugs), start=1):
        area = http_cache.fetch_json(f"{API}/location-area/{slug}/")
        parent_url = area["location"]["url"]
        if parent_url not in parents:
            parents[parent_url] = http_cache.fetch_json(parent_url)
        parent = parents[parent_url]
        out[slug] = {
            "areaName": english(area.get("names")),
            "locationSlug": parent["name"],
            "locationName": english(parent.get("names")),
        }
        if index % 200 == 0:
            print(f"    locations {index}/{len(area_slugs)}")
    return out


def main():
    dex_slugs, versions = registered()
    version_set = set(versions)
    print(f"registry: {len(dex_slugs)} pokedex(es), {len(versions)} version(s)")

    pokedexes = {}
    species_ids = {}
    for slug in dex_slugs:
        dex = fetch_pokedex(slug)
        pokedexes[slug] = dex
        for entry in dex["entries"]:
            species_ids[entry["slug"]] = entry["natdex"]
        print(f"  {slug}: {len(dex['entries'])} entries ({dex['name']})")

    total = len(species_ids)
    print(f"union: {total} distinct species")

    species, pokemon, encounters = {}, {}, {}
    chain_urls, area_slugs = set(), set()

    for index, (slug, natdex) in enumerate(sorted(species_ids.items(),
                                                  key=lambda kv: kv[1]), start=1):
        species[slug] = fetch_species(natdex)
        pokemon[slug] = fetch_pokemon(natdex)
        encounters[slug] = fetch_encounters(natdex, version_set)

        if species[slug]["evolutionChainUrl"]:
            chain_urls.add(species[slug]["evolutionChainUrl"])
        for area in encounters[slug]:
            area_slugs.add(area["area"])

        if index % 64 == 0 or index == total:
            print(f"  species {index}/{total}")

    print(f"evolution chains: {len(chain_urls)}")
    evolutions = []
    for url in sorted(chain_urls):
        flatten_chain(http_cache.fetch_json(url)["chain"], evolutions)

    print(f"location areas: {len(area_slugs)}")
    locations = fetch_location_names(area_slugs)

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump({
            "source": "pokeapi",
            "pokedexes": pokedexes,
            "versions": versions,
            "species": species,
            "pokemon": pokemon,
            "encounters": encounters,
            "evolutions": evolutions,
            "locations": locations,
        }, fh, separators=(",", ":"), sort_keys=True)
    http_cache.save_manifest()

    by_version = {v: 0 for v in versions}
    for rows in encounters.values():
        seen = set()
        for area in rows:
            seen.update(area["versions"])
        for v in seen:
            by_version[v] += 1
    print(f"\nwrote {OUT_PATH}")
    print("  species with encounter data, per version:")
    for version in versions:
        count = by_version[version]
        flag = "  <-- EMPTY" if count == 0 else ""
        print(f"    {version:28s} {count:5d} / {total}{flag}")


if __name__ == "__main__":
    main()
