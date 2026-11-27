"""Dispatch bundled Blender production scripts in an isolated job directory."""

import importlib.util
import json
import os
from pathlib import Path
import sys
import traceback

import bpy

LIBRARY = Path(__file__).resolve().parents[3] / "ext" / "blender-skills"
CATALOG = json.loads((LIBRARY / "recipes.json").read_text(encoding="utf-8"))
RECIPES = CATALOG["recipes"]
OUTPUTS = {
    "review_shots": {"out": "review.png"},
    "groom": {"out": "hair"},
    "render_batch": {"out": "render/frame_####"},
    "vse_edit": {"out": "sequence.mp4"},
    "terrain": {"export_heightmap": "heightmap.png", "export_splat": "splat.png"},
    "scatter": {"export_points": "points.json"},
    "batch_process": {"out": "exports", "save_to": "scenes"},
}
READ_ONLY = {"env_report", "qa_check", "mesh_stats", "review_shots", "render_batch", "export_asset"}


def output_path(root, value):
    target = Path(value)
    if target.is_absolute() or target.drive or target.anchor:
        raise ValueError("Recipe output paths must be relative to the job directory")
    full = (root / target).resolve()
    if full == root or not full.is_relative_to(root):
        raise ValueError("Recipe outputs must remain in the job directory")
    full.parent.mkdir(parents=True, exist_ok=True)
    return str(full)


def load_recipe(name):
    if name not in RECIPES:
        raise ValueError(f"Unknown bundled Blender recipe: {name!r}")
    path = LIBRARY / (name + ".py")
    spec = importlib.util.spec_from_file_location("_dsh_recipe_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def options_for(name, raw, output):
    if not isinstance(raw, dict):
        raise ValueError("Recipe options must be a JSON object")
    unknown = raw.keys() - set(RECIPES[name]["options"])
    if unknown:
        raise ValueError(f"Unrecognized options for {name}: {', '.join(sorted(unknown))}")
    options = dict(raw)
    for key, default in OUTPUTS.get(name, {}).items():
        value = options.get(key)
        if value is False and key == "out":
            raise ValueError("out must be an output path relative to the job directory")
        if value is False or (key.startswith("export_") and value is None) or (key == "save_to" and value is None):
            options.pop(key, None)
            continue
        options[key] = output_path(output, default if value is None or value is True else value)
    return options


def batch_options(options, output):
    module = load_recipe("batch_process")
    if options.get("op", "report") not in {"report", "convert", "script"}:
        raise ValueError("batch_process op must be report, convert or script")
    if not options.get("inp"):
        raise ValueError("batch_process needs an input directory, file or pattern")
    files = module.gather(options["inp"])
    if not files:
        raise ValueError("No files matched batch_process input")
    name_keys = [Path(file).stem.casefold() for file in files]
    if options.get("op") == "convert" and len(set(name_keys)) != len(name_keys):
        raise ValueError("Input files with identical basenames would overwrite batch outputs")
    if options.get("op") == "script":
        name = options.get("script")
        if name not in RECIPES or name in {"batch_process", "track_camera", "export_asset"} or name in OUTPUTS:
            raise ValueError("Batch script must name a bundled headless recipe without file outputs")
        if options.get("save_to") and len(set(name_keys)) != len(name_keys):
            raise ValueError("Input files with identical basenames would overwrite .blend outputs")
        options["script"] = str(LIBRARY / (name + ".py"))
        options["kwargs"] = options_for(name, options.get("kwargs", {}), output)
    elif options.get("script"):
        raise ValueError("script requires batch_process op=script")
    return module


def run_workflow(name, output, raw):
    if name not in RECIPES:
        raise ValueError(f"Unknown asset recipe {name!r}")
    minimum = tuple(CATALOG["min_blender"])
    if bpy.app.version < minimum:
        raise ValueError(f"{name} needs Blender {'.'.join(map(str, minimum))}+; found {bpy.app.version_string}")
    if not isinstance(raw, dict):
        raise ValueError("asset_options must be a JSON object")
    inputs = dict(raw)
    save = inputs.pop("save_blend", name not in READ_ONLY and name != "batch_process")
    enforce = inputs.pop("enforce", False)
    if type(save) is not bool or type(enforce) is not bool:
        raise ValueError("save_blend and enforce must be booleans")
    output.mkdir(parents=True, exist_ok=False)
    options = options_for(name, inputs, output)
    module = batch_options(options, output) if name == "batch_process" else load_recipe(name)
    if name == "export_asset":
        if options.get("batch"):
            export_objects = module._gather(options.get("objects"), options.get("collection"))
            if any(Path(obj.name).name != obj.name or ":" in obj.name or "\\" in obj.name for obj in export_objects):
                raise ValueError("Batch-export object names must be valid file names")
        fmt = module.PRESETS[options.get("preset", "gltf")][0]
        options["out"] = output_path(output, options.get("out") or ("asset" + module.EXT[fmt]))
    result = module.run(**options)
    if not isinstance(result, dict):
        raise RuntimeError(f"{name} did not return a structured result")
    report = {"ok": result.get("ok", True) and result.get("pass", True), "recipe": name,
              "blender": bpy.app.version_string, "result": result}
    if name == "mesh_stats" and isinstance(result.get("budget"), dict):
        report["ok"] = result["budget"]["pass"]
    if name == "track_camera":
        report["ok"] = bool(result.get("solved"))
    if save and report["ok"]:
        target = output / "result.blend"
        if bpy.ops.wm.save_as_mainfile(filepath=str(target), copy=True) != {"FINISHED"}:
            raise RuntimeError("Blender did not save the recipe output")
        report["blend"] = str(target)
    (output / "asset-report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    if enforce and not report["ok"]:
        raise ValueError(f"{name} did not pass; see {output / 'asset-report.json'}")
    return report


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    name, directory, encoded = sys.argv[sys.argv.index("--") + 1:]

    def execute():
        result = run_workflow(name, Path(directory).resolve(), json.loads(encoded))
        print("HEADLESS " + json.dumps(result, default=str), flush=True)

    def execute_window():
        try:
            execute()
            bpy.context.preferences.view.use_save_prompt = False
            bpy.ops.wm.quit_blender()
        except Exception:
            traceback.print_exc()
            sys.stderr.flush()
            os._exit(1)

    if bpy.app.background:
        execute()
    else:
        bpy.app.timers.register(execute_window, first_interval=0.2)
