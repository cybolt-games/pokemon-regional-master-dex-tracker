/* Shared helpers. Plain ES modules-free script; every page includes this first. */

/* ROOT is declared in assets.js, which every page loads first. */

function asset(path) {
  return Assets.url(path, Assets.start);
}

/* Create an <img> wired to the CDN -> local -> public fallback chain. */
function assetImg(path, alt, className) {
  const img = el("img", className);
  img.alt = alt || "";
  Assets.bind(img, path);
  return img;
}

async function loadGame(id) {
  const response = await fetch(`${ROOT}data/${id}.json`);
  if (!response.ok) {
    throw new Error(`could not load data/${id}.json (${response.status})`);
  }
  return response.json();
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function padDex(n) {
  return String(n).padStart(3, "0");
}

/* ---------------------------------------------------------------- caught */

/* Per-game, stored locally. Wrapped because private-mode browsers throw on
   access rather than returning null. */
const Caught = {
  key: (gameId) => `rdb:caught:${gameId}`,

  load(gameId, dexes) {
    let stored = [];
    try {
      const raw = localStorage.getItem(this.key(gameId));
      stored = raw ? JSON.parse(raw) : [];
    } catch (err) {
      return new Set();
    }
    /* Saves made before games could carry several dexes stored bare numbers.
       A single-dex game can migrate them losslessly; anything else would be a
       guess, so it is left alone. */
    if (dexes && dexes.length === 1 && stored.some((v) => typeof v === "number")) {
      const key = dexes[0].key;
      stored = stored.map((v) => (typeof v === "number" ? `${key}:${v}` : v));
    }
    return new Set(stored);
  },

  save(gameId, set) {
    try {
      localStorage.setItem(this.key(gameId), JSON.stringify([...set]));
    } catch (err) {
      /* Storage unavailable — the page still works, it just won't remember. */
    }
  },
};

/* ----------------------------------------------------------------- modal */

/* One modal element, reused. Built here so every page gets identical behaviour. */
const Modal = {
  node: null,
  onToggleCaught: null,
  current: null,

  ensure() {
    if (this.node) return this.node;

    const overlay = el("div", "overlay");
    overlay.hidden = true;
    overlay.innerHTML = `
      <div class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-name">
        <header>
          <img alt="" data-el="sprite">
          <div>
            <div class="dexno" data-el="dexno"></div>
            <h2 id="modal-name" data-el="name"></h2>
            <div class="where" data-el="where"></div>
            <div class="types" data-el="types"></div>
          </div>
          <button class="close" data-el="close" aria-label="Close">&times;</button>
        </header>
        <div class="content" data-el="content"></div>
        <footer>
          <button class="btn ghost nav" data-el="prev" aria-label="Previous Pok&eacute;mon">&#8592;</button>
          <button class="btn ghost nav" data-el="next" aria-label="Next Pok&eacute;mon">&#8594;</button>
          <button class="btn gold" data-el="catch"></button>
          <a class="ext" data-el="ext" target="_blank" rel="noopener">
            View on Pok&eacute;monDB &#8599;
          </a>
        </footer>
      </div>`;

    document.body.appendChild(overlay);
    this.node = overlay;
    this.refs = {};
    overlay.querySelectorAll("[data-el]").forEach((n) => {
      this.refs[n.dataset.el] = n;
    });

    this.refs.close.addEventListener("click", () => this.hide());
    overlay.addEventListener("click", (event) => {
      if (event.target === overlay) this.hide();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !overlay.hidden) this.hide();
    });
    this.refs.catch.addEventListener("click", () => {
      if (this.current && this.onToggleCaught) {
        this.onToggleCaught(this.current.key ?? this.current.dex);
        this.syncCatchButton();
      }
    });

    this.refs.prev.addEventListener("click", () => this.step(-1));
    this.refs.next.addEventListener("click", () => this.step(1));
    document.addEventListener("keydown", (event) => {
      if (overlay.hidden) return;
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        this.step(-1);
      } else if (event.key === "ArrowRight") {
        event.preventDefault();
        this.step(1);
      }
    });

    return overlay;
  },

  /* Walk to the neighbouring dex entry without closing the popup. */
  step(delta) {
    if (!this.entries || !this.current) return;
    const index = this.entries.indexOf(this.current);
    if (index === -1) return;
    const target = this.entries[index + delta];
    if (target) this.show(target, this.game);
  },

  syncNav() {
    if (!this.entries || !this.current) return;
    const index = this.entries.indexOf(this.current);
    this.refs.prev.disabled = index <= 0;
    this.refs.next.disabled = index < 0 || index >= this.entries.length - 1;
    const before = this.entries[index - 1];
    const after = this.entries[index + 1];
    this.refs.prev.title = before ? `#${padDex(before.dex)} ${before.name}` : "";
    this.refs.next.title = after ? `#${padDex(after.dex)} ${after.name}` : "";
  },

  syncCatchButton() {
    if (!this.current || !this.isCaught) return;
    const caught = this.isCaught(this.current.key ?? this.current.dex);
    this.refs.catch.textContent = caught ? "✓ Caught" : "Mark as caught";
    this.refs.catch.className = caught ? "btn ghost" : "btn gold";
  },

  show(entry, game) {
    this.ensure();
    this.current = entry;
    this.game = game;
    const r = this.refs;

    Assets.bind(r.sprite, entry.sprite);
    r.sprite.alt = entry.name;
    r.dexno.textContent = `Johto #${padDex(entry.dex)}  ·  National #${padDex(entry.natdex)}`;
    r.name.textContent = entry.name;
    r.where.textContent = `Where to find in ${game.shortName}`;
    r.ext.href = entry.externalUrl;

    r.types.replaceChildren(
      ...entry.types.map((t) => el("span", "type", t))
    );

    r.content.replaceChildren(...buildLocationContent(entry, game));
    r.content.scrollTop = 0;
    this.syncCatchButton();
    this.syncNav();

    this.node.hidden = false;
    r.close.focus();
  },

  hide() {
    if (this.node) this.node.hidden = true;
    this.current = null;
  },
};

/* Body of the popup: availability warnings first, then every location, then
   the evolution/breeding/source notes. */
function buildLocationContent(entry, game) {
  const parts = [];

  /* Said once at the top rather than repeated as "unknown" in every popup. */
  if (game.coverage) {
    const note = el("div", game.coverage.level === "none" ? "note bad" : "note warn");
    note.append(
      el("span", "tag", game.coverage.level === "none" ? "No data" : "Limited"),
      el("span", null, game.coverage.message)
    );
    parts.push(note);
  }

  if (entry.unobtainable) {
    const note = el("div", "note bad");
    note.append(
      el("span", "tag", "Cannot"),
      el(
        "span",
        null,
        `Not obtainable in ${game.shortName} or ${game.pairedName}. Event distribution only.`
      )
    );
    parts.push(note);
  } else if (entry.exclusiveTo && entry.exclusiveTo !== game.id) {
    const note = el("div", "note bad");
    note.append(
      el("span", "tag", "Trade"),
      el(
        "span",
        null,
        `Version exclusive to ${game.pairedName}. Trade it across to fill this slot.`
      )
    );
    parts.push(note);
  } else if (entry.exclusiveTo === game.id) {
    const note = el("div", "note warn");
    note.append(
      el("span", "tag", "Exclusive"),
      el("span", null, `Only found in ${game.shortName} — catch it here.`)
    );
    parts.push(note);
  }

  if (entry.tradeEvolution) {
    const t = entry.tradeEvolution;
    const note = el("div", "note link");
    const detail = t.heldItem
      ? `Evolves only when ${t.from} is traded while holding a ${t.heldItem}.`
      : `Evolves only when ${t.from} is traded.`;
    note.append(
      el("span", "tag", "Link"),
      el(
        "span",
        null,
        entry.needsTradePartner
          ? `${detail} You will need a trade partner — it cannot be done solo.`
          : `${detail} It can also be caught in the wild, see below.`
      )
    );
    parts.push(note);
  }

  if (entry.locationsDisputed && entry.locationClaims) {
    const note = el("div", "note dispute");
    const body = el("div");
    body.append(
      el("div", null, "Sources disagree on whether this can be caught here:")
    );
    for (const [source, claim] of Object.entries(entry.locationClaims)) {
      body.append(el("div", null, `· ${source}: ${claim}`));
    }
    if (entry.locationDisputeReason) {
      body.append(el("div", "why", entry.locationDisputeReason));
    }
    note.append(el("span", "tag", "⚠"), body);
    parts.push(note);
  }

  if (entry.disputed && entry.claims) {
    const note = el("div", "note dispute");
    const body = el("div");
    body.append(el("div", null, "Sources disagree on version exclusivity:"));
    for (const [source, claim] of Object.entries(entry.claims)) {
      body.append(el("div", null, `· ${source}: ${claim}`));
    }
    note.append(el("span", "tag", "⚠"), body);
    parts.push(note);
  }

  if (entry.locations.length) {
    for (const loc of entry.locations) {
      const row = el("div", "locrow");
      row.append(el("div", "area", loc.area));
      for (const v of loc.variants) {
        const line = el("div", "variant");
        /* Method, level and conditions share a column that wraps freely; the
           rate sits in its own column so a wrapped line can never end up
           orphaned and right-justified on its own row. */
        const detail = el("span", "vdetail");
        detail.append(el("span", "m", v.methodLabel));
        /* Some sources publish a place but no levels — Legends Z-A's Wild
           Zones, for instance. Show what exists rather than "Lv null". */
        if (v.minLevel != null) {
          detail.append(
            el(
              "span",
              "lv",
              v.minLevel === v.maxLevel
                ? `Lv ${v.minLevel}`
                : `Lv ${v.minLevel}–${v.maxLevel}`
            )
          );
        }
        for (const c of v.conditions) {
          detail.append(el("span", c.minor ? "chip minor" : "chip", c.label));
        }
        line.append(detail);
        if (v.chance) line.append(el("span", "rate", `${v.chance}%`));
        row.append(line);
      }
      parts.push(row);
    }
  } else if (!entry.notes.length) {
    parts.push(el("div", "empty-state", "No location data available."));
  }

  for (const note of entry.notes) {
    if (note.kind === "unobtainable") continue; /* already shown above */
    /* The trade-evolution banner above already says this, in more detail. */
    if (note.kind === "evolution" && entry.tradeEvolution &&
        note.text.startsWith("Trade ")) continue;
    const node = el("div", "note");
    node.append(el("span", "tag", note.source), el("span", null, note.text));
    parts.push(node);
  }

  return parts;
}
