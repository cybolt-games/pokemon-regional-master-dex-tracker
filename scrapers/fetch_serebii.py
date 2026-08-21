#!/usr/bin/env python3
"""Scrape Serebii's version-exclusive and unobtainable lists.

Serebii is the third opinion on version exclusivity, and the only source that
publishes an explicit "not available anywhere in this game" list — which is how
event-only species get flagged rather than silently appearing catchable.

Page quirks that matter: Serebii serves ISO-8859-1 (not UTF-8), the section
headings are named anchors rather than heading tags, and the national dex
number is rendered as "#056".

URLs come from games.json, so adding a game is a data change.
"""

import json
import os
import re
import sys

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import config, http_cache

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "raw", "parsed")
OUT_PATH = os.path.join(OUT_DIR, "serebii.json")

# Serebii renders the national dex number as "#056".
NATDEX = re.compile(r"^#?(\d{1,4})$")


def soup_for(url):
    # Decoding as UTF-8 mangles the accented names.
    return BeautifulSoup(http_cache.fetch(url, encoding="latin-1"), "html.parser")


TABLE_CLASSES = ("dextable", "tab")


def data_tables(soup_or_node, limit=None):
    """Serebii's data tables. Gen 4 pages use class="dextable"; every other
    generation uses class="tab" for the identical structure."""
    found = []
    for cls in TABLE_CLASSES:
        found.extend(soup_or_node.select(f"table.{cls}"))
    return found[:limit] if limit else found


# Newer Serebii pages (Gen 7 onward) drop the national dex number entirely and
# identify each species only by its /pokedex-<game>/<slug>/ link.
SLUG_LINK = re.compile(r"/pokedex[^/]*/([a-z0-9][a-z0-9-]*)/?$")


def table_rows(table):
    """One record per species in a Serebii data table.

    Two page generations to cope with: the older layout puts the national dex
    number in the first cell, the newer one omits numbers and only links to the
    species page. Either identifier is enough for the build to match on.
    """
    out = []
    seen = set()
    for row in table.select("tr"):
        cells = [c.get_text(strip=True) for c in row.select("td")]

        if len(cells) >= 3:
            match = NATDEX.match(cells[0])
            if match:
                out.append({"natdex": int(match.group(1)), "name": cells[2]})
                continue

        for link in row.select("a[href]"):
            found = SLUG_LINK.search(link["href"].split("?")[0])
            if not found:
                continue
            slug = found.group(1)
            # Type links live in the same rows; they end in .shtml and so never
            # match, but guard against picking a species up twice per row.
            if slug in seen:
                continue
            seen.add(slug)
            name = link.get_text(strip=True)
            out.append({"slug": slug, "name": name or slug.capitalize()})
            break
    return out


def parse_exclusives(url, versions):
    """The exclusive tables, labelled by the named anchor preceding each.

    Serebii marks sections with <a name="heartgold">Exclusive to HeartGold</a>
    rather than a heading tag, so the anchor is the reliable handle — the
    surrounding text also contains a nav strip naming both games.
    """
    soup = soup_for(url)
    result = {}
    for version in versions:
        # Anchors drop the punctuation: "omega-ruby" -> "omegaruby".
        for candidate in (version, version.replace("-", ""),
                          version.replace("-", "").replace("pokemon", "")):
            anchor = soup.find("a", attrs={"name": candidate})
            if anchor:
                break
        if not anchor:
            continue
        table = anchor.find_next(
            lambda t: t.name == "table"
            and any(c in TABLE_CLASSES for c in (t.get("class") or []))
        )
        if table is None:
            continue
        rows = table_rows(table)
        if rows:
            result[version] = rows

    # Serebii's Black/White page names BOTH section anchors "black" (a genuine
    # site bug), so anchor matching yields one table twice. Fall back to taking
    # the data tables in document order when that happens.
    tables = data_tables(soup)
    if len(result) < len(versions) and len(tables) >= len(versions):
        rebuilt = {}
        for version, table in zip(versions, tables):
            rows = table_rows(table)
            if rows:
                rebuilt[version] = rows
        if len(rebuilt) > len(result):
            return rebuilt
    return result


def parse_unobtainable(url):
    soup = soup_for(url)
    rows = []
    for table in data_tables(soup):
        rows.extend(table_rows(table))
    return rows


def main():
    out = {}
    for version_group, entries in config.version_groups().items():
        game = entries[0]
        sources = game.get("sources", {})
        versions = [g["pokeapiVersion"] for g in entries]
        record = {}

        url = sources.get("serebiiExclusives")
        if url:
            try:
                parsed = parse_exclusives(url, versions)
                if parsed:
                    record["exclusives"] = parsed
                    print(f"  {version_group} exclusives: "
                          + ", ".join(f"{v}={len(r)}" for v, r in parsed.items()))
                else:
                    print(f"  {version_group} exclusives: no anchors matched "
                          f"{versions} at {url}")
            except Exception as exc:  # noqa: BLE001
                print(f"  {version_group} exclusives: FAILED {exc}")

        url = sources.get("serebiiUnobtainable")
        if url:
            try:
                rows = parse_unobtainable(url)
                if rows:
                    record["unobtainable"] = rows
                    print(f"  {version_group} unobtainable: {len(rows)}")
                else:
                    print(f"  {version_group} unobtainable: empty at {url}")
            except Exception as exc:  # noqa: BLE001
                print(f"  {version_group} unobtainable: FAILED {exc}")

        if record:
            record["urls"] = {k: v for k, v in sources.items()
                              if k.startswith("serebii")}
            out[version_group] = record

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False, sort_keys=True)
    http_cache.save_manifest()
    print(f"\nwrote {OUT_PATH} — {len(out)} version group(s)")


if __name__ == "__main__":
    main()
