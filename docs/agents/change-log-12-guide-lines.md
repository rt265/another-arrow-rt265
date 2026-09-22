# 变更记录 12：辅助线（显示箭头前进方向）

对应 `docs/agents/basic-info.md` 中 Priority 第 11 条：**添加辅助线功能，显示箭头前进方向**。

这一轮给棋盘加了一层“看得见的方向提示”：**打开开关后**，每个箭头都沿**当前**的前进方向拉一条
虚线——顶到棋盘边缘说明这一箭点得动，停在另一个箭头上说明点不动，鼠标指着的那条更亮。

辅助线是**可选功能，默认关闭**：开关是右下角一颗常驻的小胶囊（`G` 键同效），打开时轨道是
青绿色、关着时是暗灰，与棋盘上到底有没有线一一对应。

辅助线**只读棋盘状态**：它问的是 `blocking_arrow()` 当下的结果，因此每帧重算就自动跟得上棋盘，
既不参与判定、也不改变任何关卡数据。颜色只表达“点得动 / 点不动”，箭头本身的主题色不受影响。

## 变更内容

| 文件 | 修改 |
| --- | --- |
| `src/another_arrow_rt265/board.py` | **新增** `GuideLine`（`arrow` / `start` / `end` / `blocker` / `blocked`）与 `Board.guide_line()`；`Board.draw()` 增加 `mouse` 与 `show_guides` 两个参数（`show_guides=False` 时一条线都不画），新增 `_draw_guides()` / `_draw_guide()` 与模块级的 `_draw_guide_cap()` |
| `src/another_arrow_rt265/config.py` | 新增“辅助线”一节：线色 / 粗细 / 虚线段长 / 端点标记尺寸，以及右下角开关的 `GUIDE_TOGGLE_*`（尺寸、留白、轨道与滑块配色） |
| `src/another_arrow_rt265/game.py` | 新增 `Game.show_guides`（默认 `False`）与 `G` 键；`_handle_click()` 先判右下角开关；`_draw()` 把开关状态交给棋盘与界面 |
| `src/another_arrow_rt265/ui.py` | 新增 `guide_toggle_rect()` / `_guide_toggle_track_rect()` / `draw_guide_toggle()`，`draw_ui()` 多画一层开关；“关于”界面的操作行写明开关位置 |
| `tests/test_board.py` | **新增** 11 项：几何 7 项（含 4 个方向参数化）、像素 4 项（含“开关关着时一条不画”） |
| `tests/test_game.py` | **新增** 7 项：默认关、`G` 键、点开关、结算时不响应、开关不随关卡重置、菜单页上按 `G` 无效、整帧绘制 |
| `tests/test_ui.py` | **新增** 6 项：开关在右下角、不压任何格子（逐关核对）、胶囊里排得下、两档绘制不同、悬停提亮、“关于”界面写明开关 |
| `.preview/ui_frames.py` | 新增 `15-guide-off` / `16-guide-all` / `17-guide-hover-blocked` / `18-guide-hover-clear` / `19-guide-toggle-hover` 五帧，`render()` 支持 `show_guides` |
| `docs/agents/basic-info.md` | 事项 11 标注“（已实现）” |

## 关键设计

### 一条线，两个终点

`Board.guide_line(arrow)` 返回的就是一条线段，终点由 `blocking_arrow()` 决定——**辅助线与点击判定
读的是同一个函数**，所以画出来的结论（“点得动 / 点不动”）永远不会和真按下去的结果不一致：

| 情况 | 起点 | 终点 | 终点标记 | 颜色 |
| --- | --- | --- | --- | --- |
| 前方畅通（`handle_click` → `CLEARED`） | 箭头圆片外沿朝前进方向的那一点 | 棋盘可见区域的边缘（箭头正是从那里飞出棋盘） | 越过边缘的小箭头 | `GUIDE_LINE_COLOR_CLEAR`（青绿） |
| 前方被挡（`handle_click` → `BLOCKED`） | 同上 | 最近那个挡路箭头圆片的外沿 | 垂直于前进方向的短横杠（“到此为止”） | `GUIDE_LINE_COLOR_BLOCKED`（红） |

两个端点都留着 `GUIDE_LINE_MARGIN` 的留白，线不会戳进圆片里；长度不足一个虚线段时直接跳过，
免得贴着边的短线上堆出一个小墨点（第 1 关右上角那种“前方只剩半格”的箭头就是这种情况）。

“显示箭头前进方向”这件事因此由三样东西一起表达：虚线的走向、终点的标记形状、以及终点的颜色。

### 开关在右下角，默认关闭

绘制顺序是「面板 → 格子 → **辅助线** → “被谁挡住”的提示 → 箭头 → 飞行中的箭头」：

- 辅助线压在箭头**下面**——它穿过别的格子时不会盖住那些箭头，玩家不会被线挡住棋子；
- 悬停的那一条最后画，所以它永远压在最上面；
- 悬停的箭头由 `Board.draw(surface, mouse)` 里的 `hit_test(mouse)` 现算，**不维护“谁被指着”的状态**：
  箭头被点掉之后，线自然就没了（不需要谁去清理），换关、重开也不会留下脏状态。

`show_guides` 是**默认关闭**的（`Game.show_guides = False`）：辅助线是可选功能，而不是“默认替玩家
把答案标出来”。打开后所有箭头各画一条**淡色**的线（把线色按 `GUIDE_LINE_DIM_MIX` 混向格子底色），
鼠标指着的那条用亮色——于是“扫一眼全局”和“看清当前这一支”能同时成立。淡色是混色而不是透明通道，
与既有的“被谁挡住”提示同一套做法（不为每条线各开一张图层）。

开关的入口有两个，指向同一个 `Game.show_guides`：

| 入口 | 位置 | 说明 |
| --- | --- | --- |
| 右下角胶囊（主入口） | `ui.guide_toggle_rect()` | 文字“辅助线” + 滑动开关；悬停时提亮，点击切换 |
| `G` 键 | 只在 `Scene.PLAYING` 生效 | 键盘快捷方式，与胶囊完全等价 |

开关自己说明自己的档位：关着时轨道是暗灰、滑块靠左、文字也是灰的；打开后轨道换成辅助线
“畅通”的青绿色、滑块靠右、文字提亮。“颜色 + 滑块位置”两层冗余，与棋盘上“有 / 没有线”一一对应。

### 开关属于窗口，不属于关卡

`Game.show_guides` 存在窗口上而不是 `Session` / `Board` 上：`Board` 每次 `_load()` 都会重建，
放在棋盘上会被重开本关、换关悄悄重置。它是显示偏好，不是游戏状态，因此也**不影响关卡进度与结算**，
`return_to_start()` 之后依然有效。

`G` 与 `R`、左右方向键一样只在 `Scene.PLAYING` 生效：菜单页上误触不该改掉任何东西
（`H` 是例外，它在菜单页也是“回主界面”）；结算卡片弹出来后棋盘点击交给结算层，
开关也一并停下（`test_guide_switch_is_inert_on_the_result_screen`）。

### 开关为什么在右下角（而不在信息栏里）

信息栏那一行是**算着排满**的（`HUD_PADDING` 32 + 主页按钮 48 + 12 + 四块卡片 92/104/120/100
+ 三个 10 的间隙 + 重新开始 140 + 32，正好 720），
`tests/test_ui.py::test_hud_row_fills_the_window_exactly` 把这件事钉住了。为一颗开关去挤这行，
得同步缩窄至少一块统计卡片，代价大于收益。

右下角则是全屏最空的地方——但也不是随便放的，开关必须落在棋盘**外面**：

| 元素 | 数值（最大的 6x6 棋盘） |
| --- | --- |
| 棋盘底板 | 一直铺到 y=686 |
| 最后一排格子 | 铺到 y=674 |
| 开关 | `y = 680 ~ 712`（尺寸 122x32，右边距 24、下边距 8） |

底边只留 8px（比常规的 32px 留白紧得多）、整体贴着窗口右下角，就是为了**不压任何格子**：
这是硬约束，`tests/test_ui.py::test_guide_toggle_never_covers_a_cell` 会对内置的六关逐一验证
每一个格子都不与开关相交（以后调棋盘布局、调格子尺寸或改开关尺寸都会第一时间报警）。
开关与棋盘底板的圆角会有 6px 左右的重叠，视觉上就是一颗“浮在棋盘角落上”的控件，
而它压在底板上而不是格子上，因此不会抢走任何一次棋盘点击。

“关于”界面的操作行也跟着改成“右下角开关切换辅助线 · R 重开 · H 回主界面”，
`test_about_screen_documents_the_guide_switch` 保证这句话不会在改动中丢掉。

## 测试

本轮新增 24 项（共 320 项：棋盘 11、窗口 7、界面 6）。

| 测试 | 验收点 |
| --- | --- |
| `test_guide_line_runs_from_the_arrow_to_the_board_edge` | 畅通：起点在圆片外沿外、终点正好落在棋盘边缘上、`blocker` 为空 |
| `test_guide_line_stops_on_the_arrow_that_blocks_it` | 被挡：终点在挡路箭头的外沿（在自己格子之外、阻挡者中心之前），`blocker` 就是 `blocking_arrow()` |
| `test_guide_line_points_at_the_edge_the_arrow_faces`（4 个方向） | 四种朝向各自指向对应的那条边，另一个坐标保持与箭头中心对齐 |
| `test_guide_line_follows_the_board_after_the_blocker_is_gone` | 线读的是当下棋盘：清掉挡路的箭头，同一条线立刻通到边缘 |
| `test_guides_stay_hidden_until_the_switch_is_on` | 像素级：开关关着时（哪怕鼠标就悬在箭头上）一条线都没有；打开就有 |
| `test_hovering_an_arrow_paints_a_brighter_guide_line` | 像素级：开关打开后不悬停 → 只有淡色；鼠标在棋盘外 → 仍无亮色；悬停到箭头上 → 亮色出现，且同一支只画一条 |
| `test_hovering_a_blocked_arrow_paints_the_blocked_color` | 像素级：被挡的箭头画红色，且同一段里没有青绿色 |
| `test_the_switch_paints_every_arrow_dimmed` | 像素级：默认一条不画；`show_guides=True` 时青绿与红的淡色版都出现，而亮色一个都没有 |
| `test_guides_start_switched_off` | 新窗口默认关着，开始游戏、换关也不会自己打开 |
| `test_guide_key_toggles_the_guides_mode` | `G` 键与右下角开关是同一个开关，来回切 |
| `test_clicking_the_guide_switch_toggles_the_guides` | 点右下角胶囊能切换，且这一下不会落到棋盘上（箭头数与失误数不变） |
| `test_guide_switch_is_inert_on_the_result_screen` | 结算时开关不响应（与棋盘一样交给结算层） |
| `test_guide_switch_belongs_to_the_window_not_the_level` | 重开本关 / 换关 / 回主界面都不会重置开关 |
| `test_guide_key_is_ignored_outside_the_board` | 菜单页上按 `G` 不改开关 |
| `test_draw_renders_a_frame_with_the_guides_switched_on` | 开着辅助线画整帧（含结算帧）不出错 |
| `test_guide_toggle_sits_in_the_bottom_right_corner` | 开关在右下角，不压信息栏 / 重新开始按钮 / 教程提示条 |
| `test_guide_toggle_never_covers_a_cell` | 逐关核对：每一关的每一个格子都不与开关相交 |
| `test_guide_toggle_content_fits_inside_the_pill` | 胶囊里“文字 + 轨道”排得下，滑块放得进轨道 |
| `test_draw_guide_toggle_shows_both_positions` / `test_draw_guide_toggle_highlights_on_hover` | 像素级：两档画出来的颜色不同（青绿轨道 / 暗灰轨道），悬停会提亮 |
| `test_about_screen_documents_the_guide_switch` | “关于”界面写明开关在右下角 |

几何测试比的是**真实坐标**（`cell_rect()` 与棋盘边缘算出来的数值），像素测试比的是**真实画出来的
颜色**——后者沿用第 3 轮彩色箭头定下的规矩：配色改动必须经得起“取像素”的检验，不只是断言常量。

## 验证

```bash
uv run pytest -q                    # 320 passed
uv run ruff check .                 # All checks passed
uv run ruff format --check .        # 26 files already formatted
uv run ty check                     # All checks passed
uv run python .preview/ui_frames.py # 22 张图（新增 15~19 五帧辅助线）
```

人工看图确认了五处：`15-guide-off.png`（默认状态：一条线也没有，右下角开关是暗灰、滑块靠左）、
`16-guide-all.png`（打开后十支箭头各一条淡线：畅通的朝边缘、被挡的各自停在挡路者身上，
线都压在箭头下面；开关换成青绿轨道、滑块靠右）、
`17-guide-hover-blocked.png`（第 3 关 `(1,0)` 的 `>` 被 `(1,4)` 的 `^` 挡住：
那一条比其余的都亮，红色虚线横穿三个空格子，终点短横杠正好贴在挡路箭头的圆片外沿）、
`18-guide-hover-clear.png`（悬停 `(1,4)` 的 `^`：青绿虚线一路向上并越过棋板上沿，终点小箭头指向棋盘外）、
`19-guide-toggle-hover.png`（鼠标停在开关上：胶囊整体提亮）。

另外打印了一遍第 3 关全部十条辅助线的几何（`.preview/crop_guides.py`），逐条核对终点：
被挡的八条中有六条只跨一格（如 `(2,0)^` 被 `(1,0)>` 挡住，线长仅 14px），
跨多格的两条（`(1,0)>` 横穿三格 / `(4,4)^` 竖穿两格）也都停在阻挡者圆片之外；
同一脚本还会放大截图的右下角，用来肉眼确认开关不压格子、两档外观不同。

## 后续事项接口

- 事项 12（生成算法的配置自由度）：辅助线的几何完全由 `cell_rect()` 与 `blocking_arrow()` 推出，
  与棋盘尺寸、箭头密度无关，因此换成更大的棋盘 / 更密的布局都不需要改这一轮的任何代码。
- 事项 13（图标、字体等素材）：如果以后要给开关配上图标，可以在 `icons.py` 里加一个
  `Icon.GUIDE` 换掉胶囊左边那三个字；开关本身的 `ui.guide_toggle_rect()` 与
  `Game.show_guides` 都不必改。
- 辅助线的样式集中在 `config.py` 的“辅助线”一节（线色 / 粗细 / 虚线段长 / 端点标记尺寸 /
  开关的尺寸与留白 / 轨道与滑块配色），想让它更淡、更细、改成点线或调整开关位置，
  只动这一节即可；`tests/test_board.py` 与 `tests/test_ui.py` 的像素与几何测试会跟着验证
  “该出现时出现、不该出现时没出现”以及“开关永远在棋盘外面”。
