"""Polite, caching HTTP fetcher shared by every scraper.

Three things this guarantees, all of which came out of checking the sources'
robots.txt and terms directly:

* **Everything is cached to disk.** PokeAPI's fair-use policy asks for exactly
  this, and it means a re-run of the pipeline costs zero requests.
* **Per-host throttling.** pokemondb.net publishes ``Crawl-delay: 2``;
  bulbagarden publishes 5. We honour the strictest value we saw per host.
* **A real User-Agent.** pokemondb's robots.txt bans ``wget`` outright, so the
  default urllib UA is not safe to use.

Every response is recorded in a provenance manifest (URL, fetch time, sha256)
so the shipped dataset can be audited without committing the raw bytes.
"""

import gzip
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from . import config

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_DIR = os.path.join(ROOT, "raw")
MANIFEST_PATH = os.path.join(RAW_DIR, "manifest.json")

# Politeness comes from config.json so it can be tuned without touching code.
# The values there are taken from each site's robots.txt; PokeAPI publishes no
# Crawl-delay but asks that we be gentle.
_SCRAPING = config.load().get("scraping", {})
USER_AGENT = _SCRAPING.get("userAgent", "RegionalDexBuddy/1.0")
CRAWL_DELAY = _SCRAPING.get("crawlDelaySeconds", {})
DEFAULT_DELAY = _SCRAPING.get("defaultCrawlDelaySeconds", 2.0)

_last_request_at = {}
_manifest = None


def _host_of(url):
    return urllib.parse.urlparse(url).netloc


def _cache_path(url):
    """Content-addressed cache path, with the host kept for legibility."""
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    host = _host_of(url).replace(":", "_")
    return os.path.join(RAW_DIR, host, digest[:2], digest + ".gz")


def _load_manifest():
    global _manifest
    if _manifest is None:
        try:
            with open(MANIFEST_PATH, "r", encoding="utf-8") as fh:
                _manifest = json.load(fh)
        except (OSError, ValueError):
            _manifest = {}
    return _manifest


def save_manifest():
    """Flush the provenance manifest to disk."""
    manifest = _load_manifest()
    os.makedirs(RAW_DIR, exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)


def manifest_entries():
    """Provenance records for everything fetched so far."""
    return dict(_load_manifest())


def _throttle(url):
    host = _host_of(url)
    delay = CRAWL_DELAY.get(host, DEFAULT_DELAY)
    last = _last_request_at.get(host)
    if last is not None:
        wait = delay - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)
    _last_request_at[host] = time.monotonic()


def fetch(url, *, encoding="utf-8", binary=False, refresh=False, retries=3):
    """Fetch ``url``, returning cached bytes/text when available.

    ``encoding`` matters: Serebii serves ISO-8859-1, not UTF-8.
    """
    path = _cache_path(url)
    if not refresh and os.path.exists(path):
        with gzip.open(path, "rb") as fh:
            raw = fh.read()
        return raw if binary else raw.decode(encoding, errors="replace")

    last_error = None
    for attempt in range(retries):
        _throttle(url)
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "*/*" if binary else "text/html,application/json;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                raw = response.read()
            break
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
    else:  # pragma: no cover - loop always breaks or raises
        raise last_error

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with gzip.open(path, "wb") as fh:
        fh.write(raw)

    manifest = _load_manifest()
    manifest[url] = {
        "url": url,
        "fetchedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }

    return raw if binary else raw.decode(encoding, errors="replace")


def fetch_json(url, *, refresh=False):
    return json.loads(fetch(url, refresh=refresh))
