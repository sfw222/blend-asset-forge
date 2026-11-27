# 参考图返修与 UE 资产作业模板 · Reference review and Unreal asset recipes

从[首页安装步骤](../../../README.md#安装)连接 Codex 和 Blender，再按下面的顺序做。This workflow starts from an attached Blender session. See the [English setup guide](../../../docs/en/README.md#install).

## 参考图返修

1. 固定用户给的参考图和要求。没有参考图时，可为原创工作生成概念图。用 `img_digest` 记下能确定的比例和特征，单张无标定图的尺寸注明为设计假设。
2. 用白模解决大形。保存一套主视角、正面和侧面机位。Codex 可一次调用 `blender_see` 的 `views`，DSH 下对相同机位逐张调用。保留每轮可对照的图。
3. 对比剪影、比例、结构、材质。记录具体差异、修改对象和预期变化。匹配摄影图时先核对机位和透视。需要计量时，在对齐的机位用 `visualreport_report` 量轮廓和缺陷。独立视觉复核可用时，提供原图、同机位图和验收目标。
4. 按影响排序修正，复拍同组机位，确认没有把其他角度改坏。定稿附前后图、剩余差异和数字检查。视觉判断与网格、UV、比例验收都有真实证据时才报通过。

## Reference review

1. Freeze the supplied reference and requirements. An original design may use a generated target. Use `img_digest` for visible proportions and features. Mark dimensions inferred from an uncalibrated image as design assumptions.
2. Establish the blockout and fix three-quarter, front, and side views. Codex can request `views` with one `blender_see` call. DSH can request each view separately. Keep comparable images from each pass.
3. Compare silhouettes, proportions, construction and material. Record the visible discrepancy, which object to change, and how it should look after the fix. Check alignment and perspective before pixel comparisons. Use `visualreport_report` on aligned images for numeric silhouette and defect evidence. An independent reviewer can use the same source images and acceptance criteria when available.
4. Fix the most important discrepancies and capture the same views again. Check for regressions across views. Record remaining differences and report geometry, UV and scale checks separately from visual judgment.

把下面的 JSON 交给 `blender_see`。`from` 和 `look_at` 是示例坐标，首轮按资产大小和位置调好。只看图时可以省略 `review`。要存档时，换成 MCP 所在机器能访问的绝对路径，并在后续每轮沿用同一组机位和参考图。默认示例面向 Windows，其他系统请换成本机路径。

Pass this JSON to `blender_see`. Adjust the sample coordinates on the first round and replace the Windows paths with absolute paths accessible to your MCP server. Use the same viewpoint settings and reference on every archived round.

```json
{
  "aspect": "1:1",
  "max_size": 544,
  "overlays": false,
  "review": {
    "directory": "F:/assets/reviews/chair",
    "reference": "F:/assets/references/chair.png"
  },
  "views": [
    {"label": "front", "viewpoint": "custom", "from": "0,-3,0.5", "look_at": "0,0,0.5", "ortho": true, "ortho_scale": 1.3},
    {"label": "side", "viewpoint": "custom", "from": "-3,0,0.5", "look_at": "0,0,0.5", "ortho": true, "ortho_scale": 1.3}
  ]
}
```

每轮在复核目录保存 PNG 和 `review.json`。界面返回图片后再判断差异。要在后续一轮记录已知问题、改动或结论，可传 `defects`、`changes`、`verdict`。截图缺失时回执会记为降级。参考图或机位参数变了就另开存档目录。详见[作业模板](production-recipes.md)。

Each archived round saves PNGs and `review.json`. Use `defects`, `changes` and `verdict` to record what is already known when capturing a round. Use a new directory when the reference or viewpoint settings change.

## 游戏资产交付 · Game asset delivery

Save the Blender scene after checking the target mesh, UV map, materials, units and origin. Submit one of the following through `blender_run` with `action="submit"`, `kind="headless"`, an absolute `file` ending in `.blend`, and an absolute `outdir`. Set the mesh name in `asset_options.low`. Each job writes into `outdir/<jobId>` and leaves the input `.blend` available for further editing. Use the returned job ID with `wait` and `collect`.

先保存 `.blend`，确认目标网格、UV、材质、单位和枢轴。用 `blender_run` 提交后台作业，`file` 和 `outdir` 传绝对路径，`asset_options.low` 指定网格名。每次生成到 `outdir/<jobId>`，通过 `wait` 和 `collect` 查看终态和产物。目标是 Blender 里的网格对象名，例如 `SM_OakChair`。

| `asset_recipe` | Options inside `asset_options` | Outputs |
| --- | --- | --- |
| `bake_maps` | `bake.high` for selected-to-active, omit for self bake. Optional `maps`, `res`, `samples`, `margin_px`, `extrusion`, `cage`, `uv_layer`, `device`, `directx`, `pack_orm`. | PNG maps + report. With ORM enabled, AO, roughness and metallic are baked and packed into R, G and B. |
| `make_lods` | `lod.ratios`: 1–7 decreasing ratios, default `0.5, 0.25, 0.125`. Generated objects use the source name + `_LOD1` onward and carry an ownership tag. | `.blend` copy, triangle counts, and LOD objects. Unowned name conflicts fail. |
| `export_unreal` | `unreal.preset`: `static` (default) or `skeletal`. Static accepts `collision` proxy names and ordered `lods`. Skeletal requires a bound mesh and `armature`, with optional `animation: true` for its current timeline. | Base FBX, optional separate static LOD FBXs, report. Runs the existing `delivery` gate on the source. |
| `prepare_unreal` | Checks the source first, then bakes textures, builds LODs and exports static FBX. Set explicit collision proxy object names when used. Use `export_unreal` for skeletal export. | Packed-texture `.blend` copy, PNG maps, base and LOD FBXs, gate receipt and report. |

```json
{
  "action": "submit", "kind": "headless", "asset_recipe": "prepare_unreal",
  "file": "F:/assets/chair-source.blend", "outdir": "F:/assets/output",
  "asset_options": {
    "low": "SM_OakChair",
    "bake": {"high": ["OakChair_High"], "res": 1024, "extrusion": 0.006},
    "lod": {"ratios": [0.52, 0.29]},
    "unreal": {"collision": ["UCX_SM_OakChair_00"]}
  }
}
```

上面的 JSON 用于 `blender_run`。作业模板先检查源工程。回执的 `verdict` 为 `pass` 才继续。提交成功后，用返回的作业 ID 去等结果，再收集产物。

    blender_run(action="wait", id="<jobId>", timeout_ms=30000)
    blender_run(action="collect", id="<jobId>")

等待到时仍在运行就用同一个 ID 继续查。导出成功后查看 `asset-report.json` 和 `delivery-gate.json`。如果交付检查失败，按报告修好源工程，再保存并重提。

Submit the JSON through `blender_run`. Use the returned ID with `wait` and `collect`. Check `asset-report.json` and `delivery-gate.json`. Fix a failed delivery check in the source scene, save, and resubmit.

For static delivery, the base FBX includes the selected named convex collision proxies. Import the separate LOD FBXs into that static mesh as successive levels. The PNG maps are separate handoff assets, including a DirectX normal by default. Verify extent, pivot, proxy assignment, LOD order and material channels in the target Unreal project when authorized. Blender FBX reimport verifies file contents and scale in Blender.

静态网格主 FBX 包含指定的凸碰撞体。各级 LOD 以独立 FBX 交付，按顺序导入同一个静态网格。PNG 贴图单独交付，法线默认 DirectX。Blender 回读能核对 FBX 内容和尺寸，UE 中的枢轴、碰撞分配和 LOD 应在获准后用目标项目复核。
