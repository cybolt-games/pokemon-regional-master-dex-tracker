/* Durable collection state.
 *
 * Caught state is real hours of play, so it does not live only in a browser
 * key that a cleared cache — or a careless line of test code — can wipe. The
 * source of truth is a CSV on disk, written through a small API on the local
 * server. Rows identify a Pokémon by game, dex and species NAME, never by an
 * internal key, so the file survives any amount of refactoring.
 *
 * localStorage stays as a mirror so the page works with no server at all, and
 * whichever side has more marked is the one that wins on load — losing progress
 * is always the worse error.
 */

const Collection = {
  api: (document.body.dataset.root || "") + "api/collection",
  /* ?demo=1 isolates everything in a throwaway namespace and never contacts
     the server. Screenshots and manual testing use it so that real progress
     can't be written over. */
  demo: new URLSearchParams(location.search).get("demo") === "1",
  serverOk: false,
  rows: [],           // canonical CSV rows, all games
  gameId: null,
  dexOf: new Map(),   // "dexKey:number" -> {dex, number, species}
  _timer: null,

  key(gameId) {
    return this.demo ? `rdb:demo:${gameId}` : `rdb:caught:${gameId}`;
  },

  /* ------------------------------------------------------------- loading */

  async load(gameId, dexes) {
    this.gameId = gameId;
    this.dexOf.clear();
    for (const dex of dexes) {
      for (const entry of dex.entries) {
        this.dexOf.set(`${dex.key}:${entry.dex}`, {
          dex: dex.key, number: entry.dex, species: entry.slug,
        });
      }
    }

    const fromServer = await this._loadServer();
    const fromLocal = this._loadLocal(dexes);

    /* Prefer whichever source knows about more caught Pokemon. A server file
       that exists but is empty must never silently wipe a populated browser. */
    let caught = fromLocal;
    if (fromServer && fromServer.size >= fromLocal.size) caught = fromServer;
    if (fromServer && fromServer.size < fromLocal.size && fromLocal.size) {
      /* Browser is ahead — push it up so the file catches up. */
      this._saveServer(caught);
    }
    return caught;
  },

  async _loadServer() {
    if (this.demo) return null;
    try {
      const response = await fetch(this.api, {cache: "no-store"});
      if (!response.ok) return null;
      const data = await response.json();
      this.serverOk = true;
      this.rows = data.rows || [];
      const set = new Set();
      const bySpecies = new Map();
      for (const [key, meta] of this.dexOf) {
        bySpecies.set(`${meta.dex}:${meta.species}`, key);
      }
      for (const row of this.rows) {
        if (row.game !== this.gameId) continue;
        if (String(row.caught) !== "1") continue;
        /* Match on species name first, falling back to the number. */
        const key = bySpecies.get(`${row.dex}:${row.species}`)
          || `${row.dex}:${row.dex_number}`;
        if (this.dexOf.has(key)) set.add(key);
      }
      return set;
    } catch (err) {
      this.serverOk = false;
      return null;
    }
  },

  _loadLocal(dexes) {
    let stored = [];
    try {
      const raw = localStorage.getItem(this.key(this.gameId));
      stored = raw ? JSON.parse(raw) : [];
    } catch (err) {
      return new Set();
    }
    /* Saves from before games could carry several dexes stored bare numbers. */
    if (dexes && dexes.length === 1 && stored.some((v) => typeof v === "number")) {
      const key = dexes[0].key;
      stored = stored.map((v) => (typeof v === "number" ? `${key}:${v}` : v));
    }
    return new Set(stored);
  },

  /* ------------------------------------------------------------- saving */

  save(caught) {
    try {
      localStorage.setItem(this.key(this.gameId), JSON.stringify([...caught]));
    } catch (err) {
      /* Storage unavailable — the server copy still carries it. */
    }
    clearTimeout(this._timer);
    this._timer = setTimeout(() => this._saveServer(caught), 400);
  },

  async _saveServer(caught) {
    if (this.demo) return;
    /* Replace only this game's rows; every other game's stay untouched. */
    const others = this.rows.filter((r) => r.game !== this.gameId);
    const mine = [];
    for (const [key, meta] of this.dexOf) {
      mine.push({
        game: this.gameId, dex: meta.dex, dex_number: meta.number,
        species: meta.species, caught: caught.has(key) ? "1" : "0",
      });
    }
    const rows = others.concat(mine);
    try {
      const response = await fetch(this.api, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({rows}),
      });
      if (response.ok) {
        this.serverOk = true;
        this.rows = rows;
      }
    } catch (err) {
      this.serverOk = false;
    }
    this._render();
  },

  /* ------------------------------------------------- export / import CSV */

  toCsv(caught) {
    const lines = ["game,dex,dex_number,species,caught"];
    for (const [key, meta] of this.dexOf) {
      lines.push([this.gameId, meta.dex, meta.number, meta.species,
                  caught.has(key) ? "1" : "0"].join(","));
    }
    return lines.join("\n");
  },

  fromCsv(text) {
    const set = new Set();
    const lines = text.trim().split(/\r?\n/);
    const header = lines.shift().split(",").map((h) => h.trim());
    const at = (row, name) => row[header.indexOf(name)];
    const bySpecies = new Map();
    for (const [key, meta] of this.dexOf) {
      bySpecies.set(`${meta.dex}:${meta.species}`, key);
    }
    for (const line of lines) {
      if (!line.trim()) continue;
      const row = line.split(",");
      if (at(row, "game") !== this.gameId) continue;
      if (String(at(row, "caught")).trim() !== "1") continue;
      const key = bySpecies.get(`${at(row, "dex")}:${at(row, "species")}`)
        || `${at(row, "dex")}:${at(row, "dex_number")}`;
      if (this.dexOf.has(key)) set.add(key);
    }
    return set;
  },

  /* ------------------------------------------------------ status display */

  mount(node, caught) {
    this._node = node;
    this._caught = caught;
    this._render();
  },

  _render() {
    if (!this._node) return;
    this._node.textContent = this.demo
      ? "Demo mode — nothing is saved"
      : this.serverOk
        ? "Saved to collection.csv"
        : "Saved in this browser only";
    this._node.className = "savestate" + (this.serverOk ? " ok" : "");
    this._node.title = this.serverOk
      ? "Every change is written to collection.csv on disk, with a rolling backup."
      : "No local server detected, so progress is kept in this browser. "
        + "Use Export to keep a copy.";
  },
};
