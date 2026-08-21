#!/usr/bin/env python3
"""Serve the Regional Dex Buddy site.

Static files, plus one small API for the collection store:

    GET  /api/collection   -> the CSV on disk
    POST /api/collection   -> replace the CSV on disk

Collection state lives in a plain CSV at the repo root rather than only in the
browser, so it survives cleared site data, a different browser, and any amount
of UI churn. The columns identify a Pokémon by game, dex and species name — not
by any internal key — so the file stays readable and importable no matter how
the app changes internally.

Usage: python3 serve.py [port]
"""

import csv
import functools
import gzip
import http.server
import io
import json
import os
import posixpath
import shutil
import socketserver
import sys
import time
import urllib.parse

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(BASE, "site")
COLLECTION = os.path.join(BASE, "collection.csv")
BACKUP_DIR = os.path.join(BASE, "collection-backups")

FIELDS = ["game", "dex", "dex_number", "species", "caught"]
MAX_BODY = 4 * 1024 * 1024

# The built datasets are large and highly repetitive — Sword's is 4 MB raw and
# 192 KB gzipped. Compressing them is the single biggest thing this server can
# do for load time on a phone.
COMPRESSIBLE = (".json", ".js", ".css", ".html", ".svg", ".csv", ".txt", ".map")
COMPRESS_MIN_BYTES = 1024

# A box page asks for one image per Pokémon — 151 for Kanto, 664 for Paldea. On
# localhost that is invisible, but over a network every one costs a round trip,
# and a single-threaded server serialises the browser's parallel connections
# into one queue. That is why the page felt fine on a desktop and took half a
# minute on a phone.
#
# Sprites and cover art never change for a given path, so they are cached hard.
# The datasets and pages are revalidated instead, which costs one cheap 304 and
# keeps a rebuild from serving stale data.
CACHE_IMMUTABLE = "public, max-age=2592000"       # 30 days — assets
CACHE_REVALIDATE = "no-cache"                      # data and pages


def read_collection():
    if not os.path.exists(COLLECTION):
        return []
    with open(COLLECTION, newline="", encoding="utf-8") as fh:
        return [row for row in csv.DictReader(fh)]


def write_collection(rows):
    """Write atomically, keeping a rolling backup.

    A collection represents real hours of play. It is never overwritten in
    place, and the previous file is always kept.
    """
    if os.path.exists(COLLECTION):
        os.makedirs(BACKUP_DIR, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        shutil.copy2(COLLECTION, os.path.join(BACKUP_DIR, f"collection-{stamp}.csv"))
        backups = sorted(os.listdir(BACKUP_DIR))
        for stale in backups[:-30]:
            os.remove(os.path.join(BACKUP_DIR, stale))

    tmp = COLLECTION + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in FIELDS})
    os.replace(tmp, COLLECTION)


class Handler(http.server.SimpleHTTPRequestHandler):
    def _json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _wants_gzip(self):
        return "gzip" in (self.headers.get("Accept-Encoding") or "").lower()

    def _local_path(self):
        path = urllib.parse.urlparse(self.path).path
        path = posixpath.normpath(urllib.parse.unquote(path))
        parts = [p for p in path.split("/") if p and p not in (".", "..")]
        return os.path.join(self.directory, *parts)

    def do_GET(self):
        if self.path.split("?")[0] == "/api/collection":
            rows = read_collection()
            return self._json(200, {"rows": rows, "count": len(rows)})

        target = self._local_path()
        if (self._wants_gzip()
                and target.lower().endswith(COMPRESSIBLE)
                and os.path.isfile(target)
                and os.path.getsize(target) >= COMPRESS_MIN_BYTES):
            try:
                with open(target, "rb") as fh:
                    body = gzip.compress(fh.read(), 6)
            except OSError:
                return super().do_GET()
            self.send_response(200)
            self.send_header("Content-Type", self.guess_type(target))
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Vary", "Accept-Encoding")
            self.send_header("Last-Modified",
                             self.date_time_string(int(os.stat(target).st_mtime)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
            return None

        return super().do_GET()

    def do_HEAD(self):
        return self.do_GET()

    def do_POST(self):
        if self.path.split("?")[0] != "/api/collection":
            return self._json(404, {"error": "not found"})

        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY:
            return self._json(400, {"error": "bad content-length"})
        try:
            payload = json.loads(self.rfile.read(length))
            rows = payload["rows"]
            if not isinstance(rows, list):
                raise ValueError("rows must be a list")
        except Exception as exc:  # noqa: BLE001
            return self._json(400, {"error": str(exc)})

        write_collection(rows)
        return self._json(200, {"ok": True, "count": len(rows)})

    def _cache_header_for(self, path):
        return CACHE_IMMUTABLE if path.startswith("/assets/") else CACHE_REVALIDATE

    def end_headers(self):
        if not self.path.startswith("/api/"):
            self.send_header("Cache-Control",
                             self._cache_header_for(self.path.split("?")[0]))
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("  %s\n" % (fmt % args))


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """Threaded, so the browser's parallel connections are actually parallel."""

    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 128


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    handler = functools.partial(Handler, directory=ROOT)
    with Server(("", port), handler) as httpd:
        existing = len(read_collection())
        print(f"Regional Dex Buddy → http://localhost:{port}")
        print(f"On your phone      → http://<this machine's IP>:{port}")
        print(f"Serving {ROOT}")
        print(f"Collection {COLLECTION} ({existing} row(s))")
        print("Ctrl-C to stop.\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nBye.")


if __name__ == "__main__":
    main()
