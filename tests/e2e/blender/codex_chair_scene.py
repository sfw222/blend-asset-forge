"""Creates and refines the furniture fixture inside the same live Blender session."""

import os

import bpy
from mathutils import Vector


def aim(obj, point):
    obj.rotation_euler = (Vector(point) - obj.location).to_track_quat("-Z", "Y").to_euler()


def wood(vertical):
    material = bpy.data.materials.new("Oak vertical" if vertical else "Oak horizontal")
    material.diffuse_color = (0.49, 0.235, 0.071, 1.0)
    material.use_nodes = True
    nt = material.node_tree
    bsdf = next(node for node in nt.nodes if node.type == "BSDF_PRINCIPLED")
    coords = nt.nodes.new("ShaderNodeTexCoord")
    stretch = nt.nodes.new("ShaderNodeVectorMath")
    stretch.operation = "MULTIPLY"
    stretch.inputs[1].default_value = (115, 83, 3.5) if vertical else (4, 120, 95)
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 4
    noise.inputs["Detail"].default_value = 2.2
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.17
    ramp.color_ramp.elements[0].color = (0.19, 0.072, 0.014, 1)
    ramp.color_ramp.elements[1].position = 0.83
    ramp.color_ramp.elements[1].color = (0.45, 0.21, 0.046, 1)
    nt.links.new(coords.outputs["Object"], stretch.inputs[0])
    nt.links.new(stretch.outputs[0], noise.inputs["Vector"])
    nt.links.new(noise.outputs["Fac"], ramp.inputs[0])
    nt.links.new(ramp.outputs[0], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.38
    return material


def box(name, location, size, material=None, bevel=0.0, segments=1):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        mod = obj.modifiers.new("Soft edges", "BEVEL")
        mod.width = bevel
        mod.segments = segments
        bpy.ops.object.modifier_apply(modifier=mod.name)
        norm = obj.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
        bpy.ops.object.modifier_apply(modifier=norm.name)
    if material:
        obj.data.materials.append(material)
    return obj


def dimensions(revised):
    leg_width = 0.043 if revised else 0.055
    seat_thick = 0.025 if revised else 0.046
    panel_height = 0.163 if revised else 0.11
    panel_z = 0.773 if revised else 0.742
    legs = [(f"Front{x}", (x * 0.197, -0.194, 0.222), (leg_width, leg_width, 0.444), True)
            for x in (-1, 1)]
    legs += [(f"Rear{x}", (x * 0.197, 0.198, 0.443), (leg_width, leg_width, 0.886), True)
             for x in (-1, 1)]
    parts = legs + [
        ("Seat", (0, -0.009, 0.461 - seat_thick / 2), (0.464, 0.442, seat_thick), False),
        ("Back", (0, 0.198, panel_z), (0.354, 0.026, panel_height), False),
        ("Rail front", (0, -0.194, 0.411), (0.365, 0.024, 0.057), False),
        ("Rail rear", (0, 0.198, 0.411), (0.365, 0.024, 0.057), False),
        ("Rail left", (-0.197, 0.002, 0.411), (0.024, 0.367, 0.057), False),
        ("Rail right", (0.197, 0.002, 0.411), (0.024, 0.367, 0.057), False),
    ]
    return parts


def join(parts, name, materials, bevel, segments):
    objects = [box(label, loc, size, materials[vertical], bevel, segments)
               for label, loc, size, vertical in parts]
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    obj = bpy.context.object
    obj.name = name
    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
    return obj


def build_chair(revised):
    # The runner uses a factory-startup Blender and owns the whole example scene.
    for obj in list(bpy.context.scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    materials = {vertical: wood(vertical) for vertical in (True, False)}
    parts = dimensions(revised)
    low = join(parts, "SM_OakChair", materials, 0.003, 2)
    if revised:
        high = join(parts, "OakChair_High", materials, 0.0038, 5)
        high.hide_set(True)
        high.hide_render = True
        for index, (_, pos, size, _) in enumerate(parts[:6]):
            proxy = box(f"UCX_SM_OakChair_{index:02d}", pos, size)
            proxy.hide_set(True)
            proxy.hide_render = True
    camera_data = bpy.data.cameras.new("Chair review")
    camera = bpy.data.objects.new("Chair review", camera_data)
    scene.collection.objects.link(camera)
    camera.location = (-1.02, -2.37, 1.17)
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 1.07
    aim(camera, (0, 0, 0.446))
    scene.camera = camera
    scene.render.resolution_x = scene.render.resolution_y = 768
    scene.render.resolution_percentage = 100
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    low.select_set(True)
    bpy.context.view_layer.objects.active = low
    bpy.context.view_layer.update()
    print(f"CHAIR {revised=} dimensions={[round(x, 4) for x in low.dimensions]}")


def beauty(output):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 12
    scene.cycles.use_denoising = True
    scene.render.threads_mode = "FIXED"
    scene.render.threads = min(12, os.cpu_count() or 4)
    scene.world.use_nodes = True
    background = next(node for node in scene.world.node_tree.nodes if node.type == "BACKGROUND")
    background.inputs[0].default_value = (0.7, 0.7, 0.7, 1)
    background.inputs[1].default_value = 0.32
    floor = bpy.data.materials.new("Warm white studio")
    floor.diffuse_color = (0.77, 0.72, 0.68, 1)
    box("Studio floor", (0, 0, -0.015), (200, 200, 0.028), floor)
    for name, position, power, size in (
        ("Key", (-2, -2, 3), 300, 2.0), ("Fill", (1.5, -1.2, 1.8), 105, 2.2),
        ("Rim", (0.4, 1.4, 2.3), 180, 1.3),
    ):
        lamp = bpy.data.lights.new(name, "AREA")
        lamp.energy, lamp.size = power, size
        obj = bpy.data.objects.new(name, lamp)
        scene.collection.objects.link(obj)
        obj.location = position
        aim(obj, (0, 0, 0.4))
    scene.render.filepath = output
    bpy.ops.render.render(write_still=True)


def build_skeletal_probe():
    material = wood(False)
    obj = box("SK_Probe", (0, 0, 0.5), (0.18, 0.18, 1), material)
    armature = bpy.data.armatures.new("ProbeSkeleton")
    rig = bpy.data.objects.new("ProbeRig", armature)
    bpy.context.collection.objects.link(rig)
    obj.select_set(False)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    bone = armature.edit_bones.new("root")
    bone.head, bone.tail = (0, 0, 0), (0, 0, 1)
    bpy.ops.object.mode_set(mode="OBJECT")
    group = obj.vertex_groups.new(name="root")
    group.add(range(len(obj.data.vertices)), 1.0, "REPLACE")
    obj.parent = rig
    obj.modifiers.new("Skin", "ARMATURE").object = rig
    rig.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def build_probe_actions():
    rig = bpy.data.objects["ProbeRig"]
    bone = rig.pose.bones["root"]
    animation = rig.animation_data_create()
    for name, end, shift in (("ProbeWalk", 12, 0.4), ("ProbeStep", 7, 0.2)):
        animation.action = None
        for frame, x in ((1, 0.0), (end, shift)):
            bone.location.x = x
            bone.keyframe_insert(data_path="location", frame=frame)
        animation.action.name = name
        animation.action.use_fake_user = True
