# Generates a low-poly, PSX-style rigged grandma and exports it as FBX.
#
# Usage (headless):
#   blender --background --python make_grandma.py -- <out.fbx> [preview_dir]
#
# Character faces -Y (Blender front view), stands in an A-pose, and is
# rigidly skinned (each part follows one bone), like PS1-era characters.
# Bone names follow Unity Humanoid conventions so the Avatar auto-maps.

import bpy, bmesh, math, sys, os
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT_FBX = argv[0] if argv else os.path.join(os.getcwd(), "Grandma.fbx")
PREVIEW_DIR = argv[1] if len(argv) > 1 else None

bpy.ops.wm.read_factory_settings(use_empty=True)

# ─── Materials ────────────────────────────────────────────────────────────────
MAT_DEFS = [
    ("Skin",     (0.62, 0.60, 0.50)),   # sallow, greyish
    ("Cardigan", (0.22, 0.28, 0.22)),   # faded green
    ("Skirt",    (0.28, 0.20, 0.16)),   # dull brown
    ("Stocking", (0.55, 0.47, 0.40)),
    ("Shoe",     (0.06, 0.05, 0.05)),
    ("Eye",      (0.00, 0.00, 0.00)),
    ("Mouth",    (0.20, 0.04, 0.05)),
]
MAT = {name: i for i, (name, _) in enumerate(MAT_DEFS)}

def make_material(name, rgb):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1.0)
    try:
        bsdf = m.node_tree.nodes.get("Principled BSDF") if m.node_tree else None
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
            bsdf.inputs["Roughness"].default_value = 1.0
    except Exception:
        pass
    return m

# ─── Skeleton (name, head, tail, parent) ──────────────────────────────────────
def side(name, x_sign):
    return ("Left" if x_sign > 0 else "Right") + name

BONES = [
    ("Hips",  (0, 0.00, 0.92), (0, 0.00, 1.02), None),
    ("Spine", (0, 0.00, 1.02), (0, 0.03, 1.16), "Hips"),
    ("Chest", (0, 0.03, 1.16), (0, 0.05, 1.30), "Spine"),   # rounded back
    ("Neck",  (0, 0.05, 1.30), (0, -0.01, 1.39), "Chest"),  # head pushed forward
    ("Head",  (0, -0.01, 1.39), (0, -0.03, 1.78), "Neck"),
]
for s in (1, -1):
    BONES += [
        (side("Shoulder", s), (0.03 * s, 0.04, 1.28), (0.15 * s, 0.04, 1.27), "Chest"),
        (side("UpperArm", s), (0.15 * s, 0.04, 1.27), (0.31 * s, 0.03, 1.05), side("Shoulder", s)),
        (side("LowerArm", s), (0.31 * s, 0.03, 1.05), (0.44 * s, -0.02, 0.84), side("UpperArm", s)),
        (side("Hand", s),     (0.44 * s, -0.02, 0.84), (0.50 * s, -0.04, 0.70), side("LowerArm", s)),
        (side("UpperLeg", s), (0.09 * s, 0.00, 0.90), (0.10 * s, 0.00, 0.50), "Hips"),
        (side("LowerLeg", s), (0.10 * s, 0.00, 0.50), (0.10 * s, 0.01, 0.06), side("UpperLeg", s)),
        (side("Foot", s),     (0.10 * s, 0.01, 0.06), (0.10 * s, -0.13, 0.04), side("LowerLeg", s)),
    ]
BONE_NAMES = [b[0] for b in BONES]
BONE_INDEX = {n: i for i, n in enumerate(BONE_NAMES)}
BONE_DATA = {b[0]: b for b in BONES}

# ─── Mesh building helpers ────────────────────────────────────────────────────
bm = bmesh.new()
deform = bm.verts.layers.deform.verify()

def tag(verts, bone, mat):
    gi = BONE_INDEX[bone]
    for v in verts:
        v[deform][gi] = 1.0
    faces = {f for v in verts for f in v.link_faces}
    for f in faces:
        f.material_index = MAT[mat]

def basis(axis):
    axis = axis.normalized()
    ref = Vector((1, 0, 0)) if abs(axis.x) < 0.9 else Vector((0, 1, 0))
    u = (ref - axis * axis.dot(ref)).normalized()
    v = axis.cross(u).normalized()
    return u, v

def prism(p0, p1, r0, r1, sides, bone, mat, sx=1.0, sy=1.0, twist=0.0):
    """Capped, tapered n-sided tube from p0 to p1."""
    p0, p1 = Vector(p0), Vector(p1)
    u, v = basis(p1 - p0)
    rings = []
    for p, r in ((p0, r0), (p1, r1)):
        ring = []
        for i in range(sides):
            a = twist + 2 * math.pi * i / sides
            ring.append(bm.verts.new(p + u * math.cos(a) * r * sx + v * math.sin(a) * r * sy))
        rings.append(ring)
    a, b = rings
    for i in range(sides):
        j = (i + 1) % sides
        bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.faces.new(list(reversed(a)))
    bm.faces.new(b)
    tag(a + b, bone, mat)
    return a + b

def box(center, size, bone, mat):
    m = Matrix.Translation(Vector(center)) @ Matrix.Diagonal((*size, 1.0))
    verts = bmesh.ops.create_cube(bm, size=1.0, matrix=m)["verts"]
    tag(verts, bone, mat)
    return verts

def bone_box(bone, width, depth, mat, pad=0.0):
    """Box spanning a bone's length (used for hands and feet)."""
    _, h, t, _ = BONE_DATA[bone]
    h, t = Vector(h), Vector(t)
    axis = t - h
    length = axis.length + pad
    u, v = basis(axis)
    rot = Matrix((u, v, axis.normalized())).transposed().to_4x4()
    m = Matrix.Translation((h + t) / 2) @ rot @ Matrix.Diagonal((width, depth, length, 1.0))
    verts = bmesh.ops.create_cube(bm, size=1.0, matrix=m)["verts"]
    tag(verts, bone, mat)
    return verts

def along(bone, r0, r1, sides, mat, **kw):
    _, h, t, _ = BONE_DATA[bone]
    return prism(h, t, r0, r1, sides, bone, mat, **kw)

# ─── Body ─────────────────────────────────────────────────────────────────────
# Skirt: long, flared, hangs from the hips. The front of the hem is partly
# weighted to the thighs so it lifts with the legs when she sits.
skirt = prism((0, 0.0, 0.99), (0, 0.0, 0.52), 0.15, 0.21, 8, "Hips", "Skirt", sy=0.85, twist=math.pi / 8)
for vtx in skirt[8:]:                       # bottom ring
    # Fully weighted (not blended): partial hip/leg blends collapse the hem.
    if vtx.co.y > -0.05 or abs(vtx.co.x) > 0.12:   # front-centre hem only
        continue
    w_leg = 1.0
    vtx[deform][BONE_INDEX["Hips"]] = 1.0 - w_leg
    if abs(vtx.co.x) < 0.03:                # centre front: split between legs
        vtx[deform][BONE_INDEX["LeftUpperLeg"]] = w_leg / 2
        vtx[deform][BONE_INDEX["RightUpperLeg"]] = w_leg / 2
    else:
        vtx[deform][BONE_INDEX[side("UpperLeg", 1 if vtx.co.x > 0 else -1)]] = w_leg
# Torso: narrow, hunched, cardigan. Pieces share the same cross-section at the
# waist/chest join so there is no gap.
prism((0, 0.0, 0.94), (0, 0.03, 1.17), 0.14, 0.14, 6, "Spine", "Cardigan", sy=0.8)
prism((0, 0.03, 1.15), (0, 0.06, 1.31), 0.14, 0.10, 6, "Chest", "Cardigan", sy=0.8)
along("Neck", 0.035, 0.03, 5, "Skin")

# Head: tall, narrow, bald egg with a long drooping chin.
HEAD_C = Vector((0, -0.035, 1.58))
head_m = Matrix.Translation(HEAD_C) @ Matrix.Diagonal((0.085, 0.095, 0.20, 1.0))
head = bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=7, radius=1.0, matrix=head_m)["verts"]
for vtx in head:
    rel = vtx.co - HEAD_C
    if rel.z < -0.05:                       # stretch the jaw down and forward
        k = (-0.05 - rel.z) / 0.15
        vtx.co.z -= 0.05 * k
        vtx.co.y -= 0.03 * k
        vtx.co.x *= 1.0 - 0.35 * k          # narrow, pointed chin
    if rel.z > 0.12:                        # slightly flattened, bony crown
        vtx.co.z -= 0.015
tag(head, "Head", "Skin")

# Face: hollow black eyes, long nose, thin dark mouth, small ears.
for s in (1, -1):
    box((0.036 * s, -0.121, 1.625), (0.036, 0.03, 0.030), "Head", "Eye")
    box((0.087 * s, -0.03, 1.60), (0.02, 0.035, 0.06), "Head", "Skin")
prism((0, -0.128, 1.63), (0, -0.15, 1.525), 0.010, 0.020, 4, "Head", "Skin")
box((0, -0.112, 1.46), (0.06, 0.03, 0.007), "Head", "Mouth")

# Arms: long sleeves, bony hands with long fingers.
for s in (1, -1):
    along(side("Shoulder", s), 0.05, 0.045, 5, "Cardigan")
    along(side("UpperArm", s), 0.042, 0.036, 5, "Cardigan")
    along(side("LowerArm", s), 0.035, 0.028, 5, "Cardigan")
    bone_box(side("Hand", s), 0.055, 0.02, "Skin", pad=0.03)

# Legs: thin stockinged legs and flat black shoes.
for s in (1, -1):
    along(side("UpperLeg", s), 0.06, 0.045, 6, "Stocking")
    along(side("LowerLeg", s), 0.042, 0.03, 6, "Stocking")
    bone_box(side("Foot", s), 0.075, 0.05, "Shoe", pad=0.02)

bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

# ─── Objects ──────────────────────────────────────────────────────────────────
mesh = bpy.data.meshes.new("GrandmaMesh")
body = bpy.data.objects.new("Grandma", mesh)
bpy.context.scene.collection.objects.link(body)
for name, rgb in MAT_DEFS:
    mesh.materials.append(make_material(name, rgb))
for name in BONE_NAMES:
    body.vertex_groups.new(name=name)
bm.to_mesh(mesh)
bm.free()
for p in mesh.polygons:
    p.use_smooth = False                    # flat shading, PSX look

arm_data = bpy.data.armatures.new("GrandmaRig")
rig = bpy.data.objects.new("GrandmaRig", arm_data)
bpy.context.scene.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode="EDIT")
for name, h, t, parent in BONES:
    eb = arm_data.edit_bones.new(name)
    eb.head, eb.tail = Vector(h), Vector(t)
    if parent:
        eb.parent = arm_data.edit_bones[parent]
bpy.ops.object.mode_set(mode="OBJECT")

body.parent = rig
mod = body.modifiers.new("Armature", "ARMATURE")
mod.object = rig

tris = sum(len(p.vertices) - 2 for p in mesh.polygons)
print(f"GRANDMA verts={len(mesh.vertices)} tris={tris} bones={len(BONE_NAMES)}")

# ─── Export ───────────────────────────────────────────────────────────────────
os.makedirs(os.path.dirname(os.path.abspath(OUT_FBX)), exist_ok=True)
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

# ─── Previews ─────────────────────────────────────────────────────────────────
if PREVIEW_DIR:
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.render.resolution_x, scene.render.resolution_y = 480, 640
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    cam.data.type = "ORTHO"
    scene.collection.objects.link(cam)
    scene.camera = cam

    def shoot(name, loc, target, scale=2.0):
        cam.location = Vector(loc)
        d = Vector(target) - cam.location
        cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        cam.data.ortho_scale = scale
        scene.render.filepath = os.path.join(PREVIEW_DIR, name + ".png")
        bpy.ops.render.render(write_still=True)

    shoot("front", (0, -5, 0.9), (0, 0, 0.9))
    shoot("side", (5, 0, 0.9), (0, 0, 0.9))
    shoot("three_quarter", (3.5, -3.5, 1.2), (0, 0, 0.9))
    shoot("face", (0, -5, 1.58), (0, 0, 1.58), scale=0.6)

    # Rig check: sit her down (thighs forward, knees bent, hands on lap).
    pb = rig.pose.bones
    for s in (1, -1):
        pb[side("UpperLeg", s)].rotation_mode = "XYZ"
        pb[side("UpperLeg", s)].rotation_euler = (math.radians(90), 0, 0)
        pb[side("LowerLeg", s)].rotation_mode = "XYZ"
        pb[side("LowerLeg", s)].rotation_euler = (math.radians(-90), 0, 0)
        pb[side("UpperArm", s)].rotation_mode = "XYZ"
        pb[side("UpperArm", s)].rotation_euler = (math.radians(15), 0, 0)
        pb[side("LowerArm", s)].rotation_mode = "XYZ"
        pb[side("LowerArm", s)].rotation_euler = (math.radians(55), 0, 0)
    bpy.context.view_layer.update()
    shoot("seated_side", (5, 0, 0.8), (0, 0, 0.8))
    shoot("seated_3q", (3.5, -3.5, 1.1), (0, 0, 0.8))
    print("PREVIEWS", PREVIEW_DIR)
