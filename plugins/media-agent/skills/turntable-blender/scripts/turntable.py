"""Turntable de um modelo glTF (.glb) em Cycles/GPU, sem abrir o Blender.

  blender -b -P turntable.py -- --glb modelo.glb --out DIR --frames 120 --samples 128 [--res 1080] [--preview]

Gera DIR/frame_0001.png ... com fundo transparente (RGBA), uma volta completa em torno do
centro da bounding box, luz key/fill/rim em area lights e AgX. CYCLES_BACKEND=OPTIX|CUDA
escolhe o backend; o padrao tenta CUDA e depois OPTIX. Testado no Blender 5.2.
"""
import argparse, math, sys
import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--glb", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--frames", type=int, default=90); ap.add_argument("--samples", type=int, default=128)
ap.add_argument("--res", type=int, default=1080); ap.add_argument("--preview", action="store_true", help="renderiza só 3 frames em baixa amostragem")
a = ap.parse_args(argv)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
bpy.ops.import_scene.gltf(filepath=a.glb)
objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if not objs:
    raise SystemExit("nenhuma mesh no glb")

# agrupa tudo num pivô centrado na bounding box
from mathutils import Vector
mins = Vector((1e9,)*3); maxs = Vector((-1e9,)*3)
for o in objs:
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        mins = Vector(map(min, mins, w)); maxs = Vector(map(max, maxs, w))
center = (mins + maxs) / 2; size = max(maxs - mins)
pivot = bpy.data.objects.new("Pivot", None); scene.collection.objects.link(pivot); pivot.location = center
for o in bpy.context.scene.objects:
    if o.parent is None and o is not pivot and o.type in {"MESH", "EMPTY"}:
        o.parent = pivot; o.matrix_parent_inverse = pivot.matrix_world.inverted()

# câmera em órbita: gira o pivô, câmera fixa em 3/4
cam_data = bpy.data.cameras.new("Cam"); cam = bpy.data.objects.new("Cam", cam_data); scene.collection.objects.link(cam)
cam_data.lens = 65
dist = size * 2.3
cam.location = center + Vector((dist * 0.8, -dist * 0.9, dist * 0.45))
look = center - cam.location
cam.rotation_euler = look.to_track_quat("-Z", "Y").to_euler()
scene.camera = cam

# luz de estúdio: key + fill + rim (area lights) e mundo neutro
def area(name, loc, energy, size_, color=(1, 1, 1)):
    l = bpy.data.lights.new(name, "AREA"); l.energy = energy; l.size = size_; l.color = color
    o = bpy.data.objects.new(name, l); scene.collection.objects.link(o); o.location = center + Vector(loc)
    o.rotation_euler = (center - o.location).to_track_quat("-Z", "Y").to_euler(); return o
area("Key", (dist * 0.6, -dist * 0.6, dist * 0.9), 60 * size * size, size * 1.2, (1.0, 0.96, 0.9))
area("Fill", (-dist * 0.9, -dist * 0.4, dist * 0.3), 22 * size * size, size * 2.0, (0.92, 0.95, 1.0))
area("Rim", (-dist * 0.3, dist * 0.9, dist * 0.7), 55 * size * size, size * 0.8)
world = bpy.data.worlds.new("World"); scene.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.9, 0.87, 0.82, 1); world.node_tree.nodes["Background"].inputs[1].default_value = 0.15

# animação: uma volta completa
frames = 3 if a.preview else a.frames
scene.frame_start = 1; scene.frame_end = frames
bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"  # Blender 5: actions em camadas, sem action.fcurves
pivot.rotation_euler = (0, 0, 0); pivot.keyframe_insert("rotation_euler", frame=1)
pivot.rotation_euler = (0, 0, math.tau); pivot.keyframe_insert("rotation_euler", frame=frames + 1)

# render: Cycles em GPU (OptiX > CUDA), transparente, PNG RGBA
scene.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
import os
for backend in tuple(filter(None, [os.environ.get("CYCLES_BACKEND")])) or ("CUDA", "OPTIX"):
    try:
        # get_devices() enumera também oneAPI/Level Zero e segfaulta com a Arc integrada; enumerar só o backend pedido
        prefs.compute_device_type = backend; devs = prefs.get_devices_for_type(backend)
        if devs:
            for d in devs: d.use = True
            scene.cycles.device = "GPU"; print("cycles device:", backend, flush=True); break
    except Exception as e: print("backend", backend, "indisponível:", e)
scene.cycles.samples = 16 if a.preview else a.samples
scene.cycles.use_denoising = True
scene.view_settings.view_transform = "AgX"; scene.view_settings.look = "AgX - Base Contrast"; scene.view_settings.exposure = 0.0
scene.render.film_transparent = True
scene.render.resolution_x = a.res; scene.render.resolution_y = a.res; scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"; scene.render.image_settings.color_mode = "RGBA"
scene.render.filepath = a.out.rstrip("/") + "/frame_"
bpy.ops.render.render(animation=True)
print("done:", scene.render.filepath, "frames", frames)
