# Notice, attribution and disclaimers

## No affiliation

This is an unofficial, non-commercial fan project. It is **not affiliated with,
endorsed by, sponsored by, or connected to** Nintendo, Creatures Inc.,
GAME FREAK inc., The Pokémon Company, or any of their subsidiaries or partners.

## No ownership claimed

Pokémon, Pokémon character names, sprites, cover art, and all related names,
marks, logos and imagery are **trademarks and copyright of their respective
owners** — Nintendo, Creatures Inc., GAME FREAK inc. and The Pokémon Company.

The maintainers of this project **claim no ownership of, and assert no rights
over**, any of that material. It is reproduced here solely to make a personal
reference tool usable, and remains the property of its owners in every respect.

The MIT licence in `LICENSE` applies to **the source code only**. It does not
grant any rights in the Pokémon data, sprites, or artwork, because those were
never the project's to grant.

## Provided as-is

This project is provided **as-is, without warranty of any kind**, express or
implied. No guarantee is made that any of the data is accurate, complete, or
current. It is a hobby tool for planning your own Pokédex, not an authoritative
reference. Verify anything that matters in-game.

Some data is known to be incomplete, and the app says so where it is:

- PokéAPI has no encounter tables for Brilliant Diamond / Shining Pearl,
  Legends: Arceus, or Scarlet / Violet; those locations come from PokémonDB's
  summary text instead, without level ranges or rarities.
- Sources sometimes disagree. Rather than pick a winner, the app flags the
  disagreement and shows what each source claims.
- Legends: Z-A has no per-game sprite set anywhere, so Scarlet/Violet sprites
  stand in for it. They are not that game's own artwork, and the app says so.

## Data sources

Gratefully assembled from, and with thanks to:

| Source | Used for |
| --- | --- |
| [PokéAPI](https://pokeapi.co/) | Regional dex ordering, encounter tables, evolution chains, location names, sprites |
| [PokémonDB](https://pokemondb.net/) | Dex-order cross-checks, human-readable locations, version exclusives, sprites, cover art |
| [Serebii](https://www.serebii.net/) | Version exclusives, unobtainable lists, Legends: Z-A locations and cover art |
| [Bulbapedia](https://bulbapedia.bulbagarden.net/) | Regional dex sizes, PC storage mechanics, walkthrough links |
| [pret disassemblies](https://github.com/pret) | Primary-source PC box dimensions for Gen 1–4 |

Bulbapedia content is licensed CC BY-NC-SA; this project links to it rather than
reproducing it. The scrapers honour each site's `robots.txt` and crawl-delay, cache
locally so re-runs cost nothing, and identify themselves with a real User-Agent.

If you run the scrapers yourself, please be equally considerate — these are free
community resources.

## Redistribution

If you fork, mirror or deploy this publicly, understand that you are also
redistributing copyrighted images and data belonging to the rights holders above.
That is your responsibility to assess, not this project's.

**Sprites and cover art are deliberately not distributed in this repository.**
They are downloaded from their original sources by `setup.py` when you set the
project up, so what is published here is the code and the factual data, not
Nintendo's artwork.

## Takedown

If you are a rights holder and want material removed, please open an issue on the
repository and it will be taken down promptly.
