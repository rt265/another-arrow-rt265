# 变更记录 04：结算界面与可玩关卡 Demo

对应 `docs/agents/basic-info.md` 中 Priority 的**事项 4**。本轮把前几轮的“棋盘 + 碰撞 + 动画”接上
游戏规则与界面：新增**失误次数**、**顶部信息栏**、**通关 / 失败结算卡片**与**重新开始**，形成一个
从第 1 关到第 3 关可以完整打通的 Demo。按设计约定，本轮**不做开始界面**，启动后直接进入第 1 关。

## 变更内容

| 文件 | 修改 |
| --- | --- |
| `src/another_arrow_rt265/session.py` | **新增**：`GameStatus` 与 `Session`，集中承载失误次数、通关判定与关卡流转 |
| `src/another_arrow_rt265/ui.py` | **新增**：字体加载、`board_area()` / `hud_rect()` / `restart_button_rect()` / `overlay_button_rect()` 布局函数，`draw_hud()` / `draw_overlay()` / `draw_ui()` 绘制函数 |
| `src/another_arrow_rt265/game.py` | 用 `Session` 取代裸 `Board`；新增 `_handle_click()` / `_run_primary_action()`，`R` 键重开本关，`Enter` / 空格触发结算主按钮 |
| `src/another_arrow_rt265/config.py` | 新增布局常量 `HUD_HEIGHT` / `HUD_PADDING` / `BOARD_TOP_GAP`（`BOARD_MARGIN` 48 → 40）、玩法常量 `MAX_MISTAKES` / `LEVEL_CLEARED_DELAY` 与界面配色 |
| `src/another_arrow_rt265/levels.py` | **修复第 3 关的死局**：(4,0) 由 `^` 改为 `<`，并加注释说明原因 |
| `tests/conftest.py` | **新增**：把 SDL 切到 dummy 驱动，测试无需真实显示器与声卡 |
| `tests/test_session.py` | **新增** 14 项：失误扣减、失败、通关、关卡流转、重开、内置关卡可通关性 |
| `tests/test_ui.py` | **新增** 10 项：布局边界、按钮文案、各状态绘制冒烟 |
| `tests/test_game.py` | **新增** 12 项：窗口级事件分发（按钮点击、快捷键、结算态点击） |

## 关键设计

### 规则与绘制分离

事项 3 的做法是把动画状态留在 `Board` 里，本轮沿用同一思路，把**玩法规则**从窗口里抽出来：

```
Game（窗口 / 事件 / 每帧刷新）
  └── Session（失误次数、通关判定、关卡流转）
        └── Board（点击命中、碰撞检测、飞出与碰撞动画）
```

`Session` 只依赖 `Board` 与 `config`，不碰 `pygame.display`，因此 T04 / T05 / T06 这些
“通关 / 失败 / 重开”的验收点可以用固定 `dt` 在无窗口环境下逐帧复现，而不必启动游戏。

### 失误次数与结算时机

`Session.click()` 转发点击并按结果结算，是规则的唯一入口：

```python
result = self._board.handle_click(position)
if result is ClickResult.BLOCKED:
    self._mistakes_left -= 1
    if self._mistakes_left <= 0:
        self.status = GameStatus.FAILED
```

需要注意“清空棋盘”与“飞出动画”之间的时间差：`Board.handle_click()` 是**立即**把箭头从网格
移除的（事项 3 的设计），所以最后一支箭头被点掉的瞬间 `is_cleared` 就已经为 `True`，但动画还在播。
因此结算判定放在 `Session.update()` 里，并且额外等动画播完再加一小段停顿：

```python
if not self._board.is_cleared or self._board.flying:
    self._cleared_pause = 0.0  # 重新计时
    return
self._cleared_pause += dt
if self._cleared_pause >= config.LEVEL_CLEARED_DELAY:
    self.status = GameStatus.LEVEL_CLEARED
```

这样“点掉最后一支箭头”与“弹出通关卡片”之间会隔一次飞出动画 + `LEVEL_CLEARED_DELAY`
（0.18 秒），观感上更自然；失败则立即结算，因为抖动提示本身就是反馈。

结算之后 `Session.click()` 直接返回 `None`，玩家在卡片上继续点棋盘不会改动任何状态。

### 界面布局与命中判定同源

`ui.py` 是界面几何的单一来源：`board_area()` 决定棋盘可用区域，`restart_button_rect()` /
`overlay_button_rect()` 决定按钮位置，`Game._handle_click()` 直接拿这两个矩形做命中判定。
绘制与判定读同一份坐标，因此不会出现“看着点到按钮了却没反应”的错位；以后调排版
（事项 5 / 7）也只需要改 `ui.py` 与 `config.py`。

窗口从上到下分为两段：

| 区域 | 内容 |
| --- | --- |
| 信息栏 `HUD_HEIGHT = 96` | 左：`第 N 关 / 共 M 关` + `剩余箭头 X`；右：`失误 ● ● ●` + `重新开始` 按钮 |
| 棋盘区 `board_area()` | `Board` 按需缩放并居中，最大不超过 `MAX_CELL_SIZE` |

失误次数用圆点表示：剩余次数画亮红色实心圆、已用掉的画暗色圆，因此“总共几次、还剩几次”
都能一眼看清，不必去读数字。

结算卡片固定在窗口正中，通关用绿色边框与标题、失败用红色边框与标题，主按钮文案由
`ui.overlay_button_text()` 统一给出，与 `Session` 的流转保持一致：

| 状态 | 标题 | 正文 | 主按钮 |
| --- | --- | --- | --- |
| 通关（还有下一关） | 关卡完成！ | 剩余失误 X 次 | 下一关 |
| 通关（最后一关） | 关卡完成！ | 全部 3 关已通关 | 重新开始游戏 |
| 失败 | 挑战失败 | 失误次数已用完，第 N 关未通过 | 重试本关 |

`Session.advance()` 在最后一关会回到第 1 关并重置失误次数，于是“重新开始游戏”不需要额外状态。

### 输入约定

| 输入 | 进行中 | 结算中 |
| --- | --- | --- |
| 左键点棋盘 | 选中 / 清除 / 扣失误 | 忽略 |
| 左键点按钮 | 重新开始本关 | 下一关 / 重试本关 |
| `Enter` / 空格 | 忽略（避免误触丢进度） | 同主按钮 |
| `R` | 重新开始本关 | 重新开始本关 |
| `←` / `→` | 开发期切换关卡 | 同左 |
| `Esc` | 退出 | 退出 |

### 中文字体

界面文字优先匹配系统中的 CJK 字体（`microsoftyahei` / `msyh` / `simhei` / `notosanscjk` 等），
找不到时退回 pygame 内置字体。`_font()` 用 `functools.cache` 缓存，避免每帧重复解析字体文件。

## 附带修复：第 3 关是无法通关的死局

本轮新增的 `test_built_in_levels_can_be_cleared`（逐关用“贪心清空”验证可解）立刻暴露了
第 3 关的问题：原来的 (4,0) 是向上的箭头，而 (0,0) 是向下的箭头，**两者在同一列上互相瞄准**，
谁也飞不出去，整关无解。修复方式是把 (4,0) 改成向左的箭头——它朝棋盘外，开局即可清除，
清掉后 (0,0) 的路径随之打开。

```diff
- "^...^<",
+ "<...^<",
```

这正是 `AGENTS.md` 里“关卡数据改动后需要正演一遍清空顺序”的实例，现在由测试自动兜底：
以后改关卡数据，只要出现死局，`pytest` 就会直接失败。

## 测试

本轮新增 36 项测试（共 65 项），覆盖验收表里的 T04 / T05 / T06：

| 测试 | 验收点 |
| --- | --- |
| `test_clearing_all_arrows_shows_the_result_and_advances` | **T04**：清空全部箭头 → 动画播完后弹出通关 → 进入下一关 |
| `test_running_out_of_mistakes_fails_the_level` | **T05**：失误耗尽 → 失败状态，允许重试 |
| `test_retry_after_failure_restores_the_level` | **T05**：失败后重试，失误与棋盘恢复 |
| `test_restart_restores_layout_and_mistakes` | **T06**：进行中重开，布局与失误次数恢复 |
| `test_built_in_levels_can_be_cleared`（3 关参数化） | 至少 3 个可通关关卡，且贪心顺序不需要消耗失误 |
| `test_clearing_the_last_level_starts_a_new_round` | 通关最后一关后可以从头再玩一轮 |
| `test_clicking_the_restart_button_restores_the_level` | 窗口级：点击信息栏按钮 → 棋盘恢复（走真实事件队列） |
| `test_overlay_button_click_advances_to_the_next_level` | 窗口级：点击卡片主按钮 → 进入下一关 |
| `test_board_clicks_are_ignored_on_the_result_screen` | 结算界面不会被误点破坏 |
| `test_draw_ui_renders_in_every_state`（3 态参数化） | 三种状态的绘制冒烟 |

## 验证

```bash
uv run pytest -q              # 65 passed
uv run ruff check .           # All checks passed
uv run ruff format --check .  # 17 files already formatted
uv run ty check               # All checks passed
uv run another-arrow-rt265    # 启动窗口，手动通关第 1 关并观察结算卡片
```

另外做了两项无窗口人工验证（脚本保留在 `.preview/`，Ruff 会跳过隐藏目录）：

1. `.preview/ui_frames.py` 离屏渲染 5 张界面图（进行中 / 6×6 最大棋盘 / 失误扣减 / 通关卡片 /
   失败卡片）并逐张查看，据此把 `BOARD_TOP_GAP` 从 8 调到 24——原来的间隙会让 6×6 棋盘
   紧贴信息栏，调整后棋盘与信息栏之间保持约 40 像素留白；
2. `.preview/run_demo.py` 在 dummy 驱动下跑真实 `Game.run()` 主循环，投递“点箭头 + 点重新开始
   按钮”两个事件后退出，确认整条链路（事件 → 会话 → 动画 → 绘制）无异常且状态正确。

## 后续事项接口

- 事项 5（UI/UX 排版）：布局常量都在 `config.py` 的“布局”一节，几何计算集中在 `ui.py`；
  按钮命中判定直接复用 `ui` 的矩形函数，改动位置不会漏改判定。
- 事项 7（开始界面）：在 `Session` 之外再加一个“开始 / 进行中”的外层状态即可；
  `GameStatus` 目前只描述关卡内状态，没有与开始界面耦合。
- 事项 9（随机模式）：`Session` 的 `levels` 是可注入的元组，随机生成的关卡只要变成
  `tuple[str, ...]` 就能直接塞进来，通关测试也已经按“逐关验证可解”的方式写好。
