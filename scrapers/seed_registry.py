#!/usr/bin/env python3
"""One-time seed for games.json.

games.json is the maintained artefact; this script exists so the initial
registry could be written from a single citation-carrying table rather than by
hand, which is where transcription errors come from. Re-running it overwrites
games.json, so edit the JSON directly after seeding.

Provenance for every value:
  dex sizes    Bulbapedia "List of Pokemon by <X> Pokedex number"
  box geometry pret disassemblies where one exists, else Bulbapedia's storage
               table with the arrangement explicitly marked as inferred
  sprites      PokeAPI/sprites where a per-game set exists, else PokemonDB
  box art      img.pokemondb.net/boxes/<slug>.jpg, all verified 200
"""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BULBA = "https://bulbapedia.bulbagarden.net/wiki/"
STORAGE = BULBA + "Pok%C3%A9mon_Storage_System"

INFERRED_GRID = (
    "Capacity 30/box from Bulbapedia's storage table (" + STORAGE + "). "
    "The 6x5 arrangement is consistent with every game from Gen 3 onward but is "
    "NOT confirmed by a primary source for this generation — treat as inferred."
)


def dex(key, name, slug, size, page):
    return {"key": key, "name": name, "pokeapiPokedex": slug, "size": size,
            "sizeSource": BULBA + page}


def grid(count, source):
    return {"style": "grid", "cols": 6, "rows": 5, "perBox": 30,
            "count": count, "source": source}


def namelist(count, source):
    return {"style": "list", "cols": 1, "rows": 20, "perBox": 20,
            "count": count, "source": source}


def sprites(source, sprite_set, directory, note=None):
    out = {"source": source, "set": sprite_set, "dir": directory}
    if note:
        out["note"] = note
    return out


PRET = "pret disassembly: "
KANTO = "List_of_Pok%C3%A9mon_by_Kanto_Pok%C3%A9dex_number"
JOHTO_OLD = "List_of_Pok%C3%A9mon_by_New_Pok%C3%A9dex_number"
JOHTO_HG = "List_of_Pok%C3%A9mon_by_Johto_Pok%C3%A9dex_number"
HOENN3 = "List_of_Pok%C3%A9mon_by_Hoenn_Pok%C3%A9dex_number_in_Generation_III"
HOENN6 = "List_of_Pok%C3%A9mon_by_Hoenn_Pok%C3%A9dex_number_in_Generation_VI"
SINNOH = "List_of_Pok%C3%A9mon_by_Sinnoh_Pok%C3%A9dex_number"
UNOVA_BW = "List_of_Pok%C3%A9mon_by_Unova_Pok%C3%A9dex_number_in_Pok%C3%A9mon_Black_and_White"
UNOVA_B2 = "List_of_Pok%C3%A9mon_by_Unova_Pok%C3%A9dex_number_in_Pok%C3%A9mon_Black_2_and_White_2"
KC = "List_of_Pok%C3%A9mon_by_Central_Kalos_Pok%C3%A9dex_number"
KO = "List_of_Pok%C3%A9mon_by_Coastal_Kalos_Pok%C3%A9dex_number"
KM = "List_of_Pok%C3%A9mon_by_Mountain_Kalos_Pok%C3%A9dex_number"
ALOLA_SM = "List_of_Pok%C3%A9mon_by_Alola_Pok%C3%A9dex_number_in_Pok%C3%A9mon_Sun_and_Moon"
ALOLA_US = "List_of_Pok%C3%A9mon_by_Alola_Pok%C3%A9dex_number_in_Pok%C3%A9mon_Ultra_Sun_and_Ultra_Moon"
GALAR = "List_of_Pok%C3%A9mon_by_Galar_Pok%C3%A9dex_number"
IOA = "List_of_Pok%C3%A9mon_by_Isle_of_Armor_Pok%C3%A9dex_number"
CT = "List_of_Pok%C3%A9mon_by_Crown_Tundra_Pok%C3%A9dex_number"
HISUI = "List_of_Pok%C3%A9mon_by_Hisui_Pok%C3%A9dex_number"
PALDEA = "List_of_Pok%C3%A9mon_by_Paldea_Pok%C3%A9dex_number"
KITA = "List_of_Pok%C3%A9mon_by_Kitakami_Pok%C3%A9dex_number"
BLUE = "List_of_Pok%C3%A9mon_by_Blueberry_Pok%C3%A9dex_number"
LUMIOSE = "List_of_Pok%C3%A9mon_by_Lumiose_Pok%C3%A9dex_number"
HYPER = "List_of_Pok%C3%A9mon_by_Hyperspace_Pok%C3%A9dex_number"

# id, name, short, gen, region, versionGroup, apiVersion, paired, accent,
# boxart slug, sprites, boxes, dexes
TABLE = [
    ("red", "Pokémon Red", "Red", 1, "Kanto", "red-blue", "red", "blue", "hg", "red",
     sprites("pokeapi", "generation-i/red-blue", "sprites/rb"),
     namelist(12, PRET + "pret/pokered constants/pokemon_data_constants.asm — "
              "MONS_PER_BOX 20, NUM_BOXES 12. UI is a scrolling name list, not a "
              "grid (" + STORAGE + ")."),
     [dex("kanto", "Kanto Pokédex", "kanto", 151, KANTO)]),
    ("blue", "Pokémon Blue", "Blue", 1, "Kanto", "red-blue", "blue", "red", "ss", "blue",
     sprites("pokeapi", "generation-i/red-blue", "sprites/rb"),
     namelist(12, PRET + "pret/pokered — MONS_PER_BOX 20, NUM_BOXES 12."),
     [dex("kanto", "Kanto Pokédex", "kanto", 151, KANTO)]),
    ("yellow", "Pokémon Yellow", "Yellow", 1, "Kanto", "yellow", "yellow", None, "hg", "yellow",
     sprites("pokeapi", "generation-i/yellow", "sprites/yellow"),
     namelist(12, PRET + "pret/pokeyellow — MONS_PER_BOX 20, NUM_BOXES 12."),
     [dex("kanto", "Kanto Pokédex", "kanto", 151, KANTO)]),

    ("gold", "Pokémon Gold", "Gold", 2, "Johto", "gold-silver", "gold", "silver", "hg", "gold",
     sprites("pokeapi", "generation-ii/gold", "sprites/gold"),
     namelist(14, PRET + "pret/pokegold — MONS_PER_BOX 20, NUM_BOXES 14 "
              "(Japanese releases use 30/box across 9 boxes)."),
     [dex("johto", "New Pokédex", "original-johto", 251, JOHTO_OLD)]),
    ("silver", "Pokémon Silver", "Silver", 2, "Johto", "gold-silver", "silver", "gold", "ss", "silver",
     sprites("pokeapi", "generation-ii/silver", "sprites/silver"),
     namelist(14, PRET + "pret/pokegold — MONS_PER_BOX 20, NUM_BOXES 14."),
     [dex("johto", "New Pokédex", "original-johto", 251, JOHTO_OLD)]),
    ("crystal", "Pokémon Crystal", "Crystal", 2, "Johto", "crystal", "crystal", None, "hg", "crystal",
     sprites("pokeapi", "generation-ii/crystal", "sprites/crystal"),
     namelist(14, PRET + "pret/pokecrystal — MONS_PER_BOX 20, NUM_BOXES 14."),
     [dex("johto", "New Pokédex", "original-johto", 251, JOHTO_OLD)]),

    ("ruby", "Pokémon Ruby", "Ruby", 3, "Hoenn", "ruby-sapphire", "ruby", "sapphire", "hg", "ruby",
     sprites("pokeapi", "generation-iii/ruby-sapphire", "sprites/rs"),
     grid(14, PRET + "pret/pokeemerald include/pokemon_storage_system.h — "
          "IN_BOX_ROWS 5, IN_BOX_COLUMNS 6, TOTAL_BOXES_COUNT 14."),
     [dex("hoenn", "Hoenn Pokédex", "hoenn", 202, HOENN3)]),
    ("sapphire", "Pokémon Sapphire", "Sapphire", 3, "Hoenn", "ruby-sapphire", "sapphire", "ruby", "ss", "sapphire",
     sprites("pokeapi", "generation-iii/ruby-sapphire", "sprites/rs"),
     grid(14, PRET + "pret/pokeemerald — IN_BOX_ROWS 5, IN_BOX_COLUMNS 6."),
     [dex("hoenn", "Hoenn Pokédex", "hoenn", 202, HOENN3)]),
    ("emerald", "Pokémon Emerald", "Emerald", 3, "Hoenn", "emerald", "emerald", None, "hg", "emerald",
     sprites("pokeapi", "generation-iii/emerald", "sprites/emerald"),
     grid(14, PRET + "pret/pokeemerald — IN_BOX_ROWS 5, IN_BOX_COLUMNS 6, "
          "TOTAL_BOXES_COUNT 14."),
     [dex("hoenn", "Hoenn Pokédex", "hoenn", 202, HOENN3)]),
    ("firered", "Pokémon FireRed", "FireRed", 3, "Kanto", "firered-leafgreen", "firered", "leafgreen", "hg", "firered",
     sprites("pokeapi", "generation-iii/firered-leafgreen", "sprites/frlg"),
     grid(14, PRET + "pret/pokefirered include/pokemon_storage_system.h — "
          "IN_BOX_ROWS 5, IN_BOX_COLUMNS 6."),
     [dex("kanto", "Kanto Pokédex", "kanto", 151, KANTO)]),
    ("leafgreen", "Pokémon LeafGreen", "LeafGreen", 3, "Kanto", "firered-leafgreen", "leafgreen", "firered", "ss", "leafgreen",
     sprites("pokeapi", "generation-iii/firered-leafgreen", "sprites/frlg"),
     grid(14, PRET + "pret/pokefirered — IN_BOX_ROWS 5, IN_BOX_COLUMNS 6."),
     [dex("kanto", "Kanto Pokédex", "kanto", 151, KANTO)]),

    ("diamond", "Pokémon Diamond", "Diamond", 4, "Sinnoh", "diamond-pearl", "diamond", "pearl", "hg", "diamond",
     sprites("pokeapi", "generation-iv/diamond-pearl", "sprites/dp"),
     grid(18, PRET + "pret/pokediamond include/pokemon_storage_system.h — "
          "NUM_BOXES 18, MONS_PER_BOX 30; grid from pret/pokeplatinum "
          "include/pc_boxes.h — MAX_PC_ROWS 5, MAX_PC_COLS 6."),
     [dex("sinnoh", "Sinnoh Pokédex", "original-sinnoh", 151, SINNOH)]),
    ("pearl", "Pokémon Pearl", "Pearl", 4, "Sinnoh", "diamond-pearl", "pearl", "diamond", "ss", "pearl",
     sprites("pokeapi", "generation-iv/diamond-pearl", "sprites/dp"),
     grid(18, PRET + "pret/pokediamond — NUM_BOXES 18, MONS_PER_BOX 30."),
     [dex("sinnoh", "Sinnoh Pokédex", "original-sinnoh", 151, SINNOH)]),
    ("platinum", "Pokémon Platinum", "Platinum", 4, "Sinnoh", "platinum", "platinum", None, "hg", "platinum",
     sprites("pokeapi", "generation-iv/platinum", "sprites/platinum"),
     grid(18, PRET + "pret/pokeplatinum include/pc_boxes.h — MAX_PC_BOXES 18, "
          "MAX_PC_ROWS 5, MAX_PC_COLS 6."),
     [dex("sinnoh", "Sinnoh Pokédex", "extended-sinnoh", 210, SINNOH)]),
    ("heartgold", "Pokémon HeartGold", "HeartGold", 4, "Johto", "heartgold-soulsilver", "heartgold", "soulsilver", "hg", "heartgold",
     sprites("pokeapi", "generation-iv/heartgold-soulsilver", "sprites/hgss"),
     grid(18, PRET + "pret/pokeheartgold include/constants/pokemon.h — NUM_BOXES 18, "
          "MONS_PER_BOX 30; grid from pret/pokeplatinum include/pc_boxes.h."),
     [dex("johto", "Johto Pokédex", "updated-johto", 256, JOHTO_HG)]),
    ("soulsilver", "Pokémon SoulSilver", "SoulSilver", 4, "Johto", "heartgold-soulsilver", "soulsilver", "heartgold", "ss", "soulsilver",
     sprites("pokeapi", "generation-iv/heartgold-soulsilver", "sprites/hgss"),
     grid(18, PRET + "pret/pokeheartgold — NUM_BOXES 18, MONS_PER_BOX 30."),
     [dex("johto", "Johto Pokédex", "updated-johto", 256, JOHTO_HG)]),

    ("black", "Pokémon Black", "Black", 5, "Unova", "black-white", "black", "white", "hg", "black",
     sprites("pokeapi", "generation-v/black-white", "sprites/bw"),
     grid(24, INFERRED_GRID + " Box count 8/16/24, unlocked progressively."),
     [dex("unova", "Unova Pokédex", "original-unova", 156, UNOVA_BW)]),
    ("white", "Pokémon White", "White", 5, "Unova", "black-white", "white", "black", "ss", "white",
     sprites("pokeapi", "generation-v/black-white", "sprites/bw"),
     grid(24, INFERRED_GRID + " Box count 8/16/24."),
     [dex("unova", "Unova Pokédex", "original-unova", 156, UNOVA_BW)]),
    ("black-2", "Pokémon Black 2", "Black 2", 5, "Unova", "black-2-white-2", "black-2", "white-2", "hg", "black-2",
     sprites("pokeapi", "generation-v/black-white", "sprites/bw",
             "Black 2/White 2 reuse the Black/White sprite set; PokeAPI has no "
             "separate black-2-white-2 folder."),
     grid(24, INFERRED_GRID + " Box count 8/16/24."),
     [dex("unova", "Unova Pokédex", "updated-unova", 301, UNOVA_B2)]),
    ("white-2", "Pokémon White 2", "White 2", 5, "Unova", "black-2-white-2", "white-2", "black-2", "ss", "white-2",
     sprites("pokeapi", "generation-v/black-white", "sprites/bw",
             "Black 2/White 2 reuse the Black/White sprite set."),
     grid(24, INFERRED_GRID + " Box count 8/16/24."),
     [dex("unova", "Unova Pokédex", "updated-unova", 301, UNOVA_B2)]),

    ("x", "Pokémon X", "X", 6, "Kalos", "x-y", "x", "y", "hg", "x",
     sprites("pokeapi", "generation-vi/x-y", "sprites/xy"),
     grid(31, INFERRED_GRID + " Box count 7/15/23/30/31; the 31st unlocks after "
          "catching Xerneas or Yveltal."),
     [dex("central", "Central Kalos Pokédex", "kalos-central", 153, KC),
      dex("coastal", "Coastal Kalos Pokédex", "kalos-coastal", 153, KO),
      dex("mountain", "Mountain Kalos Pokédex", "kalos-mountain", 151, KM)]),
    ("y", "Pokémon Y", "Y", 6, "Kalos", "x-y", "y", "x", "ss", "y",
     sprites("pokeapi", "generation-vi/x-y", "sprites/xy"),
     grid(31, INFERRED_GRID + " Box count 7/15/23/30/31."),
     [dex("central", "Central Kalos Pokédex", "kalos-central", 153, KC),
      dex("coastal", "Coastal Kalos Pokédex", "kalos-coastal", 153, KO),
      dex("mountain", "Mountain Kalos Pokédex", "kalos-mountain", 151, KM)]),
    ("omega-ruby", "Pokémon Omega Ruby", "Omega Ruby", 6, "Hoenn", "omega-ruby-alpha-sapphire", "omega-ruby", "alpha-sapphire", "hg", "omega-ruby",
     sprites("pokeapi", "generation-vi/omegaruby-alphasapphire", "sprites/oras"),
     grid(31, INFERRED_GRID + " Final box unlocks after catching Rayquaza."),
     [dex("hoenn", "Hoenn Pokédex", "updated-hoenn", 211, HOENN6)]),
    ("alpha-sapphire", "Pokémon Alpha Sapphire", "Alpha Sapphire", 6, "Hoenn", "omega-ruby-alpha-sapphire", "alpha-sapphire", "omega-ruby", "ss", "alpha-sapphire",
     sprites("pokeapi", "generation-vi/omegaruby-alphasapphire", "sprites/oras"),
     grid(31, INFERRED_GRID + " Final box unlocks after catching Rayquaza."),
     [dex("hoenn", "Hoenn Pokédex", "updated-hoenn", 211, HOENN6)]),

    ("sun", "Pokémon Sun", "Sun", 7, "Alola", "sun-moon", "sun", "moon", "hg", "sun",
     sprites("pokemondb", "sun-moon", "sprites/sm",
             "PokeAPI has no Sun/Moon sprite set; these are PokemonDB's."),
     grid(32, INFERRED_GRID + " Box count 8/16/24/32."),
     [dex("alola", "Alola Pokédex", "original-alola", 302, ALOLA_SM)]),
    ("moon", "Pokémon Moon", "Moon", 7, "Alola", "sun-moon", "moon", "sun", "ss", "moon",
     sprites("pokemondb", "sun-moon", "sprites/sm",
             "PokeAPI has no Sun/Moon sprite set; these are PokemonDB's."),
     grid(32, INFERRED_GRID + " Box count 8/16/24/32."),
     [dex("alola", "Alola Pokédex", "original-alola", 302, ALOLA_SM)]),
    ("ultra-sun", "Pokémon Ultra Sun", "Ultra Sun", 7, "Alola", "ultra-sun-ultra-moon", "ultra-sun", "ultra-moon", "hg", "ultra-sun",
     sprites("pokeapi", "generation-vii/ultra-sun-ultra-moon", "sprites/usum"),
     grid(32, INFERRED_GRID + " Box count 8/16/24/32."),
     [dex("alola", "Alola Pokédex", "updated-alola", 403, ALOLA_US)]),
    ("ultra-moon", "Pokémon Ultra Moon", "Ultra Moon", 7, "Alola", "ultra-sun-ultra-moon", "ultra-moon", "ultra-sun", "ss", "ultra-moon",
     sprites("pokeapi", "generation-vii/ultra-sun-ultra-moon", "sprites/usum"),
     grid(32, INFERRED_GRID + " Box count 8/16/24/32."),
     [dex("alola", "Alola Pokédex", "updated-alola", 403, ALOLA_US)]),
    ("lets-go-pikachu", "Pokémon: Let's Go, Pikachu!", "Let's Go Pikachu", 7, "Kanto", "lets-go-pikachu-lets-go-eevee", "lets-go-pikachu", "lets-go-eevee", "hg", "lets-go-pikachu",
     sprites("pokemondb", "lets-go-pikachu-eevee", "sprites/lgpe",
             "PokeAPI has no Let's Go sprite set; these are PokemonDB's."),
     {"style": "single", "cols": 6, "rows": 0, "perBox": 1000, "count": 1,
      "source": BULBA + "Pok%C3%A9mon_Box — \"a single continuous list of "
      "Pokémon... It can hold up to 1,000 Pokémon.\" Not a box grid at all."},
     [dex("kanto", "Kanto Pokédex", "letsgo-kanto", 153, KANTO)]),
    ("lets-go-eevee", "Pokémon: Let's Go, Eevee!", "Let's Go Eevee", 7, "Kanto", "lets-go-pikachu-lets-go-eevee", "lets-go-eevee", "lets-go-pikachu", "ss", "lets-go-eevee",
     sprites("pokemondb", "lets-go-pikachu-eevee", "sprites/lgpe",
             "PokeAPI has no Let's Go sprite set; these are PokemonDB's."),
     {"style": "single", "cols": 6, "rows": 0, "perBox": 1000, "count": 1,
      "source": BULBA + "Pok%C3%A9mon_Box — single 1,000-slot continuous list."},
     [dex("kanto", "Kanto Pokédex", "letsgo-kanto", 153, KANTO)]),

    ("sword", "Pokémon Sword", "Sword", 8, "Galar", "sword-shield", "sword", "shield", "hg", "sword",
     sprites("pokemondb", "sword-shield", "sprites/swsh",
             "PokeAPI has no Sword/Shield sprite set; these are PokemonDB's."),
     grid(32, INFERRED_GRID + " Box count 8/16/24/31/32; the 32nd unlocks after "
          "catching Eternatus."),
     [dex("galar", "Galar Pokédex", "galar", 400, GALAR),
      dex("isle-of-armor", "Isle of Armor Pokédex", "isle-of-armor", 211, IOA),
      dex("crown-tundra", "Crown Tundra Pokédex", "crown-tundra", 210, CT)]),
    ("shield", "Pokémon Shield", "Shield", 8, "Galar", "sword-shield", "shield", "sword", "ss", "shield",
     sprites("pokemondb", "sword-shield", "sprites/swsh",
             "PokeAPI has no Sword/Shield sprite set; these are PokemonDB's."),
     grid(32, INFERRED_GRID + " Box count 8/16/24/31/32."),
     [dex("galar", "Galar Pokédex", "galar", 400, GALAR),
      dex("isle-of-armor", "Isle of Armor Pokédex", "isle-of-armor", 211, IOA),
      dex("crown-tundra", "Crown Tundra Pokédex", "crown-tundra", 210, CT)]),
    ("brilliant-diamond", "Pokémon Brilliant Diamond", "Brilliant Diamond", 8, "Sinnoh", "brilliant-diamond-shining-pearl", "brilliant-diamond", "shining-pearl", "hg", "brilliant-diamond",
     sprites("pokeapi", "generation-viii/brilliant-diamond-shining-pearl", "sprites/bdsp"),
     grid(40, INFERRED_GRID + " Box count 18/24/30/35/40."),
     [dex("sinnoh", "Sinnoh Pokédex", "original-sinnoh", 151, SINNOH)]),
    ("shining-pearl", "Pokémon Shining Pearl", "Shining Pearl", 8, "Sinnoh", "brilliant-diamond-shining-pearl", "shining-pearl", "brilliant-diamond", "ss", "shining-pearl",
     sprites("pokeapi", "generation-viii/brilliant-diamond-shining-pearl", "sprites/bdsp"),
     grid(40, INFERRED_GRID + " Box count 18/24/30/35/40."),
     [dex("sinnoh", "Sinnoh Pokédex", "original-sinnoh", 151, SINNOH)]),
    ("legends-arceus", "Pokémon Legends: Arceus", "Legends: Arceus", 8, "Hisui", "legends-arceus", "legends-arceus", None, "hg", "legends-arceus",
     sprites("pokemondb", "legends-arceus", "sprites/pla",
             "PokeAPI has no Legends: Arceus sprite set; these are PokemonDB's."),
     {"style": "pasture", "cols": 6, "rows": 5, "perBox": 30, "count": 32,
      "source": BULBA + "Pasture — \"Each pasture can hold up to 30 Pokémon\", "
      "up to 32 pastures. Presentation is a pen Pokémon roam in, not fixed slots; "
      "the 6x5 arrangement here is a reading aid, not the game's layout."},
     [dex("hisui", "Hisui Pokédex", "hisui", 242, HISUI)]),

    ("scarlet", "Pokémon Scarlet", "Scarlet", 9, "Paldea", "scarlet-violet", "scarlet", "violet", "hg", "scarlet",
     sprites("pokeapi", "generation-ix/scarlet-violet", "sprites/sv"),
     grid(32, INFERRED_GRID + " Box count 8/16/32."),
     [dex("paldea", "Paldea Pokédex", "paldea", 400, PALDEA),
      dex("kitakami", "Kitakami Pokédex", "kitakami", 200, KITA),
      dex("blueberry", "Blueberry Pokédex", "blueberry", 243, BLUE)]),
    ("violet", "Pokémon Violet", "Violet", 9, "Paldea", "scarlet-violet", "violet", "scarlet", "ss", "violet",
     sprites("pokeapi", "generation-ix/scarlet-violet", "sprites/sv"),
     grid(32, INFERRED_GRID + " Box count 8/16/32."),
     [dex("paldea", "Paldea Pokédex", "paldea", 400, PALDEA),
      dex("kitakami", "Kitakami Pokédex", "kitakami", 200, KITA),
      dex("blueberry", "Blueberry Pokédex", "blueberry", 243, BLUE)]),
    ("legends-za", "Pokémon Legends: Z-A", "Legends: Z-A", 9, "Lumiose", "legends-za", "legends-za", None, "hg", None,
     sprites("pokeapi", "generation-ix/scarlet-violet", "sprites/sv",
             "No per-game sprite set exists for Legends: Z-A on PokeAPI or "
             "PokemonDB. Scarlet/Violet sprites are used as the nearest-era "
             "stand-in — these are NOT Z-A's own artwork."),
     grid(32, INFERRED_GRID + " Box count 8/16/24/31/32; the 31st unlocks after "
          "obtaining the Rogue Mega Absol."),
     [dex("lumiose", "Lumiose Pokédex", "lumiose-city", 232, LUMIOSE),
      dex("hyperspace", "Hyperspace Pokédex", "hyperspace", 132, HYPER)]),
]


def main():
    games = []
    for (gid, name, short, gen, region, vg, version, paired, accent, boxart,
         spr, boxes, dexes) in TABLE:
        entry = {
            "id": gid, "name": name, "shortName": short,
            "status": "planned",
            "generation": gen, "region": region,
            "versionGroup": vg, "pokeapiVersion": version,
            "pairedWith": paired, "accent": accent,
            "dexes": dexes, "boxes": boxes, "sprites": spr,
            "boxart": f"boxart/{boxart}.jpg" if boxart else None,
            "links": {}, "sources": {},
        }
        games.append(entry)

    with open(os.path.join(ROOT, "games.json"), encoding="utf-8") as fh:
        existing = {g["id"]: g for g in json.load(fh)["games"]}

    # Preserve anything already curated (status, links, source URLs).
    for entry in games:
        old = existing.get(entry["id"])
        if not old:
            continue
        entry["status"] = old.get("status", entry["status"])
        entry["links"] = old.get("links", {})
        entry["sources"] = old.get("sources", {})
        for dexspec in entry["dexes"]:
            for old_dex in old.get("dexes", []):
                if old_dex["key"] == dexspec["key"] and "pokemondbDex" in old_dex:
                    dexspec["pokemondbDex"] = old_dex["pokemondbDex"]

    payload = {"$schema": json.load(open(os.path.join(ROOT, "games.json"),
                                        encoding="utf-8")).get("$schema", {}),
               "games": games}
    with open(os.path.join(ROOT, "games.json"), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)

    print(f"seeded {len(games)} games")
    for style in ("grid", "list", "single", "pasture"):
        ids = [g["id"] for g in games if g["boxes"]["style"] == style]
        print(f"  {style:8s} {len(ids):2d}  {', '.join(ids)}")
    print(f"  total dex entries across all games: "
          f"{sum(d['size'] for g in games for d in g['dexes'])}")


if __name__ == "__main__":
    main()
