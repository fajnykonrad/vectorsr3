# Sprite Sheet Spec — Kangaroo Trainer pirate world

## REVISION: background art direction (redo background-1..5 with this style)

The user reviewed the first background frames and wants them redone. The
style must MATCH the pirate sprite sheets you made — same pixel language,
same palette, same outlines:

1. **Style match**: every drawn shape (wave bumps, dunes, bricks, houses,
   castle, gold) carries a 1px `#20222c` outline on its silhouette and flat
   2-3 shade fills, exactly like the pirate sprites. No soft gradients
   inside shapes.
2. **REMOVE the loose object sprites**: no clouds, no trees, no palm, no
   bushes, no fences anywhere. Detail comes from texture and structure, not
   from pasted-on props. (Architecture is allowed: one outlined house
   facade in the town, the castle wall, gate arch, banners, torch sconces.)
3. **More detail through texture**:
   - Sea: 4-5 wave rows, each a run of OUTLINED wave bumps (rounded crest
     ~5px wide, white 1px tip), two blues mixing per row.
   - Beach: outlined dune curves, sand speckles, shells, starfish,
     footprints, pebbles — all with 1px outlines like the sprites.
   - Grass: outlined grass tufts (3px diagonal blades), wheat runs.
   - Town: brick pavement floor, one detailed outlined house facade.
   - Walls: castle wall with outlined crenellations, gate arch, banners,
     torch sconces.
   - Treasure: wooden plank wall, 2 outlined framed paintings, mounted
     shield + cutlass, outlined coin mounds.
4. **HORIZON**: the surface line (sea level, beach top, grass top, town
   floor top, castle ground) must be at the SAME y in every phase. Pick
   one y and keep every ground start there — the horizon may not shift
   between phases.
5. **JAGGED transitions**: every biome boundary must be a jagged,
   multi-step edge — staggered 2-3px teeth and dither steps, NOT one
   straight vertical line. Sea->sand: jagged wet-sand edge. Sand->grass:
   jagged dither band with grass tufts overhanging the sand. Grass->town:
   jagged curb stones. Wall->courtyard: jagged stone edge.
6. **Keep everything else** from the first background spec: sky gradient
   until the beach then uniform daylight, no sky after the wall, flat
   sand (no gradient), brick pavements, red carpet with yellow borders on
   wooden planks, decorated wooden treasure wall, 5-frame loop with only
   waves/foam moving, and NO characters.

## NEW DELIVERABLE: background frames (background-1.png .. background-5.png)

Five frames of the ENTIRE 1280x60 world background, **no characters
anywhere** (no pirates, no ship, no knight — those are drawn separately).
The 5 frames form a looping ambient animation: the only things that move
between frames are waves, foam, and small water/sky details.

Requirements (user-specified, follow exactly):

1. **The sea must have waves** — visible wave rows/crests, animating across
   the 5 frames (crests shift position frame to frame).
2. **Waves must break onto the beach, creating foam** — at the sea/sand
   boundary draw white foam shapes that grow and shrink across the frames.
3. **The area behind the foam must ALSO be filled by water** — the foam
   line sits ON water: water continues behind/above the foam all the way
   to where the sand starts. Never leave sand where foam is breaking.
4. **The beach must NOT have a gradient** — flat, uniform sand color.
5. **The floor for the town, the wall and the castle entrance must be
   stone BRICK pavements** — draw a brick pattern (offset rows of bricks
   with mortar lines), not a flat color with speckles.
6. **The sky must only exist up until the wall** — the castle wall must
   rise to the very top of the frame (full height): no sky above it. After
   the wall (courtyard, castle entrance, treasure room) there is no sky
   either: the backdrop is enclosed castle structure (stone/wooden walls
   full height).
7. **The last phase (treasure room) backdrop must be a decorated wooden
   wall with paintings and stuff** — wooden planks, framed paintings,
   shields/trophies mounted on the wall.
8. **The castle floor must be a red carpet with yellow outlines; outside
   the carpet, lighter wooden flooring** — the carpet runs as a horizontal
   strip along the walkway with a yellow border on its top and bottom
   edges; left and right of the carpet strip: lighter wood planks (floor
   boards). This applies to the courtyard, castle entrance and treasure
   room floors.
9. **The sky is a gradient up until the beach; from the beach onward to
   the right it is a uniform daylight sky** — left part: dark navy
   blending to lighter blue; from the beach eastward: one consistent
   daylight blue (no further gradient), until the wall.

Frame-by-frame animation guide: shift wave crests ~2px per frame; foam
blobs grow frame 1-3 and shrink 3-5; keep everything else static between
frames.

Output: `background-1.png` .. `background-5.png` (1280x60 each, RGB, no
transparency needed), plus `background.json`: `{"frames": 5, "frameW":
1280, "frameH": 60, "fps": 5}`.

---

# Sprite Sheet Spec — Kangaroo Trainer pirate world

You are producing pixel-art sprite sheets that will be composited onto an
existing animated pixel world (a sea/beach/fields/town/castle scene). The
world renders at 1 file pixel = 1 logical game pixel, scaled up 3x with
nearest-neighbor on screen. Everything must be crisp pixel art.

## Deliverables

A generator script `trainer/static/sprites/generate_sprites.py` that draws
every sheet with PIL (Pillow) using a shared palette and shared character
definition, and writes these PNGs (RGBA, transparent background, 1px
"silhouette" outline where the shape meets nothing) into the same folder:

| File | Frames | Frame size | Description |
|---|---|---|---|
| `pirate-walk.png` | 6 | 16x18 | pirate walking RIGHT, walk cycle |
| `pirate-fight.png` | 4 | 16x18 | pirate fighting RIGHT: ready, wind-up, strike, recover |
| `pirate-cheer.png` | 3 | 16x18 | celebrating: arms up, jump, land |
| `ship-sail.png` | 4 | 44x26 | ship facing RIGHT with 3 pirates aboard, sail full |
| `ship-anchor.png` | 2 | 44x26 | ship anchored, sail furled |
| `knight-fight.png` | 3 | 16x18 | enemy knight facing LEFT vs the pirate |

Plus `manifest.json`:

```json
{
  "pirate-walk.png":  { "frames": 6, "frameW": 16, "frameH": 18, "fps": 10 },
  "ship-sail.png":    { "frames": 4, "frameW": 44, "frameH": 26, "fps": 8 },
  "...": { "...": "..." }
}
```

Run it with the project venv: `cd ~/datathon-UPC-maths-qualcomm-arduino-unoq && .venv/bin/python trainer/static/sprites/generate_sprites.py`

## Art direction (match the world that already exists)

Fixed palette (use exactly these hex colors):

- skin `#e0a878`, skin shade `#c98a5e`
- bandana red `#d03a3a` (+ dark `#a82a2a`)
- shirt blue `#2a6db5` (+ light `#5a9be0`), shirt white `#e8e4d8`, shirt green `#4e8f3a`
- trousers `#3a3a52`, boots `#23233a`
- cutlass blade `#c9ccd4` (+ dark `#8a90a0`), hilt `#8a5a2e`
- ship hull `#6a4426` / `#5a3820`, sail `#e8e4d8`, stripe `#a04b3a`,
  mast `#5a3820`, flag `#d03a3a`
- knight armor `#7a8296` / dark `#5a6272`, shield `#a04b3a`
- outline `#20222c`

Rules:

1. Side view, **facing right** for pirates and ship, **facing left** for the knight.
2. Feet on the **bottom row** (y = frameH - 1) in every frame; never float.
3. Every shape gets a 1px `#20222c` outline on its silhouette edge.
4. Round the character: 2px-radius head disc, 1px diagonal limbs where a
   pose moves (use diagonal pixel runs, not staircases of single offset
   pixels).
5. The pirate MUST be the same character in every frame: same bandana with
   a knot tail on the left, same eye position, same belt. Frames differ
   ONLY in pose.
6. Ship: curved hull (stepped bow and stern), one mast, rounded sail
   (rows shrink toward the top), red pennant, 3 tiny crew figures.
7. No text, no watermarks, no drop shadows, no gradients — flat fills
   with 1px shade rows only.
8. Walk cycle poses (6): contact right, recoil, passing, high point,
   contact left, passing. Body bobs 1px on frames 2 and 5.
9. Fight poses (4): blade up-diagonal, blade back with body leaning back,
   blade straight forward with lunge, blade recovering down.
10. Knight poses (3): shield up, shield mid with sword raised, sword swung.

## Implementation guidance

- Draw with explicit pixel maps or rect/disc helpers on a 16x18 (or
  44x26) RGBA canvas per frame; paste frames side by side into the sheet.
- Poses as data: define each pose as a dict of part offsets
  (head, bandana, torso, arm, legs, blade) drawn with the shared palette —
  this keeps every frame consistent.
- After generating, verify each PNG with PIL: open it, assert exact frame
  size, assert every sheet's width == frames * frameW, assert fully
  transparent background (corner pixel alpha == 0), print a summary.
- Write `manifest.json` with the table above.

## Done means

All 6 PNGs + manifest.json exist in `trainer/static/sprites/`, the
verification passes, and `generate_sprites.py` re-runs cleanly.
