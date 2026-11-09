# Generates a PS2-style (Silent Hill era) worn wingback armchair and exports FBX.
#
# Usage (headless):
#   blender --background --python make_chair.py -- <out.fbx> [preview_dir] [save.blend]
#
# Faces -Y (Blender front), Z up, 1 unit = 1 m. Seat height 0.47 m.
# Two materials: Chair_Fabric (faded floral upholstery) and Chair_Wood.
# Textures are painted procedurally: every texel is rasterised back to the 3D
# point it covers and coloured from that position, so patterns are seamless
# across UV islands. A PS2 grade (saturation, contrast, 5-bit dither) is
# applied before saving.

import bpy, bmesh, math, sys, os
from mathutils import Vector, Matrix
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT_FBX = argv[0] if argv else os.path.join(os.getcwd(), "Chair.fbx")
PREVIEW_DIR = argv[1] if len(argv) > 1 else None
SAVE_BLEND = argv[2] if len(argv) > 2 else None

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
view_layer = bpy.context.view_layer

FABRIC, WOOD = 0, 1
bm = bmesh.new()

def tag(faces, mat):
    for f in faces:
        f.material_index = mat

def box(lo, hi, mat, bevel=0.0, segments=1, cuts=0):
    """Axis-aligned box from lo to hi, optionally subdivided and bevelled."""
    lo, hi = Vector(lo), Vector(hi)
    size = hi - lo
    m = Matrix.Translation((lo + hi) / 2) @ Matrix.Diagonal((*size, 1.0))
    old = set(bm.faces)                      # everything new after this belongs to the box
    bmesh.ops.create_cube(bm, size=1.0, matrix=m)
    new_faces = lambda: [f for f in bm.faces if f not in old]
    if cuts:
        edges = list({e for f in new_faces() for e in f.edges})
        bmesh.ops.subdivide_edges(bm, edges=edges, cuts=cuts, use_grid_fill=True)
    if bevel:
        edges = list({e for f in new_faces() for e in f.edges})
        bmesh.ops.bevel(bm, geom=edges, offset=bevel, segments=segments,
                        profile=0.5, affect="EDGES", clamp_overlap=True)
    faces = new_faces()
    verts = list({v for f in faces for v in f.verts})
    tag(faces, mat)
    return verts

def tube(points, radii, sides, mat, cap=True):
    pts = [Vector(p) for p in points]
    rings = []
    for i, p in enumerate(pts):
        tan = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        ref = Vector((1, 0, 0)) if abs(tan.x) < 0.9 else Vector((0, 0, 1))
        u = (ref - tan * tan.dot(ref)).normalized()
        v = tan.cross(u)
        r = radii[i]
        rings.append([bm.verts.new(p + (u * math.cos(a) + v * math.sin(a)) * r)
                      for a in (2 * math.pi * k / sides + math.pi / sides for k in range(sides))])
    faces = []
    for a, b in zip(rings, rings[1:]):
        for k in range(sides):
            faces.append(bm.faces.new((a[k], a[(k + 1) % sides], b[(k + 1) % sides], b[k])))
    if cap:
        faces.append(bm.faces.new(list(reversed(rings[0]))))
        faces.append(bm.faces.new(rings[-1]))
    tag(faces, mat)
    return [v for r in rings for v in r]

def tilt(verts, pivot, degrees):
    """Lean parts backward (top toward +Y) about the X axis through pivot."""
    R = Matrix.Rotation(math.radians(-degrees), 3, "X")
    p = Vector(pivot)
    for v in verts:
        v.co = p + R @ (v.co - p)

SEAT_Z = 0.38                  # low old armchair; her feet reach the floor
BASE_TOP = 0.28
BACK_TILT = 10.0
PIVOT = (0, 0.17, BASE_TOP)

# Upholstered base.
box((-0.40, -0.33, 0.12), (0.40, 0.33, BASE_TOP), FABRIC, bevel=0.025)
# Seat cushion, sagging in the middle from years of use.
seat = box((-0.28, -0.35, BASE_TOP), (0.28, 0.17, SEAT_Z), FABRIC, bevel=0.035, segments=2, cuts=1)
for v in seat:
    if v.co.z > SEAT_Z - 0.01:
        k = max(0.0, 1 - (v.co.x / 0.28) ** 2) * max(0.0, 1 - ((v.co.y + 0.09) / 0.26) ** 2)
        v.co.z -= 0.018 * k

# Rolled arms.
for s in (1, -1):
    box((0.28 * s, -0.33, BASE_TOP), (0.40 * s, 0.30, 0.55), FABRIC, bevel=0.02)
    tube([(0.355 * s, -0.365, 0.555), (0.355 * s, -0.34, 0.555), (0.355 * s, 0.30, 0.555)],
         [0.050, 0.060, 0.060], 10, FABRIC)

# Back: tall, arched at the top, leaning back.
back = box((-0.40, 0.17, BASE_TOP), (0.40, 0.33, 1.02), FABRIC, cuts=3)
for v in back:
    if v.co.z > 0.95:
        v.co.z += 0.07 * math.cos(min(1.0, abs(v.co.x) / 0.40) * math.pi / 2)
tilt(back, PIVOT, BACK_TILT)
# Back cushion (button tufted in the texture).
bc = box((-0.27, 0.09, SEAT_Z - 0.01), (0.27, 0.18, 0.96), FABRIC, bevel=0.04, segments=2, cuts=2)
for v in bc:                                    # pillowy: bulge the front face
    if v.co.y < 0.10:
        k = max(0.0, 1 - (v.co.x / 0.27) ** 2) * max(0.0, 1 - ((v.co.z - 0.71) / 0.25) ** 2)
        v.co.y -= 0.025 * k
tilt(bc, PIVOT, BACK_TILT)

# Wings: side panels on top of the arms, curving forward at the top.
for s in (1, -1):
    # Built flush against the back (same tilt) so they read as one piece.
    w = box((0.33 * s, 0.03, 0.60), (0.40 * s, 0.33, 1.00), FABRIC, cuts=2)
    for v in w:
        t = max(0.0, (v.co.z - 0.60) / 0.40)
        if v.co.y < 0.12:
            v.co.y += 0.16 * max(0.0, (t - 0.55) / 0.45) ** 2   # rounded top-front corner
        v.co.x -= 0.03 * t * s * (1.0 if v.co.y < 0.2 else 0.3)  # wings angle inward
    tilt(w, PIVOT, BACK_TILT)

# Short turned wooden legs and a front apron trim.
for sx in (1, -1):
    for sy, splay in ((-1, 0.0), (1, 0.015)):
        x, y = 0.35 * sx, 0.28 * sy
        tube([(x, y, 0.125), (x, y, 0.10), (x, y + splay * 0.3, 0.07),
              (x + 0.005 * sx, y + splay, 0.02), (x + 0.005 * sx, y + splay, 0.0)],
             [0.030, 0.022, 0.026, 0.016, 0.018], 8, WOOD)
box((-0.405, -0.338, 0.115), (0.405, -0.325, 0.155), WOOD, bevel=0.004, segments=1)

bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
mesh = bpy.data.meshes.new("Chair")
bm.to_mesh(mesh)
bm.free()
chair = bpy.data.objects.new("Chair", mesh)
scene.collection.objects.link(chair)
for p in mesh.polygons:
    p.use_smooth = True
mesh.set_sharp_from_angle(angle=math.radians(50)) if hasattr(mesh, "set_sharp_from_angle") else None

# PSX low poly: collapse-decimate the whole chair (symmetric).
CHAIR_TRIS = 1000
dm = chair.modifiers.new("Decimate", "DECIMATE")
dm.decimate_type = "COLLAPSE"
dm.ratio = min(1.0, CHAIR_TRIS / sum(len(p.vertices) - 2 for p in mesh.polygons))
dm.use_symmetry = True
dm.symmetry_axis = "X"
for o in scene.objects:
    o.select_set(False)
chair.select_set(True)
view_layer.objects.active = chair
bpy.ops.object.modifier_apply(modifier="Decimate")

def make_material(name, rgb):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1.0)
    try:
        m.use_nodes = True
        bsdf = m.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
            bsdf.inputs["Roughness"].default_value = 0.9
    except Exception:
        pass
    return m

MAT_FABRIC = make_material("Chair_Fabric", (0.55, 0.38, 0.40))
MAT_WOOD = make_material("Chair_Wood", (0.30, 0.18, 0.10))
mesh.materials.append(MAT_FABRIC)
mesh.materials.append(MAT_WOOD)

# UVs: smart-unwrap each material separately so each gets its own full 0-1 texture.
mesh.uv_layers.new(name="UVMap")
for o in scene.objects:
    o.select_set(False)
chair.select_set(True)
view_layer.objects.active = chair
for mat_index in (FABRIC, WOOD):
    bpy.ops.object.mode_set(mode="OBJECT")
    for p in mesh.polygons:
        p.select = (p.material_index == mat_index)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.02, scale_to_bounds=True)
bpy.ops.object.mode_set(mode="OBJECT")

tris = sum(len(p.vertices) - 2 for p in mesh.polygons)
print(f"CHAIR tris={tris} verts={len(mesh.vertices)}")

# ─── Textures ─────────────────────────────────────────────────────────────────
TEX_DIR = os.path.join(os.path.dirname(os.path.abspath(OUT_FBX)), "Textures")
os.makedirs(TEX_DIR, exist_ok=True)

def rasterize(mesh, mat_index, res):
    pos = np.zeros((res, res, 3), np.float32)
    nrm = np.zeros((res, res, 3), np.float32)
    mask = np.zeros((res, res), bool)
    uvl = mesh.uv_layers.active.data
    mesh.calc_loop_triangles()
    for lt in mesh.loop_triangles:
        if lt.material_index != mat_index:
            continue
        uv = np.array([uvl[l].uv for l in lt.loops], np.float64) * res
        P = np.array([mesh.vertices[v].co for v in lt.vertices], np.float64)
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
        iy, ix = np.nonzero(inside)
        pos[iy + y0, ix + x0] = p[iy, ix]
        nrm[iy + y0, ix + x0] = np.array(lt.normal)
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

BAYER4 = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) + 0.5) / 16 - 0.5

def grade(img):
    """Same PS2 retro-horror grade as the grandma textures."""
    lum = img @ np.array([0.299, 0.587, 0.114], np.float32)
    img = lum[..., None] + (img - lum[..., None]) * 1.45
    img = (img - 0.42) * 1.32 + 0.40
    img = np.clip(img, 0, 1) ** 1.08
    h, w = img.shape[:2]
    dither = np.tile(BAYER4, (h // 4 + 1, w // 4 + 1))[:h, :w][..., None]
    # No baked dither: with big point-sampled texels it shows as a checkerboard.
    return np.clip(np.round(img * 31) / 31, 0, 1)

PIXELATE = 2          # paint at full res, save at 1/PIXELATE (chunky PSX texels)

def save_png(img, name):
    if PIXELATE > 1:
        h_, w_ = img.shape[0] // PIXELATE, img.shape[1] // PIXELATE
        img = img[:h_ * PIXELATE, :w_ * PIXELATE].reshape(h_, PIXELATE, w_, PIXELATE, 3).mean((1, 3))
    img = grade(img)
    h, w = img.shape[:2]
    im = bpy.data.images.new(name, w, h, alpha=False)
    rgba = np.concatenate([img, np.ones((h, w, 1), np.float32)], -1).astype(np.float32)
    im.pixels.foreach_set(rgba.ravel())
    im.filepath_raw = os.path.join(TEX_DIR, name + ".png")
    im.file_format = "PNG"
    im.save()
    print("TEXTURE", im.filepath_raw)
    return im


# Baked lighting, PSX style: ambient occlusion (creases between cushions,
# arms and back, under the seat, between the legs) plus a soft light from
# above, painted straight into the texture.
from mathutils.bvhtree import BVHTree
CHAIR_BVH = BVHTree.FromObject(chair, bpy.context.evaluated_depsgraph_get())

def bake_light(img, pos, nrm, mask, rays=16, dist=0.25, step=2):
    res = mask.shape[0]
    rng = np.random.default_rng(5)
    u1, u2 = rng.random(rays), rng.random(rays)
    r_, phi = np.sqrt(u1), 2 * np.pi * u2
    local = np.stack([r_ * np.cos(phi), r_ * np.sin(phi), np.sqrt(1 - u1)], -1)
    ao = np.zeros(mask.shape, np.float32)
    for by in range(0, res, step):
        for bx in range(0, res, step):
            blk = mask[by:by + step, bx:bx + step]
            if not blk.any():
                continue
            iy, ix = np.argwhere(blk)[0]
            n = Vector(nrm[by + iy, bx + ix])
            if n.length < 0.5:
                continue
            n.normalize()
            p = Vector(pos[by + iy, bx + ix]) + n * 0.004
            t = n.orthogonal().normalized()
            b = n.cross(t)
            hits = sum(1 for d in local
                       if CHAIR_BVH.ray_cast(p, t * d[0] + b * d[1] + n * d[2], dist)[0] is not None)
            ao[by:by + step, bx:bx + step] = hits / rays
    for _ in range(4):                                       # soften
        acc = ao.copy(); cnt = np.ones_like(ao)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            m = np.roll(mask, (dy, dx), (0, 1))
            acc += np.roll(ao, (dy, dx), (0, 1)) * m
            cnt += m
        ao = np.where(mask, acc / cnt, ao)
    sky = np.clip(nrm[..., 2], -1, 1)                        # +1 facing up, -1 facing the floor
    light = (0.98 + 0.18 * sky) * (1.0 - 0.55 * np.clip(ao * 1.3, 0, 1))
    img *= light[..., None]
    mix(img, (0.06, 0.03, 0.04), 0.25 * np.clip(ao * 1.6 - 0.5, 0, 1))   # deepest creases go near-black

def lattice(p, cell, offset=0.0):
    c = p / cell + offset
    return (c - np.floor(c) - 0.5) * cell

# Fabric: faded mauve upholstery with an olive/cream floral damask, worn
# patches where hands and bodies rubbed it, dark stains and grime low down.
FR = 256
fp, fn, fmask = rasterize(mesh, FABRIC, FR)
X, Y, Z = fp[..., 0], fp[..., 1], fp[..., 2]
fab = np.empty(fp.shape, np.float32); fab[:] = (0.56, 0.37, 0.42)
fab *= (1 + 0.06 * wave_noise(fp, 500, seed=1) + 0.05 * wave_noise(fp, 40, seed=2))[..., None]
loc = lattice(fp, 0.15)            # big enough to survive 128px texels
r = np.linalg.norm(loc, axis=-1)
ang = np.arctan2(loc[..., 2] + loc[..., 0] * 0.3, loc[..., 0] + loc[..., 1])
rose = r < 0.044 * (0.70 + 0.30 * np.cos(6 * ang))
mix(fab, (0.86, 0.74, 0.66), 0.80 * rose)                                      # cream roses
mix(fab, (0.62, 0.30, 0.36), 0.80 * (r < 0.016))                               # deep rose centres
mix(fab, (0.36, 0.20, 0.26), 0.70 * (np.abs(r - 0.047) < 0.005))               # dark outline
leaf_loc = lattice(fp, 0.15, 0.5)
lr_ = np.linalg.norm(leaf_loc * np.array([1.0, 1.0, 1.8], np.float32), axis=-1)
mix(fab, (0.42, 0.50, 0.30), 0.85 * (lr_ < 0.028))                              # olive leaves
# Button tufting on the back cushion: dark dimples with small buttons.
on_back = (Y > 0.04) & (Y < 0.20) & (Z > 0.50) & (Z < 0.98) & (np.abs(X) < 0.27) & (fn[..., 1] < -0.3)
grid = lattice(np.stack([X, Y * 0, Z], -1), 0.12, 0.5)
bd = np.linalg.norm(grid, axis=-1)
mix(fab, (0.22, 0.12, 0.16), 0.75 * gauss(bd, 0.016) * on_back)
mix(fab, (0.40, 0.22, 0.28), 1.0 * (bd < 0.007) * on_back)
mix(fab, (0.18, 0.10, 0.12), 0.35 * (np.abs(np.abs(grid[..., 0]) - np.abs(grid[..., 2])) < 0.004) * on_back)  # pleats
# Wear: faded, threadbare patches on arm tops and the seat front edge.
wear = gauss(np.abs(X) - 0.355, 0.05) * gauss(Z - 0.58, 0.04) * gauss(Y + 0.25, 0.12)
wear += gauss(Z - SEAT_Z, 0.03) * gauss(Y + 0.33, 0.06) * (np.abs(X) < 0.26)
wear += gauss(Z - (SEAT_Z - 0.03), 0.06) * gauss(Y + 0.05, 0.12) * gauss(X, 0.16) * (fn[..., 2] > 0.5)  # where she sits
mix(fab, (0.70, 0.60, 0.56), 0.55 * np.clip(wear, 0, 1) * (0.6 + 0.4 * wave_noise(fp, 120, seed=3)))
# Stains: a few dark, irregular blotches with darker rims.
st = wave_noise(fp, 18, n=6, seed=4) + 0.4 * wave_noise(fp, 70, seed=5)
mix(fab, (0.30, 0.20, 0.16), 0.55 * np.clip((st - 1.45) * 4, 0, 1))
mix(fab, (0.24, 0.15, 0.12), 0.45 * gauss(st - 1.45, 0.05))
# Grime: darker toward the floor and in the crevices around the seat cushion.
mix(fab, (0.18, 0.12, 0.12), 0.45 * np.clip((0.30 - Z) / 0.18, 0, 1))
crevice = gauss(Z - (BASE_TOP + 0.005), 0.015) + gauss(np.abs(X) - 0.28, 0.012) * (Z > BASE_TOP) * (Z < 0.62)
mix(fab, (0.15, 0.09, 0.10), 0.55 * np.clip(crevice, 0, 1))
bake_light(fab, fp, fn, fmask)
fab = dilate(fab, fmask)
IMG_FABRIC = save_png(fab, "Chair_Fabric")

# Wood: dark varnished walnut, grain running along each leg, scuffed tips.
WR = 256
wp, wn, wmask = rasterize(mesh, WOOD, WR)
X, Y, Z = wp[..., 0], wp[..., 1], wp[..., 2]
wd = np.empty(wp.shape, np.float32); wd[:] = (0.32, 0.18, 0.10)
grain = np.sin((X * 0.7 + Y) * 420 + 6 * wave_noise(wp * np.array([1, 1, 0.15], np.float32), 30, seed=6))
wd *= (0.85 + 0.15 * grain)[..., None]
mix(wd, (0.16, 0.08, 0.05), 0.5 * np.clip(wave_noise(wp, 60, seed=7) - 0.6, 0, 1))
mix(wd, (0.55, 0.40, 0.28), 0.5 * gauss(Z - 0.0, 0.012))                      # scuffed feet
mix(wd, (0.70, 0.55, 0.40), 0.35 * np.clip(wn[..., 2], 0, 1) * gauss(Z - 0.135, 0.02) * (np.abs(Y) > 0.2) * (np.abs(Y) < 0.32))  # worn leg tops only
bake_light(wd, wp, wn, wmask)
wd = dilate(wd, wmask)
IMG_WOOD = save_png(wd, "Chair_Wood")

def attach_texture(mat, img):
    nt = mat.node_tree
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    bsdf = nt.nodes.get("Principled BSDF")
    if bsdf:
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    tex.interpolation = "Closest"         # PSX: hard texels, no filtering
    nt.nodes.active = tex
    mat.diffuse_color = (1, 1, 1, 1)

attach_texture(MAT_FABRIC, IMG_FABRIC)
attach_texture(MAT_WOOD, IMG_WOOD)

# ─── Export ───────────────────────────────────────────────────────────────────
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

if SAVE_BLEND:
    bpy.ops.wm.save_as_mainfile(filepath=SAVE_BLEND)

# ─── Previews ─────────────────────────────────────────────────────────────────
if PREVIEW_DIR:
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "TEXTURE"
    scene.render.resolution_x, scene.render.resolution_y = 512, 512
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    cam.data.type = "ORTHO"
    scene.collection.objects.link(cam)
    scene.camera = cam
    def shoot(name, loc, target, scale=1.4):
        cam.location = Vector(loc)
        cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()
        cam.data.ortho_scale = scale
        scene.render.filepath = os.path.join(PREVIEW_DIR, name + ".png")
        bpy.ops.render.render(write_still=True)
    shoot("chair_front", (0, -5, 0.55), (0, 0, 0.55))
    shoot("chair_side", (5, 0, 0.55), (0, 0, 0.55))
    shoot("chair_3q", (3.5, -3.5, 2.0), (0, 0, 0.5))
    shoot("chair_back", (-3.0, 4.0, 1.6), (0, 0, 0.5))
    print("PREVIEWS", PREVIEW_DIR)
