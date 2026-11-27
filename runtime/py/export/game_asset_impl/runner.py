"""Isolated Blender jobs for texture baking, LOD creation and Unreal FBX delivery."""

import importlib.util
import json
import math
from pathlib import Path
import re
import sys

import bmesh
import bpy


RECIPES = {"bake_maps", "make_lods", "export_unreal", "prepare_unreal"}
LOD_OWNER = "codex_blender_lod_source"
SKILL_LIBRARY = Path(__file__).resolve().parents[3] / "ext" / "blender-skills"


def mesh(name):
    obj = bpy.context.view_layer.objects.get(name) if isinstance(name, str) else None
    if obj is None or obj.type != "MESH" or not obj.data.polygons:
        raise ValueError(f"Expected a mesh with faces in the active view layer: {name!r}")
    return obj


def names(items, field):
    if not isinstance(items, list) or any(not isinstance(item, str) or not item for item in items):
        raise ValueError(f"{field} must be an array of object names")
    if len(set(items)) != len(items):
        raise ValueError(f"{field} contains duplicate names")
    return items


def check_keys(options, allowed):
    if not isinstance(options, dict) or options.keys() - set(allowed):
        raise ValueError(f"Expected options with fields: {', '.join(allowed)}")


def selection(objects):
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    for obj in objects:
        obj.hide_set(False)
        obj.select_set(True)
        if not obj.select_get():
            raise ValueError(f"Cannot select {obj.name}; check visibility and selectability")
    bpy.context.view_layer.objects.active = objects[0]


def number(value, field, minimum, maximum):
    if type(value) not in (int, float) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{field} must be between {minimum} and {maximum}")
    return value


def load_module(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not locate Blender runtime module: {file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def delivery_gate(source, output):
    bootstrap = load_module("_asset_offline_bootstrap", Path(__file__).parents[2] / "core" / "offline_bootstrap.py")
    gate = bootstrap.boot(["uv_tools", "material", "gate"])["kapi"]("gate")
    params = {"preset": "delivery", "overrides": {key: {"objects": [source.name]} for key in ("uv", "materials")}}
    receipt = gate("run", params)
    if isinstance(receipt, str):
        receipt = json.loads(receipt)
    (output / "delivery-gate.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    if receipt.get("verdict") != "pass":
        raise ValueError(f"Delivery gate returned {receipt.get('verdict')}: see {output / 'delivery-gate.json'}")
    return receipt


def extended_delivery(source, output, settings):
    check_keys(settings, ("profile", "max_tris", "budget", "overlap_limit", "allow_outside_uv", "armature", "influence_limit"))
    qa = load_module("_dsh_delivery_qa", SKILL_LIBRARY / "qa_check.py")
    mesh_stats = load_module("_dsh_delivery_budget", SKILL_LIBRARY / "mesh_stats.py")
    kwargs = {"profile": settings["profile"]} if "profile" in settings else {}
    mesh_report = qa.run(objects=[source.name], **kwargs)
    budget = mesh_stats.run(objects=[source.name], budget=settings.get("budget"))
    errors = list(mesh_report["errors"])
    if settings.get("max_tris") is not None:
        maximum = number(settings["max_tris"], "qa.max_tris", 1, 100_000_000)
        triangles = mesh_report["objects"][source.name]["tris"]
        if triangles > maximum:
            errors.append(f"{source.name}: {triangles} triangles exceed the budget {maximum}")
    if settings.get("overlap_limit") is not None:
        limit = number(settings["overlap_limit"], "qa.overlap_limit", 0, 100)
        if mesh_report["objects"][source.name].get("uv_overlap_pct", 0) > limit:
            errors.append(f"Estimated UV overlap exceeds {limit}%")
    if settings.get("allow_outside_uv") is False and mesh_report["objects"][source.name].get("uv_oob_pct", 0) > 0:
        errors.append("UV coordinates are outside the 0–1 tile")
    if budget.get("budget", {}).get("pass") is False:
        errors.extend(map(str, budget["budget"]["over"]))
    report = {"ok": not errors, "errors": errors, "mesh": mesh_report, "budget": budget}
    if settings.get("armature"):
        rig = load_module("_dsh_delivery_rig", SKILL_LIBRARY / "rig_check.py")
        skin = rig.run(armature=settings["armature"], meshes=[source.name], limit=settings.get("influence_limit", 4))
        report["rig"] = skin
        if not skin.get("ok") or not skin.get("pass"):
            errors.extend(skin.get("errors") or ["Skeleton or skin check failed"])
        if any(item["not_normalized"] for item in skin.get("skin", {}).values()):
            errors.append("Some skin weights do not sum to 1")
    report["ok"] = not errors
    (output / "extended-qa.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    if errors:
        raise ValueError(f"Extended delivery QA failed: see {output / 'extended-qa.json'}")
    return str(output / "extended-qa.json")


def bake_maps(source, output, options):
    check_keys(options, (
        "high", "maps", "res", "samples", "margin_px", "extrusion", "cage", "directx", "pack_orm", "device", "uv_layer",
    ))
    if not source.data.uv_layers:
        raise ValueError(f"{source.name} needs a UV map before baking")
    high = [mesh(name) for name in names(options.get("high", []), "bake.high")]
    cage = mesh(options["cage"]) if "cage" in options else None
    if source in high or cage is source or cage in high or (cage and not high):
        raise ValueError("Bake target, high meshes and cage must be distinct; a cage requires high meshes")
    for obj in [source, *high]:
        if not obj.material_slots or any(not slot.material or not slot.material.node_tree for slot in obj.material_slots):
            raise ValueError(f"Assign node materials to all slots on {obj.name} before baking")
    res = int(number(options.get("res", 1024), "bake.res", 16, 8192))
    samples = int(number(options.get("samples", 32), "bake.samples", 1, 4096))
    margin = int(number(options.get("margin_px", 8), "bake.margin_px", 0, 256))
    extrusion = options.get("extrusion")
    if extrusion is not None:
        number(extrusion, "bake.extrusion", 0, 100)
    directx = options.get("directx", True)
    pack = options.get("pack_orm", True)
    device = options.get("device", "CPU")
    if type(directx) is not bool or type(pack) is not bool or device not in ("CPU", "GPU"):
        raise ValueError("directx/pack_orm must be booleans and device must be CPU or GPU")
    uv_layer = options.get("uv_layer")
    if uv_layer is not None and (not isinstance(uv_layer, str) or uv_layer not in source.data.uv_layers):
        raise ValueError("bake.uv_layer must name an existing UV map")
    vendor = SKILL_LIBRARY / "bake_maps.py"
    module = load_module("_dsh_blender_skills_bake", vendor)
    maps = names(options.get("maps", ["basecolor", "normal", "ao", "roughness", "metallic"]), "bake.maps")
    if not maps or set(maps) - module.SUFFIX.keys():
        raise ValueError(f"Choose at least one supported map from {sorted(module.SUFFIX)}")
    if pack:
        maps.extend(key for key in ("ao", "roughness", "metallic") if key not in maps)
    hidden = [(obj, obj.hide_render, obj.hide_get()) for obj in [source, *high, *([cage] if cage else [])]]
    try:
        for obj, _, _ in hidden:
            obj.hide_render = False
            obj.hide_set(False)
        selection([source, *high])
        result = module.run(
            low=source.name, high=[obj.name for obj in high], maps=maps, res=res, samples=samples,
            margin_px=margin, extrusion=extrusion, cage=cage.name if cage else None,
            directx=directx, out=str(output / "textures"), name=source.name.removeprefix("SM_"),
            pack_orm=pack, device=device, uv_layer=uv_layer,
        )
    finally:
        for obj, render, viewport in hidden:
            obj.hide_render = render
            obj.hide_set(viewport)
    result["maps"] = {key: str(Path(bpy.path.abspath(value)).resolve()) for key, value in result["maps"].items()}
    result["normal_format"] = "DirectX" if directx else "OpenGL"
    if uv_layer:
        source.data.uv_layers[uv_layer].active_render = True
    return result


def baked_material(source, baked):
    maps = baked["maps"]
    material = bpy.data.materials.new("M_" + source.name.removeprefix("SM_") + "_Baked")
    material.use_nodes = True
    tree = material.node_tree
    bsdf = next(node for node in tree.nodes if node.type == "BSDF_PRINCIPLED")
    uv = tree.nodes.new("ShaderNodeUVMap")
    uv.uv_map = source.data.uv_layers.active.name
    uv.location = (-850, 0)
    textures = {}
    for index, key in enumerate(("basecolor", "normal", "roughness", "metallic", "orm")):
        if key in maps:
            node = tree.nodes.new("ShaderNodeTexImage")
            node.label = key
            node.location = (-610, 330 - 300 * index)
            node.image = bpy.data.images.load(maps[key], check_existing=False)
            node.image.colorspace_settings.name = "sRGB" if key == "basecolor" else "Non-Color"
            node.image.pack()
            tree.links.new(uv.outputs[0], node.inputs["Vector"])
            textures[key] = node.outputs["Color"]
    for key, name in (("basecolor", "Base Color"), ("roughness", "Roughness"), ("metallic", "Metallic")):
        if key in textures:
            tree.links.new(textures[key], bsdf.inputs[name])
    if "normal" in textures:
        normal = textures["normal"]
        if baked["normal_format"] == "DirectX":
            rgb = tree.nodes.new("ShaderNodeSeparateColor")
            invert = tree.nodes.new("ShaderNodeMath")
            invert.operation = "SUBTRACT"
            invert.inputs[0].default_value = 1
            combine = tree.nodes.new("ShaderNodeCombineColor")
            tree.links.new(normal, rgb.inputs[0])
            tree.links.new(rgb.outputs["Green"], invert.inputs[1])
            tree.links.new(invert.outputs[0], combine.inputs["Green"])
            for channel in ("Red", "Blue"):
                tree.links.new(rgb.outputs[channel], combine.inputs[channel])
            normal = combine.outputs[0]
        node = tree.nodes.new("ShaderNodeNormalMap")
        node.uv_map = uv.uv_map
        tree.links.new(normal, node.inputs["Color"])
        tree.links.new(node.outputs[0], bsdf.inputs["Normal"])
    source.data = source.data.copy()
    source.data.materials.clear()
    source.data.materials.append(material)
    for face in source.data.polygons:
        face.material_index = 0
    return material.name


def tris(data):
    return sum(len(poly.vertices) - 2 for poly in data.polygons)


def make_lods(source, options):
    check_keys(options, ("ratios",))
    ratios = options.get("ratios", [0.5, 0.25, 0.125])
    if not isinstance(ratios, list) or not 1 <= len(ratios) <= 7:
        raise ValueError("lod.ratios must contain 1 to 7 decreasing ratios between 0 and 1")
    ratios = [number(ratio, "lod ratio", 0.001, 0.999) for ratio in ratios]
    if any(left <= right for left, right in zip(ratios, ratios[1:])):
        raise ValueError("lod.ratios must be strictly decreasing")
    lod_names = [f"{source.name}_LOD{i}" for i in range(1, len(ratios) + 1)]
    existing = [bpy.data.objects.get(name) for name in lod_names]
    for old in existing:
        if old is not None and (old.type != "MESH" or old.get(LOD_OWNER) != source.name):
            raise ValueError(f"Refusing to replace existing object {old.name}")
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = source.evaluated_get(depsgraph)
    original = tris(evaluated.data)
    last = original
    staged = []
    collection = source.users_collection[0]
    for ratio, name in zip(ratios, lod_names):
        data = bpy.data.meshes.new_from_object(evaluated, preserve_all_data_layers=True, depsgraph=depsgraph)
        obj = bpy.data.objects.new(name, data)
        collection.objects.link(obj)
        obj.matrix_world = source.matrix_world.copy()
        obj[LOD_OWNER] = source.name
        selection([obj])
        decimate = obj.modifiers.new("LOD Decimate", "DECIMATE")
        decimate.ratio = ratio
        decimate.use_collapse_triangulate = True
        if bpy.ops.object.modifier_apply(modifier=decimate.name) != {"FINISHED"}:
            raise RuntimeError(f"Could not decimate {name}")
        count = tris(obj.data)
        if not 0 < count < last:
            raise ValueError(f"{name} has {count} triangles versus {last} at the preceding level; choose different ratios")
        staged.append((obj, ratio, count))
        last = count
    for old, name, (obj, _, _) in zip(existing, lod_names, staged):
        if old is not None:
            bpy.data.objects.remove(old, do_unlink=True)
        obj.name = name
        obj.data.name = name
        obj.hide_set(True)
        obj.hide_render = True
    selection([source])
    return [{"name": source.name, "triangles": original, "ratio": 1.0}, *[
        {"name": obj.name, "triangles": count, "ratio": ratio} for obj, ratio, count in staged
    ]]


def collision_meshes(source, options):
    objects = [mesh(name) for name in names(options, "unreal.collision")]
    pattern = re.compile(rf"(?:UCX|UBX|USP|UCP)_{re.escape(source.name)}(?:_\d+)?$")
    for obj in objects:
        if not pattern.fullmatch(obj.name):
            raise ValueError(f"Collision object {obj.name} must use the target mesh name and a UE collision prefix")
        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            if not all(edge.is_manifold for edge in bm.edges) or abs(bm.calc_volume()) < 1e-10:
                raise ValueError(f"Collision object {obj.name} must be a closed volume")
            volume = abs(bm.calc_volume())
            hull = bmesh.ops.convex_hull(bm, input=list(bm.verts), use_existing_faces=False)
            faces = {item for item in hull["geom"] if isinstance(item, bmesh.types.BMFace)}
            if not faces:
                raise ValueError(f"Could not construct a convex hull for {obj.name}")
            hull_mesh = bmesh.new()
            try:
                unique = {vert for face in faces for vert in face.verts}
                verts = {vert: hull_mesh.verts.new(vert.co) for vert in unique}
                for face in faces:
                    hull_mesh.faces.new([verts[vert] for vert in face.verts])
                if not math.isclose(volume, abs(hull_mesh.calc_volume()), rel_tol=0.005, abs_tol=1e-10):
                    raise ValueError(f"Collision object {obj.name} must be convex")
            finally:
                hull_mesh.free()
        finally:
            bm.free()
    return objects


def write_fbx(destination, objects, skeletal=False, animation=False):
    if not hasattr(bpy.ops.export_scene, "fbx"):
        raise RuntimeError("The Blender FBX exporter is unavailable")
    hidden = [(obj, obj.hide_get()) for obj in objects]
    selection(objects)
    try:
        result = bpy.ops.export_scene.fbx(
            filepath=str(destination), use_selection=True, object_types={"MESH", "ARMATURE"},
            apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS", axis_forward="-Z", axis_up="Y",
            mesh_smooth_type="FACE", use_triangles=True, use_tspace=True, use_mesh_modifiers=not skeletal,
            add_leaf_bones=False, use_armature_deform_only=skeletal, armature_nodetype="NULL",
            bake_anim=animation, bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False,
        )
    finally:
        for obj, hide in hidden:
            obj.hide_set(hide)
    with destination.open("rb") as handle:
        if result != {"FINISHED"} or not handle.read(23).startswith(b"Kaydara FBX Binary"):
            raise RuntimeError(f"FBX exporter did not write a valid binary header: {destination.name}")


def export_clips(output, objects, armature, actions):
    clips_dir = output / "clips"
    clips_dir.mkdir()
    scene = bpy.context.scene
    animation = armature.animation_data_create()
    previous = (animation.action, animation.use_nla, scene.frame_start, scene.frame_end, scene.frame_current)
    files = []
    try:
        animation.use_nla = False
        for index, name in enumerate(actions, start=1):
            action = bpy.data.actions.get(name)
            if action is None:
                raise ValueError(f"Unknown action: {name}")
            animation.action = action
            if hasattr(action, "slots") and not animation.action_slot:
                slots = list(animation.action_suitable_slots)
                if len(slots) != 1:
                    raise ValueError(f"Choose an unambiguous armature action for {name}")
                animation.action_slot = slots[0]
            start, stop = action.frame_range
            scene.frame_start, scene.frame_end = math.floor(start), math.ceil(stop)
            scene.frame_set(scene.frame_start)
            safe = re.sub(r"[^A-Za-z0-9_-]+", "_", name)[:60]
            destination = clips_dir / f"{index:02d}_{safe}.fbx"
            write_fbx(destination, objects, skeletal=True, animation=True)
            files.append({"action": name, "file": str(destination), "frames": [start, stop]})
    finally:
        animation.action, animation.use_nla, scene.frame_start, scene.frame_end, frame = previous
        scene.frame_set(frame)
    return files


def export_unreal(source, output, options):
    check_keys(options, ("preset", "armature", "animation", "clips", "collision", "lods"))
    preset = options.get("preset", "static")
    if preset not in ("static", "skeletal"):
        raise ValueError("unreal.preset must be static or skeletal")
    skeletal = preset == "skeletal"
    lods = [mesh(name) for name in names(options.get("lods", []), "unreal.lods")]
    collision = collision_meshes(source, options.get("collision", []))
    if len(set([source, *lods, *collision])) != 1 + len(lods) + len(collision):
        raise ValueError("The base mesh, LODs and collision meshes must be distinct")
    objects = [source, *collision]
    if skeletal:
        armature = next((obj for obj in bpy.context.view_layer.objects if obj.name == options.get("armature")), None)
        if not armature or armature.type != "ARMATURE":
            raise ValueError("Skeletal FBX requires unreal.armature naming the active rig")
        if lods or collision or not any(mod.type == "ARMATURE" and mod.object == armature for mod in source.modifiers):
            raise ValueError("Skeletal FBX needs a bound mesh; this preset expects a base skeletal asset")
        objects.append(armature)
    elif {"armature", "animation", "clips"} & options.keys():
        raise ValueError("unreal.armature, unreal.animation and unreal.clips require preset=skeletal")
    animation = options.get("animation", False)
    clips = names(options.get("clips", []), "unreal.clips")
    if type(animation) is not bool:
        raise ValueError("unreal.animation must be a boolean")
    base = output / (source.name + ".fbx")
    write_fbx(base, objects, skeletal, animation and not clips)
    clip_files = export_clips(output, objects, armature, clips) if clips else []
    files = []
    for index, obj in enumerate(lods, start=1):
        dest = output / f"{source.name}_LOD{index}.fbx"
        write_fbx(dest, [obj], False)
        files.append({"level": index, "file": str(dest), "object": obj.name})
    return {"preset": preset, "base": str(base), "lods": files, "clips": clip_files, "collision": [obj.name for obj in collision],
            "bounds_m": [round(value * bpy.context.scene.unit_settings.scale_length, 6) for value in source.dimensions]}


def run(recipe, output, options):
    if recipe not in RECIPES:
        raise ValueError(f"Unknown asset recipe {recipe!r}")
    sections = {"bake_maps": ("bake",), "make_lods": ("lod",), "export_unreal": ("unreal",),
                "prepare_unreal": ("bake", "lod", "unreal")}[recipe]
    check_keys(options, ("low", *sections, *(("qa",) if "unreal" in sections else ())))
    source = mesh(options.get("low"))
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,54}", source.name):
        raise ValueError("Name the source mesh with up to 55 ASCII alphanumeric, underscore or hyphen characters")
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    output.mkdir(parents=True, exist_ok=False)
    result = {"ok": True, "recipe": recipe, "source": source.name, "blender": bpy.app.version_string}
    if "unreal" in sections:
        result["gate"] = delivery_gate(source, output)["verdict"]
        if "qa" in options:
            if bpy.app.version < (5, 2, 0):
                raise ValueError("Extended delivery QA needs Blender 5.2 or newer")
            result["qa"] = extended_delivery(source, output, options["qa"])
    if "bake" in sections:
        baked = bake_maps(source, output, options.get("bake", {}))
        result["textures"] = baked
        if recipe == "prepare_unreal":
            result["material"] = baked_material(source, baked)
    if "lod" in sections:
        result["lods"] = make_lods(source, options.get("lod", {}))
    if "unreal" in sections:
        settings = options.get("unreal", {}).copy()
        if recipe == "prepare_unreal":
            settings["lods"] = [row["name"] for row in result["lods"][1:]]
        result["unreal"] = export_unreal(source, output, settings)
    if "lod" in sections:
        for row in result["lods"][1:]:
            mesh(row["name"]).hide_set(True)
        selection([source])
        snapshot = output / (source.name + ".blend")
        if bpy.ops.wm.save_as_mainfile(filepath=str(snapshot), copy=True) != {"FINISHED"}:
            raise RuntimeError("Could not save the asset .blend copy")
        result["blend"] = str(snapshot)
    (output / "asset-report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    recipe_arg, directory_arg, options_arg = sys.argv[sys.argv.index("--") + 1:]
    print("HEADLESS " + json.dumps(run(recipe_arg, Path(directory_arg), json.loads(options_arg))), flush=True)
