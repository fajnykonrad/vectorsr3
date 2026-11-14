/* The pirate attack: a Krillion-style pixel world driven by the general Elo.
 *
 * The world background is a 5-frame looping animation (background-1..5.png,
 * 1280x60 each, baked by generate_sprites.py) — waves crest, foam breaks,
 * water shimmers. The crew, ship and knights are sprite-sheet frames from
 * trainer/static/sprites/ (manifest.json). The general Elo places the crew
 * on the world map (300..2700, 300 per phase); the camera follows and
 * clamps at the world's end, so at max Elo nothing moves.
 *
 * Layout facts of the baked background (verified by probe):
 *   shoreline (first sand) x=269, surface line y=33, grass from x=380,
 *   full-height castle wall from x=760, red carpet 830..1244.
 */
(function () {
  "use strict";

  const VIEW_W = 200, VIEW_H = 60;
  const WORLD_W = 1280;
  const ELO_BASE = 300, ELO_PER_ZONE = 300, ZONES = 8;
  const PX_PER_ELO = WORLD_W / (ELO_PER_ZONE * ZONES);   // 0.533 px per point
  const SHORE_X = 310;                                   // where dry sand starts
  const GROUND_Y = 33;                                   // surface line
  const BG_FRAMES = 5, BG_FPS = 5;

  const c = document.getElementById("pirate-scene");
  if (!c) return;
  let ctx = c.getContext("2d");

  let elo = 800, eloShown = 800, eloTarget = 800, tweenT0 = 0, tweenDur = 0;

  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const smooth = t => { t = clamp(t, 0, 1); return t * t * (3 - 2 * t); };
  const RGB = hex => [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16),
                      parseInt(hex.slice(5, 7), 16)];
  const mix = (a, b, t) => [
    Math.round(a[0] + (b[0] - a[0]) * t),
    Math.round(a[1] + (b[1] - a[1]) * t),
    Math.round(a[2] + (b[2] - a[2]) * t)];
  const eloToX = e => clamp(e - ELO_BASE, 0, ELO_PER_ZONE * ZONES) * PX_PER_ELO;
  const zoneOf = x => clamp(Math.floor(x / ELO_PER_ZONE / PX_PER_ELO), 0, ZONES - 1);
  const shoreElo = ELO_BASE + SHORE_X / PX_PER_ELO;      // ~804

  /* ---------------- assets ---------------- */

  const MANIFEST = {
    "pirate-walk.png":  { frames: 6, frameW: 16, frameH: 18, fps: 10 },
    "pirate-fight.png": { frames: 4, frameW: 16, frameH: 18, fps: 10 },
    "pirate-cheer.png": { frames: 3, frameW: 16, frameH: 18, fps: 6 },
    "knight-fight.png": { frames: 3, frameW: 16, frameH: 18, fps: 10 },
    "ship-sail.png":    { frames: 4, frameW: 44, frameH: 26, fps: 8 },
    "ship-anchor.png":  { frames: 2, frameW: 44, frameH: 26, fps: 4 },
    "palm.png":         { frames: 1, frameW: 32, frameH: 32, fps: 1 },
    "bush.png":         { frames: 1, frameW: 32, frameH: 32, fps: 1 },
    "barrel.png":       { frames: 1, frameW: 32, frameH: 32, fps: 1 },
  };
  const bgFrames = [];
  const sheets = {};
  let loadedCount = 0, onReady = null;

  function loadAll() {
    const done = () => { if (++loadedCount >= expected() && onReady) { const f = onReady; onReady = null; f(); } };
    const expected = () => BG_FRAMES + Object.keys(MANIFEST).length;
    for (let i = 1; i <= BG_FRAMES; i++) {
      const img = new Image();
      img.onload = done;
      img.src = `/static/sprites/background-${i}.png`;
      bgFrames.push(img);
    }
    for (const name of Object.keys(MANIFEST)) {
      const img = new Image();
      img.onload = done;
      img.src = `/static/sprites/${name}`;
      sheets[name] = { img, ...MANIFEST[name] };
    }
  }

  function blitBackground(cam, time) {
    const img = bgFrames[Math.floor(time * BG_FPS) % BG_FRAMES];
    if (img.complete) ctx.drawImage(img, cam, 0, VIEW_W, VIEW_H, 0, 0, VIEW_W, VIEW_H);
  }

  function sheet(name, frame, sx, sy, flip) {
    const s = sheets[name];
    if (!s || !s.img.complete) return;
    frame = ((frame % s.frames) + s.frames) % s.frames;
    const fx = frame * s.frameW;
    if (flip) {
      ctx.save();
      ctx.translate(sx + s.frameW, sy);
      ctx.scale(-1, 1);
      ctx.drawImage(s.img, fx, 0, s.frameW, s.frameH, 0, 0, s.frameW, s.frameH);
      ctx.restore();
    } else {
      ctx.drawImage(s.img, fx, 0, s.frameW, s.frameH, sx, sy, s.frameW, s.frameH);
    }
  }

  /* ---------------- scenery and the crew ---------------- */

  function drawProps(cam) {
    /* user-made scenery: palms on the sand, bushes on the grass, barrels
       in town — bottomY is where each prop's base sits (larger = closer) */
    const props = [
      ["palm.png", 300, 36], ["palm.png", 332, 36], ["palm.png", 362, 36],
      ["bush.png", 400, 35], ["bush.png", 448, 38], ["bush.png", 496, 36],
      ["bush.png", 544, 39], ["bush.png", 592, 37], ["bush.png", 640, 35],
      ["barrel.png", 782, 36], ["barrel.png", 818, 37],
    ];
    for (const [name, wx, bottomY] of props) {
      const s = sheets[name];
      if (!s || !s.img.complete) continue;
      const sx = Math.round(wx - cam);
      if (sx < -34 || sx > VIEW_W) continue;
      ctx.drawImage(s.img, 0, 0, s.frameW, s.frameH, sx, bottomY - 32, s.frameW, s.frameH);
    }
  }

  function drawCrew(cam, t, moving) {
    /* the crew never walks off the right edge, even at max Elo */
    const x = Math.min(eloToX(eloShown), WORLD_W - 26);
    const onLand = x >= SHORE_X;
    const baseY = VIEW_H - 30;                      // feet 12px from the bottom
    if (!onLand) {
      const bob = Math.round(Math.sin(t * 2.2) * 1);
      sheet("ship-sail.png", Math.floor(t * MANIFEST["ship-sail.png"].fps),
            Math.round(x - 22 - cam), GROUND_Y - 25 + bob);   // hull on the waterline
      return;
    }
    /* the ship stays anchored at the shoreline once they disembark */
    const ax = SHORE_X - 48 - cam;
    if (ax > -46 && ax < VIEW_W)
      sheet("ship-anchor.png", Math.floor(t * MANIFEST["ship-anchor.png"].fps),
            Math.round(ax), GROUND_Y - 25 + Math.round(Math.sin(t * 2.2) * 1));
    const fighting = eloShown >= 1860 && eloShown < 2400;   // the castle region
    const celebrating = eloShown >= 2400;
    const anim = celebrating ? "pirate-cheer.png" : fighting ? "pirate-fight.png" : "pirate-walk.png";
    const fps = MANIFEST[anim].fps;
    const frame = Math.floor(t * fps);
    /* three pirates at all times; walk/fight/cheer only while moving,
       a gentle idle bob when standing */
    const baseX = [x - 8, x - 22, x + 6];
    const poses = moving ? [frame, frame + 1, frame + 2] : [0, 0, 0];
    const bobs = moving ? [0, 0, 0]
                        : [Math.round(Math.sin(t * 2) * 1),
                           Math.round(Math.sin(t * 2 + 2.1) * 1),
                           Math.round(Math.sin(t * 2 + 4.2) * 1)];
    for (let i = 0; i < 3; i++) {
      const sx = clamp(Math.round(baseX[i] - cam), 2, VIEW_W - 18);
      sheet(anim, poses[i], sx, baseY + bobs[i]);
    }
    if (fighting) {                                  // the castle guard
      sheet("knight-fight", Math.floor(t * 10), 900 - cam, baseY);
      sheet("knight-fight", Math.floor(t * 10) + 1, 1000 - cam, baseY);
    }
  }

  /* ---------------- loop ---------------- */

  function render(cam, t, moving) {
    blitBackground(cam, t);
    drawProps(cam);
    drawCrew(cam, t, moving);
  }

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
    render(cam, time, moving);

    requestAnimationFrame(frame);
  }

  window.Pirates = {
    init() {
      eloShown = eloTarget = elo = 800;
      loadAll();
      onReady = () => requestAnimationFrame(frame);
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
    /* debug: render one full frame into any 200x60 context, so a script
       can record the whole world as an animation */
    captureFrame(cam, time, eloValue, targetCtx) {
      const savedCtx = ctx, savedShown = eloShown;
      ctx = targetCtx; eloShown = eloValue;
      const camv = clamp(cam, 0, WORLD_W - VIEW_W);
      render(camv, time, true);
      ctx = savedCtx; eloShown = savedShown;
    },
  };
})();
