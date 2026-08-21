/* Where images come from — driven entirely by config.json.
 *
 * The default profile is "local": every file is served from this repo, no
 * external host is contacted, and the app works with no internet at all.
 * Other profiles can put a self-hosted CDN in front, or fall back to a public
 * mirror, without any code change. See config.json for the profile list.
 *
 * A CDN behind a private CA or a LAN-only name fails *slowly* from outside the
 * network, so when one is configured a single probe up front decides whether
 * to use it at all — rather than letting several hundred images each discover
 * the problem on their own. Per-image onerror still walks the chain after that.
 */

const ROOT = document.body.dataset.root || "";

const Assets = {
  config: null,
  tiers: [],
  start: 0,

  /* Resolve a logical path like "sprites/hgss/152.png" for one tier. */
  _resolve(path, tier) {
    const cfg = this.config;
    switch (tier) {
      case "local":
        return ROOT + (cfg.localBase || "assets/") + path;

      case "cdn": {
        const base = cfg.cdn && cfg.cdn.baseUrl;
        return base ? base + path : null;
      }

      case "public": {
        const pub = cfg.public || {};
        const sprite = path.match(/^(sprites\/[^/]+)\/(\d+)\.png$/);
        if (sprite && pub.sprites) {
          const set = (cfg.spriteSets || {})[sprite[1]];
          if (!set) return null;
          return pub.sprites.replace("{set}", set).replace("{id}", sprite[2]);
        }
        const box = path.match(/^boxart\/([a-z0-9-]+)\.jpg$/);
        if (box && pub.boxart) return pub.boxart.replace("{game}", box[1]);
        return null;
      }

      default:
        return null;
    }
  },

  url(path, startAt) {
    for (let i = startAt ?? this.start; i < this.tiers.length; i++) {
      const url = this._resolve(path, this.tiers[i]);
      if (url) return url;
    }
    return this._resolve(path, "local");
  },

  /* Attach the whole fallback chain to an <img>. */
  bind(img, path) {
    let tier = this.start;
    const next = () => {
      while (tier < this.tiers.length) {
        const url = this._resolve(path, this.tiers[tier]);
        tier += 1;
        if (url) return url;
      }
      return null;
    };
    img.addEventListener("error", () => {
      const url = next();
      if (url) img.src = url;
    });
    const first = next();
    if (first) img.src = first;
    return img;
  },

  async load() {
    if (this.config) return this.config;
    const response = await fetch(ROOT + "config.json");
    if (!response.ok) throw new Error("could not load config.json");
    this.config = await response.json();
    this.tiers = this.config.tiers || ["local"];
    this.start = 0;
    return this.config;
  },

  /* Decide once whether the CDN tier is usable, and remember it. */
  async probe() {
    await this.load();
    const index = this.tiers.indexOf("cdn");
    if (index === -1) return "n/a"; /* no CDN configured — nothing to probe */

    const cdn = this.config.cdn || {};
    if (!cdn.baseUrl) {
      this.start = index + 1;
      return "unconfigured";
    }

    const key = "rdb:cdn:" + cdn.baseUrl;
    let cached = null;
    try {
      cached = sessionStorage.getItem(key);
    } catch (err) {
      /* Storage blocked — just probe again. */
    }
    if (cached === "up") return "up";
    if (cached === "down") {
      this.start = index + 1;
      return "down";
    }

    const timeout = cdn.probeTimeoutMs || 2500;
    const probePath = cdn.probePath || "";
    const ok = await new Promise((resolve) => {
      const img = new Image();
      const timer = setTimeout(() => {
        img.src = "";
        resolve(false);
      }, timeout);
      img.onload = () => {
        clearTimeout(timer);
        resolve(true);
      };
      img.onerror = () => {
        clearTimeout(timer);
        resolve(false);
      };
      img.src = cdn.baseUrl + probePath + "?probe=" + Date.now();
    });

    if (!ok) this.start = index + 1;
    try {
      sessionStorage.setItem(key, ok ? "up" : "down");
    } catch (err) {
      /* Not fatal. */
    }
    return ok ? "up" : "down";
  },
};
