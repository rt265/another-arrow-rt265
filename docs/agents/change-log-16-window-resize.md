# change-log 16：窗口自由缩放（事项 12 前半）

> 事项 12 原文：*UI/UX 修复：游戏内素材的低分辨率、无法自由更改窗口大小*。
> 本轮只做**窗口缩放**那一半（用户确认“分两步”）；“素材清晰度”那一半的根因是
> **完全没有抗锯齿**（实测一个圆只有 2 种颜色），留到下一轮用超采样贴图解决，
> 调查与方案见 `explore-12-window-resize-and-crispness.md`。

## 做了什么

窗口现在可以随便拖边、最大化：界面整体**等比放大并居中**，文字与图形都是照着目标尺寸
**重画**的（不是把 720² 的画面拉大），所以窗口越大越清楚。拖窗口不会打断关卡：箭头布局、
失误次数、本关用时、教程进度与结算状态全部保留。

- **窗口尺寸 = 设计尺寸（720×720）时逐像素不变**：`Viewport.fit` 在这种情形下给出
  `scale = 1.0, origin = (0, 0)`，`s()` / `x()` / `y()` / `rect()` 全是恒等变换，
  因此既有布局与 345 条旧测试一条都不用改。
- 长宽比与 720×720 不一致时（横幅、竖屏）**留白**，背景照旧铺满整窗，界面元素居中。
- 窗口比设计尺寸还小时**不缩小内容**（`config.MIN_SCALE = 1.0`），居中后裁掉超出部分：
  设计尺寸下的字号与格子尺寸是下限，再小就该重新排版而不是缩放了。

## 改法

### 新增 `src/another_arrow_rt265/viewport.py`

`Viewport`（`size` / `scale` / `origin`）负责“设计坐标 ↔ 屏幕坐标”，外加一个模块级的
“当前视口”（`set_current()` / `current()` / `reset()`，以及 `s()` / `x()` / `y()` /
`point()` / `rect()` / `map()` / `scaled()` 这些快捷函数）。这个模块只依赖 `config` 与
`pygame`，所以 `ui` 与 `board` 都能引它而不会绕出循环依赖。

**约定（很重要，新写绘制代码时照做）**：

1. 布局常量一律按设计尺寸写成绝对值；
2. **几何函数**（`ui.board_area()`、`ui.menu_layout()`、`Board.cell_rect()` …）返回**屏幕坐标**；
3. 绘制里遇到**设计长度**（半径、留白、行距、线宽、字号）就用 `viewport.s()` /
   `viewport.scaled()` 现算；由矩形派生的值（`rect.height // 2`、`rect.width * 0.46`）
   本来就是像素，**不要**再换算一次。

`scale` 取 `min(w/720, h/720)` 并**向下取整到 1/16 档**（`config.SCALE_STEP`）：拖拽窗口时
中间尺寸无穷多，量化后按尺寸缓存的贴图 / 字体不会每个中间值各长一份；向下取整保证设计框
永远放得进窗口。`k/16` 的倍数是二进制精确的，量化不会累积浮点误差。

### `ui.py`

- 几何层改成“**先在设计坐标里排好，再统一映射**”：`_hud_home_button()` / `_restart_button()` /
  `_stack_sections()` / `_hero_row_rects()` / `_footer_row_rects()` / `_overlay_card()` 全是
  设计坐标，公开函数（`hud_chip_rects()` / `restart_button_rect()` / `menu_layout()` /
  `overlay_card_rect()` …）用 `viewport.map()` 交出屏幕坐标。**信息栏“整行恰好铺满”这类算账
  因此仍在设计单位里算**，不会因为取整露出缝隙（`Viewport.rect()` 对左右 / 上下边界分别取整，
  `test_adjacent_rects_stay_flush` 钉住这一点）。
- 绘制层在设计常量与像素交界处补 `viewport.s()`；`_draw_cell_ring()` 与 `_draw_dashed_line()`
  把 `grow` / `dash` / `gap` / `width` 当作设计长度在内部换算，调用方不必逐个改。
- `_TextStyle.font()` 现在返回“**实际字号**”的字体（`_font(viewport.s(size), weight)`），
  因此窗口放大后文字是按更大字号重新渲染的。`_font` 从 `functools.cache` 改成
  `lru_cache(maxsize=96)`：字号会随窗口连续变化，无上限缓存会一路长下去。
- `_draw_shadow` / `_draw_glow` / `_draw_panel` 的 `spread` / `shadow_spread` 默认值改成
  `None`（表示“取 config 里的设计值并按视口换算”），显式传入的值一律由调用方换算成像素。

### `board.py`

- 格子尺寸上限 `config.MAX_CELL_SIZE` 跟着视口放大（`viewport.s(...)`），所以窗口变大时
  棋盘确实会变大，而不是“窗口大了、棋盘还是原来那么大”。
- 抽出 `_layout(area)` 与 `panel_rect`（底板区域，原先在 `draw` / `guide_line` /
  `_fly_out_distance` 里各 inflate 了一遍）。
- 新增 `Board.reshape(area)`：只重算 `cell_size` / `rect`，**不动任何规则状态**
  （箭头、选中、碰撞提示都保留）；飞出动画记的是像素坐标，缩放后不再成立，直接清空
  （它只持续 0.32 秒，看不出中断）。
- 圆片描边 / 光环 / 火花 / 辅助线的线宽与虚线长短、圆角、间隙全部走视口。

### `session.py` / `game.py`

- `Session.resize(area)`：更新 `area` 并让棋盘就地改形，关卡进度、失误、计时、教程与
  结算状态都不动。
- `game.py`：`set_mode(config.WINDOW_SIZE, pygame.RESIZABLE)`；主循环每帧调用
  `_sync_window_size()` —— 比对 `pygame.display.get_surface().get_size()` 与当前视口，
  变了才重建视口、刷新 `self.screen` 并让会话重摆棋盘（返回是否真的换了尺寸，便于测试）。
  **从“当前尺寸”反推而不是只听事件**：拖边、最大化、系统改缩放都会改变尺寸，
  这样最稳；`VIDEORESIZE` / `WINDOWRESIZED` 事件也接了，只是同样走这条路径。
- 顺手把 `set_mode` 的尺寸换成 `config.WINDOW_SIZE`（新增，等于原来的 720×720）。

## 测试

- 新增 `tests/test_viewport.py`（9 条）：设计尺寸恒等、放大、横幅 / 竖屏居中、下限、
  量化（含“设计框放得进窗口”）、相邻矩形不裂缝、`map == rect`、模块级视口的 set/reset。
- `tests/test_ui.py` 新增“窗口缩放”一节，用 `WINDOW_SIZES = ((720,720), (1080,1080),
  (1440,900), (900,1440))` 参数化：信息栏整行仍然左贴齐 / 右贴齐、棋盘区域等比且留在设计框内、
  菜单页各块居中不越界、**“辅助线开关不压任何格子”在 4 个尺寸下都成立**、
  文字确实按更大字号重画（宽度 ≈ 2 倍）、小于设计尺寸时尺寸不变、背景铺满整窗。
- `tests/test_board.py` +3：`reshape` 保留箭头 / 选中与碰撞提示、丢掉飞出动画。
- `tests/test_session.py` +2：缩放保留全部进度（失误 / 箭头 / 计时 / 进行中）、
  结算界面弹着时缩放不丢成绩。
- `tests/test_game.py` +5：缩放保留进度且格子变大、缩放后按新坐标点击仍然有效、
  `VIDEORESIZE` 事件走同一条路、尺寸没变时**不重建棋盘**、教程提示条跟着视口。
- `tests/conftest.py` 新增 autouse fixture：每个用例结束时 `viewport.reset()`，
  免得某个用例改过的窗口尺寸泄漏到下一个用例。
- 全量 **386 条**通过；`ruff format` / `ruff check` / `ty check` 全绿。

## 验证

- `.preview/window_sizes.py`（新增）：按 720²、1080²、1440×900、900×1440 四种窗口离屏渲染
  游戏画面 / 开始界面 / 关于界面 / 教程 / 结算，并打印 `scale`、`origin`、格子尺寸与信息栏右端。
- `.preview/run_demo.py` 增加一段真实缩放：`set_mode` + 投递 `VIDEORESIZE` → 断言 1.5 倍视口、
  格子变大、失误与教程状态不变 → 在新几何下继续点击 → 拖回 720² 复原。主循环冒烟通过。
- `.preview/resize_real_window.py`（新增）：在**真实显示驱动**下跑 2 秒，用
  `pygame.window.Window.from_display_module().size = (1100, 820)` 触发一次真正的窗口缩放
  （等价于用户拖边），实测 `scale=1.125`、`origin=(145, 5)`、格子 `112 → 126`，进度不变。
  这条会短暂弹窗，因此不进测试套件，只作为人工冒烟。
- 既有 21 张 `.preview/*.png`（720×720）重新生成后与改动前肉眼一致。

## 遗留 / 下一轮

- **素材清晰度（事项 12 后半）**：`pygame.draw.circle` / `polygon` / `rect` 没有抗锯齿
  （实测一块画布上只有 2 种颜色），箭头圆片与箭头斜边是硬锯齿。方案已写在探索文档里：
  箭头部件改成 4× 超采样后缩小的离屏贴图（按半径 / 主题色 / 状态 / 方向缓存），
  与现有 `_glow_sprite()` 同一手法；面板圆角（`border_radius`）优先级最低。
- **HiDPI**：本机是 100% 缩放（`dist_window.png` 实测 740×768），无法就地复现系统位图放大。
  若别的机器上发糊，可设置 `SDL_WINDOWS_DPI_AWARENESS=permonitorv2` 环境变量（SDL 直接读该 hint）
  让窗口按原生像素渲染——这不会改变现在的渲染管线。
- `pygame.display` **没有** `set_window_minimum_size`（pygame-ce 2.5.8），所以“最小窗口”
  只能靠 `MIN_SCALE` 逻辑兜住；真要限制窗口极限尺寸得走 `ctypes` 调 Win32，跨平台很差，没做。
