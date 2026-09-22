# 变更记录 02：碰撞检测与箭头移除

对应 `docs/agents/basic-info.md` 中 Priority 的**事项 2**。本轮实现“点击箭头 → 判断前进方向是否被阻挡 →
畅通则移除箭头、被阻挡则给出碰撞反馈”，并在过程中修复了关卡 2 的一处死锁数据错误。
飞出动画、失误次数与结算界面留待事项 3/4。

## 变更内容

| 文件 | 修改 |
| --- | --- |
| `src/another_arrow_rt265/board.py` | 新增 `ClickResult` 枚举、`blocking_arrow()`、`is_path_clear()`、`remove()`、`update()`、`remaining`/`is_cleared`/`blocked_flash`，改写 `handle_click()`，绘制中新增碰撞反馈 |
| `src/another_arrow_rt265/config.py` | 新增 `BLOCKED_FLASH_SECONDS` 与碰撞提示配色 `COLOR_CHIP_BLOCKED` / `COLOR_ARROW_BLOCKED` / `COLOR_BLOCKED_RING` |
| `src/another_arrow_rt265/game.py` | 主循环按 `clock.tick()` 的返回值计算 `dt`，每帧调用 `Board.update(dt)` |
| `src/another_arrow_rt265/levels.py` | **修复关卡 2**：原数据存在无法通关的死锁，替换为新的 5x5 / 8 箭头布局 |
| `tests/test_board.py` | 新增 9 项碰撞检测、移除与提示的测试（共 16 项） |

## 关键设计

### 碰撞检测

方向增量来自 `Direction.delta`（屏幕坐标下 y 轴向下），从箭头所在格子沿该方向逐格前进，
直到越出棋盘或遇到非空格子：

```python
def blocking_arrow(self, arrow: Arrow) -> Arrow | None:
    delta_row, delta_col = arrow.direction.delta
    row = arrow.row + delta_row
    col = arrow.col + delta_col
    while 0 <= row < self.rows and 0 <= col < self.cols:
        occupant = self._cells[row][col]
        if occupant is not None:
            return occupant
        row += delta_row
        col += delta_col
    return None
```

- `blocking_arrow()` 返回**最近**的阻挡者（便于后续做“撞到哪个箭头就提示哪个箭头”的效果）；
- `is_path_clear()` 只是 `blocking_arrow() is None` 的语义化封装；
- 由于箭头只在网格内移动且不会穿行，单格箭头模型下“同一行/列、箭头与边界之间是否有箭头”即等价于该逐格检查。

### 点击结果

`Board.handle_click()` 的返回值由“被点中的箭头”改为 `ClickResult` 枚举：

| 取值 | 含义 | 副作用 |
| --- | --- | --- |
| `MISS` | 点到空格子或棋盘外 | 清除 `selected` |
| `CLEARED` | 前方畅通，箭头飞出棋盘 | 从网格移除、清除选中态 |
| `BLOCKED` | 前方有其他箭头 | 箭头保留、设为选中态、开始闪烁提示 |

调用方（`Game`）后续可直接按结果累加失误次数、播放动画或触发结算，无需再自行判断。

### 箭头移除

`Board.remove(arrow)` 把对应格子置为 `None`，因此 `__iter__()` / `arrows` / `remaining` /
`is_cleared` 都会立即反映最新状态。移除时会同步清理该箭头的选中态与碰撞提示。
为避免“幽灵箭头”被误删，移除前会校验格子中确实是同一个 `Arrow`（包含方向）。

### 碰撞反馈

被阻挡的箭头进入 `BLOCKED_FLASH_SECONDS`（0.45 秒）的提示状态：

- 底片换成深红 `COLOR_CHIP_BLOCKED`，箭头本身换成浅红 `COLOR_ARROW_BLOCKED`；
- 外圈绘制一圈随剩余时间向外扩散的红环 `COLOR_BLOCKED_RING`（半径从 `0.44` → `0.64` 格宽）。

提示状态通过 `Board.update(dt)` 推进，由 `Game.run()` 每帧传入 `clock.tick() / 1000` 的秒数驱动，
因此不依赖 `pygame.time` 的全局状态，单元测试可以直接用固定 `dt` 验证倒计时。

## 关卡 2 数据修复

原关卡 2 第 5 行为 `">...<"`，即同行上两个箭头**面对面互相瞄准**：

- `(4,0) >` 的路径上有 `(4,4) <`；
- `(4,4) <` 的路径上有 `(4,0) >`。

两者互相阻挡，任何一方都无法先飞出，整关无解（这正是事项 6 “自动化验证可通关”要防的问题）。
现替换为重新按“逆序构造”生成的新布局（5x5、8 个箭头，仍然保留行列相互阻挡的难度）：

```
"..>.v"
"^...."
"^.^.."
"....<"
".^v.."
```

初始可点击的只有 `(1,0)^`、`(3,4)<`、`(4,1)^`、`(4,2)v`；`(2,2)^` 需要先清掉
`(3,4)< → (0,4)v → (0,2)>` 这条链，存在明确的先后顺序。逆序点击
`(1,0)^ → (3,4)< → (4,1)^ → (0,4)v → (0,2)> → (4,2)v → (2,0)^ → (2,2)^` 可清空整关（已手工验证）。

## 测试

`tests/test_board.py` 使用若干**测试专用小棋盘**（`CROSS_LEVEL` / `LINE_LEVEL` / `CHAIN_LEVEL` /
`NEAR_LEVEL` / `EDGE_LEVEL`）隔离单个规则：

- 前方畅通 → `CLEARED`，箭头从网格与 `arrows` 中消失，`remaining` 减一；
- 被阻挡 → `BLOCKED`，箭头保留、`selected` 与 `blocked_flash` 指向该箭头，倒计时结束后提示消失；
- 四个方向分别检测阻挡（十字形棋盘，四方互相锁定）；
- 多个箭头共线时只返回最近阻挡者；
- 阻挡者被移除后，原本被阻挡的箭头变为畅通；
- 指向棋盘边界的箭头路径始终畅通；
- 点空格子 → `MISS` 并清除选中；
- `remove()` 拒绝方向不符的“幽灵箭头”、越界坐标与重复移除；
- 移除正在闪烁的箭头会同步清除提示。

## 验证

```bash
uv run pytest -q          # 16 passed
uv run ruff check .       # All checks passed
uv run ruff format --check .  # 11 files already formatted
uv run ty check           # All checks passed
uv run another-arrow-rt265    # 启动窗口，手动点击箭头
```

另用 `SDL_VIDEODRIVER=dummy` 渲染了一张棋盘截图人工检查：被阻挡的箭头显示红底、浅红箭头与扩散红环，
被点掉的箭头即时消失。

## 后续事项接口

- 事项 3（动画与提示）：`ClickResult.CLEARED` 目前是瞬时移除，可在 `Board` 中把被移除箭头放入“飞行中”列表，
  每帧按方向位移像素坐标，飞出棋盘后再从列表移除；`Board.update(dt)` 已经具备推进动画的位置。
- 事项 4（结算界面）：`Game` 可依据 `ClickResult.BLOCKED` 累加失误次数，依据 `Board.is_cleared` 判断过关。
- 事项 6（关卡预生成）：建议同时补一个“按任意顺序模拟点击，验证存在清空顺序”的求解器测试，
  以免再次出现关卡 2 那样的死锁数据。
