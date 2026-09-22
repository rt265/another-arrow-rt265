# 变更记录 03：动画与提示

对应 `docs/agents/basic-info.md` 中 Priority 的**事项 3**。本轮为已有的“点击 → 碰撞检测 → 移除”流程补上
视觉反馈：清除箭头时播放**飞出棋盘**动画，被阻挡时**抖动 + 火花 + 指出挡路者**，选中箭头带**呼吸式描边**。
失误次数与结算界面仍留待事项 4。

## 变更内容

| 文件 | 修改 |
| --- | --- |
| `src/another_arrow_rt265/board.py` | 新增 `FlyingArrow`、`flying`、`flash_progress`、`shake_offset`、`blocker_hint`，新增 `_start_fly_out()` / `_fly_out_distance()` / `_update_flying()` 与 `_draw_flying_arrow()` / `_draw_blocker_hint()`，重写 `draw()` / `_draw_arrow()` / `update()`，新增模块级绘制辅助函数 |
| `src/another_arrow_rt265/config.py` | 新增动画参数 `FLY_OUT_SECONDS` / `FLY_OUT_EASE_POWER` / `BLOCKED_SHAKE_RATIO` / `BLOCKED_SHAKE_CYCLES` / `SELECTION_PULSE_SECONDS` / `SELECTION_PULSE_RATIO` 与配色 `COLOR_BLOCKED_SPARK` / `COLOR_BLOCKER_HINT` |
| `src/another_arrow_rt265/direction.py` | 新增 `Direction.vector`，返回屏幕像素坐标下的单位向量 `(dx, dy)` |
| `src/another_arrow_rt265/game.py` | 点击改用 `event.pos`（而不是 `pygame.mouse.get_pos()`），更新模块说明 |
| `tests/test_board.py` | 新增 10 项动画与提示测试（共 29 项） |

## 关键设计

### 飞出动画与阻挡判定解耦

`handle_click()` 命中畅通箭头时**仍然立即**把箭头从网格里移除，只额外排入一段动画：

```python
self.remove(arrow)
self._start_fly_out(arrow)
return ClickResult.CLEARED
```

这一点很关键：如果把移除推迟到动画播完，玩家连点两次或在下一条路径上点击时，判定就会和画面上看到的
不一致（已经“飞走”的箭头仍在挡路）。因此约定：

- **逻辑状态**（`remaining` / `is_cleared` / `blocking_arrow()` / `hit_test()`）只反映网格，动画不参与；
- **动画状态**放在 `Board.flying`（`FlyingArrow` 列表）里，只提供绘制所需的像素坐标。

`FlyingArrow` 保存箭头、起点、路程与已飞行时长，坐标与进度都是计算属性：

```python
linear = min(1.0, self.elapsed / config.FLY_OUT_SECONDS)
progress = linear**config.FLY_OUT_EASE_POWER  # 缓入：起步慢、后段像被射出
position = origin + direction.vector * distance * progress
```

- `distance` 由 `_fly_out_distance()` 按方向求出“刚好完全离开棋盘可见区域”的距离（面板外再留一格宽），
  这样四种方向都能确保箭头彻底消失，而不是停在面板边缘；
- 路程与方向由 `Direction.vector` 统一给出，避免在 `board.py` 里散落 `dx/dy` 换算；
- 终点由 `finished` 判定，`Board.update(dt)` 每帧推进 `elapsed` 并丢弃已完成的动画；
- 绘制时箭头被画到临时 `SRCALPHA` 图层上，透明度按 `1 - progress³` 递减，最后 40% 行程快速淡出；
- 飞行中的箭头永远画在面板与格子之上，不会被棋盘遮挡。

### 碰撞提示：抖动 + 火花 + 指出挡路者

提示仍由 `config.BLOCKED_FLASH_SECONDS`（0.45 秒）驱动，`Board.update(dt)` 推进，但表现丰富为四层：

1. **抖动**（`Board.shake_offset`）：沿箭头方向做阻尼振荡，即“先撞出去、再弹回来”：

   $$
   \text{amplitude} = w \cdot r \cdot (1-p)^2, \qquad \text{offset} = \mathbf{u}\sin(2\pi c p) + \mathbf{u}_\perp \cdot 0.4\sin(4\pi c p)
   $$

   其中 $w$ 为格宽、$r$ 为 `BLOCKED_SHAKE_RATIO`、$c$ 为 `BLOCKED_SHAKE_CYCLES`、$\mathbf{u}$ 为方向单位向量。
   振幅随进度衰减到 0，保证提示结束时箭头**精确**回到原位，不会留下偏移。
2. **火花**：在被阻挡箭头的前方画三道琥珀色短线（-0.5 / 0 / +0.5 弧度），长度随提示进度收缩。
3. **指出挡路者**（`Board.blocker_hint`）：从被阻挡箭头指向 `blocking_arrow()` 结果的虚线，
   外加阻挡者外圈的高亮环；颜色由格子底色渐变到 `COLOR_BLOCKER_HINT`，提示结束自然淡回背景，
   不需要额外的透明通道。
4. **变色**：沿用事项 2 的深红底片 + 浅红箭头 + 向外扩散的红环（扩散幅度由 0.45 收到 0.35，
   让红环留在格子附近，不侵入邻格）。

`blocker_hint` 每次都**实时**重新查询 `blocking_arrow()`，所以提示期间挡路者被清掉时，
虚线和高亮环会立刻消失，不会指向一个已经不存在的箭头。

### 选中脉冲

`Board._elapsed` 累计总时长（`update()` 现在无论有没有提示都会累加），选中箭头的描边环半径按
`1 + SELECTION_PULSE_RATIO · sin(2π t / SELECTION_PULSE_SECONDS)` 呼吸，让“当前选中”更醒目。

### 绘制顺序

`draw()` 固定为：

```
面板 → 格子 → 被谁挡住的提示 → 棋盘上的箭头 → 飞行中的箭头
```

提示画在箭头**之前**，虚线与高亮环因此不会被底片盖住；飞行箭头画在最后，飞出过程中始终可见。

### 附带修复：点击坐标取自事件

`Game._handle_events()` 原本用 `pygame.mouse.get_pos()` 取点击位置，改为使用 `event.pos`。
两者在正常情况下结果相同，但 `pygame.mouse.get_pos()` 反映的是**处理事件那一刻**的鼠标位置，
鼠标在事件入队与该帧处理之间移动时，点击会落到错误的格子上；用 `event.pos` 还能让无窗口环境下
用 `pygame.event.post()` 模拟点击（本轮的动画冒烟测试即依赖于此）。

## 测试

`tests/test_board.py` 新增 10 项，覆盖“动画不改变判定规则”与各提示状态：

| 测试 | 验证点 |
| --- | --- |
| `test_direction_vector_matches_delta_in_screen_coordinates` | `Direction.vector` 与 `delta` 的行列转置关系 |
| `test_cleared_arrow_leaves_grid_before_animation_finishes` | 清除后网格立即释放（可再点、不再阻挡、不可移除），同时进入 `flying` |
| `test_fly_out_animation_ends_after_configured_duration` | 缓入进度、位移方向、到点后从 `flying` 移除且已飞离面板 |
| `test_fly_out_always_exits_the_board`（四个方向参数化） | 四种方向的最终位移与“飞出面板” |
| `test_board_can_be_cleared_while_animations_are_playing` | 三个动画同时播放时 `is_cleared` 已为 `True` |
| `test_shake_offset_pushes_along_direction_then_springs_back` | 先沿方向推出、再弹回（幅度更小）、结束后精确归零 |
| `test_flash_progress_runs_from_zero_to_one` | 提示进度边界值 |
| `test_blocker_hint_follows_the_current_blocker` | 提示指向阻挡者；阻挡者被清掉后自动失效 |
| `test_removing_flashed_arrow_clears_animation_state` | 强制移除正在提示的箭头会同时清空抖动与提示 |
| `test_draw_handles_blocked_and_flying_arrows` | 绘制冒烟测试：抖动、火花、虚线、飞出动画同帧绘制不报错 |

## 验证

```bash
uv run pytest -q              # 29 passed
uv run ruff check .           # All checks passed
uv run ruff format --check .  # 11 files already formatted
uv run ty check               # All checks passed
uv run another-arrow-rt265    # 启动窗口，手动点击箭头观察动画
```

另外用 `SDL_VIDEODRIVER=dummy` 做了两项人工验证：

1. 离屏渲染 5 个关键帧（碰撞峰值 / 提示衰减 / 选中脉冲 / 飞行前段 / 飞行后段）并逐张看图，
   确认抖动幅度不越过格子、火花与虚线清晰、飞出时箭头越过面板后淡出；
2. 用 `pygame.event.post()` 模拟“点一个畅通箭头 + 点一个被阻挡箭头”，再跑一次真实 `Game.run()`
   主循环 0.6 秒，确认动画期间不报错且逻辑状态正确（`remaining` 5 → 4，`flying` 回到 0）。

## 后续事项接口

- 事项 4（结算界面）：`ClickResult.BLOCKED` 可直接累加失误次数；`Board.is_cleared` 判断过关。
  注意动画期间 `is_cleared` 已经为 `True`，若希望“等最后一个箭头飞完再弹出结算”，
  可以额外判断 `not board.flying`。
- 事项 5/7（UI 排版与视觉）：动画参数都集中在 `config.py` 的“动画”与“反馈”两节，便于整体调节手感；
  若后续引入字体与 HUD，可复用 `_draw_dashed_line()` / `_mix()` 这两个纯几何辅助函数。
