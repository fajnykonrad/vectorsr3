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
  const SHORE_X = 269;                                   // first sand column
  const GROUND_Y = 33;                                   // surface line
  const BG_FRAMES = 5, BG_FPS = 5;

  const c = document.getElementById("pirate-scene");
  if (!c) return;
  let ctx = c.getContext("2d");

  let elo = 800, eloShown = 800, eloTarget = 800, tweenT0 = 0, tweenDur = 0;

  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
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

  /* ---------------- the crew ---------------- */

  function drawCrew(cam, t, moving) {
    const x = eloToX(eloShown);
    const onLand = x >= SHORE_X;
    const baseY = GROUND_Y - 18;                    // 18-tall: feet on y=32
    if (!onLand) {
      const bob = Math.round(Math.sin(t * 2.2) * 1);
      sheet("ship-sail", Math.floor(t * MANIFEST["ship-sail.png"].fps),
            Math.round(x - 22 - cam), GROUND_Y - 25 + bob);   // hull on the waterline
      return;
    }
    /* the ship stays anchored at the shoreline once they disembark */
    const ax = SHORE_X - 48 - cam;
    if (ax > -46 && ax < VIEW_W)
      sheet("ship-anchor", Math.floor(t * MANIFEST["ship-anchor.png"].fps),
            Math.round(ax), GROUND_Y - 25 + Math.round(Math.sin(t * 2.2) * 1));
    const fighting = eloShown >= 1800 && eloShown < 2400;
    const celebrating = eloShown >= 2400;
    const anim = celebrating ? "pirate-cheer.png" : fighting ? "pirate-fight.png" : "pirate-walk.png";
    const frame = Math.floor(t * MANIFEST[anim].fps);
    sheet(anim, frame, Math.round(x - 8 - cam), baseY);
    sheet(anim, frame + 1, Math.round(x - 22 - cam), baseY);
    if (!moving) sheet(anim, frame + 2, Math.round(x + 6 - cam), baseY);
    if (fighting) {                                  // the castle guard
      sheet("knight-fight", Math.floor(t * 10), 900 - cam, baseY);
      sheet("knight-fight", Math.floor(t * 10) + 1, 1000 - cam, baseY);
    }
  }

  /* ---------------- loop ---------------- */

  function render(cam, t, moving) {
    blitBackground(cam, t);
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
