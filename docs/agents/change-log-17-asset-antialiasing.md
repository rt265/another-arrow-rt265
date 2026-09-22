# 变更记录 17：素材抗锯齿（超采样贴图）

对应 `docs/agents/basic-info.md` 中 Priority 第 13 条：**UI 优化：优化图标、字体等素材的
显示效果**。这条事项剩下的最后一块就是本轮的“素材抗锯齿”（字体已在
`change-log-13-bundled-font.md` / `change-log-15-static-font-weights.md` 两轮做完）。

## 问题：没有位图素材，但画面确实是“低分辨率”的

`assets/` 里只有三个 OTF 字体，箭头、图标、面板全是矢量绘制，所以“素材糊”不是图片被
拉大，而是 **`pygame.draw` 画出来的图形完全没有抗锯齿**：一个圆只有“填充色 + 底色”
两种颜色，圆弧与斜边全是台阶。事项 12 的探索已经量过（
`explore-12-window-resize-and-crispness.md`）：`pygame.draw.circle` 2 种颜色、
`gfxdraw.aacircle` 46 种、4× 超采样 16 种；窗口越大、格子越大，台阶越显眼。
上一轮把画布从“钉死的 720²”变成“按窗口等比重绘”，剩下的这一半就是本轮的活。

## 变更内容

| 文件 | 修改 |
| --- | --- |
| `src/another_arrow_rt265/sprites.py` | **新增**：超采样贴图模块 —— `render()`（4× 画布 + `smoothscale`）、`circle()` / `blit_circle()`、`round_rect()` / `blit_round_rect()`、`rounded_mask()`，全部按绘制参数 `lru_cache` |
| `src/another_arrow_rt265/icons.py` | 图标改成 `_sprite(icon, size, color)` 缓存贴图；四个 `_draw_*` 形状函数放宽成浮点坐标（它们现在画在 4 倍画布上），新增 `_draw()` 分发 |
| `src/another_arrow_rt265/board.py` | 底板、格子、圆片描边走 `sprites.blit_round_rect`；新增 `_arrow_sprite()`（圆片 + 描边 + 箭头图形一张贴图，按“格子尺寸 + 朝向 + 三种颜色 + 线宽”缓存）；选中环 / 碰撞环 / 挡住提示环走 `sprites.blit_circle`；飞出动画改成“复制贴图 + `set_alpha`”；火花与辅助线箭头改用 `pygame.draw.aaline`；`_draw_dashed_line(..., smooth=True)` 供斜向的“被谁挡住”虚线使用 |
| `src/another_arrow_rt265/ui.py` | `_gradient` 的圆角蒙版换成 `sprites.rounded_mask`（四角抗锯齿）；投影、主按钮光晕、面板描边、开关轨道、开关滑块、失误圆点、说明圆点、教程高亮环、装饰箭头、结算徽章全部走贴图；新增 `_arrow_glyph_sprite()` / `_result_emblem_sprite()` |
| `tests/test_sprites.py` | **新增**：尺寸、斜边过渡色、圆环中空、圆角蒙版、缓存命中、降档倍数、极小尺寸等 |
| `tests/test_icons.py` | 颜色断言改成“图形内部正好是请求色 + 边缘只允许出现请求色与底色的过渡色”，新增 `test_every_icon_is_anti_aliased` |
| `tests/test_board.py` | 新增 `test_arrow_chips_are_anti_aliased`（数一个格子里出现多少种颜色，硬边只有 3 种，抗锯齿后 57 种） |
| `tests/test_ui.py` | 新增 `test_guide_toggle_knob_edges_are_anti_aliased` |
| `.preview/aa_zoom.py` | **新增**：抗锯齿前后对照图（左硬边 / 右贴图，各放大 4 倍），产出 `.preview/aa-compare.png` |
| `.preview/capture_dist.ps1` | 等窗口的方式从“固定等 4 秒”改成“轮询窗口句柄，最多 20 秒”：刚编出来的 exe 首次启动实测要 8 秒左右，旧写法会误报成“没有窗口” |

## 关键设计

### 只有一条实现思路：超采样 + 缓存

`sprites.render(size, painter)` 的做法是：新建一张 `SUPERSAMPLE`（4）× 大小的带透明通道
画布，让 `painter(canvas, factor)` 把图形按倍数放大画上去，再 `smoothscale` 缩回目标尺寸。
一个像素因此由 4×4 个子像素按覆盖率平均，边缘自然得到过渡色——这与项目里已有的
`ui._glow_sprite()`（48×48 缓存贴图再放大）是同一套思路，只是方向相反。

抗锯齿本身不便宜（探索报告量过：整屏 2× 超采样 ≈ 2.5ms/帧），但**这些图形是静态的**：
同一尺寸 + 同一颜色的圆角矩形在整局游戏里反复出现，缓存之后稳定状态每帧只是一次
`blit`。实测 6×6 棋盘 + 信息栏 + 辅助线全开的一帧是 **1.14ms**（`sprites` 两张缓存分别
命中 482 / 6995 次），比每帧现画一组硬边图形还省。

### 大图形降档，小图形满配

超采样代价按面积走：1440 宽的面板在 4× 下要 4000 万个像素的画布（约 160MB）。因此
`sprites` 里有一条面积上限（`MAX_CANVAS_PIXELS = 4_000_000`），超了就往下减倍数：

| 图形 | 典型尺寸 | 超采样倍数 |
| --- | --- | --- |
| 图标 / 圆点 / 滑块 | 16～48px | 4× |
| 箭头圆片（含箭头图形） | 50～300px | 4× |
| 说明卡片、按钮 | 200～700px | 3～4× |
| 整屏面板 / 结算卡片 | 900px+ | 2～3× |

大图形的圆角与描边本来就长，2× 已经看不出台阶；而小图形（图标、圆点）永远拿得到 4×，
正是它们最需要。

### 哪些地方**故意**保持硬边

- **辅助线的虚线**：辅助线永远是水平或垂直的（箭头只有四个方向），轴对齐的线本来就
  没有锯齿，保持 `pygame.draw.line` 反而更利落——而且 `tests/test_board.py` 是按
  “精确等于线色”的像素个数验证辅助线的，抗锯齿会让这些断言失去意义。被挡住时那条
  斜向虚线用 `smooth=True`，走 `aaline`。
- **渐变、背景**：整屏填色与逐行渐变没有斜边，超采样没有意义。

## 踩到的两个坑

- **SDL `smoothscale` 在大表面上有通道取整**：均匀的 `(240, 240, 240, 255)` 缩回来会
  变成 `(238, 238, 238, 253)`（实测 600×600 贴图）。小贴图（圆片、图标）颜色是精确的，
  因此棋盘那些“取格子中心像素必须是主题色”的断言照旧成立；只有面板描边这类整屏大的
  贴图会有 1～2 级的偏差，肉眼不可见。`tests/test_sprites.py` 对降档贴图因此按
  “±2 且有实体像素”判定。
- **`set_alpha()` 可以与逐像素 alpha 叠加**（pygame-ce 2.5.8 实测：缓存贴图的中心
  255 在 `set_alpha(128)` 后落到 128）。教程呼吸环因此不必每帧重建贴图：半径（取整后
  只有几档）进缓存，透明度改贴图**副本**的整体 alpha。

## 验证

```powershell
uv run pytest -q                      # 407 passed
uv run ruff check . ; uv run ruff format --check . ; uv run ty check
uv run python .preview/aa_zoom.py     # 前后对照图 .preview/aa-compare.png
uv run python .preview/ui_frames.py   # 28 张界面截图（720² + 4 种窗口尺寸）
uv run python .preview/run_demo.py    # dummy 驱动下跑真实主循环冒烟
uv run python .preview/resize_real_window.py   # 真实窗口缩放（scale 1.125）冒烟
uv run python -m nuitka --project     # 打包（含新增模块，数据文件校验通过）
& .preview/capture_dist.ps1           # 产物冒烟：标题 Another Arrow、关窗退出码 0
```

`.preview/aa-compare.png` 是同几何的左右对照（左：改之前的 `pygame.draw`，右：贴图）：
圆片圆弧、箭头斜边、房子屋顶与门、面板圆角的台阶在右侧全部消失。

稳态开销（`SDL_VIDEODRIVER=dummy`，6×6 棋盘 + 信息栏 + 辅助线全开，120 帧平均）：
**1.14ms/帧**，`sprites` 的圆 / 圆角矩形两张缓存分别命中 482 / 6995 次。切窗口尺寸时
首帧要重建贴图，实测 900×1440 那档是 **8.3ms**（同一档已经建过就更快），
换成新尺寸才会再建一次。

## 后续

- 图标仍然是代码绘制（`icons.py`），只是画法换成了贴图；如果以后要换成图标字体或
  矢量资源，只需要替换 `icons._sprite()` 里的实现，`draw_icon()` 的调用方不用动。
- 新增图形时优先走 `sprites.blit_circle / blit_round_rect`；只有形状复杂到需要多处
  拼接时，才在调用方写一个 `@functools.lru_cache` 的贴图函数（`_arrow_sprite` /
  `_result_emblem_sprite` 是范例），键里要包含**所有**影响画面的参数（含线宽与颜色）。
