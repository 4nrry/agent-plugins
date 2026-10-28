"""Helpers for scripted Blender scenes: quality tiers, a camera that tracks an
empty, hand-held shake, one spot with a sweep, and rigged .glb figures that
keep their rotation and stand in a chosen pose.

Import it from a scene script run with
    blender -b --factory-startup --python-exit-code 1 -P scene.py -- ...
after `sys.path.insert(0, "<this skill>/scripts")`. Run it directly for a demo:
    blender -b --factory-startup --python-exit-code 1 -P scene_kit.py -- \
        --demo figure.glb OUT_DIR [--quality preview] [--frames 8] [--action Idle] [--frame 10]
"""

import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

# resolution, TAA samples, volume samples
QUALITY = {
    "preview": ((270, 480), 4, 8),
    "final": ((540, 960), 8, 64),
}


def reset(quality="final", frames=120, fps=30, fog=0.035, res=None):
    """Empty scene on EEVEE with a black world and optional volumetric fog."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            sc.render.engine = engine
            break
        except TypeError:
            continue
    (w, h), taa, vol = QUALITY[quality]
    if res:
        w, h = res
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.fps = fps
    sc.frame_start, sc.frame_end = 1, frames
    sc.eevee.taa_render_samples = taa
    if hasattr(sc.eevee, "volumetric_samples"):
        sc.eevee.volumetric_samples = vol
    if quality == "final" and hasattr(sc.eevee, "volumetric_tile_size"):
        # The default 8 px froxels show as a grid in a fogged spotlight cone.
        sc.eevee.volumetric_tile_size = "2"
    sc.view_settings.view_transform = "Standard"
    sc.render.image_settings.file_format = "PNG"
    world = bpy.data.worlds.new("world")
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes["Background"].inputs["Color"].default_value = (0, 0, 0, 1)
    if fog:
        vol_node = nt.nodes.new("ShaderNodeVolumePrincipled")
        vol_node.inputs["Density"].default_value = fog
        nt.links.new(vol_node.outputs["Volume"], nt.nodes["World Output"].inputs["Volume"])
    return sc


def link(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def empty(name, loc):
    ob = link(bpy.data.objects.new(name, None))
    ob.location = loc
    return ob


def track(ob, target):
    c = ob.constraints.new("TRACK_TO")
    c.target = target
    c.track_axis, c.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"


def camera(loc, target, lens=35, fstop=None):
    """Camera aimed at an empty. Animate the camera and the empty, never the rotation."""
    data = bpy.data.cameras.new("cam")
    data.lens = lens
    cam = link(bpy.data.objects.new("cam", data))
    cam.location = loc
    tgt = empty("cam_target", target)
    track(cam, tgt)
    if fstop:
        data.dof.use_dof = True
        data.dof.aperture_fstop = fstop
        data.dof.focus_object = tgt
    bpy.context.scene.camera = cam
    return cam, tgt


def keys(ob, path, pairs, index):
    """pairs: [(frame, value), ...] on one channel of a vector property."""
    for frame, value in pairs:
        getattr(ob, path)[index] = value
        ob.keyframe_insert(path, index=index, frame=frame)


def _fcurves(ob):
    ad = ob.animation_data
    if not ad or not ad.action:
        return []
    act = ad.action
    if hasattr(act, "fcurves"):
        return list(act.fcurves)
    # Blender 5: layered actions keep the curves in a channelbag per slot.
    out = []
    for layer in act.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                out.extend(bag.fcurves)
    return out


def shake(target, strength=0.03, scale=6.0):
    """Hand-held tremor as noise on the target, added on top of any move."""
    have = {fc.array_index for fc in _fcurves(target) if fc.data_path == "location"}
    for i in range(3):
        if i not in have:
            target.keyframe_insert("location", index=i, frame=1)
    for fc in _fcurves(target):
        if fc.data_path == "location":
            m = fc.modifiers.new("NOISE")
            m.strength, m.scale, m.phase = strength, scale, 7 * fc.array_index + 3


def spot(loc, target, energy=1200, angle=40, blend=0.1, size=0.02):
    data = bpy.data.lights.new("spot", "SPOT")
    data.energy = energy
    data.spot_size, data.spot_blend = math.radians(angle), blend
    data.shadow_soft_size = size
    ob = link(bpy.data.objects.new("spot", data))
    ob.location = loc
    tgt = empty("spot_target", target)
    track(ob, tgt)
    return ob, tgt


def sweep(target, frames, axis=0, amp=1.5, cycles=1.0):
    """The light target oscillates on one axis over the shot."""
    base = target.location[axis]
    pairs = [(f, base + amp * math.sin(2 * math.pi * cycles * (f - 1) / frames))
             for f in range(1, frames + 1, 4)]
    keys(target, "location", pairs, axis)


def flat(name, color, emit=0.0):
    """Diffuse plus emission of the same colour: a flat low-poly look."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = 1.0
    if emit:
        key = "Emission Color" if "Emission Color" in bsdf.inputs else "Emission"
        bsdf.inputs[key].default_value = (*color, 1)
        bsdf.inputs["Emission Strength"].default_value = emit
    return m


def _world_z(root):
    bpy.context.view_layer.update()
    zs = [(ob.matrix_world @ Vector(c)).z
          for ob in [root, *root.children_recursive] if ob.type == "MESH" for c in ob.bound_box]
    return min(zs), max(zs)


_TEMPLATES = {}


def _template(glb, action, frame):
    """Import the glb once per (file, action, frame) and freeze that pose into the mesh."""
    key = (str(glb), action, frame)
    if key in _TEMPLATES:
        return _TEMPLATES[key]
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(glb))
    new = [o for o in bpy.data.objects if o not in before]
    arm = next((o for o in new if o.type == "ARMATURE"), None)
    if arm is None:
        raise RuntimeError("%s has no armature" % glb)
    root = arm
    while root.parent:
        root = root.parent
    keep = {root, *root.children_recursive}
    for ob in new:  # glbs often ship a Cube, Camera or Light beside the character
        if ob not in keep:
            bpy.data.objects.remove(ob)
    if action:
        names = sorted(a.name for a in bpy.data.actions)
        act = next((a for a in bpy.data.actions
                    if a.name.split("|")[-1].split(".")[0].lower() == action.lower()), None)
        if act is None:
            raise RuntimeError("no action %r in %s; actions: %s" % (action, glb, ", ".join(names)))
        if arm.animation_data is None:
            arm.animation_data_create()
        arm.animation_data.action = act
        slots = list(getattr(act, "slots", []) or [])
        if slots and hasattr(arm.animation_data, "action_slot"):
            arm.animation_data.action_slot = slots[0]
    bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    for mesh in [o for o in root.children_recursive if o.type == "MESH"]:
        if any(m.type == "ARMATURE" for m in mesh.modifiers):
            mesh.data = bpy.data.meshes.new_from_object(mesh.evaluated_get(deps))
            mesh.modifiers.clear()
        for poly in mesh.data.polygons:
            poly.use_smooth = False
    for ob in keep:
        if ob.animation_data:
            ob.animation_data_clear()
    root.rotation_mode = "XYZ"
    root.rotation_euler = (0, 0, 0)
    root.location = (0, 0, 0)
    root.scale = (1, 1, 1)
    z0, z1 = _world_z(root)
    for ob in keep:
        ob.hide_render = ob.hide_viewport = True
    _TEMPLATES[key] = (root, z1 - z0, -z0)
    return _TEMPLATES[key]


def _copy_tree(ob, parent=None):
    dup = ob.copy()  # mesh data stays shared
    link(dup)
    dup.hide_render = dup.hide_viewport = False
    if parent is not None:
        dup.parent = parent
        dup.matrix_parent_inverse = ob.matrix_parent_inverse.copy()
    for child in ob.children:
        _copy_tree(child, dup)
    return dup


def figure(glb, loc=(0, 0, 0), face=0.0, height=1.9, material=None, action="Idle", frame=10):
    """A rigged glb frozen in one pose, `height` metres tall, feet on z=loc.z.

    face: 0 faces -Y (a camera on -Y sees the front), pi faces away, -pi/2 shows
    a profile. Root objects imported from glTF use quaternion rotation, which
    ignores rotation_euler; the copy is switched to XYZ.
    """
    root, measured, lift = _template(glb, action, frame)
    dup = _copy_tree(root)
    s = height / measured
    dup.rotation_mode = "XYZ"
    dup.rotation_euler = (0, 0, face)
    dup.scale = (s, s, s)
    dup.location = (loc[0], loc[1], loc[2] + lift * s)
    if material is not None:
        for ob in dup.children_recursive:
            if ob.type == "MESH":
                ob.data = ob.data.copy()
                ob.data.materials.clear()
                ob.data.materials.append(material)
    return dup


def render(out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    bpy.context.scene.render.filepath = str(out / "f_")
    bpy.ops.render.render(animation=True)


def _demo(argv):
    import argparse
    p = argparse.ArgumentParser(prog="scene_kit.py --demo")
    p.add_argument("glb")
    p.add_argument("out")
    p.add_argument("--quality", default="preview", choices=sorted(QUALITY))
    p.add_argument("--frames", type=int, default=8)
    p.add_argument("--action", default="Idle")
    p.add_argument("--frame", type=int, default=10)
    a = p.parse_args(argv)
    reset(a.quality, frames=a.frames, fog=0.03)
    floor = link(bpy.data.objects.new("floor", bpy.data.meshes.new("floor")))
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=20)
    bm.to_mesh(floor.data)
    floor.data.materials.append(flat("floor", (0.06, 0.06, 0.06)))
    white = flat("white", (0.82, 0.83, 0.80), emit=0.12)
    figs = [figure(a.glb, (-1.2, 0, 0), 0.0, material=white, action=a.action, frame=a.frame),
            figure(a.glb, (0, 0, 0), -math.pi / 2, material=white, action=a.action, frame=a.frame),
            figure(a.glb, (1.2, 0, 0), math.pi, material=white, action=a.action, frame=a.frame)]
    cam, tgt = camera((-0.6, -6.5, 1.4), (0, 0, 1.0), lens=30)
    keys(cam, "location", [(1, -0.6), (a.frames, 0.6)], 0)
    shake(tgt, 0.01)
    light, ltgt = spot((0, -3, 6), (0, 0, 0.8), energy=1500, angle=60, blend=0.4)
    sweep(ltgt, a.frames, axis=0, amp=0.8)
    for f in figs:
        z0, z1 = _world_z(f)
        print("FIGURE %s mode=%s face=%.3f height=%.3f feet=%.3f"
              % (f.name, f.rotation_mode, f.rotation_euler.z, z1 - z0, z0))
    render(a.out)
    print("DEMO_OK", a.out)


if __name__ == "__main__" and "--demo" in sys.argv:
    _demo(sys.argv[sys.argv.index("--demo") + 1:])
