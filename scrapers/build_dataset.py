#!/usr/bin/env python3
"""Merge the scraped sources into one dataset per game.

The contract: nothing reaches ``site/data/`` that isn't traceable to a source,
and where sources disagree the disagreement is shipped rather than resolved by
picking a favourite.

Everything is driven by ``games.json``. A game may carry several regional
dexes — Kalos is split in three, Galar and Paldea each add DLC dexes — so each
dex gets its own box run and they are emitted as a list.

Exits non-zero if any validation gate fails.
"""

import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import config, http_cache, labels

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARSED_DIR = os.path.join(ROOT, "raw", "parsed")
SITE_DIR = os.path.join(ROOT, "site")
DATA_DIR = os.path.join(SITE_DIR, "data")
TEMPLATE_DIR = os.path.join(ROOT, "scrapers", "templates")

# PokemonDB uses these fixed phrases when a species has no wild encounter in a
# game. Seeing one while PokeAPI reports locations means the sources disagree.
# PokemonDB uses these phrases to assert a species has no wild encounter in a
# game. Seeing one while another source reports locations is a real conflict.
NO_WILD_TEXT = re.compile(r"^(Evolve |Breed |Trade/migrate|Not available)", re.I)

# This one asserts nothing — it means PokemonDB has not covered the game yet.
# It must never be treated as a contradiction of another source, and it is
# worth showing only when we have nothing better.
NO_DATA_TEXT = re.compile(r"^Location data not", re.I)

problems = []
notes = []


def load(name, required=True):
    path = os.path.join(PARSED_DIR, f"{name}.json")
    if not os.path.exists(path):
        if required:
            raise SystemExit(f"missing {path}\nRun scrapers/fetch_{name}.py first.")
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------
# Locations
# --------------------------------------------------------------------------

def build_locations(area_rows, location_names, version):
    """Collapse raw encounter rows into something readable.

    PokeAPI emits one row per condition combination, so a single patch of grass
    can produce a dozen near-identical rows. Rows sharing a method and condition
    set are summed — they are genuinely separate slots in the same table — and
    their level ranges merged.
    """
    out = []
    for area in area_rows:
        if area["area"] in labels.PSEUDO_AREAS:
            continue
        rows = area["versions"].get(version)
        if not rows:
            continue

        grouped = {}
        for row in rows:
            key = (row["method"], tuple(sorted(row["conditions"])))
            bucket = grouped.setdefault(
                key,
                {"minLevel": row["minLevel"], "maxLevel": row["maxLevel"], "chance": 0},
            )
            bucket["minLevel"] = min(bucket["minLevel"], row["minLevel"])
            bucket["maxLevel"] = max(bucket["maxLevel"], row["maxLevel"])
            bucket["chance"] += row["chance"]

        variants = [
            {
                "method": method,
                "methodLabel": labels.method_label(method),
                "minLevel": bucket["minLevel"],
                "maxLevel": bucket["maxLevel"],
                "chance": min(bucket["chance"], 100),
                "conditions": [
                    {"label": labels.condition_label(c),
                     "minor": c in labels.NOISY_CONDITIONS}
                    for c in conditions
                ],
            }
            for (method, conditions), bucket in grouped.items()
        ]
        variants.sort(key=lambda v: (labels.method_sort_key(v["method"]), -v["chance"]))

        meta = location_names.get(area["area"], {})
        out.append({
            "area": labels.location_name(meta) if meta else labels.humanise(area["area"]),
            "areaSlug": area["area"],
            "bestChance": max(v["chance"] for v in variants),
            "variants": variants,
        })

    out.sort(key=lambda a: (-a["bestChance"], a["area"]))
    return out


# --------------------------------------------------------------------------
# Notes for species with no wild encounters
# --------------------------------------------------------------------------

def build_notes(slug, species, evolutions_by_species, display_names,
                pokemondb_text, is_unobtainable):
    """How to obtain a species that isn't found in the wild."""
    out = []

    if is_unobtainable:
        out.append({
            "text": "Not obtainable in this game — event distribution only.",
            "kind": "unobtainable",
            "source": "serebii",
        })

    for row in evolutions_by_species.get(slug, []):
        parent = row.get("from")
        if not parent:
            continue
        out.append({
            "text": labels.evolution_note(
                row, display_names.get(parent, parent.capitalize())),
            "kind": "evolution",
            "source": "pokeapi",
        })

    if species.get("isBaby") and not out:
        groups = ", ".join(labels.humanise(g) for g in species.get("eggGroups", []))
        out.append({
            "text": f"Breed to obtain — egg group: {groups or 'unknown'}.",
            "kind": "breeding",
            "source": "pokeapi",
        })

    if pokemondb_text:
        out.append({"text": pokemondb_text, "kind": "pokemondb", "source": "pokemondb"})

    # PokeAPI ships duplicate evolution_details rows for some chains, so
    # collapse by rendered text.
    seen, deduped = set(), []
    for note in out:
        if note["text"] in seen:
            continue
        seen.add(note["text"])
        deduped.append(note)
    return deduped


def trade_evolution(slug, evolutions_by_species, display_names):
    """The trade-evolution record for a species, or None.

    Evolving only by trade is a real barrier to finishing a dex solo, so it
    earns a tag of its own rather than being buried in the notes.
    """
    for row in evolutions_by_species.get(slug, []):
        if row.get("trigger") != "trade":
            continue
        parent = row.get("from")
        return {
            "from": display_names.get(parent, (parent or "").capitalize()),
            "heldItem": labels.humanise(row["heldItem"]) if row.get("heldItem") else None,
        }
    return None


# --------------------------------------------------------------------------
# Version exclusivity, computed from up to three sources
# --------------------------------------------------------------------------

ABSTAIN = "abstain"


def derive_exclusives(encounters, slugs, versions):
    """Verdict from PokeAPI's own encounter tables, per paired-version group.

    Returns a version name, ``None`` for "appears in both", or ABSTAIN when the
    species has no encounter data at all in either version. The distinction
    matters: an evolution-only species is absent from every encounter table,
    which is silence, not evidence.
    """
    result = {}
    for slug in slugs:
        seen = set()
        for area in encounters.get(slug, []):
            if area["area"] in labels.PSEUDO_AREAS:
                continue
            seen.update(v for v in area["versions"] if v in versions)
        if not seen:
            result[slug] = ABSTAIN
        elif len(seen) == 1:
            result[slug] = next(iter(seen))
        else:
            result[slug] = None
    return result


def reconcile_exclusives(entries, derived, serebii_by_slug, pokemondb_by_slug):
    """Combine the verdicts, recording genuine disagreements.

    Serebii and PokemonDB both publish complete exclusive lists, so their
    silence is a real "not exclusive" claim. PokeAPI only votes where it has
    encounter data. Conflicts take the majority and stay flagged; ties fall to
    "not exclusive", because wrongly telling someone to trade for something
    they could have caught is the worse error.
    """
    verdicts = {}
    for entry in entries:
        slug = entry["slug"]
        claims = {
            "Serebii": serebii_by_slug.get(slug),
            "PokémonDB": pokemondb_by_slug.get(slug),
            "PokéAPI encounter data": derived.get(slug, ABSTAIN),
        }
        votes = [v for v in claims.values() if v != ABSTAIN]
        if not any(votes):
            continue

        agreed = len(set(votes)) == 1
        tally = {}
        for vote in votes:
            tally[vote] = tally.get(vote, 0) + 1
        best = max(tally.values())
        winners = [v for v, c in tally.items() if c == best]

        verdicts[slug] = {
            "version": winners[0] if len(winners) == 1 else None,
            "agreed": agreed,
            "claims": {
                source: ("no encounter data — cannot say" if value == ABSTAIN
                         else value or "not listed as exclusive")
                for source, value in claims.items()
            },
        }
    return verdicts


# --------------------------------------------------------------------------
# Boxes
# --------------------------------------------------------------------------

def build_boxes(entries, box_config):
    """Split a dex into boxes, labelled the way the game labels them."""
    per_box = box_config["perBox"]
    boxes = []
    for start in range(0, len(entries), per_box):
        chunk = entries[start:start + per_box]
        boxes.append({
            "index": len(boxes) + 1,
            "label": f"{chunk[0]['dex']}-{chunk[-1]['dex']}",
            "from": chunk[0]["dex"],
            "to": chunk[-1]["dex"],
            "count": len(chunk),
        })
    return boxes


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------

def render_pages():
    """Emit one landing page and one box page per live game."""
    with open(os.path.join(TEMPLATE_DIR, "game.html"), encoding="utf-8") as fh:
        game_tmpl = fh.read()
    with open(os.path.join(TEMPLATE_DIR, "boxes.html"), encoding="utf-8") as fh:
        boxes_tmpl = fh.read()

    written = 0
    for entry in config.games(status="live"):
        name = entry["name"].replace("é", "&eacute;")
        for tmpl, folder in ((game_tmpl, "game"), (boxes_tmpl, "boxes")):
            target = os.path.join(SITE_DIR, folder, f"{entry['id']}.html")
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as fh:
                fh.write(tmpl.replace("{{GAME_ID}}", entry["id"])
                             .replace("{{GAME_NAME}}", name))
            written += 1
    print(f"pages: generated {written} shells for "
          f"{len(config.games(status='live'))} live game(s)")


REGION_ORDER = ["Kanto", "Johto", "Hoenn", "Sinnoh", "Unova", "Kalos",
                "Alola", "Galar", "Hisui", "Paldea"]


def write_home(built):
    """The Pokémon HOME aggregate view.

    HOME is stored by region and then by that region's dex number, so this
    groups the built games by region and offers each region's dex variants as
    alternatives — Kanto alone has three, and they disagree on both size and
    ordering, so which one is "the" Kanto dex is a choice, not a fact.

    Only the display data is emitted. Caught state is never duplicated here;
    the page reads it from the same collection the per-game pages write.
    """
    regions = {}
    for game in config.games(status="live"):
        payload = built.get(game["id"])
        if not payload:
            continue
        region = regions.setdefault(
            game["region"], {"key": game["region"].lower(),
                             "name": game["region"], "variants": {}})
        variant = region["variants"].setdefault(
            game["versionGroup"],
            {"key": game["versionGroup"], "games": [], "dexes": []})
        variant["games"].append({"id": game["id"], "name": game["shortName"]})
        if variant["dexes"]:
            continue  # paired versions share a dex; take the first
        for dex in payload["dexes"]:
            variant["dexes"].append({
                "key": dex["key"],
                "name": dex["name"],
                "size": dex["size"],
                "entries": [
                    {"dex": e["dex"], "slug": e["slug"], "name": e["name"],
                     "sprite": e["sprite"], "types": e["types"]}
                    for e in dex["entries"]
                ],
            })

    out = []
    for name in REGION_ORDER:
        region = regions.pop(name, None)
        if not region:
            continue
        variants = []
        for variant in region["variants"].values():
            total = sum(d["size"] for d in variant["dexes"])
            variants.append({
                **variant,
                "size": total,
                "label": " / ".join(g["name"] for g in variant["games"]),
            })
        variants.sort(key=lambda v: -v["size"])
        out.append({"key": region["key"], "name": region["name"],
                    "variants": variants})
    for leftover in regions.values():           # any region not in the order
        out.append({"key": leftover["key"], "name": leftover["name"],
                    "variants": list(leftover["variants"].values())})

    with open(os.path.join(DATA_DIR, "home.json"), "w", encoding="utf-8") as fh:
        json.dump({"regions": out, "perBox": 30}, fh, ensure_ascii=False,
                  separators=(",", ":"))
    total = sum(v["size"] for r in out for v in r["variants"])
    print(f"home: {len(out)} regions, "
          f"{sum(len(r['variants']) for r in out)} dex variants, "
          f"{total} entries")


def write_site_config():
    site_config = config.site_asset_config()
    site_config["spriteSets"] = {
        entry["sprites"]["dir"]: entry["sprites"]["set"]
        for entry in config.games() if entry.get("sprites")
    }
    site_config["games"] = [
        {
            "id": e["id"], "name": e["name"], "shortName": e["shortName"],
            "generation": e["generation"], "region": e["region"],
            "status": e["status"], "accent": e.get("accent"),
            "boxart": e.get("boxart"),
            "dexName": e["dexes"][0]["name"] if e.get("dexes") else None,
            "dexSize": sum(d["size"] for d in e.get("dexes", [])),
            "boxes": {k: v for k, v in e["boxes"].items() if k != "source"},
        }
        for e in config.games()
    ]
    with open(os.path.join(SITE_DIR, "config.json"), "w", encoding="utf-8") as fh:
        json.dump(site_config, fh, indent=1, ensure_ascii=False)
    print(f"site config: profile '{site_config['profile']}', "
          f"tiers {' -> '.join(site_config['tiers'])}, "
          f"{len(site_config['games'])} game(s) registered")


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------

ZA_METHOD = {"lumiose": "Wild Zone", "hyperspace": "Mega Dimension"}


def build_za_locations(text, dex_key):
    """Turn Serebii's Z-A location text into location rows.

    Serebii gives places, not encounter tables — "Wild Zone 3, Wild Zone 6,
    Vert District" — so these rows carry a place and a method and deliberately
    no level range, rarity or time of day, because none is published.
    """
    if not text:
        return []
    head, _, tail = text.partition(" - ")
    places = [p.strip() for p in (tail or head).split(",") if p.strip()]
    prefix = head.strip() if tail else None
    out = []
    for place in places:
        out.append({
            "area": f"{prefix} — {place}" if prefix else place,
            "areaSlug": place.lower().replace(" ", "-"),
            "bestChance": 0,
            "variants": [{
                "method": "wild-zone",
                "methodLabel": ZA_METHOD.get(dex_key, "Wild Zone"),
                "minLevel": None, "maxLevel": None, "chance": 0,
                "conditions": [],
            }],
        })
    return out


def build_game(game, pokeapi, pokemondb, serebii, serebii_za=None):
    game_id = game["id"]
    version = game.get("pokeapiVersion")
    pdb_version = game.get("pokemondbVersion") or version
    paired = game.get("pairedWith")
    paired_game = None
    if paired:
        try:
            paired_game = config.game(paired)
        except KeyError:
            problems.append(f"{game_id}: pairedWith '{paired}' is not in games.json")

    species = pokeapi["species"]
    display_names = {s: (species[s]["name"] or s.capitalize()) for s in species}
    types_by_slug = {s: pokeapi["pokemon"][s]["types"] for s in pokeapi["pokemon"]}

    evolutions_by_species = defaultdict(list)
    for row in pokeapi["evolutions"]:
        evolutions_by_species[row["species"]].append(row)

    # Serebii's unobtainable list is per version group where we have one.
    sere = (serebii or {}).get(game["versionGroup"], {})
    unobtainable = set()          # national dex ids
    unobtainable_slugs = set()    # species slugs, for newer Serebii pages
    for row in sere.get("unobtainable", []):
        if row.get("natdex") is not None:
            unobtainable.add(row["natdex"])
        if row.get("slug"):
            unobtainable_slugs.add(row["slug"])

    # Exclusivity only means something for a paired release.
    pair_versions = set()
    if paired_game:
        pair_versions = {version, paired_game.get("pokeapiVersion")}

    serebii_by_slug, pokemondb_by_slug = {}, {}
    natdex_to_slug = {}
    for dex in game.get("dexes", []):
        for entry in pokeapi["pokedexes"][dex["pokeapiPokedex"]]["entries"]:
            natdex_to_slug[entry["natdex"]] = entry["slug"]
    # Serebii identifies species by national dex number on older pages and by
    # species slug on newer ones, so accept either.
    for ver, rows in (sere.get("exclusives") or {}).items():
        for row in rows:
            slug = row.get("slug") or natdex_to_slug.get(row.get("natdex"))
            if slug:
                serebii_by_slug[slug] = ver
    pdb = (pokemondb or {}).get("exclusives", {}).get(game["versionGroup"], {})
    for ver, slugs in pdb.items():
        for slug in slugs:
            pokemondb_by_slug[slug] = ver

    pdb_locations = (pokemondb or {}).get("locations", {})
    pdb_dexes = (pokemondb or {}).get("dexes", {})

    out_dexes = []
    all_entries = []

    for dex in game.get("dexes", []):
        source = pokeapi["pokedexes"].get(dex["pokeapiPokedex"])
        if source is None:
            problems.append(f"{game_id}: pokedex '{dex['pokeapiPokedex']}' not scraped")
            continue
        raw = source["entries"]

        # A size difference between the registry (Bulbapedia) and PokeAPI is
        # usually a real editorial difference rather than an error — Central
        # Kalos is 153 on Bulbapedia and 150 on PokeAPI, which omits the three
        # mythicals. Record it and show it; don't silently pick a winner and
        # don't fail the build over a documented disagreement.
        size_note = None
        order_disputed = None
        if dex.get("size") and len(raw) != dex["size"]:
            size_note = {
                "Bulbapedia (registry)": dex["size"],
                "PokéAPI": len(raw),
            }
            notes.append(
                f"{game_id}/{dex['key']}: dex size differs — Bulbapedia "
                f"{dex['size']}, PokéAPI {len(raw)} (shipping PokéAPI's order, "
                f"difference surfaced in the UI)"
            )

        # Cross-check order against PokemonDB where we scraped that game's dex.
        their = pdb_dexes.get(dex.get("pokemondbDex") or "")
        if their:
            ours = {e["dex"]: e["slug"] for e in raw}
            theirs = {e["dex"]: e["slug"] for e in their}
            mismatch = [f"#{n}: {ours[n]} vs {theirs.get(n)}"
                        for n in sorted(ours) if theirs.get(n) != ours[n]]
            if mismatch and len(mismatch) > max(6, len(ours) // 10):
                problems.append(
                    f"{game_id}/{dex['key']}: dex order mismatch vs PokémonDB on "
                    f"{len(mismatch)}/{len(ours)} entries — wrong page? "
                    + "; ".join(mismatch[:4])
                )
            elif mismatch:
                order_disputed = mismatch
                notes.append(
                    f"{game_id}/{dex['key']}: sources disagree on the order of "
                    f"{len(mismatch)} entr{'y' if len(mismatch)==1 else 'ies'} "
                    f"({'; '.join(mismatch[:3])}) — shipping PokéAPI's"
                )
            else:
                notes.append(
                    f"{game_id}/{dex['key']}: order confirmed by two sources "
                    f"({len(ours)} entries)"
                )

        derived = derive_exclusives(
            pokeapi["encounters"], [e["slug"] for e in raw], pair_versions)
        verdicts = (reconcile_exclusives(raw, derived, serebii_by_slug,
                                         pokemondb_by_slug)
                    if pair_versions else {})

        entries = []
        for entry in raw:
            slug = entry["slug"]
            index = entry["dex"] - 1
            box_cfg = game["boxes"]
            per_box = box_cfg["perBox"]
            cols = box_cfg.get("cols") or per_box

            locations = build_locations(
                pokeapi["encounters"].get(slug, []), pokeapi["locations"], version
            ) if version else []

            # Legends Z-A has no encounter tables anywhere; Serebii publishes
            # the places on its species pages, so those become the locations.
            if not locations and serebii_za:
                locations = build_za_locations(
                    (serebii_za["locations"].get(slug) or {}).get(dex["key"]),
                    dex["key"])

            pdb_text = (pdb_locations.get(slug, {}) or {}).get(pdb_version)
            is_unobtainable = (entry["natdex"] in unobtainable
                               or slug in unobtainable_slugs)
            # PokemonDB's "not yet available" adds nothing once we have real
            # locations from elsewhere.
            note_text = pdb_text
            if locations and pdb_text and NO_DATA_TEXT.match(pdb_text.strip()):
                note_text = None
            note_rows = build_notes(
                slug, species.get(slug, {}), evolutions_by_species, display_names,
                note_text, is_unobtainable)

            verdict = verdicts.get(slug)
            exclusive_to = verdict["version"] if verdict else None
            obtainable = not is_unobtainable and exclusive_to in (None, version)

            locations_disputed = bool(
                locations and pdb_text and NO_WILD_TEXT.match(pdb_text.strip()))
            dispute_reason = None
            if locations_disputed:
                slugs = [loc["areaSlug"] for loc in locations]
                methods = {v["method"] for loc in locations
                           for v in loc["variants"]}
                if all("johto-safari" in a for a in slugs):
                    dispute_reason = ("PokémonDB has no page for the Johto Safari "
                                      "Zone interior, so its summary is probably "
                                      "just incomplete.")
                elif all("friend-safari" in a for a in slugs):
                    dispute_reason = ("The Friend Safari is the difference — "
                                      "PokémonDB's summary doesn't count it, but "
                                      "it is a real way to catch this.")
                elif methods <= {"max-raid", "dynamax-adventure"}:
                    dispute_reason = ("Raid dens are the difference — PokémonDB's "
                                      "summary covers overworld encounters, not "
                                      "raids.")
                elif methods <= {"gift", "gift-egg"}:
                    dispute_reason = ("PokéAPI records this as a gift; PokémonDB's "
                                      "summary doesn't count gifts as a location.")
                else:
                    dispute_reason = ("PokémonDB's one-line summary doesn't cover "
                                      "every encounter type, so it may simply be "
                                      "incomplete.")

            trade_evo = trade_evolution(slug, evolutions_by_species, display_names)
            needs_partner = bool(trade_evo and (not locations or locations_disputed))

            sprite = f"{game['sprites']['dir']}/{entry['natdex']}.png"
            if not os.path.exists(os.path.join(SITE_DIR, "assets", sprite)):
                problems.append(f"{game_id}: missing sprite {sprite} "
                                f"(#{entry['dex']} {slug})")
            if not locations and not note_rows:
                problems.append(f"{game_id}: #{entry['dex']} {slug} has "
                                f"neither locations nor notes")

            entries.append({
                "dex": entry["dex"], "natdex": entry["natdex"], "slug": slug,
                "name": display_names.get(slug, slug.capitalize()),
                "types": types_by_slug.get(slug, []),
                "sprite": sprite,
                "box": index // per_box + 1,
                "slot": index % per_box + 1,
                "row": (index % per_box) // cols + 1,
                "col": index % cols + 1,
                "obtainable": obtainable,
                "unobtainable": is_unobtainable,
                "exclusiveTo": exclusive_to,
                "tradeEvolution": trade_evo,
                "needsTradePartner": needs_partner,
                "disputed": bool(verdict and not verdict["agreed"]),
                "claims": verdict["claims"] if verdict and not verdict["agreed"] else None,
                "locationsDisputed": locations_disputed,
                "locationClaims": ({
                    "PokéAPI encounter data":
                        f"{len(locations)} location"
                        f"{'s' if len(locations) != 1 else ''} in {game['shortName']}",
                    "PokémonDB": pdb_text,
                } if locations_disputed else None),
                "locationDisputeReason": dispute_reason,
                "locations": locations,
                "notes": note_rows,
                "externalUrl": f"https://pokemondb.net/pokedex/{slug}#dex-locations",
            })

        out_dexes.append({
            "key": dex["key"],
            "name": dex["name"],
            "size": len(entries),
            "sizeDisputed": size_note,
            "orderDisputed": order_disputed,
            "boxes": build_boxes(entries, game["boxes"]),
            "entries": entries,
        })
        all_entries.extend(entries)

    # A game where neither source has any location data at all is worth saying
    # out loud once, rather than repeating "unknown" in 364 popups.
    with_locations = sum(1 for e in all_entries if e["locations"])
    with_real_text = sum(
        1 for e in all_entries
        if any(n["kind"] == "pokemondb" and not NO_WILD_TEXT.match(n["text"].strip())
               for n in e["notes"])
    )
    coverage = None
    if not with_locations and not with_real_text:
        coverage = {
            "level": "none",
            "message": (
                f"No location data exists for {game['name']} yet — PokéAPI has no "
                f"encounter tables for it and PokémonDB reports "
                f"\u201cLocation data not yet available\u201d for every species. "
                f"The dex order and box layout below are correct; where to catch "
                f"each Pokémon is simply not published anywhere we can cite."
            ),
        }
    elif not with_locations:
        coverage = {
            "level": "text-only",
            "message": (
                f"PokéAPI has no encounter tables for {game['name']}, so locations "
                f"come from PokémonDB's summary text rather than full tables — "
                f"no level ranges, rarities or time-of-day."
            ),
        }

    attainable = [e["dex"] for e in all_entries if e["exclusiveTo"] == version]
    trade_only = [e["dex"] for e in all_entries
                  if e["exclusiveTo"] and e["exclusiveTo"] != version]
    trade_evos = [e["dex"] for e in all_entries if e["tradeEvolution"]]

    payload = {
        "game": {
            "id": game_id,
            "name": game["name"],
            "shortName": game["shortName"],
            "generation": game["generation"],
            "region": game["region"],
            "dexName": game["dexes"][0]["name"] if game.get("dexes") else "",
            "pairedVersion": paired,
            "pairedName": paired_game["shortName"] if paired_game else None,
            "accent": game.get("accent"),
            "walkthroughUrl": game.get("links", {}).get("walkthrough"),
            "nationalExclusivesUrl": game.get("links", {}).get("nationalExclusives"),
            "boxart": game.get("boxart"),
            "boxStyle": game["boxes"]["style"],
            "spriteNote": (game.get("sprites") or {}).get("note"),
            "coverage": coverage,
        },
        "boxLayout": {k: v for k, v in game["boxes"].items() if k != "source"},
        "dexes": out_dexes,
        "exclusives": {
            "attainable": attainable,
            "tradeOnly": trade_only,
            "tradeEvolutions": trade_evos,
        },
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, f"{game_id}.json"), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))

    total = len(all_entries)
    flag = ""
    if coverage:
        flag = "  <-- " + coverage["level"].upper()
    print(f"  {game['name']:34s} {total:4d} entries  "
          f"{with_locations:4d} with locations  "
          f"{len(attainable):2d}/{len(trade_only):2d} exclusives  "
          f"{len(trade_evos):2d} trade evos  "
          f"{sum(1 for e in all_entries if e['unobtainable']):2d} unobtainable{flag}")
    return payload


def main():
    # site/config.json and the page shells derive from config.json + games.json
    # alone. Regenerating them must not require the scrape cache, so a fresh
    # checkout can re-point the asset profile without re-scraping anything.
    if "--config-only" in sys.argv:
        render_pages()
        write_site_config()
        return

    pokeapi = load("pokeapi")
    pokemondb = load("pokemondb", required=False)
    serebii = load("serebii", required=False)
    serebii_za = load("serebii_za", required=False)

    live = config.games(status="live")
    print(f"building {len(live)} game(s)\n")
    built = {}
    for game in live:
        za = serebii_za if game.get("pokeapiVersion") == "legends-za" else None
        built[game["id"]] = build_game(game, pokeapi, pokemondb, serebii, za)

    print()
    write_home(built)
    render_pages()
    write_site_config()

    manifest = http_cache.manifest_entries()
    with open(os.path.join(DATA_DIR, "sources.json"), "w", encoding="utf-8") as fh:
        json.dump({
            "note": "Every HTTP response behind site/data/, by URL. "
                    "Raw bodies live in raw/ (gitignored) and are re-fetchable.",
            "responses": sorted(manifest.values(), key=lambda r: r["url"]),
        }, fh, indent=1)
    print(f"provenance: {len(manifest)} responses recorded")

    for note in notes:
        print(f"  ok   {note}")
    if problems:
        print(f"\n{len(problems)} PROBLEM(S):")
        for problem in problems[:40]:
            print(f"  FAIL {problem}")
        raise SystemExit(1)
    print("  ok   all validation gates passed")


if __name__ == "__main__":
    main()
