# Main Agent Workflow

Use this workflow when the current environment supports subagents and the user provides multiple pages, multiple images, or a multi-page PDF.

Before using this file, read `workflows/quality-rules.md`. That file is the full quality contract.

## Role

The main Agent is the coordinator. It must not casually process every page itself. It owns:

- Task decomposition.
- Passing complete page instructions to subagents.
- Final integration.
- Final `inspect`.
- Acceptance or rework decisions.

## Required routing

1. Resolve the current skill root directory. The required rule files are:

```text
<skill-root>/workflows/quality-rules.md
<skill-root>/workflows/subagent-page.md
```

2. Create or locate the DeckLens review assets and page images.
3. Assign each page to a subagent. Each subagent prompt must include:

- Page number.
- Original page image path.
- Review directory or page-specific review assets.
- The exact path to `workflows/quality-rules.md`.
- The exact path to `workflows/subagent-page.md`.
- Output paths for the page result and any generated icon/SVG/PNG assets.
- Requirement to read `workflows/subagent-page.md` directly before doing page work.

Subagent prompt template:

```text
你负责 DeckLens 第 <page> 页。

必须先读取这两个规则文件：
1. <skill-root>/workflows/quality-rules.md
2. <skill-root>/workflows/subagent-page.md

输入：
- 原图：<page-image>
- 审阅资料：<review-dir-or-assets>
- 输出目录：<page-output-dir>

任务：
1. 基于原图语义检查程序分层是否合理。
2. 手动合并复杂图片碎片，手动拆分或重建被合进图片里的扁平对象。
3. 扁平 icon 必须通过 DeckLens icon 库替换；禁止 emoji/Unicode/文本冒充 icon，也禁止自己手绘扁平 icon。
4. 只重绘柱状图和条形图，其他图表默认保留位图。
5. 矢量/shape 绘制范围仅限独立矩形、圆形、卡片/按钮容器、分割线和 icon 库输出。箭头、手绘样式、复杂装饰、复杂图片内部色块、logo、截图和非柱状/条形图不要强行拆绘。
6. 不要把 logo、截图、照片、3D、复杂插画、复杂图表强行 SVG 化。
7. 删除所有被替换的源图片层，并保持原图层顺序。
8. 如果该页有合规范围内扁平候选但没有生成任何合规 shape/SVG/icon/vector 对象，该页直接失败。
9. 返回页级质量审计表、替换清单、删除源图层清单、保留位图原因、图层顺序检查和自检结论。
```

## Main Agent acceptance

After subagents return, the main Agent must validate every page. Do not accept a page with vague statements such as “已优化” or “已检查”.

Every page result must include:

- Page owner / subagent id.
- Quality audit table.
- Replacement list.
- Source image layer deletion list.
- Flat element forced redraw results.
- Manual split/merge results.
- Remaining bitmap reasons.
- Self-check conclusion.

Fail a page if:

- The subagent did not read or cite both `workflows/quality-rules.md` and `workflows/subagent-page.md`.
- The page has flat icon candidates but no DeckLens icon find/render results. Hand-drawn icon replacements, emoji, Unicode and text substitutes are never acceptable. If no library match exists, preserve the original bitmap/crop and record the reason.
- The page uses emoji, Unicode symbols, font symbols or plain text as icons.
- The page has bar/column chart candidates but no redraw.
- The page redraws non-bar charts without explicit user request.
- The page has standalone flat rectangle/circle/background candidates still kept as ordinary pictures.
- A rebuilt rectangle/card/button container changes original size, corner radius, fill, border or shadow arbitrarily.
- The page has approved in-scope flat candidates but the final page has zero generated shape/SVG/icon/vector objects.
- The page overvectorizes screenshots, logos, photos, 3D, complex illustrations or complex charts.
- The page vectorizes arrows, hand-drawn marks, complex decorations or other non-basic shapes outside the icon-library path.
- The rebuilt card does not match original radius, fill, border, shadow or gradient closely enough.
- A complex single image is still split into multiple selectable pictures.
- New shape/SVG/icon objects were added but corresponding source picture layers were not deleted.
- Replacement object layer order changes original visual stacking.
- The audit table has candidates but no matching completion counts or explicit reasons.

## Integration

1. Combine page outputs in original page order.
2. Run final `inspect` on the combined PPTX.
3. Verify page count and order.
4. Verify every page still satisfies the subagent acceptance rules.
5. Send failed pages back to the same subagent or a new subagent for rework.

## Final response

Report:

- Final PPTX path.
- Per-page subagent owner and acceptance status.
- Per-page audit summary.
- Manual split/merge summary.
- Flat icon/bar-chart/shape/background redraw counts.
- Non-bar chart/logo/screenshot/photo/3D/complex illustration preserve decisions.
- Icon library or SVG/PNG sources.
- Card style match and layer order check.
- Remaining bitmap reasons.
- Any pages that failed and were reworked.

Do not call the result final if any page remains in a failed state.
