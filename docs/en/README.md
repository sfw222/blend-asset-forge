# Blend Asset Forge

[简体中文](../../README.md)

Use Codex to build assets from reference images in Blender. Review each revision from the same camera angles. For game props, you can also bake textures, build LODs, and export static FBX files for Unreal.

## Install

Source builds require Node.js **24.9** or newer. The Blender bridge requires Blender 4.2 or newer. The asset recipes were tested with Blender 5.2.

1. Run these commands from the repository root:

   ```sh
   npm ci --legacy-peer-deps
   npm run build
   ```

2. In Blender, open **Edit → Preferences → Extensions → Install from Disk** and install [dsh_blender_bridge.zip](../../extension/dsh_blender_bridge.zip). Press **N** in the 3D Viewport, open the **DSH Blender Bridge** panel, and click **Connect**. Disable any other agent bridge for Blender first.
3. Register the local MCP server. Replace the example path with your checkout path:

   ```sh
   codex mcp add blender-assets -- node "/path/to/blend-asset-forge/lib/mcp/index.js"
   ```

   If Blender cannot be found, add `--env "DSH_BLENDER_EXE=/path/to/blender"` before `--`.
4. Start a new Codex chat and run `doctor` through `blender_session`. When it returns `kind=ok`, use `attach` to connect to the Blender session.

For headless work, submit a job with `blender_run`, then use `wait` and `collect` to retrieve the results. See the [configuration reference](../配置参考.md).

## Build an asset

1. **Model.** Give Codex the reference, dimensions, and intended use. See the [Blender modeling skill](../../skills/blender-modeling/SKILL.md) for the workflow.
2. **Review.** Fetch up to six images per call with `blender_see`. Use the same viewpoints for each revision. Check the silhouette and proportions first, then look at materials, seams, and details.
3. **Prepare for delivery.** Use `blender_run(action="asset_catalog")` to find recipes for UV checks, retopology, materials, rigging, and animation. Run baking, LOD generation, and Unreal export individually or use `prepare_unreal` to run them in order.

- [Multi-view review and Unreal export](../../skills/blender-modeling/references/reference-review-and-unreal.md)
- [Production recipes and parameters](../../skills/blender-modeling/references/production-recipes.md)
- [Blender bridge troubleshooting](../../extension/README.md)

For the original DSH setup, see the [DSH guide](../操作教程.md) (Chinese).

## Development

Use Node.js **24.9** or newer. Python tests need a venv with pytest. Set `PYTHON` to the interpreter path. See [AGENTS.md](../../AGENTS.md#1-commands-single-source) for build and test commands and [CONTRIBUTING.md](../../CONTRIBUTING.md) for the contribution process.

## Credits and licenses

Based on [DSH Blender Plugin](https://github.com/sixtysevenlf/dsh-blender-plugin). The reference review workflow draws on [dream-loop](https://github.com/achimala/dream-loop), and some of the asset recipes come from [blender-skills](https://github.com/EL4CTEO/blender-skills).

- Host and runtime code: [BSD-3-Clause](../../LICENSE).
- Blender bridge: [GPL-3.0-or-later](../../extension/LICENSE), with the [MIT notice](../../extension/NOTICE) for code from `blender-mcp`.
- Bundled modeling skills and production scripts: MIT. See the [third-party notices](../../skills/blender-modeling/NOTICE.md) for copyrights, licenses, and upstream revisions.
