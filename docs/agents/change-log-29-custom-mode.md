# 变更记录 29：自定义模式（事项 19）

事项 19 有两句话：“自定义模式：通过调整参数实时生成关卡”与“‘开始游戏’分裂成‘关卡模式’和
‘自定义模式’”。本轮把两句话都落成代码：

- 开始界面主按钮行变成**两个并排的入口**：金色的“关卡模式”（原来那条路）与次色的
  “自定义模式”；
- 新增画面 `Scene.CUSTOM`：两行滑动条调**棋盘边长**与**箭头数量**，中间那块棋盘是
  **实时预览**（参数一动就重新生成），页脚是“返回 / 换一关 / 开始游戏”。

## 1. 参数范围是测出来的，不是拍出来的

自定义模式每跨一档就要重算一关，所以参数范围必须落在生成器**又快又稳**的区间里。
先写脚本把候选范围整片扫了一遍（`.preview/custom_range.py`：13 个尺寸 × 7 档密度 × 3 个种子，
取最慢的一次），再定上限：

| 密度（箭头数 / 格子数） | 0.35 ~ 0.50 | 0.55 | 0.60 |
| --- | --- | --- | --- |
| 单关最慢耗时（16x16 为例） | 3.5 ms | 11 ms | 319 ms，且抽查里有 200 次重试后失败 |
| 12x12 | 2.9 ms | 9.8 ms | 156 ms，且失败 |
| 5x5 | 0.2 ms | — | — |

于是范围定为：**边长 4 ~ 16**（16x16 是默认窗口下棋盘的可读上限，见
`generator.generate_level` 的尺寸说明），**箭头数量上限 = 格子数的一半**
（`.preview/custom_drag_cost.py` 复测：把 16x16 的箭头条从 1 支拖到 128 支，
128 个取值全部生成一遍共 **198 ms**，平均 1.5 ms/关，摊在拖动里只有一两帧，
看不出卡顿）。默认值取 8x8 + 四成密度，离上限留一截。

这份数据写在 `custom.py` 的模块 docstring 里，并由
`tests/test_custom.py::test_every_parameter_combination_generates_a_valid_level`
守着：6 个代表尺寸 × 全部箭头数量 × 2 批，每一组都要生成得出来、还要过
`verify_level`（尺寸、箭头数、开局被挡数、可通关性）。**范围一旦画大，这里先红。**

## 2. `custom.py`：参数 → 关卡是确定的

新模块 `custom.py` 只做“参数 → 关卡”这一件事（不依赖 pygame，可脱离窗口测试），
对外是三类东西：

- `CustomLevel`：**正在捏的那一关**。两个参数 + 第几批 + 现成的关卡；参数一律夹到合法区间
  （`clamp_size` / `clamp_arrows`），所以界面把滑动条的取值直接塞进来就行，
  越界、缩棋盘导致箭头超上限这些情况都在里面处理掉；
- `spec_for(size, arrows, batch)`：把自定义参数翻译成一份 `LevelSpec`
  （方棋盘、`min_blocked = arrows × 0.25`、种子由 `seed_for` 算出来）——这是两层之间唯一的口径；
- `build_level(size, arrows, batch)`：带 `lru_cache` 的生成入口。

**同一个 `(边长, 箭头数量, 批次)` 永远同一关**：种子是算出来的（`seed_for`），
不是抽出来的。这样做的三个好处：玩家调参数时看到的是“这组参数的那一关”，而不是每动一下
都换一张无关的图；生成结果可以按参数缓存（拖着滑动条来回蹭不会重复算）；测试可复现。
`reroll()` 换的是**批次**（种子推进一批），参数不动——这就是“换一关”。

## 3. 滑动条是新的控件，但只借了这一块新代码

`ui.py` 里加了一类控件描述 `SliderRow(key, label, value, minimum, maximum, rect, track)`：
和 `MenuButton` / `MenuToggle` 一样**只声明**“改哪个参数 + 当前取值”，
`key` 交给 `Game._set_custom_parameter` 分发（写回参数、参数真变了才重建预览），
排布由 `custom_slider_rows()` 一处算出来（绘制与命中判定同源）。三处细节值得记下：

- **读数一侧按量程上限预留宽度**：取值位数变化（8 与 128）不会把轨道挤来挤去。
  否则拖到一半轨道突然变短，滑块下的取值就会跟着回退，看起来像在抖；
  `test_custom_slider_track_ignores_the_readout_width` 钉住这一点；
- **正反两向共用一套映射**：`slider_value(row, x)`（点哪里取哪个值）与 `_slider_thumb_x(row)`
  （取值画在哪儿）都从 `_slider_thumb_span(row)` 出发，因此“点到哪儿就是哪儿”；
  两端夹得住量程（拖到轨道外面也只会得到 min / max）；
- **拖动是事件驱动的**：`MOUSEBUTTONDOWN` 落在某一行上就记下 `Game._dragging_slider`，
  之后的 `MOUSEMOTION` 都算这一行的连续调节，`MOUSEBUTTONUP` 收尾。
  没按住时鼠标移动不会改参数。

外观沿用“轨道 = 胶囊、滑块 = 正圆”的连续量语义（与滑动开关同一种形状，
见 `config.UI_RADIUS` 的例外说明），但用色相反：开关靠滑块偏向哪侧表达开与关，
滑动条把**滑过的那一段**填成主色，于是“调到哪儿了”从颜色与滑块两处都看得出来。
颜色常量复用既有的角色（`SLIDER_TRACK_REST = SWITCH_TRACK_OFF` 等），不新增色值。

**滑动条不发声**：拖动是一串连续操作，每跨一档响一声会变成噪声；
页脚按钮照旧响一声音效。这条语义写在 `Game._handle_custom_click` 的 docstring 里，
由 `test_custom_sliders_are_silent_and_the_buttons_click` 钉住。

## 4. 预览是一块真正的棋盘

`Game.custom_board` 就是一块普通的 `Board`（构造参数是 `ui.custom_preview_area()`），
所以预览里的箭头、配色、格子几何与进场后完全一致，而不是另画一套小样例；
参数一变就重建一块（`_rebuild_custom_preview`），窗口缩放时跟着换几何
（`_sync_window_size` 里与主棋盘一起 `reshape`）。它**只画不点**：自定义画面的点击先判
滑动条、再交给页脚按钮，预览区里的点击什么也不发生。

布局上，自定义模式是唯一“控件 + 实时预览”同屏的画面，因此它**不套菜单页那套竖栏排版**
（那套排版里没有地方放棋盘）：标题提到 108（别的页面是 126）腾出预览区，
后面依次是预览区（184~540）、两行滑动条（556~612，左右并排各占一半宽）与页脚按钮。
**但页脚仍然走 `_footer_row_rects`**——`custom_page()` 是一个只有标题与三个页脚按钮的
`MenuPage`，所以“返回 / 换一关 / 开始游戏”与其它页面的页脚落在同一条线上，
`test_menu_pages_put_their_footer_buttons_on_the_same_row` 之类先前的遍历测试
不加修改地继续覆盖它。预览区与控件的相对关系由
`test_custom_preview_stays_clear_of_the_controls` 逐尺寸核对（4x4 ~ 16x16 都不压标题与控件）。

## 5. “自定义”只影响报读，不影响规则

`Session` 多了一个 `is_custom` 标志（构造参数，默认 `False`）。它**只影响界面怎么报读**：

- 信息栏第 1 格：自定义关卡报“自定义”，而不是误导性的“1 / 1”（`ui.level_chip_text`）。
  这个标签是三个 24 号字（72px），所以信息栏第 1 格从 92 加宽到 112；
  末格（失误圆点，三颗共占 58px）由“重新开始按钮的左边”倒推，正好匀出这 20px，
  720 的宽度账照旧对得上（`test_hud_row_fills_the_window_exactly` 继续通过）；
- 结算卡片：通关正文是“自定义关卡已通关”，失败是“失误次数已用完，本关未通过”
  （不说“第 1 关”）；主按钮是“再玩一次”（`advance()` 在单关会话里就是重新载入这一关）。

规则层完全不知道“自定义”这回事：`start_custom()` 只是拿
`Session(area, levels=(self.custom.level,), is_custom=True)` 开一局，
因此失误、计时、结算、辅助线、音效全部照旧。**自定义关卡不带教程**这件事也是现成的：
`Session._needs_tutorial` 本来就要求 `self.levels == LEVELS`。

**两种模式各有自己的会话**：从自定义模式回“关卡模式”时 `Game.start()` 会重建会话
（否则会接着玩刚才捏出来的那一关）；代价是切模式等于重新开一局，本关最佳成绩从头记起。
`Game._swap_session()` 顺带把音频的“状态变化”基准挪到新会话上。

## 变更内容

| 文件 | 修改 |
| --- | --- |
| `src/another_arrow_rt265/custom.py` | **新增**：`CustomLevel`（参数夹取 + 实时生成 + `reroll`）、`spec_for` / `seed_for` / `build_level`、范围常量（`MIN_SIZE` 4 / `MAX_SIZE` 16 / `MAX_ARROWS_RATIO` 0.5 …）与实测数据的说明 |
| `src/another_arrow_rt265/ui.py` | 新增 `SliderRow` / `custom_page()` / `custom_preview_area()` / `custom_slider_rows()` / `slider_value()` / `_slider_track_rect()` / `_slider_thumb_span()` / `_slider_thumb_x()` / `_draw_slider_row()` / `draw_custom_screen()` / `custom_button_rect()` / `level_chip_text()`；`start_page()` 的主按钮改成“关卡模式 + 自定义模式”两个入口；`_draw_page_title()` 支持自定义标题位置；`_result_message()` / `overlay_button_text()` / `draw_hud()` 认自定义关卡；信息栏第 1 格 92 → 112（末格相应 89 → 69） |
| `src/another_arrow_rt265/config.py` | 新开“滑动条”一节：`SLIDER_TRACK_HEIGHT` / `SLIDER_THUMB_RADIUS` / `SLIDER_TRACK_PADDING` / `SLIDER_GAP` / `SLIDER_TRACK_REST`（= `SWITCH_TRACK_OFF`）/ `SLIDER_TRACK_FILL`（= `COLOR_PRIMARY`）/ `SLIDER_THUMB`（= `SWITCH_KNOB_ON`） |
| `src/another_arrow_rt265/game.py` | 新增 `Scene.CUSTOM`、`show_custom()` / `start_custom()` / `reroll_custom()` / `_swap_session()` 及 `_custom_sliders()` / `_handle_custom_click()` / `_handle_drag()` / `_set_custom_parameter()` / `_rebuild_custom_preview()`；`_handle_events()` 接 `MOUSEMOTION` / `MOUSEBUTTONUP`；动作表补 `custom` / `custom-start` / `custom-reroll`；`_menu_page()` 与 `_draw()` 各补一个分支；`start()` 在从自定义模式回来时重建会话；`_sync_window_size()` 同步预览棋盘 |
| `src/another_arrow_rt265/session.py` | 新增 `Session.is_custom`（构造参数，默认 `False`）：只让界面换个报读口径，规则层不受影响 |
| `src/another_arrow_rt265/icons.py` | 新增 `Icon.SLIDERS`（三条带滑块的横线）：开始界面“自定义模式”按钮的图标 |
| `src/another_arrow_rt265/assets/fonts/*.otf` | 重新子集化（新增 9 个汉字：自定义模式 / 棋盘边长 / 箭头数量 / 换一关 / 再玩一次） |
| `tests/test_custom.py` | **新增** 23 条：默认参数、**全范围可生成且合法**、密度下限确实有被挡箭头、越界夹取、缩棋盘夹箭头、取值没变不重算、同参数同关卡、换一关只换批次、种子互不相同 |
| `tests/test_ui.py` | 新增 18 条 + 改写 1 条：两个模式入口（并排居中 + 主按钮是关卡模式）、自定义页只有页脚按钮、滑动条取值 / 量程 / 返回值双向映射 / 轨道不变形 / 填色随取值、预览不压标题与控件、缩放后滑动条与预览仍不重叠、绘制与整屏覆盖、信息栏读数与结算文案；`MENU_PAGES` 与“页面互不相同”纳入自定义页；`test_start_button_is_centred_on_the_page` 改写为 `test_start_screen_hero_row_holds_both_modes`（产品前提变了：主按钮位现在是两个入口） |
| `tests/test_game.py` | 新增 17 条：两个模式入口、页脚三个按钮、Enter 开局、换一关、点 / 拖滑动条改参数并刷新预览、缩棋盘夹箭头、自定义画面不吃棋盘点击与游戏快捷键、规则与普通关卡一致、通关后“再玩一次”、切回关卡模式拿回内置关卡、`S` 进出设置、缩放保留参数、滑动条不发声、整帧绘制；`_post_motion` / `_post_button_up` 两个事件helper；`test_every_declared_menu_action_is_wired` 覆盖自定义页 |
| `docs/dev/development-guide.md` | 模块表与依赖图补 `custom.py`；“加一个界面”与“界面几何只有一个来源”补自定义模式这两处例外 |
| `docs/player/player-guide.md` | 新增“两种模式”一节与自定义模式的操作说明 |
| `docs/agents/basic-info.md` | 事项 19 标记为已实现，并补上本轮的结论（见文末“自定义模式”一节） |

新增脚本（`.preview/` 不进版本库）：`custom_range.py`（参数范围实测）、
`custom_drag_cost.py`（整段拖动的生成成本）、`custom_frames.py`（自定义画面出图）、
`icon_sliders.py`（新图标放大对照）。

### 被改掉的那条旧测试

`test_start_button_is_centred_on_the_page` 断言“首屏主按钮横向居中且压在窗口中线上”。
主按钮位现在是并排的两个入口，单个按钮不再居中，因此这条测试的**产品前提变了**：
它被重写为 `test_start_screen_hero_row_holds_both_modes`（整行居中 + 两个入口等宽 +
整行仍压在窗口中线上 + 不压页脚），并新增
`test_start_screen_marks_the_level_mode_as_the_primary_button` 钉住“金色的是关卡模式”。
`test_menu_pages_stay_centred_and_inside_the_design_box` 里那句“主按钮居中”
同样改成“主按钮整行居中”。

## 验证

- `uv run pytest -q` → **556 passed**（上轮 501，新增 55 条：`test_custom.py` +23、
  `test_ui.py` +18、`test_game.py` +17，另有改写不增删的 3 处）；
- `uv run ruff check .` / `uv run ruff format --check .`（72 files）/ `uv run ty check` 全绿；
- 参数范围实测：`.preview/custom_range.py`（见第 1 节的表）与
  `.preview/custom_drag_cost.py`（16x16 全量拖拽 198 ms）；
- `.preview/custom_frames.py` 离屏出图人工核对：8x8 预览、4x4（最小）、16x16（最大）、
  12x12 悬停态、自定义关卡的游戏画面（信息栏报“自定义”）与结算卡片（“再玩一次”）；
  `.preview/ui_frames.py` 重出开始界面（两个模式入口）。12x12 及以下预览清楚可读；
  16x16 在预览区里只能看出密度（真进场后棋盘会占满整屏，格子大一倍）；
- `.preview/run_demo.py` 在 dummy 驱动下跑完整主循环，并把自定义模式接进链路：
  拖滑动条 → 换一关 → 开始游戏 → 回主界面 → 关卡模式拿回内置关卡 → 第 1 关教程；
- **重新打包** `uv run python -m nuitka --project`（22 s，ccache 命中 40/47）后用
  `.preview/capture_dist.ps1` 冒烟：窗口标题 `Another Arrow`、截图里能看到两个模式入口、
  关窗退出码 0；dist 80 个文件 34.8 MB，exe 7.7 MB，两个字体共 158 KB（子集化后）。

## 后续维护

- **改参数范围**：只动 `custom.py` 顶部的常量，然后跑 `tests/test_custom.py`——
  全范围那条会实打实地把每一组参数生成一遍，范围画大了、或者生成器变慢了都会先红；
- **加一个参数**：`custom.py` 里加一位状态（含 `_apply` 的夹取与 `spec_for` 的翻译）、
  `ui.custom_slider_rows()` 的描述表里加一行、`Game._set_custom_parameter()` 的分发表里加一条，
  滑动条本身不必再画一遍；
- **想让自定义关卡也带点别的界面语言**（例如结算卡片换标题）：读 `Session.is_custom`
  到 `ui` 里分支即可，规则层不需要动；
- 自定义参数目前**不落盘**，与音频开关同一条口径（关掉程序就回到默认的 8x8）。
