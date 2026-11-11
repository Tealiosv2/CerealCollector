# Generates the first-person hand (PSX style, unrigged) and exports FBX.
#
# Usage (headless):
#   blender --background --python make_hand.py -- <out.fbx> [preview_dir]
#
# A glove-like hand in three separate pieces, so the existing procedural arm
# animation can curl it without a rig:
#   FP_Hand_Palm     origin at the wrist  (palm + short wrist cuff)
#   FP_Hand_Fingers    origin at the knuckles (four fingers as one mitten block, first segment)
#   FP_Hand_FingerTips origin at the middle joint (second segment, child of Fingers)
#   FP_Hand_Thumb    origin at the thumb base
#   FP_Arm_Fore, FP_Arm_Upper  skin forearm and upper arm (no sleeve), pivots at elbow and shoulder
# Units match the house (~3x real scale) and the placeholder arm's hand.
# Orientation: fingers point forward (-Y in Blender = +Z in Unity), palm down,
# thumb on the left (a right hand seen from behind; Blender +X is that side when
# looking down -Y). One shared skin texture,
# painted procedurally, half-res pixelated, no baked dither.

import bpy, bmesh, math, sys, os
from mathutils import Vector, Matrix
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT_FBX = argv[0] if argv else os.path.join(os.getcwd(), "FP_Hand.fbx")
PREVIEW_DIR = argv[1] if len(argv) > 1 else None

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
view_layer = bpy.context.view_layer

# ─── Dimensions (scene units) ────────────────────────────────────────────────
PALM_LEN = 0.26          # wrist -> knuckles
FINGER_LEN = 0.23        # knuckles -> fingertips
SIDES = 8                # vertices around each cross-section (low poly)

def section(cx, y, cz, half_w, half_h, n=SIDES, flat_bottom=0.0, arch=0.0):
    """Rounded-rectangle (superellipse) cross-section in the XZ plane at Y=y.
    flat_bottom flattens the palm side, arch lifts the middle of the top."""
    pts = []
    for k in range(n):
        a = 2 * math.pi * k / n + math.pi / n
        c, s = math.cos(a), math.sin(a)
        x = math.copysign(abs(c) ** 0.55, c) * half_w
        z = math.copysign(abs(s) ** 0.75, s) * half_h
        if z < 0:
            z *= (1.0 - flat_bottom)
        else:
            z += arch * half_h * (1 - (x / half_w) ** 2)
        pts.append(Vector((cx + x, y, cz + z)))
    return pts

def loft(bm, rings, cap_start=True, cap_end=True, tip=None):
    vrings = [[bm.verts.new(p) for p in r] for r in rings]
    n = len(rings[0])
    for a, b in zip(vrings, vrings[1:]):
        for k in range(n):
            bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]))
    if cap_start:
        bm.faces.new(list(reversed(vrings[0])))
    if tip is not None:                      # rounded end: fan to a tip vertex
        t = bm.verts.new(tip)
        last = vrings[-1]
        for k in range(n):
            bm.faces.new((last[k], last[(k + 1) % n], t))
    elif cap_end:
        bm.faces.new(vrings[-1])

def make_object(name, bm, origin):
    """Mesh object whose origin (pivot) is at `origin` (given in hand space)."""
    for v in bm.verts:
        v.co -= Vector(origin)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.location = origin
    scene.collection.objects.link(ob)
    for p in me.polygons:
        p.use_smooth = True
    return ob

# ─── Palm with wrist cuff (origin at the wrist) ──────────────────────────────
bm = bmesh.new()
palm_rings = [
    section(0.0,  0.07, 0.000, 0.085, 0.075),                      # forearm stub (inside the sleeve/forearm)
    section(0.0,  0.00, 0.000, 0.092, 0.060, flat_bottom=0.2),     # wrist
    section(0.0, -0.10, 0.006, 0.128, 0.050, flat_bottom=0.40, arch=0.10),   # heel of the hand
    section(0.0, -PALM_LEN, 0.004, 0.128, 0.040, flat_bottom=0.35, arch=0.12),   # knuckles
]
loft(bm, palm_rings, cap_start=True, cap_end=True)
palm = make_object("FP_Hand_Palm", bm, (0.0, 0.0, 0.0))

# ─── Fingers: one mitten block in two segments, rounded tips ─────────────────
# Glove-like: the four fingers stay together. They bend twice: at the
# knuckles (FP_Hand_Fingers) and once more halfway along (FP_Hand_FingerTips,
# a child of the first segment). The segments overlap slightly at the middle
# joint so no gap opens when it bends. The thumb is one piece.
K = -PALM_LEN
J = K - 0.105                                   # middle finger joint (second bend)

def shape_fingers(bm):
    # Rounded fingertip line: middle two "fingers" a little longer.
    for v in bm.verts:
        if v.co.y < K - 0.15:
            x = v.co.x / 0.12
            v.co.y -= 0.022 * (1 - min(1.0, abs(x - 0.05)) ** 2) * min(1.0, (K - 0.15 - v.co.y) / 0.08)
    # Shallow grooves along the top between fingers (suggests four fingers).
    for gx in (-0.062, 0.0, 0.062):
        for v in bm.verts:
            if v.co.z > 0.0 and v.co.y < K - 0.01:
                w = math.exp(-((v.co.x - gx) / 0.018) ** 2)
                v.co.z -= 0.006 * w

bm = bmesh.new()
loft(bm, [
    section(0.0, K + 0.000, 0.004, 0.126, 0.036, flat_bottom=0.30, arch=0.12),
    section(0.0, K - 0.060, 0.000, 0.124, 0.034, flat_bottom=0.26, arch=0.08),
    section(0.0, J - 0.010, -0.005, 0.121, 0.031, flat_bottom=0.22, arch=0.06),   # just past the joint
], cap_start=True, cap_end=True)
shape_fingers(bm)
fingers = make_object("FP_Hand_Fingers", bm, (0.0, K, 0.004))

bm = bmesh.new()
loft(bm, [
    section(0.0, J + 0.010, -0.003, 0.122, 0.032, flat_bottom=0.22, arch=0.06),   # just before the joint
    section(0.0, K - 0.175, -0.013, 0.113, 0.028, flat_bottom=0.15),
    section(0.0, K - FINGER_LEN + 0.020, -0.020, 0.104, 0.024),
    section(0.0, K - FINGER_LEN, -0.024, 0.088, 0.017),                            # blunt, rounded fingertip row
], cap_start=True, cap_end=True)
shape_fingers(bm)
fingertips = make_object("FP_Hand_FingerTips", bm, (0.0, J, -0.004))

# ─── Thumb: separate, from the side of the palm near the wrist ───────────────
bm = bmesh.new()
TB = Vector((0.112, -0.050, -0.012))                  # thumb base. Looking down the arm (-Y), +X is
                                                       # the LEFT side, where a right hand's thumb is (palm down).
                                                       # (Verified in Unity: thumb lands on the left.)
tdir = Vector((0.30, -1.0, -0.22)).normalized()       # forward, out to the left, a bit down
tu = tdir.cross(Vector((0, 0, 1))).normalized()
tv = tu.cross(tdir).normalized()
thumb_rings = []
for t, r in ((0.000, 0.042), (0.085, 0.036), (0.165, 0.026)):
    c = TB + tdir * t
    thumb_rings.append([c + (tu * math.cos(a) * r + tv * math.sin(a) * r * 0.8)
                        for a in (2 * math.pi * k / 6 for k in range(6))])
loft(bm, thumb_rings, cap_start=True, cap_end=False, tip=TB + tdir * 0.195)
thumb = make_object("FP_Hand_Thumb", bm, tuple(TB))

# Fingers and thumb hang off the palm, so animating the palm moves the lot.
# Hierarchy: Palm -> Fingers -> FingerTips, Palm -> Thumb. Nothing is rotated
# at rest, so a child's local position is its pivot minus its parent's pivot.
for child, parent in ((fingers, palm), (thumb, palm), (fingertips, fingers)):
    pivot = child.location.copy()
    child.parent = parent
    child.location = pivot - parent.location if parent is not palm else pivot
view_layer.update()


# ─── Arm: forearm and upper arm, skin (no sleeve), low poly ──────────────────
# Laid out as a straight continuation of the hand along +Y (toward the
# shoulder), so the skin texture paints them in place. Each piece pivots at
# its upper joint, matching the first-person arm rig:
#   FP_Arm_Fore   pivot at the elbow, runs to the wrist (0.72 long)
#   FP_Arm_Upper  pivot at the shoulder, runs to the elbow (0.78 long)
FORE_LEN, UPPER_LEN = 0.72, 0.78
ELBOW_Y, SHOULDER_Y = FORE_LEN, FORE_LEN + UPPER_LEN

def arm_section(y, half_w, half_h, cz=0.0, n=SIDES):
    """Slightly flattened oval cross-section (wider than tall), at Y=y."""
    pts = []
    for k in range(n):
        a = 2 * math.pi * k / n + math.pi / n
        pts.append(Vector((math.cos(a) * half_w, y, cz + math.sin(a) * half_h)))
    return pts

bm = bmesh.new()
loft(bm, [
    arm_section(0.035, 0.084, 0.074),               # wrist (tucks into the hand's wrist cuff)
    arm_section(0.200, 0.092, 0.080),
    arm_section(0.420, 0.112, 0.094, cz=0.004),     # forearm muscle
    arm_section(0.620, 0.104, 0.092, cz=0.002),
    arm_section(ELBOW_Y + 0.030, 0.100, 0.096),     # just past the elbow (overlaps the upper arm)
], cap_start=True, cap_end=True)
for v in bm.verts:                                  # bony point of the elbow (back/top side)
    if v.co.y > ELBOW_Y - 0.06 and v.co.z > 0.05:
        v.co.z += 0.018 * math.exp(-((v.co.x) / 0.05) ** 2)
fore = make_object("FP_Arm_Fore", bm, (0.0, ELBOW_Y, 0.0))

bm = bmesh.new()
loft(bm, [
    arm_section(ELBOW_Y - 0.020, 0.098, 0.094),     # elbow end (overlaps the forearm)
    arm_section(ELBOW_Y + 0.250, 0.112, 0.104, cz=-0.004),   # biceps
    arm_section(ELBOW_Y + 0.520, 0.122, 0.112),
    arm_section(SHOULDER_Y + 0.040, 0.128, 0.118),  # shoulder end (hidden at the screen edge)
], cap_start=True, cap_end=True)
upper = make_object("FP_Arm_Upper", bm, (0.0, SHOULDER_Y, 0.0))
HAND = [palm, fingers, fingertips, thumb, fore, upper]
tris = {o.name: sum(len(p.vertices) - 2 for p in o.data.polygons) for o in HAND}
print("HAND_TRIS", tris, "total", sum(tris.values()))

# ─── Material + shared UVs ───────────────────────────────────────────────────
mat = bpy.data.materials.new("FP_Hand")
try:
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.85
except Exception:
    pass
for o in HAND:
    o.data.materials.append(mat)
    o.data.uv_layers.new(name="UVMap")

for o in scene.objects:
    o.select_set(False)
for o in HAND:
    o.select_set(True)
view_layer.objects.active = palm
bpy.ops.object.mode_set(mode="EDIT")                 # multi-object edit: one shared UV layout
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.03, scale_to_bounds=True)
bpy.ops.object.mode_set(mode="OBJECT")

# ─── Skin texture (painted from 3D position, PSX resolution) ─────────────────
TEX_DIR = os.path.join(os.path.dirname(os.path.abspath(OUT_FBX)), "Textures")
os.makedirs(TEX_DIR, exist_ok=True)
RES, PIXELATE = 512, 2          # hand + whole arm share it: 256px after pixelating

def rasterize(objs, res):
    pos = np.zeros((res, res, 3), np.float32)
    nrm = np.zeros((res, res, 3), np.float32)
    mask = np.zeros((res, res), bool)
    for ob in objs:
        me = ob.data
        mw = ob.matrix_world
        uvl = me.uv_layers.active.data
        me.calc_loop_triangles()
        for lt in me.loop_triangles:
            uv = np.array([uvl[l].uv for l in lt.loops], np.float64) * res
            P = np.array([mw @ me.vertices[v].co for v in lt.vertices], np.float64)
            N = np.array([(mw.to_3x3() @ me.vertices[v].normal).normalized() for v in lt.vertices], np.float64)
            x0, x1 = int(max(0, np.floor(uv[:, 0].min()))), int(min(res - 1, np.ceil(uv[:, 0].max())))
            y0, y1 = int(max(0, np.floor(uv[:, 1].min()))), int(min(res - 1, np.ceil(uv[:, 1].max())))
            if x1 < x0 or y1 < y0:
                continue
            xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            (ax, ay), (bx, by), (cx, cy) = uv
            den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(den) < 1e-12:
                continue
            w0 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / den
            w1 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / den
            w2 = 1 - w0 - w1
            inside = (w0 >= -0.02) & (w1 >= -0.02) & (w2 >= -0.02)
            if not inside.any():
                continue
            p = w0[..., None] * P[0] + w1[..., None] * P[1] + w2[..., None] * P[2]
            n = w0[..., None] * N[0] + w1[..., None] * N[1] + w2[..., None] * N[2]
            iy, ix = np.nonzero(inside)
            pos[iy + y0, ix + x0] = p[iy, ix]
            nrm[iy + y0, ix + x0] = n[iy, ix]
            mask[iy + y0, ix + x0] = True
    return pos, nrm, mask

def dilate(img, mask, steps=6):
    img, mask = img.copy(), mask.copy()
    for _ in range(steps):
        acc = np.zeros_like(img); cnt = np.zeros(mask.shape, np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            m = np.roll(mask, (dy, dx), (0, 1))
            acc += np.roll(img, (dy, dx), (0, 1)) * m[..., None]
            cnt += m
        new = (~mask) & (cnt > 0)
        img[new] = acc[new] / cnt[new][:, None]
        mask |= new
    img[~mask] = img[mask].mean(0)
    return img

def wave_noise(p, freq, n=8, seed=0):
    r = np.random.default_rng(seed)
    out = np.zeros(p.shape[:-1], np.float32)
    for _ in range(n):
        k = r.normal(size=3); k = k / np.linalg.norm(k) * freq * r.uniform(0.7, 1.3)
        out += np.sin(p @ k + r.uniform(0, 6.283))
    return out / math.sqrt(n / 2)

def gauss(x, s):
    return np.exp(-(x / s) ** 2)

def mix(img, color, w):
    w = np.clip(w, 0, 1)[..., None]
    img[:] = img * (1 - w) + np.array(color, np.float32) * w

def grade(img):
    """Same PS2/PSX grade as the other props: saturation, contrast, 5-bit levels."""
    lum = img @ np.array([0.299, 0.587, 0.114], np.float32)
    img = lum[..., None] + (img - lum[..., None]) * 1.35
    img = (img - 0.42) * 1.25 + 0.40
    img = np.clip(img, 0, 1) ** 1.05
    return np.clip(np.round(img * 31) / 31, 0, 1)

def save_png(img, name):
    h_, w_ = img.shape[0] // PIXELATE, img.shape[1] // PIXELATE
    img = img[:h_ * PIXELATE, :w_ * PIXELATE].reshape(h_, PIXELATE, w_, PIXELATE, 3).mean((1, 3))
    img = grade(img)
    im = bpy.data.images.new(name, w_, h_, alpha=False)
    rgba = np.concatenate([img, np.ones((h_, w_, 1), np.float32)], -1).astype(np.float32)
    im.pixels.foreach_set(rgba.ravel())
    im.filepath_raw = os.path.join(TEX_DIR, name + ".png")
    im.file_format = "PNG"
    im.save()
    print("TEXTURE", im.filepath_raw)
    return im

hp, hn, hmask = rasterize(HAND, RES)
X, Y, Z = hp[..., 0], hp[..., 1], hp[..., 2]
top = hn[..., 2] > 0.25                    # back of the hand
under = hn[..., 2] < -0.25                 # palm side

skin = np.empty(hp.shape, np.float32); skin[:] = (0.84, 0.66, 0.56)
skin *= (1 + 0.045 * wave_noise(hp, 70, seed=1) + 0.03 * wave_noise(hp, 300, seed=2))[..., None]
mix(skin, (0.82, 0.52, 0.46), 0.18 * np.clip(wave_noise(hp, 30, seed=3), 0, 1))   # blotchy warmth
mix(skin, (0.92, 0.72, 0.66), 0.45 * under)                                        # paler, pinker palm
# Baked light: top lit, underside and sides darker (PSX props carry their shading).
skin *= (0.90 + 0.12 * np.clip(hn[..., 2], -1, 1))[..., None]
# Knuckles: a row of reddish bumps across the back of the hand + finger knuckle creases.
for kx in (-0.093, -0.031, 0.031, 0.093):
    mix(skin, (0.80, 0.50, 0.46), 0.40 * gauss(X - kx, 0.022) * gauss(Y - (-PALM_LEN + 0.005), 0.018) * top)
    for jy in (-PALM_LEN - 0.075, -PALM_LEN - 0.150):            # finger joints
        mix(skin, (0.55, 0.36, 0.32), 0.45 * gauss(Y - jy, 0.004) * gauss(X - kx, 0.020) * top)
# Lines between the fingers (they are one block; the texture separates them).
for gx in (-0.062, 0.0, 0.062):
    mix(skin, (0.42, 0.26, 0.22), 0.65 * gauss(X - gx, 0.0045) * (Y < -PALM_LEN - 0.005) * (np.abs(hn[..., 0]) < 0.6))
# Fingernails: pale pink ovals on the back of each fingertip.
for kx in (-0.093, -0.031, 0.031, 0.093):
    tip_y = -PALM_LEN - FINGER_LEN + 0.03 - 0.018 * (1 - min(1.0, abs(kx / 0.12 - 0.05)) ** 2)
    d = ((X - kx) / 0.020) ** 2 + ((Y - tip_y) / 0.028) ** 2
    mix(skin, (0.93, 0.76, 0.72), 0.95 * (d < 1.0) * top)
    mix(skin, (0.70, 0.48, 0.44), 0.60 * (np.abs(d - 1.0) < 0.25) * top)
# Thumb nail.
tt = TB + tdir * 0.15
d = np.linalg.norm(hp - np.array(tt, np.float32), axis=-1)
mix(skin, (0.93, 0.76, 0.72), 0.90 * (d < 0.020) * (hn[..., 2] > 0.0))
# Palm creases (underside) and wrist crease.
mix(skin, (0.50, 0.32, 0.28), 0.40 * gauss(Y + 0.10 + 0.25 * X, 0.004) * under * (np.abs(X) < 0.10))
mix(skin, (0.50, 0.32, 0.28), 0.40 * gauss(Y + 0.17 - 0.10 * X, 0.004) * under * (np.abs(X) < 0.11))
mix(skin, (0.55, 0.36, 0.32), 0.40 * gauss(Y - 0.005, 0.005) * (Y > -0.02) * (Y < 0.03))
# Faint veins on the back of the hand.
mix(skin, (0.55, 0.52, 0.62), 0.25 * (np.abs(np.sin(X * 90 + Y * 25)) < 0.08) * top * (Y > -0.20) * (Y < -0.02))
# Arm: reddish, wrinkled elbow (back), soft crease inside the elbow, faint veins
# on the inner forearm.
mix(skin, (0.80, 0.52, 0.46), 0.35 * gauss(Y - ELBOW_Y, 0.05) * top)
mix(skin, (0.55, 0.36, 0.32), 0.35 * (np.abs(np.sin((Y - ELBOW_Y) * 260)) < 0.25) * gauss(Y - ELBOW_Y, 0.035) * top)
mix(skin, (0.60, 0.40, 0.36), 0.30 * gauss(Y - ELBOW_Y, 0.012) * under)
mix(skin, (0.55, 0.55, 0.68), 0.22 * (np.abs(np.sin(X * 70 + Y * 9)) < 0.07) * under * (Y > 0.10) * (Y < 0.60))
skin = dilate(skin, hmask)
img = save_png(skin, "FP_Hand")

nt = mat.node_tree
tex = nt.nodes.new("ShaderNodeTexImage")
tex.image = img
tex.interpolation = "Closest"                 # PSX: hard texels
bsdf = nt.nodes.get("Principled BSDF")
if bsdf:
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
nt.nodes.active = tex

# ─── Export ───────────────────────────────────────────────────────────────────
os.makedirs(os.path.dirname(os.path.abspath(OUT_FBX)), exist_ok=True)
for o in scene.objects:
    o.select_set(False)
bpy.ops.export_scene.fbx(
    filepath=OUT_FBX,
    object_types={"MESH"},
    apply_scale_options="FBX_SCALE_UNITS",
    axis_forward="-Z", axis_up="Y",
    mesh_smooth_type="FACE",
    bake_anim=False,
)
print("EXPORTED", OUT_FBX)

# ─── Previews (open hand and gripping) ───────────────────────────────────────
if PREVIEW_DIR:
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "TEXTURE"
    scene.render.resolution_x, scene.render.resolution_y = 480, 480
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    cam.data.type = "ORTHO"
    scene.collection.objects.link(cam)
    scene.camera = cam
    centre = Vector((-0.01, -0.24, 0.0))

    def shoot(name, loc, scale=0.75, up="Y"):
        cam.location = centre + Vector(loc)
        cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", up).to_euler()
        cam.data.ortho_scale = scale
        scene.render.filepath = os.path.join(PREVIEW_DIR, name + ".png")
        bpy.ops.render.render(write_still=True)

    def views(prefix):
        shoot(prefix + "top", (0, 0.0001, 3), up="Y")
        shoot(prefix + "under", (0, 0.0001, -3), up="Y")
        shoot(prefix + "side", (-3, 0, 0), up="Z")
        shoot(prefix + "3q", (-1.8, 2.0, 1.6), up="Z")
        shoot(prefix + "fp", (0.35, 1.6, 0.9), scale=0.9, up="Z")    # roughly the first-person angle

    views("hand_open_")
    # Grip: the fingers bend at the knuckles and again at the middle joint (X axis)
    # and here the thumb is turned in, as when holding a cereal box.
    # Positive X curls toward the palm (checked: the tips end up under the hand).
    fingers.rotation_euler = (math.radians(55), 0, 0)       # bend at the knuckles
    fingertips.rotation_euler = (math.radians(70), 0, 0)    # and again halfway along
    view_layer.update()
    views("hand_grip_")
    centre = Vector((0.0, 0.45, 0.0))
    fingers.rotation_euler = (0, 0, 0); fingertips.rotation_euler = (0, 0, 0)
    view_layer.update()
    shoot("arm_top", (0, 0.0001, 4), scale=2.2, up="Y")
    shoot("arm_side", (-4, 0, 0), scale=2.2, up="Z")
    shoot("arm_3q", (-2.5, 1.5, 2.0), scale=2.2, up="Z")
    print("PREVIEWS", PREVIEW_DIR)
