/* The pirate attack: a continuous Krillion-style pixel world driven by Elo.
 *
 * One world, 300..2700 Elo mapped onto 1280 logical px (300 per phase):
 *   1 dark ocean  2 open water  3 the beach  4 the fields
 *   5 the town    6 the walls   7 the courtyard 8 the riches
 *
 * The background is baked ONCE into an offscreen buffer, column by column:
 * biome colors blend smoothly along x (no straight edges — the shoreline
 * wiggles, sand dithers into grass), the sea has a vertical gradient
 * (light surface, deep bottom), and static props (palm, trees, houses,
 * castle, gold) are baked too. Every frame we blit the visible slice and
 * draw the living layers on top: wave crests mixing two blues, foam
 * washing the shore, bubbles rising, drifting clouds, the sun, growing
 * grass tufts, torch flames, banners, and the ship/crew sprites.
 * The camera clamps at the world's end, so at max Elo nothing moves.
 */
(function () {
  "use strict";

  const VIEW_W = 200, VIEW_H = 60;
  const WORLD_W = 1280, WORLD_H = 60;
  const ELO_BASE = 300, ELO_PER_ZONE = 300, ZONES = 8;
  const PX_PER_ELO = WORLD_W / (ELO_PER_ZONE * ZONES);   // 0.533 px per point
  const GROUND = 50, SEA_TOP = 30, SHORE = 350;          // shoreline column

  const c = document.getElementById("pirate-scene");
  if (!c) return;
  const ctx = c.getContext("2d");

  let elo = 800, eloShown = 800, eloTarget = 800, tweenT0 = 0, tweenDur = 0;

  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const smooth = t => { t = clamp(t, 0, 1); return t * t * (3 - 2 * t); };
  const eloToX = e => clamp(e - ELO_BASE, 0, ELO_PER_ZONE * ZONES) * PX_PER_ELO;
  const zoneOf = x => clamp(Math.floor(x / ELO_PER_ZONE / PX_PER_ELO), 0, ZONES - 1);

  /* ---- color helpers: hex -> [r,g,b], mix, per-pixel writer ---- */
  const RGB = hex => [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16),
                      parseInt(hex.slice(5, 7), 16)];
  const mix = (a, b, t) => [
    Math.round(a[0] + (b[0] - a[0]) * t),
    Math.round(a[1] + (b[1] - a[1]) * t),
    Math.round(a[2] + (b[2] - a[2]) * t)];
  const colAt = (x, stops) => {                       // stops: [[x, rgb], ...]
    if (x <= stops[0][0]) return stops[0][1];
    for (let i = 1; i < stops.length; i++) {
      if (x <= stops[i][0]) {
        const t = (x - stops[i - 1][0]) / (stops[i][0] - stops[i - 1][0]);
        return mix(stops[i - 1][1], stops[i][1], smooth(t));
      }
    }
    return stops[stops.length - 1][1];
  };
  const hash = (x, y) => {                            // stable per-pixel noise
    const s = Math.sin(x * 12.9898 + y * 78.233) * 43758.5453;
    return s - Math.floor(s);
  };

  /* ---- live drawing onto the visible canvas ---- */
  const R = (x, y, w, h, color) => { ctx.fillStyle = color; ctx.fillRect(x, y, w, h); };
  function disc(cx, cy, r, color) {
    for (let dy = -r; dy <= r; dy++) {
      const w = Math.floor(Math.sqrt(r * r - dy * dy));
      R(cx - w, cy + dy, w * 2 + 1, 1, color);
    }
  }
  function diag(x, y, n, color, dx, dy) {
    for (let i = 0; i < n; i++) R(x + i * dx, y + i * dy, 1, 1, color);
  }
  function tri(x, y, w, h, color) {
    for (let i = 0; i < h; i++) {
      const inset = Math.floor((h - 1 - i) * w / (2 * h));
      R(x + inset, y + i, w - inset * 2, 1, color);
    }
  }

  /* palettes as color stops along the world */
  const SEA_SURF = [[0, RGB("#1d4a86")], [140, RGB("#2a6db5")], [330, RGB("#57a4e0")]];
  const SEA_DEEP = [[0, RGB("#0a1e3c")], [160, RGB("#123a6e")], [350, RGB("#1d4a86")]];
  const SKY_SEA_TOP = [[0, RGB("#0e1830")], [160, RGB("#16264e")], [350, RGB("#4a7fc0")]];
  const SKY_SEA_BOT = [[0, RGB("#15234a")], [160, RGB("#1f3468")], [350, RGB("#a9d4f2")]];
  const SKY_TOP = [[350, RGB("#4a7fc0")], [480, RGB("#79b7e8")], [640, RGB("#87b7e0")],
                   [800, RGB("#5a4a8a")], [960, RGB("#3a2f5a")], [1120, RGB("#241d33")],
                   [1280, RGB("#1a1526")]];
  const SKY_BOT = [[350, RGB("#a9d4f2")], [480, RGB("#a9d4f2")], [640, RGB("#b8d9f2")],
                   [800, RGB("#7a6ab0")], [960, RGB("#52447c")], [1120, RGB("#3a2f4a")],
                   [1280, RGB("#3a2f4a")]];
  const RGB_SAND = RGB("#d9b36c"), RGB_WET = RGB("#a8813f"),
        RGB_SAND_L = RGB("#e0c185"), RGB_SAND_D = RGB("#c19a52"),
        RGB_GRASS = RGB("#4e8f3a"), RGB_GRASS_D = RGB("#3d7530"),
        RGB_STONE = RGB("#8a7f6e"), RGB_STONE_D = RGB("#756b5c"),
        RGB_WALL = RGB("#6f7480"), RGB_WALL_D = RGB("#5a5f6a"),
        RGB_FLOOR = RGB("#3a2f4a"), RGB_FLOOR_D = RGB("#2e2439"),
        RGB_IVORY = RGB("#241d33"), RGB_IVORY_D = RGB("#1a1526"),
        RGB_GOLD = RGB("#f2c14e"), RGB_GOLD_D = RGB("#d4a017");

  /* ---- the baked world: one offscreen buffer, built once ---- */
  const world = document.createElement("canvas");
  world.width = WORLD_W; world.height = WORLD_H;
  const wctx = world.getContext("2d");
  const WIMG = wctx.createImageData(WORLD_W, WORLD_H);
  const WD = WIMG.data;
  const Wpx = (x, y, rgb) => {
    const i = (y * WORLD_W + x) * 4;
    WD[i] = rgb[0]; WD[i + 1] = rgb[1]; WD[i + 2] = rgb[2]; WD[i + 3] = 255;
  };
  const Wrect = (x, y, w, h, rgb) => {
    for (let yy = y; yy < y + h; yy++)
      for (let xx = x; xx < x + w; xx++)
        if (xx >= 0 && xx < WORLD_W && yy >= 0 && yy < WORLD_H) Wpx(xx, yy, rgb);
  };
  const Wdisc = (cx, cy, r, rgb) => {
    for (let dy = -r; dy <= r; dy++)
      for (let dx = -r; dx <= r; dx++)
        if (dx * dx + dy * dy <= r * r)
          if (cx + dx >= 0 && cx + dx < WORLD_W && cy + dy >= 0 && cy + dy < WORLD_H)
            Wpx(cx + dx, cy + dy, rgb);
  };
  const Wtri = (x, y, w, h, rgb) => {
    for (let i = 0; i < h; i++) {
      const inset = Math.floor((h - 1 - i) * w / (2 * h));
      Wrect(x + inset, y + i, w - inset * 2, 1, rgb);
    }
  };
  const Wdiag = (x, y, n, rgb, dx, dy) => {
    for (let i = 0; i < n; i++) Wpx(x + i * dx, y + i * dy, rgb);
  };

  function bakeWorld() {
    for (let x = 0; x < WORLD_W; x++) {
      const sea = x < SHORE;                           // wet shore to 400
      // sky (or interior wall) above the ground line
      if (!sea && x >= 1120) {
        for (let y = 0; y < GROUND; y++)
          Wpx(x, y, mix(RGB_IVORY, RGB_IVORY_D, y / GROUND));
      } else {
        const top = sea ? colAt(x, SKY_SEA_TOP) : colAt(x, SKY_TOP);
        const bot = sea ? colAt(x, SKY_SEA_BOT) : colAt(x, SKY_BOT);
        for (let y = 0; y < SEA_TOP; y++) Wpx(x, y, mix(top, bot, y / SEA_TOP));
      }
      if (sea) {                                       // sea with depth gradient
        const surf = colAt(x, SEA_SURF), deep = colAt(x, SEA_DEEP);
        for (let y = SEA_TOP; y < WORLD_H; y++) {
          const d = Math.pow((y - SEA_TOP) / (WORLD_H - SEA_TOP), 0.8);
          Wpx(x, y, mix(surf, deep, d));
        }
      } else if (x < SHORE + 12) {                     // defined shoreline: crisp
        const wet = mix(RGB_WET, RGB_SAND, (x - SHORE) / 12);
        for (let y = SEA_TOP; y < WORLD_H; y++) {
          // one lighter row at the water edge reads as the wet line
          Wpx(x, y, y < SEA_TOP + 2 ? mix(RGB("#a8d0f0"), wet, (y - SEA_TOP) / 2) : wet);
        }
      } else if (x < 500) {                            // dry sand with dune shade
        const dune = Math.sin(x / 11) * 0.5 + 0.5;
        for (let y = SEA_TOP; y < WORLD_H; y++) {
          const base = y < SEA_TOP + 6 ? mix(RGB_WET, RGB_SAND, (y - SEA_TOP) / 6)
                                        : mix(RGB_SAND_L, RGB_SAND_D, dune * 0.6);
          Wpx(x, y, base);
        }
      } else if (x < 560) {                            // grass dithers onto sand
        for (let y = SEA_TOP; y < WORLD_H; y++) {
          const t = smooth((x - 500) / 60) + Math.sin(y * 0.6 + x * 0.2) * 0.18;
          Wpx(x, y, hash(x, y) < t ? RGB_GRASS : RGB_SAND);
        }
      } else if (x < 640) {                            // fields
        const speck = hash(x, 7) > 0.7;
        for (let y = SEA_TOP; y < WORLD_H; y++)
          Wpx(x, y, y >= GROUND && speck && (y - GROUND) % 3 === 0 ? RGB_GRASS_D : RGB_GRASS);
      } else if (x < 800) {                            // town stone
        const speck = hash(x, 11) > 0.6;
        for (let y = SEA_TOP; y < WORLD_H; y++)
          Wpx(x, y, y >= GROUND && speck && (y - GROUND) % 4 === 0 ? RGB_STONE_D : RGB_STONE);
      } else if (x < 960) {                            // castle stone
        const speck = hash(x, 13) > 0.6;
        for (let y = SEA_TOP; y < WORLD_H; y++)
          Wpx(x, y, y >= GROUND && speck && (y - GROUND) % 5 === 0 ? RGB_WALL_D : RGB_WALL);
      } else if (x < 1120) {                           // courtyard floor
        const speck = hash(x, 17) > 0.7;
        for (let y = SEA_TOP; y < WORLD_H; y++)
          Wpx(x, y, y >= GROUND && speck && (y - GROUND) % 4 === 0 ? RGB_FLOOR_D : RGB_FLOOR);
      } else {                                         // castle interior
        const speck = hash(x, 23) > 0.75;
        for (let y = 0; y < WORLD_H; y++)
          Wpx(x, y, y >= GROUND ? (speck && (y - GROUND) % 4 === 0 ? RGB_FLOOR_D : RGB_FLOOR)
                                : mix(RGB_IVORY, RGB_IVORY_D, y / GROUND));
      }
    }
    /* ---- static props, baked over the columns ---- */
    // seaweed silhouettes and rocks on the sea floor
    for (const [wx, h] of [[24, 9], [58, 12], [96, 7], [140, 11], [186, 8], [228, 13],
                           [268, 9], [306, 6]]) {
      Wdiag(wx, GROUND + 2, h, "#0d2c52", 1, -1);
      Wdiag(wx + 2, GROUND + 2, h - 4, "#123a5e", 1, -1);
      Wdiag(wx + 4, GROUND + 2, h - 6, "#0d2c52", 1, -1);
    }
    for (const rx of [80, 176, 250]) Wdisc(rx, GROUND + 7, 3, "#123a5e");
    // beach: dunes
    for (const dx of [400, 460, 490]) {
      Wdisc(dx, GROUND + 9, 5, RGB_SAND_D);
      Wrect(dx - 5, GROUND + 2, 10, 2, RGB_SAND_L);
    }
    // palm and trees
    (function palm(wx) {
      Wdiag(wx + 6, GROUND - 2, 9, RGB("#7a5230"), -1, -2);
      Wdiag(wx, GROUND - 20, 6, RGB("#3d7530"), 1, -1);
      Wdiag(wx + 8, GROUND - 20, 6, RGB("#3d7530"), 1, 1);
      Wdiag(wx + 2, GROUND - 22, 5, RGB("#4e8f3a"), 1, 0);
      Wdiag(wx + 6, GROUND - 22, 5, RGB("#4e8f3a"), 1, 1);
      Wdisc(wx + 7, GROUND - 21, 1, RGB("#5a9a45"));
      Wrect(wx + 5, GROUND - 16, 2, 2, RGB("#8a5a2e"));
    })(450);
    for (const tx of [540, 608]) {
      Wrect(tx + 6, GROUND - 14, 3, 14, RGB("#5a3a22"));
      Wdisc(tx + 7, GROUND - 19, 6, RGB("#3d7530"));
      Wdisc(tx + 5, GROUND - 21, 4, RGB("#4e8f3a"));
      Wdisc(tx + 10, GROUND - 20, 3, RGB("#5a9a45"));
    }
    // the town: three houses
    for (const [hx, wall, roof] of [[648, "#c9a06a", "#a04b3a"], [698, "#9a7550", "#8a4a3a"],
                                    [752, "#c9a06a", "#a04b3a"]]) {
      Wrect(hx, GROUND - 18, 30, 18, RGB(wall));
      for (let i = 0; i < 4; i++) Wrect(hx, GROUND - 18 + i * 4, 30, 1, RGB("#3a2f1c"));
      Wtri(hx - 3, GROUND - 30, 36, 12, RGB(roof));
      Wrect(hx + 6, GROUND - 12, 5, 5, RGB("#f2c14e"));
      Wrect(hx + 19, GROUND - 12, 5, 5, RGB("#f2c14e"));
      Wrect(hx + 13, GROUND - 7, 5, 7, RGB("#5a3a22"));
      Wrect(hx + 16, GROUND - 4, 1, 2, RGB("#f2c14e"));
    }
    // banner poles
    Wrect(684, GROUND - 42, 1, 14, RGB("#5a3820"));
    Wrect(1030, GROUND - 42, 1, 14, RGB("#5a3820"));
    // the castle wall and gate tower
    (function castleWall(wx) {
      Wrect(wx, GROUND - 34, 44, 34, RGB("#8d93a1"));
      for (let yy = 0; yy < 34; yy += 5)
        for (let xx = (yy / 5) % 2 ? 0 : 5; xx < 44; xx += 10)
          Wrect(wx + xx, GROUND - 34 + yy, 8, 1, RGB("#6f7480"));
      for (let xx = 0; xx < 44; xx += 10) {
        Wrect(wx + xx, GROUND - 38, 6, 4, RGB("#8d93a1"));
        Wtri(wx + xx - 1, GROUND - 38, 6, 2, RGB("#9aa0ac"));
      }
      Wtri(wx + 12, GROUND - 46, 20, 12, RGB("#9aa0ac"));
      Wdisc(wx + 22, GROUND - 34, 3, RGB("#5a3a22"));
      Wrect(wx + 16, GROUND - 34, 12, 34, RGB("#5a3a22"));
      Wrect(wx + 18, GROUND - 32, 8, 32, RGB("#4a2f1c"));
      Wrect(wx + 21, GROUND - 40, 2, 6, RGB("#6f7480"));
    })(916);
    // courtyard edge and torch poles
    Wrect(962, GROUND - 30, 10, 30, RGB("#52447c"));
    for (const tx of [990, 1080, 1132, 1266]) Wrect(tx, GROUND - 30, 1, 10, RGB("#5a3820"));
    // the riches: table and coin mounds
    Wrect(1210, GROUND - 22, 26, 3, RGB("#8a5a2e"));
    Wrect(1214, GROUND - 19, 4, 8, RGB("#6a4426"));
    Wrect(1224, GROUND - 19, 4, 8, RGB("#6a4426"));
    Wtri(1150, GROUND - 8, 16, 8, RGB_GOLD);
    Wtri(1180, GROUND - 12, 16, 12, RGB_GOLD);
    Wtri(1240, GROUND - 10, 16, 10, RGB_GOLD);
    for (let i = 0; i < 8; i++) Wrect(1154 + (i % 3) * 4, GROUND - 7 + (i % 4), 2, 1, RGB_GOLD_D);
    wctx.putImageData(WIMG, 0, 0);
  }

  /* ---------------- live sprites ---------------- */

  function pirate(x, y, opts) {
    const o = opts || {};
    const step = o.step || 0, face = o.face || 1, f = face;
    const moving = !!o.moving;
    const bob = moving && step % 2 ? -1 : 0;
    const skin = "#e0a878", shirt = o.shirt || "#2a6db5",
          pants = "#3a3a52", boot = "#23233a", band = o.band || "#d03a3a";
    y += bob;
    const skinP = skin, shirtP = shirt, pantsP = pants, bootP = boot, bandP = band,
          eyeP = "#20222c", bladeP = "#c9ccd4", woodP = "#8a5a2e", sparkP = "#fff3c4";
    disc(x + 2, y + 3, 2, skinP);
    R(x, y + 2, 5, 1, bandP);
    diag(x + 4, y + 1, 2, bandP, f, -1);
    R(x + (f > 0 ? 3 : 1), y + 3, 1, 1, eyeP);
    R(x, y + 6, 5, 3, shirtP);
    R(x + 1, y + 9, 3, 2, shirtP);
    const armSw = moving ? (step % 2 ? 1 : -1) : 0;
    diag(x + (f > 0 ? 4 : 0), y + 6 + (armSw > 0 ? 0 : 1), 2, skinP, f, armSw || 1);
    R(x + 1, y + 11, 2, 2, pantsP); R(x + 3, y + 11, 2, 2, pantsP);
    if (moving) {
      diag(x + 1, y + 12, 2, bootP, f * (step % 2 ? 1 : -1), 1);
      diag(x + 4, y + 12, 2, bootP, -f * (step % 2 ? 1 : -1), 1);
    } else {
      R(x + 1, y + 13, 2, 1, bootP); R(x + 4, y + 13, 2, 1, bootP);
    }
    if (o.sword) {
      const frame = o.step % 3;
      const bx = x + (f > 0 ? 5 : -5), by = y + 5;
      if (frame === 0) diag(bx, by, 5, bladeP, f, -1);
      else if (frame === 1) { for (let i = 0; i < 5; i++) R(bx + f * (4 - i), by - i, 1, 1, bladeP); }
      else diag(bx, by + 1, 5, bladeP, f, 1);
      R(x + (f > 0 ? 4 : 0), y + 6, 2, 1, woodP);
    }
    if (o.spark) {
      const sx = x + (f > 0 ? 9 : -9), sy = y + 3;
      R(sx - 1, sy, 3, 1, sparkP); R(sx, sy - 1, 1, 3, sparkP);
      R(sx - 1, sy - 1, 1, 1, sparkP); R(sx + 1, sy + 1, 1, 1, sparkP);
    }
  }

  function knight(x, y, step) {
    const armor = "#7a8296", dark = "#5a6272";
    disc(x + 2, y + 2, 2, dark);
    R(x + 1, y + 3, 3, 1, "#20222c");
    R(x, y + 4, 5, 5, armor);
    R(x, y + 9, 2, 3, dark); R(x + 3, y + 9, 2, 3, dark);
    R(x + (step % 2 ? 5 : 4), y + 5, 2, 3, "#a04b3a");
    diag(x + 5, y + 3, 4, "#c9ccd4", 1, step % 2 ? -1 : 1);
  }

  function ship(x, y, bob, moving, crewed) {
    const sailWave = moving ? Math.floor(performance.now() / 200) % 2 : 0;
    y += bob;
    R(x + 1, y + 14, 34, 2, "#6a4426");
    R(x, y + 16, 36, 2, "#5a3820");
    diag(x - 3, y + 12, 4, "#6a4426", 1, 1);
    diag(x + 33, y + 12, 4, "#6a4426", 1, 1);
    R(x + 2, y + 18, 32, 2, "#16305e");
    R(x + 17, y - 12, 2, 24, "#5a3820");
    for (let i = 0; i < 10; i++) {
      const inset = Math.abs(5 - i) + sailWave;
      R(x + 8 + inset, y - 10 + i, 20 - inset * 2, 1, "#e8e4d8");
    }
    R(x + 10 + sailWave, y - 4, 16, 2, "#a04b3a");
    tri(x + 19, y - 18, 8, 4, "#d03a3a");
    if (crewed !== false) {
      R(x + 3, y + 6, 4, 8, "#e0a878");
      R(x + 10, y + 7, 4, 7, "#e0a878");
      R(x + 26, y + 7, 4, 7, "#e0a878");
      R(x + 3, y + 5, 4, 1, "#d03a3a"); R(x + 10, y + 6, 4, 1, "#d03a3a");
      R(x + 26, y + 6, 4, 1, "#d03a3a");
    }
    /* foam crashing at the hull */
    const t = performance.now() / 1000;
    for (let i = 0; i < 10; i++) {
      const fx = x + 2 + i * 3.4;
      if (Math.sin(t * 3 + i * 1.7) > 0.1)
        R(fx, y + 18 + (i % 2), 2, 1, Math.sin(t * 3 + i) > 0.6 ? "#e8f4ff" : "#a8d0f0");
    }
  }

  /* ---------------- ambient live layers ---------------- */

  const clouds = [[60, 7, 1.2], [210, 5, 0.8], [360, 10, 1], [520, 6, 1.1]];
  const bubbles = Array.from({ length: 14 }, (_, i) => ({
    x: 20 + (i * 23) % 300, y: 34 + (i * 7) % 20, s: 0.15 + (i % 5) * 0.06,
  }));

  function drawSkyLayer(cam, time) {
    if (cam > 1000) return;                            // inside: walls, no sky
    /* the sun, early phases only */
    const sx = 110 - cam * 0.4;
    if (sx > -10 && sx < VIEW_W + 10) {
      ctx.globalAlpha = 0.35; disc(sx, 9, 6, "#ffd76e"); ctx.globalAlpha = 1;
      disc(sx, 9, 3, "#ffe9a8"); R(sx - 1, 8, 2, 2, "#fff8dc");
    }
    /* drifting clouds */
    ctx.globalAlpha = 0.85;
    for (const [bx, cy, cs] of clouds) {
      const wx = ((bx + time * 2.2) % 1300);
      const sx = wx - cam * 0.55;
      if (sx < -14 || sx > VIEW_W + 14) continue;
      disc(sx, cy, 3 * cs, "#eef2f8");
      disc(sx + 4 * cs, cy + 1, 3 * cs, "#eef2f8");
      disc(sx - 4 * cs, cy + 1, 2 * cs, "#eef2f8");
      R(sx - 6 * cs, cy + 2, 13 * cs, 1, "#dbe4f0");
    }
    ctx.globalAlpha = 1;
  }

  function drawSeaLayer(cam, time) {
    const t = time;
    const x0 = Math.max(Math.floor(cam), 0);
    const x1 = Math.min(Math.ceil(cam + VIEW_W), SHORE);
    /* the surface line, cresting; two blues mixing below it */
    for (let x = x0; x < x1; x++) {
      const sx = x - cam;
      const y = SEA_TOP + Math.round(Math.sin(x * 0.25 + t * 2) * 1 + Math.sin(x * 0.11 - t * 1.4) * 0.6);
      R(sx, y - 1, 1, 1, "#bfe3ff");
      for (let k = 0; k < 3; k++) {
        const by = SEA_TOP + 4 + k * 7 + Math.round(Math.sin(x * 0.2 - t * (1 + k * 0.35) + k) * 1);
        if (by > SEA_TOP && by < GROUND) R(sx, by, 1, 1, k % 2 ? "#5a9be0" : "#2a6db5");
      }
    }
    /* bubbles rising */
    for (const b of bubbles) {
      b.y -= b.s;
      b.x += Math.sin(time * 2 + b.y * 0.15) * 0.25;
      if (b.y < SEA_TOP + 1) { b.y = 40 + (b.x * 7) % 15; b.x = 20 + (b.x * 13) % 300; }
      const sx = Math.round(b.x) - cam;
      if (sx > 0 && sx < VIEW_W) R(sx, Math.round(b.y), 1, 1, "#bfe3ff");
    }
  }

  function drawShoreLayer(cam, time) {
    /* foam washing up the sand and receding */
    for (let x = SHORE - 12; x < SHORE + 42; x++) {
      const sx = x - cam;
      if (sx < 0 || sx > VIEW_W) continue;
      const depth = clamp((x - SHORE) / 42, 0, 1);
      const y = SEA_TOP + Math.round((1 - depth) * (GROUND - SEA_TOP - 4)
               + Math.sin(time * 1.8 + x * 0.35) * 1.5);
      if (Math.sin(time * 2.4 + x * 0.7) > -0.2) R(sx, y, 1, 2, "#a8d0f0");
      if (Math.sin(time * 1.7 + x * 0.5) > 0.55) R(sx, y - 1, 1, 1, "#e8f4ff");
    }
    /* grass slowly growing onto the sand */
    for (let i = 0; i < 12; i++) {
      const gx = 502 + i * 5;
      const t0 = Math.sin(time * 0.12 + i * 1.3);
      if (t0 <= 0) continue;
      const sway = Math.round(Math.sin(time * 2 + i) * 1);
      const sx = gx - cam, h = 2 + Math.round(t0 * 2);
      if (sx > 0 && sx < VIEW_W) {
        R(sx, GROUND - h, 1, h, "#4e8f3a");
        R(sx + sway, GROUND - h - 1, 1, 1, "#5a9a45");
      }
    }
  }

  function drawPropsLayer(cam, time) {
    /* banners waving */
    for (const bx of [684, 1030]) {
      const sx = bx - cam;
      if (sx < -12 || sx > VIEW_W) continue;
      const wave = Math.floor(time * 3) % 2;
      R(sx + 1, GROUND - 41, 7, 5, "#5b8def");
      R(sx + 1, GROUND - 36 + wave, 6, 2, "#5b8def");
      tri(sx + 8, GROUND - 41, 3, 5, "#5b8def");
    }
    /* torch flames */
    for (const tx of [990, 1080, 1132, 1266]) {
      const sx = tx - cam;
      if (sx < -8 || sx > VIEW_W) continue;
      const f = Math.floor(time * 8) % 2;
      disc(sx, GROUND - 32 - f, 1, "#f2a13e");
      R(sx, GROUND - 35 - f, 1, 2, "#f2c14e");
    }
    /* gold sparkles */
    const tw = Math.floor(time * 4);
    for (let i = 0; i < 4; i++) {
      const sx = 1152 + ((tw + i * 3) % 9) * 5 - cam, sy = GROUND - 4 - (i % 3) * 3;
      if (sx > 0 && sx < VIEW_W) R(sx, sy, 1, 1, "#fff3c4");
    }
  }

  /* ---------------- the crew ---------------- */

  function drawCrew(cam, t, moving) {
    const x = eloToX(eloShown);
    const z = zoneOf(x);
    const step = Math.floor(t * (moving ? 9 : 5));
    const onSea = x < SHORE - 12;                      // still sailing
    if (onSea) {
      const bob = Math.round(Math.sin(t * 2.2) * 1.5);
      ship(x - 10 - cam, SEA_TOP - 8 + bob, bob, moving);
      return;
    }
    /* the ship stays anchored at the shoreline once they disembark */
    const ax = SHORE - 14 - cam;
    if (ax > -40 && ax < VIEW_W) {
      const bob = Math.round(Math.sin(t * 2.2) * 1.5);
      ship(ax, SEA_TOP - 8 + bob, bob, false, false);
    }
    const fighting = z >= 5 && z <= 6;
    const celebrating = z === 7;
    const base = GROUND - 13;
    const spread = moving ? [0, 14, -12] : [0, 14, 28];
    pirate(x - cam, base, {
      step, moving, sword: fighting, spark: fighting && step % 4 === 0,
      face: 1, shirt: "#2a6db5", band: "#d03a3a",
    });
    pirate(x - cam - spread[1], base + (celebrating ? Math.abs(Math.sin(t * 4)) * -2 | 0 : 0),
           { step: step + 1, moving, sword: fighting, shirt: "#e8e4d8", band: "#2a6db5" });
    if (!moving || celebrating)
      pirate(x - cam + spread[2], base,
             { step: step + 2, moving: false, sword: false, shirt: "#4e8f3a", band: "#f2c14e" });
    if (celebrating) {                                 // the flag goes up
      R(x - cam - 16, GROUND - 30, 2, 17, "#5a3820");
      R(x - cam - 14, GROUND - 30, 10, 6, "#d03a3a");
      disc(x - cam - 9, GROUND - 27, 1, "#f2c14e");
    }
  }

  /* ---------------- loop ---------------- */

  function frame() {
    const now = performance.now();
    const time = now / 1000;
    if (tweenDur > 0) {
      const k = clamp((now - tweenT0) / tweenDur, 0, 1);
      const ease = 1 - Math.pow(1 - k, 3);
      eloShown = elo + (eloTarget - elo) * ease;
      if (k >= 1) { eloShown = eloTarget; tweenDur = 0; }
    } else eloShown = eloTarget;
    const moving = tweenDur > 0;

    const heroX = eloToX(eloShown);
    const cam = clamp(heroX - VIEW_W * 0.42, 0, WORLD_W - VIEW_W);

    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(world, cam, 0, VIEW_W, VIEW_H, 0, 0, VIEW_W, VIEW_H);
    drawSkyLayer(cam, time);
    drawSeaLayer(cam, time);
    drawShoreLayer(cam, time);
    drawPropsLayer(cam, time);
    drawCrew(cam, time, moving);

    requestAnimationFrame(frame);
  }

  window.Pirates = {
    init() {
      bakeWorld();
      eloShown = eloTarget = elo = 800;
      requestAnimationFrame(frame);
    },
    /* tween the crew to the new general Elo; forward on correct answers,
       backward on wrong ones */
    setTarget(newElo) {
      elo = eloShown;
      eloTarget = clamp(newElo, ELO_BASE, ELO_BASE + ELO_PER_ZONE * ZONES);
      tweenT0 = performance.now();
      tweenDur = 900;
    },
    phaseName(elo) {
      return ["Dark Ocean", "Open Water", "The Beach", "The Fields", "The Town",
              "The Castle Walls", "The Courtyard", "The Riches"][
        clamp(Math.floor((elo - ELO_BASE) / ELO_PER_ZONE), 0, 7)];
    },
  };
})();
