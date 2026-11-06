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

def g(x, s):
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
        d += height * g(th, width)
    d += 0.007 * g(ath - 0.17, 0.06) * g(z - 1.481, 0.008)     # nostril wings
    d -= 0.013 * g(ath - 0.36, 0.16) * g(z - 1.533, 0.014)     # eye sockets
    d += 0.005 * g(th, 0.55) * g(z - 1.557, 0.008)             # brow ridge
    d += 0.007 * g(ath - 0.68, 0.20) * g(z - 1.503, 0.016)     # cheekbones
    d -= 0.008 * g(ath - 0.55, 0.20) * g(z - 1.462, 0.016)     # sunken cheeks
    d += 0.004 * g(th, 0.30) * g(z - 1.453, 0.009)             # lips
    d -= 0.004 * g(th, 0.26) * g(z - 1.450, 0.0025)            # mouth line
    d += 0.008 * g(th, 0.26) * g(z - 1.420, 0.010)             # chin
    d += 0.020 * g(ath - math.pi / 2 - 0.08, 0.11) * g(z - 1.503, 0.024)  # ears
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
    SEG, RINGS = 20, [1.000, 0.930, 0.840, 0.740, 0.620, 0.500, 0.420]
    body_verts = [v.co.copy() for v in body.data.vertices]
    def extent(z, band=0.03):
        """Max half-width (x) and half-depth (y) of the body near height z."""
        xs = [abs(c.x) for c in body_verts if abs(c.z - z) < band and abs(c.x) < 0.30]
        ys = [abs(c.y - 0.01) for c in body_verts if abs(c.z - z) < band and abs(c.x) < 0.30]
        return (max(xs) if xs else 0.2), (max(ys) if ys else 0.15)
    ring_r = []
    rx_prev = ry_prev = 0
    for i, z in enumerate(RINGS):
        rx, ry = extent(z)
        flare = 0.012 + 0.03 * i / (len(RINGS) - 1)
        rx, ry = max(rx + flare, rx_prev), max(ry + flare, ry_prev)   # never narrows going down
        ring_r.append((rx, ry))
        rx_prev, ry_prev = rx, ry
    sbm = bmesh.new()
    rings = []
    for z, (rx, ry) in zip(RINGS, ring_r):
        rings.append([sbm.verts.new((rx * math.cos(2 * math.pi * k / SEG),
                                     0.01 + ry * math.sin(2 * math.pi * k / SEG), z)) for k in range(SEG)])
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

tris = sum(len(p.vertices) - 2 for p in body.data.polygons)
stris = sum(len(p.vertices) - 2 for p in skirt.data.polygons) if skirt else 0
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

def rasterize(mesh, mat_index, res):
    """Return (positions[res,res,3], mask[res,res]) for faces of one material.
    Row 0 is v = 0 (Blender image pixel order)."""
    pos = np.zeros((res, res, 3), np.float32)
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
    return pos, mask

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

SKIN = (0.80, 0.67, 0.59)

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

def save_png(img, name):
    res = img.shape[0]
    im = bpy.data.images.new(name, res, res, alpha=False)
    rgba = np.concatenate([np.clip(img, 0, 1), np.ones((res, res, 1), np.float32)], -1)
    im.pixels.foreach_set(rgba.ravel())
    im.filepath_raw = os.path.join(TEX_DIR, name + ".png")
    im.file_format = "PNG"
    im.save()
    print("TEXTURE", im.filepath_raw)
    return im

# --- Head ---------------------------------------------------------------------
HEAD_RES = 256
hp, hmask = rasterize(body.data, 0, HEAD_RES)
head_img = skin_base(hp)
X, Y, Z = hp[..., 0], hp[..., 1], hp[..., 2]
AY = np.array([head_axis_y(z) for z in Z.ravel()]).reshape(Z.shape)
TH = np.arctan2(X, -(Y - AY))            # 0 at the face, matches the sculpt
ATH = np.abs(TH)
R_FACE = 0.094                            # face radius: angle -> arc length (m)
U = TH * R_FACE                           # metres across the face (signed)
AU = np.abs(U)
front_mask = np.cos(TH) > 0

# Shading baked in, PS2 style: deep eye sockets.
mix(head_img, (0.45, 0.33, 0.33), 0.35 * gauss(ATH - 0.36, 0.17) * gauss(Z - 1.533, 0.016) * front_mask)
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
    head_img[eye] = (0.76, 0.72, 0.62)
    iris = eye & ((eu + 0.001) ** 2 + (ez - 0.0006) ** 2 < 0.0047 ** 2)
    head_img[iris] = (0.30, 0.27, 0.23)
    pupil = eye & ((eu + 0.001) ** 2 + (ez - 0.0006) ** 2 < 0.0018 ** 2)
    head_img[pupil] = (0.05, 0.04, 0.04)
    upper = side & (shape < 1.35) & (ez > 0) & ~eye
    head_img[upper] = head_img[upper] * 0.55                                              # heavy upper lash line
    # Crow's feet: a few short lines fanning from the outer corner.
    for ang in (-0.5, -0.15, 0.2):
        du, dz = eu - 0.016, ez
        along = du * math.cos(ang) + dz * math.sin(ang)
        across = -du * math.sin(ang) + dz * math.cos(ang)
        mix(head_img, (0.55, 0.42, 0.40), 0.35 * gauss(across, 0.0006) * (along > 0) * gauss(along, 0.008) * side)
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
mouth_line = 1.4505 - 0.0035 * (AU / 0.022) ** 2
lip_w = 0.022
lips = (AU < lip_w) & front_mask
upper_lip = lips & (Z > mouth_line) & (Z < mouth_line + 0.0035 * (1 - (AU / lip_w) ** 2))
lower_lip = lips & (Z < mouth_line) & (Z > mouth_line - 0.0050 * (1 - (AU / lip_w) ** 2))
mix(head_img, (0.62, 0.42, 0.42), 0.85 * (upper_lip | lower_lip))
mix(head_img, (0.25, 0.10, 0.10), 0.95 * gauss(Z - mouth_line, 0.0007) * (AU < lip_w + 0.002) * front_mask)
# Fine vertical lip wrinkles above the mouth.
mix(head_img, (0.60, 0.45, 0.42), 0.25 * (np.sin(U * 900) > 0.6) * (Z > mouth_line + 0.003)
    * (Z < mouth_line + 0.009) * (AU < 0.018) * front_mask)
# Forehead wrinkles: three faint, slightly wavy lines.
for zl in (1.574, 1.584, 1.594):
    wz = Z - zl - 0.0015 * np.sin(U * 120)
    mix(head_img, (0.58, 0.45, 0.42), 0.35 * gauss(wz, 0.0008) * (AU < 0.045) * front_mask)

head_img = dilate(head_img, hmask)
IMG_HEAD = save_png(head_img, "Grandma_Head")

# --- Body ---------------------------------------------------------------------
BODY_RES = 256
bp, bmask = rasterize(body.data, 1, BODY_RES)
body_img = skin_base(bp)
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

def attach_texture(mat, img):
    nt = mat.node_tree
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    bsdf = nt.nodes.get("Principled BSDF")
    if bsdf:
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    nt.nodes.active = tex
    mat.diffuse_color = (1, 1, 1, 1)

attach_texture(MAT_HEAD, IMG_HEAD)
attach_texture(MAT_BODY, IMG_BODY)
if skirt:
    attach_texture(MAT_SKIRT, IMG_SKIRT)

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
    shoot("textured_face", (0, -5, 1.50), (0, 0, 1.50), scale=0.30)
    shoot("textured_face_3q", (3.2, -3.8, 1.55), (0, -0.03, 1.50), scale=0.30)
    shoot("textured_hand", (2.5, -4.0, 0.95), (0.58, 0, 0.84), scale=0.35)

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
