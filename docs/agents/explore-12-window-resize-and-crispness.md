# 事项 12 探索：游戏内素材的“低分辨率”与“无法自由更改窗口大小”

> 本轮先做探索与方案设计（未改动游戏代码），结论已由用户确认，**后半部分已按下面的
> “决策”实现**，实现记录见 `change-log-16-window-resize.md`。
> 事项 12 的原文：*UI/UX 修复：游戏内素材的低分辨率、无法自由更改窗口大小*。

## 0.1 用户确认的决策（2026-09-22）

| 问题 | 决定 |
|---|---|
| 缩放方式 | **等比放大 + 居中留白**（宽高比不符时留边，不拉伸变形） |
| 最小窗口 | **不小于设计尺寸**：窗口更小时保持 1:1 并居中，超出部分裁掉 |
| 抗锯齿 | **分两步**：本轮只做窗口缩放，素材清晰度（超采样贴图）下一轮再做 |
| 本轮进度 | 直接开始实现 |


## 0. 结论速览

| 现象 | 真正的原因 | 修法 |
|---|---|---|
| “素材低分辨率” | ① 圆片 / 箭头多边形 / 圆角面板**完全没有抗锯齿**（`pygame.draw` 的硬边）<br>② 画面被钉死在 **720×720**，大屏上既不能放大、也不会重绘成更精细的图 | ① 箭头部件改用**超采样离屏贴图**（或 `gfxdraw` 的 AA 原语）<br>② 窗口可缩放 + **等比视口**，几何/字号按实际窗口重算（矢量重绘，而不是把位图拉大） |
| “无法自由更改窗口大小” | `game.py` 的 `set_mode` 没传 `pygame.RESIZABLE`，且**整套排版常量都是 720×720 的绝对值**，即使能缩放也会散架 | 开启 `RESIZABLE`、处理 `VIDEORESIZE/WINDOWRESIZED`，把几何集中到 `Viewport`（等比 `scale` + 居中 `origin`） |

一句话：**这里没有位图素材**（`assets/` 只有 3 个矢量 OTF 字体），所以“低分辨率”不是“图片糊”，
而是**不抗锯齿 + 画布固定 720²** 这两件事叠加出的观感。

## 1. 现状实测

### 1.1 抗锯齿：没有

`.preview/explore_resize.py` 里数“一块画布上出现过多少种颜色”——一个**抗锯齿**的圆会有几十种
过渡色，**硬边**的圆只会有 2 种（填充色 + 背景色）：

| 画法 | 颜色种数 |
|---|---|
| `pygame.draw.circle`（圆片正在用的） | **2** |
| `pygame.draw.polygon`（箭头正在用的） | **2** |
| `pygame.gfxdraw.aacircle` | 46 |
| 4× 超采样 + `smoothscale` | 16 |

棋盘上的箭头放大 4 倍后可以肉眼确认（`.preview/explore-aliasing-zoom.png`）：圆片描边与箭头斜边
都是明显的阶梯。**这是“素材低分辨率”最直接的来源**，而且和窗口大小无关——720² 下同样糊。

### 1.2 画布被钉死在 720×720

- `game.py:65`：`set_mode((720, 720))`，**没有** `pygame.RESIZABLE` → 标题栏没有缩放边，
  也点不了最大化。实测 `pygame.RESIZABLE` 在本机可用；`pygame.display` **没有**
  `set_window_minimum_size`（想设最小尺寸只能走 `ctypes` 或逻辑裁剪）。
- 排版是“写死的绝对值 + 少数地方现读 `config.WINDOW_WIDTH`”的混合体。把窗口改成 1080×800 后
  （`.preview/explore_resize.py` 第 4 节）：
  - `board_area()` 变宽（1016×632），**这一处是自适应的**；
  - 卡片宽度仍是写死的 `(92, 104, 120, 100)`，而“重新开始”按钮按 `WINDOW_WIDTH - PADDING`
    贴到了右边 → 信息栏中间空出一大块（见 `explore-resize-playing-1080x800.png`）；
  - 棋盘格子被 `MAX_CELL_SIZE=112` 顶住：第 1 关只占 448×448，大窗口里孤零零一块；
  - 菜单页的 Y 坐标全是常量（`_PAGE_TITLE_Y=126`、`_PAGE_HERO_BUTTON_Y=340`…），
    只有横向居中读 `WINDOW_WIDTH` → 内容全部挤在窗口上半部（`explore-resize-start-1080x800.png`）；
  - 右侧“辅助线”开关跑到窗口右下角（它按 `WINDOW_HEIGHT` 算，属于“半自适应”）。
  - 也就是说：**能读 `config` 的地方跟着变，写死的常量不跟着变**，结果比“全写死”更难看。

### 1.3 顺带排除的两件事

- **位图素材**：`src/another_arrow_rt265/assets/` 只有 `NotoSansCJKsc-{Light,Regular,Bold}.otf`，
  界面图标、箭头、背景全部由代码矢量绘制。没有“低分辨率图片”可换。
- **系统 DPI 拉伸**：`.preview/dist_window.png` 实测窗口外框 740×768（= 720 内容 + 边框/标题栏），
  说明本机是 100% 缩放，**没有**被 Windows 位图放大。所以 HiDPI 只是“换台机器可能出问题”的
  次要项，不是本次抱怨的主因。

### 1.4 成本参考：超采样贵不贵？

6×6 棋盘画 30 帧（`.preview/explore_resize_api.py`）：1× 共 18ms；2× 超采样 + 缩回共 74.7ms
（≈2.5ms/帧）。整屏都做超采样不划算，但**只给箭头部件做一张缓存贴图**成本可以忽略。

## 2. 方案

### 2.1 缩放策略：等比视口 + 居中留白（推荐）

引入一个值对象（`ui.py`）：

```python
@dataclass(frozen=True)
class Viewport:
    width: int  # 实际窗口宽（像素）
    height: int  # 实际窗口高
    scale: float  # 设计尺寸(720²) → 实际窗口的等比系数
    origin: tuple[int, int]  # 设计框左上角在窗口里的位置（非等比时留出边）

    @classmethod
    def fit(cls, size, design=config.DESIGN_SIZE) -> "Viewport": ...
    def s(self, value: float) -> int: ...  # 缩放一个设计尺寸
    def rect(self, x, y, w, h) -> pygame.Rect: ...  # 设计坐标 → 屏幕坐标
```

- `scale = min(w/720, h/720)`，窗口比 1:1 更宽/更高时用留白居中（背景铺满，棋盘与界面元素等比放大）。
- 实现时把 `scale` **向下取整到 1/16 的档位**：拖拽窗口产生的中间尺寸无穷多，量化之后按尺寸缓存的
  贴图 / 字体不会每个中间值各留一份；向下取整还保证设计框永远不会比窗口大（不会为了取整多裁一条）。
- **不采用非等比拉伸**：会把圆片压成椭圆、字距变形。
- 好处：`ui.py` 里现有的“布局不变量”全部照旧成立（信息栏恰好铺满一行、第 1 关教程条正好落在
  棋盘上方空白带、开关不压格子……），只是整体乘了一个系数——**这正是既有测试能继续钉住的原因**。
- 关键收益：文字与图形都是**按目标尺寸重绘**（`_font(size * scale)`、`cell_size * scale`），
  不是把 720² 的帧放大，所以窗口越大越清晰。

对照的另一条路（**不推荐**，仅记录）：`set_mode(..., pygame.SCALED | pygame.RESIZABLE)`
让 SDL 把 720² 逻辑画面缩放铺满窗口——改动最小（几乎零重构）、HiDPI 自动处理，但**渲染分辨率
仍然是 720²**，放大后文字与箭头依旧是插值糊的，等于没解决“低分辨率”那一半。

### 2.2 清晰度：给箭头部件做抗锯齿贴图

`Board._draw_arrow()` 每帧现画的四件东西（圆片、圆片描边、选中/碰撞环、箭头多边形）改成
**一张缓存贴图**：

- 键：`(半径, 主题色索引, 状态, 方向)`（方向 4 种、状态 3 种、主题色 6 种、半径按格子尺寸）；
- 画法：先在 4× 画布上画，再 `smoothscale` 到目标尺寸——与现有 `_glow_sprite()` 的做法一致；
- 抖动的浮点位移用 `blit` 时的 `round()` 定位（≤1px 量化，肉眼不可见）。

备选：`pygame.gfxdraw.aacircle / aapolygon`（本机可用）。缺点是它要求整数中心与半径，
与抖动动画的浮点坐标冲突，且属于 SDL_gfx 的“experimental”接口。

面板 / 按钮的圆角（`pygame.draw.rect(border_radius=)`）同样没有 AA，但半径小、对比低，
**优先级最低**：先不动，等箭头改完再肉眼验收要不要统一。

### 2.3 窗口事件与状态保真

- `Game` 处理 `pygame.VIDEORESIZE`（`event.w/h`）与 `pygame.WINDOWRESIZED`（SDL2 原生事件，
  pygame-ce 两个都会发）→ 按新尺寸重建 `Viewport`，必要时去重。
- `Session.resize(area)`：更新 `self.area`，把当前 `Board` **就地改形**（只重算 `cell_size`/`rect`），
  保留箭头布局、选中、碰撞提示、计时、教程进度；飞出动画的像素坐标会失效 → 直接清空
  （`FLY_OUT_SECONDS = 0.32`，玩家几乎察觉不到）。
- 缓存上限：`_background`(8) / `_gradient`(64) / `_shade`(1) / `_glow_sprite`(4) 都按尺寸缓存，
  拖拽窗口会不停产生新尺寸 → 把 `scale` **量化到固定档位**（如 1/16 步进）再算几何，
  否则缓存在拖拽时会膨胀（1440×900 的背景贴图约 5MB/张）。

## 3. 实施清单（下一轮直接照做）

| 文件 | 改动 |
|---|---|
| `config.py` | `WINDOW_WIDTH/HEIGHT` → `DESIGN_SIZE`（保留 720 基准）；`MAX_CELL_SIZE` 语义改为“设计尺寸下的上限” |
| `ui.py` | 新增 `Viewport` + `set_viewport()/viewport()`；15 个几何函数（`board_area` / `hud_rect` / `hud_home_button_rect` / `hud_chip_rects` / `restart_button_rect` / `guide_toggle_rect` / `tutorial_panel_rect` / `tutorial_skip_button_rect` / `overlay_card_rect` / `overlay_button_rect` / `overlay_home_button_rect` / `menu_layout` 及其 `_*_row_rects`、`_stack_sections`）改读视口；绘制层里直接引用绝对常量的地方（`_PAGE_*`、`_HUD_CHIP_CAPTION_TOP`、`_CARD_*`、`_SECTION_*`、`_TUTORIAL_*`、`_MISTAKE_*`、`_BUTTON_ICON_SIZE`、`_TextStyle.size`）统一乘 `view.s()` |
| `board.py` | `Board.reshape(area)`；箭头贴图缓存 + AA 绘制 |
| `session.py` | `Session.resize(area)`（保留进度） |
| `game.py` | `RESIZABLE`、`VIDEORESIZE/WINDOWRESIZED` 事件、`F11` 全屏（可选） |
| `tests/` | 既有不变量保持 720² 默认；新增尺寸矩阵参数化（720²、1000×700、1280×900、900×1100）+ “缩放不丢进度” |

**待定决策**（见对话里的提问）：① 等比留白 vs 铺满；② 最小窗口尺寸下限；
③ 是否与本项一起做抗锯齿。

## 4. 复现命令

```powershell
uv run python .preview/explore_resize.py      # 抗锯齿 / 柔光放大倍数 / 缩放后排版 + 出图
uv run python .preview/explore_resize_api.py  # pygame 缩放接口、gfxdraw 原语、超采样耗时
```
