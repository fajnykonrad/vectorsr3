/* The pirate attack: a pixel-art progress world driven by the general Elo.
 *
 * Eight phases of 100 Elo points each, starting at 700:
 *   1 dark ocean   2 near the shore   3 the beach    4 the fields
 *   5 the town     6 the castle walls 7 the courtyard 8 the riches
 *
 * The crew's x position on the world map is the general Elo (1.6 px per
 * point); the camera follows them. Correct answers tween the crew forward
 * (sail, walk or fight), wrong ones backward. Idle animations run all the
 * time: waves, a bobbing ship, a walk cycle, sword swings, celebration.
 * Everything is drawn on a 200x60 logical canvas that the CSS scales up
 * with image-rendering: pixelated.
 */
(function () {
  "use strict";

  const VIEW_W = 200, VIEW_H = 60;
  const ZONE = 160, ZONES = 8, WORLD_W = ZONE * ZONES;   // 1280
  const ELO_BASE = 700, ELO_PER_ZONE = 100, PX_PER_ELO = WORLD_W / (ELO_PER_ZONE * ZONES);
  const GROUND = 50;                                     // land ground line
  const SEA_TOP = 30;                                    // sea surface line

  const SKY = [
    ["#0e1830", "#15234a"],  // 1 dark ocean night sky
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
  let started = performance.now();

  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const eloToX = e => clamp(e - ELO_BASE, 0, ELO_PER_ZONE * ZONES) * PX_PER_ELO;
  const zoneOf = x => clamp(Math.floor(x / ZONE), 0, ZONES - 1);
  const R = (x, y, w, h, color) => { ctx.fillStyle = color; ctx.fillRect(x, y, w, h); };

  /* ---------------- background pieces (world coordinates) --------------- */

  function sky(cam) {
    const [top, bottom] = SKY[zoneOf(cam + VIEW_W / 2)];
    R(0, 0, VIEW_W, SEA_TOP, top);
    R(0, SEA_TOP, VIEW_W, VIEW_H - SEA_TOP, bottom);
    // a few pixel stars for the dark phases
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
    for (let row = 0; row < 4; row++) {                  // wave rows, drifting
      const y = SEA_TOP + 2 + row * 5;
      const shift = Math.floor((t + row * 0.6) * 4) % 8;
      for (let x = x0 - (x0 % 8) + shift; x < x1; x += 8)
        R(x, y, 4, 1, colors.wave);
    }
    R(x0, GROUND - 6, x1 - x0, 6, colors.deep);          // deeper at the bottom
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
    if (x < -12 || x > VIEW_W) return;
    R(x + 5, y - 16, 2, 16, "#7a5230");
    R(x, y - 20, 12, 2, "#3d7530"); R(x + 2, y - 22, 8, 2, "#4e8f3a");
    R(x - 2, y - 18, 5, 2, "#3d7530"); R(x + 9, y - 18, 5, 2, "#3d7530");
  }

  function tree(wx, cam) {
    const x = wx - cam;
    if (x < -14 || x > VIEW_W) return;
    R(x + 5, GROUND - 14, 3, 14, "#5a3a22");
    R(x + 1, GROUND - 22, 11, 9, "#3d7530");
    R(x + 3, GROUND - 24, 7, 3, "#4e8f3a");
  }

  function house(wx, cam, wall, roof) {
    const x = wx - cam;
    if (x < -34 || x > VIEW_W) return;
    R(x, GROUND - 20, 30, 20, wall);
    for (let i = 0; i < 5; i++) R(x, GROUND - 20 + i * 4, 30, 1, "rgba(0,0,0,.15)");
    for (let i = 0; i <= 6; i++)                        // pixel roof slope
      R(x + i * 2 - 2, GROUND - 20 - (6 - i) * 2, 30 - i * 4 + 4, 2, roof);
    R(x + 6, GROUND - 14, 5, 5, "#f2c14e");             // lit windows
    R(x + 19, GROUND - 14, 5, 5, "#f2c14e");
    R(x + 13, GROUND - 8, 5, 8, "#5a3a22");             // door
  }

  function castleWall(wx, cam) {
    const x = wx - cam;
    if (x < -46 || x > VIEW_W) return;
    R(x, GROUND - 34, 44, 34, "#8d93a1");
    for (let yy = 0; yy < 34; yy += 5)
      for (let xx = (yy / 5) % 2 ? 0 : 5; xx < 44; xx += 10)
        R(x + xx, GROUND - 34 + yy, 8, 1, "#6f7480");
    for (let xx = 0; xx < 44; xx += 10) R(x + xx, GROUND - 38, 6, 4, "#8d93a1"); // crenels
    R(x + 16, GROUND - 26, 12, 26, "#5a3a22");           // gate
    R(x + 18, GROUND - 24, 8, 24, "#4a2f1c");
    R(x + 20, GROUND - 34, 4, 8, "#6f7480");             // arrow slit
  }

  function banner(wx, cam, color) {
    const x = wx - cam;
    if (x < -10 || x > VIEW_W) return;
    R(x, GROUND - 40, 1, 12, "#5a3820");
    const wave = Math.floor(performance.now() / 300) % 2;
    R(x + 1, GROUND - 39, 7, 5, color);
    R(x + 1, GROUND - 34 + wave, 6, 2, color);
  }

  function goldPile(wx, cam, h) {
    const x = wx - cam;
    if (x < -16 || x > VIEW_W) return;
    for (let i = 0; i < h; i++)
      R(x + i, GROUND - (h - i) * 2, 16 - 2 * i, 2, i % 2 ? "#d4a017" : "#f2c14e");
    const tw = Math.floor(performance.now() / 250) % 3;
    R(x + 6 + tw * 3, GROUND - h * 2 - 2, 1, 1, "#fff3c4");   // sparkle
  }

  function torch(wx, cam) {
    const x = wx - cam;
    if (x < -6 || x > VIEW_W) return;
    R(x, GROUND - 30, 1, 10, "#5a3820");
    const f = Math.floor(performance.now() / 150) % 2;
    R(x - 1, GROUND - 33 - f, 3, 3, "#f2a13e");
    R(x, GROUND - 35 - f, 1, 2, "#f2c14e");
  }

  /* ---------------- sprites ---------------- */

  function pirate(x, y, opts) {
    const o = opts || {};
    const step = o.step || 0, face = o.face || 1;
    const legA = step % 2 ? 1 : -1;
    const skin = "#e0a878", shirt = o.shirt || "#2a6db5",
          pants = "#3a3a52", boot = "#23233a", band = o.band || "#d03a3a";
    R(x, y, 5, 2, band);                                 // bandana
    R(x, y + 2, 5, 3, skin);                             // head
    R(x + (face > 0 ? 3 : 0), y + 3, 1, 1, "#20222c");   // eye
    R(x, y + 5, 5, 4, shirt);                            // body
    R(x + (face > 0 ? 4 : -1), y + 6, 2, 2, skin);       // arm
    R(x + 1, y + 9, 2, 3, pants); R(x + 3, y + 9, 2, 3, pants);
    R(x + 1 + legA, y + 12, 2, 1, boot); R(x + 3 - legA, y + 12, 2, 1, boot);
    if (o.sword) {                                       // sword, swings
      const sw = o.step % 2 ? -1 : 1;
      R(x + (face > 0 ? 5 : -3), y + 4 + (sw < 0 ? 2 : 0), face > 0 ? 4 : 4, 1, "#c9ccd4");
      R(x + (face > 0 ? 8 : -4), y + 3 + (sw < 0 ? 2 : 0), 1, 2, "#8a5a2e");
    }
    if (o.spark) {
      const sx = x + (face > 0 ? 8 : -6), sy = y + 4;
      R(sx, sy, 3, 1, "#fff3c4"); R(sx + 1, sy - 1, 1, 3, "#fff3c4");
    }
  }

  function knight(x, y, step) {
    const armor = "#7a8296", dark = "#5a6272";
    R(x, y, 5, 3, dark);                                 // helmet
    R(x + 1, y + 3, 3, 1, "#20222c");                    // visor slit
    R(x, y + 4, 5, 5, armor);
    R(x, y + 9, 2, 3, dark); R(x + 3, y + 9, 2, 3, dark);
    const off = step % 2 ? 1 : 0;
    R(x + (step % 2 ? 5 : 4), y + 5, 2, 3, "#a04b3a");   // shield
    if (step % 2) R(x + 6, y + 3, 1, 3, "#c9ccd4");      // swinging sword
  }

  function ship(x, y, bob, moving) {
    const sailWave = moving ? Math.floor(performance.now() / 200) % 2 : 0;
    R(x, y + 12, 34, 5, "#6a4426");                      // hull
    R(x + 2, y + 10, 30, 2, "#5a3820");
    R(x + 2, y + 17, 32, 2, "#16305e");                  // waterline shadow
    R(x + 16, y - 10, 2, 20, "#5a3820");                 // mast
    R(x + 6 + sailWave, y - 8, 20, 14, "#e8e4d8");       // sail
    R(x + 6 + sailWave, y - 3, 20, 2, "#a04b3a");        // sail stripe
    R(x + 18, y - 14, 6, 4, "#d03a3a");                  // flag
    R(x, y + 4, 4, 8, "#e0a878");                        // crew figures
    R(x + 8, y + 5, 4, 7, "#e0a878");
    R(x + 26, y + 5, 4, 7, "#e0a878");
    R(x + 1, y + 3, 3, 2, "#d03a3a");                    // little bandanas
    R(x + 9, y + 4, 3, 2, "#d03a3a"); R(x + 27, y + 4, 3, 2, "#d03a3a");
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
      case 2: {  // the beach: sea at the shoreline, then sand and a palm
        seaRows(cam, left, { base: "#3f86d6", wave: "#a8d0f0", deep: "#2a6db5" });
        const sand0 = Math.max(left + 50 - cam, 0);
        const sand1 = Math.min(left + ZONE - cam, VIEW_W);
        if (sand1 > sand0) {
          R(sand0, SEA_TOP - 1, sand1 - sand0, GROUND - SEA_TOP + 1, "#d9b36c");
          R(sand0, GROUND, sand1 - sand0, VIEW_H - GROUND, "#d9b36c");
          R(sand0, SEA_TOP - 1, sand1 - sand0, 1, "#a8d0f0");   // foam line
        }
        palm(left + 150, cam);
        break;
      }
      case 3: {  // fields
        ground(cam, left, "#4e8f3a", "#3d7530");
        for (let i = 0; i < 6; i++) {                      // wheat tufts
          const wx = left + 12 + i * 26;
          const x = wx - cam;
          if (x > -6 && x < VIEW_W) { R(x, GROUND - 4, 1, 4, "#c9a94e"); R(x + 2, GROUND - 5, 1, 5, "#c9a94e"); }
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
        R(left + 78 - cam + (tw % 4) * 4, GROUND - 30, 2, 2, "#f2c14e"); // tossed coin
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
    // walking / fighting / celebrating pirates on the ground
    const fighting = z === 5 || z === 6;
    const celebrating = z === 7;
    const base = GROUND - 13;
    const spread = moving ? [0, 14, -12] : [0, 14, 28];
    pirate(x - cam, base, {
      step, sword: fighting, spark: fighting && step % 4 === 0,
      face: 1, shirt: "#2a6db5", band: "#d03a3a",
    });
    pirate(x - cam - spread[1], base + (celebrating ? Math.abs(Math.sin(t * 4)) * -2 | 0 : 0),
           { step: step + 1, sword: fighting, shirt: "#e8e4d8", band: "#2a6db5" });
    if (!moving || celebrating)
      pirate(x - cam + spread[2], base,
             { step: step + 2, sword: false, shirt: "#4e8f3a", band: "#f2c14e" });
    if (celebrating) {                                     // the flag goes up
      R(x - cam - 16, GROUND - 30, 2, 17, "#5a3820");
      R(x - cam - 14, GROUND - 30, 10, 6, "#d03a3a");
      R(x - cam - 12, GROUND - 28, 3, 2, "#f2c14e");
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
