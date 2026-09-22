# 变更记录 01：绘制棋盘，摆放可点击的箭头

对应 `docs/agents/basic-info.md` 中 Priority 的**事项 1**。本轮只完成“棋盘 + 可点击箭头”的框架，
碰撞检测、动画与结算界面留待后续事项。

## 变更内容

### 新增模块

| 文件 | 作用 |
| --- | --- |
| `src/another_arrow_rt265/config.py` | 全局常量：窗口尺寸、棋盘布局参数（边距、最大格宽、间隙、圆角）与配色 |
| `src/another_arrow_rt265/direction.py` | `Direction` 枚举（上/下/左/右），提供网格增量 `delta`、绘制旋转角 `angle` 与 `from_symbol()` 转换 |
| `src/another_arrow_rt265/levels.py` | 内置关卡数据：`Level` 类型别名与 `LEVELS`（3 个手写关卡） |
| `src/another_arrow_rt265/board.py` | `Arrow` 数据类与 `Board` 棋盘类：关卡解析、格子布局、绘制、鼠标命中与选中状态 |
| `src/another_arrow_rt265/game.py` | `Game` 主循环：窗口初始化、事件分发、画面刷新 |
| `tests/test_board.py` | 棋盘解析、命中判定、点击选中的单元测试（7 项） |

### 修改模块

| 文件 | 修改 |
| --- | --- |
| `src/another_arrow_rt265/main.py` | 由空文件改为真正的入口：`main()` 启动 `Game().run()` |
| `src/another_arrow_rt265/__init__.py` | 对外导出 `main()`，内部延迟导入 pygame，保持 `another-arrow-rt265` 命令可用 |

## 关键设计

### 关卡表示

关卡是等宽的字符串元组，`.` 表示空格子，`^ v < >` 表示四种方向的箭头。行数/列数由数据本身决定，
因此不同关卡尺寸可以不同。

```
".^v."
"..<."
"...<"
">..."
```

### 棋盘与坐标

- 棋盘在给定区域内居中，格子边长 = `min(区域宽 // 列数, 区域高 // 行数, MAX_CELL_SIZE)`。
- `Board.cell_rect(row, col)` 返回扣除间隙后的格子矩形；`Board.hit_test(pos)` 由像素坐标反推行列并返回箭头。
- `Board.handle_click(pos)` 更新 `Board.selected` 并返回被点中的箭头（点空格子会取消选中）。
- 箭头形状是“向上”为基准的单位多边形，按 `Direction.angle` 顺时针旋转后缩放绘制，因此四种方向共用一套顶点数据。

### 视觉

深色背景 + 圆角棋盘面板 + 圆角格子；箭头带深色圆形底片，被选中的箭头使用金色实心箭头与金色描边环。

## 内置关卡

| 关卡 | 尺寸 | 箭头数 |
| --- | --- | --- |
| 1 | 4x4 | 5 |
| 2 | 5x5 | 8 |
| 3 | 6x6 | 14 |

三个关卡均按“逆序构造”设计：从空棋盘开始逐个放置箭头，且放置时该箭头指向边界的方向上没有已放置的箭头，
因此按放置顺序**逆序**点击必然可以清空棋盘，保证后续加入碰撞检测后仍可通关。

## 操作方式

- 鼠标左键点击箭头：选中/高亮；点击空格子：取消选中。
- `←` / `→`：开发期切换关卡（正式关卡流程在事项 4/6 中实现）。
- `Esc` 或关闭窗口：退出。

## 验证

```bash
uv run pytest -q          # 7 passed
uv run ruff check .       # All checks passed
uv run ruff format --check .
uv run ty check           # All checks passed
uv run another-arrow-rt265  # 启动窗口，手动检查绘制与点击
```

## 后续事项接口

- 事项 2（碰撞检测）：可在 `Board` 中新增 `is_blocked(arrow)`，路径 = 沿 `Direction.delta` 走到边界所经过的格子，遍历 `arrow_at()` 判断是否为空；飞出动画需要箭头脱离网格，建议后续把 `Arrow` 的位置从“网格坐标”扩展为“像素坐标 + 网格坐标”。
- 事项 4/5（结算与排版）：`Game._draw()` 目前只画棋盘，可在其上叠加 HUD 与覆盖层。
