/* Box layout page.
 *
 * A game can carry several regional dexes — Kalos is split in three, Galar and
 * Paldea each add DLC dexes — so each dex gets its own run of boxes and its
 * own heading. Dex numbers repeat across dexes, so caught state is keyed by
 * "dexKey:number", never by number alone.
 *
 * Box presentation follows the game, not a house style:
 *   grid    a cols x rows PC grid (Gen 3 onward)
 *   list    Gen 1/2, where storage is a scrolling name list, not a grid
 *   single  Let's Go, one continuous 1,000-slot box
 *   pasture Legends Arceus, same capacity but pens rather than slots
 */

(async function () {
  const gameId = document.body.dataset.game;
  const mount = document.getElementById("boxes");

  /* The CDN probe and the dataset download are independent, so they overlap.
     Awaiting the probe first meant that off-network every page paid the full
     probe timeout before the data even started downloading. */
  const [, game] = await Promise.all([
    Assets.probe(),
    loadGame(gameId).catch((err) => {
      mount.textContent = err.message;
      return null;
    }),
  ]);
  if (!game) return;

  const layout = game.boxLayout;
  const style = layout.style || "grid";
  const perBox = layout.perBox;
  const cols = style === "grid" || style === "pasture" ? layout.cols || 6 : 1;
  const noun = layout.boxNoun || "Box";

  const allEntries = game.dexes.flatMap((d) =>
    d.entries.map((e) => ({ ...e, dexKey: d.key, key: `${d.key}:${e.dex}` }))
  );
  const byKey = new Map(allEntries.map((e) => [e.key, e]));
  const cellByKey = new Map();

  const caught = await Collection.load(gameId, game.dexes);

  /* Tap-to-catch mode. Off: tap opens the popup, long-press marks caught.
     On: those swap, so a whole box can be ticked off with single taps. */
  const TAP_KEY = (Collection.demo ? "rdb:demo:tapmode:" : "rdb:tapmode:") + gameId;
  let tapMode = false;
  try {
    tapMode = localStorage.getItem(TAP_KEY) === "1";
  } catch (err) {
    /* Storage unavailable — default to off. */
  }

  document.title = `Box layouts · ${game.game.name}`;
  document.getElementById("game-name").textContent = game.game.name;
  document.getElementById("game-sub").textContent =
    game.dexes.map((d) => `${d.name} · ${d.size} entries`).join("  ·  ") +
    `  ·  ${perBox} per ${noun.toLowerCase()}`;

  Modal.onToggleCaught = (key) => toggle(key);
  Modal.isCaught = (key) => caught.has(key);
  Modal.entries = allEntries;

  /* ---------------------------------------------------------- rendering */

  function applyState(entry) {
    const cell = cellByKey.get(entry.key);
    if (cell) cell.classList.toggle("caught", caught.has(entry.key));
  }

  function toggle(key) {
    if (caught.has(key)) caught.delete(key);
    else caught.add(key);
    Collection.save(caught);
    const entry = byKey.get(key);
    if (entry) applyState(entry);
    renderStats();
  }

  function buildCell(entry) {
    const cell = el("div", "cell");
    cell.tabIndex = 0;
    cell.dataset.key = entry.key;

    const blocked =
      entry.unobtainable || (entry.exclusiveTo && entry.exclusiveTo !== gameId);
    if (blocked) cell.classList.add("blocked");
    else if (entry.tradeEvolution) cell.classList.add("tradeevo");

    const head = el("div", "chead");
    head.append(el("span", "num", padDex(entry.dex)));
    const flags = el("span", "flags");
    if (entry.unobtainable) flags.append(el("span", "flag never", "EVENT"));
    else if (entry.exclusiveTo && entry.exclusiveTo !== gameId)
      flags.append(el("span", "flag trade", "TRADE"));
    else if (entry.tradeEvolution) flags.append(el("span", "flag tradeevo", "LINK"));
    if (entry.disputed || entry.locationsDisputed)
      flags.append(el("span", "flag dispute", "!"));
    head.append(flags);

    const img = assetImg(entry.sprite, entry.name);
    img.loading = "lazy";
    img.width = 80;
    img.height = 80;

    cell.append(head, img, el("div", "nm", entry.name));

    const title = [entry.name];
    if (entry.unobtainable) title.push("event only");
    else if (blocked) title.push("not catchable in this version");
    else if (entry.needsTradePartner) title.push("needs a trade partner");
    else if (entry.tradeEvolution) title.push("evolves by trading");
    if (entry.disputed || entry.locationsDisputed) title.push("sources disagree");
    cell.title = title.join(" — ");

    const primary = () => (tapMode ? toggle(entry.key) : Modal.show(entry, game.game));
    const secondary = () => (tapMode ? Modal.show(entry, game.game) : toggle(entry.key));

    cell.addEventListener("click", primary);
    cell.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        primary();
      }
    });
    cell.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      secondary();
    });

    let timer = null;
    let longPressed = false;
    cell.addEventListener("touchstart", () => {
      longPressed = false;
      timer = setTimeout(() => {
        timer = null;
        longPressed = true;
        secondary();
        if (navigator.vibrate) navigator.vibrate(18);
      }, 450);
    }, { passive: true });
    const cancel = () => {
      if (timer) clearTimeout(timer);
      timer = null;
    };
    cell.addEventListener("touchend", (event) => {
      cancel();
      if (longPressed) {
        event.preventDefault();
        longPressed = false;
      }
    });
    cell.addEventListener("touchmove", cancel, { passive: true });

    cellByKey.set(entry.key, cell);
    return cell;
  }

  const boxNodes = [];
  const frag = document.createDocumentFragment();

  for (const dex of game.dexes) {
    if (game.dexes.length > 1) {
      const heading = el("h2", "dex-heading");
      heading.append(
        el("span", null, dex.name),
        el("span", "count",
           `${dex.size} entries · ${dex.boxes.length} ${noun.toLowerCase()}${noun === "Box" ? "es" : "s"}`)
      );
      if (dex.sizeDisputed) {
        const warn = el("span", "flag dispute", "!");
        warn.title =
          "Sources disagree on this dex's size: " +
          Object.entries(dex.sizeDisputed)
            .map(([k, v]) => `${k} says ${v}`)
            .join(", ") + ". Shipping PokéAPI's ordering.";
        heading.append(warn);
      }
      frag.append(heading);
    }

    const grid = el("div", "boxgrid");
    for (const box of dex.boxes) {
      const node = el("section", "box");
      const head = el("header");
      const markAll = el("button", "boxmark");
      markAll.type = "button";
      head.append(
        el("span", "label", box.label),
        el("span", "idx", `${noun} ${box.index}`),
        markAll,
        el("span", "prog")
      );
      node.append(head);

      const cells = el("div", "cells" + (style === "grid" || style === "pasture"
        ? "" : " " + style));
      cells.style.setProperty("--cols", cols);

      const slots = style === "single" ? box.count : perBox;
      for (let slot = 0; slot < slots; slot++) {
        const dexNo = box.from + slot;
        const entry = dexNo <= box.to ? byKey.get(`${dex.key}:${dexNo}`) : null;
        cells.append(entry ? buildCell(entry) : el("div", "cell empty"));
      }
      node.append(cells);
      grid.append(node);
      boxNodes.push({ dex, box, progress: head.querySelector(".prog"), markAll });

      markAll.addEventListener("click", () => {
        const keys = [];
        for (let n = box.from; n <= box.to; n++) keys.push(`${dex.key}:${n}`);
        const everyCaught = keys.every((k) => caught.has(k));
        for (const key of keys) {
          if (everyCaught) caught.delete(key);
          else caught.add(key);
          const entry = byKey.get(key);
          if (entry) applyState(entry);
        }
        Collection.save(caught);
        renderStats();
      });
    }
    frag.append(grid);
  }
  mount.append(frag);

  /* ------------------------------------------------------------- stats */

  const total = allEntries.length;
  const blockedCount = allEntries.filter(
    (e) => e.unobtainable || (e.exclusiveTo && e.exclusiveTo !== gameId)
  ).length;

  const pctNode = document.getElementById("pct");
  const barNode = document.getElementById("bar");
  const caughtNode = document.getElementById("stat-caught");
  const remainNode = document.getElementById("stat-remaining");
  const blockedNode = document.getElementById("stat-blocked");
  const linkNode = document.getElementById("stat-link");

  function renderStats() {
    const n = allEntries.filter((e) => caught.has(e.key)).length;
    const pct = total ? (n / total) * 100 : 0;
    pctNode.textContent = `${pct.toFixed(1)}%`;
    barNode.style.width = `${pct}%`;
    caughtNode.textContent = `${n} / ${total}`;
    remainNode.textContent = String(total - n);
    blockedNode.textContent = String(
      allEntries.filter(
        (e) => !caught.has(e.key) &&
          (e.unobtainable || (e.exclusiveTo && e.exclusiveTo !== gameId))
      ).length
    );
    linkNode.textContent = String(
      allEntries.filter((e) => !caught.has(e.key) && e.needsTradePartner).length
    );

    for (const { dex, box, progress, markAll } of boxNodes) {
      let done = 0;
      for (let n2 = box.from; n2 <= box.to; n2++) {
        if (caught.has(`${dex.key}:${n2}`)) done++;
      }
      progress.textContent = `${done}/${box.count}`;
      const full = done === box.count;
      markAll.textContent = full
        ? `Clear ${noun.toLowerCase()}`
        : `Mark ${noun.toLowerCase()} caught`;
      markAll.classList.toggle("on", full);
    }
  }

  blockedNode.title =
    `${blockedCount} of the ${total} entries cannot be caught in ` +
    `${game.game.shortName} — they need a trade or an event.`;
  linkNode.title =
    "Trade evolutions with no other way to get them in this version — " +
    "they need a second player, not just the paired cartridge.";

  /* --------------------------------------------------- tap-mode toggle */

  const tapToggle = document.getElementById("tapmode");
  const tapHint = document.getElementById("tapmode-hint");

  function renderTapMode() {
    tapToggle.checked = tapMode;
    tapToggle.setAttribute("aria-checked", String(tapMode));
    document.body.classList.toggle("tapmode", tapMode);
    tapHint.textContent = tapMode
      ? "Tap marks a Pokémon caught, tap again to clear it. Long-press (or right-click) opens its details."
      : "Tap a Pokémon to see exactly where to find it. Long-press (or right-click) marks it caught.";
  }

  tapToggle.addEventListener("change", () => {
    tapMode = tapToggle.checked;
    try {
      localStorage.setItem(TAP_KEY, tapMode ? "1" : "0");
    } catch (err) {
      /* Not fatal — the mode just won't persist. */
    }
    renderTapMode();
  });

  /* ------------------------------------------------ export / import CSV */

  Collection.mount(document.getElementById("savestate"), caught);

  document.getElementById("export-csv").addEventListener("click", () => {
    const blob = new Blob([Collection.toCsv(caught)], {type: "text/csv"});
    const url = URL.createObjectURL(blob);
    const link = el("a");
    link.href = url;
    link.download = `${gameId}-collection.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });

  const importInput = document.getElementById("import-csv");
  document.getElementById("import-btn").addEventListener("click",
    () => importInput.click());
  importInput.addEventListener("change", async () => {
    const file = importInput.files && importInput.files[0];
    if (!file) return;
    const incoming = Collection.fromCsv(await file.text());
    /* Import only ever adds. Nothing is unmarked by loading a file. */
    for (const key of incoming) caught.add(key);
    Collection.save(caught);
    for (const entry of allEntries) applyState(entry);
    renderStats();
    importInput.value = "";
  });

  renderTapMode();
  for (const entry of allEntries) applyState(entry);
  renderStats();

  /* ?open=<species|dex number> deep-links straight to one Pokémon's details,
     so a particular entry can be linked to or bookmarked. */
  const open = new URLSearchParams(location.search).get("open");
  if (open) {
    const wanted = open.toLowerCase();
    const target = allEntries.find(
      (e) => e.slug === wanted || String(e.dex) === wanted || e.key === wanted
    );
    if (target) Modal.show(target, game.game);
  }
})();
