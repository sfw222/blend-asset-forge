"""Exercise the integrated Blender scripts with the pinned upstream fixture suite."""

import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import traceback


def module_from(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def exercise(upstream, output):
    root = Path(__file__).resolve().parents[3]
    output.mkdir(parents=True, exist_ok=False)
    os.environ["TEMP"] = str(output)
    os.environ["TMP"] = str(output)
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(upstream / "tests"))
    import run_all

    workflows = module_from("dsh_workflows", root / "runtime/py/export/game_asset_impl/workflows.py")
    library = workflows.LIBRARY
    previous = run_all.skill_module
    seen = {name: 0 for name in workflows.RECIPES}
    touched = set()

    def skill_module(skill, name):
        if name not in seen:
            return previous(skill, name)
        module = workflows.load_recipe(name)
        execute = module.run

        def observed(*args, **kwargs):
            result = execute(*args, **kwargs)
            touched.add(name)
            return result

        module.run = observed
        return module

    run_all.skill_module = skill_module
    results = []
    for file in sorted(run_all.HERE.glob("test_*.py")):
        if file.stem == "test_addon":
            # The upstream template is outside the runtime and its test deletes files.
            continue
        if file.stem == "test_video":
            text = file.read_text(encoding="utf-8")
            old = 'HERE.parent / "skills" / "blender-video-editing" / "scripts"'
            assert old in text
            namespace = {"__file__": str(file), "__name__": "test_video"}
            exec(compile(text.replace(old, "pathlib.Path(" + repr(str(library)) + ")"), str(file), "exec"), namespace)
        else:
            namespace = vars(module_from(file.stem, file))
        for name, fun in sorted(namespace.items()):
            if not name.startswith("test_") or not callable(fun):
                continue
            run_all.fresh()
            touched.clear()
            started = time.monotonic()
            result = {"test": f"{file.stem}::{name}"}
            try:
                fun()
                if name == "test_track_camera_solves_in_ui_session":
                    touched.add("track_camera")
                for recipe in touched:
                    seen[recipe] += 1
                result.update(status="pass", recipes=sorted(touched))
            except Exception:
                result.update(status="fail", detail=traceback.format_exc())
            result["seconds"] = round(time.monotonic() - started, 3)
            results.append(result)
            print(result["status"].upper(), result["test"], flush=True)
    missing = [name for name, count in seen.items() if not count]
    failures = [result["test"] for result in results if result["status"] == "fail"]
    report = {"blender": __import__("bpy").app.version_string, "passed": len(results) - len(failures),
              "failures": failures, "untested": missing, "recipe_checks": seen, "cases": results,
              "fixture_artifacts": str(run_all.TMP)}
    (output / "blender-recipes.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("blender", "passed", "failures", "untested")}), flush=True)
    if missing or failures:
        raise RuntimeError("Integrated Blender acceptance failed")


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:]
    exercise(*[Path(arg).resolve() for arg in args])
