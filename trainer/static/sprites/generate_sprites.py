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


# -------------------------------------------------------- background frames
# Five 1280x60 frames of the whole world background: sea -> beach ->
# fields -> town -> castle wall -> courtyard -> castle entrance ->
# treasure room.  No characters.  Only waves, foam and small sky details
# animate between frames; everything else is drawn identically every time.
# All animated patterns have a horizontal period dividing 10 (5 frames x
# 2px shift) so the loop wraps seamlessly.

SKY_NAVY = (0x16, 0x23, 0x3F)
SKY_DAY = (0x7E, 0xC0, 0xEE)
SEA_DEEP = (0x1D, 0x4F, 0x8F)
SEA_MID = (0x2B, 0x6B, 0xB5)
SEA_LIGHT = (0x3F, 0x86, 0xC9)
SEA_CREST = (0x6D, 0xB2, 0xE8)
SPARK = (0xCF, 0xE8, 0xF8)
FOAM = (0xF2, 0xF7, 0xFB)
CLOUD = (0xF4, 0xF8, 0xFB)
SUN = (0xF7, 0xE8, 0xA0)
SAND = (0xE9, 0xD6, 0xA1)
GRASS = (0x4E, 0x8F, 0x3A)
GRASS_DK = (0x3A, 0x70, 0x30)
GRASS_LT = (0x67, 0xA9, 0x4C)
WOOD_TRUNK = (0x6A, 0x44, 0x26)
STONE_FACE = (0x9F, 0xA0, 0xAA)
STONE_LT = (0xB4, 0xB5, 0xBF)
MORTAR = (0x5C, 0x5D, 0x66)
WOOD_LT = (0xC9, 0x9A, 0x5E)
WOOD_MD = (0xA8, 0x7B, 0x44)
WOOD_DK = (0x7C, 0x57, 0x30)
WOOD_SEAM = (0x63, 0x45, 0x2A)
CARPET_RED = (0xB0, 0x32, 0x34)
CARPET_DK = (0x7C, 0x21, 0x24)
GOLD = (0xE6, 0xC2, 0x5A)
GOLD_DK = (0xB6, 0x91, 0x3E)
HOUSE_WALL = (0xEC, 0xDF, 0xC0)
ROOF = (0xA0, 0x4B, 0x3A)
ROOF_DK = (0x7A, 0x36, 0x28)
WINDOW = (0x23, 0x23, 0x3A)
DOOR = (0x8A, 0x5A, 0x2E)
BANNER = (0xD0, 0x3A, 0x3A)
BANNER_DK = (0xA8, 0x2A, 0x2A)
DARK_HOLE = (0x1A, 0x1B, 0x26)
FLAME = (0xE6, 0xA5, 0x3A)
CANVAS = (0xDF, 0xEE, 0xF8)
PAINT_SKY = (0xB9, 0xD9, 0xF0)

HORIZON = 34        # sea horizon row; sky above, world below
FLOOR_TOP = 44      # pavement / interior floor top row
CARPET_TOP = 46
CARPET_BOT = 55
SEA_END = 260       # sea/sand boundary (waterline)
BEACH_END = 380
FIELDS_END = 540
TOWN_END = 760
WALL_END = 830
COURT_END = 970
ENTR_END = 1100     # treasure room runs to x=1279
BG_W, BG_H = 1280, 60
WASH = [6, 10, 14, 10, 6]   # foam/wash extent per frame: grow 1-3, shrink 3-5


def _lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


SKY_GRAD = [ _lerp(SKY_NAVY, SKY_DAY, round(i * 6 / (SEA_END - 1)) / 6)
             for i in range(SEA_END) ]  # navy (west) -> daylight (beach)


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


def bg_sky(img, f):
    """Req 9: stepped navy->daylight gradient across the sky until the
    beach (dark navy in the west), then uniform daylight blue from the
    beach eastward until the wall - no seam at the boundary.  A notch
    shimmers along each cloud (period-5 pattern, seamless loop)."""
    for x in range(SEA_END):
        brect(img, x, 0, x, HORIZON - 2, SKY_GRAD[x])
    brect(img, SEA_END, 0, TOWN_END - 1, FLOOR_TOP - 1, SKY_DAY)
    brect(img, 0, HORIZON - 1, TOWN_END - 1, HORIZON - 1, CANVAS)  # haze row


def bg_clouds(img, f):
    """Small sky detail: notches travel along the cloud tops (+1/frame)."""
    for bx, y, w, r0, r1 in ((40, 6, 26, 0, SEA_END - 12),
                             (150, 12, 20, 0, SEA_END - 12),
                             (210, 4, 14, 0, SEA_END - 12),
                             (560, 8, 22, 400, 640),
                             (660, 14, 16, 400, 640)):
        x0 = r0 + (bx - r0) % (r1 - r0 - w)
        for i in range(w):
            if (i + f) % 5 != 0:
                bpx(img, x0 + i, y, CLOUD)
        for i in range(-2, w + 2):
            if (i + 3 + f) % 5 != 0:
                bpx(img, x0 + i, y + 1, CLOUD)
        for i in range(3, w - 3):
            if (i + f) % 5 != 0:
                bpx(img, x0 + i, y + 2, CLOUD)


def bg_sun(img):
    for x in range(698, 705):
        bpx(img, x, 5, SUN)
    brect(img, 695, 6, 707, 11, SUN)
    for x in range(698, 705):
        bpx(img, x, 12, SUN)


CREST_MOTIFS = [  # rel = (x - shift) % 10 -> colour per pixel of the wave
    {2: SEA_CREST, 3: SEA_CREST, 4: SEA_CREST, 5: SEA_CREST, 6: SEA_CREST,
     7: SEA_CREST, 8: FOAM, 9: FOAM},
    {0: SEA_CREST, 1: SEA_CREST, 2: SEA_CREST, 3: SEA_CREST, 4: SEA_CREST,
     5: FOAM, 6: FOAM},
    {4: SEA_CREST, 5: SEA_CREST, 6: SEA_CREST, 7: SEA_CREST, 8: SEA_CREST,
     9: SEA_CREST, 0: FOAM, 1: FOAM},
    {6: SEA_CREST, 7: SEA_CREST, 8: SEA_CREST, 9: SEA_CREST, 0: FOAM,
     1: FOAM, 3: SPARK},
]
CREST_ROWS = (39, 42, 45, 50, 54, 57)


def bg_sea(img, f):
    brect(img, 0, HORIZON, SEA_END - 1, 46, SEA_MID)
    brect(img, 0, 47, SEA_END - 1, 59, SEA_DEEP)
    brect(img, 0, HORIZON, SEA_END - 1, HORIZON + 1, SEA_LIGHT)
    for yr in CREST_ROWS:
        motif = CREST_MOTIFS[(yr * 3) % 4]
        rel_off = f * 2 + yr * 3
        for x in range(0, SEA_END):
            kind = motif.get((x - rel_off) % 10)
            if kind:
                bpx(img, x, yr, kind)
    # glinting water sparkles (period 5, shifts 2px/frame, seamless)
    for y in (38, 41, 48, 53, 56):
        for x in range(0, SEA_END):
            if (x + f * 2) % 5 == 1 and (x * 13 + y * 7) % 9 < 2:
                bpx(img, x, y, SPARK)


def bg_beach(img):
    """Req 4: perfectly flat, uniform sand (no gradient, no speckles)."""
    brect(img, SEA_END, HORIZON, BEACH_END - 1, 59, SAND)


def bg_shore(img, f):
    """Reqs 2+3: waves break onto the beach as white foam; water fills the
    whole wash sheet right up to where dry sand starts, and foam only
    overhangs onto sand while covering it."""
    e = SEA_END + WASH[f]        # one past the water's leading column
    brect(img, SEA_END, 40, e + 2, 59, SEA_LIGHT)          # water sheet
    for x in range(SEA_END, e):                            # top foam fringe
        if x % 4 != 0:
            bpx(img, x, 39, FOAM)
        if x % 3 == 1:
            bpx(img, x, 38, FOAM)
    for y in range(40, 60):                                # leading foam lip
        dx = (y * y * 7) % 3
        for i in range(dx + 2):
            bpx(img, e - 1 + i, y, FOAM)
    for k in range(3):                                     # foam patches
        bx = SEA_END + 2 + (k * 11) % (e - SEA_END - 4)
        by = 43 + (k * 5) % 14
        bpx(img, bx, by, FOAM)
        bpx(img, bx + 1, by, FOAM)
    for x in range(SEA_END, e):                            # heel of the wave
        if x % 2 == 0:
            bpx(img, x, 59, FOAM)


def bg_fields(img):
    brect(img, BEACH_END, HORIZON, FIELDS_END - 1, 59, GRASS)
    brect(img, BEACH_END, HORIZON, FIELDS_END - 1, HORIZON, GRASS_LT)
    for y in (44, 50, 56):                                 # grass tufts
        for x in range(BEACH_END + 4, FIELDS_END, 9):
            if (x // 9 + y) % 3:
                bpx(img, x + (y // 6) % 3, y, GRASS_LT)
                bpx(img, x + (y // 6) % 3 + 1, y + 1, GRASS_LT)
    brect(img, 446, 40, 462, 45, GRASS_DK)                 # bush
    brect(img, 449, 38, 459, 39, GRASS_DK)
    brect(img, 450, 38, 458, 38, GRASS_LT)
    for x in (500, 512, 524, 536):                         # fence
        brect(img, x, 38, x, 43, WOOD_TRUNK)
    brect(img, 500, 39, 538, 39, WOOD_TRUNK)
    brect(img, 500, 41, 538, 41, WOOD_TRUNK)
    # palm at the top of the beach
    brect(img, 350, 20, 352, 43, WOOD_TRUNK)
    for tx, ty in ((338, 22), (342, 16), (364, 16), (368, 22)):
        bline(img, 351, 19, tx, ty, GRASS_DK)
    brect(img, 346, 17, 356, 19, GRASS_DK)


def bg_house(img, x0, x1, wall_top):
    cx = (x0 + x1) // 2
    brect(img, x0, wall_top, x1, FLOOR_TOP - 1, HOUSE_WALL)
    for i, hw in enumerate((10, 22, (x1 - x0) // 2)):
        brect(img, cx - hw, wall_top - 4 + i, cx + hw, wall_top - 4 + i, ROOF)
    brect(img, x0, wall_top - 1, x1, wall_top - 1, ROOF_DK)
    brect(img, cx - 4, FLOOR_TOP - 8, cx + 3, FLOOR_TOP - 1, DOOR)
    for wx in (x0 + 10, x1 - 16):
        brect(img, wx, FLOOR_TOP - 14, wx + 6, FLOOR_TOP - 9, WINDOW)
        brect(img, wx, FLOOR_TOP - 8, wx + 6, FLOOR_TOP - 8, STONE_LT)


def bg_town(img):
    """Req 5: stone brick pavement floor for the town (houses above)."""
    bg_bricks(img, FIELDS_END, TOWN_END - 1, FLOOR_TOP, 59)
    brect(img, FIELDS_END, FLOOR_TOP, TOWN_END - 1, FLOOR_TOP, MORTAR)
    bg_house(img, 556, 636, 28)
    bg_house(img, 668, 738, 22)
    brect(img, 546, 38, 553, 43, WOOD_MD)                  # barrel
    brect(img, 546, 38, 553, 38, WOOD_DK)
    brect(img, 742, 40, 752, 43, WOOD_MD)                  # crates
    brect(img, 742, 40, 752, 40, WOOD_DK)
    brect(img, 747, 40, 747, 43, WOOD_DK)


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


def bg_wall(img):
    """Req 5+6: castle wall rises to the very top of the frame (full
    height, no sky above) over a brick pavement, with a gate arch."""
    bg_bricks(img, TOWN_END, WALL_END - 1, 0, FLOOR_TOP - 1)
    for x in (TOWN_END, WALL_END - 1):
        brect(img, x, 0, x, FLOOR_TOP - 1, STONE_LT)
    brect(img, 786, 10, 803, 10, STONE_LT)                 # gate arch frame
    brect(img, 778, 11, 811, FLOOR_TOP - 1, STONE_LT)
    brect(img, 790, 12, 799, 12, DARK_HOLE)
    brect(img, 785, 13, 804, 13, DARK_HOLE)
    brect(img, 781, 14, 808, FLOOR_TOP - 1, DARK_HOLE)
    for x in (772, 817):                                   # torches
        brect(img, x, 27, x, 29, DOOR)
        bpx(img, x, 26, FLAME)
        bpx(img, x, 25, FLAME)
        bpx(img, x, 24, BANNER)


def bg_banner(img, cx):
    brect(img, cx - 4, 9, cx + 4, 9, WOOD_DK)
    bpx(img, cx - 5, 9, GOLD)
    bpx(img, cx + 5, 9, GOLD)
    brect(img, cx - 3, 10, cx + 3, 27, BANNER)
    brect(img, cx + 2, 11, cx + 3, 26, BANNER_DK)
    bpx(img, cx - 3, 28, BANNER)
    bpx(img, cx + 3, 28, BANNER_DK)


def bg_courtyard(img):
    """Enclosed stone backdrop (no sky), banner decorations, wood floor."""
    bg_bricks(img, WALL_END, COURT_END - 1, 0, FLOOR_TOP - 1)
    brect(img, WALL_END, 30, COURT_END - 1, 30, MORTAR)
    for x in (848, 895, 940):
        brect(img, x, 12, x + 1, 24, DARK_HOLE)
    bg_banner(img, 870)
    bg_banner(img, 928)


def bg_entrance(img):
    """Full-height stone facade with a grand arched doorway."""
    bg_bricks(img, COURT_END, ENTR_END - 1, 0, FLOOR_TOP - 1)
    for x in (978, 979, 1086, 1087):
        brect(img, x, 0, x, FLOOR_TOP - 1, STONE_LT)
    brect(img, 977, 40, 980, FLOOR_TOP - 1, STONE_LT)
    brect(img, 1085, 40, 1088, FLOOR_TOP - 1, STONE_LT)
    brect(img, 1022, 6, 1046, 6, STONE_LT)
    brect(img, 1016, 7, 1052, 7, STONE_LT)
    brect(img, 1012, 8, 1056, 8, STONE_LT)
    brect(img, 1008, 9, 1060, FLOOR_TOP - 1, STONE_LT)
    brect(img, 1026, 8, 1042, 8, DARK_HOLE)
    brect(img, 1020, 9, 1048, 9, DARK_HOLE)
    brect(img, 1016, 10, 1052, 10, DARK_HOLE)
    brect(img, 1012, 11, 1056, FLOOR_TOP - 1, DARK_HOLE)
    for x in (998, 1068):
        brect(img, x, 27, x, 29, DOOR)
        bpx(img, x, 26, FLAME)
        bpx(img, x, 25, FLAME)
        bpx(img, x, 24, BANNER)


def bg_treasure_wall(img):
    """Req 7: wooden plank backdrop wall for the treasure room."""
    bg_planks(img, ENTR_END, 1279, 0, FLOOR_TOP - 1)
    brect(img, ENTR_END, 12, 1279, 12, WOOD_SEAM)
    brect(img, ENTR_END, 32, 1279, 32, WOOD_SEAM)
    brect(img, ENTR_END, 40, 1279, FLOOR_TOP - 1, WOOD_DK)


def bg_treasure_props(img):
    """Req 7: paintings, mounted shield and cutlass, treasure chest."""
    # painting A: sea scene with a little ship
    brect(img, 1116, 8, 1158, 30, WOOD_TRUNK)
    brect(img, 1118, 10, 1156, 28, CANVAS)
    brect(img, 1118, 10, 1156, 17, PAINT_SKY)
    brect(img, 1122, 12, 1124, 14, SUN)
    brect(img, 1118, 18, 1156, 28, SEA_MID)
    brect(img, 1118, 26, 1156, 28, SEA_DEEP)
    brect(img, 1136, 23, 1142, 24, DARK_HOLE)
    brect(img, 1138, 20, 1140, 22, CANVAS)
    bpx(img, 1139, 19, DARK_HOLE)
    # painting B: palm over grass
    brect(img, 1170, 12, 1206, 28, WOOD_TRUNK)
    brect(img, 1172, 14, 1204, 26, CANVAS)
    brect(img, 1172, 22, 1204, 26, GRASS)
    brect(img, 1187, 17, 1188, 22, DOOR)
    bline(img, 1187, 17, 1182, 15, GRASS_DK)
    bline(img, 1187, 17, 1193, 15, GRASS_DK)
    bline(img, 1187, 17, 1187, 15, GRASS_DK)
    # mounted round shield
    brect(img, 1227, 10, 1232, 10, CARPET_RED)
    brect(img, 1225, 11, 1234, 19, CARPET_RED)
    brect(img, 1227, 20, 1232, 20, CARPET_RED)
    brect(img, 1227, 11, 1232, 11, CARPET_DK)
    bpx(img, 1225, 19, CARPET_DK)
    bpx(img, 1234, 19, CARPET_DK)
    brect(img, 1229, 14, 1230, 16, GOLD)
    # mounted cutlass trophy
    bline(img, 1239, 18, 1247, 10, STONE_LT)
    bline(img, 1240, 18, 1248, 10, WOOD_SEAM)
    brect(img, 1238, 18, 1239, 19, DOOR)
    # treasure chest with an overflowing coin heap
    brect(img, 1248, 43, 1272, 46, GOLD)
    brect(img, 1250, 42, 1252, 43, GOLD)
    brect(img, 1260, 41, 1266, 43, GOLD)
    for x in range(1248, 1273):
        if x % 3 == 0:
            bpx(img, x, 46, GOLD_DK)
    brect(img, 1246, 47, 1274, 50, WOOD_MD)
    brect(img, 1246, 48, 1274, 50, WOOD_DK)
    brect(img, 1244, 51, 1276, 58, WOOD_MD)
    brect(img, 1244, 57, 1276, 58, WOOD_DK)
    brect(img, 1250, 51, 1251, 58, GOLD)
    brect(img, 1266, 51, 1267, 58, GOLD)
    brect(img, 1258, 51, 1260, 52, GOLD)
    bpx(img, 1259, 53, GOLD_DK)


def bg_carpet(img, x0, x1):
    """Req 8: red carpet strip with yellow top/bottom borders."""
    brect(img, x0, CARPET_TOP, x1, CARPET_TOP, GOLD)
    brect(img, x0, CARPET_TOP + 1, x1, CARPET_BOT - 1, CARPET_RED)
    brect(img, x0, CARPET_BOT, x1, CARPET_BOT, GOLD)
    for x in range(x0 + 8, x1, 16):
        bpx(img, x, 49, CARPET_DK)
        bpx(img, x - 1, 50, CARPET_DK)
        bpx(img, x + 1, 50, CARPET_DK)
        bpx(img, x, 50, CARPET_DK)
        bpx(img, x, 51, CARPET_DK)


def build_background_frame(f):
    img = new(BG_W, BG_H)
    bg_sky(img, f)
    bg_sun(img)
    bg_clouds(img, f)
    bg_beach(img)
    bg_fields(img)
    bg_sea(img, f)
    bg_town(img)
    bg_wall(img)
    bg_bricks(img, TOWN_END, WALL_END - 1, FLOOR_TOP, 59)  # pavement thru gate
    brect(img, 781, FLOOR_TOP, 808, FLOOR_TOP, DARK_HOLE)  # threshold
    bg_courtyard(img)
    bg_entrance(img)
    bg_treasure_wall(img)
    bg_planks(img, WALL_END, COURT_END - 1, FLOOR_TOP, 59)
    bg_bricks(img, COURT_END, ENTR_END - 1, FLOOR_TOP, 59)
    bg_planks(img, ENTR_END, 1279, FLOOR_TOP, 59)
    bg_carpet(img, WALL_END, 1279)
    bg_treasure_props(img)
    bg_shore(img, f)
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
    print("verify backgrounds:")
    ok = True

    def chk(label, cond):
        nonlocal ok
        print(f"  {'ok  ' if cond else 'FAIL'} {label}")
        if not cond:
            ok = False

    frames = [Image.open(os.path.join(SPRITE_DIR, f"background-{i}.png"))
              for i in range(1, 6)]
    chk("5 frames of 1280x60 RGB",
        all(im.size == (BG_W, BG_H) and im.mode == "RGB" for im in frames))
    pix = [im.load() for im in frames]

    # only waves/foam/sky details move: all differences left of the wall
    diffs = [(x, y) for x in range(BG_W) for y in range(BG_H)
             if pix[0][x, y] != pix[1][x, y]]
    chk("only sea/foam/sky animate (diffs all x < 760)",
        bool(diffs) and max(x for x, _ in diffs) < TOWN_END)

    # req 1: waves - crest pixels present everywhere on the sea
    crests = sum(1 for x in range(SEA_END) for y in range(HORIZON, 60)
                 if pix[0][x, y] in (SEA_CREST, FOAM, SPARK))
    chk(f"wave crests on the sea ({crests} crest/foam px)", crests > 200)

    # req 4: flat uniform sand (columns clear of the palm)
    flat = all(pix[0][x, y] == SAND
               for x in list(range(SEA_END + WASH[4] + 3, 347))
               + list(range(356, BEACH_END))
               for y in range(HORIZON, 60))
    chk("beach sand flat and uniform", flat)

    # req 3: water fills the whole wash zone, foam only rides on water
    wash_ok = True
    for f in range(5):
        for x in range(SEA_END, SEA_END + WASH[f] + 3):
            for y in range(40, 60):
                if pix[f][x, y] not in (SEA_LIGHT, FOAM):
                    wash_ok = False
    chk("water behind/under foam across the whole wash", wash_ok)

    # req 5: brick mortar lines present on town/wall/entrance floors
    for x0, x1, label in ((FIELDS_END, TOWN_END, "town"),
                          (COURT_END, ENTR_END, "entrance")):
        n = sum(1 for x in range(x0, x1) for y in range(FLOOR_TOP, 60)
                if pix[0][x, y] == MORTAR)
        chk(f"{label} floor is brick pavement (mortar px={n})", n > 120)

    # req 6: wall full height, no sky above or after it
    chk("wall reaches the top of the frame",
        all(pix[0][770, y] == MORTAR or pix[0][770, y] == STONE_FACE
            or pix[0][770, y] == STONE_LT for y in range(0, FLOOR_TOP)))
    skyfree = all(pix[0][x, y] not in (SKY_DAY, SKY_NAVY)
                  for x in range(TOWN_END, BG_W) for y in range(0, BG_H))
    chk("no sky at/after the wall (interior enclosed)", skyfree)

    # req 7: paintings/shield/chest present in the treasure room
    chk("treasure room decorated (gold present)",
        sum(1 for x in range(1100, 1280) for y in range(40, 60)
            if pix[0][x, y] == GOLD) > 30)

    # req 8: carpet with yellow borders; wood planks beside it
    carb = all(pix[0][x, 46] == GOLD and pix[0][x, 55] == GOLD
               and pix[0][x, 50] in (CARPET_RED, CARPET_DK)
               for x in range(840, 1230, 20))
    seam = sum(1 for x in range(830, 970) for y in range(FLOOR_TOP, 60)
               if pix[0][x, y] == WOOD_SEAM)
    chk("carpet strip with yellow outlines full length", carb)
    chk(f"wood plank floor beside the carpet (seam px={seam})", seam > 60)

    # req 9: gradient west of the beach, uniform daylight east of it
    col = [sum(pix[0][x, 3]) for x in range(0, SEA_END, 4)]
    chk("sky gradient (navy -> light) up to the beach",
        col[0] < col[len(col) // 2] < col[-1]
        and pix[0][0, 0] == SKY_NAVY and pix[0][SEA_END - 1, 3] == SKY_DAY)
    uni = all(pix[0][x, y] == SKY_DAY for x in range(390, 640, 10)
              for y in range(0, 6))
    chk("uniform daylight sky from the beach to the wall", uni)
    return ok


def dump_bg(f, x0, x1):
    img = build_background_frame(f).convert("RGB")
    p = img.load()
    names = {SKY_NAVY: ".", SKY_DAY: ".", SEA_MID: "~", SEA_DEEP: "~",
             SEA_LIGHT: "~", SEA_CREST: "^", SPARK: "*", FOAM: "o",
             CLOUD: "c", SUN: "S", SAND: ",", GRASS: '"', GRASS_DK: "w",
             GRASS_LT: "u", WOOD_TRUNK: "|", STONE_FACE: "#", STONE_LT: "+",
             MORTAR: ":", WOOD_LT: "-", WOOD_MD: "=", WOOD_DK: "%",
             WOOD_SEAM: "/", CARPET_RED: "C", CARPET_DK: "@", GOLD: "$",
             GOLD_DK: "$", HOUSE_WALL: "H", ROOF: "R", ROOF_DK: "R",
             WINDOW: "@", DOOR: "d", BANNER: "R", BANNER_DK: "R",
             DARK_HOLE: "@", FLAME: "F", CANVAS: "."}
    for y in range(BG_H):
        print("".join(names.get(p[x, y], "?") for x in range(x0, x1)))


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
