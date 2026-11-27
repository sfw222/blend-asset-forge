# Blender 作业模板 · Production recipes

用 `blender_run(action="asset_catalog")` 查询本仓作业模板、参数和最低 Blender 版本。这个调用显示目录。实际执行用 `blender_run(action="submit", kind="headless")`，之后用返回的 `job.id` 调 `wait` 和 `collect`。指定现有场景时用 `file` 传绝对 `.blend` 路径。新建场景和目录批处理可以省略 `file`。传入的场景不会原地保存，所有报告和输出写入 `outdir/<jobId>`。

Use `blender_run(action="asset_catalog")` for recipe names, parameters, and Blender requirements. Submit with `kind="headless"`, `asset_recipe`, `asset_options` and an absolute `outdir`. Pass an absolute `.blend` as `file` when a scene is needed. Recipes save outputs to `outdir/<jobId>`, with a structured `asset-report.json`. Mutating recipes save a separate `result.blend` unless `save_blend=false`. Set `enforce=true` to fail the job when the recipe reports a failed check.

| 用途 / Purpose | 作业模板 / Recipes |
| --- | --- |
| UV、材质和预算 / UV, materials, budgets | `uv_pack`, `texel_density`, `qa_check`, `mesh_stats`, `scene_audit` |
| 顶点和材质制作 / Modeling and shading | `auto_retopo`, `apply_stack`, `sculpt_ops`, `build_pbr_material`, `decal`, `smart_material` |
| 视觉质检 / Visual QA | `review_shots`, or fixed custom MCP views with `review` |
| 骨骼与动画 / Rigging and animation | `rig_check`, `loop_check`, `bake_action`, `retarget`, `bind_mesh`, `rigify_build`, `stress_poses`, `shapekeys` |
| 角色部件 / Character specialization | `garment`, `groom` |
| 模块与场景 / Procedural environments | `gn_builder`, `kit_check`, `terrain`, `scatter` |
| 批处理与交付 / Batch and delivery | `batch_process`, `export_asset`, plus `bake_maps`, `make_lods`, `export_unreal`, `prepare_unreal` |
| 渲染、效果及制片 / Render, FX, production | `turntable`, `render_batch`, `scene_mood`, `toon_setup`, `sim_setup`, `surface_weather`, `precipitation`, `lightning`, `vse_edit`, `track_camera` |
| 环境诊断 / Diagnostics | `env_report` |

按参考图做 Unreal 静态道具时，先看[建模返修与交付示例](reference-review-and-unreal.md)。这里按需要查单项制作工具。

For an Unreal static prop, start with the [reference review and delivery example](reference-review-and-unreal.md). This page lists recipes you can run individually.

## 提交示例 / Job example

```json
{
  "action": "submit",
  "kind": "headless",
  "asset_recipe": "texel_density",
  "file": "F:/assets/chair.blend",
  "outdir": "F:/assets/working",
  "asset_options": {"objects": ["SM_Chair"], "res": 1024, "save_blend": false}
}
```

Recipe options named `out`, `save_to`, `export_points`, `export_heightmap` and `export_splat` are job-relative. For scatter/terrain, pass `true` to choose the default filename. Batch inventory and conversion accept paths under `inp`. Batch `op="script"` uses the name of a bundled headless recipe, with its arguments in `kwargs`. The job fails when conversion inputs would overwrite one another by basename. `track_camera` uses a temporary Blender window for Clip Editor operations, then the queued process exits.

作业模板的输出路径相对于作业目录。地形和散布的导出参数接受 `true` 以使用默认文件名。批处理的 `op="script"` 接受本仓内置作业模板名，作业模板参数传入 `kwargs`。不同来源的同名文件会拦截批量覆盖。相机跟踪由队列启动临时 Blender 窗口运行 Clip Editor，完成后退出。

## 视觉返修 / Visual revisions

把这段 `review` 配置并入同一次 `blender_see` 调用。同一次调用中的 `views` 必须全是固定的 `custom` 机位，每个机位有 `from` 和 `look_at`。

```json
{
  "review": {
    "directory": "F:/assets/reviews/chair",
    "reference": "F:/assets/references/chair.png",
    "defects": ["backrest too low"],
    "changes": ["raise backrest by 30 mm"],
    "verdict": "degraded"
  }
}
```

Each round records PNGs and a `review.json` receipt. Reuse the exact custom viewpoints and original reference for comparable iterations. A defect repeated verbatim from the previous round is reported to the reviewer. Check camera or modeling strategy when the same difference persists. A failed capture makes the round degraded. The receipt records the supplied human or model verdict, alongside existing geometric checks such as `visualreport_report`.

每轮保存独立的 PNG 和回执。用同一组自定义机位和原参考图复拍。上一轮和本轮写法完全相同的缺陷会在回执提示。截图失败时该轮会标记为降级。视觉判断与主仓的几何和尺寸比较配合使用。

## 扩展交付门与动作 / Extended delivery QA and clips

For `export_unreal` and `prepare_unreal`, optional `asset_options.qa` adds checks before export. Fields include `profile`, `max_tris`, `budget`, percentage `overlap_limit`, `allow_outside_uv`, `armature`, and `influence_limit`. UV overlap is an estimate. Leave overlap and tile restrictions unset when the asset intentionally stacks UVs or uses multiple tiles. For skeletal exports, `unreal.clips` accepts action names and writes one FBX per clip. Use `unreal.animation=true` for the current timeline.

现有交付门可用 `asset_options.qa` 加上贴图、几何、预算和权重检查。重叠率是近似值，计划使用镜像叠放或 UDIM 时可保留相应自由度。骨骼导出通过 `unreal.clips` 指定动作名，每段输出一个 FBX。

## 可选 Fal 资产提供方 / Optional Fal provider

`blender_run(action="asset_provider", op="check", file="<absolute manifest.json>")` validates local images offline. Each entry has `id`, `endpoint`, `image`, `output`, and optional `input` inside a `jobs` array. `submit` requires `allow_upload=true` and `FAL_KEY` or `FAL_API_KEY`; it sends the chosen images to Fal. `collect` resumes from persisted IDs and verifies downloaded GLB files. Keep uncertain requests in the manifest until reconciled, since creating a replacement request can incur another charge. Import collected models into Blender and run the same QA and retopology steps.

Fal 的 `check` 在本地检查图片与清单。经用户允许的 `submit` 需要显式设置 `allow_upload=true` 和凭据。通过 `collect` 续查已有请求并验证下载的 GLB。不确定是否已受理时保留原记录，再用 Blender 检查和处理下载模型。
