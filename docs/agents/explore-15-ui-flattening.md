# 事项 15 探索：UI/UX 整体优化的“扁平化”设计规范

> 事项 15 原文：**UI/UX 整体优化：重构 UI 设计，扁平、简洁为上**。
> 本轮先做探索与设计（含现状盘点与规范定稿），结论已由用户确认，
> **实现记录见 `change-log-19-ui-flattening.md`**；本文件是那次重构的依据与口径说明。

## 0.1 用户确认的决策（2026-09-22）

| 问题 | 决定 |
|---|---|
| 扁平化力度 | **彻底扁平**：背景也改纯色，同步改掉“背景必须是竖直渐变”那条测试 |
| 信息栏结构 | **合并为一条整宽信息栏**，内部用细分隔线分区（不再四块独立卡片） |
| 圆角 | **全部统一为中等圆角 12**，按钮不再是胶囊 |
| 装饰元素 | **全部保留**，只改材质（纯色化）——只去掉“材质”，不减“元素” |
| 配色 | 保持现有深蓝底 + 金色强调色，只去掉渐变与高光 |

## 0. 结论速览

现状的“不扁平”集中在一个很小的集合里——**四个基元 + 一组双色常量**：

| 立体手法 | 实现 | 覆盖范围 | 扁平化做法 |
|---|---|---|---|
| 整屏渐变 + 径向柔光 | `_background()` / `_glow_sprite()`（432px 光斑，几乎盖满 720²） | 每一个画面 | 背景改**单一纯色**，删掉两个函数 |
| 面板 / 按钮的渐变底 | `_gradient()`（逐行混两个颜色 + 圆角蒙版） | **11 处** `_draw_panel` 调用点 | 一个角色只留**一种颜色**，改走 `sprites.blit_round_rect` |
| 4 层柔和投影 | `_draw_shadow()`（同心圆角矩形 + 向下偏移 3px） | 约 10 个组件 | 删除；层次改由“明度差 + 1px 描边”表达 |
| 外发光 / 文字光晕 | `_draw_glow()`（主按钮悬停）、标题的金色副本（alpha 80，下移 4px） | 主按钮 + 页面标题 | 删除；悬停只换填充色 |

一句话：**这不是“换个色板”，而是“把制造立体感的三层手段（渐变 / 投影 / 光晕）整体去掉，
只留下形状与明度”**。因此改动集中在 `config.py` 的“界面”配色与 `ui.py` 的基元层，
棋盘的箭头、辅助线、教程高亮这些“玩法视觉”一行都不用动。

## 1. 扁平化规范（重构后的口径）

### 1.1 色板：一个角色一种颜色

| 角色 | 常量 | 新值 | 取代 |
|---|---|---|---|
| 窗口背景 | `COLOR_BACKGROUND` | `(16, 20, 30)` | `COLOR_BACKGROUND_TOP/BOTTOM`、`COLOR_BACKGROUND_GLOW`、`GLOW_ALPHA` |
| 面板底（信息栏 / 卡片 / 圆牌 / 结算卡片 / 教程条） | `COLOR_PANEL` | `(36, 44, 63)` | `COLOR_PANEL_DEEP`、`COLOR_CARD_TOP/BOTTOM` |
| 面板描边 / 分隔线 | `COLOR_PANEL_BORDER` | `(62, 77, 108)` | 原值不变（同时兼作信息栏分隔线与底边） |
| 次要按钮底 | `COLOR_BUTTON` | `(54, 66, 92)` | `COLOR_BUTTON_TOP` |
| 次要按钮悬停 | `COLOR_BUTTON_HOVER` | `(70, 86, 118)` | `COLOR_BUTTON_TOP_HOVER` |
| 按钮描边 / 文字 | `COLOR_BUTTON_BORDER` / `COLOR_BUTTON_TEXT` | 原值不变 | — |
| 强调色（主按钮 / 标题装饰） | `COLOR_PRIMARY` `(255,196,74)` + `COLOR_ON_PRIMARY` | 原值不变 | — |
| 遮罩 | `COLOR_OVERLAY (8,11,18)` + `OVERLAY_ALPHA 200` | 原值不变 | **保留**：它是“本关结束”的功能反馈，不是装饰 |

删除：`COLOR_SHADOW`、`COLOR_BUTTON_BOTTOM`、`COLOR_BUTTON_BOTTOM_HOVER`。

**不动**的色：棋盘三色、箭头的主题色与圆片推导（`palette.py`）、选中 / 碰撞 / 阻挡提示、
辅助线两色、开关轨道与滑块、成功 / 失败、失误红点、计时蓝、三级文字色。
理由：它们要么是玩法语义，要么被 `tests/test_board.py` 的**像素级断言**钉住。

主按钮（强调色填充）的三种状态：

| 状态 | 旧 | 新 |
|---|---|---|
| 常态 | 渐变 `accent→白 0.14` / `accent→黑 0.26`，描边 `accent→白 0.35` | **纯 `accent`**，描边 `accent→黑 0.28` |
| 悬停 | 渐变 `0.28 / 0.10` + 白 0.35 描边 + **外发光** | **纯 `accent→白 0.18`**，描边不变（无发光、面积不变） |

### 1.2 形状：统一圆角 12 + 1px 描边

新增两个常量作为唯一口径：`config.UI_RADIUS = 12`、`config.UI_BORDER_WIDTH = 1`。

| 组件 | 旧圆角 | 新圆角 |
|---|---|---|
| 统计卡片（`_HUD_CHIP_RADIUS`） | 20 | `UI_RADIUS` |
| 说明卡片（`_SECTION_RADIUS`） | 24 | `UI_RADIUS` |
| 结算卡片（`_CARD_RADIUS`） | 30 | `UI_RADIUS` |
| 教程提示条（`_TUTORIAL_BAR_RADIUS`） | 22 | `UI_RADIUS` |
| 装饰箭头圆牌 | 16 | `UI_RADIUS` |
| 全部按钮（次要 / 图标 / 主 / 紧凑） | `rect.height // 2`（胶囊） | `UI_RADIUS` |
| 棋盘底板 `BOARD_RADIUS` | 24 | `UI_RADIUS` |
| 格子 `CELL_RADIUS` | 12 | `UI_RADIUS`（不变） |

**唯一例外**：右下角“辅助线”开关的**轨道**（胶囊）与**滑块**（正圆）——它们是开关语义，
形状本身在表达“这是一个开关”，因此不参与统一圆角。开关的**外框**仍按 `UI_RADIUS`。

描边宽度也统一：面板默认 `UI_BORDER_WIDTH`（原来是 2px，结算卡片 3px）。
棋盘上的选中环 / 碰撞环 / 教程呼吸环**不在此列**——它们是叠在格子上的功能标记，宽度 2~3px 是刻意的。

### 1.3 信息栏：四块卡片 → 一条通栏

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ [🏠] │ 关卡  1 / 6 │ 剩余箭头  5 │ 用时  0:00.0 │ 失误  ●●● │ [重新开始] │
└──────────────────────────────────────────────────────────────────────────┘
  32   48    12   └──────────── 3 条 1px 竖直分隔线 ────────────┘  10   140    32
```

- 底色 = `COLOR_PANEL` 铺满 `hud_rect()`（设计框宽度 × 104），底边一条 1px `COLOR_PANEL_BORDER`；
  三条分隔线落在相邻分区的正中间，上下各内缩 6px（“把这一栏分开”而不是“切断”）。
- 分区只保留文字与失误圆点，**不再各自带描边**——否则一条栏里会出现四道边框互相挤压。

宽度账（设计坐标，必须恰好 720）：

```text
32 + 48 + 12 + 92 + (8+1+8) + 92 + (8+1+8) + 122 + (8+1+8) + 89 + 10 + 140 + 32 = 720
     home       关卡        分隔线      剩余箭头    分隔线      用时     分隔线   失误  重开
```

分区宽度按“最宽的那行字 + 两侧 14px 留白”倒推：用时读数是上限（`99:59.9` 24 号 Bold ≈ 88px）、
“剩余箭头”四个字决定第二段下限（15 号 ≈ 60px）、失误圆点共 58px。`_HUD_CHIP_PADDING` 由 16 收到 14
才腾出这些余量；末段宽度仍由“重新开始按钮的左边 − 10”倒推，因此按钮宽度变化时它会自动伸缩。

### 1.4 保留不动的“玩法视觉”

箭头圆片与彩色主题色、选中呼吸环、碰撞红环与火花、辅助线（虚线 / 终点标记 / 开关配色）、
教程呼吸环与挡路红环、失误圆点、结算遮罩与徽章——**全部保持原样**。它们要么是判定反馈，
要么是可选功能的开关状态，去掉或换风格都会削弱可读性。

## 2. 落点清单（改哪里）

**集中修改点（约 80% 的观感来自这 6 处）**

| 位置 | 处理 |
|---|---|
| `ui._glow_sprite` / `ui._background` | 删除；`draw_background(surface)` 改为整屏 `fill(config.COLOR_BACKGROUND)` |
| `ui._gradient` | 删除；面板底改走 `sprites.blit_round_rect`（缓存键从“尺寸+两色+圆角”变成“尺寸+单色+圆角”） |
| `ui._draw_shadow` | 删除（连同 `shadow` / `shadow_spread` 参数与 `_SHADOW_SPREAD`） |
| `ui._draw_glow` | 删除（连同 `_GLOW_SPREAD`） |
| `ui._draw_panel` | 签名由 `(surface, rect, top, bottom, *, radius, border, border_width, shadow, shadow_spread)` 收敛为 `(surface, rect, fill, *, radius, border=None, border_width=None)` |
| `ui._draw_page_title` | 删掉金色副本（`_PAGE_GLOW_ALPHA`） |

**散落修改点（逐个改）**：11 处 `_draw_panel` 调用点（次要 / 图标 / 主 / 紧凑按钮、装饰圆牌、
说明卡片、开关、教程条、结算卡片）+ 被删掉的 `_draw_chip_frame` + `_result_emblem_sprite` 的底色混色；
8 个圆角常量 + 6 处 `rect.height // 2`；`draw_background` 的 6 个调用点
（`game.py`、`tests/test_tutorial.py`、`.preview/{ui_frames,window_sizes,arrow_size,explore_resize}.py`）。

## 3. 约束与风险（改之前必须知道的）

**会被“改颜色 / 改形状 / 改坐标”撞到的测试**

- `tests/test_board.py`：格子中心像素 **必须正好等于箭头主题色**、圆片外沿的留白 = `格子内边宽 × (0.5 − ARROW_CHIP_RATIO)`、
  格子底色必须纯 `COLOR_CELL`（圆片外不许有投影 / 阴影）、辅助线按**精确颜色计数**。
  → 所以箭头与棋盘**不能**加渐变、投影或整体 alpha。
- `tests/test_ui.py::test_guide_toggle_shows_both_positions`：开关轨道必须是**该纯色块**
  （渐变 / 蒙版 / 半透明一律失败）；`_color_hits` 按精确颜色计数。
- `tests/test_icons.py`：图标颜色只能是请求色与背景的**等比混合**，且不许越出尺寸框 → 图标不能带投影 / 外发光。
- `tests/test_ui.py` 的布局硬约束：信息栏整行恰好 720（`test_hud_row_fills_the_window_exactly`）、
  计时分区放得下最长读数、辅助线开关不压任何格子（6×6 只剩 6px 余量）、
  教程提示条与第 1 关棋盘底板只差 2px。
  → 所以 `HUD_HEIGHT` / `HUD_PADDING` / `BOARD_MARGIN` / `BOARD_TOP_GAP` **一律不动**：
  动它们会连锁改变棋盘格子的尺寸与位置。

**安全区**：`COLOR_PANEL*` / `COLOR_BUTTON*` / `COLOR_SHADOW` / `COLOR_CARD_*` / `COLOR_BACKGROUND_*`
这些 chrome 色**不被任何像素断言引用**，是扁平化时唯一能自由改的一组。

**测试要跟着改的**：`test_draw_background_paints_a_top_to_bottom_gradient` —— 它断言
“背景自上而下由亮转暗”，与“背景改纯色”直接冲突，必须改写成“背景是一块纯色”。

## 4. 怎么验证

```powershell
uv run pytest -q                       # 412 passed
uv run ruff check . ; uv run ruff format --check . ; uv run ty check
uv run python .preview/ui_frames.py    # 28 张界面状态图，人工核对
uv run python .preview/window_sizes.py # 4 种窗口尺寸 × 4 个画面，查非等比留白
uv run python .preview/run_demo.py     # dummy 下跑真实主循环与点击流
uv run python .preview/frame_time.py   # 稳态每帧绘制耗时（6×6 + 辅助线全开）
```

人工看图时按这四条核对：① 背景与面板都是**一块纯色**、没有明暗过渡；② 组件外侧**没有柔和的深色边**
（旧投影）；③ 按钮圆角是 12 而不是半圆；④ 信息栏是**一条**而不是四块。

## 5. 顺带的效果（不是目标，但值得记一笔）

- **每帧更省**：面板不再各叠 4 层投影、背景从“整屏缓存贴图 blit”变成一次 `fill`。
  同一台机器、同一口径（6×6 + 辅助线全开）实测稳态中位耗时 **1.17 ms → 0.97 ms/帧**。
- **缓存更简单**：面板贴图从“尺寸 + 两个颜色 + 圆角”降到“尺寸 + 一个颜色 + 圆角”，
  `_gradient` / `_background` / `_glow_sprite` 三份缓存整体消失。
- **改风格只剩一处**：想调深浅只改 `COLOR_BACKGROUND` / `COLOR_PANEL` / `COLOR_BUTTON` 三行；
  想调“圆一点还是方一点”只改 `UI_RADIUS`。
