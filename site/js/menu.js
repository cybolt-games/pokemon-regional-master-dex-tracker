/* Game menu, rendered from the registry in config.json.
 * Adding a game to games.json puts a tile here — no markup to maintain. */

(async function () {
  const cfg = await Assets.load();
  await Assets.probe();

  const mount = document.getElementById("menu");
  const games = cfg.games || [];

  const ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"];

  /* Group by generation, then by region, preserving registry order. */
  const byGen = new Map();
  for (const game of games) {
    if (!byGen.has(game.generation)) byGen.set(game.generation, new Map());
    const regions = byGen.get(game.generation);
    if (!regions.has(game.region)) regions.set(game.region, []);
    regions.get(game.region).push(game);
  }

  const frag = document.createDocumentFragment();

  for (const [gen, regions] of [...byGen.entries()].sort((a, b) => a[0] - b[0])) {
    for (const [region, list] of regions) {
      const label = el("div", "gen-label");
      label.textContent = `Generation ${ROMAN[gen] || gen} — ${region}`;
      frag.append(label);

      const tiles = el("div", "tiles");
      for (const game of list) {
        const live = game.status === "live";
        const tile = el(live ? "a" : "span", "tile" + (live ? "" : " soon"));
        if (live) tile.href = `game/${game.id}.html`;
        if (game.accent) tile.classList.add(game.accent);

        if (game.boxart) {
          const art = el("img", "art");
          art.alt = `${game.name} box art`;
          art.loading = "lazy";
          Assets.bind(art, game.boxart);
          tile.append(art);
        }

        tile.append(el("div", "name", game.name));

        const bits = [];
        if (game.dexName) bits.push(game.dexName);
        if (game.dexSize) bits.push(`${game.dexSize} entries`);
        if (game.boxes && game.boxes.style === "grid") {
          bits.push(`${Math.ceil(game.dexSize / game.boxes.perBox)} boxes`);
        }
        tile.append(el("div", "meta", bits.join(" · ")));

        if (!live) tile.append(el("div", "badge", "Coming soon"));
        tiles.append(tile);
      }
      frag.append(tiles);
    }
  }

  mount.replaceChildren(frag);

  /* Any static tile in the page (the HOME entry point) still needs binding
     through the same fallback chain as the generated ones. */
  for (const img of document.querySelectorAll("img[data-asset]")) {
    Assets.bind(img, img.dataset.asset);
  }

  const live = games.filter((g) => g.status === "live").length;
  const note = document.getElementById("menu-note");
  if (note) {
    note.textContent = games.length
      ? `${live} of ${games.length} games built out so far.`
      : "";
  }
})();
