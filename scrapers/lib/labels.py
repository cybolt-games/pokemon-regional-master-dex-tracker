"""Turn PokeAPI's slug vocabulary into text a player can act on.

Every key here was observed in the actual HG/SS encounter data (see
``raw/parsed/pokeapi.json``) rather than assumed. Anything unmapped falls back
to a humanised version of the slug, which is still source-derived — we never
invent a label we can't trace.
"""

import re

# Methods, in the order they should appear when a species has several.
METHOD_LABELS = {
    "walk": "Tall grass",
    "surf": "Surfing",
    "old-rod": "Fishing · Old Rod",
    "good-rod": "Fishing · Good Rod",
    "super-rod": "Fishing · Super Rod",
    "headbutt": "Headbutt tree",
    "rock-smash": "Rock Smash",
    "static": "Fixed encounter",
    "gift": "Gift",
    "gift-egg": "Gift · Egg",
    "roaming-grass": "Roaming",
    "pokeflute": "Poké Flute",
    "squirt-bottle": "SquirtBottle",
    # Gen 2-4
    "headbutt-low": "Headbutt tree (low)",
    "headbutt-normal": "Headbutt tree",
    "headbutt-high": "Headbutt tree (high)",
    "honey-tree": "Honey tree",
    "berry-trees": "Berry tree",
    "npc-trade": "In-game trade",
    "roaming-water": "Roaming (water)",
    "devon-scope": "Devon Scope",
    "wailmer-pail": "Wailmer Pail",
    "feebas-tile-fishing": "Feebas tile (fishing)",
    # Gen 5
    "dark-grass": "Dark grass",
    "grass-spots": "Rustling grass",
    "cave-spots": "Dust cloud",
    "bridge-spots": "Bird shadow",
    "surf-spots": "Rippling water",
    "super-rod-spots": "Fishing · rippling water",
    "hidden-grotto": "Hidden Grotto",
    "seaweed": "Seaweed",
    # Gen 6
    "horde": "Horde encounter",
    "rough-terrain": "Rough terrain",
    "red-flowers": "Red flowers",
    "yellow-flowers": "Yellow flowers",
    "purple-flowers": "Purple flowers",
    # Gen 7
    "sos": "SOS call",
    "sos-from-bubbling-spot": "SOS call · bubbling spot",
    "bubbling-spots": "Bubbling spot",
    "island-scan": "Island Scan",
    # Let's Go — everything is visible in the overworld
    "overworld": "Overworld",
    "overworld-water": "Overworld · water",
    "overworld-flying": "Overworld · flying",
    "overworld-flying-special": "Overworld · rare flying",
    "overworld-dirt": "Overworld · dirt patch",
    "overworld-special": "Overworld · rare spawn",
    "overworld-water-special": "Overworld · rare water",
    # Sword/Shield
    "max-raid": "Max Raid Battle",
    "wanderer": "Wandering overworld",
    "wanderer-water": "Wandering on water",
    "ceiling-ambush": "Ambush from the ceiling",
    "ground-ambush": "Ambush from the ground",
    "sky-ambush": "Ambush from the sky",
    "trash-can-ambush": "Ambush from a bin",
    "rustling-bush-ambush": "Ambush from a bush",
    "dynamax-adventure": "Dynamax Adventure",
    # Side games that share the encounter tables
    "colosseum-bonus-disc-jpn": "Colosseum bonus disc (JP)",
    "colosseum-bonus-disc-us": "Colosseum bonus disc (US)",
    "pokemon-channel-pal": "Pokémon Channel (PAL)",
    "pokemon-ranger": "Pokémon Ranger",
}

METHOD_ORDER = [
    "gift", "gift-egg", "static", "npc-trade",
    "roaming-grass", "roaming-water", "pokeflute", "squirt-bottle", "devon-scope",
    "walk", "dark-grass", "grass-spots", "rough-terrain",
    "overworld", "overworld-special", "overworld-dirt",
    "overworld-flying", "overworld-flying-special",
    "wanderer", "wanderer-water",
    "red-flowers", "yellow-flowers", "purple-flowers",
    "horde", "sos", "sos-from-bubbling-spot", "island-scan",
    "headbutt", "headbutt-low", "headbutt-normal", "headbutt-high",
    "honey-tree", "berry-trees", "rock-smash",
    "cave-spots", "bridge-spots", "hidden-grotto",
    "ceiling-ambush", "ground-ambush", "sky-ambush",
    "trash-can-ambush", "rustling-bush-ambush",
    "surf", "surf-spots", "overworld-water", "overworld-water-special",
    "bubbling-spots", "seaweed",
    "old-rod", "good-rod", "super-rod", "super-rod-spots", "feebas-tile-fishing",
    "max-raid", "dynamax-adventure",
]

# Conditions that repeat on nearly every row and say nothing about *where* to
# look. Kept in the data, dimmed in the UI.
NOISY_CONDITIONS = {
    "radio-off", "swarm-no", "bug-catching-contest-no",
    "johto-safari-blocks-inactive", "radar-off", "slot2-none",
    "weather-normal",
}

CONDITION_LABELS = {
    "time-morning": "Morning",
    "time-day": "Day",
    "time-night": "Night",
    "radio-off": "Radio off",
    "swarm-yes": "During a swarm",
    "swarm-no": "No swarm",
    "bug-catching-contest-yes": "Bug-Catching Contest",
    "bug-catching-contest-no": "Outside the contest",
    "headbutt-tree-common": "Common tree",
    "headbutt-tree-rare": "Rare tree",
    "headbutt-tree-secret": "Special tree",
    "johto-safari-blocks-inactive": "Before placing blocks",
    "story-progress-national-dex": "After the National Dex",
    "story-progress-before-national-dex": "Before the National Dex",
    "story-progress-beat-red": "After beating Red",
    "story-progress-awakened-beasts": "After awakening the beasts",
    "story-progress-zephyr-badge": "After the Zephyr Badge",
    "story-progress-receive-tm-from-claire": "After Clair's TM",
    "story-progress-returned-machine-part": "After returning the Machine Part",
    "other-correct-password": "With the correct password",
    "other-snorlax-11-beat-league": "After beating the League",
    "item-old-amber": "Revive the Old Amber",
    "item-dome-fossil": "Revive the Dome Fossil",
    "item-helix-fossil": "Revive the Helix Fossil",
    # Gen 4
    "radar-on": "Using the Poké Radar",
    "radar-off": "Without the Poké Radar",
    "radio-hoenn": "Radio: Hoenn Sound",
    "radio-sinnoh": "Radio: Sinnoh Sound",
    "slot2-none": "No GBA cartridge inserted",
    "backlot-mentioned": "After the Backlot mentions it",
    # Gen 5
    "season-spring": "Spring",
    "season-summer": "Summer",
    "season-autumn": "Autumn",
    "season-winter": "Winter",
}

# Condition families rendered by pattern rather than one key at a time.
_SLOT2 = re.compile(r"^slot2-(\w+)$")
_WEATHER = re.compile(r"^weather-(\w+)$")
_DEN_RARITY = re.compile(r"^max-den-rarity-(\w+)$")
_DEN_RATING = re.compile(r"^max-den-rating-(\d+)-star$")
_FRIEND_SAFARI = re.compile(r"^friend-safari-slot-(\d+)$")
_HONEY = re.compile(r"^honey-tree-group-(\w+)$")
_MARSH = re.compile(r"^great-marsh-daily-slot-(\d+)-of-(\d+)$")
_STORY_HALL = re.compile(r"^story-progress-(before-)?hall-of-fame$")
_STORY_ANY = re.compile(r"^story-progress-(before-)?(.+)$")
_ITEM = re.compile(r"^item-(.+)$")
_BERRY = re.compile(r"^berry-tree-type-(\w+)$")
_DEFEATED = re.compile(r"^defeated-(.+)$")
_OTHER = re.compile(r"^other-(.+)$")

_SAFARI = re.compile(r"^johto-safari-blocks-(\w+)-min-(\d+)$")
_COINS = re.compile(r"^coins-(\d+)$")
_WEEKDAY = re.compile(r"^weekday-(\w+)$")


def humanise(slug):
    """Last-resort label: the slug itself, made readable."""
    return slug.replace("-", " ").capitalize()


# Words that stay lowercase when title-casing a slug.
_SMALL = {"a", "an", "and", "of", "the", "in", "on", "at", "to", "from", "with"}


def title(slug):
    """Title-case a slug, leaving short joining words alone."""
    words = slug.replace("-", " ").split()
    return " ".join(
        w if i and w in _SMALL else w.capitalize() for i, w in enumerate(words)
    )


def method_label(slug):
    return METHOD_LABELS.get(slug, humanise(slug))


def method_sort_key(slug):
    try:
        return METHOD_ORDER.index(slug)
    except ValueError:
        return len(METHOD_ORDER)


def condition_label(slug):
    if slug in CONDITION_LABELS:
        return CONDITION_LABELS[slug]

    match = _STORY_HALL.match(slug)
    if match:
        return "Before the Hall of Fame" if match.group(1) else "After the Hall of Fame"

    match = _SLOT2.match(slug)
    if match:
        return f"With {humanise(match.group(1))} in the GBA slot"

    match = _WEATHER.match(slug)
    if match:
        return {"intense": "Intense sun", "normal": "Clear weather"}.get(
            match.group(1), humanise(match.group(1)))

    match = _DEN_RARITY.match(slug)
    if match:
        return f"{humanise(match.group(1))} den"

    match = _DEN_RATING.match(slug)
    if match:
        return f"{match.group(1)}-star raid"

    match = _FRIEND_SAFARI.match(slug)
    if match:
        return f"Friend Safari slot {match.group(1)}"

    match = _HONEY.match(slug)
    if match:
        return f"Honey tree group {match.group(1).upper()}"

    match = _MARSH.match(slug)
    if match:
        return f"Great Marsh daily slot {match.group(1)} of {match.group(2)}"

    match = _BERRY.match(slug)
    if match:
        return f"{match.group(1).capitalize()} berry tree"

    match = _DEFEATED.match(slug)
    if match:
        return f"After defeating {title(match.group(1))}"

    match = _ITEM.match(slug)
    if match:
        return f"With the {title(match.group(1))}"

    match = _OTHER.match(slug)
    if match:
        words = match.group(1).replace("-", " ")
        return words[:1].upper() + words[1:]

    match = _STORY_ANY.match(slug)
    if match:
        when = "Before" if match.group(1) else "After"
        return f"{when} {title(match.group(2)).lower()}"

    match = _SAFARI.match(slug)
    if match:
        area, count = match.group(1), match.group(2)
        return f"Safari Zone · {count}+ {area} blocks"

    match = _COINS.match(slug)
    if match:
        return f"{int(match.group(1)):,} coins"

    match = _WEEKDAY.match(slug)
    if match:
        return f"{match.group(1).capitalize()}s"

    return humanise(slug)


def location_name(entry):
    """Display name for an encounter area.

    Two quirks confirmed against the live API: location-area English names
    render routes as "Road 29" where the parent location correctly says
    "Route 29", and ``pewter-city-area`` ships an empty ``names`` array.
    """
    name = entry.get("areaName") or entry.get("locationName")
    if not name:
        return humanise(entry.get("locationSlug", "")).title()
    if name.startswith("Road "):
        return "Route " + name[5:]
    return name


# PokeAPI carries three pseudo-areas ("unknown-all-bugs", "unknown-all-rattata",
# "unknown-all-poliwag") that are generic slot tables, not places you can walk
# to. Every species that appears in them also has real locations, so they are
# dropped rather than shown as a destination we can't name.
PSEUDO_AREAS = {
    "unknown-all-bugs-area",
    "unknown-all-rattata-area",
    "unknown-all-poliwag-area",
}


TRIGGER_TEMPLATES = {
    "level-up": "Level up",
    "use-item": "Use item",
    "trade": "Trade",
    "use-move": "Level up knowing a move",
}


def evolution_note(row, display_name):
    """A one-line 'how do I get this' sentence built from an evolution record."""
    parts = []
    trigger = row.get("trigger")

    if trigger == "level-up":
        if row.get("minLevel"):
            parts.append(f"Evolve {display_name} at Lv {row['minLevel']}")
        else:
            parts.append(f"Evolve {display_name}")
    elif trigger == "use-item" and row.get("item"):
        parts.append(f"Evolve {display_name} with a {humanise(row['item'])}")
    elif trigger == "trade":
        if row.get("heldItem"):
            parts.append(
                f"Trade {display_name} holding a {humanise(row['heldItem'])}"
            )
        elif row.get("tradeSpecies"):
            parts.append(
                f"Trade {display_name} for {row['tradeSpecies'].capitalize()}"
            )
        else:
            parts.append(f"Trade {display_name}")
    elif trigger == "use-move" and row.get("knownMove"):
        parts.append(
            f"Level up {display_name} knowing {humanise(row['knownMove'])}"
        )
    else:
        parts.append(f"Evolve {display_name}")

    qualifiers = []
    if row.get("timeOfDay"):
        qualifiers.append(f"during the {row['timeOfDay']}")
    if row.get("minHappiness"):
        qualifiers.append("with high friendship")
    if row.get("minBeauty"):
        qualifiers.append("with high beauty")
    if row.get("location"):
        qualifiers.append(f"at {humanise(row['location'])}")
    if row.get("heldItem") and trigger != "trade":
        qualifiers.append(f"holding a {humanise(row['heldItem'])}")
    if row.get("knownMove") and trigger != "use-move":
        qualifiers.append(f"knowing {humanise(row['knownMove'])}")
    if row.get("gender") == 1:
        qualifiers.append("female only")
    elif row.get("gender") == 2:
        qualifiers.append("male only")
    if row.get("partySpecies"):
        qualifiers.append(f"with {row['partySpecies'].capitalize()} in the party")
    if row.get("relativePhysicalStats") is not None:
        stats = {1: "Attack > Defense", 0: "Attack = Defense", -1: "Attack < Defense"}
        qualifiers.append(stats.get(row["relativePhysicalStats"], ""))

    qualifiers = [q for q in qualifiers if q]
    if qualifiers:
        parts.append("(" + ", ".join(qualifiers) + ")")
    return " ".join(parts)
