# 变更记录 08：单关卡计时器

对应 `docs/agents/basic-info.md` 中 Priority 第 6 条：**单关卡计时器（不用统计整体通关时间）**。

这一轮给每一关配上独立的计时器：进关归零、只在“还在解谜”时走字、清空或失败的那一刻停表，
并把本关的最佳用时记下来。信息栏因此从三块卡片变成四块，结算卡片也多报一行成绩。

## 变更内容

| 文件 | 修改 |
| --- | --- |
| `src/another_arrow_rt265/session.py` | 新增 `elapsed` / `best_time` / `is_new_record` 三个只读状态；`update()` 拆出 `_settle()`，并把“走表”限定在棋盘未清空时；新增 `_finish()` 负责结算并刷新最佳用时；`_load()` 额外重置 `_elapsed` 与本把是否破纪录的标志（最佳用时不清） |
| `src/another_arrow_rt265/config.py` | 新增 `COLOR_TIME`（计时读数的浅蓝） |
| `src/another_arrow_rt265/ui.py` | 信息栏重排为“回到主界面 + 四块卡片（关卡 / 剩余箭头 / **用时** / 失误）+ 重新开始”，卡片宽度与间隙重算；新增 `elapsed_text()`（`分:秒.十分位`）与 `result_time_text()`；`_draw_stat_chip()` 支持数值右对齐；失误圆点改为整组居中；结算卡片新增一行用时（破纪录时用主色金字） |
| `src/another_arrow_rt265/game.py` | 主循环里的“推进会话”抽成 `Game._update(dt)`，只有游戏画面会调用，开始界面停留再久也不计入关卡用时 |
| `tests/test_session.py` | **新增** 7 项：计时累计、清空停表、失败停表、重开归零但保留成绩、只留最快的一把、成绩按关卡分开记、切关重置 |
| `tests/test_ui.py` | **新增** 11 项：整行恰好铺满窗口、计时卡片放得下长读数、`elapsed_text()` 的进位与负值、结算文案的三种形态；原有三块卡片的断言更新为四块 |
| `tests/test_game.py` | **新增** 2 项：计时器随主循环推进、结算后停表；开始界面不计时 |
| `.preview/ui_frames.py` | 新增 `09-timer.png`（信息栏读秒）与 `10-best-time.png`（没破纪录时的结算卡片），通关 / 失败截图改为“先玩 N 秒再结算” |
| `.preview/run_demo.py` | 主循环冒烟额外断言计时器真的被跑起来了 |
| `docs/agents/basic-info.md` | 事项 6 标注“（已实现）” |

## 关键设计

### 计时语义：停表时刻就是“最后一步有效点击”

`Session.elapsed` 只在 **还在解谜** 时累加，也就是 `status is PLAYING` 且棋盘尚未清空的那些帧：

| 时刻 | 走表？ | 原因 |
| --- | --- | --- |
| 进关 / 重开 / 切关 | 归零 | 每关各计时一次，重开算新的一次挑战 |
| 停留在开始界面 | 不走 | 主循环只会在游戏画面调用 `Session.update()`（`Game._update`） |
| 棋盘还有箭头 | 走 | 这才是玩家在思考 / 操作的时间 |
| 清空棋盘后的飞出动画 + 结算停顿 | 不走 | 最后一步点击落下的瞬间成绩就定下来了 |
| 失败（失误耗尽） | 不走 | 失败判定就在那一次点击里，与通关对称 |

这里刻意**不把飞出动画（0.32s）算进成绩**：动画是程序在播片，玩家已经无事可做，
让秒表继续跳只会让“手快”变成运气。同理，结算的 0.18s 停顿也不计入。

### 最佳用时与“新纪录”

`Session._best_times` 是一个 `{关卡序号: 秒数}` 的字典，进关时不清空：

- `best_time` 报的是**本关**的历史最好成绩，重开本关、回到主界面、重开一轮都不会丢；
- 通关结算时比较一次：比历史成绩快（或这是第一次通关本关）就写回字典，并把
  `is_new_record` 置为 `True`，结算卡片上那行成绩就变成金色的“新纪录 · 用时 …”；
- 没破纪录时显示“本关用时 … · 最佳 …”，玩家能立刻看出差了多少。

失败时只显示“本关用时 …”，因为失败的那一把本来就不参与评分。

### 信息栏重排：一行里的 720 像素要重新算

原来三块卡片的宽度是 132 / 150 / 116，加起来正好铺满窗口，**没有给第四块留位置**。
先把每块卡片按“最宽的那行字 + 两侧留白”量出来（数字字号 24、标题字号 15）：

| 卡片 | 最宽内容 | 宽度 |
| --- | --- | --- |
| 关卡 | `1 / 3`（46px） | 92 |
| 剩余箭头 | `剩余箭头`（60px） | 104 |
| 用时 | `0:12.3`（73px） | 120 |
| 失误 | 三个圆点（一次失误 3 次，共 58px） | 100 |

行内元素从 32（左边距）到 688（窗口宽 − 右边距）依次是：
回到主界面按钮 48 → 间隙 12 → 92 → 10 → 104 → 10 → 120 → 10 → 100 → 10 → 重新开始按钮 140，
总和刚好 688，“重新开始”按钮由原来的 156 收窄到 140（里面仍是图标 20 + 间隙 10 + 文字 80），
卡片之间的间隙则统一成 10。`tests/test_ui.py::test_hud_row_fills_the_window_exactly`
把这个账钉住了：整行必须左贴 `HUD_PADDING`、右贴 `WINDOW_WIDTH - HUD_PADDING`，
中间不许重叠——以后谁改宽了任何一块卡片，测试都会先报警，而不是等到画面被挤出窗口。

### 读数为什么右对齐、为什么带十分位

计时器是唯一会自己变化的读数。它的值**右对齐**在卡片里：跳动的只有十分位那一位数字，
右对齐能让它待在原地，不会每 0.1 秒整行抖一下（左对齐时 `0:09.9` → `0:10.0` 会整串左移）。

格式取 `分:秒.十分位`（`elapsed_text()`），先把时间取整到十分之一秒再进位，
因此 59.96 秒会显示成 `1:00.0` 而不是 `0:60.0`；负数按 0 处理，避免把动画误差显示成负时间。
读数颜色用浅蓝 `COLOR_TIME`：金色已经是关卡号的，红色是失误的，再借一个色就能一眼分开三块卡片。

## 测试

本轮新增 20 项（共 175 项）：

| 测试 | 验收点 |
| --- | --- |
| `test_timer_starts_at_zero_and_counts_every_update` | 初始为 0，按 `dt` 累加 |
| `test_timer_stops_at_the_click_that_clears_the_board` | 清空瞬间停表，飞出动画与结算停顿都不计入 |
| `test_timer_stops_when_the_level_fails` | 失败那一刻停表 |
| `test_restart_resets_the_timer_but_keeps_the_best_time` | 重开归零，但成绩还在 |
| `test_best_time_only_keeps_the_fastest_run` | 慢了不覆盖，快了才刷新，`is_new_record` 同步 |
| `test_best_times_are_tracked_per_level` | 成绩按关卡分开记，下一关没有残留 |
| `test_switching_levels_resets_the_timer` | `advance()` / `load_level()` 都会归零 |
| `test_hud_row_fills_the_window_exactly` | 信息栏整行恰好落在两侧留白之间、元素互不重叠 |
| `test_timer_chip_has_room_for_a_long_time_reading` | 计时卡片放得下 `99:59.9`（真实渲染量宽） |
| `test_elapsed_text_formats_minutes_seconds_and_tenths`（6 项） | 0 / 12.34 / 59.96 / 65 / 3725.4 秒的进位与格式 |
| `test_elapsed_text_never_shows_a_negative_time` | 负值按 0 处理 |
| `test_result_time_text_on_failure` | 失败只报用时 |
| `test_result_time_text_marks_a_new_record_and_remembers_the_best` | 首次通关显示“新纪录”，慢了显示“本关用时 · 最佳” |
| `test_timer_advances_with_the_game_loop` | `Game._update()` 推进计时，结算后停表 |
| `test_timer_does_not_run_on_the_start_screen` | 开始界面不计时，回到主界面后归零 |

## 验证

```bash
uv run pytest -q                    # 175 passed
uv run ruff check .                 # All checks passed
uv run ruff format --check .        # 21 files already formatted
uv run ty check                     # All checks passed
uv run python .preview/ui_frames.py # 12 张图（新增 09-timer / 10-best-time）
uv run python .preview/run_demo.py  # 本关用时 0.601s，主循环冒烟通过
```

人工看图确认的两处：`09-timer.png`（信息栏四块卡片一行排开、`用时 0:12.3` 读数右对齐），
`04-level-cleared.png` / `10-best-time.png`（结算卡片的“新纪录 · 用时 0:08.0”金色行
与“本关用时 0:25.0 · 最佳 0:20.0”灰色行的对比）。

## 后续事项接口

- 事项 7（关卡预生成）：生成器可以直接读 `Session.best_time`，如果以后要做“金牌 / 银牌”
  之类的评价，把阈值调成关卡数据的一部分即可，计时器本身不用改。
- 事项 11（辅助线）：辅助线会占用棋盘区域的注意力，但不会影响计时——计时只看
  “棋盘是否清空”，与玩家点了多少次、点了哪里无关。
- 若要暂停（例如窗口失去焦点时），只需在 `Game._update()` 里加一个判断，
  不要动 `Session`：会话仍然只关心“被推进了多少秒”。
