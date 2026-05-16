---
name: decklens-convert
description: 当用户提供图片、截图或 PDF，并希望转换、拆分或还原为可编辑 PPTX 时使用。
metadata:
  decklens:
    version: "0.2.9"
    min_app_version: "0.2.8"
    update_channel: stable
    source: decklens
---

# DeckLens 转换

使用 DeckLens 产品 CLI，把图片类演示页转换为可编辑 PPTX。执行元素分层时，DeckLens 负责基础拆分，Agent 负责视觉判断、矢量重绘、图标替换、图层顺序检查和最终交付质量。

## 必须遵守

| 场景 | 必须执行 | 不允许 |
| --- | --- | --- |
| 用户要求“拆分”“分层”“还原为可编辑 PPT” | 默认运行元素分层，并完成后处理验收 | 只返回 DeckLens 原始输出 |
| 页面里有简单形状、按钮、卡片、分割线、图标 | 在转换前列出矢量/icon 计划，转换后落实替换 | 等用户提醒后才补做 |
| 页面里有背景渐变、底部色带渐变、按钮渐变、卡片渐变 | 必须还原渐变方向、主要色阶和覆盖范围 | 用单一纯色替代明显渐变 |
| 图标可匹配标准符号 | 优先用内置图标库替换，并保持同页风格一致 | 用 emoji、Unicode 符号或噪声蒙版像素代替 |
| SVG 在预览器里显示异常 | 用 `decklens icons render --format png --size 512` 生成透明 PNG 回退 | 交付预览损坏的 PPTX |
| 元素不适合矢量化 | 明确保留为位图，并说明原因 | 强行重绘照片、3D、复杂纹理、复杂渐变 |

除非用户明确说“不要矢量化”“只要原始分层结果”，否则元素分层任务的最终结果必须包含一次矢量/icon 后处理判断。即使最终没有任何元素适合替换，也要在回复里说明“未替换”的原因。

## CLI 位置

优先使用已安装 App 内置 CLI，不要让 Agent 到处搜索仓库。找到 CLI 后必须先看 `--help`，确认输出里同时有 `inspect` 和 `icons render`。如果没有这两个命令，说明 App CLI 低于 `0.2.8`，不要继续用它做分层后处理。

macOS 默认路径：

```bash
node "/Applications/DeckLens.app/Contents/Resources/cli/decklens.cjs" --help
```

Windows 默认路径：

```powershell
node "$env:LOCALAPPDATA\Programs\DeckLens\resources\cli\decklens.cjs" --help
```

如果默认 App CLI 不存在，或 `--help` 缺少 `inspect` / `icons render`，再按顺序回退：

1. 当前仓库：`./bin/decklens.cjs`
2. 当前开发机固定仓库路径：`/Users/jadon7/Documents/SynologyDrive/code/DeckLens/bin/decklens.cjs`
3. 用户明确给出的 DeckLens Desktop 仓库路径
4. `PATH` 中的 `decklens`
5. 如果以上都不可用，先提示用户安装或更新 DeckLens，再继续转换。

找到可用 CLI 后，后续所有 `convert`、`inspect`、`icons` 命令必须使用同一个 CLI 路径，避免一会儿用旧安装版、一会儿用仓库版导致 icon 库或命令能力不一致。

## 工作流程

1. 确认输入文件存在，并且是 `.png`、`.jpg`、`.jpeg` 或 `.pdf`。
2. 选择 DeckLens CLI。优先使用上方固定 App CLI 路径，但必须确认它支持 `inspect` 和 `icons render`。
3. 查看原始图片，先写下 4 类判断：可矢量化目标、可 icon 替换目标、必须保留位图目标、必须保留或重建的渐变/背景装饰目标。
4. 默认运行元素分层：

```bash
node "/Applications/DeckLens.app/Contents/Resources/cli/decklens.cjs" convert "/path/to/input.png" --mode element --output "/path/to/output.pptx"
```

5. 生成后立即检查 PPTX 结构：

```bash
node "/Applications/DeckLens.app/Contents/Resources/cli/decklens.cjs" inspect "/path/to/output.pptx" --json
```

6. 按转换前计划后处理 PPTX：删除被替换的位图层，插入原生 PPT 形状、SVG 或高清透明 PNG 图标，并保持 z-order。
7. 后处理完成后再次运行 `inspect`，确认图片层、shape、文本框和图层顺序符合预期。
8. 最终返回 PPTX 路径，并报告转换模式、矢量替换、渐变/背景还原方式、icon 来源、保留位图原因。

## 常用命令

标准还原：

```bash
node "/Applications/DeckLens.app/Contents/Resources/cli/decklens.cjs" convert "/path/to/input.png" --output "/path/to/output.pptx"
```

多页输入：

```bash
node "/Applications/DeckLens.app/Contents/Resources/cli/decklens.cjs" convert "/path/to/page1.png" "/path/to/page2.png" --output "/path/to/deck.pptx"
```

PDF 输入：

```bash
node "/Applications/DeckLens.app/Contents/Resources/cli/decklens.cjs" convert "/path/to/file.pdf" --output "/path/to/deck.pptx"
```

元素分层：

```bash
node "/Applications/DeckLens.app/Contents/Resources/cli/decklens.cjs" convert "/path/to/input.png" --mode element --output "/path/to/deck.pptx"
```

AI 智能分层：

```bash
FAL_KEY="$FAL_KEY" node "/Applications/DeckLens.app/Contents/Resources/cli/decklens.cjs" convert "/path/to/input.png" --mode ai --qwen-layers 4 --output "/path/to/deck.pptx"
```

检查 PPTX 结构：

```bash
node "/Applications/DeckLens.app/Contents/Resources/cli/decklens.cjs" inspect "/path/to/deck.pptx" --json
```

查找和渲染内置图标：

```bash
node "/Applications/DeckLens.app/Contents/Resources/cli/decklens.cjs" icons libraries
node "/Applications/DeckLens.app/Contents/Resources/cli/decklens.cjs" icons find mail --style outline --json
node "/Applications/DeckLens.app/Contents/Resources/cli/decklens.cjs" icons render mail --style outline --color 111111 --format svg --output "/path/to/mail.svg" --json
node "/Applications/DeckLens.app/Contents/Resources/cli/decklens.cjs" icons render mail --style outline --color 111111 --format png --size 512 --output "/path/to/mail.png" --json
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

如果 App 没安装，先询问用户是否需要帮助安装。用户同意后使用直达下载链接：

- macOS：`https://updates.dsxzai.com/download/mac`
- Windows：`https://updates.dsxzai.com/download/windows`
- 自动识别平台：`https://updates.dsxzai.com/download`

## 转换前计划

运行 `convert --mode element` 之前，必须基于原始图片列出候选，不要基于分割后的毛边判断。

优先标记为矢量候选：

- 页面背景、圆角页面框、面板、卡片、按钮、胶囊、徽标、分割线、下划线、进度条、简单装饰色带。
- 扁平色或简单渐变的圆形、椭圆形、矩形、圆角矩形。
- 背景渐变、底部 CTA 色带渐变、按钮渐变、卡片渐变等大面积视觉层。渐变本身是设计元素，不能因为它不是图标或文字就忽略。
- 直线、箭头、连接线、基础几何标记。
- 常见 UI 图标、演示图标、状态图标、社交图标，只要能匹配标准符号库。
- 文字内容在 OCR 质量可接受时保留为可编辑文本，并修正明显空格、标点、合并词问题。

必须保留位图：

- 照片、复杂截图、写实插画、3D 渲染、细节 logo、复杂渐变、重阴影、柔光、纸张噪声、半调纹理、复杂背景，以及矢量化后保真度会明显变差的元素。

计划必须写成语义对象，不要写成未来图层编号。例如写“4 个指标卡片的圆形图标底、图标、绿色下划线”，不要写“image4/image5/image6”。

对渐变目标，计划里必须写清楚位置和处理方式。例如：“底部 CTA 蓝色横向渐变条，用 PPT 渐变填充重建；如果当前 PPT 库不支持等效渐变，则裁切原图底部渐变条作为位图背景保留，上层文字和图标仍保持可编辑。”

## 矢量和图标后处理

1. 对每个预标记矢量目标，在 `inspect` 输出中找到对应位图层。
2. 如果一个语义目标被拆成多个位图层，替换前删除或隐藏所有对应碎片。
3. 使用 PPT 原生形状重绘规则几何元素：矩形、圆角矩形、圆形、椭圆、线条、箭头、分割线、进度条。
4. 重绘完整语义对象范围，不要只按紧贴像素的蒙版边界画。例如重绘完整卡片、完整图标底、完整下划线、完整胶囊。
5. 对渐变元素，优先用 PPT 原生渐变填充还原方向、主要色阶、透明度和圆角。不能等效重建时，裁切原图对应区域作为底层位图保留，再把文字、图标、线条等前景元素放在其上方。不要把明显渐变简化成单一纯色。
6. 对背景渐变和底部色带渐变，必须在 Quick Look 或截图预览中与原图并排核对。若渐变方向、亮暗过渡或覆盖范围明显不对，继续调整后再交付。
7. 对图标先做语义匹配，再使用 `decklens icons find` 和 `decklens icons render`。优先级：`lucide-static` outline、`tabler-icons` outline/filled、`heroicons` outline/solid。
8. 如果 `icons find thumbs-up` 失败，继续尝试同义或单复数名称，例如 `thumb-up`、`like`、`check`、`users`、`user`。不要因为第一次搜索失败就放弃图标替换。
9. 同一页内图标风格必须一致。不要混用 outline、filled、emoji、SF Symbols、Material Symbols 和手绘图标，除非原图本身就是混用。
10. SVG 可用时优先使用 SVG；若预览器或 PowerPoint 显示 SVG 异常，统一渲染为 512px 透明 PNG 再插入。
11. 插入替换元素时保持原图层顺序。替换元素要放在被删除位图层相同的 z-order 位置，避免遮挡关系变化。
12. 不要运行 `npm install`、不要从网络下载图标包、不要要求用户安装图标依赖。

## 验收要求

返回给用户前必须完成：

1. `inspect` 原始 DeckLens 输出。
2. 执行矢量/icon 后处理，或明确判断没有适合目标。
3. `inspect` 最终 PPTX。
4. 最终说明包含：
   - 使用的转换模式。
   - 替换为 PPT 原生形状的元素。
   - 背景渐变、底部渐变、按钮/卡片渐变的还原方式；如果使用位图保留，要说明保留区域。
   - 替换为 SVG/PNG 图标的元素和图标库来源。
   - 保留为位图的元素和原因。
   - 最终 PPTX 路径。

如果没有完成矢量/icon 后处理，不要把结果称为最终版本，只能称为“原始分层结果”。

## 注意事项

- 默认底图清理使用 `--inpaint-backend lama`；简单背景可以用 `--inpaint-backend local_mean`。
- 除非确定当前机器有可用加速后端，否则优先使用 `DECKLENS_DEVICE=cpu`。
- 已存在输出文件不会被替换，除非用户明确允许使用 `--overwrite`。
- 不要直接调用 `decklens_cli.py`。它是产品 CLI 背后的内部后端适配层。
