# NOTICE — 来源与许可

本技能（`blender-modeling`）是 MIT 许可项目的派生作品，工具调用已改写为本插件 6 个模型工具的直连链。

## 上游项目

1. **RobLe3/cc-blender-skill** — https://github.com/RobLe3/cc-blender-skill （MIT）
   使用：`plugin/skills/blender-modeling/SKILL.md` 的决策树、8 个操作示例、三条关键坑、修改器栈序与症状表；`references/overview.md`（本目录 `references/modeling-overview.md`，原文收录）。

2. **arjun988/blender-skills** — https://github.com/arjun988/blender-skills （MIT）
   使用：`.claude/skills/blender-modeler/SKILL.md` 的六步总纲、集合结构、修改器栈哲学与规则、清理清单、MUST DO / MUST NOT DO。

## 本地改动

- `mcp__blender__execute_blender_code` / `get_scene_info` / `get_object_info` → `blender_py` / `blender_run` / `blender_inspect` / `blender_see` / `blender_session`。
- 新增「通道语义」一节（MCP 的「每次重新 import」假设在本机只对 headless 成立）。
- 正文改写为中文，结构精简合并。

MIT 许可要求保留版权与许可声明；上游版权和许可全文随本技能分发，见 [RobLe3 的 MIT 许可证](LICENSE.cc-blender-skill)与 [arjun988/blender-skills 的 MIT 许可证](LICENSE.arjun988-blender-skills)。本派生作品同样以 MIT 提供。

参考图返修流程借鉴 [achimala/dream-loop](https://github.com/achimala/dream-loop) 在提交 `9bddb901f7d071cfefdd21e264267c757177a9df` 的参考图、复拍和复核循环。许可见 [LICENSE.dream-loop](LICENSE.dream-loop)。

资产制作脚本来自 [EL4CTEO/blender-skills](https://github.com/EL4CTEO/blender-skills) 提交 `15cebb2dc94a0c77bef2d9a5e6e378138488dcf7`。LOD 与 FBX 作业模板参考同一提交的 `make_lods.py` 和 `export_asset.py`，并适配本仓的作业和验收流程。许可见 [blender-skills LICENSE](../../runtime/ext/blender-skills/LICENSE)。Fal 队列助手来自同一版 dream-loop，许可见 [Fal 助手 LICENSE](../../runtime/ext/fal/LICENSE)。
