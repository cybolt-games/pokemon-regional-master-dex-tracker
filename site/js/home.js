/* Pokémon HOME aggregate view.
 *
 * The goal is one of every Pokémon from each regional dex, caught in its OWN
 * region. So this renders every region's dex in sequence as boxes of 30
 * labelled "Kanto 1-30", "Kanto 31-60", and so on, and a slot is filled only
 * by a catch made in a game of that region — a Johto catch fills a Johto box,
 * never the Kanto one, even when the same species appears in both dexes.
 *
 * Read-only by design: it never holds caught state of its own, it reads the
 * same collection the per-game pages write.
 *
 * Several regions have more than one dex and they disagree on size and order
 * (Kanto alone has four). Which one is "the" Kanto dex is a preference, not a
 * fact, so the default is whichever variant you have the most of, and the
 * choice is overridable per region.
 */

(async function () {
  const mount = document.getElementById("regions");

  /* Probe and download concurrently — see boxes.js. */
  const [, data] = await Promise.all([
    Assets.probe(),
    fetch(`${ROOT}data/home.json`).then((r) => r.json()).catch(() => null),
  ]);
  if (!data) {
    mount.textContent = "Could not load data/home.json";
    return;
  }

  const perBox = data.perBox || 30;

  /* --------------------------------------------- caught, scoped by region */

  /* Species caught, per game. Kept per game rather than pooled, because a
     species only fills a region's slot when it was caught in that region. */
  const caughtByGame = new Map();
  const add = (gameId, species) => {
    if (!caughtByGame.has(gameId)) caughtByGame.set(gameId, new Set());
    caughtByGame.get(gameId).add(species);
  };

  let fromServer = false;
  try {
    const rows = (await fetch(`${ROOT}api/collection`, {cache: "no-store"})
      .then((r) => (r.ok ? r.json() : null)))?.rows || [];
    for (const row of rows) {
      if (String(row.caught) === "1") add(row.game, row.species);
    }
    fromServer = true;
  } catch (err) {
    /* No server — fall back to whatever the browser mirrors. */
  }

  if (!fromServer || !caughtByGame.size) {
    const browserKeys = new Map();
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (!key.startsWith("rdb:caught:")) continue;
      try {
        browserKeys.set(key.slice("rdb:caught:".length),
                        new Set(JSON.parse(localStorage.getItem(key))));
      } catch (err) {
        /* skip a malformed entry */
      }
    }
    /* Browser keys store dexKey:number, so the region data maps them back to
       species names. */
    for (const region of data.regions) {
      for (const variant of region.variants) {
        for (const game of variant.games) {
          const set = browserKeys.get(game.id);
          if (!set) continue;
          for (const dex of variant.dexes) {
            for (const entry of dex.entries) {
              if (set.has(`${dex.key}:${entry.dex}`)) add(game.id, entry.slug);
            }
          }
        }
      }
    }
  }

  /* Everything caught in a game belonging to this region. Any of the region's
     games counts — catching Pidgey in Gold or in HeartGold both make it a
     Johto catch — but a catch from another region never does. */
  const heldByRegion = new Map();
  for (const region of data.regions) {
    const held = new Set();
    for (const variant of region.variants) {
      for (const game of variant.games) {
        for (const species of caughtByGame.get(game.id) || []) held.add(species);
      }
    }
    heldByRegion.set(region.key, held);
  }

  /* ---------------------------------------------------------- variants */

  const PREF_KEY = "rdb:home:variants";
  let prefs = {};
  try {
    prefs = JSON.parse(localStorage.getItem(PREF_KEY) || "{}");
  } catch (err) {
    prefs = {};
  }

  function heldIn(region, variant) {
    const held = heldByRegion.get(region.key) || new Set();
    let n = 0;
    for (const dex of variant.dexes) {
      for (const entry of dex.entries) if (held.has(entry.slug)) n++;
    }
    return n;
  }

  /* Default to the variant you have the most of, so the view follows what you
     have actually been filling rather than an arbitrary pick. */
  function chosen(region) {
    const saved = region.variants.find((v) => v.key === prefs[region.key]);
    if (saved) return saved;
    let best = region.variants[0];
    let bestCount = -1;
    for (const variant of region.variants) {
      const count = heldIn(region, variant);
      if (count > bestCount) {
        best = variant;
        bestCount = count;
      }
    }
    return best;
  }

  /* ---------------------------------------------------------- rendering */

  function render() {
    const frag = document.createDocumentFragment();
    let grandTotal = 0;
    let grandHeld = 0;

    for (const region of data.regions) {
      const variant = chosen(region);
      const held = heldByRegion.get(region.key) || new Set();
      const entries = variant.dexes.flatMap((d) => d.entries);
      const count = entries.filter((e) => held.has(e.slug)).length;
      grandTotal += entries.length;
      grandHeld += count;

      const heading = el("h2", "dex-heading");
      heading.append(
        el("span", null, region.name),
        el("span", "count",
           `${variant.label} · ${count}/${entries.length} · ` +
           `${Math.ceil(entries.length / perBox)} boxes`)
      );
      frag.append(heading);

      const grid = el("div", "boxgrid");
      for (let start = 0; start < entries.length; start += perBox) {
        const chunk = entries.slice(start, start + perBox);
        const box = el("section", "box");
        const head = el("header");
        const done = chunk.filter((e) => held.has(e.slug)).length;
        head.append(
          el("span", "label", `${region.name} ${start + 1}-${start + chunk.length}`),
          el("span", "prog", `${done}/${chunk.length}`)
        );
        box.append(head);

        const cells = el("div", "cells");
        cells.style.setProperty("--cols", 6);
        for (let slot = 0; slot < perBox; slot++) {
          const entry = chunk[slot];
          if (!entry) {
            cells.append(el("div", "cell empty"));
            continue;
          }
          const cell = el("div", "cell readonly");
          if (held.has(entry.slug)) cell.classList.add("caught");
          const chead = el("div", "chead");
          chead.append(el("span", "num", padDex(start + slot + 1)));
          const img = assetImg(entry.sprite, entry.name);
          img.loading = "lazy";
          cell.append(chead, img, el("div", "nm", entry.name));
          cell.title = `${entry.name} — ${region.name} #${start + slot + 1}`;
          cells.append(cell);
        }
        box.append(cells);
        grid.append(box);
      }
      frag.append(grid);
    }

    mount.replaceChildren(frag);

    const pct = grandTotal ? (grandHeld / grandTotal) * 100 : 0;
    document.getElementById("pct").textContent = `${pct.toFixed(1)}%`;
    document.getElementById("bar").style.width = `${pct}%`;
    document.getElementById("stat-held").textContent = `${grandHeld} / ${grandTotal}`;
    document.getElementById("stat-remaining").textContent =
      String(grandTotal - grandHeld);
    document.getElementById("stat-regions").textContent =
      String(data.regions.length);
  }

  /* ---------------------------------------------------------- settings */

  function renderSettings() {
    const box = document.getElementById("variant-settings");
    const frag = document.createDocumentFragment();

    for (const region of data.regions) {
      if (region.variants.length < 2) continue;
      const active = chosen(region);
      const row = el("div", "variant-row");
      row.append(el("div", "variant-region", region.name));

      const options = el("div", "variant-options");
      for (const variant of region.variants) {
        const label = el("label", "variant-opt");
        const input = el("input");
        input.type = "radio";
        input.name = `variant-${region.key}`;
        input.checked = variant.key === active.key;
        input.addEventListener("change", () => {
          prefs[region.key] = variant.key;
          try {
            localStorage.setItem(PREF_KEY, JSON.stringify(prefs));
          } catch (err) {
            /* preference just won't persist */
          }
          render();
          renderSettings();
        });
        label.append(input, el("span", null,
          `${variant.label} (${variant.size})`));
        options.append(label);
      }
      row.append(options);
      frag.append(row);
    }

    const reset = el("button", "btn tiny");
    reset.type = "button";
    reset.textContent = "Use whichever I have most of";
    reset.addEventListener("click", () => {
      prefs = {};
      try {
        localStorage.removeItem(PREF_KEY);
      } catch (err) {
        /* nothing to clear */
      }
      render();
      renderSettings();
    });
    frag.append(reset);

    box.replaceChildren(frag);
  }

  render();
  renderSettings();
})();
