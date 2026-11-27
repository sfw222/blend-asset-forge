# `dsh_blender_bridge` 包 —— Blender 侧扩展（本仓附带，唯一受支持版本）

[English](README.md) | 中文

这是 [Blend Asset Forge](../README.md) 随附的 Blender 扩展。面板显示名为 **Blend Asset Forge Bridge**，Codex 的 `blender-assets` 通过本地 Gateway 与它通信。

> **3.1 起 Blender 侧是 Blender 4.2 Extension 包：zip 只有一个顶层 `dsh_blender_bridge/`，内含
> `blender_manifest.toml`；单文件 `dsh_blender_bridge.py` 不再是安装入口，且已从本仓删除。**
> 旧单文件安装过的用户请先在 Blender 里停用并移除它，再安装 `blend_asset_forge_bridge.zip`（见
> [`../MIGRATIONS.md`](../MIGRATIONS.md)）。上游 `MCP for Blender`（模块 `blender_mcp`）与
> harveyxiacn `blender_mcp_addon` 同样不再支持。

## 这个包是什么

| 项 | 值 |
|---|---|
| 安装包 / 模块名 | `blend_asset_forge_bridge.zip`（包根 `dsh_blender_bridge/`，含 `blender_manifest.toml`） / `dsh_blender_bridge` |
| 源码目录 | `extension/dsh_blender_bridge/`（`__init__.py` 为入口，子包 `commands/`、`recorders/`、`assets/`、`integrations/`、`ui/`） |
| 显示名（Blender 插件列表里） | **Blend Asset Forge Bridge** |
| 版本 / 协议 | extension **v2.0.0 / protocol 12**；extension manifest v2.0.0 |
| 标识前缀 | `dshbb_`（注册类 `bpy.types.dshbb_server`、5 个集成开关 `dshbb_use_*`） |
| TCP 端口 | Gateway `127.0.0.1:39877`；addon 主动连接，不监听入站端口 |
| 命令面 | 25 条（18 条常驻 + 7 条集成门控；其中 21 条只读、4 条内部传输；命令名、参数与返回结构向后不兼容，见 MIGRATIONS） |

## 来源与许可（GPL-3.0-or-later，上游 MIT）

扩展承自 DSH Blender Plugin 的桥接组件，其中包含源自 [ahujasid/blender-mcp](https://github.com/ahujasid/blender-mcp) 的 MIT 代码。
扩展采用向本地 Gateway 主动连接的方式。上游版权和 MIT 许可声明随包保留，本扩展按
**GPL-3.0-or-later** 分发（见 extension 根目录的 [`LICENSE`](LICENSE) 与 [`NOTICE`](NOTICE)，以及
`blender_manifest.toml` 的 `license`）。DSH 宿主插件本体仍是 BSD-3-Clause（仓库根 `LICENSE`）。

```
# Code created by Siddharth Ahuja: www.github.com/ahujasid © 2025
```

上游 MIT 许可要求保留上述版权声明 —— **请勿删除**；完整 MIT 文本与 GPL 文本随扩展 zip 分发。

## 构建 zip

仓库已提交 `extension/blend_asset_forge_bridge.zip`；改源码后重新构建：

```bash
node scripts/build-extension.mjs          # 写 extension/blend_asset_forge_bridge.zip
node scripts/build-extension.mjs --check  # 只校验现有 zip 清单与版本
```

zip 内只有一个包根 `dsh_blender_bridge/`，含 `blender_manifest.toml`、`LICENSE`、`NOTICE` 与全部 `.py` 模块，不含
`__pycache__` / `.pyc`，并使用固定时间戳保证可复现。构建脚本同时校验 manifest、`gateway_schema.py`
与 `config/gateway.json` 的版本一致。要用 Blender 验证安装包，可在仓库根目录运行 `blender --command extension validate extension/blend_asset_forge_bridge.zip`。

## 装法

1. Blender → `Edit ▸ Preferences ▸ Extensions ▸ Install from Disk...` → 选本目录的 `blend_asset_forge_bridge.zip`（Blender 扩展包，不是目录、不是单个 `.py`）。
   - 如果还有其他用于 AI 控制 Blender 的扩展，先停用。若旧版同名扩展挡住安装，先在 Blender 里移除同名旧版。
2. 启用 **Blend Asset Forge Bridge**。按[首页](../README.md#安装)注册 `blender-assets`，在 Codex 调用 `blender_session(action="status")` 启动 Gateway。
3. 在 Blender 的 3D 视图按 `N`，打开 **Blend Asset Forge Bridge** 面板，点 **Connect**。扩展会连接本地 Gateway，默认 `127.0.0.1:39877`。

如果使用 DSH，Gateway 由 DSH 宿主启动。

## 验证

Codex 先跑 `blender_session(action="doctor")`。返回 `kind=ok` 后执行 `attach`。如果连不上，先确认 Gateway 已启动，再检查扩展是否启用、面板是否已连接、端口是否一致。连接成功后可检查扩展版本和活动状态：

```bash
blender_inspect(command="get_addon_info")     # addon_version 应为 [2, 0, 0]，protocol_version 应为 12
blender_inspect(command="get_activity_state") # state 可能为 idle / human / agent / both
```

在 DSH 宿主中，装好后在 Blender 里选物体 → `N` →「Selection → DSH」→ 发送，选中会进 **DSH 当前会话草稿**（不自动发送）。
编辑模式选顶点/边/面、姿态模式选骨骼、编辑曲线/晶格控制点也会一起发送（payload 里 `selection.sub`）；
N 面板的对象 / 成员列表默认折叠，展开后带滚动条且高度可调。

面板结构：活动状态置顶（AI 操作时显示红色警告）+「暂停 AI 操作」按钮；
「环境与角色模型API调用」为父面板，内含「环境生成」（Poly Haven / Sketchfab / Poly Pizza）与
「模型生成」（Hyper3D / Hunyuan3D）两个子面板，默认全部折叠。暂停期间 socket 只放行只读命令。

## 环境变量（旧名仍兼容）

新名优先、旧名回退：`DSHBB_HYPER3D_API_KEY` → 回退 `BLENDERMCP_HYPER3D_API_KEY`，其余同理
（`SKETCHFAB` / `POLYPIZZA` / `HUNYUAN3D_*`）。**你已设的旧变量不会失效**（这只是 key 名兼容，不代表支持旧扩展）。