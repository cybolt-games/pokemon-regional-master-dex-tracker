#!/usr/bin/env python3
"""One-command setup: fetch the images, then build the site.

The repository ships the *data* — dex ordering, locations, exclusives, box
geometry — but not the sprites and cover art. Those are Nintendo's artwork and
are not this project's to redistribute, so they are downloaded from their
original sources on first run instead.

    python3 setup.py

Takes a few minutes on a first run, mostly waiting out the crawl delays the
sources ask for. Everything is cached under raw/, so re-running is cheap.
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))

STEPS = [
    ("scrapers/fetch_sprites.py", "sprites for every registered game"),
    ("scrapers/fetch_boxart.py", "game cover art"),
    ("scrapers/build_dataset.py --config-only", "page shells and site config"),
]


def have_data():
    return os.path.isfile(os.path.join(ROOT, "site", "data", "home.json"))


def main():
    if not have_data():
        print("site/data is missing — this looks like an incomplete checkout.")
        print("Run the full pipeline instead (see the README):")
        print("  python3 scrapers/fetch_pokeapi.py  ... etc")
        return 1

    print("Fetching assets. They are cached, so re-running this is cheap.\n")
    for step, description in STEPS:
        print(f"==> {description}")
        parts = step.split()
        result = subprocess.run([sys.executable] + parts, cwd=ROOT)
        if result.returncode != 0:
            print(f"\n'{step}' failed. Fix the error above and re-run; "
                  f"anything already downloaded is kept.")
            return result.returncode
        print()

    sprites = os.path.join(ROOT, "site", "assets", "sprites")
    count = sum(len(files) for _, _, files in os.walk(sprites)) if os.path.isdir(sprites) else 0
    print(f"Done — {count} sprites in place.\n")
    print("Start it with:  python3 serve.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
