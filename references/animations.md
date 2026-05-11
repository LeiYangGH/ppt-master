# 页面切换与逐元素动画

PPT Master 导出的 PPTX 支持**页面切换**（页与页之间）和**逐元素入场动画**（页内元素）。两者都由 `svg_to_pptx.py` 的 CLI 参数控制，输出为真实 OOXML，可在 PowerPoint 和 Keynote 中播放，不是嵌入视频。

## 默认值

| 层级 | 默认值 | 说明 |
|---|---|---|
| 页面切换 | `fade`，0.4 秒 | 稳妥、通用 |
| 逐元素动画 | `mixed` + `after-previous` | 进页后自动级联播放，无需点击 |

如需改设置，直接对同一份 `svg_output/`（或 `svg_final/`）重新运行 `svg_to_pptx.py` 即可，无需重新跑 LLM。若要完全关闭逐元素动画，传 `-a none`。

## 页面切换

```powershell
# 使用其他切换效果
python scripts/svg_to_pptx.py <project> -t push --transition-duration 0.6

# 关闭切换
python scripts/svg_to_pptx.py <project> -t none

# 每 5 秒自动翻页（展台/轮播）
python scripts/svg_to_pptx.py <project> --auto-advance 5
```

可用效果：`fade`、`push`、`wipe`、`split`、`strips`、`cover`、`random`。

参数：

- `-t/--transition`：切换效果名，或 `none` 关闭。默认 `fade`。
- `--transition-duration`：时长，单位秒，默认 `0.4`。
- `--auto-advance`：自动翻页秒数；不传则由演讲者手动翻页。

## 逐元素动画

默认开启（`mixed` + `after-previous`）。共有三种开始方式，对应 PowerPoint 动画面板中的 “Start”：

- **`on-click`**：进入页面后，第一次点击显示第一个语义组；之后每点一次显示下一个。适合现场演示。
- **`with-previous`**：所有组在进页时同时开始播放；忽略 stagger。
- **`after-previous`**（默认）：第一个组进页即播，后续组在前一个结束后依次级联，并附加 `--animation-stagger` 间隔。适合轮播、录屏或不想点击的场景。

```powershell
# 默认行为：mixed + after-previous
python scripts/svg_to_pptx.py <project>

# 完全关闭逐元素动画
python scripts/svg_to_pptx.py <project> -a none

# 固定使用一种效果
python scripts/svg_to_pptx.py <project> --animation fade

# 切为点击触发
python scripts/svg_to_pptx.py <project> --animation-trigger on-click

# 自定义节奏
python scripts/svg_to_pptx.py <project> --animation mixed \
        --animation-stagger 0.6 --animation-duration 0.5

# 所有组同时播放
python scripts/svg_to_pptx.py <project> --animation-trigger with-previous
```

共 22 种单一效果：`appear`、`fade`、`fly`、`cut`、`zoom`、`wipe`、`split`、`blinds`、`checkerboard`、`dissolve`、`random_bars`、`peek`、`wheel`、`box`、`circle`、`diamond`、`plus`、`strips`、`wedge`、`stretch`、`expand`、`swivel`。另有两种自动模式：

- `mixed`：确定性。每页第一个动画组用 `fade`，之后从精选效果池轮换。
- `random`：从同一效果池随机抽取。

效果池不包含 `appear`，因为它没有明显运动感。

参数：

- `-a/--animation`：效果名、`mixed`、`random` 或 `none`。默认 `mixed`。
- `--animation-trigger`：开始方式：`on-click`、`with-previous`、`after-previous`（默认）。
- `--animation-duration`：单个元素入场时长，默认 `0.3` 秒。
- `--animation-stagger`：`after-previous` 模式下元素间隔，默认 `0.4` 秒；其他模式忽略。

## 锚点逻辑：顶层 `<g id="...">`

逐元素动画以 SVG 中**顶层 `<g id="...">` 内容组**为锚点（如 `<g id="cover-title">`、`<g id="card-1">`）。一个组对应一次显示。

建议每页有 **3–8 个内容组**。这也正是 PowerPoint 里更好选中、移动、编辑的粒度。

**页面装饰组会自动跳过级联。** 像背景、页眉页脚、装饰、水印、页码这类顶层组不会进入点击/级联序列，而是随整页一起出现。判断依据是 `id` 按 `-`、`_` 拆分后是否包含 `background`、`bg`、`decoration`、`decorations`、`decor`、`header`、`footer`、`chrome`、`watermark`、`pagenumber`、`pagenum`。会自动跳过的示例：`<g id="background">`、`<g id="bg-texture">`、`<g id="cover-footer">`、`<g id="p03-header">`、`<g id="bottom-decor">`、`<g id="watermark">`。仍会参与动画的示例：`<g id="card-1">`、`<g id="cover-title">`、`<g id="step-discover">`。不要为了避开动画去掉 `<g>`，只需正确命名。

**扁平 SVG 的兜底逻辑**（没有顶层 `<g>`，只有根级 `<rect>` / `<text>` / `<path>`）：

- 可见顶层图元 ≤ 8：每个图元作为一个锚点。
- > 8：该页跳过入场动画，但仍能正常显示。

不论是否打算做动画，Executor 都应把逻辑区域包进 `<g id>`。`shared-standards.md` 已强制要求。

## 限制

- **仅适用于原生形状模式。** 逐元素动画需要可编辑形状锚点。`--only legacy` 会把每页做成一张图片，无法做到元素级动画；该模式只响应 `-t/--transition`，不响应 `-a/--animation`。
- **不同 Office 版本的元素动画可能略有差异。** 效果通过 `<p:animEffect filter=...>` 实现，而不是靠 `presetID` 查表，以提高跨版本稳定性。PowerPoint 2016+ 基本一致；更老版本可能退化成普通 `Appear`。
- **PNG 兼容回退只影响视觉渲染。** 页面切换和动画写在 slide XML 中，不在 PNG 内，所以关闭 compat mode 不会影响两者。

## 快速参考

| 目标 | 命令 |
|---|---|
| 关闭页面切换 | `-t none` |
| 切换效果改为其他 | `-t push` |
| 放慢切换 | `--transition-duration 0.8` |
| 自动播放 | `--auto-advance 5` |
| 关闭逐元素动画 | `-a none` |
| 改为点击触发 | `--animation-trigger on-click` |
| 使用固定效果而非 mixed | `--animation fade` |
| 所有组同时播放 | `--animation-trigger with-previous` |
| 放慢元素入场 | `--animation-duration 0.5` |
| 增大 after-previous 间隔 | `--animation-stagger 0.8` |

