---
name: blender-asset-pipeline
description: Use the repository's Codex Blender MCP for reference-driven modeling, multi-angle visual review, and game asset baking, LODs or Unreal FBX delivery.
---

# Blender asset pipeline

Use the `blender-assets` MCP server with this checkout's DSH Blender Bridge. Confirm `blender_session(action="doctor")` reports `kind=ok` and attach to the intended Blender session before editing. Discover named operations with `blender_op(op="catalog")`.

For visual matching or game asset delivery, read [Reference review and Unreal asset recipes](../../../skills/blender-modeling/references/reference-review-and-unreal.md). For other modeling operations, use the relevant recipe or reference from [the bundled modeling guide](../../../skills/blender-modeling/SKILL.md).

For UV and texture QA, retopology, rigging, animation, batch export, procedural scenes or production, call `blender_run(action="asset_catalog")` and read [Production recipes](../../../skills/blender-modeling/references/production-recipes.md).
