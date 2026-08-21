"""Load the deployment config and the game registry.

Two files at the repo root drive everything:

``config.json``  how this deployment behaves — where assets come from, whether
                 a CDN is in play, scraping politeness. Defaults are fully
                 local so a fresh clone works offline with no setup.
``games.json``   which games exist and how each one is shaped. Adding a game is
                 a data change, not a code change.

An optional ``config.local.json`` overrides ``config.json`` key by key, so a
personal setup (a private CDN, say) never has to be committed.
"""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_PATH = os.path.join(ROOT, "config.json")
LOCAL_CONFIG_PATH = os.path.join(ROOT, "config.local.json")
GAMES_PATH = os.path.join(ROOT, "games.json")

_config = None
_games = None


def _strip_comments(value):
    """Drop the ``$``-prefixed documentation keys before the config is used."""
    if isinstance(value, dict):
        return {k: _strip_comments(v) for k, v in value.items()
                if not k.startswith("$")}
    if isinstance(value, list):
        return [_strip_comments(v) for v in value]
    return value


def _deep_merge(base, override):
    out = dict(base)
    for key, value in override.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load():
    """The merged config, comments stripped."""
    global _config
    if _config is None:
        with open(CONFIG_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        if os.path.exists(LOCAL_CONFIG_PATH):
            with open(LOCAL_CONFIG_PATH, encoding="utf-8") as fh:
                data = _deep_merge(data, json.load(fh))
        _config = _strip_comments(data)
    return _config


def games(status=None):
    """Every game in the registry, optionally filtered by status."""
    global _games
    if _games is None:
        with open(GAMES_PATH, encoding="utf-8") as fh:
            _games = _strip_comments(json.load(fh))["games"]
    if status is None:
        return list(_games)
    wanted = {status} if isinstance(status, str) else set(status)
    return [g for g in _games if g.get("status") in wanted]


def games_meta():
    """Top-level metadata from games.json (anything outside the games list)."""
    with open(GAMES_PATH, encoding="utf-8") as fh:
        raw = json.load(fh)
    return _strip_comments(raw.get("$assets", {}))


def game(game_id):
    for entry in games():
        if entry["id"] == game_id:
            return entry
    raise KeyError(f"no game '{game_id}' in games.json")


def version_groups(status=None):
    """Games grouped by version group — the unit most scraping works on."""
    grouped = {}
    for entry in games(status):
        grouped.setdefault(entry["versionGroup"], []).append(entry)
    return grouped


def active_profile():
    cfg = load()
    name = cfg["assets"]["profile"]
    profiles = cfg["assets"]["profiles"]
    if name not in profiles:
        raise SystemExit(
            f"config.json: assets.profile '{name}' is not one of "
            f"{', '.join(sorted(profiles))}"
        )
    return name, profiles[name]


def site_asset_config():
    """The subset of config the browser needs.

    Deliberately excludes everything under ``publish`` — SSH hosts and remote
    paths have no business being served to a browser.
    """
    cfg = load()
    assets = cfg["assets"]
    name, profile = active_profile()
    return {
        "profile": name,
        "tiers": profile["tiers"],
        "cdn": assets.get("cdn", {}),
        "public": assets.get("public", {}),
        "localBase": assets.get("localBase", "assets/"),
    }
