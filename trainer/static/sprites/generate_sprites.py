#!/usr/bin/env python3
"""Kangaroo Trainer - pirate world pixel-art sprite sheet generator.

Implements trainer/static/sprites/SPEC.md: draws every sheet with Pillow
on a fixed palette, shared character rigs, 1px silhouette outlines and a
transparent background, then verifies the output and writes manifest.json.

Usage:
    .venv/bin/python trainer/static/sprites/generate_sprites.py [--dump]

--dump prints an ASCII map of every frame (debug QA aid).
"""

import json
import os
import sys

from PIL import Image

SPRITE_DIR = os.path.dirname(os.path.abspath(__file__))

# ------------------------------------------------------------------ palette
PAL = {
    "skin":        "#e0a878",
    "skin_shade":  "#c98a5e",
    "bandana":     "#d03a3a",
    "bandana_dk":  "#a82a2a",
    "shirt":       "#2a6db5",
    "shirt_light": "#5a9be0",
    "shirt_white": "#e8e4d8",
    "shirt_green": "#4e8f3a",
    "trousers":    "#3a3a52",
    "boots":       "#23233a",
    "blade":       "#c9ccd4",
    "blade_dk":    "#8a90a0",
    "hilt":        "#8a5a2e",
    "hull":        "#6a4426",
    "hull_dk":     "#5a3820",
    "stripe":      "#a04b3a",
    "mast":        "#5a3820",
    "flag":        "d03a3a",  # fixed below (same red as bandana)
    "armor":       "#7a8296",
    "armor_dk":    "#5a6272",
    "shield":      "#a04b3a",
    "outline":     "#20222c",
}
PAL["flag"] = "#d03a3a"

RGB = {k: tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) for k, h in PAL.items()}

# ascii glyphs for the --dump QA mode
GLYPH = {
    "outline": "#", "skin": "s", "skin_shade": "S", "bandana": "r",
    "bandana_dk": "R", "shirt": "b", "shirt_light": "l", "shirt_white": "w",
    "shirt_green": "g", "trousers": "p", "boots": "B", "blade": "c",
    "blade_dk": "C", "hilt": "h", "hull": "H", "hull_dk": "d", "stripe": "t",
    "mast": "m", "flag": "f", "armor": "a", "armor_dk": "A", "shield": "v",
}

# ------------------------------------------------------------------ helpers


def new(w, h):
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def px(img, x, y, c):
    if 0 <= x < img.width and 0 <= y < img.height:
        img.putpixel((x, y), RGB[c] + (255,))


def rect(img, x0, y0, x1, y1, c):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            px(img, x, y, c)


def line2(img, x0, y0, x1, y1, c):
    """2px-thick Bresenham run. 2x2 stamps give chunky diagonal limbs
    (continuous runs, not staircases of single offset pixels)."""
    dx = abs(x1 - x0)
    sx = 1 if x0 < x1 else -1
    dy = -abs(y1 - y0)
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        rect(img, x0, y0, x0 + 1, y0 + 1, c)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def disc5(img, cx, cy, c):
    """Rounded 2px-radius head disc: row half-widths 1,2,2,2,1."""
    for i, hw in enumerate((1, 2, 2, 2, 1)):
        y = cy - 2 + i
        for x in range(cx - hw, cx + hw + 1):
            px(img, x, y, c)


def boot(img, x, y0, d=1, toe=False):
    """Foot occupying rows y0..y0+1, toe pointing d(+1 right / -1 left).
    toe=True: heel raised, only the bottom (toe) row touches the ground."""
    if toe:
        px(img, x, y0 + 1, "boots")
        px(img, x + d, y0 + 1, "boots")
        return
    px(img, x, y0, "boots")
    px(img, x + d, y0, "boots")
    for i in (0, 1, 2):
        px(img, x + i * d, y0 + 1, "boots")


def cutlass(img, hx, hy, dx, dy, length, edge):
    """Sword anchored at the hand: 1px hilt, then `length` blade px plus a
    1px dark edge offset `edge` (the blade's shaded side)."""
    px(img, hx + dx, hy + dy, "hilt")
    for i in range(2, length + 2):
        px(img, hx + dx * i, hy + dy * i, "blade")
        px(img, hx + dx * i + edge[0], hy + dy * i + edge[1], "blade_dk")


def add_outline(img):
    """1px #20222c outline on every silhouette edge (where the shape meets
    nothing / transparent)."""
    w, h = img.size
    p = img.load()
    solid = [[p[x, y][3] > 0 for y in range(h)] for x in range(w)]
    for y in range(h):
        for x in range(w):
            if solid[x][y]:
                continue
            if ((x > 0 and solid[x - 1][y]) or (x < w - 1 and solid[x + 1][y])
                    or (y > 0 and solid[x][y - 1])
                    or (y < h - 1 and solid[x][y + 1])):
                p[x, y] = RGB["outline"] + (255,)


# ------------------------------------------------------------------- pirate
# Rig (16x18, facing right, feet always on row y=17):
#   head disc centre (cx+lean, 4+bob); torso y 7..11; belt y 11;
#   shoulders y 8+bob: near (cx+2) / far (cx-3); hips y 12+bob:
#   near (cx+1) / far (cx-2); ankle y 15 (16 when toe), boots y 16..17.
CX = 7


def draw_pirate(img, pose):
    bob = pose.get("bob", 0)
    cx = CX + pose.get("lean", 0)

    # far arm (behind torso)
    ax, ay = pose["arm_far"]
    sx, sy = cx - 3, 8 + bob
    line2(img, sx, sy, sx + ax, sy + ay, "shirt")
    rect(img, sx + ax, sy + ay, sx + ax + 1, sy + ay + 1, "skin")

    # legs (feet x is absolute relative to cx, always on the bottom rows)
    for which in ("far", "near"):
        hip_dx, foot_dx, toe = pose["legs"][which]
        ax0 = cx + foot_dx
        line2(img, cx + hip_dx, 12 + bob, ax0, 16 if toe else 15, "trousers")
        boot(img, ax0, 16, 1, toe)

    # torso + 1px shoulder highlight + belt (same belt in every frame)
    rect(img, cx - 3, 7 + bob, cx + 2, 11 + bob, "shirt")
    rect(img, cx - 3, 7 + bob, cx + 2, 7 + bob, "shirt_light")
    rect(img, cx - 3, 11 + bob, cx + 2, 11 + bob, "hilt")
    px(img, cx + 2, 11 + bob, "shirt_white")  # buckle

    # head: skin disc, bandana band, knot tail on the LEFT, fixed eye
    disc5(img, cx, 4 + bob, "skin")
    rect(img, cx - 1, 2 + bob, cx + 1, 2 + bob, "bandana_dk")
    rect(img, cx - 2, 3 + bob, cx + 2, 3 + bob, "bandana")
    px(img, cx - 3, 3 + bob, "bandana")       # knot
    px(img, cx - 4, 4 + bob, "bandana_dk")    # tail tip
    px(img, cx + 1, 4 + bob, "outline")       # eye
    rect(img, cx - 1, 6 + bob, cx + 1, 6 + bob, "skin_shade")

    # near arm + cutlass (blade rides the hand, always a up-forward guard)
    ax, ay = pose["arm_near"]
    sx, sy = cx + 2, 8 + bob
    hx, hy = sx + ax, sy + ay
    elbow = pose.get("elbow_near")
    if elbow:  # two-segment arm (route around the head, e.g. wind-up)
        exv, eyv = elbow
        mx, my = sx + exv, sy + eyv
        line2(img, sx, sy, mx, my, "shirt")
        line2(img, mx, my, hx, hy, "shirt")
    else:
        line2(img, sx, sy, hx, hy, "shirt")
    rect(img, hx, hy, hx + 1, hy + 1, "skin")
    if "blade" in pose:
        dx, dy, ln, edge = pose["blade"]
        cutlass(img, hx, hy, dx, dy, ln, edge)


# 6-frame walk: contact right, recoil, passing, high point, contact left,
# passing. Body bobs 1px down on frames 2 and 5; the legs shorten instead
# of floating so the feet stay on the bottom row in every frame.
WALK = [
    dict(legs={"near": (1, 4, False), "far": (-2, -3, True)},
         arm_near=(-3, 3), arm_far=(3, 4), blade=(1, -1, 4, (0, -1))),       # contact right
    dict(bob=1, legs={"near": (1, 2, False), "far": (-2, -2, False)},
         arm_near=(-1, 2), arm_far=(1, 3), blade=(1, -1, 4, (0, -1))),       # recoil
    dict(legs={"near": (1, 1, False), "far": (-2, 2, True)},
         arm_near=(1, 3), arm_far=(-2, 3), blade=(1, -1, 4, (0, -1))),       # passing
    dict(bob=-1, legs={"near": (1, -1, False), "far": (-2, 3, False)},
         arm_near=(3, 2), arm_far=(-3, 3), blade=(1, -1, 3, (0, -1))),       # high point
    dict(bob=1, legs={"near": (1, -3, True), "far": (-2, 4, False)},
         arm_near=(2, 2), arm_far=(-2, 3), blade=(1, -1, 3, (0, -1))),       # contact left
    dict(legs={"near": (1, 2, True), "far": (-2, 1, False)},
         arm_near=(0, 3), arm_far=(0, 4), blade=(1, -1, 4, (0, -1))),        # passing
]

# 4-frame fight: ready (blade up-diagonal), wind-up (blade back, leaning
# back), strike (straight forward thrust with a lunge), recover (down).
FIGHT = [
    dict(legs={"near": (1, 2, False), "far": (-2, -2, False)},
         arm_near=(2, -2), arm_far=(-2, 3), blade=(1, -1, 3, (0, -1))),      # ready
    dict(lean=-1, legs={"near": (1, 1, False), "far": (-2, -2, False)},
         arm_near=(-5, -2), elbow_near=(-3, 0), arm_far=(4, 3),
         blade=(-1, -1, 2, (0, -1))),                                # wind-up
    dict(legs={"near": (1, 5, False), "far": (-2, -3, True)},
         arm_near=(2, 0), arm_far=(-3, 3), blade=(1, 0, 3, (0, 1))),         # strike
    dict(legs={"near": (1, 2, False), "far": (-2, -2, False)},
         arm_near=(2, 1), arm_far=(2, 3), blade=(1, 1, 3, (1, 0))),          # recover
]

# 3-frame cheer: arms up, jump (stretched, feet still grounded), land
# (crouch). Cutlass stays raised - same character, same weapon.
CHEER = [
    dict(legs={"near": (1, 2, False), "far": (-2, -2, False)},
         arm_near=(2, -3), arm_far=(-2, -3), blade=(1, -1, 3, (0, -1))),     # arms up
    dict(bob=-1, legs={"near": (1, 3, False), "far": (-2, -3, False)},
         arm_near=(2, -4), arm_far=(-2, -4), blade=(1, -1, 2, (0, -1))),     # jump
    dict(bob=1, legs={"near": (1, 3, False), "far": (-2, -2, False)},
         arm_near=(3, 2), arm_far=(-3, 2), blade=(1, 1, 2, (1, 0))),         # land
]

# ------------------------------------------------------------------- knight
# 16x18, facing LEFT. Front side is the left edge, so boots' toes point
# left and the shield rides the front.
KX = 9


def shield(img, x0, y0):
    """4x5 rounded heater shield, top-left anchored."""
    rect(img, x0 + 1, y0, x0 + 2, y0, "shield")
    rect(img, x0, y0 + 1, x0 + 3, y0 + 3, "shield")
    rect(img, x0 + 1, y0 + 4, x0 + 2, y0 + 4, "shield")


def draw_knight(img, pose):
    bob = pose.get("bob", 0)
    cx = KX + pose.get("lean", 0)

    # far (back/right) arm behind the torso
    ax, ay = pose["arm_far"]
    sx, sy = cx + 2, 8 + bob
    fhx, fhy = sx + ax, sy + ay
    line2(img, sx, sy, fhx, fhy, "armor")
    rect(img, fhx, fhy, fhx + 1, fhy + 1, "hilt")  # glove

    # legs (dark armour), boots toe left
    for which in ("far", "near"):
        hip_dx, foot_dx, toe = pose["legs"][which]
        ax0 = cx + foot_dx
        line2(img, cx + hip_dx, 12 + bob, ax0, 16 if toe else 15, "armor_dk")
        boot(img, ax0, 16, -1, toe)

    # torso + belt (brown leather, buckle on the front-left)
    rect(img, cx - 3, 7 + bob, cx + 2, 11 + bob, "armor")
    rect(img, cx + 2, 7 + bob, cx + 2, 10 + bob, "armor_dk")  # back shade col
    rect(img, cx - 3, 11 + bob, cx + 2, 11 + bob, "hilt")
    px(img, cx - 3, 11 + bob, "shirt_white")  # buckle

    # head: armoured disc, dark crest, plume falling back (right), visor
    disc5(img, cx, 4 + bob, "armor")
    rect(img, cx - 1, 2 + bob, cx + 1, 2 + bob, "armor_dk")
    px(img, cx, 1 + bob, "stripe")     # plume
    px(img, cx + 1, bob, "stripe")
    rect(img, cx - 2, 4 + bob, cx - 1, 4 + bob, "outline")  # visor slit
    rect(img, cx - 1, 6 + bob, cx + 1, 6 + bob, "armor_dk")

    # near (front) arm + shield + sword on top
    ax, ay = pose["arm_near"]
    sx, sy = cx - 3, 8 + bob
    line2(img, sx, sy, sx + ax, sy + ay, "armor")
    rect(img, sx + ax, sy + ay, sx + ax + 1, sy + ay + 1, "hilt")
    if "shield_at" in pose:
        shield(img, pose["shield_at"][0], pose["shield_at"][1])
    if "sword" in pose:
        if pose.get("sword_hand") == "far":
            hx, hy = fhx, fhy
        else:
            hx, hy = sx + ax, sy + ay
        dx, dy, ln, edge = pose["sword"]
        cutlass(img, hx, hy, dx, dy, ln, edge)


# 3 knight poses: shield up, shield mid with sword raised, sword swung.
KNIGHT = [
    dict(legs={"near": (-1, -2, False), "far": (1, 2, False)},
         arm_near=(-3, -2), arm_far=(0, 3), sword_hand="far",
         shield_at=(1, 2), sword=(1, 1, 2, (1, 0))),                  # shield up
    dict(legs={"near": (-1, -1, False), "far": (1, 2, False)},
         arm_near=(-2, 1), arm_far=(0, -4), sword_hand="far",
         shield_at=(1, 7), sword=(1, -1, 2, (0, -1))),                # shield mid, sword raised
    dict(legs={"near": (-1, -3, False), "far": (1, 3, False)},
         arm_near=(-3, 0), arm_far=(-3, 2),
         shield_at=(1, 11), sword=(-1, 0, 2, (0, 1))),                # sword swung
]

# --------------------------------------------------------------------- ship
# 44x26, facing right. Hull bottom (waterline) always on row y=25.
HULL_ROWS = [  # (y, x0, x1) - curved hull, wider toward the keel
    (19, 5, 38), (20, 6, 37), (21, 7, 36), (22, 8, 35),
    (23, 9, 34), (24, 10, 33), (25, 12, 31),
]
SAIL_ROWS = [  # (y, x0, x1) - rounded sail, rows shrink toward the top
    (8, 17, 28), (9, 15, 30), (10, 14, 31), (11, 13, 32),
    (12, 13, 32), (13, 14, 31), (14, 15, 30), (15, 17, 28),
]
CREW = [(12, "shirt_white"), (16, "shirt_green"), (31, "shirt")]


def draw_ship(img, billow=0, pennant=(5, 2), furled=False, crew_wave=False,
              anchor=False):
    # hull
    for y, x0, x1 in HULL_ROWS:
        rect(img, x0, y, x1, y, "hull")
    rect(img, 5, 19, 38, 19, "hull_dk")   # deck edge (1px shade row)
    rect(img, 12, 25, 31, 25, "hull_dk")  # keel shade
    rect(img, 7, 21, 36, 21, "stripe")    # red stripe along the hull

    # stepped raised stern (left) and forecastle (right)
    rect(img, 6, 14, 8, 14, "hull")
    rect(img, 5, 15, 9, 18, "hull")
    rect(img, 5, 15, 9, 15, "hull_dk")
    rect(img, 35, 15, 37, 15, "hull")
    rect(img, 34, 16, 38, 18, "hull")
    rect(img, 34, 16, 38, 16, "hull_dk")

    # bowsprit pointing forward (right)
    for x, y in ((38, 15), (39, 14), (40, 13), (41, 12)):
        px(img, x, y, "mast")

    # anchor, hung from the bowsprit area (anchored pose only)
    if anchor:
        for y in range(13, 17):
            px(img, 41, y, "mast")                    # rope
        px(img, 41, 17, "mast")
        rect(img, 39, 18, 43, 18, "mast")             # stock
        for y in range(19, 22):
            px(img, 41, y, "mast")                    # shank
        rect(img, 39, 22, 43, 22, "mast")             # bottom arms
        px(img, 39, 21, "mast")
        px(img, 43, 21, "mast")                       # flukes

    # mast + yard
    rect(img, 20, 3, 21, 19, "mast")
    rect(img, 11, 7, 31, 7, "mast")

    # sail: full and billowing, or furled on the yard
    if furled:
        rect(img, 13, 8, 30, 8, "shirt_white")
        rect(img, 15, 9, 28, 9, "shirt_white")
        px(img, 18, 8, "mast")
        px(img, 18, 9, "mast")
        px(img, 26, 8, "mast")
        px(img, 26, 9, "mast")                        # lashings
    else:
        for y, x0, x1 in SAIL_ROWS:
            extra = billow if 9 <= y <= 14 else (billow + 1) // 2
            rect(img, x0, y, x1 + extra, y, "shirt_white")

    # red pennant streaming back (left) from the mast top
    l3, l2 = pennant
    for i in range(l2):
        px(img, 19 - i, 2, "flag")
    for i in range(l3):
        px(img, 19 - i, 3, "flag")

    # 3 tiny crew figures on the deck
    for x, shirt in CREW:
        px(img, x, 16, "skin")
        px(img, x, 17, shirt)
        px(img, x, 18, "boots")
    if crew_wave:  # the middle sailor waves on the second anchor frame
        px(img, 15, 16, "shirt_green")


SAIL_FRAMES = [dict(billow=0, pennant=(5, 2)), dict(billow=1, pennant=(6, 3)),
               dict(billow=2, pennant=(5, 1)), dict(billow=1, pennant=(6, 2))]
ANCHOR_FRAMES = [dict(pennant=(5, 2), anchor=True),
                 dict(pennant=(3, 1), anchor=True, crew_wave=True)]

# ------------------------------------------------------------ sheet writing

SHEETS = [
    ("pirate-walk", 16, 18, 10, [lambda im, p=p: draw_pirate(im, p) for p in WALK]),
    ("pirate-fight", 16, 18, 10, [lambda im, p=p: draw_pirate(im, p) for p in FIGHT]),
    ("pirate-cheer", 16, 18, 6, [lambda im, p=p: draw_pirate(im, p) for p in CHEER]),
    ("knight-fight", 16, 18, 10, [lambda im, p=p: draw_knight(im, p) for p in KNIGHT]),
    ("ship-sail", 44, 26, 8, [lambda im, p=p: draw_ship(im, **p) for p in SAIL_FRAMES]),
    ("ship-anchor", 44, 26, 4, [lambda im, p=p: draw_ship(im, **p) for p in ANCHOR_FRAMES]),
]


def build_sheets():
    manifest = {}
    for name, fw, fh, fps, drawers in SHEETS:
        sheet = new(fw * len(drawers), fh)
        for i, draw in enumerate(drawers):
            frame = new(fw, fh)
            draw(frame)
            add_outline(frame)
            sheet.paste(frame, (i * fw, 0))
        path = os.path.join(SPRITE_DIR, name + ".png")
        sheet.save(path)
        manifest[name + ".png"] = {"frames": len(drawers), "frameW": fw,
                                   "frameH": fh, "fps": fps}
        print(f"wrote {name + '.png'}  {sheet.width}x{sheet.height} "
              f"({len(drawers)} frames of {fw}x{fh})")
    with open(os.path.join(SPRITE_DIR, "manifest.json"), "w") as fh_:
        json.dump(manifest, fh_, indent=2)
        fh_.write("\n")
    print("wrote manifest.json")


def verify():
    print("verify:")
    ok = True
    with open(os.path.join(SPRITE_DIR, "manifest.json")) as fh_:
        manifest = json.load(fh_)
    for fname, meta in sorted(manifest.items()):
        path = os.path.join(SPRITE_DIR, fname)
        img = Image.open(path).convert("RGBA")
        fw, fh_ = meta["frameW"], meta["frameH"]
        expect = (meta["frames"] * fw, fh_)
        checks = []

        def chk(label, cond):
            nonlocal ok
            checks.append(label)
            if not cond:
                ok = False
                checks[-1] += " <- FAIL"

        chk(f"size {img.width}x{img.height} == {expect[0]}x{expect[1]}",
            img.size == expect)
        p = img.load()
        corners = [p[0, 0], p[img.width - 1, 0], p[0, img.height - 1],
                   p[img.width - 1, img.height - 1]]
        chk("transparent background (all corners alpha=0)",
            all(c[3] == 0 for c in corners))
        grounded = True
        for f in range(meta["frames"]):
            row = [p[x, img.height - 1][3]
                   for x in range(f * fw, (f + 1) * fw)]
            if not any(a for a in row):
                grounded = False
        chk("bottom row touched in every frame", grounded)
        colours = {p[x, y] for y in range(img.height) for x in range(img.width)
                   if p[x, y][3] > 0}
        allowed = {v + (255,) for v in RGB.values()}
        bad = colours - allowed
        chk("fixed palette only" + (f" (stray: {sorted(bad)})" if bad else ""),
            not bad)
        print(f"  {fname}: " + "; ".join(checks))
    return ok


def dump():
    """ASCII QA dump of every frame."""
    for name, fw, fh, _fps, drawers in SHEETS:
        print(f"== {name} ==")
        for i in range(len(drawers)):
            frame = new(fw, fh)
            drawers[i](frame)
            add_outline(frame)
            p = frame.load()
            print(f"-- frame {i}")
            for y in range(fh):
                row = []
                for x in range(fw):
                    rgba = p[x, y]
                    g = "."
                    if rgba[3]:
                        best, bd = None, 999
                        for k, v in RGB.items():
                            d = sum(abs(a - b) for a, b in zip(v, rgba[:3]))
                            if d < bd:
                                bd, best = d, k
                        g = GLYPH.get(best, "?")
                    row.append(g)
                print("".join(row))



# ------------------------------------------- background frames (revision 2)
# Redone in the pirate-sprite art direction: flat 2-3 shade fills and a
# 1px #20222c silhouette outline on EVERY drawn shape. Shapes are drawn on
# a transparent "props" layer which is outlined exactly like the character
# sprites, then composited over the flat ground base.
# One fixed horizon row for every phase; jagged multi-step biome
# boundaries; no clouds/palm/bush/fence/sun; only waves, foam and water
# glints animate (period-10 patterns, seamless over 5 frames).

SKY_NAVY   = (0x16, 0x23, 0x3F)
SKY_DAY    = (0x7E, 0xC0, 0xEE)
SEA_DEEP   = (0x1D, 0x4F, 0x8F)
SEA_MID    = (0x2B, 0x6B, 0xB5)
SEA_LIGHT  = (0x3F, 0x86, 0xC9)
SEA_CREST  = (0x6D, 0xB2, 0xE8)
SPARK      = (0xCF, 0xE8, 0xF8)
FOAM       = (0xF2, 0xF7, 0xFB)
SAND       = (0xE9, 0xD6, 0xA1)
SAND_DK    = (0xD9, 0xC2, 0x8C)
SAND_WET   = (0xD5, 0xC0, 0x8B)
GRASS      = (0x4E, 0x8F, 0x3A)
GRASS_LT   = (0x67, 0xA9, 0x4C)
STONE_FACE = (0x9F, 0xA0, 0xAA)
STONE_LT   = (0xB4, 0xB5, 0xBF)
MORTAR     = (0x5C, 0x5D, 0x66)
WOOD_LT    = (0xC9, 0x9A, 0x5E)
WOOD_MD    = (0xA8, 0x7B, 0x44)
WOOD_DK    = (0x7C, 0x57, 0x30)
WOOD_SEAM  = (0x63, 0x45, 0x2A)
WOOD_TRUNK = (0x6A, 0x44, 0x26)   # banner poles, torch sticks, house timbers
STEEL      = (0xC9, 0xCC, 0xD4)
CARPET_RED = (0xB0, 0x32, 0x34)
CARPET_DK  = (0x7C, 0x21, 0x24)
GOLD       = (0xE6, 0xC2, 0x5A)
GOLD_DK    = (0xB6, 0x91, 0x3E)
HOUSE_WALL = (0xEC, 0xDF, 0xC0)
ROOF       = (0xA0, 0x4B, 0x3A)
ROOF_DK    = (0x7A, 0x36, 0x28)
WINDOW     = (0x23, 0x23, 0x3A)
DOOR       = (0x8A, 0x5A, 0x2E)
BANNER     = (0xD0, 0x3A, 0x3A)
BANNER_DK  = (0xA8, 0x2A, 0x2A)
DARK_HOLE  = (0x1A, 0x1B, 0x26)
FLAME      = (0xE6, 0xA5, 0x3A)
CANVAS     = (0xDF, 0xEE, 0xF8)
PAINT_SKY  = (0xB9, 0xD9, 0xF0)

HORIZON = 34          # THE one surface row: sea, sand, grass, town, castle
CARPET_TOP = 38
CARPET_BOT = 47
SEA_END = 260         # nominal sea/sand boundary (jagged around it)
BEACH_END = 380
FIELDS_END = 540
TOWN_END = 760
WALL_END = 830
COURT_END = 970
ENTR_END = 1100       # treasure room runs to x=1279
BG_W, BG_H = 1280, 60
WASH = [6, 10, 14, 10, 6]   # foam/wash extent per frame: grow 1-3, shrink 3-5
def _lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def bpx(img, x, y, c):
    if 0 <= x < img.width and 0 <= y < img.height:
        img.putpixel((x, y), c + (255,))


def brect(img, x0, y0, x1, y1, c):
    for y in range(max(0, y0), min(img.height - 1, y1) + 1):
        for x in range(max(0, x0), min(img.width - 1, x1) + 1):
            img.putpixel((x, y), c + (255,))


def bline(img, x0, y0, x1, y1, c):
    dx = abs(x1 - x0)
    sx = 1 if x0 < x1 else -1
    dy = -abs(y1 - y0)
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        bpx(img, x0, y0, c)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


SKY_GRAD = [_lerp(SKY_NAVY, SKY_DAY, round(i * 6 / (SEA_END - 1)) / 6)
            for i in range(SEA_END)]

# jagged multi-step boundary offsets: staggered 2-3px teeth with dither
JAG_SEA   = (-3, -3, -2, -2, -1, -1, 0, 0, 1, 1, 2, 2, 3, 3, 2, 2,
             1, 1, 0, 0, -1, -1, -2, -2)
JAG_GRASS = (-2, -2, -1, -1, 0, 0, 1, 1, 2, 2, 1, 1, 0, 0, -1, -1,
             -2, -2, -2, -1, 0, 0, 1, 1)
JAG_TOWN  = (-2, -1, -1, 0, 0, 1, 1, 2, 2, 1, 1, 0, 0, -1, -1, -2,
             -2, -1, -1, 0, 0, 1, 1, 2)
JAG_WALL  = (-2, -2, -1, -1, 0, 0, 1, 1, 2, 2, 1, 1, 0, 0, -1, -1,
             -2, -2, -2, -1, 0, 0, 1, 1)


def bpx(img, x, y, c):
    if 0 <= x < img.width and 0 <= y < img.height:
        img.putpixel((x, y), c + (255,))


def brect(img, x0, y0, x1, y1, c):
    for y in range(max(0, y0), min(img.height - 1, y1) + 1):
        for x in range(max(0, x0), min(img.width - 1, x1) + 1):
            img.putpixel((x, y), c + (255,))


def bline(img, x0, y0, x1, y1, c):
    dx = abs(x1 - x0)
    sx = 1 if x0 < x1 else -1
    dy = -abs(y1 - y0)
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        bpx(img, x0, y0, c)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def brick_px(x, y, y0):
    """Single pavement-brick colour at (x,y) matching bg_bricks(x0=y0) for
    pattern-consistent overpainting along a jagged edge."""
    if (y - y0) % 3 == 2:
        return MORTAR
    off = (((y - y0) // 3) % 2) * 4
    return MORTAR if (x - off) % 8 == 0 else STONE_FACE


OUTLINE_C = (0x20, 0x22, 0x2C)


def bg_sky(img, f):
    """Req 9: stepped navy->daylight gradient west of the beach; uniform
    daylight east of it until the wall.  No props in the sky."""
    for x in range(SEA_END):
        brect(img, x, 0, x, HORIZON - 2, SKY_GRAD[x])
    brect(img, SEA_END, 0, TOWN_END - 1, HORIZON - 1, SKY_DAY)
    brect(img, 0, HORIZON - 1, TOWN_END - 1, HORIZON - 1, CANVAS)  # haze row


def bg_ground(img):
    """Flat base fills + the jagged biome boundaries.  Every phase's
    ground starts on the same HORIZON row."""
    # sea base (two flat blues + horizon light row)
    brect(img, 0, HORIZON, 267, 45, SEA_MID)
    brect(img, 0, 46, 267, 59, SEA_DEEP)
    brect(img, 0, HORIZON, 267, HORIZON, SEA_LIGHT)
    # flat sand base, then the jagged wet-sand sea edge
    brect(img, 266, HORIZON, BEACH_END - 1, 59, SAND)
    for y in range(HORIZON, 60):
        e = SEA_END + JAG_SEA[(y + 5) % 24]
        bpx(img, e, y, SAND_WET)
        brect(img, e + 1, y, BEACH_END - 1, y, SAND)
        if y % 2 == 0:
            bpx(img, e + 1, y, SEA_LIGHT)          # dither tooth into water
        if JAG_SEA[(y + 5) % 24] != JAG_SEA[(y + 4) % 24]:
            bpx(img, e, y, SAND_DK)                # darker sand at each step
    # grass with its jagged dither band, sand left of the edge
    for y in range(HORIZON, 60):
        g = BEACH_END - 2 + JAG_GRASS[(y + 9) % 24]
        brect(img, 376, y, g - 1, y, SAND)
        brect(img, g, y, FIELDS_END - 1, y, GRASS)
        if y == HORIZON:
            brect(img, g, y, FIELDS_END - 1, y, GRASS_LT)
        if (y + 9) % 2 == 0 and y > HORIZON:
            bpx(img, g - 1, y, GRASS_LT)           # grass tooth into sand
    # wheat runs - soft base texture (no outline), static between frames
    for x0, ra in ((398, (40, 46)), (498, (48, 54))):
        for x in range(x0, min(x0 + 48, 536), 4):
            if x % 12 != 0:
                brect(img, x, ra[0] + 2, x, ra[1], GOLD_DK)   # stalk
                bpx(img, x, ra[0] + 1, GOLD)
                bpx(img, x + 1, ra[0] + 3, GOLD)
    # town pavement behind the jagged curb-stone edge
    bg_bricks(img, 536, TOWN_END - 1, HORIZON, 59)
    for y in range(HORIZON, 60):
        t = FIELDS_END + JAG_TOWN[(y + 2) % 24]
        brect(img, 381, y, t - 1, y, GRASS)
        brect(img, t, y, t, y, MORTAR)
        if y % 2 == 0:
            bpx(img, t + 1, y, STONE_LT)
    # castle: wall face (full height, no sky above), enclosed backdrops
    bg_bricks(img, TOWN_END, 835, 0, HORIZON - 1)
    bg_bricks(img, 828, COURT_END - 1, 0, HORIZON - 1)
    bg_bricks(img, COURT_END, ENTR_END - 1, 0, HORIZON - 1)
    bg_planks(img, ENTR_END, 1279, 0, HORIZON - 1)
    # floors - all starting on the same horizon row
    bg_bricks(img, TOWN_END, 835, HORIZON, 59)
    bg_planks(img, WALL_END, COURT_END - 1, HORIZON, 59)
    bg_bricks(img, COURT_END, ENTR_END - 1, HORIZON, 59)
    bg_planks(img, ENTR_END, 1279, HORIZON, 59)
    # wall->courtyard: jagged stone seam on the backdrop AND the floor
    for y in range(0, 60):
        s = WALL_END + 1 + JAG_WALL[(y + 3) % 24]
        for x in range(828, s):
            bpx(img, x, y, brick_px(x, y, 0 if y < HORIZON else HORIZON))
        bpx(img, s, y, OUTLINE_C)
        if y % 2 == 0:
            bpx(img, s + 1, y, STONE_LT)
    # carpet: red strip with yellow borders, jagged start at the seam
    for y in range(CARPET_TOP, CARPET_BOT + 1):
        s = WALL_END + 1 + JAG_WALL[(y + 3) % 24]
        c = GOLD if y in (CARPET_TOP, CARPET_BOT) else CARPET_RED
        brect(img, s + 1, y, 1279, y, c)


def bg_bricks(img, x0, x1, y0, y1):
    brect(img, x0, y0, x1, y1, STONE_FACE)
    for y in range(y0, y1 + 1):
        if (y - y0) % 3 == 2:
            for x in range(x0, x1 + 1):
                bpx(img, x, y, MORTAR)
        else:
            off = ((y - y0) // 3 % 2) * 4
            for x in range(x0, x1 + 1):
                if (x - off) % 8 == 0:
                    bpx(img, x, y, MORTAR)


def bg_planks(img, x0, x1, y0, y1):
    brect(img, x0, y0, x1, y1, WOOD_LT)
    for y in range(y0, y1 + 1):
        if (y - y0) % 3 == 2:
            for x in range(x0, x1 + 1):
                bpx(img, x, y, WOOD_SEAM)
        else:
            off = ((y - y0) // 3 % 2) * 11
            for x in range(x0, x1 + 1):
                if (x - off) % 22 == 0:
                    bpx(img, x, y, WOOD_SEAM)


def bg_sea_base(img, f):
    """Water glints (small water detail, period 5, seamless)."""
    for y in (36, 42, 50, 58):
        for x in range(0, 248):
            if (x + f * 2) % 5 == 1 and (x * 13 + y * 7) % 9 < 2:
                bpx(img, x, y, SPARK)


def bg_shore_base(img, f):
    """Req 3: the wash sheet - water behind all foam, its right edge
    follows the jagged shoreline."""
    for y in range(40, 60):
        e = SEA_END + JAG_SEA[(y + 5) % 24]
        brect(img, 252, y, e + WASH[f], y, SEA_LIGHT)


def bg_props(img, f):
    """Everything outlined: waves, foam, beach/grass/wall/treasure
    texture. Drawn on the transparent props layer, outlined like sprites."""
    # --- sea: runs of outlined wave bumps with white tips, two blues/row
    for r, yr in enumerate((39, 43, 47, 51, 55)):
        base = (r * 5 + f * 2) % 10
        for k in range(26):
            bx = k * 10 + base - 2
            if bx < 1 or bx > 248:
                continue
            col = SEA_LIGHT if (k + r) % 2 == 0 else SEA_CREST
            brect(img, bx + 1, yr, bx + 3, yr, col)   # crest mound
            bpx(img, bx + 2, yr - 1, FOAM)            # white tip

    # --- foam riding onto the beach (grow 1-3, shrink 3-5)
    for y in range(40, 60):
        e = SEA_END + JAG_SEA[(y + 5) % 24]
        w = e + WASH[f]
        bpx(img, w - 1, y, FOAM)
        bpx(img, w, y, FOAM)
        if (y * 7) % 3 != 0:
            bpx(img, w + 1, y, FOAM)
        if y % 3 == 0:
            bpx(img, w, y - 1, FOAM)
    for x in range(252, 292):
        if x % 3 != 0:
            bpx(img, x, 39, FOAM)                     # top foam fringe
        if x % 4 == 1:
            bpx(img, x, 38, FOAM)
    for k in range(WASH[f] // 3 + 1):                 # foam patches scale
        pxx = 253 + ((k * 13 + WASH[f] * 3) % (WASH[f] + 2))
        pyy = 41 + (k * 7) % 18
        brect(img, pxx, pyy, pxx + 2, pyy, FOAM)
        bpx(img, pxx, pyy - 1, FOAM)

    # --- beach texture: dune curves, speckles, shells, starfish, prints
    for i, x in enumerate(range(284, 348, 2)):
        yd = 41 + (i * i // 10 + i) % 4               # outlined dune curve
        bpx(img, x, yd, SAND_DK)
        bpx(img, x, yd + 1, SAND_DK)
    for i, x in enumerate(range(296, 364, 2)):
        yd = 54 + ((x // 6) % 3)
        bpx(img, x, yd, SAND_DK)
    for x in range(282, 374):                         # sand speckles
        for y in range(40, 59):
            if x % 5 == 2 and (x * 7 + y * 3) % 13 == 4:
                bpx(img, x, y, SAND_DK)
    shell(img, 300, 47)
    shell(img, 334, 52)
    starfish(img, 316, 46)
    for i, (fx, fy) in enumerate(((288, 52), (295, 50), (302, 48),
                                  (309, 46), (316, 44))):
        brect(img, fx, fy, fx + 1, fy, SAND_DK)       # footprints
        bpx(img, fx, fy + 1, SAND_DK)
    brect(img, 346, 44, 348, 45, STONE_LT)            # pebbles
    brect(img, 356, 55, 358, 56, STONE_LT)

    # --- grass texture: outlined tufts + wheat runs
    for ry, y0 in enumerate((37, 43, 49, 55)):
        for x in range(386, 536, 9):
            if (x // 9 + ry) % 3:
                bl = x + ((ry * 3) % 5) - 2
                bpx(img, bl, y0, GRASS_LT)
                bpx(img, bl + 1, y0 - 1, GRASS_LT)
                bpx(img, bl + 2, y0 - 2, GRASS_LT)
                bpx(img, bl + 3, y0, GRASS_LT)
                bpx(img, bl + 4, y0 - 1, GRASS_LT)
    for x0, ra in ((398, (40, 46)), (498, (48, 54))):
        for x in range(x0, min(x0 + 48, 536), 4):
            if x % 12 != 0:
                brect(img, x, ra[0] + 2, x, ra[1], GOLD_DK)   # wheat stalk
                bpx(img, x, ra[0] + 1, GOLD)
                bpx(img, x + 1, ra[0] + 3, GOLD)
    for y in (36, 42, 48, 54):                        # tufts overhang sand
        t = FIELDS_END + JAG_TOWN[(y + 2) % 24]
        bpx(img, t - 3, y, GRASS_LT)
        bpx(img, t - 2, y - 1, GRASS_LT)
        bpx(img, t - 1, y - 2, GRASS_LT)

    # --- town: jagged curb stones along the pavement edge
    for y in range(HORIZON, 59, 3):
        t = FIELDS_END + JAG_TOWN[(y + 2) % 24]
        brect(img, t - 2, y, t + 1, y + 1, STONE_LT)
        bpx(img, t - 2, y + 1, MORTAR)

    # --- town: one detailed outlined house facade
    brect(img, 600, 18, 690, 33, HOUSE_WALL)
    brect(img, 628, 13, 662, 13, ROOF)
    brect(img, 618, 14, 672, 14, ROOF)
    brect(img, 608, 15, 682, 15, ROOF)
    brect(img, 598, 16, 692, 17, ROOF)
    brect(img, 598, 17, 692, 17, ROOF_DK)
    brect(img, 600, 18, 690, 18, WOOD_TRUNK)          # beam
    for px_ in (602, 688):                            # corner timbers
        brect(img, px_, 19, px_ + 1, 33, WOOD_TRUNK)
    brect(img, 640, 25, 648, 33, DOOR)                # door
    brect(img, 639, 25, 639, 33, WOOD_DK)
    brect(img, 649, 25, 649, 33, WOOD_DK)
    bpx(img, 646, 29, GOLD)
    for wx in (612, 656):                             # windows
        brect(img, wx, 21, wx + 8, 28, WINDOW)
        brect(img, wx + 4, 21, wx + 4, 28, CANVAS)
        brect(img, wx, 24, wx + 8, 24, CANVAS)
        brect(img, wx - 1, 29, wx + 9, 29, STONE_LT)  # sill
    brect(img, 644, 20, 646, 22, WINDOW)              # attic window
    bpx(img, 645, 21, CANVAS)

    # --- castle wall: crenellations, gate arch, torch sconces
    for mx in (762, 769, 814, 821):
        brect(img, mx, 0, mx + 5, 3, STONE_LT)
        brect(img, mx, 3, mx + 5, 3, MORTAR)
    brect(img, 786, 10, 803, 10, STONE_LT)            # gate arch frame
    brect(img, 778, 11, 811, 33, STONE_LT)
    brect(img, 790, 12, 799, 12, DARK_HOLE)
    brect(img, 785, 13, 804, 13, DARK_HOLE)
    brect(img, 781, 14, 808, 33, DARK_HOLE)
    bpx(img, 781, 34, DARK_HOLE)
    brect(img, 782, 34, 808, 34, DARK_HOLE)
    for tx in (773, 816, 996, 1070):                  # torch sconces
        brect(img, tx, 25, tx, 27, DOOR)
        bpx(img, tx, 24, DARK_HOLE)
        bpx(img, tx, 23, FLAME)
        bpx(img, tx, 22, FLAME)
        bpx(img, tx, 21, BANNER)

    # --- banners on poles (courtyard backdrop)
    for cx in (870, 928):
        brect(img, cx - 5, 5, cx + 5, 5, WOOD_DK)
        bpx(img, cx - 6, 5, GOLD)
        bpx(img, cx + 6, 5, GOLD)
        brect(img, cx - 3, 6, cx + 3, 23, BANNER)
        brect(img, cx + 2, 7, cx + 3, 22, BANNER_DK)
        bpx(img, cx - 3, 24, BANNER)
        bpx(img, cx + 3, 24, BANNER_DK)
    for x in (848, 895, 940):                         # arrow slits
        brect(img, x, 8, x + 1, 20, DARK_HOLE)

    # --- castle entrance: grand arch + pilasters
    brect(img, 1022, 6, 1046, 6, STONE_LT)
    brect(img, 1016, 7, 1052, 7, STONE_LT)
    brect(img, 1012, 8, 1056, 8, STONE_LT)
    brect(img, 1008, 9, 1060, 33, STONE_LT)
    brect(img, 1026, 7, 1042, 7, DARK_HOLE)
    brect(img, 1020, 8, 1048, 8, DARK_HOLE)
    brect(img, 1016, 9, 1052, 9, DARK_HOLE)
    brect(img, 1012, 10, 1056, 33, DARK_HOLE)
    for x in (978, 1086):
        brect(img, x, 0, x + 2, 33, STONE_LT)
        brect(img, x - 1, 30, x + 3, 33, STONE_LT)

    # --- treasure room props: paintings, shield, cutlass, chest, coins
    brect(img, 1116, 5, 1158, 25, WOOD_TRUNK)         # painting A: sea
    brect(img, 1118, 7, 1156, 23, CANVAS)
    brect(img, 1118, 7, 1156, 14, PAINT_SKY)
    brect(img, 1122, 8, 1124, 10, GOLD)
    brect(img, 1118, 15, 1156, 23, SEA_MID)
    brect(img, 1118, 21, 1156, 23, SEA_DEEP)
    brect(img, 1136, 18, 1142, 19, DARK_HOLE)
    brect(img, 1139, 15, 1141, 17, CANVAS)
    bpx(img, 1140, 14, DARK_HOLE)
    brect(img, 1170, 7, 1206, 23, WOOD_TRUNK)         # painting B: hills
    brect(img, 1172, 9, 1204, 21, CANVAS)
    brect(img, 1172, 9, 1204, 16, PAINT_SKY)
    brect(img, 1194, 10, 1196, 12, GOLD)
    brect(img, 1172, 17, 1204, 21, GRASS)
    for hx in (1178, 1192):                           # painted hills
        bpx(img, hx, 16, GRASS)
        bpx(img, hx + 1, 16, GRASS)
        bpx(img, hx + 2, 15, GRASS)
    shield_b(img, 1222, 5)                            # mounted shield
    bline(img, 1237, 13, 1245, 5, STEEL)              # mounted cutlass
    bline(img, 1238, 13, 1246, 5, WOOD_SEAM)
    brect(img, 1235, 14, 1236, 15, DOOR)
    coin_mound(img, 1196, 56)                         # coin mounds
    coin_mound(img, 1210, 56)
    brect(img, 1244, 50, 1276, 56, WOOD_MD)           # treasure chest
    brect(img, 1246, 47, 1274, 49, WOOD_MD)
    brect(img, 1246, 49, 1274, 49, WOOD_DK)
    brect(img, 1244, 55, 1276, 56, WOOD_DK)
    brect(img, 1250, 47, 1251, 56, GOLD)
    brect(img, 1266, 47, 1267, 56, GOLD)
    brect(img, 1258, 50, 1260, 51, GOLD)
    bpx(img, 1259, 52, GOLD_DK)
    brect(img, 1252, 44, 1270, 46, GOLD)              # overflowing heap
    bpx(img, 1254, 43, GOLD)
    bpx(img, 1264, 43, GOLD)


def shield_b(img, x0, y0):
    brect(img, x0 + 2, y0, x0 + 7, y0, CARPET_RED)
    brect(img, x0, y0 + 1, x0 + 9, y0 + 8, CARPET_RED)
    brect(img, x0 + 2, y0 + 9, x0 + 7, y0 + 9, CARPET_RED)
    bpx(img, x0 + 1, y0 + 8, CARPET_DK)
    bpx(img, x0 + 8, y0 + 8, CARPET_DK)
    brect(img, x0 + 4, y0 + 4, x0 + 5, y0 + 5, GOLD)


def coin_mound(img, x0, ybase):
    for i, w in enumerate((13, 11, 9, 7, 5)):
        y = ybase - i
        brect(img, x0 + (13 - w) // 2, y, x0 + (13 - w) // 2 + w - 1, y, GOLD)
        if i == 0:
            brect(img, x0 + 2, y, x0 + 10, y, GOLD_DK)


def shell(img, x, y):
    brect(img, x + 1, y, x + 2, y, CANVAS)
    brect(img, x, y + 1, x + 3, y + 2, CANVAS)
    bpx(img, x + 1, y + 2, SAND_DK)
    bpx(img, x + 2, y + 2, SAND_DK)


def starfish(img, x, y):
    for dx, dy in ((2, 0), (2, 4), (0, 2), (4, 2), (2, 2), (1, 1),
                   (3, 1), (1, 3), (3, 3)):
        bpx(img, x + dx, y + dy, ROOF)
    bpx(img, x + 2, y + 2, GOLD)


def composite_props(img, props):
    p = img.load()
    pp = props.load()
    for y in range(img.height):
        for x in range(img.width):
            a = pp[x, y][3]
            if a:
                p[x, y] = pp[x, y]


def build_background_frame(f):
    img = new(BG_W, BG_H)
    bg_sky(img, f)
    bg_ground(img)
    bg_sea_base(img, f)
    bg_shore_base(img, f)
    props = new(BG_W, BG_H)
    bg_props(props, f)
    add_outline(props)      # 1px silhouette outline, sprite-style
    composite_props(img, props)
    return img


def build_backgrounds():
    for f in range(5):
        path = os.path.join(SPRITE_DIR, f"background-{f + 1}.png")
        build_background_frame(f).convert("RGB").save(path)
        print(f"wrote background-{f + 1}.png  {BG_W}x{BG_H}")
    with open(os.path.join(SPRITE_DIR, "background.json"), "w") as fh_:
        json.dump({"frames": 5, "frameW": 1280, "frameH": 60, "fps": 5}, fh_)
        fh_.write("\n")
    print("wrote background.json")


def verify_backgrounds():
    """Extended verification for the revised background frames."""
    print("verify backgrounds (revision 2):")
    ok = True

    def chk(label, cond, extra=""):
        nonlocal ok
        print(f"  {'ok  ' if cond else 'FAIL'} {label}{extra}")
        if not cond:
            ok = False

    frames = [Image.open(os.path.join(SPRITE_DIR, f"background-{i}.png"))
              for i in range(1, 6)]
    chk("5 frames of 1280x60 RGB",
        all(im.size == (BG_W, BG_H) and im.mode == "RGB" for im in frames))
    pix = [im.load() for im in frames]
    OUT = OUTLINE_C

    diffs = [(x, y) for x in range(BG_W) for y in range(BG_H)
             if pix[0][x, y] != pix[1][x, y]]
    chk("only waves/foam/glints animate (diffs all x < 760)",
        bool(diffs) and max(x for x, _ in diffs) < TOWN_END)

    # --- req 1/3: organised, outlined wave bumps, two blues per row
    crest = [sum(1 for x in range(252) for y in range(36, 59)
                 if pix[f][x, y] in (SEA_CREST, SEA_LIGHT, FOAM, SPARK))
             for f in range(5)]
    out_sea = [sum(1 for x in range(252) for y in range(36, 59)
                   if pix[f][x, y][:3] == OUT) for f in range(5)]
    chk(f"waves: outlined bumps with white tips on the sea "
        f"(crest px={crest[0]}, sea outlines={out_sea[0]})",
        min(crest) > 300 and min(out_sea) > 400)

    # --- req 4: one fixed horizon row for every phase, every frame
    hz = []
    for p in pix:
        hz.append((
            p[120, 33], p[120, 34],            # sea
            p[320, 33], p[320, 34],            # sand
            p[460, 33], p[460, 34],            # grass
            p[560, 33], p[560, 34],            # town pavement (by the house)
            p[770, 33], p[770, 34],            # castle ground at the wall
            p[900, 33], p[900, 34],            # courtyard floor
            p[990, 33], p[990, 34],            # entrance floor (by facade)
            p[1150, 33], p[1150, 34]))         # treasure floor
    horizon_ok = (
        hz[0][0] == CANVAS and hz[0][1] == SEA_LIGHT
        and hz[0][2] == CANVAS and hz[0][3] == SAND
        and hz[0][4] == CANVAS and hz[0][5] in (GRASS, GRASS_LT)
        and hz[0][6] == CANVAS and hz[0][7] in (STONE_FACE, MORTAR)
        and hz[0][8] == STONE_FACE
        and hz[0][9] in (STONE_FACE, MORTAR)
        and hz[0][10] in (STONE_FACE, MORTAR) and hz[0][11] == WOOD_LT
        and hz[0][12] == STONE_FACE and hz[0][13] in (STONE_FACE, MORTAR)
        and hz[0][14] in (WOOD_LT, WOOD_MD, WOOD_SEAM)
        and hz[0][15] == WOOD_LT
        and all(frame == hz[0] for frame in hz))
    chk("horizon: ground starts on the SAME row (34) in every phase/frame",
        horizon_ok)

    # --- req 2/3: foam rides on water all the way to dry sand
    wash_ok = True
    for f in range(5):
        for y in range(40, 60):
            e = SEA_END + JAG_SEA[(y + 5) % 24]
            lim = e + WASH[f] + 2
            for x in range(252, lim):
                if pix[f][x, y] not in (SEA_LIGHT, FOAM, OUTLINE_C):
                    wash_ok = False
    chk("water continues behind foam across the whole wash", wash_ok)

    foam_counts = [
        sum(1 for x in range(252, 300) for y in range(38, 60)
            if pix[f][x, y] == FOAM) for f in range(5)]
    chk(f"foam blobs grow 1-3 and shrink 3-5 ({foam_counts})",
        foam_counts[0] < foam_counts[2] and foam_counts[4] < foam_counts[2])

    # --- req 1/4: flat, uniform sand (texture outlines ok, no gradient)
    allowed_sand = {SAND, SAND_DK, SAND_WET, ROOF, GOLD, CANVAS, STONE_LT,
                    OUT, FOAM, GRASS, GRASS_LT}
    bad = [(x, y) for x in range(282, 377) for y in range(34, 60)
           if pix[0][x, y] not in allowed_sand]
    n_sand = sum(1 for x in range(282, 377) for y in range(34, 60)
                 if pix[0][x, y] == SAND)
    chk(f"beach sand flat (single tone, textured props, stray={len(bad)}, "
        f"sand share={n_sand / (95 * 26):.2f})",
        not bad and n_sand > 0.7 * 95 * 26)

    # --- req 5: brick pavements (town, wall/entrance floors)
    for x0, x1, label in ((540, TOWN_END, "town"),
                          (COURT_END, ENTR_END, "entrance")):
        n = sum(1 for x in range(x0, x1) for y in range(34, 60)
                if pix[0][x, y] == MORTAR)
        chk(f"{label} floor is brick pavement (mortar px={n})", n > 120)

    # --- req 6: wall full height, no sky above or after it
    chk("wall reaches the top of the frame",
        all(pix[0][770, y][:3] in (STONE_FACE, MORTAR, OUT, STONE_LT)
            for y in range(0, 34)))
    skyfree = all(pix[0][x, y][:3] not in (SKY_DAY, SKY_NAVY)
                  for x in range(TOWN_END, BG_W) for y in range(0, BG_H))
    chk("no sky at/after the wall (interior enclosed)", skyfree)

    # --- new: sprite-style outlines present everywhere
    zones = {
        "beach": (282, 377, 34, 59, 60),
        "house/town": (540, 758, 8, 34, 130),
        "wall": (760, 829, 0, 33, 120),
        "courtyard-deco": (830, 969, 0, 33, 100),
        "treasure": (1100, 1279, 0, 59, 250),
    }
    for label, (x0, x1, y0, y1, need) in zones.items():
        n = sum(1 for x in range(x0, x1) for y in range(y0, y1)
                if pix[0][x, y][:3] == OUT)
        chk(f"style: outlined shapes in {label} ({n} outline px)", n >= need)
    total = sum(1 for x in range(BG_W) for y in range(BG_H)
                if pix[0][x, y][:3] == OUT)
    chk(f"style: silhouette outlines overall ({total} px)", total > 1500)

    # --- new: loose props removed (no clouds/palm/bush/fence/sun)
    loose = 0
    for p in pix:
        for x in range(BG_W):
            for y in range(BG_H):
                c = p[x, y][:3]
                if c in ((0xF4, 0xF8, 0xFB), (0x3A, 0x70, 0x30)):
                    loose += 1
                if x < 760 and c == (0xF7, 0xE8, 0xA0):
                    loose += 1
    chk("no clouds/bushes/palm fronds (removed colours absent)", loose == 0)
    fence = sum(1 for x in range(260, 540) for y in range(0, 60)
                if pix[0][x, y] == WOOD_TRUNK)
    chk("no palm trunks or fence posts left on beach/fields", fence == 0)

    # --- new: jagged multi-step biome boundaries (edge x varies > 3px)
    def _scan(p, y, x0, x1, cols, first):
        hits = [x for x in range(x0, x1) if p[x, y][:3] in cols]
        if first:
            return hits[0] if hits else None
        return hits[-1] if hits else None

    sea_cols = (SEA_MID, SEA_DEEP, SEA_LIGHT)
    edges_sea = [_scan(pix[0], y, 250, 286, sea_cols, False)
                 for y in range(34, 60)]
    edges_sg = [_scan(pix[0], y, 366, 392, (SAND, SAND_DK, SAND_WET), False)
                for y in range(34, 60)]
    edges_gt = [_scan(pix[0], y, 524, 552, (GRASS, GRASS_LT), False)
                for y in range(34, 60)]
    edges_wc = [_scan(pix[0], y, 824, 842, (OUT,), True)
                for y in range(8, 60)]
    for label, edges in (("sea->sand", edges_sea), ("sand->grass", edges_sg),
                         ("grass->town", edges_gt),
                         ("wall->courtyard", edges_wc)):
        pts = [e for e in edges if e is not None]
        span = max(pts) - min(pts) if pts else 0
        chk(f"jagged {label} edge (x varies {span}px over height)",
            len(pts) > 20 and span > 3)

    # --- req 8: carpet with yellow borders; wood planks beside it
    carb = all(pix[0][x, 38] == GOLD and pix[0][x, 47] == GOLD
               and pix[0][x, 42] in (CARPET_RED, CARPET_DK)
               for x in range(840, 1230, 20))
    seam = sum(1 for x in range(830, 970) for y in range(34, 60)
               if pix[0][x, y] == WOOD_SEAM)
    chk("carpet strip with yellow outlines full length", carb)
    chk(f"wood plank floor beside the carpet (seam px={seam})", seam > 60)

    # --- req 7: decorated treasure wall
    chk("treasure room decorated (gold present)",
        sum(1 for x in range(1100, 1280) for y in range(34, 60)
            if pix[0][x, y] == GOLD) > 60)

    # --- req 9: gradient until the beach, uniform daylight after it
    row0 = [sum(pix[0][x, 3]) for x in range(0, SEA_END, 4)]
    chk("sky gradient (navy -> light) up to the beach",
        row0[0] < row0[len(row0) // 2] < row0[-1]
        and pix[0][0, 0] == SKY_NAVY and pix[0][SEA_END - 1, 3] == SKY_DAY)
    uni = all(pix[0][x, y] == SKY_DAY for x in range(390, 640, 10)
              for y in range(0, 6))
    chk("uniform daylight sky from the beach to the wall", uni)
    return ok


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--dump" in args:
        dump()
        sys.exit(0)
    if "--dump-bg" in args:
        i = args.index("--dump-bg")
        f = int(args[i + 1]) if len(args) > i + 1 else 0
        x0 = int(args[i + 2]) if len(args) > i + 2 else 0
        x1 = int(args[i + 3]) if len(args) > i + 3 else 260
        dump_bg(f, x0, x1)
        sys.exit(0)
    ok = True
    build_backgrounds()
    ok &= verify_backgrounds()
    build_sheets()
    ok &= verify()
    sys.exit(0 if ok else 1)
