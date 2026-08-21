/* Game landing page: walkthrough + box links, and the version-exclusive split. */

(async function () {
  const gameId = document.body.dataset.game;
  /* Probe and download concurrently — see boxes.js. */
  const [, game] = await Promise.all([
    Assets.probe(),
    loadGame(gameId).catch((err) => {
      document.getElementById("exclusives").textContent = err.message;
      return null;
    }),
  ]);
  if (!game) return;

  const meta = game.game;
  document.title = `${meta.name} · Regional Dex Buddy`;
  document.getElementById("game-name").textContent = meta.name;
  document.getElementById("game-sub").textContent =
    game.dexes.map((d) => `${d.name} · ${d.size}`).join("  ·  ") +
    `  ·  Generation ${meta.generation}`;

  document.getElementById("link-walkthrough").href = meta.walkthroughUrl;
  document.getElementById("link-boxes").href = `${ROOT}boxes/${meta.id}.html`;
  document.getElementById("link-national").href = meta.nationalExclusivesUrl;

  const allEntries = game.dexes.flatMap((d) =>
    d.entries.map((e) => ({ ...e, dexKey: d.key, key: `${d.key}:${e.dex}` }))
  );
  const byDex = new Map(allEntries.map((e) => [e.dex, e]));
  Modal.entries = allEntries;

  function monTile(entry) {
    const node = el("div", "mon");
    node.tabIndex = 0;
    const img = assetImg(entry.sprite, entry.name);
    img.loading = "lazy";
    node.append(
      img,
      el("div", "nm", entry.name),
      el("div", "n", `#${padDex(entry.dex)}`)
    );
    node.addEventListener("click", () => Modal.show(entry, meta));
    node.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        Modal.show(entry, meta);
      }
    });
    return node;
  }

  function fill(listId, countId, dexNumbers) {
    const list = document.getElementById(listId);
    document.getElementById(countId).textContent = `${dexNumbers.length} Pokémon`;
    list.replaceChildren(
      ...dexNumbers.map((dex) => monTile(byDex.get(dex)))
    );
  }

  fill("list-attainable", "count-attainable", game.exclusives.attainable);
  fill("list-trade", "count-trade", game.exclusives.tradeOnly);

  document.getElementById("head-attainable").textContent =
    `Catch these in ${meta.shortName}`;
  document.getElementById("head-trade").textContent =
    `Trade these from ${meta.pairedName}`;
  document.getElementById("lead-attainable").textContent =
    `Version exclusives you can find yourself. They do not appear in ${meta.pairedName}.`;
  document.getElementById("lead-trade").textContent =
    `Exclusive to ${meta.pairedName}. Nothing you do in ${meta.shortName} will produce ` +
    `them — the ${meta.dexName} needs them traded across.`;

  /* Trade evolutions need a second player, which no amount of solo play fixes.
     Worth its own list so it can be planned for. */
  const tradeEvos = game.exclusives.tradeEvolutions.map((dex) => byDex.get(dex));
  if (tradeEvos.length) {
    document.getElementById("panel-tradeevo").hidden = false;
    document.getElementById("count-tradeevo").textContent =
      `${tradeEvos.length} Pokémon`;
    const unavoidable = tradeEvos.filter((e) => e.needsTradePartner).length;
    document.getElementById("lead-tradeevo").textContent =
      `These only evolve when traded, so they need a trade partner rather than ` +
      `just the paired cartridge. ${unavoidable} of them have no other route in ` +
      `${meta.shortName}; the rest can also be caught in the wild.`;
    document
      .getElementById("list-tradeevo")
      .replaceChildren(...tradeEvos.map(monTile));
  }

  /* Anything unobtainable in both versions is worth calling out separately,
     otherwise it looks like an ordinary gap. */
  const eventOnly = allEntries.filter((e) => e.unobtainable);
  if (eventOnly.length) {
    const panel = document.getElementById("panel-event");
    panel.hidden = false;
    document.getElementById("count-event").textContent =
      `${eventOnly.length} Pokémon`;
    document
      .getElementById("list-event")
      .replaceChildren(...eventOnly.map(monTile));
  }

  const disputed = allEntries.filter((e) => e.disputed || e.locationsDisputed);
  if (disputed.length) {
    const panel = document.getElementById("panel-disputed");
    panel.hidden = false;
    document.getElementById("count-disputed").textContent =
      `${disputed.length} Pokémon`;
    document
      .getElementById("list-disputed")
      .replaceChildren(...disputed.map(monTile));
  }
})();
