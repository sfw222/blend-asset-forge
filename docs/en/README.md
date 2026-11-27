# Blend Asset Forge

[简体中文](../../README.md)

Use Codex to build assets from reference images in Blender. Review each revision from the same camera angles. For game props, you can also bake textures, build LODs, and export static FBX files for Unreal.

## Install

Source builds require Node.js **24.9** or newer. The Blender bridge installs on Blender 4.2 or newer. The workflow below was tested with Blender 5.2.3. The extended production recipes require Blender 5.2 or newer.

1. Run these commands from the repository root:

   ```sh
   npm ci --legacy-peer-deps
   npm run build
   ```

2. In Blender, open **Edit → Preferences → Extensions → Install from Disk** and install [blend_asset_forge_bridge.zip](../../extension/blend_asset_forge_bridge.zip). Enable **Blend Asset Forge Bridge** after installation. Disable any other agent bridge for Blender first.
3. Register the local MCP server. Replace the example path with your checkout path:

   ```sh
   codex mcp add blender-assets -- node "/path/to/blend-asset-forge/lib/mcp/index.js"
   ```

   If Blender cannot be found, add `--env "DSH_BLENDER_EXE=/path/to/blender"` before `--`.
4. In a new Codex chat, call `blender_session(action="status")` to start the local Gateway. Press **N** in the Blender 3D Viewport and click **Connect** in the **Blend Asset Forge Bridge** panel. Back in Codex, run `doctor` and then `attach` once it returns `kind=ok`.

For headless work, submit a job with `blender_run`, then use `wait` and `collect` to retrieve the results. See the [configuration reference](../配置参考.md).

## Build an asset

1. **Set dimensions and block out the model.** Give Codex the original reference, intended use, construction, and known dimensions. Set design dimensions if the image has no scale. Check the silhouette and proportions in Blender. See the [Blender modeling skill](../../skills/blender-modeling/SKILL.md).
2. **Review from fixed views.** Use `blender_see` with `views` for up to six images per call. Add `review` to save PNGs and `review.json` for each round. Keep the same reference and viewpoints. Fix the silhouette and proportions first, then check seams, materials, and details.
3. **Check and save.** Inspect the mesh, UVs, materials, units, and pivot before saving the source `.blend`. Use `blender_run(action="asset_catalog")` to find the relevant checks and recipes.
4. **Export an Unreal static mesh.** Submit `prepare_unreal` through `blender_run`. It runs the delivery checks, bakes textures, builds LODs, and exports the FBXs. Use the job ID with `wait` and `collect` to get the report and outputs. FBX reimport was tested in Blender. Check the import separately in the target Unreal project.

- [Multi-view review and Unreal export](../../skills/blender-modeling/references/reference-review-and-unreal.md)
- [Production recipes and parameters](../../skills/blender-modeling/references/production-recipes.md)
- [Blender bridge troubleshooting](../../extension/README.md)

For the original DSH setup, see the [DSH guide](../操作教程.md) (Chinese).

## Development

Use Node.js **24.9** or newer. Python tests need a venv with pytest. Set `PYTHON` to the interpreter path. See [AGENTS.md](../../AGENTS.md#1-commands-single-source) for build and test commands and [CONTRIBUTING.md](../../CONTRIBUTING.md) for the contribution process. See the [architecture guide](../architecture.md) for the repository layout.

## Credits and licenses

Based on [DSH Blender Plugin](https://github.com/sixtysevenlf/dsh-blender-plugin). The reference review workflow draws on [dream-loop](https://github.com/achimala/dream-loop), and some of the asset recipes come from [blender-skills](https://github.com/EL4CTEO/blender-skills).

- Host and runtime code: [BSD-3-Clause](../../LICENSE).
- Blender bridge: [GPL-3.0-or-later](../../extension/LICENSE), with the [MIT notice](../../extension/NOTICE) for code from `blender-mcp`.
- Bundled modeling skills and production scripts: MIT. See the [third-party notices](../../skills/blender-modeling/NOTICE.md) for copyrights, licenses, and upstream revisions.

The npm package ships these components together and lists all three licenses in its SPDX expression. The licenses apply to the components listed above.
