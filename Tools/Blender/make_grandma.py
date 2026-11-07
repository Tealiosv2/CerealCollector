# Generates a PS2-style (Silent Hill era) rigged elderly woman and exports FBX.
#
# Usage (headless):
#   blender --background --python make_grandma.py -- <out.fbx> [preview_dir]
#
# Pipeline:
#   1. A vertex "framework" with per-vertex radii is turned into one continuous
#      body mesh by the Skin modifier, then subdivided once.
#   2. The head is subdivided again for extra detail.
#   3. Anatomy is shaped procedurally (bust, belly, buttocks, face structure,
#      knees, flattened hands and feet). No eyes: a texture supplies the face.
#   4. UVs: the head gets its own cylindrical unwrap (material Grandma_Head) so
#      a front face photo/painting maps directly; the body is smart-unwrapped
#      (material Grandma_Body). UV layouts are exported as painting guides.
#   5. A Unity-Humanoid-named skeleton is added with automatic (heat) weights.
#   6. A separate skirt object borrows weights from the nearest body vertices.
#
# Character faces -Y (Blender front), A-pose, Z up, 1 unit = 1 m.

import bpy, bmesh, math, sys, os
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT_FBX = argv[0] if argv else os.path.join(os.getcwd(), "Grandma.fbx")
PREVIEW_DIR = argv[1] if len(argv) > 1 else None
MAKE_SKIRT = True
MAKE_HAIR = False   # bald; set True for grey hair pulled back into a ponytail

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
view_layer = bpy.context.view_layer

def activate(obj, mode=None):
    for o in scene.objects:
        o.select_set(False)
    obj.select_set(True)
    view_layer.objects.active = obj
    if mode:
        bpy.ops.object.mode_set(mode=mode)

def smooth01(d, r):
    """Smooth falloff: 1 at d=0, 0 at d>=r."""
    if d >= r:
        return 0.0
    x = 1.0 - (d / r) ** 2
    return x * x

# ─── 1. Body framework (position, (radius_x, radius_y)) ───────────────────────
# Mirrored entries use an "L"/"R" suffix; x is given for the left (+X) side.
NODES = {}
EDGES = []

def node(name, co, r, mirror=False):
    if mirror:
        x, y, z = co
        NODES[name + "L"] = ((x, y, z), r)
        NODES[name + "R"] = ((-x, y, z), r)
    else:
        NODES[name] = (co, r)

def edge(a, b, mirror=False):
    if mirror:
        for s in ("L", "R"):
            EDGES.append((a + s if a in MIRRORED else a, b + s if b in MIRRORED else b))
    else:
        EDGES.append((a, b))

# Torso, rounded upper back (y grows toward the back), head pushed forward.
# Radii are larger than the final body: the subdivision step shrinks the hull.
node("crotch",   (0, 0.000, 0.740), (0.130, 0.100))
node("hips",     (0, 0.015, 0.850), (0.215, 0.145))   # widest point
node("belly",    (0, 0.000, 0.960), (0.180, 0.135))
node("waist",    (0, 0.010, 1.060), (0.165, 0.120))
node("chest",    (0, 0.020, 1.160), (0.180, 0.120))
node("yoke",     (0, 0.045, 1.255), (0.185, 0.100))
node("neckBase", (0, 0.045, 1.320), (0.054, 0.054))
node("neckTop",  (0, 0.015, 1.385), (0.046, 0.048))
node("jaw",      (0, -0.015, 1.420), (0.070, 0.082))
node("cheek",    (0, -0.020, 1.470), (0.085, 0.100))
node("skull",    (0, -0.020, 1.530), (0.095, 0.115))
node("crown",    (0, -0.010, 1.590), (0.078, 0.098))

# Arms (A-pose, ~45 degrees down). Hands and feet are simple mitten/shoe
# shapes (no separate fingers or toes); the texture supplies detail.
MIRRORED = set()
def mnode(name, co, r):
    MIRRORED.add(name)
    node(name, co, r, mirror=True)

mnode("collar",   (0.085, 0.045, 1.270), (0.075, 0.072))
mnode("shoulder", (0.190, 0.040, 1.255), (0.068, 0.066))   # deltoid
mnode("bicep",    (0.280, 0.040, 1.160), (0.052, 0.052))
mnode("elbow",    (0.370, 0.035, 1.065), (0.042, 0.042))
mnode("forearm",  (0.450, 0.025, 0.985), (0.044, 0.040))
mnode("wrist",    (0.525, 0.005, 0.905), (0.031, 0.031))
mnode("knuckle",  (0.585, -0.005, 0.845), (0.046, 0.046))
mnode("fingers",  (0.645, -0.015, 0.785), (0.036, 0.036))

# Legs: thighs kept slightly apart for clean weights; calf bulges backward.
mnode("hipJoint", (0.105, 0.000, 0.720), (0.090, 0.095))
mnode("thigh",    (0.105, 0.000, 0.580), (0.076, 0.080))
mnode("knee",     (0.105, -0.005, 0.445), (0.056, 0.058))
mnode("calf",     (0.105, 0.022, 0.310), (0.058, 0.062))
mnode("ankle",    (0.105, 0.025, 0.080), (0.034, 0.036))
mnode("ball",     (0.105, -0.095, 0.030), (0.048, 0.026))
mnode("toe",      (0.105, -0.170, 0.026), (0.036, 0.020))

for a, b in [("crotch", "hips"), ("hips", "belly"), ("belly", "waist"), ("waist", "chest"),
             ("chest", "yoke"), ("yoke", "neckBase"), ("neckBase", "neckTop"),
             ("neckTop", "jaw"), ("jaw", "cheek"), ("cheek", "skull"), ("skull", "crown")]:
    edge(a, b)
for a, b in [("yoke", "collar"), ("collar", "shoulder"), ("shoulder", "bicep"), ("bicep", "elbow"),
             ("elbow", "forearm"), ("forearm", "wrist"), ("wrist", "knuckle"), ("knuckle", "fingers"),
             ("crotch", "hipJoint"), ("hipJoint", "thigh"), ("thigh", "knee"), ("knee", "calf"),
             ("calf", "ankle"), ("ankle", "ball"), ("ball", "toe")]:
    edge(a, b, mirror=True)

names = list(NODES)
idx = {n: i for i, n in enumerate(names)}
frame = bpy.data.meshes.new("GrandmaFrame")
frame.from_pydata([NODES[n][0] for n in names], [(idx[a], idx[b]) for a, b in EDGES], [])
body = bpy.data.objects.new("Grandma", frame)
scene.collection.objects.link(body)

skin_mod = body.modifiers.new("Skin", "SKIN")
skin_mod.branch_smoothing = 0.6
skin_mod.use_smooth_shade = True
for n in names:
    sv = frame.skin_vertices[0].data[idx[n]]
    sv.radius = NODES[n][1]
    sv.use_root = (n == "crotch")
sub = body.modifiers.new("Subsurf", "SUBSURF")
sub.levels = sub.render_levels = 1

activate(body)
bpy.ops.object.modifier_apply(modifier="Skin")
bpy.ops.object.modifier_apply(modifier="Subsurf")

# ─── 2/3. Head detail and anatomy shaping ─────────────────────────────────────
bm = bmesh.new()
bm.from_mesh(body.data)

HEAD_Z = 1.395                                  # faces above this are "head"
head_faces = [f for f in bm.faces if f.calc_center_median().z > HEAD_Z]
head_edges = list({e for f in head_faces for e in f.edges})
bmesh.ops.subdivide_edges(bm, edges=head_edges, cuts=1, use_grid_fill=True, smooth=1.0)
bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
# One more level on the face itself so the nose, brow and chin have vertices
# to hold them (positions are reshaped by the head profile below anyway).
face_faces = [f for f in bm.faces
              if 1.40 < f.calc_center_median().z < 1.59 and f.calc_center_median().y < -0.03]
face_edges = list({e for f in face_faces for e in f.edges})
bmesh.ops.subdivide_edges(bm, edges=face_edges, cuts=1, use_grid_fill=True)
bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])

def push(center, radius, offset, scale=(1, 1, 1)):
    """Move vertices near `center` by `offset`, with smooth falloff.
    `scale` stretches the influence region per axis (ellipsoidal)."""
    c, o = Vector(center), Vector(offset)
    for v in bm.verts:
        d = v.co - c
        d = Vector((d.x / scale[0], d.y / scale[1], d.z / scale[2]))
        w = smooth01(d.length, radius)
        if w:
            v.co += o * w

def mirror_push(center, radius, offset, scale=(1, 1, 1)):
    x, y, z = center
    ox, oy, oz = offset
    push((x, y, z), radius, (ox, oy, oz), scale)
    push((-x, y, z), radius, (-ox, oy, oz), scale)

def _search(pick, test, band):
    """Widen the search band until some vertices match (sparse mesh areas)."""
    while band < 0.2:
        vals = [v for v in bm.verts if test(v, band)]
        if vals:
            return pick(vals)
        band *= 1.5
    raise ValueError("no surface found")

def front(x, z, band=0.012):
    """Y of the body's front surface (most negative y) near (x, z)."""
    return _search(lambda vs: min(v.co.y for v in vs),
                   lambda v, b: abs(v.co.x - x) < b and abs(v.co.z - z) < b and v.co.y < 0.05, band)

def side_x(y, z, band=0.015):
    """X of the head/body's outer (+X) surface near (y, z), ignoring the arms."""
    return _search(lambda vs: max(v.co.x for v in vs),
                   lambda v, b: abs(v.co.y - y) < b and abs(v.co.z - z) < b and 0 < v.co.x < 0.14, band)

def back(x, z, band=0.012):
    """Y of the body's back surface (most positive y) near (x, z)."""
    return _search(lambda vs: max(v.co.y for v in vs),
                   lambda v, b: abs(v.co.x - x) < b and abs(v.co.z - z) < b and v.co.y > -0.05, band)

# Body.
mirror_push((0.085, front(0.085, 1.150), 1.150), 0.090, (0.008, -0.060, -0.035))  # sagging bust
push((0, front(0, 0.950), 0.950), 0.130, (0, -0.014, -0.012), (1.3, 1, 1))         # soft belly
mirror_push((0.085, back(0.085, 0.820), 0.820), 0.110, (0.004, 0.050, -0.020))     # buttocks
mirror_push((0.095, back(0.095, 0.680), 0.680), 0.080, (0.000, 0.015, 0.000))      # back of thighs
mirror_push((0.170, 0.015, 0.850), 0.120, (0.018, 0, -0.010))                      # wide hips
push((0, 0.100, 1.235), 0.140, (0, 0.022, 0.0), (1.4, 1, 1))                        # dowager's hump
mirror_push((0.105, front(0.105, 0.450), 0.450), 0.045, (0, -0.010, 0))            # kneecaps
mirror_push((0.125, 0.020, 0.560), 0.080, (0.010, 0, -0.010))                      # loose thigh flesh
mirror_push((0.080, front(0.08, 1.275), 1.275), 0.050, (0, -0.008, 0.004))         # collarbones

# ─── Head: reshape to a designed profile ──────────────────────────────────────
# Every head vertex keeps its angle around the head's vertical axis and its
# relative height, but its distance from the axis is replaced by a designed
# shape: an elliptical skull defined slice by slice, plus smooth bumps for the
# facial structure. No eyes: a texture supplies the face.
NECK_Z, TOP_Z = 1.370, 1.645
# (z, half width, front depth, back depth), measured from the head axis.
HEAD_PROFILE = [
    (1.370, 0.046, 0.044, 0.058),
    (1.395, 0.050, 0.056, 0.064),   # under the jaw
    (1.420, 0.058, 0.090, 0.072),   # chin
    (1.445, 0.064, 0.088, 0.082),   # mouth
    (1.470, 0.069, 0.091, 0.092),
    (1.500, 0.074, 0.095, 0.103),   # nose / cheekbones
    (1.535, 0.077, 0.094, 0.110),   # eyes
    (1.560, 0.078, 0.097, 0.112),   # brow
    (1.590, 0.075, 0.090, 0.107),
    (1.615, 0.064, 0.073, 0.090),
    (1.633, 0.045, 0.050, 0.062),
    (1.645, 0.004, 0.004, 0.004),
]

def catmull(z):
    """Smooth (Catmull-Rom) interpolation of HEAD_PROFILE at height z."""
    P = HEAD_PROFILE
    z = max(P[0][0], min(P[-1][0], z))
    i = max(0, min(len(P) - 2, next(k for k in range(len(P) - 1) if P[k + 1][0] >= z)))
    p0, p1, p2, p3 = P[max(i - 1, 0)], P[i], P[i + 1], P[min(i + 2, len(P) - 1)]
    t = (z - p1[0]) / (p2[0] - p1[0])
    out = []
    for c in range(1, 4):
        a, b, cc, d = p0[c], p1[c], p2[c], p3[c]
        out.append(0.5 * ((2 * b) + (-a + cc) * t + (2 * a - 5 * b + 4 * cc - d) * t * t
                          + (-a + 3 * b - 3 * cc + d) * t ** 3))
    return out

def _g(x, s):
    return math.exp(-(x / s) ** 2)

def head_detail(z, th):
    """Extra radius (m) for facial structure. th = 0 at the front of the face."""
    ath = abs(th)
    d = 0.0
    # Nose: narrow bridge growing to a drooping tip, then tucking under.
    if 1.466 < z < 1.548:
        if z >= 1.478:
            t = (1.548 - z) / (1.548 - 1.478)
            height = 0.006 + 0.026 * t ** 1.3
            width = 0.10 + 0.06 * t
        else:
            height = 0.032 * (z - 1.466) / 0.012
            width = 0.16
        d += height * _g(th, width)
    d += 0.007 * _g(ath - 0.17, 0.06) * _g(z - 1.481, 0.008)     # nostril wings
    d -= 0.013 * _g(ath - 0.36, 0.16) * _g(z - 1.533, 0.014)     # eye sockets
    d += 0.005 * _g(th, 0.55) * _g(z - 1.557, 0.008)             # brow ridge
    d += 0.007 * _g(ath - 0.68, 0.20) * _g(z - 1.503, 0.016)     # cheekbones
    d -= 0.008 * _g(ath - 0.55, 0.20) * _g(z - 1.462, 0.016)     # sunken cheeks
    d += 0.004 * _g(th, 0.37) * _g(z - 1.453, 0.009)             # lips (wide mouth)
    d -= 0.004 * _g(th, 0.33) * _g(z - 1.450, 0.0025)            # mouth line
    d += 0.008 * _g(th, 0.26) * _g(z - 1.420, 0.010)             # chin
    d += 0.020 * _g(ath - math.pi / 2 - 0.08, 0.11) * _g(z - 1.503, 0.024)  # ears
    return d

def head_axis_y(z):
    # The head sits forward of the neck: blend the axis from neck to skull.
    k = max(0.0, min(1.0, (z - NECK_Z) / 0.06))
    return 0.012 * (1 - k) + (-0.020) * k

head_vs = [v for v in bm.verts if v.co.z >= NECK_Z]
orig_top = max(v.co.z for v in head_vs)
for v in head_vs:
    z = NECK_Z + (v.co.z - NECK_Z) * (TOP_Z - NECK_Z) / (orig_top - NECK_Z)
    ay = head_axis_y(z)
    th = math.atan2(v.co.x, -(v.co.y - ay))
    half_w, depth_f, depth_b = catmull(z)
    depth = depth_f if math.cos(th) > 0 else depth_b
    r = 1.0 / math.sqrt((math.sin(th) / half_w) ** 2 + (math.cos(th) / depth) ** 2)
    r += head_detail(z, th)
    target = Vector((r * math.sin(th), ay - r * math.cos(th), z))
    k = max(0.0, min(1.0, (z - NECK_Z) / 0.025))        # blend into the neck
    k = k * k * (3 - 2 * k)
    v.co = v.co.lerp(target, k)

# Hands: flatten each hand across the palm (perpendicular to the arm, in XZ).
for s in (1, -1):
    w0 = Vector(NODES["wristL"][0]) * Vector((s, 1, 1))
    tip = Vector(NODES["fingersL"][0]) * Vector((s, 1, 1)) + (Vector(NODES["fingersL"][0]) * Vector((s, 1, 1)) - w0) * 0.25
    axis = (tip - w0).normalized()
    palm_n = Vector((0.707 * s, 0, 0.707))
    for v in bm.verts:
        rel = v.co - w0
        t = rel.dot(axis)
        if t < -0.01 or t > (tip - w0).length:
            continue
        radial = rel - axis * t
        if radial.length > 0.07:
            continue
        k = min(1.0, (t + 0.01) / 0.04)                 # blend in past the wrist
        along_n = radial.dot(palm_n)
        v.co -= palm_n * along_n * 0.55 * k

# Feet: flat sole on the ground.
for v in bm.verts:
    if v.co.z < 0.0:
        v.co.z = 0.0

bm.normal_update()
bm.to_mesh(body.data)
bm.free()
for p in body.data.polygons:
    p.use_smooth = True

# PSX-style low poly: collapse-decimate the shaped body, keeping it symmetric.
TARGET_RATIO = 0.33
dec = body.modifiers.new("Decimate", "DECIMATE")
dec.decimate_type = "COLLAPSE"
dec.ratio = TARGET_RATIO
dec.use_symmetry = True
dec.symmetry_axis = "X"
activate(body)
bpy.ops.object.modifier_apply(modifier="Decimate")

# ─── 4. Materials and UVs ─────────────────────────────────────────────────────
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

MAT_HEAD = make_material("Grandma_Head", (0.70, 0.62, 0.55))
MAT_BODY = make_material("Grandma_Body", (0.70, 0.62, 0.55))
body.data.materials.append(MAT_HEAD)
body.data.materials.append(MAT_BODY)

uv_layer = body.data.uv_layers.new(name="UVMap")
is_head = [p.center.z > HEAD_Z for p in body.data.polygons]
for p, h in zip(body.data.polygons, is_head):
    p.material_index = 0 if h else 1

# Body: smart unwrap of non-head faces.
activate(body, "EDIT")
bpy.ops.mesh.select_all(action="DESELECT")
bpy.ops.object.mode_set(mode="OBJECT")
for p, h in zip(body.data.polygons, is_head):
    p.select = not h
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.02, scale_to_bounds=True)
bpy.ops.object.mode_set(mode="OBJECT")

# Head: cylindrical unwrap around the head's vertical axis; front of face at
# u = 0.5, seam down the back of the skull. Uniform texel scale, centred in V.
HEAD_AXIS = Vector((0, -0.03, 0))
head_top = max(v.co.z for v in body.data.vertices)
head_h = head_top - HEAD_Z
circ = 2 * math.pi * 0.085
uvs = body.data.uv_layers.active.data
for p, h in zip(body.data.polygons, is_head):
    if not h:
        continue
    us = []
    for li in p.loop_indices:
        co = body.data.vertices[body.data.loops[li].vertex_index].co
        a = math.atan2(co.x - HEAD_AXIS.x, -(co.y - HEAD_AXIS.y))   # 0 at the face
        us.append(0.5 + a / (2 * math.pi))
    if max(us) - min(us) > 0.5:                     # face straddles the back seam
        us = [u + 1.0 if u < 0.5 else u for u in us]
    for li, u in zip(p.loop_indices, us):
        co = body.data.vertices[body.data.loops[li].vertex_index].co
        v = (co.z - HEAD_Z) / circ                  # same scale as u
        uvs[li].uv = (u / 1.06 + 0.02, 0.5 + (v - head_h / circ / 2) / 1.06)

# ─── 5. Skeleton (Unity Humanoid names) and automatic weights ─────────────────
def L(name):  return NODES[name + "L"][0]
def lr(co, s): return (co[0] * s, co[1], co[2])

BONES = [
    ("Hips",       (0, 0.010, 0.860), (0, 0.010, 0.970), None),
    ("Spine",      (0, 0.010, 0.970), (0, 0.015, 1.080), "Hips"),
    ("Chest",      (0, 0.015, 1.080), (0, 0.030, 1.200), "Spine"),
    ("UpperChest", (0, 0.030, 1.200), (0, 0.040, 1.300), "Chest"),
    ("Neck",       (0, 0.040, 1.300), (0, 0.000, 1.425), "UpperChest"),
    ("Head",       (0, 0.000, 1.425), (0, -0.020, 1.640), "Neck"),
]
for s, side in ((1, "Left"), (-1, "Right")):
    BONES += [
        (side + "Shoulder", lr((0.030, 0.040, 1.275), s), lr(L("shoulder"), s), "UpperChest"),
        (side + "UpperArm", lr(L("shoulder"), s), lr(L("elbow"), s), side + "Shoulder"),
        (side + "LowerArm", lr(L("elbow"), s), lr(L("wrist"), s), side + "UpperArm"),
        (side + "Hand",     lr(L("wrist"), s), lr((0.665, -0.020, 0.765), s), side + "LowerArm"),
        (side + "UpperLeg", lr((0.105, 0.000, 0.800), s), lr(L("knee"), s), "Hips"),
        (side + "LowerLeg", lr(L("knee"), s), lr(L("ankle"), s), side + "UpperLeg"),
        (side + "Foot",     lr(L("ankle"), s), lr(L("ball"), s), side + "LowerLeg"),
        (side + "Toes",     lr(L("ball"), s), lr((0.105, -0.195, 0.026), s), side + "Foot"),
    ]

arm_data = bpy.data.armatures.new("GrandmaRig")
rig = bpy.data.objects.new("GrandmaRig", arm_data)
scene.collection.objects.link(rig)
activate(rig, "EDIT")
for name, h, t, parent in BONES:
    eb = arm_data.edit_bones.new(name)
    eb.head, eb.tail = Vector(h), Vector(t)
    if parent:
        eb.parent = arm_data.edit_bones[parent]
bpy.ops.object.mode_set(mode="OBJECT")

for o in scene.objects:
    o.select_set(False)
body.select_set(True)
rig.select_set(True)
view_layer.objects.active = rig
bpy.ops.object.parent_set(type="ARMATURE_AUTO")

# Fallback: any vertex the heat solver missed gets its nearest bone.
bone_segs = {b.name: (rig.matrix_world @ b.head_local, rig.matrix_world @ b.tail_local) for b in arm_data.bones}
def nearest_bone(co):
    best, bd = None, 1e9
    for n, (h, t) in bone_segs.items():
        ab = t - h
        k = max(0.0, min(1.0, (co - h).dot(ab) / ab.length_squared))
        d = (co - (h + ab * k)).length
        if d < bd:
            best, bd = n, d
    return best
unweighted = 0
for v in body.data.vertices:
    if sum(g.weight for g in v.groups) < 1e-4:
        unweighted += 1
        vg = body.vertex_groups.get(nearest_bone(v.co)) or body.vertex_groups.new(name=nearest_bone(v.co))
        vg.add([v.index], 1.0, "REPLACE")

# ─── 6. Skirt (separate object, weights borrowed from the body) ───────────────
skirt = None
if MAKE_SKIRT:
    SEG, RINGS = 12, [1.000, 0.930, 0.840, 0.720, 0.580, 0.420]
    SK_C = Vector((0.0, 0.01))
    # Radial extent of the body per (height band, angular sector). Shirt sits
    # ~1 cm outside the body above the waist, so that is added in. Each
    # vertex is pushed out by 1/cos(pi/SEG) so the flat panels between
    # vertices (not just the corners) clear the body: no buttocks or hips
    # poking through between corners.
    pts = []
    for v in body.data.vertices:
        c = v.co
        d = Vector((c.x, c.y)) - SK_C
        if d.length < 0.32 and 0.38 < c.z < 1.06:                  # torso/legs, not arms
            pts.append((c.z, math.atan2(d.y, d.x), d.length + (0.011 if c.z > 0.88 else 0.0)))
    half = math.pi / SEG
    def sector_extent(z, ang, band=0.05):
        best = 0.0
        for pz, pa, pr in pts:
            da = abs((pa - ang + math.pi) % (2 * math.pi) - math.pi)
            if abs(pz - z) < band and da < half * 1.6:
                best = max(best, pr)
        return best
    ring_r = []
    prev = [0.0] * SEG
    for i, z in enumerate(RINGS):
        flare = 0.014 + 0.028 * i / (len(RINGS) - 1)
        rr = []
        for k in range(SEG):
            r = sector_extent(z, 2 * math.pi * k / SEG) / math.cos(half) + flare
            rr.append(max(r, prev[k], 0.12))                         # never narrows going down
        rr = [max(rr[k], 0.85 * max(rr[k - 1], rr[(k + 1) % SEG])) for k in range(SEG)]  # no dents
        ring_r.append(rr)
        prev = rr
    sbm = bmesh.new()
    rings = []
    for z, rr in zip(RINGS, ring_r):
        rings.append([sbm.verts.new((SK_C.x + rr[k] * math.cos(2 * math.pi * k / SEG),
                                     SK_C.y + rr[k] * math.sin(2 * math.pi * k / SEG), z)) for k in range(SEG)])
    for a, b in zip(rings, rings[1:]):
        for k in range(SEG):
            sbm.faces.new((a[k], a[(k + 1) % SEG], b[(k + 1) % SEG], b[k]))
    bmesh.ops.recalc_face_normals(sbm, faces=sbm.faces)
    smesh = bpy.data.meshes.new("GrandmaSkirt")
    sbm.to_mesh(smesh)
    sbm.free()
    skirt = bpy.data.objects.new("Grandma_Skirt", smesh)
    scene.collection.objects.link(skirt)
    for p in smesh.polygons:
        p.use_smooth = True
    MAT_SKIRT = make_material("Grandma_Skirt", (0.30, 0.22, 0.18))
    smesh.materials.append(MAT_SKIRT)
    # Simple cylindrical UVs (u around, v down the skirt).
    suv = smesh.uv_layers.new(name="UVMap").data
    for p in smesh.polygons:
        us = []
        for li in p.loop_indices:
            co = smesh.vertices[smesh.loops[li].vertex_index].co
            us.append((math.atan2(co.x, -(co.y - 0.01)) / (2 * math.pi)) % 1.0)
        if max(us) - min(us) > 0.5:
            us = [u + 1.0 if u < 0.5 else u for u in us]
        for li, u in zip(p.loop_indices, us):
            co = smesh.vertices[smesh.loops[li].vertex_index].co
            suv[li].uv = (u / 1.06, (co.z - RINGS[-1]) / (RINGS[0] - RINGS[-1]))
    # Solidify so the skirt has thickness (visible from inside/below).
    sol = skirt.modifiers.new("Solidify", "SOLIDIFY")
    sol.thickness = 0.006
    sol.offset = 1.0
    activate(skirt)
    bpy.ops.object.modifier_apply(modifier="Solidify")
    # Weights: average of the 6 nearest body vertices.
    kd = KDTree(len(body.data.vertices))
    for v in body.data.vertices:
        kd.insert(v.co, v.index)
    kd.balance()
    gname = {g.index: g.name for g in body.vertex_groups}
    for name in gname.values():
        skirt.vertex_groups.new(name=name)
    for v in smesh.vertices:
        acc = {}
        hits = kd.find_n(v.co, 6)
        wsum = 0.0
        for co, i, d in hits:
            w = 1.0 / max(d, 1e-4)
            wsum += w
            for g in body.data.vertices[i].groups:
                acc[g.group] = acc.get(g.group, 0.0) + g.weight * w
        total = sum(acc.values())
        for gi, w in acc.items():
            if w / total > 0.02:
                skirt.vertex_groups[gname[gi]].add([v.index], w / total, "REPLACE")
    skirt.parent = rig
    m = skirt.modifiers.new("Armature", "ARMATURE")
    m.object = rig

# ─── 6b. Shirt, hair, ponytail, glasses ───────────────────────────────────────
GROUP = {g.name: g.index for g in body.vertex_groups}

def attach_to_rig(obj):
    obj.parent = rig
    mod = obj.modifiers.new("Armature", "ARMATURE")
    mod.object = rig

def solidify(obj, thickness, offset=-1.0):
    sol = obj.modifiers.new("Solidify", "SOLIDIFY")
    sol.thickness = thickness
    sol.offset = offset
    activate(obj)
    bpy.ops.object.modifier_apply(modifier="Solidify")

def shell(name, face_pred, offset, mat, thickness=0.003, boundary_fix=None):
    """Copy the body faces selected by face_pred(center, weights), inflate
    them along the normals, and return a new skinned object. UVs and skin
    weights are inherited from the body. boundary_fix(vert) can reposition
    the open edge (e.g. to smooth a stair-stepped hairline)."""
    sb = bmesh.new()
    sb.from_mesh(body.data)
    dl = sb.verts.layers.deform.active
    for v in sb.verts:
        v.co += v.normal * offset
    def weights(f):
        acc = {}
        for v in f.verts:
            for gi, w in v[dl].items():
                acc[gi] = acc.get(gi, 0.0) + w / len(f.verts)
        return acc
    drop = [f for f in sb.faces if not face_pred(f.calc_center_median(), weights(f))]
    bmesh.ops.delete(sb, geom=drop, context="FACES")
    if boundary_fix:
        for v in [v for v in sb.verts if v.is_boundary]:
            boundary_fix(v)
    for f in sb.faces:
        f.material_index = 0
    me = bpy.data.meshes.new(name)
    sb.to_mesh(me)
    sb.free()
    obj = bpy.data.objects.new(name, me)
    scene.collection.objects.link(obj)
    for g in body.vertex_groups:                 # same order, so deform indices match
        obj.vertex_groups.new(name=g.name)
    me.materials.clear()
    me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = True
    solidify(obj, thickness)
    attach_to_rig(obj)
    return obj

def wsum(w, names):
    return sum(w.get(GROUP[n], 0.0) for n in names if n in GROUP)

def tube(bm_, points, radii, sides=8, closed=False, cap=True):
    """Loft rings of `sides` vertices along a polyline. Returns rings."""
    pts = [Vector(p) for p in points]
    n = len(pts)
    rings = []
    prev_u = None
    for i, p in enumerate(pts):
        if closed:
            tan = (pts[(i + 1) % n] - pts[(i - 1) % n]).normalized()
        else:
            tan = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        if prev_u is None:
            u_, v_ = basis_for(tan)
        else:                                    # parallel transport: no twisting
            u_ = (prev_u - tan * prev_u.dot(tan)).normalized()
            v_ = tan.cross(u_)
        prev_u = u_
        r = radii[i] if isinstance(radii, (list, tuple)) else radii
        rings.append([bm_.verts.new(p + (u_ * math.cos(a) + v_ * math.sin(a)) * r)
                      for a in (2 * math.pi * k / sides for k in range(sides))])
    count = n if closed else n - 1
    for i in range(count):
        a, b = rings[i], rings[(i + 1) % n]
        for k in range(sides):
            bm_.faces.new((a[k], a[(k + 1) % sides], b[(k + 1) % sides], b[k]))
    if cap and not closed:
        bm_.faces.new(list(reversed(rings[0])))
        bm_.faces.new(rings[-1])
    return rings

def basis_for(axis):
    ref = Vector((0, 0, 1)) if abs(axis.z) < 0.9 else Vector((1, 0, 0))
    u_ = (ref - axis * axis.dot(ref)).normalized()
    return u_, axis.cross(u_)

def rigid_object(name, bm_, mat, bone="Head"):
    me = bpy.data.meshes.new(name)
    bmesh.ops.recalc_face_normals(bm_, faces=bm_.faces)
    bm_.to_mesh(me)
    bm_.free()
    obj = bpy.data.objects.new(name, me)
    scene.collection.objects.link(obj)
    me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = True
    vg = obj.vertex_groups.new(name=bone)
    vg.add(list(range(len(me.vertices))), 1.0, "REPLACE")
    attach_to_rig(obj)
    return obj

def head_surface(z, th, out=0.0):
    """Point on the designed head surface at height z, angle th (0 = face)."""
    half_w, depth_f, depth_b = catmull(z)
    depth = depth_f if math.cos(th) > 0 else depth_b
    r = 1.0 / math.sqrt((math.sin(th) / half_w) ** 2 + (math.cos(th) / depth) ** 2)
    r += head_detail(z, th) + out
    ay = head_axis_y(z)
    return Vector((r * math.sin(th), ay - r * math.cos(th), z))

# Shirt: a dusty-rose blouse, round neck, three-quarter sleeves, tucked into the skirt.
MAT_SHIRT = make_material("Grandma_Shirt", (0.78, 0.52, 0.58))
ELBOWS = [Vector(lr(L("elbow"), s)) for s in (1, -1)]
TORSO = ["Hips", "Spine", "Chest", "UpperChest", "LeftShoulder", "RightShoulder",
         "LeftUpperArm", "RightUpperArm"]
def neckline_z(y):
    return 1.335 - 0.050 * max(0.0, min(1.0, -(y - 0.02) / 0.13))
def shirt_pred(c, w):
    if c.z < 0.90 or c.z > neckline_z(c.y) or w.get(GROUP["Neck"], 0) > 0.4:
        return False
    if wsum(w, TORSO) > 0.5:
        return True
    near_elbow = min((c - e).length for e in ELBOWS) < 0.10
    return near_elbow and wsum(w, ["LeftLowerArm", "RightLowerArm"]) > 0.3
WRISTS = [Vector(lr(L("wrist"), s)) for s in (1, -1)]
CUFF_T = 0.075                         # sleeve ends this far past the elbow
def clean_shirt_edges(v):
    """Snap the jagged (decimated) open edges onto clean lines: a straight
    cuff across the forearm, the curved neckline, and a level hem."""
    c = v.co
    if abs(c.x) > 0.24:                                   # sleeve cuff
        i = 0 if c.x > 0 else 1
        axis = (WRISTS[i] - ELBOWS[i]).normalized()
        t = (c - ELBOWS[i]).dot(axis)
        v.co = c + axis * (CUFF_T - t)
    elif c.z > 1.15:                                       # neckline
        c.z = neckline_z(c.y)
    else:                                                  # hem, tucked in the skirt
        c.z = 0.905
shirt = shell("Grandma_Shirt", shirt_pred, 0.007, MAT_SHIRT, boundary_fix=clean_shirt_edges)

body_cos = [v.co for v in body.data.vertices]
hair = ponytail = None
if MAKE_HAIR:
    # Hair: grey, pulled back from a receding hairline into a low ponytail.
    MAT_HAIR = make_material("Grandma_Hair", (0.62, 0.62, 0.64))
    def hairline(ath):
        if ath < 0.9:
            return 1.588 - 0.025 * (ath / 0.9) ** 2
        if ath < 1.85:
            return 1.548
        t = (ath - 1.85) / (math.pi - 1.85)
        return 1.548 - 0.090 * t
    def hair_pred(c, w):
        if c.z < 1.40:
            return False
        th = math.atan2(c.x, -(c.y - head_axis_y(c.z)))
        return c.z > hairline(abs(th))
    def smooth_hairline(v):
        # Snap the open edge of the hair onto the hairline curve itself.
        th = math.atan2(v.co.x, -(v.co.y - head_axis_y(v.co.z)))
        v.co = head_surface(hairline(abs(th)), th, out=0.006)
    hair = shell("Grandma_Hair", hair_pred, 0.006, MAT_HAIR, boundary_fix=smooth_hairline)

    # Ponytail: a tapered tube from the nape, kept clear of the neck and back.
    MAT_PONY = make_material("Grandma_Ponytail", (0.62, 0.62, 0.64))
    def back_surface(z):
        ys = [c.y for c in body_cos if abs(c.x) < 0.03 and abs(c.z - z) < 0.015]
        return max(ys) if ys else 0.1
    anchor = head_surface(1.488, math.pi, out=0.004)
    plan = [(anchor.y - 0.004, 1.490, 0.017), (anchor.y + 0.022, 1.468, 0.021),
            (anchor.y + 0.032, 1.425, 0.019), (anchor.y + 0.034, 1.375, 0.013),
            (anchor.y + 0.030, 1.335, 0.004)]
    pts, rads = [], []
    for y, z, r in plan:
        y = max(y, back_surface(z) + r + 0.008) if z < 1.47 else y
        pts.append((0.0, y, z)); rads.append(r)
    pbm = bmesh.new()
    pony_rings = tube(pbm, pts, rads, sides=10)
    ponytail = rigid_object("Grandma_Ponytail", pbm, MAT_PONY)
    # Ponytail UVs: u around the tube, v from the tie (0) to the tip (1).
    puv = ponytail.data.uv_layers.new(name="UVMap").data
    pz = [p[2] for p in pts]
    for p in ponytail.data.polygons:
        us = []
        for li in p.loop_indices:
            vi = ponytail.data.loops[li].vertex_index
            us.append((vi % 10) / 10.0)
        if max(us) - min(us) > 0.5:
            us = [u + 1.0 if u < 0.5 else u for u in us]
        for li, u in zip(p.loop_indices, us):
            co = ponytail.data.vertices[ponytail.data.loops[li].vertex_index].co
            puv[li].uv = (u / 1.1, (pz[0] - co.z) / (pz[0] - pz[-1]))

# Glasses: round wire frames, a small arched bridge, arms back over the ears.
MAT_GLASSES = make_material("Grandma_Glasses", (0.42, 0.33, 0.16))
gbm = bmesh.new()
LENS_R, WIRE = 0.0175, 0.0013
EYE_Z = 1.536
for s in (1, -1):
    eye = head_surface(EYE_Z, 0.36 * s)
    yaw = 0.14 * s                                    # slight wrap with the face
    c = Vector((0.034 * s, min(eye.y, head_surface(EYE_Z + 0.02, 0.36 * s).y) - 0.013, EYE_Z))
    ring = []
    for k in range(10):
        a = 2 * math.pi * k / 10
        local = Vector((math.cos(a) * LENS_R, 0, math.sin(a) * LENS_R))
        ring.append(c + Matrix.Rotation(yaw, 3, "Z") @ local)
    tube(gbm, ring, WIRE, sides=3, closed=True)
    outer = c + Matrix.Rotation(yaw, 3, "Z") @ Vector((LENS_R * s, 0, 0.002))
    temple = [outer,
              Vector((0.084 * s, outer.y + 0.035, EYE_Z + 0.002)),
              Vector((0.087 * s, -0.005, EYE_Z - 0.004)),
              Vector((0.086 * s, 0.030, EYE_Z - 0.020)),
              Vector((0.082 * s, 0.040, EYE_Z - 0.040))]
    tube(gbm, temple, WIRE, sides=3)
bridge_y = head_surface(EYE_Z + 0.004, 0.0).y - 0.006
tube(gbm, [Vector((0.0165, bridge_y + 0.004, EYE_Z + 0.004)), Vector((0, bridge_y, EYE_Z + 0.009)),
           Vector((-0.0165, bridge_y + 0.004, EYE_Z + 0.004))], WIRE, sides=3)
glasses = rigid_object("Grandma_Glasses", gbm, MAT_GLASSES)

# Shoes: deliberately simple, PSX style. Per foot: the top half of an
# ellipsoid for the upper, sitting on a thick elliptical sole. The foot skin
# is pulled inside the shoe so only the leg comes out of the opening.
MAT_SHOES = make_material("Grandma_Shoes", (0.07, 0.06, 0.06))
BALL_Y = NODES["ballL"][0][1]
SOLE_T = 0.024                     # sole thickness
SEGS = 10                          # around the ellipse
sbm = bmesh.new()
sdl = sbm.verts.layers.deform.verify()
shoe_groups = {}
SHOE_SPECS = []

def add_vert(co, side):
    v = sbm.verts.new(co)
    w_toe = max(0.0, min(1.0, (BALL_Y + 0.02 - co[1]) / 0.05))   # toe bends with Toes
    for bone, w in ((side + "Foot", 1 - w_toe), (side + "Toes", w_toe)):
        if w > 0.001:
            v[sdl][shoe_groups.setdefault(bone, len(shoe_groups))] = w
    return v

for s in (1, -1):
    side = "Left" if s > 0 else "Right"
    fx = NODES["ankleL"][0][0] * s
    foot = [c for c in body_cos if abs(c.x - fx) < 0.09 and c.z < 0.09]
    y_back = max(c.y for c in foot)
    y_toe = min(c.y for c in foot)
    cx, cy = fx, (y_back + y_toe) / 2 - 0.004
    rx, ry, rz = 0.053, (y_back - y_toe) / 2 + 0.014, 0.066
    SHOE_SPECS.append((cx, cy, rx, ry, rz))
    ring = lambda r_x, r_y, z: [add_vert((cx + r_x * math.cos(2 * math.pi * k / SEGS),
                                          cy + r_y * math.sin(2 * math.pi * k / SEGS), z), side)
                                for k in range(SEGS)]
    # Upper: half ellipsoid (latitudes 0, 35, 65 degrees, then the top pole).
    lats = [ring(rx * math.cos(math.radians(a)), ry * math.cos(math.radians(a)),
                 SOLE_T + rz * math.sin(math.radians(a))) for a in (0, 35, 65)]
    pole = add_vert((cx, cy, SOLE_T + rz), side)
    for a, b in zip(lats, lats[1:]):
        for k in range(SEGS):
            sbm.faces.new((a[k], a[(k + 1) % SEGS], b[(k + 1) % SEGS], b[k]))
    for k in range(SEGS):
        sbm.faces.new((lats[-1][k], lats[-1][(k + 1) % SEGS], pole))
    sbm.faces.new(list(reversed(lats[0])))
    # Thick sole: an elliptical slab slightly larger than the upper's footprint.
    top = ring(rx + 0.007, ry + 0.008, SOLE_T)
    bot = ring(rx + 0.007, ry + 0.008, 0.0)
    for k in range(SEGS):
        sbm.faces.new((bot[k], bot[(k + 1) % SEGS], top[(k + 1) % SEGS], top[k]))
    sbm.faces.new(top)
    sbm.faces.new(list(reversed(bot)))

# Straight leg into the shoe: below the ankle the body becomes a vertical
# column (same centre and radius as the leg just above), so there is no
# forward ramp of the instep visible above the shoe. The foot itself is
# hidden inside the shoe anyway.
for s in (1, -1):
    fx = NODES["ankleL"][0][0] * s
    # Decimation leaves the shin as one span from the calf to the ankle ring,
    # so anchor the column on the ankle joint itself.
    lx, ly, lr_ = fx, NODES["ankleL"][0][1] + 0.004, 0.042
    for v in body.data.vertices:
        c = v.co
        if abs(c.x - fx) < 0.10 and c.z < 0.110:
            d = Vector((c.x - lx, c.y - ly))
            if d.length > lr_:
                d *= lr_ / d.length
            c.x, c.y = lx + d.x, ly + d.y

# Pull any foot skin that would poke out back inside the upper.
for v in body.data.vertices:
    c = v.co
    for cx, cy, rx, ry, rz in SHOE_SPECS:
        if abs(c.x - cx) > 0.11 or c.z > 0.075:
            continue
        c.z = max(c.z, SOLE_T + 0.002)
        d = Vector(((c.x - cx) / (rx * 0.90), (c.y - cy) / (ry * 0.90), (c.z - SOLE_T) / (rz * 0.90)))
        if d.length > 1.0:
            k = 1.0 / d.length
            c.x, c.y = cx + (c.x - cx) * k, cy + (c.y - cy) * k
            c.z = SOLE_T + (c.z - SOLE_T) * k
bmesh.ops.recalc_face_normals(sbm, faces=sbm.faces)
shoe_me = bpy.data.meshes.new("Grandma_Shoes")
sbm.to_mesh(shoe_me)
sbm.free()
shoes = bpy.data.objects.new("Grandma_Shoes", shoe_me)
scene.collection.objects.link(shoes)
for name, gi in sorted(shoe_groups.items(), key=lambda kv: kv[1]):
    shoes.vertex_groups.new(name=name)
shoe_me.materials.append(MAT_SHOES)
for p in shoe_me.polygons:
    p.use_smooth = True
shoe_me.uv_layers.new(name="UVMap")
activate(shoes, "EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.03, scale_to_bounds=True)
bpy.ops.object.mode_set(mode="OBJECT")
attach_to_rig(shoes)

tris = sum(len(p.vertices) - 2 for p in body.data.polygons)
stris = sum(len(p.vertices) - 2 for p in skirt.data.polygons) if skirt else 0
extra = {o.name: sum(len(p.vertices) - 2 for p in o.data.polygons) for o in (shirt, hair, ponytail, glasses, shoes) if o}
print("ACCESSORY_TRIS", extra)
print(f"GRANDMA body_tris={tris} skirt_tris={stris} verts={len(body.data.vertices)} "
      f"bones={len(BONES)} unweighted_fixed={unweighted}")

# ─── 7. Textures (procedurally painted, PS2 resolution) ───────────────────────
# Each texel is rasterised back to the 3D point it covers on the mesh, then
# coloured from that 3D position. Features are therefore placed by the same
# coordinates the face was sculpted with, and the skin is seamless across UV
# islands and across the head/body boundary.
import numpy as np

TEX_DIR = os.path.join(os.path.dirname(os.path.abspath(OUT_FBX)), "Textures")
os.makedirs(TEX_DIR, exist_ok=True)
RNG = np.random.default_rng(7)

def rasterize(mesh, mat_index, res, want_normals=False):
    """Return (positions[res,res,3], mask[res,res]) for faces of one material,
    plus smooth normals[res,res,3] if want_normals. Row 0 is v = 0."""
    pos = np.zeros((res, res, 3), np.float32)
    nrm = np.zeros((res, res, 3), np.float32)
    mask = np.zeros((res, res), bool)
    uvl = mesh.uv_layers.active.data
    mesh.calc_loop_triangles()
    for lt in mesh.loop_triangles:
        if mat_index is not None and lt.material_index != mat_index:
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
        mask[iy + y0, ix + x0] = True
        if want_normals:
            Nv = np.array([mesh.vertices[v].normal for v in lt.vertices], np.float64)
            n = w0[..., None] * Nv[0] + w1[..., None] * Nv[1] + w2[..., None] * Nv[2]
            n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-9
            nrm[iy + y0, ix + x0] = n[iy, ix]
    return (pos, mask, nrm) if want_normals else (pos, mask)

from mathutils.bvhtree import BVHTree
BODY_BVH = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())

def occlusion(pos, nrm, mask, rays=16, dist=0.16, step=2):
    """Ambient occlusion per texel: fraction of hemisphere rays that hit the
    body within `dist`. Computed every `step` texels, then softened."""
    res = mask.shape[0]
    rng = np.random.default_rng(3)
    u1, u2 = rng.random(rays), rng.random(rays)
    r_, phi = np.sqrt(u1), 2 * np.pi * u2                       # cosine-weighted
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
            p = Vector(pos[by + iy, bx + ix]) + n * 0.004
            t = n.orthogonal().normalized()
            b = n.cross(t)
            hits = sum(1 for d in local
                       if BODY_BVH.ray_cast(p, t * d[0] + b * d[1] + n * d[2], dist)[0] is not None)
            ao[by:by + step, bx:bx + step] = hits / rays
    for _ in range(8):                                           # soften (avoid blotchy patches)
        acc = ao.copy(); cnt = np.ones_like(ao)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            m = np.roll(mask, (dy, dx), (0, 1))
            acc += np.roll(ao, (dy, dx), (0, 1)) * m
            cnt += m
        ao = np.where(mask, acc / cnt, ao)
    return ao

def roast(img, nrm, ao):
    """Reddened, almost roasted skin, much stronger where light doesn't reach:
    occluded creases (armpits, under the chin, neck, between the legs, behind
    the knees) and downward-facing skin."""
    down = np.clip(-nrm[..., 2], 0, 1)
    shade = np.clip(ao * 2.4 + 0.55 * down ** 1.4, 0, 1)
    mix(img, (0.88, 0.48, 0.40), 0.48)                          # sunburnt overall
    mix(img, (0.68, 0.20, 0.13), 0.85 * shade)                  # roasted red in shadow
    mix(img, (0.28, 0.06, 0.04), 0.75 * shade ** 2.0)           # charred crimson in the deepest creases

def dilate(img, mask, steps=6):
    """Bleed colour outward from filled texels so mip/filtering has no black seams."""
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
    """Cheap smooth 3D noise: sum of random plane waves, roughly in [-1, 1]."""
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

SKIN = (0.80, 0.71, 0.67)          # pallid; the grade adds saturation back

def skin_base(p):
    """Shared elderly skin: pale, mottled, with blotchy redness and age spots."""
    img = np.empty(p.shape, np.float32)
    img[:] = SKIN
    mott = wave_noise(p, 55, seed=1)
    fine = wave_noise(p, 260, seed=2)
    img *= (1 + 0.045 * mott + 0.025 * fine)[..., None]
    mix(img, (0.78, 0.55, 0.52), 0.18 * np.clip(wave_noise(p, 25, seed=3), 0, 1))   # blotchy redness
    spots = wave_noise(p, 140, n=10, seed=4)
    mix(img, (0.60, 0.45, 0.36), 0.35 * np.clip((spots - 2.1) * 3.0, 0, 1))         # sparse, faint age spots
    return img

BAYER4 = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) + 0.5) / 16 - 0.5

def grade(img):
    """PS2 retro-horror grade: punchier saturation and contrast, crushed
    shadows, then 5-bit-per-channel quantisation with ordered dithering."""
    lum = img @ np.array([0.299, 0.587, 0.114], np.float32)
    img = lum[..., None] + (img - lum[..., None]) * 1.45          # saturation
    img = (img - 0.42) * 1.32 + 0.40                              # contrast
    img = np.clip(img, 0, 1) ** 1.08                              # slightly crushed shadows
    h, w = img.shape[:2]
    dither = np.tile(BAYER4, (h // 4 + 1, w // 4 + 1))[:h, :w][..., None]
    levels = 31
    # No baked dither: with big point-sampled texels it shows as a checkerboard.
    return np.clip(np.round(img * levels) / levels, 0, 1)

PIXELATE = 2          # paint at full res, save at 1/PIXELATE (chunkier PS2 texels)

def save_png(img, name, w=None):
    if PIXELATE > 1:                     # box-filter downsample keeps thin details as soft marks
        h_, w_ = img.shape[0] // PIXELATE, img.shape[1] // PIXELATE
        img = img[:h_ * PIXELATE, :w_ * PIXELATE].reshape(h_, PIXELATE, w_, PIXELATE, 3).mean((1, 3))
    img = grade(img)
    res = img.shape[0]
    im = bpy.data.images.new(name, img.shape[1], res, alpha=False)
    rgba = np.concatenate([np.clip(img, 0, 1), np.ones(img.shape[:2] + (1,), np.float32)], -1)
    im.pixels.foreach_set(rgba.astype(np.float32).ravel())
    im.filepath_raw = os.path.join(TEX_DIR, name + ".png")
    im.file_format = "PNG"
    im.save()
    print("TEXTURE", im.filepath_raw)
    return im

# --- Head ---------------------------------------------------------------------
HEAD_RES = 256
hp, hmask, hn = rasterize(body.data, 0, HEAD_RES, want_normals=True)
head_img = skin_base(hp)
roast(head_img, hn, occlusion(hp, hn, hmask))
X, Y, Z = hp[..., 0], hp[..., 1], hp[..., 2]
AY = np.array([head_axis_y(z) for z in Z.ravel()]).reshape(Z.shape)
TH = np.arctan2(X, -(Y - AY))            # 0 at the face, matches the sculpt
ATH = np.abs(TH)
R_FACE = 0.094                            # face radius: angle -> arc length (m)
U = TH * R_FACE                           # metres across the face (signed)
AU = np.abs(U)
front_mask = np.cos(TH) > 0
WRINKLE = (0.38, 0.12, 0.10)              # dark crimson creases on the roasted skin

# Shading baked in, PS2 style: deep, crater-like eye sockets. A wide soft
# shadow plus a tighter, darker ring hugging each eye makes them read as
# sunken holes even though the eyes themselves are painted flat.
mix(head_img, (0.30, 0.20, 0.22), 0.45 * gauss(ATH - 0.36, 0.20) * gauss(Z - 1.536, 0.018) * front_mask)
mix(head_img, (0.08, 0.03, 0.04), 0.80 * gauss(ATH - 0.36, 0.13) * gauss(Z - 1.535, 0.011) * front_mask)
# Rosy cheeks, ears and nose tip; pale, slightly shiny scalp.
mix(head_img, (0.85, 0.55, 0.52), 0.22 * gauss(ATH - 0.62, 0.16) * gauss(Z - 1.49, 0.018))
mix(head_img, (0.82, 0.55, 0.50), 0.30 * gauss(ATH - math.pi / 2 - 0.08, 0.14) * gauss(Z - 1.503, 0.03))
mix(head_img, (0.84, 0.58, 0.54), 0.30 * gauss(TH, 0.06) * gauss(Z - 1.482, 0.010))
mix(head_img, (0.88, 0.78, 0.72), 0.25 * np.clip((Z - 1.58) / 0.04, 0, 1))

# Eyes: narrow, hooded, drooping at the outer corner; dull sclera, grey-brown iris.
for s in (1, -1):
    eu = (TH * s - 0.36) * R_FACE          # + = toward the outer corner
    ez = Z - 1.535 + 0.0035 * np.clip(eu / 0.013, 0, 1) ** 2  # outer corner droops
    side = (TH * s > 0) & front_mask
    shape = (np.abs(eu) / 0.0150) ** 1.6 + (ez / 0.0055) ** 2
    eye = (shape < 1) & side
    mix(head_img, (0.30, 0.20, 0.20), 0.55 * gauss(shape - 1.0, 0.35) * side)            # lid rim
    mix(head_img, (0.62, 0.48, 0.48), 0.45 * gauss(eu, 0.014) * gauss(ez + 0.0085, 0.0035) * side)  # eye bag
    mix(head_img, (0.66, 0.50, 0.46), 0.35 * gauss(eu, 0.014) * gauss(ez - 0.0085, 0.003) * side)   # hooded lid fold
    # Dim, shadowed sclera (darker toward the lids) so the eyes sit in the dark.
    head_img[eye] = (0.58, 0.53, 0.46)
    mix(head_img, (0.20, 0.14, 0.14), 0.55 * np.clip(shape, 0, 1) * eye)
    iris = eye & ((eu + 0.001) ** 2 + (ez - 0.0006) ** 2 < 0.0047 ** 2)
    head_img[iris] = (0.22, 0.20, 0.17)
    pupil = eye & ((eu + 0.001) ** 2 + (ez - 0.0006) ** 2 < 0.0018 ** 2)
    head_img[pupil] = (0.05, 0.04, 0.04)
    upper = side & (shape < 1.35) & (ez > 0) & ~eye
    head_img[upper] = head_img[upper] * 0.55                                              # heavy upper lash line
    # Crow's feet: a few short lines fanning from the outer corner.
    for ang in (-0.75, -0.42, -0.12, 0.18, 0.48):
        du, dz = eu - 0.016, ez
        along = du * math.cos(ang) + dz * math.sin(ang)
        across = -du * math.sin(ang) + dz * math.cos(ang)
        mix(head_img, WRINKLE, 0.55 * gauss(across, 0.0011) * (along > 0) * gauss(along, 0.013) * side)
    # Eyebrows: thin, sparse, grey; arched, longer toward the outside.
    bz = Z - (1.553 - 0.004 * (eu / 0.016) ** 2)
    brow = gauss(bz, 0.0018) * (eu > -0.014) * (eu < 0.020) * side
    sparse = np.clip(wave_noise(hp, 900, seed=5 + (s > 0)) * 0.8 + 0.6, 0, 1)
    mix(head_img, (0.55, 0.52, 0.50), 0.75 * brow * sparse)

# Nose: nostrils (dark, on the underside), fold lines from nose to mouth corners.
mix(head_img, (0.22, 0.10, 0.09), 0.9 * gauss(ATH - 0.10, 0.035) * gauss(Z - 1.470, 0.0028) * front_mask)
for s in (1, -1):
    t = np.clip((1.480 - Z) / 0.032, 0, 1)
    line_u = (0.017 + 0.009 * t) * s
    mix(head_img, (0.52, 0.38, 0.36), 0.40 * gauss(U - line_u, 0.0012) * (Z < 1.481) * (Z > 1.446) * front_mask)

# Mouth: thin pale lips with a downturned line.
lip_w = 0.0275                                 # wider mouth
mouth_line = 1.4505 - 0.0040 * (AU / lip_w) ** 2
lips = (AU < lip_w) & front_mask
upper_lip = lips & (Z > mouth_line) & (Z < mouth_line + 0.0035 * (1 - (AU / lip_w) ** 2))
lower_lip = lips & (Z < mouth_line) & (Z > mouth_line - 0.0050 * (1 - (AU / lip_w) ** 2))
mix(head_img, (0.88, 0.42, 0.58), 0.92 * (upper_lip | lower_lip))         # pink lipstick
mix(head_img, (0.70, 0.30, 0.45), 0.50 * lower_lip * (Z < mouth_line - 0.0025))  # darker lower edge
mix(head_img, (0.30, 0.08, 0.14), 0.95 * gauss(Z - mouth_line, 0.0007) * (AU < lip_w + 0.002) * front_mask)
if MAKE_HAIR:
    # Grey tint on the scalp under the hair shell, so any gap reads as hair.
    for_hair = np.array([Z[i, j] > hairline(abs(TH[i, j])) - 0.004 for i, j in np.ndindex(Z.shape)]).reshape(Z.shape)
    mix(head_img, (0.55, 0.55, 0.57), 0.85 * for_hair)
# Fine vertical lip wrinkles above the mouth.
mix(head_img, (0.60, 0.45, 0.42), 0.25 * (np.sin(U * 900) > 0.6) * (Z > mouth_line + 0.003)
    * (Z < mouth_line + 0.009) * (AU < 0.024) * front_mask)
# Wrinkles. Lines are a little wider than real creases so they survive the
# downsample to PS2 resolution.
def crease(dist, width=0.0012):
    return gauss(dist, width)
# Forehead: five deep, wavy horizontal lines, fading out toward the temples.
for i, zl in enumerate((1.568, 1.577, 1.586, 1.595, 1.604)):
    wz = Z - zl - 0.0018 * np.sin(U * 110 + i * 1.7) - 0.004 * (AU / 0.05) ** 2
    mix(head_img, WRINKLE, 0.55 * crease(wz) * gauss(U, 0.040) * front_mask)
# Frown lines: two vertical creases between the brows.
for s in (1, -1):
    mix(head_img, WRINKLE, 0.55 * crease(U - 0.006 * s, 0.0010) * (Z > 1.540) * (Z < 1.562) * front_mask)
# Under-eye creases: two curved lines below each eye bag.
for s in (1, -1):
    eu = (TH * s - 0.36) * R_FACE
    for off in (0.013, 0.019):
        cz = Z - (1.535 - off + 0.004 * (eu / 0.016) ** 2)
        mix(head_img, WRINKLE, 0.45 * crease(cz, 0.0010) * (np.abs(eu) < 0.016) * (TH * s > 0) * front_mask)
# Cheek creases: long diagonal folds down the cheeks, plus fine crosshatching.
for s in (1, -1):
    t = np.clip((1.505 - Z) / 0.055, 0, 1)
    for off in (0.034, 0.044):
        line_u = (off + 0.010 * t) * s
        mix(head_img, WRINKLE, 0.28 * crease(U - line_u, 0.0012) * (Z < 1.505) * (Z > 1.445) * front_mask)
fine = (np.abs(np.sin(U * 700 + Z * 500)) < 0.12) | (np.abs(np.sin(U * 650 - Z * 520)) < 0.12)
mix(head_img, WRINKLE, 0.14 * fine * gauss(AU - 0.045, 0.020) * gauss(Z - 1.48, 0.03) * front_mask)
# Marionette lines: from the mouth corners down toward the chin.
for s in (1, -1):
    t = np.clip((1.450 - Z) / 0.030, 0, 1)
    line_u = (lip_w + 0.002 + 0.004 * t) * s
    mix(head_img, WRINKLE, 0.55 * crease(U - line_u, 0.0012) * (Z < 1.450) * (Z > 1.420) * front_mask)
# More vertical lip lines (upper and lower), and a deeper nose-to-mouth fold.
lipl = np.abs(np.sin(U * 600)) < 0.15
mix(head_img, WRINKLE, 0.35 * lipl * (AU < lip_w) * (np.abs(Z - mouth_line) < 0.010)
    * (np.abs(Z - mouth_line) > 0.0012) * front_mask)
for s in (1, -1):
    t = np.clip((1.480 - Z) / 0.032, 0, 1)
    mix(head_img, WRINKLE, 0.45 * crease(U - (0.018 + 0.010 * t) * s, 0.0014) * (Z < 1.481) * (Z > 1.444) * front_mask)
# Neck creases just under the jaw.
for zl in (1.400, 1.412):
    mix(head_img, WRINKLE, 0.40 * crease(Z - zl - 0.002 * np.sin(U * 90), 0.0012) * (np.cos(TH) > -0.2))

head_img = dilate(head_img, hmask)
IMG_HEAD = save_png(head_img, "Grandma_Head")

# --- Body ---------------------------------------------------------------------
BODY_RES = 256
bp, bmask, bn = rasterize(body.data, 1, BODY_RES, want_normals=True)
body_img = skin_base(bp)
roast(body_img, bn, occlusion(bp, bn, bmask))
X, Y, Z = bp[..., 0], bp[..., 1], bp[..., 2]
# Knees and elbows: redder, slightly wrinkled.
for s in (1, -1):
    kn = np.sqrt((X - 0.105 * s) ** 2 + (Y + 0.05) ** 2 + (Z - 0.445) ** 2)
    mix(body_img, (0.78, 0.52, 0.50), 0.35 * gauss(kn, 0.04))
    el = np.sqrt((X - 0.37 * s) ** 2 + (Y - 0.075) ** 2 + (Z - 1.065) ** 2)
    mix(body_img, (0.76, 0.52, 0.50), 0.35 * gauss(el, 0.035))
    # Hands: knuckle redness, faint veins, pale nails at the tips.
    w0 = np.array(lr(L("wrist"), s)); tip = np.array(lr((0.665, -0.020, 0.765), s))
    ax_ = (tip - w0) / np.linalg.norm(tip - w0)
    t = (bp - w0) @ ax_
    radial = np.linalg.norm((bp - w0) - t[..., None] * ax_, axis=-1)
    on_hand = (t > 0) & (radial < 0.06)
    mix(body_img, (0.80, 0.55, 0.52), 0.35 * gauss(t - 0.075, 0.015) * on_hand)
    mix(body_img, (0.55, 0.55, 0.68), 0.30 * (np.abs(np.sin(t * 160 + X * 300)) < 0.08) * (t < 0.07) * on_hand)
    mix(body_img, (0.90, 0.78, 0.74), 0.70 * (t > 0.150) * on_hand)
    # Toenails area / feet: slightly redder heels and toes.
    ft = np.sqrt((X - 0.105 * s) ** 2 + (Y + 0.17) ** 2 + (Z - 0.03) ** 2)
    mix(body_img, (0.82, 0.58, 0.54), 0.35 * gauss(ft, 0.035))
# Stockings: sheer, slightly darker tan nylon below the knee-length skirt,
# with a darker reinforced toe; plain black shoes painted on the feet.
legs = (Z < 0.62) & (np.abs(X) < 0.2)
mix(body_img, (0.70, 0.45, 0.40), 0.18 * legs)                     # very sheer: the reddened skin shows through
mix(body_img, (0.06, 0.05, 0.05), 1.0 * legs * (Z < 0.075))
mix(body_img, (0.30, 0.26, 0.24), 0.8 * legs * (np.abs(Z - 0.075) < 0.004))   # shoe top edge
# Neck wrinkles (matching the head texture's skin, just below the jaw).
mix(body_img, (0.58, 0.45, 0.42), 0.25 * (np.sin(Z * 700) > 0.85) * (Z > 1.32) * (Z < 1.395) * (Y < 0.02))
body_img = dilate(body_img, bmask)
IMG_BODY = save_png(body_img, "Grandma_Body")

# --- Skirt: dull plum wool with a faint faded floral print ---------------------
IMG_SKIRT = None
if skirt:
    SK_RES = 128
    sp, smask = rasterize(skirt.data, None, SK_RES)
    sk = np.empty(sp.shape, np.float32); sk[:] = (0.32, 0.22, 0.26)
    sk *= (1 + 0.06 * wave_noise(sp, 300, seed=11))[..., None]
    flowers = np.clip(wave_noise(sp, 90, n=10, seed=12) - 1.3, 0, 1)
    mix(sk, (0.52, 0.42, 0.40), 0.6 * flowers)
    sk = dilate(sk, smask)
    IMG_SKIRT = save_png(sk, "Grandma_Skirt")

# --- Shirt: dusty-rose blouse, cream lace collar, pearl buttons, small print ----
SH_RES = 256
shp, shmask = rasterize(shirt.data, None, SH_RES)
X, Y, Z = shp[..., 0], shp[..., 1], shp[..., 2]
sh = np.empty(shp.shape, np.float32); sh[:] = (0.80, 0.50, 0.58)
sh *= (1 + 0.05 * wave_noise(shp, 400, seed=21) + 0.04 * wave_noise(shp, 60, seed=22))[..., None]
# Small calico print: cream five-petal flowers with yellow centres on a 3D
# lattice (so it is seamless across UV islands), plus offset green leaf dots.
def lattice(p, cell, offset=0.0):
    c = p / cell + offset
    return (c - np.floor(c) - 0.5) * cell          # local offset within each cell (m)
loc = lattice(shp, 0.026)
r = np.linalg.norm(loc, axis=-1)
ang = np.arctan2(loc[..., 2], loc[..., 0] + loc[..., 1])
petal = r < 0.0065 * (0.75 + 0.25 * np.cos(5 * ang))
mix(sh, (0.96, 0.90, 0.82), 0.95 * petal)
mix(sh, (0.92, 0.75, 0.30), 0.95 * (r < 0.0018))
leaf = np.linalg.norm(lattice(shp, 0.026, 0.5), axis=-1) < 0.0035
mix(sh, (0.40, 0.52, 0.36), 0.80 * leaf)
# Folds baked in: under the bust, armpits, and the tuck at the waist.
mix(sh, (0.35, 0.18, 0.24), 0.45 * gauss(Z - 1.085, 0.020) * (Y < -0.04))
for s in (1, -1):
    mix(sh, (0.35, 0.18, 0.24), 0.40 * gauss(np.sqrt((X - 0.16 * s) ** 2 + (Y - 0.04) ** 2 + (Z - 1.18) ** 2), 0.05))
mix(sh, (0.35, 0.18, 0.24), 0.35 * np.clip((0.97 - Z) / 0.05, 0, 1))
# Collar: a cream lace band along the neckline.
nl = np.array([neckline_z(y) for y in Y.ravel()]).reshape(Y.shape)
collar = (Z > nl - 0.018)
mix(sh, (0.93, 0.89, 0.82), 0.95 * collar)
mix(sh, (0.70, 0.62, 0.58), 0.6 * collar * (np.sin(X * 900 + Y * 900) > 0.7))   # lace holes
# Button placket and pearl buttons down the front.
front_c = (Y < 0) & (np.abs(X) < 0.012)
mix(sh, (0.62, 0.36, 0.44), 0.6 * front_c * (np.abs(np.abs(X) - 0.010) < 0.0015))
for bz in np.arange(0.96, 1.27, 0.05):
    d = np.sqrt(X ** 2 + (Z - bz) ** 2)
    mix(sh, (0.96, 0.95, 0.90), 1.0 * (d < 0.0055) * (Y < 0))
    mix(sh, (0.40, 0.35, 0.35), 0.8 * (np.abs(d - 0.0055) < 0.0012) * (Y < 0))
# Sleeve cuffs.
for e in ELBOWS:
    d = np.linalg.norm(shp - np.array(e), axis=-1)
    mix(sh, (0.93, 0.89, 0.82), 0.9 * (d > 0.075) * (d < 0.11) * (np.abs(X) > 0.30))
sh = dilate(sh, shmask)
IMG_SHIRT = save_png(sh, "Grandma_Shirt")

if MAKE_HAIR:
    # --- Hair: grey strands flowing back to the ponytail ----------------------------
    HR_RES = 256
    hrp, hrmask = rasterize(hair.data, None, HR_RES)
    hc = Vector((0, -0.02, 1.52))
    A = (anchor - hc).normalized()
    A_np = np.array(A, np.float32)
    up2 = Vector((0, 0, 1)) - A * A.z; up2.normalize()
    side2 = A.cross(up2)
    d = hrp - np.array(hc, np.float32)
    d /= np.linalg.norm(d, axis=-1, keepdims=True) + 1e-6
    q = d - (d @ A_np)[..., None] * A_np
    strand = np.arctan2(q @ np.array(side2, np.float32), q @ np.array(up2, np.float32))
    along = d @ A_np
    hr = np.empty(hrp.shape, np.float32); hr[:] = (0.68, 0.68, 0.70)
    streak = np.sin(strand * 55 + 1.5 * wave_noise(hrp, 30, seed=31)) * 0.5 + 0.5   # low freq: no moire at 256px
    hr *= (0.78 + 0.30 * streak + 0.06 * wave_noise(hrp, 300, seed=32))[..., None]
    mix(hr, (0.86, 0.84, 0.78), 0.35 * np.clip(wave_noise(hrp, 25, seed=33), 0, 1))  # yellowed white streaks
    mix(hr, (0.30, 0.30, 0.33), 0.40 * np.clip((along - 0.80) / 0.2, 0, 1))         # shadow at the gather
    hr = dilate(hr, hrmask)
    IMG_HAIR = save_png(hr, "Grandma_Hair")

    # --- Ponytail: strands down its length, dark red hair tie at the top -----------
    pv = np.linspace(0, 1, 128)[:, None] * np.ones((1, 64))
    pu = np.ones((128, 1)) * np.linspace(0, 1, 64)[None, :]
    pt = np.empty((128, 64, 3), np.float32); pt[:] = (0.68, 0.68, 0.70)
    pt *= (0.80 + 0.30 * (np.sin(pu * 2 * math.pi * 9 + np.sin(pv * 9) * 1.5) * 0.5 + 0.5))[..., None]
    mix(pt, (0.86, 0.84, 0.78), 0.3 * (np.sin(pu * 2 * math.pi * 4 + 1) > 0.7))
    mix(pt, (0.42, 0.42, 0.45), 0.5 * np.clip((pv - 0.8) / 0.2, 0, 1))              # thinning, darker tip
    mix(pt, (0.55, 0.08, 0.12), 1.0 * (pv < 0.10))                                    # hair tie
    pt = pt[::-1]                                                                     # row 0 = v 0
    IMG_PONY = save_png(pt, "Grandma_Ponytail")

# --- Shoes: black leather Mary Janes ---------------------------------------------
SHO_RES = 128
so, somask = rasterize(shoes.data, None, SHO_RES)
X, Y, Z = so[..., 0], so[..., 1], so[..., 2]
AX = np.abs(X)
shoe = np.empty(so.shape, np.float32); shoe[:] = (0.07, 0.06, 0.07)
shoe *= (1 + 0.15 * wave_noise(so, 250, seed=41))[..., None]                  # creased leather
toe_front = np.clip((BALL_Y + 0.01 - Y) / 0.05, 0, 1)
mix(shoe, (0.42, 0.40, 0.44), 0.55 * toe_front * gauss(Z - SOLE_T - 0.040, 0.014))      # polished toe-cap sheen
mix(shoe, (0.30, 0.28, 0.32), 0.35 * gauss(Z - SOLE_T - 0.055, 0.008) * (Y > BALL_Y))   # upper highlight
mix(shoe, (0.36, 0.24, 0.15), 1.0 * (Z < SOLE_T + 0.001))                       # thick tan sole
mix(shoe, (0.26, 0.16, 0.10), 1.0 * (Z < SOLE_T + 0.001) * (Y > BALL_Y + 0.090))  # darker heel
mix(shoe, (0.20, 0.12, 0.08), 0.8 * (np.abs(Z - SOLE_T * 0.5) < 0.002))       # sole groove
mix(shoe, (0.55, 0.50, 0.46), 0.7 * (np.abs(Z - SOLE_T - 0.004) < 0.0015) * (np.sin(Y * 900) > 0))  # welt stitching
STRAP_Y = BALL_Y + 0.060
for s in (1, -1):
    fx = NODES["ankleL"][0][0] * s
    # Instep strap: glossy band with light edges so it reads against the shoe.
    strap = (np.abs(Y - STRAP_Y) < 0.010) & (Z > SOLE_T + 0.030)
    mix(shoe, (0.14, 0.13, 0.16), 1.0 * strap * (np.abs(X - fx) < 0.08))
    mix(shoe, (0.45, 0.42, 0.46), 0.8 * (np.abs(np.abs(Y - STRAP_Y) - 0.009) < 0.0015) * (Z > SOLE_T + 0.030)
        * (np.abs(X - fx) < 0.08))
    # Small square gold buckle on the outer side of the strap.
    outer = s * (X - fx)
    buckle = (np.abs(Y - STRAP_Y) < 0.012) & (outer > 0.024) & (Z > SOLE_T + 0.020) & (Z < SOLE_T + 0.052)
    mix(shoe, (0.85, 0.68, 0.30), 1.0 * buckle)
    mix(shoe, (0.12, 0.09, 0.05), 1.0 * (buckle & (np.abs(Y - STRAP_Y) < 0.005) & (Z > SOLE_T + 0.028) & (Z < SOLE_T + 0.044)))
shoe = dilate(shoe, somask)
IMG_SHOES = save_png(shoe, "Grandma_Shoes")

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

attach_texture(MAT_HEAD, IMG_HEAD)
attach_texture(MAT_BODY, IMG_BODY)
if skirt:
    attach_texture(MAT_SKIRT, IMG_SKIRT)
attach_texture(MAT_SHIRT, IMG_SHIRT)
if MAKE_HAIR:
    attach_texture(MAT_HAIR, IMG_HAIR)
    attach_texture(MAT_PONY, IMG_PONY)
attach_texture(MAT_SHOES, IMG_SHOES)

# ─── Export ───────────────────────────────────────────────────────────────────
os.makedirs(os.path.dirname(os.path.abspath(OUT_FBX)), exist_ok=True)
for o in scene.objects:
    o.select_set(False)
bpy.ops.export_scene.fbx(
    filepath=OUT_FBX,
    object_types={"ARMATURE", "MESH"},
    add_leaf_bones=False,
    apply_scale_options="FBX_SCALE_UNITS",
    axis_forward="-Z", axis_up="Y",
    mesh_smooth_type="FACE",
    bake_anim=False,
)
print("EXPORTED", OUT_FBX)

# UV layout guides for texture painting, saved next to the FBX.
def export_uv_layout(obj, mat_index, path):
    activate(obj, "EDIT")
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.object.mode_set(mode="OBJECT")
    for p in obj.data.polygons:
        p.select = (mat_index is None or p.material_index == mat_index)
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        bpy.ops.uv.export_layout(filepath=path, export_all=False, modified=False,
                                 mode="SVG", size=(1024, 1024), opacity=0.0)
        print("UVLAYOUT", path)
    except Exception as e:
        print("UVLAYOUT_FAILED", path, e)
    bpy.ops.object.mode_set(mode="OBJECT")

out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uv")  # outside Assets/
os.makedirs(out_dir, exist_ok=True)
export_uv_layout(body, 0, os.path.join(out_dir, "Grandma_Head_UV.svg"))
export_uv_layout(body, 1, os.path.join(out_dir, "Grandma_Body_UV.svg"))
if skirt:
    export_uv_layout(skirt, None, os.path.join(out_dir, "Grandma_Skirt_UV.svg"))

# ─── Previews ─────────────────────────────────────────────────────────────────
if PREVIEW_DIR:
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.render.resolution_x, scene.render.resolution_y = 480, 640
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    cam.data.type = "ORTHO"
    scene.collection.objects.link(cam)
    scene.camera = cam

    def shoot(name, loc, target, scale=1.9):
        cam.location = Vector(loc)
        cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()
        cam.data.ortho_scale = scale
        scene.render.filepath = os.path.join(PREVIEW_DIR, name + ".png")
        bpy.ops.render.render(write_still=True)

    def views(prefix):
        shoot(prefix + "front", (0, -5, 0.82), (0, 0, 0.82))
        shoot(prefix + "side", (5, 0, 0.82), (0, 0, 0.82))
        shoot(prefix + "three_quarter", (3.5, -3.5, 1.1), (0, 0, 0.82))
        shoot(prefix + "back", (0, 5, 0.82), (0, 0, 0.82))

    # Plain shaded views, with and without the skirt.
    scene.display.shading.color_type = "MATERIAL"
    views("")
    shoot("face", (0, -5, 1.50), (0, 0, 1.50), scale=0.38)
    shoot("face_3q", (3.2, -3.8, 1.55), (0, -0.03, 1.50), scale=0.38)
    shoot("face_side", (5, 0, 1.50), (0, 0, 1.50), scale=0.38)
    if skirt:
        skirt.hide_render = True
        views("noskirt_")
        skirt.hide_render = False

    # Textured views (the painted PNGs are the active image nodes).
    scene.display.shading.color_type = "TEXTURE"
    shoot("textured_front", (0, -5, 0.82), (0, 0, 0.82))
    shoot("textured_3q", (3.5, -3.5, 1.1), (0, 0, 0.82))
    shoot("textured_back", (0, 5, 0.82), (0, 0, 0.82))
    shoot("textured_side", (5, 0, 0.82), (0, 0, 0.82))
    shoot("textured_back_3q", (-3.5, 3.5, 1.1), (0, 0, 0.82))
    shoot("textured_sleeve", (2.2, -2.6, 1.3), (0.40, 0.03, 1.02), scale=0.5)
    shoot("textured_face", (0, -5, 1.50), (0, 0, 1.50), scale=0.30)
    shoot("textured_face_3q", (3.2, -3.8, 1.55), (0, -0.03, 1.50), scale=0.30)
    shoot("textured_hand", (2.5, -4.0, 0.95), (0.58, 0, 0.84), scale=0.35)
    for o in (shirt, skirt):
        o.hide_render = True
    shoot("textured_skin_front", (0, -5, 0.82), (0, 0, 0.82))
    shoot("textured_skin_3q", (3.5, -3.5, 1.1), (0, 0, 0.82))
    shoot("textured_skin_back", (0, 5, 0.82), (0, 0, 0.82))
    shoot("textured_skin_armpit", (2.0, -1.0, 0.75), (0.15, 0.03, 1.15), scale=0.6)
    shoot("textured_skin_under_chin", (0.6, -2.5, 0.9), (0, -0.03, 1.40), scale=0.45)
    for o in (shirt, skirt):
        o.hide_render = False
    shoot("textured_shoes_3q", (2.6, -3.4, 1.4), (0.0, -0.05, 0.04), scale=0.45)
    shoot("textured_shoes_side", (5, 0, 0.06), (0, -0.05, 0.06), scale=0.40)
    shoot("textured_shoes_front", (0, -5, 0.08), (0, 0, 0.08), scale=0.40)

    # UV check: a generated UV grid on every material.
    grid = bpy.data.images.new("UVGrid", 1024, 1024)
    grid.generated_type = "UV_GRID"
    for mat in bpy.data.materials:
        nt = mat.node_tree
        if not nt:
            continue
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = grid
        nt.nodes.active = tex
    scene.display.shading.color_type = "TEXTURE"
    shoot("uvcheck_3q", (3.5, -3.5, 1.1), (0, 0, 0.82))
    shoot("uvcheck_face", (0, -5, 1.50), (0, 0, 1.50), scale=0.38)
    scene.display.shading.color_type = "MATERIAL"

    # Rig check: seated pose.
    pb = rig.pose.bones
    for side in ("Left", "Right"):
        for bone, ang in (("UpperLeg", -90), ("LowerLeg", 90), ("LowerArm", -40)):
            pb[side + bone].rotation_mode = "XYZ"
            pb[side + bone].rotation_euler = (math.radians(ang), 0, 0)
    view_layer.update()
    shoot("seated_side", (5, 0, 0.75), (0, 0, 0.75))
    shoot("seated_3q", (3.5, -3.5, 1.0), (0, 0, 0.75))
    print("PREVIEWS", PREVIEW_DIR)
