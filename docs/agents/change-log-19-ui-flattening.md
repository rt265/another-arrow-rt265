# 变更记录 19：UI 扁平化重构

对应 `docs/agents/basic-info.md` 中 Priority 第 15 条：**UI/UX 整体优化：重构 UI 设计，扁平、简洁为上**。

设计与规范见 `docs/agents/explore-15-ui-flattening.md`（本轮先出规范、再按规范实施）。

## 问题：界面靠“渐变 + 投影 + 光晕”制造立体感

到事项 14 为止，界面已经挺好看，但审美上是**拟物**的：背景是竖直渐变 + 一团几乎盖满 720² 的
径向柔光；每一块面板 / 按钮都是“渐变底 + 2px 高光描边 + 4 层柔和投影”；主按钮悬停还会向外
发光；菜单页标题下面垫着一份半透明的金色副本。叠加起来有三个问题：

1. **不够简洁**：一块按钮上同时压着渐变、描边、投影三种手段，信息密度感偏高；
2. **层次口径不统一**：圆角有 20 / 24 / 30 / 22 / 16 与“按钮胶囊（`height // 2`）”六套说法；
3. **样式分散**：渐变色对散在 11 个 `_draw_panel` 调用点里，想加深一点底色要改好几个地方。

## 变更内容

| 文件 | 修改 |
| --- | --- |
| `src/another_arrow_rt265/config.py` | 配色收敛：新增 `COLOR_BACKGROUND (16,20,30)`、`COLOR_BUTTON`（← `COLOR_BUTTON_TOP`）、`COLOR_BUTTON_HOVER`（← `COLOR_BUTTON_TOP_HOVER`）；**删除** `COLOR_BACKGROUND_TOP/BOTTOM/GLOW`、`GLOW_ALPHA`、`COLOR_SHADOW`、`COLOR_PANEL_DEEP`、`COLOR_BUTTON_BOTTOM(_HOVER)`、`COLOR_CARD_TOP/BOTTOM`（面板底统一用 `COLOR_PANEL`）。新增形状口径 `UI_RADIUS = 12` / `UI_BORDER_WIDTH = 1`，`BOARD_RADIUS` 24 → `UI_RADIUS`、`CELL_RADIUS` → `UI_RADIUS` |
| `src/another_arrow_rt265/ui.py` | **删除四个非扁平基元**：`_glow_sprite` / `_background`（整屏渐变 + 柔光）、`_gradient`（渐变底）、`_draw_shadow`（4 层投影）、`_draw_glow`（外发光）；`draw_background(surface)` 改成一次 `fill`，同时去掉 `center` 参数；`_draw_panel` 签名由 `(..., top, bottom, *, radius, border, border_width, shadow, shadow_spread)` 收敛为 `(..., fill, *, radius, border=None, border_width=None)`（内部走 `sprites.blit_round_rect`，1px 描边仍抗锯齿）；`_draw_page_title` 删掉金色副本；11 处调用点逐个改成单色 + `UI_RADIUS`；**信息栏重排**（见下）：新增 `_draw_hud_bar()` / `hud_dividers()`，`hud_chip_rects()` 拆出设计坐标的 `_hud_sections()`，删除 `_draw_chip_frame`；`_result_emblem_sprite` 的底色混色改用 `COLOR_PANEL` |
| `src/another_arrow_rt265/game.py` | `_draw()` 里 `ui.draw_background(screen, board.rect.center)` → `ui.draw_background(screen)`（背景不再需要光心） |
| `src/another_arrow_rt265/sprites.py` | 只改文档：删掉指向已被删除的 `ui._glow_sprite` / `ui._gradient` 的引用 |
| `tests/test_ui.py` | `test_draw_background_paints_a_top_to_bottom_gradient` **改写**为 `test_draw_background_paints_one_flat_color`（四角 + 中心必须完全一致）；**新增 4 条**：`test_hud_is_one_bar_with_three_dividers`、`test_chrome_components_are_flat_without_shadow_or_gradient`、`test_buttons_share_one_corner_radius`、`test_menu_title_has_no_glow_copy` |
| `tests/test_tutorial.py` | `_frame()` 里的 `ui.draw_background(...)` 跟签名同步 |
| `.preview/` | `frame_time.py` **新增**（稳态每帧绘制耗时的测量脚本）；`ui_frames.py` / `window_sizes.py` / `arrow_size.py` / `explore_resize.py` 同步 `draw_background` 签名；`explore_resize.py` 里引用 `_glow_sprite` 的历史探针（`probe_glow`）随基元一起删除 |

## 关键设计

### 一处外观入口，一种颜色

`_draw_panel()` 是所有面板 / 卡片 / 按钮的唯一外观入口。它现在只有两个视觉参数：
`fill`（纯色）与可选的 `border` / `border_width`——**没有渐变、没有投影、没有光晕**。
于是“界面长什么样”收敛成三件事：

```text
背景      = COLOR_BACKGROUND        一次 fill
块         = COLOR_PANEL (+ 1px 描边)   sprites.blit_round_rect
悬停 / 强调 = 换一个填充色（COLOR_BUTTON_HOVER / accent→白 0.18）
```

层次不再靠“浮起来”（投影），而靠**明度差 + 描边**：背景 `(16,20,30)` < 面板 `(36,44,63)` <
按钮 `(54,66,92)`，每一档之间都有 1px 的 `COLOR_PANEL_BORDER` / `COLOR_BUTTON_BORDER` 勾边。
这样即使把窗口放到 1440×900，也不会有“投影糊在渐变上”的脏边。

### 信息栏：四块卡片 → 一条通栏

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ [🏠] │ 关卡 1 / 6 │ 剩余箭头 5 │ 用时 0:00.0 │ 失误 ●●● │ [重新开始]      │
└──────────────────────────────────────────────────────────────────────────┘
```

- 底色 = `COLOR_PANEL` 铺满 `hud_rect()`，底边一条 1px 横线；三条 1px 竖线落在相邻分区正中，
  上下各内缩 6px。横竖线都是轴对齐的，直接用 `pygame.draw.line`（本来就没有锯齿）。
- 分区**不再各自带描边**：一条栏里出现四道边框会互相挤压，反而比卡片更乱。
- 宽度账（设计坐标，恰好 720；末段仍由“重新开始按钮的左边 − 10”倒推）：

  ```text
  32 + 48 + 12 + 92 + (8+1+8) + 92 + (8+1+8) + 122 + (8+1+8) + 89 + 10 + 140 + 32 = 720
  ```

  分区宽度按“最宽的那行字 + 两侧 14px”倒推：用时读数 `99:59.9`（24 号 Bold ≈ 88px）是上限，
  “剩余箭头”四个字是第二段的下限（15 号 ≈ 60px），失误圆点共 58px。
  `_HUD_CHIP_PADDING` 16 → 14 才腾出这些余量；`_HUD_CHIP_GAP` 被“分隔线占位”`_HUD_DIVIDER_SPAN = 17` 取代。
- `hud_chip_rects()` **保持原名与顺序**（关卡 → 剩余箭头 → 用时 → 失误），只是语义从“卡片”变成“分区”；
  它拆成“设计坐标的 `_hud_sections()` + 公开映射”，于是 `hud_dividers()` 能复用同一份几何，
  绘制与测试不会各算一遍。

### 圆角统一，但保留“开关”的例外

八处圆角常量与六处 `rect.height // 2` 全部改成 `viewport.s(config.UI_RADIUS)`。
唯一的例外是辅助线开关的**轨道**（胶囊）与**滑块**（正圆）：形状本身在表达“这是一个开关”，
把轨道改成 12 圆角反而会削弱这个语义。这条例外写在代码注释里。

## 验证

```powershell
uv run pytest -q                       # 412 passed（本轮从 408 增加 4 条）
uv run ruff check . ; uv run ruff format --check . ; uv run ty check   # 全部通过
uv run python .preview/ui_frames.py    # 28 张界面状态图，人工核对
uv run python .preview/window_sizes.py # 4 种窗口尺寸 × 4 个画面
uv run python .preview/run_demo.py     # dummy 下真实主循环 + 点击流，输出“主循环冒烟通过”
uv run python .preview/frame_time.py   # 6×6 + 辅助线全开的稳态中位耗时 0.97 ms/帧
```

同一台机器、同一口径下的前后对比（用 `git stash push -- src/` 临时回退测得）：

| | 中位耗时 | 最慢 |
| --- | --- | --- |
| 扁平化之前 | 1.17 ms/帧 | 1.69 ms |
| **扁平化之后** | **0.97 ms/帧** | 1.11 ms |

省下来的正是“每块面板 4 层投影”和“整屏背景贴图 blit”。

人工看图的核对点：① 背景与面板都是**一块纯色**；② 组件外侧**没有柔和的深色边**；
③ 按钮圆角是 12 而不是半圆；④ 信息栏是**一条**而不是四块；⑤ 1440×900 下通栏仍落在设计框内
（左右留白是背景色，与棋盘、按钮的边界一致）。

## 影响与后续

- **玩法视觉一行未动**：箭头主题色、选中 / 碰撞反馈、辅助线、教程高亮全部保持原样，
  `tests/test_board.py` 的像素级断言（格子中心 == 主题色、圆片留白、辅助线精确色计数）一像素未改地通过。
- **调风格只剩几行**：深浅改 `COLOR_BACKGROUND` / `COLOR_PANEL` / `COLOR_BUTTON`；
  圆角改 `UI_RADIUS`；描边粗细改 `UI_BORDER_WIDTH`。
- **后续可选项**：信息栏高度 104 → 88 会更紧凑，但 `board_area()` 会跟着上移、
  棋盘格子尺寸与“辅助线开关不压格子”的 6px 余量都要重算，本轮按“不动布局常量”处理。
  `_HUD_CHIP_*` 这套名字仍沿用（语义已变成“分区”），改名会牵动测试与 `.preview`，同样留待以后。
