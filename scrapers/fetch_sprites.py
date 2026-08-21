#!/usr/bin/env python3
"""Vendor era-correct sprites for every registered game.

Era-correct art is the whole point of the box pages — a modern render beside a
DS-era box is useless for matching what is on screen. Sprites come from
whichever source actually has that game's set:

* PokeAPI's sprite repository, keyed by national dex id, for the games it
  covers (Gen 1 through Gen 4, BW, XY, ORAS, USUM, BDSP, SV).
* PokemonDB, keyed by species slug, for the sets PokeAPI has no folder for
  (Sun/Moon, Let's Go, Sword/Shield, Legends: Arceus).

Only the species each dex actually contains are downloaded, so the total stays
far below a full mirror. Failures are reported per file rather than silently
substituting something else.
"""

import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import config, http_cache

API = "https://pokeapi.co/api/v2"

# PokeAPI and PokemonDB spell regional forms differently.
FORM_ALIASES = {
    "hisui": "hisuian",
    "alola": "alolan",
    "galar": "galarian",
    "paldea": "paldean",
}


def form_slugs(natdex):
    """Every variety name for a species, spelled the way PokemonDB spells it.

    Games that show a regional form — Legends: Arceus showing Hisuian Growlithe,
    Sun/Moon showing Oricorio's styles — file the sprite under the form name,
    not the base species. The variety list comes from PokeAPI rather than being
    guessed, so the correct form is used instead of a stand-in.
    """
    try:
        data = http_cache.fetch_json(f"{API}/pokemon-species/{natdex}/")
    except Exception:  # noqa: BLE001
        return []
    out = []
    for variety in data.get("varieties", []):
        name = variety["pokemon"]["name"]
        if variety.get("is_default"):
            continue
        base, _, suffix = name.partition("-")
        if suffix:
            out.append(f"{base}-{FORM_ALIASES.get(suffix, suffix)}")
        out.append(name)
    return out

POKEAPI_BASE = ("https://raw.githubusercontent.com/PokeAPI/sprites/master/"
                "sprites/pokemon/versions/{set}/{id}.png")
POKEAPI_OTHER = ("https://raw.githubusercontent.com/PokeAPI/sprites/master/"
                 "sprites/pokemon/other/{set}/{id}.png")
POKEMONDB_BASE = "https://img.pokemondb.net/sprites/{set}/normal/{slug}.png"


def source_url(spec, natdex, slug):
    source = spec["source"]
    if source == "pokeapi":
        return POKEAPI_BASE.format(**{"set": spec["set"], "id": natdex})
    if source == "pokeapi-other":
        return POKEAPI_OTHER.format(**{"set": spec["set"], "id": natdex})
    return POKEMONDB_BASE.format(**{"set": spec["set"], "slug": slug})

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARSED = os.path.join(ROOT, "raw", "parsed", "pokeapi.json")
ASSET_DIR = os.path.join(ROOT, "site", "assets")


def png_size(data):
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", data[16:24])


def main():
    only = None
    if "--games" in sys.argv:
        only = set(sys.argv[sys.argv.index("--games") + 1].split(","))

    # Which species each dex contains. The built datasets in site/data carry
    # this and are committed, so a fresh checkout can fetch its assets without
    # first re-running the whole scrape; the raw cache is used when present.
    def species_for(game):
        built = os.path.join(ROOT, "site", "data", f"{game['id']}.json")
        if os.path.isfile(built):
            with open(built, encoding="utf-8") as fh:
                data = json.load(fh)
            return [(e["natdex"], e["slug"])
                    for dex in data["dexes"] for e in dex["entries"]]
        if os.path.isfile(PARSED):
            with open(PARSED, encoding="utf-8") as fh:
                pokedexes = json.load(fh)["pokedexes"]
            out = []
            for dex in game.get("dexes", []):
                source = pokedexes.get(dex["pokeapiPokedex"])
                if source:
                    out += [(e["natdex"], e["slug"]) for e in source["entries"]]
            return out
        raise SystemExit(
            f"no species list for {game['id']}: neither site/data/{game['id']}.json "
            f"nor {PARSED} exists. Run the fetchers and build first."
        )

    # Work out exactly which (sprite set, species) pairs are needed.
    wanted = {}
    for game in config.games():
        if only and game["id"] not in only:
            continue
        spec = game.get("sprites")
        if not spec:
            continue
        target = wanted.setdefault(
            spec["dir"], {"spec": dict(spec), "species": {}, "games": []})
        target["games"].append(game["id"])
        # Several games can share one sprite dir (Scarlet, Violet and Legends
        # Z-A all use sprites/sv) with different coverage needs. If any of them
        # declares a fallback, the shared set has to honour it — otherwise the
        # first game seen silently decides for the rest.
        if spec.get("fallback") and not target["spec"].get("fallback"):
            target["spec"]["fallback"] = spec["fallback"]
        for natdex, slug in species_for(game):
            target["species"][natdex] = slug

    grand_total = sum(len(t["species"]) for t in wanted.values())
    print(f"{len(wanted)} sprite set(s), {grand_total} files to ensure\n")

    all_failures = []
    for directory, target in sorted(wanted.items()):
        spec = target["spec"]
        out_dir = os.path.join(ASSET_DIR, directory)
        os.makedirs(out_dir, exist_ok=True)

        sizes, failures, written, fell_back, forms = set(), [], 0, [], []
        items = sorted(target["species"].items())
        for index, (natdex, slug) in enumerate(items, start=1):
            path = os.path.join(out_dir, f"{natdex}.png")
            if os.path.exists(path) and os.path.getsize(path) > 0:
                continue
            # Some sets do not cover every species a game's dex contains —
            # Legends Z-A borrows Scarlet/Violet's sprites but its dex reaches
            # further. A declared fallback fills those gaps rather than leaving
            # holes or silently swapping in a different art style.
            attempts = [spec]
            if spec.get("fallback"):
                attempts.append(spec["fallback"])

            data, used, last_error = None, None, None
            for attempt in attempts:
                candidates = [slug]
                if attempt["source"] == "pokemondb":
                    candidates += form_slugs(natdex)
                for candidate in candidates:
                    try:
                        data = http_cache.fetch(
                            source_url(attempt, natdex, candidate), binary=True)
                        used = attempt
                        if candidate != slug:
                            forms.append((natdex, candidate))
                        break
                    except Exception as exc:  # noqa: BLE001
                        last_error = str(exc)[:60]
                if data is not None:
                    break
            if data is None:
                failures.append((natdex, slug, last_error or "not found"))
                continue
            if used is not attempts[0]:
                fell_back.append(natdex)

            dimensions = png_size(data)
            if dimensions is None:
                failures.append((natdex, slug, "not a PNG"))
                continue
            sizes.add(dimensions)
            with open(path, "wb") as fh:
                fh.write(data)
            written += 1
            if index % 128 == 0:
                print(f"    {directory} {index}/{len(items)}")

        have = len([n for n in os.listdir(out_dir) if n.endswith(".png")])
        total_bytes = sum(os.path.getsize(os.path.join(out_dir, n))
                          for n in os.listdir(out_dir))
        print(f"  {directory:18s} {spec['source']:10s} {have:4d}/{len(items)} files"
              f"  {total_bytes / 1024:7.0f} KB  dims={sorted(sizes) or 'cached'}"
              f"  ({', '.join(target['games'][:3])}"
              f"{'...' if len(target['games']) > 3 else ''})")
        if forms:
            print(f"    {len(forms)} resolved via a regional/alternate form: "
                  + ", ".join(f"{n}->{c}" for n, c in forms[:6])
                  + (" ..." if len(forms) > 6 else ""))
        if fell_back:
            fb = spec["fallback"]
            print(f"    {len(fell_back)} filled from the declared fallback "
                  f"({fb['source']}/{fb['set']})")
        if failures:
            print(f"    {len(failures)} FAILED: "
                  + ", ".join(f"{n}/{s}" for n, s, _ in failures[:8])
                  + (" ..." if len(failures) > 8 else ""))
            all_failures.extend((directory, n, s, r) for n, s, r in failures)

    http_cache.save_manifest()
    total = sum(
        os.path.getsize(os.path.join(dp, f))
        for d in wanted
        for dp, _, fs in os.walk(os.path.join(ASSET_DIR, d))
        for f in fs
    )
    print(f"\ntotal vendored sprites: {total / 1024 / 1024:.1f} MB")
    if all_failures:
        print(f"{len(all_failures)} failure(s) — these species have no sprite in "
              f"their game's set and will fail the build:")
        for directory, natdex, slug, reason in all_failures[:40]:
            print(f"  {directory}/{natdex}.png ({slug}): {reason}")


if __name__ == "__main__":
    main()
