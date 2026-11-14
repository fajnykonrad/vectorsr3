/* The pirate attack: a pixel-art progress world driven by the general Elo.
 *
 * Eight phases of 300 Elo points each, starting at 300:
 *   1 dark ocean   2 open water   3 the beach    4 the fields
 *   5 the town     6 the walls    7 the courtyard 8 the riches
 *
 * The crew's x position on the world map is the general Elo; the camera
 * follows them. Correct answers tween the crew forward (sail, walk or
 * fight), wrong ones backward. Idle animations run all the time: waves, a
 * bobbing ship, walk cycles with body bob, sword arcs, scuttling crabs,
 * flickering torches, celebration. Shapes are rounded where it matters —
 * scanline discs, slopes and triangles, not stacks of rectangles.
 * Everything is drawn on a 200x60 logical canvas that the CSS scales up
 * with image-rendering: pixelated.
 */
(function () {
  "use strict";

  const VIEW_W = 200, VIEW_H = 60;
  const ZONE = 160, ZONES = 8, WORLD_W = ZONE * ZONES;   // 1280
  const ELO_BASE = 300, ELO_PER_ZONE = 300;
  const PX_PER_ELO = WORLD_W / (ELO_PER_ZONE * ZONES);   // 0.533 px per point
  const GROUND = 50;                                     // land ground line
  const SEA_TOP = 30;                                    // sea surface line
  const ROW_GAP = 25;

  const SKY = [
    ["#0e1830", "#15234a"],  // 1 dark ocean, night
    ["#16264e", "#1f3468"],  // 2 open water, pre-dawn
    ["#2e5d9e", "#4a7fc0"],  // 3 beach morning
    ["#79b7e8", "#a9d4f2"],  // 4 fields, clear day
    ["#87b7e0", "#b8d9f2"],  // 5 town, clear day
    ["#5a4a8a", "#7a6ab0"],  // 6 walls at dusk
    ["#3a2f5a", "#52447c"],  // 7 courtyard, night battle
    ["#241d33", "#322a48"],  // 8 inside, torchlight
  ];

  const c = document.getElementById("pirate-scene");
  if (!c) return;
  const ctx = c.getContext("2d");

  let elo = 800, eloShown = 800, eloTarget = 800, tweenT0 = 0, tweenDur = 0;

  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const eloToX = e => clamp(e - ELO_BASE, 0, ELO_PER_ZONE * ZONES) * PX_PER_ELO;
  const zoneOf = x => clamp(Math.floor(x / ZONE), 0, ZONES - 1);
  const R = (x, y, w, h, color) => { ctx.fillStyle = color; ctx.fillRect(x, y, w, h); };
  /* a filled scanline circle: the pixel way to draw round things */
  function disc(cx, cy, r, color) {
    for (let dy = -r; dy <= r; dy++) {
      const w = Math.floor(Math.sqrt(r * r - dy * dy));
      R(cx - w, cy + dy, w * 2 + 1, 1, color);
    }
  }
  /* a diagonal run of pixels, used for blades, arms, roofs, fronds */
  function diag(x, y, n, color, dx, dy) {
    for (let i = 0; i < n; i++) R(x + i * dx, y + i * dy, 1, 1, color);
  }
  /* a triangle, tip up, built from widening scanlines */
  function tri(x, y, w, h, color) {
    for (let i = 0; i < h; i++) {
      const inset = Math.floor((h - 1 - i) * w / (2 * h));
      R(x + inset, y + i, w - inset * 2, 1, color);
    }
  }

  /* ---------------- background pieces (world coordinates) --------------- */

  function sky(cam) {
    const [top, bottom] = SKY[zoneOf(cam + VIEW_W / 2)];
    R(0, 0, VIEW_W, SEA_TOP, top);
    R(0, SEA_TOP, VIEW_W, VIEW_H - SEA_TOP, bottom);
    if (zoneOf(cam + VIEW_W / 2) <= 1 || zoneOf(cam + VIEW_W / 2) >= 6) {
      const t = Math.floor(performance.now() / 700);
      for (let i = 0; i < 14; i++) {
        const sx = ((i * 37 + (t % 2) * 7) % VIEW_W), sy = ((i * 13) % (SEA_TOP - 6)) + 3;
        if ((i + (t % 3)) % 3) R(sx, sy, 1, 1, "#cfd8ec");
      }
    }
  }

  function seaRows(cam, zoneLeft, colors) {
    const x0 = Math.max(zoneLeft - cam, 0), x1 = Math.min(zoneLeft + ZONE - cam, VIEW_W);
    if (x1 <= x0) return;
    const t = performance.now() / 500;
    R(x0, SEA_TOP, x1 - x0, GROUND - SEA_TOP, colors.base);
    for (let row = 0; row < 4; row++) {
      const y = SEA_TOP + 2 + row * 5;
      const shift = Math.floor((t + row * 0.6) * 4) % 8;
      for (let x = x0 - (x0 % 8) + shift; x < x1; x += 8) {
        R(x, y, 3, 1, colors.wave);                    // the wave crest...
        R(x + 3, y + 1, 1, 1, colors.wave);            // ...with a soft tail
      }
    }
    R(x0, GROUND - 6, x1 - x0, 6, colors.deep);
  }

  function ground(cam, zoneLeft, color, dark) {
    const x0 = Math.max(zoneLeft - cam, 0), x1 = Math.min(zoneLeft + ZONE - cam, VIEW_W);
    if (x1 <= x0) return;
    R(x0, GROUND, x1 - x0, VIEW_H - GROUND, color);
    for (let x = Math.ceil(x0 / 6) * 6; x < x1; x += 6)
      R(x, GROUND, 3, 1, dark);
  }

  function palm(wx, cam) {
    const x = wx - cam, y = GROUND;
    if (x < -16 || x > VIEW_W) return;
    diag(x + 6, y - 2, 8, "#7a5230", -1, -2);          // trunk leans
    R(x + 6 - 8, y - 18, 3, 2, "#7a5230");
    diag(x, y - 20, 6, "#3d7530", 1, -1);              // fronds splay
    diag(x + 8, y - 20, 6, "#3d7530", 1, 1);
    diag(x + 2, y - 22, 5, "#4e8f3a", 1, 0);
    diag(x + 6, y - 22, 5, "#4e8f3a", 1, 1);
    disc(x + 7, y - 21, 1, "#5a9a45");
    R(x + 5, y - 16, 2, 2, "#8a5a2e");                 // coconuts
  }

  function tree(wx, cam) {
    const x = wx - cam;
    if (x < -16 || x > VIEW_W) return;
    R(x + 6, GROUND - 14, 3, 14, "#5a3a22");
    disc(x + 7, GROUND - 19, 6, "#3d7530");
    disc(x + 5, GROUND - 21, 4, "#4e8f3a");
    disc(x + 10, GROUND - 20, 3, "#5a9a45");
  }

  function house(wx, cam, wall, roof) {
    const x = wx - cam;
    if (x < -40 || x > VIEW_W) return;
    R(x, GROUND - 18, 30, 18, wall);
    for (let i = 0; i < 4; i++) R(x, GROUND - 18 + i * 4, 30, 1, "rgba(0,0,0,.15)");
    tri(x - 3, GROUND - 30, 36, 12, roof);              // pitched roof
    for (let i = 0; i < 12; i += 3)                     // roof shingles
      R(x - 3 + i + 2, GROUND - 30 + i * 0 + 1, 1, 11 - i, "rgba(0,0,0,.12)");
    R(x + 6, GROUND - 12, 5, 5, "#f2c14e");
    R(x + 19, GROUND - 12, 5, 5, "#f2c14e");
    R(x + 13, GROUND - 7, 5, 7, "#5a3a22");
    R(x + 16, GROUND - 4, 1, 2, "#f2c14e");             // door handle
  }

  function castleWall(wx, cam) {
    const x = wx - cam;
    if (x < -48 || x > VIEW_W) return;
    R(x, GROUND - 34, 44, 34, "#8d93a1");
    for (let yy = 0; yy < 34; yy += 5)
      for (let xx = (yy / 5) % 2 ? 0 : 5; xx < 44; xx += 10)
        R(x + xx, GROUND - 34 + yy, 8, 1, "#6f7480");
    for (let xx = 0; xx < 44; xx += 10) {
      R(x + xx, GROUND - 38, 6, 4, "#8d93a1");
      tri(x + xx - 1, GROUND - 38, 6, 2, "#9aa0ac");    // chamfered merlons
    }
    tri(x + 12, GROUND - 46, 20, 12, "#9aa0ac");        // a corner tower
    disc(x + 22, GROUND - 34, 3, "#5a3a22");            // gate arch top
    R(x + 16, GROUND - 34, 12, 34, "#5a3a22");
    R(x + 18, GROUND - 32, 8, 32, "#4a2f1c");
    R(x + 21, GROUND - 40, 2, 6, "#6f7480");            // arrow slit
  }

  function banner(wx, cam, color) {
    const x = wx - cam;
    if (x < -12 || x > VIEW_W) return;
    R(x, GROUND - 42, 1, 14, "#5a3820");
    const wave = Math.floor(performance.now() / 300) % 2;
    R(x + 1, GROUND - 41, 7, 5, color);
    R(x + 1, GROUND - 36 + wave, 6, 2, color);
    tri(x + 8, GROUND - 41, 3, 5, color);               // swallow-tail
  }

  function goldPile(wx, cam, h) {
    const x = wx - cam;
    if (x < -20 || x > VIEW_W) return;
    tri(x, GROUND - h, 16, h, "#f2c14e");               // a mound of coins
    for (let i = 0; i < h; i++)
      R(x + 4 - (i % 2), GROUND - h + i, 2, 1, "#d4a017");
    const tw = Math.floor(performance.now() / 250) % 3;
    R(x + 7 + tw * 2, GROUND - h - 2, 1, 1, "#fff3c4"); // sparkle
  }

  function torch(wx, cam) {
    const x = wx - cam;
    if (x < -8 || x > VIEW_W) return;
    R(x, GROUND - 30, 1, 10, "#5a3820");
    const f = Math.floor(performance.now() / 150) % 2;
    disc(x, GROUND - 32 - f, 1, "#f2a13e");
    R(x, GROUND - 35 - f, 1, 2, "#f2c14e");
  }

  /* ---------------- the detailed beach ---------------- */

  function beachDetail(left, cam, t) {
    const x0 = Math.max(left - cam, 0), x1 = Math.min(left + ZONE - cam, VIEW_W);
    if (x1 <= x0) return;
    // dunes: rounded mounds of darker sand
    for (const dx of [24, 78, 132]) {
      const x = left + dx - cam;
      if (x > -10 && x < VIEW_W) {
        disc(x, GROUND + 8, 5, "#c19a52");
        R(x - 5, GROUND + 2, 10, 2, "#e0c185");
      }
    }
    // shells, pebbles, starfish, driftwood, seaweed, footprints, crabs
    const items = [
      [14, "pebble"], [26, "shell"], [38, "starfish"], [52, "driftwood"],
      [64, "seaweed"], [76, "footprint"], [88, "crab"], [100, "shell"],
      [112, "pebble"], [124, "starfish"], [136, "driftwood"], [148, "seaweed"],
      [160, "crab"], [172, "footprint"], [184, "shell"], [196, "pebble"],
      [208, "starfish"], [220, "driftwood"], [232, "seaweed"], [244, "shell"],
      [256, "crab"], [268, "pebble"], [280, "footprint"], [292, "starfish"],
      [304, "driftwood"], [316, "seaweed"], [328, "shell"], [340, "crab"],
      [352, "pebble"], [364, "driftwood"],
    ];
    for (const [off, kind] of items) {
      const x = left + off - cam;
      if (x < -12 || x > VIEW_W) continue;
      const y = GROUND + 4 + (off % 3) * 2;
      switch (kind) {
        case "pebble": disc(x, y + 1, 1, "#9aa0ac"); disc(x, y + 1, 0, "#c8cdd4"); break;
        case "shell": R(x, y, 3, 3, "#f0e0d0"); R(x + 1, y + 1, 1, 1, "#d98a8a");
          R(x, y, 1, 1, "#d98a8a"); break;
        case "starfish":
          R(x - 1, y + 1, 7, 1, "#e08a4a"); R(x + 1, y - 1, 3, 5, "#e08a4a");
          diag(x - 1, y - 1, 2, "#e08a4a", 1, -1); diag(x + 2, y + 2, 2, "#e08a4a", 1, 1);
          diag(x + 2, y - 1, 2, "#e08a4a", 1, 1); diag(x - 1, y + 2, 2, "#e08a4a", 1, 1);
          R(x + 1, y + 1, 1, 1, "#c96a2a"); break;
        case "driftwood": R(x, y + 1, 11, 2, "#8a5a2e"); diag(x - 1, y, 2, "#8a5a2e", 1, 1);
          R(x + 3, y + 1, 1, 1, "#6a4426"); R(x + 7, y + 2, 3, 1, "#6a4426"); break;
        case "seaweed": diag(x, y, 5, "#3d7530", 1, -1); diag(x + 2, y + 1, 4, "#4e8f3a", 1, -1);
          R(x + 1, y - 3, 1, 1, "#5a9a45"); break;
        case "footprint": R(x, y, 2, 1, "#b08a55"); R(x + 4, y + 1, 2, 1, "#b08a55");
          R(x + 8, y, 2, 1, "#b08a55"); R(x + 12, y + 1, 2, 1, "#b08a55"); break;
        case "crab": {
          const cx = x + Math.sin(t * 1.5 + off) * 7;    // scuttles sideways
          disc(cx + 2, y + 1, 1, "#d04a3a");
          R(cx - 1, y + 1, 1, 1, "#d04a3a"); R(cx + 5, y + 1, 1, 1, "#d04a3a");
          diag(cx - 1, y + 2, 2, "#d04a3a", 1, 1); diag(cx + 4, y + 2, 2, "#d04a3a", -1, 1);
          R(cx + 1, y, 1, 1, "#20222c"); R(cx + 3, y, 1, 1, "#20222c");
          break;
        }
      }
    }
  }

  /* ---------------- sprites ---------------- */

  function pirate(x, y, opts) {
    const o = opts || {};
    const step = o.step || 0, face = o.face || 1, f = face;
    const moving = !!o.moving;
    const bob = moving && step % 2 ? -1 : 0;             // body bob while walking
    const skin = "#e0a878", shirt = o.shirt || "#2a6db5",
          pants = "#3a3a52", boot = "#23233a", band = o.band || "#d03a3a";
    y += bob;
    disc(x + 2, y + 3, 2, skin);                         // round head
    R(x, y + 2, 5, 1, band);                             // bandana band
    diag(x + 4, y + 1, 2, band, f, -1);                  // bandana tail
    R(x + (f > 0 ? 3 : 1), y + 3, 1, 1, "#20222c");      // eye
    R(x, y + 6, 5, 3, shirt);                            // body
    R(x + 1, y + 9, 3, 2, shirt);                        // belt line
    const armSw = moving ? (step % 2 ? 1 : -1) : 0;
    diag(x + (f > 0 ? 4 : 0), y + 6 + (armSw > 0 ? 0 : 1), 2, skin, f, armSw || 1);
    R(x + 1, y + 11, 2, 2, pants); R(x + 3, y + 11, 2, 2, pants);
    if (moving) {                                        // diagonal stride
      diag(x + 1, y + 12, 2, boot, f * (step % 2 ? 1 : -1), 1);
      diag(x + 4, y + 12, 2, boot, -f * (step % 2 ? 1 : -1), 1);
    } else {
      R(x + 1, y + 13, 2, 1, boot); R(x + 4, y + 13, 2, 1, boot);
    }
    if (o.sword) {                                       // arcing blade
      const frame = o.step % 3;
      const bx = x + (f > 0 ? 5 : -5), by = y + 5;
      if (frame === 0) diag(bx, by, 5, "#c9ccd4", f, -1);
      else if (frame === 1) { for (let i = 0; i < 5; i++) R(bx + f * (4 - i), by - i, 1, 1, "#c9ccd4"); }
      else diag(bx, by + 1, 5, "#c9ccd4", f, 1);
      R(x + (f > 0 ? 4 : 0), y + 6, 2, 1, "#8a5a2e");    // hilt
    }
    if (o.spark) {
      const sx = x + (f > 0 ? 9 : -9), sy = y + 3;
      R(sx - 1, sy, 3, 1, "#fff3c4"); R(sx, sy - 1, 1, 3, "#fff3c4");
      R(sx - 1, sy - 1, 1, 1, "#fff3c4"); R(sx + 1, sy + 1, 1, 1, "#fff3c4");
    }
  }

  function knight(x, y, step) {
    const armor = "#7a8296", dark = "#5a6272";
    disc(x + 2, y + 2, 2, dark);                         // rounded helmet
    R(x + 1, y + 3, 3, 1, "#20222c");                    // visor slit
    R(x, y + 4, 5, 5, armor);
    R(x, y + 9, 2, 3, dark); R(x + 3, y + 9, 2, 3, dark);
    R(x + (step % 2 ? 5 : 4), y + 5, 2, 3, "#a04b3a");   // shield
    diag(x + 5, y + 3, 4, "#c9ccd4", 1, step % 2 ? -1 : 1);  // swinging blade
  }

  function ship(x, y, bob, moving) {
    const sailWave = moving ? Math.floor(performance.now() / 200) % 2 : 0;
    y += bob;
    R(x + 1, y + 14, 34, 2, "#6a4426");                  // hull: curved with
    R(x, y + 16, 36, 2, "#5a3820");                      // stepped bow & stern
    diag(x - 3, y + 12, 4, "#6a4426", 1, 1);             // raised bow
    diag(x + 33, y + 12, 4, "#6a4426", 1, 1);
    R(x + 2, y + 18, 32, 2, "#16305e");                  // waterline shadow
    R(x + 17, y - 12, 2, 24, "#5a3820");                 // mast
    for (let i = 0; i < 10; i++) {                       // rounded sail
      const inset = Math.abs(5 - i) + sailWave;
      R(x + 8 + inset, y - 10 + i, 20 - inset * 2, 1, "#e8e4d8");
    }
    R(x + 10 + sailWave, y - 4, 16, 2, "#a04b3a");       // sail stripe
    tri(x + 19, y - 18, 8, 4, "#d03a3a");                // pennant
    R(x + 3, y + 6, 4, 8, "#e0a878");                    // crew figures
    R(x + 10, y + 7, 4, 7, "#e0a878");
    R(x + 26, y + 7, 4, 7, "#e0a878");
    R(x + 3, y + 5, 4, 1, "#d03a3a"); R(x + 10, y + 6, 4, 1, "#d03a3a");
    R(x + 26, y + 6, 4, 1, "#d03a3a");
  }

  /* ---------------- the world ---------------- */

  function drawZone(z, cam) {
    const left = z * ZONE;
    if (left + ZONE < cam || left > cam + VIEW_W) return;
    const t = performance.now() / 1000;
    switch (z) {
      case 0: {  // dark ocean
        seaRows(cam, left, { base: "#16305e", wave: "#1d3d75", deep: "#0e2148" });
        break;
      }
      case 1: {  // approaching the shore: lighter sea
        seaRows(cam, left, { base: "#2a6db5", wave: "#5a9be0", deep: "#1d4a86" });
        break;
      }
      case 2: {  // the beach: sand from the shoreline, dunes, shells, crabs
        const foam = Math.round(Math.sin(performance.now() / 400) * 2);
        const sand0 = Math.max(left - cam, 0);            // shoreline = zone edge
        const sand1 = Math.min(left + ZONE - cam, VIEW_W);
        if (sand1 > sand0) {
          R(sand0, SEA_TOP - 1, sand1 - sand0, GROUND - SEA_TOP + 1, "#d9b36c");
          R(sand0, GROUND, sand1 - sand0, VIEW_H - GROUND, "#d9b36c");
          R(sand0 - 1 + foam, SEA_TOP - 1, sand1 - sand0, 1, "#a8d0f0");  // surf line
          R(sand0 - 2 + foam, SEA_TOP + 1, sand1 - sand0, 1, "#a8d0f0");
        }
        beachDetail(left, cam, t);
        palm(left + 130, cam);
        break;
      }
      case 3: {  // fields
        ground(cam, left, "#4e8f3a", "#3d7530");
        for (let i = 0; i < 7; i++) {
          const wx = left + 12 + i * 22;
          const x = wx - cam;
          if (x > -6 && x < VIEW_W) { diag(x, GROUND, 3, "#c9a94e", 1, -1); diag(x + 2, GROUND, 3, "#c9a94e", 1, 0); }
        }
        tree(left + 60, cam); tree(left + 128, cam);
        break;
      }
      case 4: {  // medieval town
        ground(cam, left, "#8a7f6e", "#756b5c");
        house(left + 8, cam, "#c9a06a", "#a04b3a");
        house(left + 58, cam, "#9a7550", "#8a4a3a");
        house(left + 112, cam, "#c9a06a", "#a04b3a");
        banner(left + 44, cam, "#5b8def");
        break;
      }
      case 5: {  // fighting at the castle walls
        ground(cam, left, "#6f7480", "#5a5f6a");
        castleWall(left + 116, cam);
        knight(left + 96 - cam, GROUND - 13, Math.floor(t * 4));
        break;
      }
      case 6: {  // fighting inside the walls (courtyard)
        R(Math.max(left - cam, 0), 0, Math.min(ZONE - cam, VIEW_W), VIEW_H, "#241d33");
        ground(cam, left, "#3a2f4a", "#2e2439");
        R(left + 4 - cam, GROUND - 30, 10, 30, "#52447c");   // inner wall edge
        torch(left + 30, cam); torch(left + 120, cam);
        banner(left + 70, cam, "#d03a3a");
        knight(left + 100 - cam, GROUND - 13, Math.floor(t * 5));
        break;
      }
      case 7: {  // inside the castle, celebrating the riches
        R(Math.max(left - cam, 0), 0, Math.min(ZONE - cam, VIEW_W), VIEW_H, "#1a1526");
        ground(cam, left, "#3a2f4a", "#2e2439");
        goldPile(left + 30, cam, 8); goldPile(left + 60, cam, 12);
        goldPile(left + 120, cam, 10);
        R(left + 90 - cam, GROUND - 22, 26, 3, "#8a5a2e");   // table
        R(left + 94 - cam, GROUND - 19, 4, 8, "#6a4426");
        R(left + 104 - cam, GROUND - 19, 4, 8, "#6a4426");
        torch(left + 12, cam); torch(left + 146, cam);
        const tw = Math.floor(performance.now() / 200);
        disc(left + 78 - cam + (tw % 4) * 4, GROUND - 30, 1, "#f2c14e"); // tossed coin
        break;
      }
    }
  }

  /* ---------------- the crew ---------------- */

  function drawCrew(cam, t, moving) {
    const x = eloToX(eloShown);
    const z = zoneOf(x);
    const step = Math.floor(t * (moving ? 9 : 5));
    const onSea = z <= 1;
    if (onSea) {
      const bob = Math.round(Math.sin(t * 2.2) * 1.5);
      ship(x - 8 - cam, SEA_TOP - 6 + bob, bob, moving);
      return;
    }
    const fighting = z === 5 || z === 6;
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
    if (celebrating) {                                     // the flag goes up
      R(x - cam - 16, GROUND - 30, 2, 17, "#5a3820");
      R(x - cam - 14, GROUND - 30, 10, 6, "#d03a3a");
      disc(x - cam - 9, GROUND - 27, 1, "#f2c14e");
    }
  }

  /* ---------------- loop ---------------- */

  function frame() {
    const now = performance.now();
    const t = now / 1000;
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
    ctx.clearRect(0, 0, VIEW_W, VIEW_H);
    sky(cam);
    for (let z = 0; z < ZONES; z++) drawZone(z, cam);
    drawCrew(cam, t, moving);

    requestAnimationFrame(frame);
  }

  window.Pirates = {
    init() {
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
