# `dsh_blender_bridge` — the Blender-side extension bundled with this repository

The Blender-side add-on for the [`dsh-blender-plugin`](../README.md) host plugin.

**English** | [中文](README.zh.md)

> **Since 3.1 the Blender side is a Blender 4.2 Extension package.** The zip has a single top-level
> `dsh_blender_bridge/` directory containing `blender_manifest.toml`; the legacy single-file
> `dsh_blender_bridge.py` installer is gone. Stop and remove any legacy copy in Blender first, then
> install `blend_asset_forge_bridge.zip` (see [`../MIGRATIONS.md`](../MIGRATIONS.md)). Upstream
> `MCP for Blender` (module `blender_mcp`) and `blender_mcp_addon` are not supported either.

This extension ships with [Blend Asset Forge](../docs/en/README.md). Codex connects through the local Gateway started by the `blender-assets` MCP server.

## What this package is

| Item | Value |
|---|---|
| Package / module | `blend_asset_forge_bridge.zip` (package root `dsh_blender_bridge/`, with `blender_manifest.toml`) / `dsh_blender_bridge` |
| Source directory | `extension/dsh_blender_bridge/` (`__init__.py` is the entry; subpackages `commands/`, `recorders/`, `assets/`, `integrations/`, `ui/`) |
| Display name | **Blend Asset Forge Bridge** |
| Version / protocol | extension **v2.0.0 / protocol 12** |
| Identifier prefix | `dshbb_` (registered type `bpy.types.dshbb_server`, five `dshbb_use_*` integration switches) |
| Transport | Gateway `127.0.0.1:39877`; the extension dials the Gateway and never listens for inbound connections |
| Command surface | 25 registered commands (18 always-on + 7 integration-gated); see MIGRATIONS for the 3.0 -> 3.1 breaking changes |

## Source and license (GPL-3.0-or-later, upstream MIT)

The bridge comes from DSH Blender Plugin and includes MIT-licensed code from
[ahujasid/blender-mcp](https://github.com/ahujasid/blender-mcp). It connects to the local Gateway.
The upstream copyright and MIT notice are preserved. The extension is distributed under **GPL-3.0-or-later** (see the
`license` field in `blender_manifest.toml`, [`LICENSE`](LICENSE), and [`NOTICE`](NOTICE)).

```
# Code created by Siddharth Ahuja: www.github.com/ahujasid © 2025
```

The upstream MIT license requires keeping that copyright line. Both the full GPL text
(`extension/LICENSE`) and the upstream MIT notice (`extension/NOTICE`) are copied into the extension
zip at its package root; the DSH host plugin itself remains BSD-3-Clause (root `LICENSE`).

## Build the zip

The repository commits `extension/blend_asset_forge_bridge.zip`; rebuild it after changing the sources:

```bash
node scripts/build-extension.mjs          # write extension/blend_asset_forge_bridge.zip
node scripts/build-extension.mjs --check  # verify the existing zip manifest and versions only
```

The zip contains one package root (`dsh_blender_bridge/`) with `blender_manifest.toml`, `LICENSE`,
`NOTICE` and every `.py` module; it contains no `__pycache__` / `.pyc` files and uses fixed timestamps
so the bytes are reproducible. The build also checks that the manifest, `gateway_schema.py` and
`config/gateway.json` versions agree. To validate the archive in Blender, run `blender --command extension validate extension/blend_asset_forge_bridge.zip` from the repository root.

## Install

1. In Blender open `Edit ▸ Preferences ▸ Extensions ▸ Install from Disk...` and choose
   `extension/blend_asset_forge_bridge.zip` (an extension package, not the directory and not a single `.py`).
   - Disable other Blender agent bridges first. If an older copy of this extension blocks installation, remove that copy in Blender.
2. Enable **Blend Asset Forge Bridge**. Follow the [setup instructions](../docs/en/README.md#install) to register `blender-assets`, then call `blender_session(action="status")` in Codex to start the Gateway.
3. Press `N` in the Blender 3D Viewport, open **Blend Asset Forge Bridge**, and click **Connect**. The default Gateway address is `127.0.0.1:39877`.

When using DSH, the DSH host starts the Gateway.

## Verify

In Codex, run `blender_session(action="doctor")` and use `attach` once it returns `kind=ok`. If the connection fails, check that the Gateway is running, the extension is enabled and connected, and the ports match. Once connected, you can check the version and activity state:

```bash
blender_inspect(command="get_addon_info")     # addon_version should be [2, 0, 0], protocol_version 12
blender_inspect(command="get_activity_state") # idle / human / agent / both
```

With the DSH host, selecting an object in Blender after installation and pressing `N` shows the **Selection -> DSH** control;
sending puts the selection into the **current DSH session draft** (it does not auto-send). Edit-mode
vertex/edge/face, pose-mode bone and curve/lattice control-point selections are included under
`selection.sub`. The object/member lists start collapsed and scroll when expanded.

The activity panel is pinned on top (a red warning appears while the agent operates) with a
**Pause AI operations** button. The environment/model-generation parent panels
(Poly Haven / Sketchfab / Poly Pizza; Hyper3D / Hunyuan3D) start collapsed. While paused, the socket only
lets read-only commands through.

## Environment variables (legacy names still work)

New names win, old names fall back: `DSHBB_HYPER3D_API_KEY` -> `BLENDERMCP_HYPER3D_API_KEY`, and the
same for `SKETCHFAB` / `POLYPIZZA` / `HUNYUAN3D_*`. Existing legacy variables keep working (key-name
compatibility only; legacy add-ons are still unsupported).
