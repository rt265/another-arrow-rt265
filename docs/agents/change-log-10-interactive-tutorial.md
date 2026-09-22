# 变更记录 10：第一关的交互式教程

对应 `docs/agents/basic-info.md` 中 Priority 第 8 条：**UI/UX 优化：在第一关实现可交互的教程，
而不是首屏的文字描述**。

这一轮把“怎么玩”从首屏的一段文字搬进了第 1 关：玩家打开游戏点“开始游戏”后，棋盘上方会挂一条
引导提示，并给当前该点的那支箭头套一圈呼吸高亮；玩家跟着点几下（飞出棋盘 → 撞一次墙 → 清空棋盘），
就把三条核心规则都亲手做了一遍。**首屏不再有任何文字说明**（只有标题、方向箭头装饰与两个按钮），
而教程里那次“撞墙”是演示：碰撞反馈照播，但不扣真实失误。

## 变更内容

| 文件 | 修改 |
| --- | --- |
| `src/another_arrow_rt265/tutorial.py` | **新增**：教程状态机。`TutorialStep`（三步）/ `TutorialHint`（`1 / 3` + 文案）/ `Tutorial`（`note_click()` / `sync()` / `step` / `hint` / `suggested_arrow()` / `collision_demo_pending`），只有进度、不碰棋盘也不绘制 |
| `src/another_arrow_rt265/session.py` | 会话持有教程：`Session.tutorial`、`skip_tutorial()`；`click()` 把棋盘结果喂给教程，`update()` 每帧同步；`_load()` 按“是否教程关 + 本局是否教过”决定要不要新建教程，`_sync_tutorial()` 在教学完成或棋盘清空时收起；`_is_collision_demo()` 让教程演示的那次撞墙不扣失误 |
| `src/another_arrow_rt265/config.py` | 新增“教程”一节：`TUTORIAL_LEVEL_INDEX` / `TUTORIAL_BAR_HEIGHT` / `TUTORIAL_SKIP_SIZE` / `TUTORIAL_PULSE_SECONDS` / `TUTORIAL_RING_GROW` |
| `src/another_arrow_rt265/ui.py` | 新增 `tutorial_panel_rect()` / `tutorial_skip_button_rect()` / `draw_tutorial()` / `_draw_tutorial_highlight()` / `_draw_cell_ring()` / `_tutorial_phase()` / `_draw_compact_button()`；`_draw_button_content()` 支持 `font_size`；`draw_ui()` 多画一层教程；开始界面去掉说明卡片与提示行（`start_page()` 只剩标题与按钮，入参保留与 `about_page()` 同形） |
| `src/another_arrow_rt265/game.py` | 游戏画面里先判教程提示条：点中“跳过教程”就跳过，点中条上其他地方吃掉点击（不漏给棋盘） |
| `tests/test_tutorial.py` | **新增** 28 项：状态机 8 项、会话接线与演示规则 13 项、提示条布局 5 项（含 3 个参数化）、绘制 3 项 |
| `tests/test_game.py` | **新增** 7 项：第 1 关带教程、后续关卡没有、提示条吃点击、跳过按钮放开棋盘、清空本关收工、整帧绘制、一局只教一次 |
| `tests/test_ui.py` | 开始界面的三处断言换新：主按钮居中且在页脚之上、首屏不留任何文字块、“关于”界面仍保留文字版规则 |
| `.preview/ui_frames.py` | 新增 `12-tutorial-start` / `13-tutorial-blocked` / `14-tutorial-clear-board` 三帧 |
| `.preview/run_demo.py` | 主循环冒烟改为进第 1 关后“跟着教程走两步 → 演示撞墙（验证不扣失误）→ 跳过教程 → 再撞墙（验证真扣）”。 |
| `docs/agents/basic-info.md` | 事项 8 标注“（已实现）” |

## 关键设计

### 教程是“叠加层”，不是新画面

上一轮（事项 10）留下的接口是“写一个 `MenuPage`、加一个 `Scene`、补一行动作表”。教程**没有**走这条路：
它不占一整屏，而是直接叠在第 1 关的游戏画面上——棋盘仍然可见可点，提示条只是旁边的一行字。
理由很直接：教程要教的是“点击箭头之后会发生什么”，把玩家从棋盘前拉开去看一整页说明，
恰好就是这一轮要消灭的那种体验。

于是分工是：

| 层 | 职责 |
| --- | --- |
| `tutorial.py` | 记住玩家做过哪些动作，回答“现在该教第几步、该点哪支箭头” |
| `session.py` | 把点击结果与板面状态喂给教程，决定教程何时出现 / 收起，并判断这一次撞墙要不要真的扣失误 |
| `ui.py` | 把 `TutorialHint` 与 `suggested_arrow()` 画成提示条与呼吸高亮 |
| `game.py` | 把“跳过教程”按钮接到 `Session.skip_tutorial()` |

教程因此**完全不依赖窗口**：`tests/test_tutorial.py` 里的状态机测试只用 `Tutorial` 与 `Board`，
不需要 pygame 的显示子系统（虽然仓库的 `conftest.py` 已经把它切到了 dummy 驱动）。

### 三步，但进度是单调的

| 步骤 | 触发条件 | 提示文案 |
| --- | --- | --- |
| 1 `CLEAR_FREE` | `ClickResult.CLEARED` | 点击高亮的箭头：前方没有阻挡，它会飞出棋盘 |
| 2 `BLOCKED` | `ClickResult.BLOCKED` **且**教程正在引导这一步 | 再点这支被挡住的箭头：飞不出去，这次演示不扣失误 |
| 3 `CLEAR_BOARD` | `board.is_cleared` | 继续点击清空棋盘即可过关；再撞墙就要扣失误了 |

三步各记一个“已完成”标记（`Tutorial._done`），`step` 取**第一个还没完成**的，
玩家怎么乱点都不会把教程顶回去。只有碰撞那一步多了个条件（必须是教程点名的那次点击），
因为它对应的豁免不能让人提前白拿，详细理由见下面“演示只送一次”一节。
`MISS`（点在空格子上）不算学习进度。

`Tutorial.suggested_arrow(board)` 负责“指哪打哪”：第一步给一支 `is_path_clear()` 的箭头，
第二步给一支被挡住的箭头，最后一步不指定（要清空整个棋盘）。它在棋盘上**按行优先顺序**找第一支
符合条件的箭头，因此玩家清掉当前这支之后，高亮会自然落到下一支上，不需要教程自己维护指针。

### 提示条为什么挂在棋盘上方

第 1 关是 4×4 的小棋盘，格子尺寸被 `config.MAX_CELL_SIZE`（112）顶住，因此棋盘上下各空出一段：

| 元素 | 位置（y） |
| --- | --- |
| 信息栏 | 0 ~ 104 |
| 教程提示条（656×44，圆角 22） | 128 ~ 172 |
| 第 1 关棋盘底板 | 174 ~ 634 |

提示条正好落在棋盘上方的空白带里，**不必缩小棋盘**：第 1 关的棋盘位置与正式关卡完全一致，
玩家学会之后进入第 2、3 关时，棋盘不会“跳”一下。`tests/test_tutorial.py::
test_tutorial_panel_sits_above_the_first_level_board` 用真实的 `Board` 算了一遍两者的矩形，
把“提示条不压棋子、也不压信息栏”钉住——以后调 `HUD_HEIGHT` / `MAX_CELL_SIZE` 时会立刻报警。

条内一行从左到右排开：`1 / 3` 进度（主色）→ 竖分隔线 → 指引文案（17 号字）→ 右侧“跳过教程”
（104×30 的小按钮，不投影、字号降一档，不抢主按钮的戏）。
`test_tutorial_text_fits_beside_the_skip_button` 会把三条文案都真实渲染量宽，保证加点字也不会顶到按钮上。

高亮环则是画在棋盘**之上**的一圈圆角描边（金色、3px、半径与透明度按 1.2 秒的周期呼吸）。
第二步还会额外把“挡路的那个箭头”用细一档的红环圈出来——`blocking_arrow()` 本来就是公开 API，
于是“谁挡住了谁”这条规则也从文字变成了看得见的图形。

### 玩家不被锁死，但演示只送一次

教程只是**提示**：它高亮一支箭头，但棋盘照常接受任何点击。理由与 `_handle_primary_action()` 里
“进行中不响应 Enter”同源——误触不该被惩罚性地拦下，而真点错了也确实应该体验一次失误。

这就是本轮的第二个重点：**教程当着玩家的面演示“撞墙”时，不应该真的扣掉一次失误**。玩家还在学，
第一次撞墙应该只换来一条经验。于是把“碰撞”那一步改成一步显式的**脚本化演示**：

| 条件 | 行为 |
| --- | --- |
| `Tutorial.collision_demo_pending`（`step` 正好是 `BLOCKED`） | 棋盘照常晃动 / 溅火花 / 圈出挡路的箭头；`mistakes_left` **不动**；这一次点击同时把碰撞那一步记完成 |
| 其他任何撞墙（演示之前、演示之后、跳过教程之后、非教程关） | 按真实规则扣一次失误，扣到 0 就失败 |

豁免只送一次，而且不能提前“用掉”：`Tutorial.note_click()` 里的碰撞记录多了一个条件
（`self.step is TutorialStep.BLOCKED`），所以玩家自己在第一步乱点撞墙既不会完成那一步、也不会白拿豁免。
`Session._is_collision_demo()` 必须在 `note_click()` **之前**问——演示那次点击会顺手把这一步记完，
问晚了就变成“真扣”。

文案也跟着说清楚：第二步是“飞不出去，这次演示不扣失误”，第三步是“继续点击清空棋盘即可过关；
再撞墙就要扣失误了”——把“刚才那次是特例”明确讲出来，避免玩家误以为撞墙本来就不痛。

另外三个边界仍然是上一轮的约定：

- 本关**失败**不收起教程（失败说明还没学会），重开本关会从第一步重新教一遍；
- 本关**通关**或三步都走完则收起教程，并记下“本局教过了”：之后重开本关、回到第 1 关都不再打扰；
- “跳过教程”走同一套收起逻辑，一局之内不再出现（新开一局是新的 `Session`，教程会重新走一遍）。

`Session._tutorial_seen` 是这一套的总开关，它**不**随 `_load()` 重置，因此“教过就不再重复”
是会话级的事实；`Session.tutorial` 为 `None` 时，`ui` 与 `game` 的相关分支都直接跳过。

教程也**只挂在内置关卡列表的第 1 关**（`_needs_tutorial()` 里同时看 `config.TUTORIAL_LEVEL_INDEX`
与 `self.levels == LEVELS`）：自定义关卡（测试、以后的自制关卡）即使排在序号 0，也不会被塞进教程，
更不会继承“演示不扣失误”这处对游戏规则的放宽。

### 首屏不再复述规则，也不再说“去玩教程”

开始界面现在只有：大标题 + 英文副标题 + 四个方向的箭头装饰 + 主按钮“开始游戏” + 页脚“关于”。
上一轮留下的单行“上手”卡片与页脚提示行一并拿掉——玩家点“开始游戏”就会撞上教程，
不需要先在标题页被告知“你会遇到教程”。

规则的完整文字仍然留在“关于”界面（`about_page` 的“玩法与操作”那一块），想复习的玩家找得到。
`start_page()` 保留 `total_levels` / `max_mistakes` 两个入参（与 `about_page()` 同形），
页面上要加提示行时直接可用；`tests/test_ui.py::test_start_screen_keeps_no_rule_text`
把“首屏不留文字块”钉住，防止以后又慢慢长回来。

## 测试

本轮新增 36 项（共 232 项）。

| 测试 | 验收点 |
| --- | --- |
| `test_tutorial_starts_on_the_first_step` | 新教程停在第一步，进度读数是 `1 / 3` |
| `test_clearing_an_arrow_advances_to_the_collision_step` | 点掉一支畅通箭头 → 进入碰撞那一步 |
| `test_clicking_empty_space_teaches_nothing` | 点空格子（`MISS`）不推进进度 |
| `test_steps_are_latched_so_the_order_does_not_matter` → `test_collision_step_waits_for_the_tutorial_to_ask_for_it` | 自己先撞墙不算完成第二步（也不会白拿豁免），轮到教程点名时才“演示并完成” |
| `test_clearing_the_board_finishes_the_tutorial` | 棋盘清空 → 教程结束、`hint` 为 `None` |
| `test_suggested_arrow_is_clear_then_blocked` | 第一步指畅通箭头、第二步指被挡住的箭头（用真实 `Board` 验证） |
| `test_suggested_arrow_is_none_on_the_last_step` | 最后一步不指定箭头 |
| `test_session_offers_the_tutorial_on_the_first_level` / `..._no_tutorial_on_later_levels` | 教程只挂在第 1 关 |
| `test_session_moves_the_tutorial_along_with_the_players_clicks` | 会话点击 → 教程进度同步前进 |
| `test_the_demo_collision_does_not_cost_a_mistake` | 演示撞墙：失误不变、状态仍是进行中、碰撞反馈照播 |
| `test_collisions_after_the_demo_cost_mistakes_again` | 演示之后再撞墙就按真实规则扣（`max_mistakes=1` 时直接失败） |
| `test_collisions_before_the_demo_cost_mistakes` | 还没轮到演示就自己撞墙，那是一次真实失误 |
| `test_skipping_the_tutorial_makes_collisions_count_again` | 跳过教程后撞墙照样扣失误 |
| `test_custom_level_sets_never_get_the_tutorial` | 自定义关卡不继承教程与豁免 |
| `test_session_drops_the_tutorial_once_the_board_is_cleared` | 通关后收起教程 |
| `test_session_drops_the_tutorial_when_it_is_cleared_without_a_collision` | 一路只点畅通箭头通关，教程也不残留 |
| `test_tutorial_comes_back_after_a_failed_attempt` | 失败后重开本关，教程从第一步重来 |
| `test_skipping_the_tutorial_keeps_it_hidden_for_the_rest_of_the_session` | 跳过后重开本关 / 回到第 1 关都不再弹 |
| `test_next_level_has_no_tutorial` | 进入第 2 关没有教程 |
| `test_tutorial_panel_sits_above_the_first_level_board` | 提示条在窗口内、不压信息栏、不压第 1 关棋子 |
| `test_tutorial_skip_button_is_inside_the_panel` | “跳过教程”在条内且垂直居中 |
| `test_tutorial_text_fits_beside_the_skip_button`（3 个参数） | 三条文案都放得下，不会顶到按钮上 |
| `test_draw_tutorial_renders_every_step_without_error` | 三步 + 悬停 + 无教程，绘制都不出错 |
| `test_draw_tutorial_paints_the_panel_over_the_board_frame` | 同一关“跳过 / 未跳过”两帧在提示条位置颜色不同（确实画上去了） |
| `test_draw_tutorial_keeps_quiet_on_the_result_screen` | 结算时不再画教程 |
| `test_first_level_opens_with_the_interactive_tutorial` | 窗口进第 1 关就有教程进度与高亮箭头 |
| `test_later_levels_have_no_tutorial` | 切到第 2 关教程消失 |
| `test_tutorial_panel_swallows_clicks_that_miss_the_skip_button` | 条上空白处吃点击，棋盘与失误都不动 |
| `test_skip_button_hands_the_board_back_to_the_player` | 跳过后棋盘照常响应 |
| `test_clearing_the_first_level_ends_the_tutorial` | 真实通关 → 教程收工（走事件分发路径） |
| `test_draw_renders_the_first_level_frame_with_the_tutorial` | `Game._draw()` 连教程一起画不出错 |
| `test_tutorial_is_only_taught_once_per_session` | 同一会话不再重播，新窗口重新教 |
| `test_start_button_is_centered_above_the_footer_button` | 首屏主按钮居中、在页脚“关于”之上 |
| `test_start_screen_keeps_no_rule_text` | 首屏真的没有说明卡片与提示行 |
| `test_about_screen_still_explains_the_rules` | 文字版规则搬到“关于”界面后仍在 |

## 验证

```bash
uv run pytest -q                    # 232 passed
uv run ruff check .                 # All checks passed
uv run ruff format --check .        # 24 files already formatted
uv run ty check                     # All checks passed
uv run python .preview/ui_frames.py # 17 张图（新增 12/13/14 三帧教程）
uv run python .preview/run_demo.py  # 本关用时 0.613s，主循环冒烟通过
```

人工看图确认了四处：`12-tutorial-start.png`（提示条 + 金色高亮骑在 `^` 上，紧贴棋盘上沿而不压棋子）、
`13-tutorial-blocked.png`（第二步文案 + 被挡箭头套金环、挡路的 `<` 套细红环，而右上角“失误”仍是 3/3 个红点——
演示确实没扣）、`14-tutorial-clear-board.png`（第三步没有高亮，提示条仍在）、
`00-start.png`（只剩标题 / 方向箭头装饰 / “开始游戏” / 页脚“关于”）。

## 后续事项接口

- 事项 11（辅助线）：辅助线要画在棋盘上、跟着“选中 / 悬停的箭头”走，可以复用本轮新增的
  `_draw_cell_ring()` 与 `_tutorial_phase()`（呼吸相位）；教程的“挡路提示环”也可以并进辅助线的
  统一表达里，届时把 `_draw_tutorial_highlight()` 里那两段合并即可。
- 事项 12（生成算法的配置自由度）：`TUTORIAL_LEVEL_INDEX` 已经是一个配置项，但提示条的位置目前
  假设“教程关的棋盘上沿在 174”。如果以后生成的教程关棋盘更大，需要把提示条改成
  “棋盘上沿与信息栏之间居中”或“贴着棋盘底部”，`test_tutorial_panel_sits_above_the_first_level_board`
  会第一时间指出这件事。
- 教程文案集中在 `tutorial._TEXTS`，如果以后要做多语言或“重看教程”入口，改这一处即可；
  “重看教程”按钮只需调 `Session.restart_level()` 并把 `_tutorial_seen` 复位（可新增一个公开方法）。
