---
name: decklens-convert
description: 当用户提供图片、截图或 PDF，并希望转换、拆分或还原为可编辑 PPTX 时使用。
metadata:
  decklens:
    version: "0.2.18"
    min_app_version: "0.2.17"
    update_channel: stable
    source: decklens
---

# DeckLens 转换路由

使用 DeckLens 产品 CLI，把图片类演示页转换为可编辑 PPTX。这个文件只负责路由和共享入口，不承载完整页面处理规则。

## 先做路由

| 当前环境 | 必须读取 | 执行方式 |
| --- | --- | --- |
| 用户要求拆单页、只提供一张图片，或 PDF/输入明确只有 1 页 | `workflows/quality-rules.md` + `workflows/single-agent.md` | 直接由当前 Agent 处理，不走 subagent |
| 支持 subagent，且任务包含多页、多张图片或 PDF 多页 | `workflows/quality-rules.md` + `workflows/main-agent.md` | 主 Agent 只负责分派、汇总和验收；每页交给子 Agent |
| 不支持 subagent 的多页/多图任务 | `workflows/quality-rules.md` + `workflows/single-agent.md` | 当前 Agent 按页级隔离流程执行 |

判断是否支持 subagent：

- 先判断任务规模。单页拆分优先级最高：即使当前环境支持 subagent，也不要创建子 Agent，直接读取 `workflows/single-agent.md`。
- 如果当前 Agent 运行环境明确提供子 Agent / subagent / worker / task delegation 能力，视为支持。
- 如果不确定，先按“不支持 subagent”处理，读取 `workflows/single-agent.md`。
- 任意路径都必须先读取 `workflows/quality-rules.md`。这是完整质量标准，不能只读路由文件。
- 如果支持 subagent，主 Agent 必须把当前 skill 根目录下的 `workflows/quality-rules.md` 和 `workflows/subagent-page.md` 路径传给每个子 Agent，并要求子 Agent 直接读取这两个文件。不要只口头转述规则。

## 共享硬规则

无论走哪条路径，都必须遵守：

- DeckLens 程序分层只是中间草稿，不是最终图层结构。
- 扁平 icon 必须替换，不能保留为图片。
- 扁平柱状图和条形图必须重新绘制；其他图表默认不重绘。
- 矢量/shape 绘制范围仅限独立矩形、圆形、圆角矩形/胶囊/按钮容器、ICON、分割线。箭头、手绘样式、复杂装饰和其他非基础形状默认保持原图构造；只有它们本身是标准扁平 icon 时才走 icon 库替换。
- 矩形、圆角矩形、卡片和按钮容器必须按原图尺寸、圆角、投影、描边、填充、透明度和渐变绘制，尤其不能随意套默认圆角。
- 独立扁平背景用 PPT 背景、矩形或渐变形状重建；复杂图片内部的局部色块不要为了矢量化而拆出来。
- 程序分层不好时，Agent 必须基于原图语义手动拆分、合并、裁切或重建。
- 新增 shape/SVG/icon/合并位图后，必须删除或隐藏对应源图片层，避免重复叠加。
- 每页必须有质量审计表；多页任务不能只写“整体已检查”。
- 如果页面有合规范围内的扁平候选（矩形、圆形、icon、分割线、柱状/条形图或背景容器），但最终没有任何 shape/SVG/icon/vector 类对象，直接判定失败。
- 不允许用 emoji、Unicode 字符或普通文本冒充 icon；扁平 icon 必须用 DeckLens icon 库替换，不能遗漏，也不能自己手绘；不允许把所有能画的东西都画成 SVG。

## CLI 位置

优先使用已安装 App 内置 CLI。找到 CLI 后必须先看 `--help`，确认输出里同时有 `review create`、`review apply`、`inspect` 和 `icons render`。

macOS 默认路径：

```bash
node "/Applications/DeckLens.app/Contents/Resources/cli/decklens.cjs" --help
```

Windows 默认路径：

```powershell
node "$env:LOCALAPPDATA\Programs\DeckLens\resources\cli\decklens.cjs" --help
```

如果默认 App CLI 不存在，或 `--help` 缺少 `review` / `inspect` / `icons render`，再按顺序回退：

1. 当前仓库：`./bin/decklens.cjs`
2. 当前开发机固定仓库路径：`/Users/jadon7/Documents/SynologyDrive/code/DeckLens/bin/decklens.cjs`
3. 用户明确给出的 DeckLens Desktop 仓库路径
4. `PATH` 中的 `decklens`
5. 如果以上都不可用，先提示用户安装或更新 DeckLens，再继续转换。

找到可用 CLI 后，后续所有 `review`、`convert`、`inspect`、`icons` 命令必须使用同一个 CLI 路径。

## 常用命令

Agent 审阅式元素分层：

```bash
node "/Applications/DeckLens.app/Contents/Resources/cli/decklens.cjs" review create "/path/to/input.png" --review-dir "/path/to/decklens-review" --json
node "/Applications/DeckLens.app/Contents/Resources/cli/decklens.cjs" review apply "/path/to/decklens-review/manifest.json" --decision "/path/to/decklens-review/decision.json" --output "/path/to/deck.pptx" --json
node "/Applications/DeckLens.app/Contents/Resources/cli/decklens.cjs" inspect "/path/to/deck.pptx" --json
```

图标检索和渲染：

```bash
node "/Applications/DeckLens.app/Contents/Resources/cli/decklens.cjs" icons find mail --style outline --json
node "/Applications/DeckLens.app/Contents/Resources/cli/decklens.cjs" icons render mail --style outline --color 111111 --format svg --output "/path/to/mail.svg" --json
```

Windows 命令把 CLI 路径替换为：

```powershell
node "$env:LOCALAPPDATA\Programs\DeckLens\resources\cli\decklens.cjs"
```

## Skill 维护命令

用户已经触发本 skill 时，不需要再安装 skill。下面命令只用于用户明确要求“安装/更新 DeckLens skill”时。

```bash
node "/Applications/DeckLens.app/Contents/Resources/cli/decklens.cjs" install-skills
node "/Applications/DeckLens.app/Contents/Resources/cli/decklens.cjs" skills status
node "/Applications/DeckLens.app/Contents/Resources/cli/decklens.cjs" skills update
```
