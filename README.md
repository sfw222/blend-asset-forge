# Blend Asset Forge

[English](docs/en/README.md)

用 Codex 在 Blender 里按参考图做资产。模型改完一轮，可以从几个固定角度截图，和上一版一起对照。做游戏道具时，也可以接着烘焙贴图、生成 LOD，再导出 Unreal 用的静态 FBX。

## 安装

从源码构建需要 Node.js **24.9** 或更高版本。Blender 桥接扩展可在 4.2 或更新版本安装。下面的资产流程用 Blender 5.2.3 验证，扩展作业模板要求 5.2 或更新版本。

1. 在仓库根目录运行：

   ```sh
   npm ci --legacy-peer-deps
   npm run build
   ```

2. 打开 Blender，进入 **Edit → Preferences → Extensions → Install from Disk**，安装 [blend_asset_forge_bridge.zip](extension/blend_asset_forge_bridge.zip)。安装后启用 **Blend Asset Forge Bridge**。如果已有其他用于 AI 控制 Blender 的桥接扩展，先停用它。
3. 注册本地 MCP。把命令里的路径换成你的实际路径：

   ```sh
   codex mcp add blender-assets -- node "/path/to/blend-asset-forge/lib/mcp/index.js"
   ```

   找不到 Blender 时，在命令的 `--` 前加 `--env "DSH_BLENDER_EXE=Blender 可执行文件的绝对路径"`。
4. 新开一个 Codex 聊天，调用 `blender_session(action="status")` 启动本地 Gateway。回 Blender，在 3D 视图按 **N**，在 **Blend Asset Forge Bridge** 面板点 **Connect**。回到 Codex 执行 `doctor`，返回 `kind=ok` 后执行 `attach`。

如果只跑后台任务，可以用 `blender_run` 提交无头作业，再用 `wait` 和 `collect` 取回结果。配置项见[配置参考](docs/配置参考.md)。

## 做一个资产

1. **定尺寸，搭白模。** 给 Codex 原参考图、结构、用途和已知尺寸。没有标尺时先定设计尺寸，再用 Blender 白模检查轮廓和比例。见 [Blender 建模技能](skills/blender-modeling/SKILL.md)。
2. **固定机位返修。** 用 `blender_see` 的 `views` 一次取回最多六张图。加 `review` 后，每轮保存 PNG 和 `review.json`。沿用同一参考图和机位，先修轮廓和比例，再修接缝、材质和细节。
3. **检查并保存。** 核对网格、UV、材质、单位和枢轴，再保存源 `.blend`。用 `blender_run(action="asset_catalog")` 查看适用的检查项和作业模板。
4. **导出 Unreal 静态道具。** 用 `blender_run` 提交 `prepare_unreal`。它先跑交付检查，再烘焙贴图、生成 LOD、导出 FBX。拿作业 ID 执行 `wait` 和 `collect`，查看报告和输出。实测已用 Blender 回读 FBX，目标 UE 项目里的导入效果需要另行核对。

- [多视角返修与 Unreal 导出](skills/blender-modeling/references/reference-review-and-unreal.md)
- [作业模板与参数](skills/blender-modeling/references/production-recipes.md)
- [Blender 桥接与常见故障](extension/README.zh.md)

旧版 DSH 的安装和部署见[原 DSH 指南](docs/操作教程.md)。

## 开发

使用 Node.js **24.9** 或更高版本。Python 测试需要装有 pytest 的 venv，用 `PYTHON` 指定解释器路径。构建、检查和测试命令见 [AGENTS.md](AGENTS.md#1-commands-single-source)。代码结构见[架构说明](docs/architecture.md)，提交改动前可参考[贡献说明](docs/zh/CONTRIBUTING.md)。

## 来源与许可

项目基于 [DSH Blender Plugin](https://github.com/sixtysevenlf/dsh-blender-plugin)。参考图返修流程参考了 [dream-loop](https://github.com/achimala/dream-loop)，部分资产制作脚本来自 [blender-skills](https://github.com/EL4CTEO/blender-skills)。

- 主体代码：[BSD-3-Clause](LICENSE)。
- Blender 桥接扩展：[GPL-3.0-or-later](extension/LICENSE)。源自 `blender-mcp` 的代码保留原有 [MIT 声明](extension/NOTICE)。
- 随附的建模技能和制作脚本：MIT。版权声明、许可证和上游版本见[第三方来源](skills/blender-modeling/NOTICE.md)。

npm 包同时分发上述组件，包的 SPDX 声明列出这三种许可证。各组件按上面列出的许可使用。
