---
name: decklens-convert
description: 当用户提供图片、截图或 PDF，并希望转换、拆分或还原为可编辑 PPTX 时使用。
metadata:
  decklens:
    version: "0.2.12"
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
| DeckLens 拆出大量碎片图层 | 按语义对象手动合并或替换为一个对象 | 把碎片图层原样交付 |
| 照片、人物、3D、纹理图、复杂插画被拆成多块 | 裁切原图对应区域，合并成一张完整位图 | 把同一个复杂图像拆成很多可选中的碎片 |
| 多页输入 | 每一页都单独做转换前计划、替换清单和验收 | 只认真处理第一页或最后一页 |
| 页面里有简单形状、按钮、卡片、分割线、图标 | 在转换前列出矢量/icon 计划，转换后落实替换 | 等用户提醒后才补做 |
| 页面里有纯色背景、纯色区块、普通卡片 | 优先用 PPT 原生形状或 SVG 重建 | 直接沿用被拆分后的整块图片 |
| 页面里有卡片容器 | 卡片本体必须用圆角矩形/描边/阴影/渐变重建 | 因为卡片里有图片或文字就把整张卡片保留为位图 |
| 页面里有柱状图、条形图、饼图、环形图、折线图 | 优先用 PPT 形状/SVG 重绘基础图表 | 把基础图表当作普通位图保留 |
| 页面里有背景渐变、底部色带渐变、按钮渐变、卡片渐变 | 必须还原渐变方向、主要色阶和覆盖范围 | 用单一纯色替代明显渐变 |
| 图标可匹配标准符号 | 优先用内置图标库替换，并保持同页风格一致 | 用 emoji、Unicode 符号或噪声蒙版像素代替 |
| 矢量/SVG/icon 已替换原图片层 | 删除或隐藏所有对应源位图层，并复查没有重复叠加 | 只新增矢量层但保留原图片 |
| OCR 文本回写到 PPT | 单行段落用自动宽度；同样式多行文本用固定宽度、自动高度 | 把同一段文字拆成多个互相漂移的文本框 |
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
3. 查看每一页原始图片，逐页写下 7 类判断：可矢量化目标、卡片容器目标、可 icon 替换目标、可合并的碎片目标、复杂位图组目标、必须保留位图目标、必须保留或重建的渐变/背景装饰目标。
4. 默认运行元素分层：

```bash
node "/Applications/DeckLens.app/Contents/Resources/cli/decklens.cjs" convert "/path/to/input.png" --mode element --output "/path/to/output.pptx"
```

5. 生成后立即检查 PPTX 结构：

```bash
node "/Applications/DeckLens.app/Contents/Resources/cli/decklens.cjs" inspect "/path/to/output.pptx" --json
```

6. 建立逐页替换清单：每个语义目标都要列出“源位图层/碎片层 -> 新 PPT 形状、SVG 或 PNG 图标”。没有源位图层编号的替换不允许直接开始。
7. 按替换清单后处理 PPTX：先删除或隐藏对应源位图层，再插入原生 PPT 形状、SVG 或高清透明 PNG 图标，并保持 z-order。
8. 对 OCR 文本层应用文本框尺寸策略：单行段落自动宽度；同样式多行固定宽度、自动高度；标题、标签、数值保持原对齐方式。
9. 后处理完成后再次运行 `inspect`，确认图片层、shape、文本框、图层顺序和被替换源位图删除情况符合预期。
10. 最终返回 PPTX 路径，并报告转换模式、逐页矢量替换、渐变/背景还原方式、icon 来源、图表重绘情况、保留位图原因。

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

多页输入必须逐页列计划。每一页都要有自己的候选、icon 风格判断、图表判断和保留位图判断。不要把第一页的风格规则机械套到后续页面。

优先标记为矢量候选：

- 页面背景、圆角页面框、面板、卡片、按钮、胶囊、徽标、分割线、下划线、进度条、简单装饰色带。
- 大面积纯色背景、纯色侧栏、纯色页脚、纯色内容区块。只要没有复杂纹理或照片细节，默认用 PPT 形状重建，不要保留整块拆分图片。
- 扁平色或简单渐变的圆形、椭圆形、矩形、圆角矩形。
- 常规卡片：白底卡片、浅灰卡片、描边卡片、阴影很弱的卡片、圆角信息块、KPI 卡片、列表项容器。卡片本体优先用圆角矩形、描边、透明度和阴影参数重建。
- 基础图表：柱状图、条形图、饼图、环形图、折线图、坐标轴、网格线、图例、数据标签。只要图表由基础几何和文字组成，默认用 PPT 形状或 SVG 重绘。
- 背景渐变、底部 CTA 色带渐变、按钮渐变、卡片渐变等大面积视觉层。渐变本身是设计元素，不能因为它不是图标或文字就忽略。
- 直线、箭头、连接线、基础几何标记。
- 常见 UI 图标、演示图标、状态图标、社交图标，只要能匹配标准符号库。
- 文字内容在 OCR 质量可接受时保留为可编辑文本，并修正明显空格、标点、合并词问题。

必须保留位图：

- 照片、复杂截图、写实插画、3D 渲染、细节 logo、复杂渐变、重阴影、柔光、纸张噪声、半调纹理、复杂背景，以及矢量化后保真度会明显变差的元素。

必须合并为一张位图：

- 同一张照片、人物、头发、服装、3D 物体、复杂插画、纹理图、截图缩略图，被 DeckLens 拆成多个相邻、重叠或嵌套的图片层。
- 多个碎片共享同一个视觉边界或外接矩形，选中时出现一堆控制框，但肉眼看起来就是一张图片。
- 碎片之间没有可独立编辑的语义，例如不是独立按钮、独立图标、独立文字、独立图表数据，而只是同一张复杂图里的局部像素。

这种情况不要尝试逐块修复，也不要把碎片保留下来。应从原始输入图裁切出完整语义区域，作为一张位图插回 PPT，并删除或隐藏所有对应碎片层。例如：一张黑底人物/白色布料照片被拆成十几块，最终 PPT 里应该只有一张该照片图片层。

计划必须写成语义对象，不要写成未来图层编号。例如写“4 个指标卡片的圆形图标底、图标、绿色下划线”，不要写“image4/image5/image6”。后处理阶段再把这些语义对象映射到具体源位图层。

对渐变目标，计划里必须写清楚位置和处理方式。例如：“底部 CTA 蓝色横向渐变条，用 PPT 渐变填充重建；如果当前 PPT 库不支持等效渐变，则裁切原图底部渐变条作为位图背景保留，上层文字和图标仍保持可编辑。”

## 卡片容器规则

卡片是版式结构，不是普通图片。只要原图中某个区域表现为卡片容器，默认必须矢量化卡片本体。

识别为卡片的条件包括任意一项：

- 有明显矩形或圆角矩形边界。
- 有统一底色、半透明底色、描边、投影、毛玻璃、弱渐变或内边距。
- 多个同尺寸或同样式区块按网格、列表、横向卡组排列。
- 内部包含标题、说明、数字、图标、照片、截图或图表，但外部仍然有独立容器边界。
- 原图中看起来是“一个内容块”“一个 KPI 卡”“一个项目卡”“一个图片卡”“一个列表项卡”。

卡片后处理必须拆成“容器”和“内容”两层：

1. 容器层：用 PPT 圆角矩形、填充、描边、阴影、透明度、渐变重建。
2. 内容层：文字用可编辑文本；图标用内置图标或 SVG/PNG；照片、截图、复杂插画可作为裁切位图保留。
3. 如果卡片里有照片或复杂图像，只保留内部复杂图像为位图，不能因此把卡片背景、圆角、描边、投影也整体保留为位图。
4. 如果 DeckLens 把卡片背景、边框、阴影、内容拆成多个图片碎片，要用一个容器 shape 替换卡片本体，并删除对应卡片背景/边框/阴影碎片。
5. 如果同一页有重复卡片，优先统一尺寸、圆角、描边、阴影、内边距和对齐，不要每张卡片生成不同样式。

卡片允许保留位图的例外很少，必须明确说明原因：

- 卡片本体就是复杂纹理、照片拼贴、重拟物光影或 3D 材质。
- 卡片边缘没有明确容器语义，只是复杂截图的一部分。
- 当前 PPT 库无法近似重建关键视觉，并且裁切位图比矢量重绘更接近原图。

每页验收前必须做一次“卡片审计”：原图中肉眼可见的卡片数量、最终 PPT 中被 shape/SVG 重建的卡片数量、仍保留位图的卡片数量和原因。如果发现原图卡片没有进入替换清单，要返回补做。

## 多页和替换清单

多页任务按“页”作为最小验收单位。每一页都必须完成：

1. 原图观察和候选计划。
2. DeckLens 原始输出 `inspect`。
3. 源图层到目标对象的替换清单。
4. 后处理。
5. 最终 `inspect`。
6. 预览或截图核对。

替换清单必须包含：

- 页码。
- 语义对象，例如“第 3 页三张项目卡片背景”“第 5 页曝光趋势柱状图”“第 2 页底部社交图标组”。
- 所有对应源位图层或碎片层的 index/media path。
- 新对象类型：PPT shape、PPT text、SVG、PNG icon、保留位图。
- z-order 位置：放在原对象同层、前景文字下方、背景上方等。
- 删除动作：被替换源位图层必须标记为“删除/隐藏”。如果保留，必须说明原因。
- 卡片审计：每个卡片容器对应的源图层、重建方式、保留位图的内部内容、被删除的卡片背景/边框/阴影碎片。

不能只说“补了矢量元素”。必须能说明每个新增矢量对应删除了哪些源位图层。若最终 `inspect` 里仍然存在相同位置、相同尺寸、相同视觉内容的源图片层，要继续清理。

复杂位图组合并清单必须额外包含：

- 合并原因，例如“同一张人物照片被拆成 12 个重叠碎片”。
- 合并后的完整裁切区域，按原图坐标或 PPT 坐标记录。
- 被删除的所有碎片层 index/media path。
- 新插入的单张图片层位置、尺寸和 z-order。
- 验收结论：最终该语义对象只能剩一个可选中的图片层。

## 矢量和图标后处理

1. 对每个预标记矢量目标，在 `inspect` 输出中找到对应位图层。
2. 如果一个语义目标被拆成多个位图层，先判断它是“可矢量语义对象”还是“复杂位图组”。可矢量对象重绘为 shape/SVG；复杂位图组裁切原图为一张完整图片。两种情况都必须删除或隐藏所有对应碎片。
3. 使用 PPT 原生形状重绘规则几何元素：矩形、圆角矩形、圆形、椭圆、线条、箭头、分割线、进度条。
4. 重绘完整语义对象范围，不要只按紧贴像素的蒙版边界画。例如重绘完整卡片、完整图标底、完整下划线、完整胶囊。
5. 对渐变元素，优先用 PPT 原生渐变填充还原方向、主要色阶、透明度和圆角。不能等效重建时，裁切原图对应区域作为底层位图保留，再把文字、图标、线条等前景元素放在其上方。不要把明显渐变简化成单一纯色。
6. 对背景渐变和底部色带渐变，必须在 Quick Look 或截图预览中与原图并排核对。若渐变方向、亮暗过渡或覆盖范围明显不对，继续调整后再交付。
7. 对纯色背景、纯色区块、卡片容器，优先用 PPT shape 重建。卡片容器尤其要拆分处理：容器矢量化，内部复杂图片可位图保留。只有卡片本体存在明显纹理、噪声、照片或复杂光影时，才允许把卡片本体保留为位图。
8. 对基础图表，先判断图表类型和数据关系，再用形状重绘：柱状图/条形图用矩形，饼图/环形图用 SVG 扇区或 PPT 形状，折线图用线段和圆点，坐标轴/网格线/图例用线条和文本。图表的数据值无法精确读出时，允许按视觉比例近似，但要保留原来的标签、颜色和图例顺序。
9. 对图标先做语义匹配，再使用 `decklens icons find` 和 `decklens icons render`。优先级：`lucide-static` outline、`tabler-icons` outline/filled、`heroicons` outline/solid。
10. 如果 `icons find thumbs-up` 失败，继续尝试同义或单复数名称，例如 `thumb-up`、`like`、`check`、`users`、`user`。不要因为第一次搜索失败就放弃图标替换。
11. 图标风格以“当前页”为边界统一，不要跨页强行统一。同一页内如果原图的同一组图标都是线性，就全部线性；如果都是面型，就全部面型；如果原图同页本身有线性和面型混用，要按原图分组保留这种差异。不要默认把所有图标都画成线性。
12. SVG 可用时优先使用 SVG；若预览器或 PowerPoint 显示 SVG 异常，统一渲染为 512px 透明 PNG 再插入。
13. 插入替换元素时保持原图层顺序。替换元素要放在被删除位图层相同的 z-order 位置，避免遮挡关系变化。
14. 对复杂位图组，优先从原始输入图按完整语义区域裁切，不要尝试把 DeckLens 的碎片重新拼起来。原图裁切能保留边缘、纹理和抗锯齿，拼碎片通常会留下缝隙、毛边和重复像素。
15. 每新增一个 shape/SVG/icon/合并位图替换原图内容，都必须删除或隐藏对应源位图层。不要让“新对象 + 旧碎片”同时叠在一起。
16. 不要运行 `npm install`、不要从网络下载图标包、不要要求用户安装图标依赖。

## 文本图层规则

OCR 文本回写到 PPT 时，文本框尺寸必须按文本语义定义：

- 单行段落、按钮文字、导航项、标签、数字指标：使用自动宽度，文本框宽度跟随内容，不要保留过宽固定框。
- 同一段话被 OCR 成多行、或原图里本来就是多行说明文字：使用固定宽度、自动高度，保持原始换行区域和左/中/右对齐。
- 同一 style 的多行项目列表：每个列表项可以独立文本框，但宽度、字号、颜色、行高和 x 坐标要统一。
- 不同 style 的文字不要强行合并。比如标题和副标题、数字和单位、粗体和浅色说明，应保留为独立文本框。
- 同一段文字不要因为 OCR 分词被拆成多个互相漂移的文本框。若视觉上是一段话，先合并文本，再按单行或多行规则放置。
- 单行中文或英文句子如果原图没有换行，不要为了适配 OCR 框宽主动换行；用自动宽度并保持原基线。
- 多行说明文字必须避免互相重叠。最终 `inspect` 后检查相邻文本框 bbox，发现不合理重叠时调整宽度、高度或 y 坐标。

## 验收要求

返回给用户前必须完成：

1. `inspect` 原始 DeckLens 输出。
2. 逐页建立替换清单，尤其标明被合并的碎片层、复杂位图组和被删除的源位图层。
3. 执行矢量/icon/图表/卡片/背景后处理，或明确判断没有适合目标。
4. `inspect` 最终 PPTX。
5. 完成卡片审计：每页原图卡片数量必须和最终矢量/保留说明对上。
6. 复查最终 PPTX 中没有“被替换源位图 + 新矢量对象”重复叠加。
7. 最终说明包含：
   - 使用的转换模式。
   - 每页替换为 PPT 原生形状的元素。
   - 被手动合并的碎片图层或语义对象；复杂位图组合并后剩余几个图片层。
   - 背景渐变、底部渐变、按钮/卡片渐变的还原方式；如果使用位图保留，要说明保留区域。
   - 纯色背景、卡片、基础图表的重绘情况；卡片未矢量化时必须逐个说明原因。
   - 替换为 SVG/PNG 图标的元素和图标库来源。
   - 保留为位图的元素和原因。
   - 最终 PPTX 路径。

如果没有完成矢量/icon 后处理，不要把结果称为最终版本，只能称为“原始分层结果”。

## 注意事项

- 默认底图清理使用 `--inpaint-backend lama`；简单背景可以用 `--inpaint-backend local_mean`。
- 除非确定当前机器有可用加速后端，否则优先使用 `DECKLENS_DEVICE=cpu`。
- 已存在输出文件不会被替换，除非用户明确允许使用 `--overwrite`。
- 不要直接调用 `decklens_cli.py`。它是产品 CLI 背后的内部后端适配层。
