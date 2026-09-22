# 变更记录 06：各画面统一的“回到主界面”与图标

对应 `docs/agents/basic-info.md` 中 Priority 第 5 条的补充需求：**每个关卡都要能回到主界面**
（游戏界面与通关 / 失败界面都要有入口），并**用图标丰富视觉**。上一轮只让“通关最后一关后的
主按钮”回主界面，这一轮把它拆成三处常态化入口，同时新增一套矢量图标（房子 / 环形箭头 / 右箭头）
装在按钮上。

## 变更内容

| 文件 | 修改 |
| --- | --- |
| `src/another_arrow_rt265/icons.py` | **新增**：`Icon`（`HOME` / `RESTART` / `NEXT`）与 `draw_icon()`，三个图标全部用几何图形绘制，不引入任何外部资源 |
| `src/another_arrow_rt265/ui.py` | **新增** `hud_home_button_rect()` / `overlay_home_button_rect()` / `_overlay_button_row()` / `overlay_primary_icon()` / `_draw_icon_button()` / `_draw_button_content()`；`_draw_primary_button()` 与 `_draw_secondary_button()` 支持 `icon`；信息栏加左上角图标按钮、“重新开始”加图标；结算卡片底部改为并排两个按钮；`overlay_button_text()` 最后一关改为“再来一轮” |
| `src/another_arrow_rt265/game.py` | `_handle_click()` 分派两个新按钮；新增 `H` 键回主界面；主按钮不再承担“回到主界面”（改由旁边的次要按钮提供） |
| `tests/test_icons.py` | **新增** 13 项：每个图标都画出了东西、只用指定颜色、不越出图标框、随尺寸放大、三种图标互不相同 |
| `tests/test_ui.py` | **新增** 2 项：信息栏主界面按钮的布局、主按钮图标随状态变化；按钮行居中测试改为覆盖两个按钮 |
| `tests/test_game.py` | **新增** 7 项：每关的信息栏入口（3 关参数化）、`H` 键、通关与失败两种结算界面的入口、最后一关主按钮“再来一轮” |
| `docs/agents/basic-info.md` | 事项 5 补注“含各画面的回到主界面入口与图标” |

## 关键设计

### 三处“回到主界面”入口

| 画面 | 位置 | 形式 | 快捷键 |
| --- | --- | --- | --- |
| 游戏界面（进行中） | 信息栏左上角 | 48×48 图标按钮（房子），悬停提亮 | `H` |
| 游戏界面（通关 / 失败） | 结算卡片底部左侧 | “回到主界面”次要按钮（房子图标） | `H` |
| 开始界面 | —— | 本身就是主界面，不需要入口 | —— |

主按钮的文案相应调整为“按状态变化”，最后一关通关时不再和次要按钮重复：

| 状态 | 主按钮 | 主按钮图标 | 次要按钮 |
| --- | --- | --- | --- |
| 失败 | 重试本关 | 环形箭头 | 回到主界面 |
| 通关（还有下一关） | 下一关 | 右箭头 | 回到主界面 |
| 通关（最后一关） | 再来一轮 | 环形箭头 | 回到主界面 |

左上角放“回主界面”是手游信息栏的常见位置，因此没有额外文字也不会让人误读；`H` 键与既有的
`R`（重新开始）保持同一套“单键快捷操作”习惯。

### 为什么用矢量图标，而不是引入第三方图标字体

`assets/` 目前是空的，而且**在 Python 包之外**：Nuitka 用 `--project` 打包时不会自动带上它，
要用起来得同时做三件事——给 `[tool.nuitka]` 加 `include-data-dir = ["assets=assets"]`、
把资源定位改成“exe 同级目录”而不是 cwd、在 `THIRD-PARTY.md` 里登记字体许可。
相比之下，本轮需要的三个图标用几何图形就能画清楚，还额外得到两个好处：

1. 颜色直接取所在按钮的文字色，主/次按钮、悬停态自动跟着变，不会出现“位图图标对不上配色”；
2. 线宽按尺寸等比缩放（`max(2, size * 0.11)`），任何分辨率下都清晰。

因此本轮**没有引入任何第三方素材**，`THIRD-PARTY.md` 也就无需改动。如果以后确实想换成
图标字体（Font Awesome / Bootstrap Icons 等），替换点只有 `icons.py` 的 `draw_icon()`：
保持函数签名不变，界面代码一行都不用动。

| 图标 | 画法 |
| --- | --- |
| `HOME` 房子 | 三角屋顶（两条斜线）+ 屋身（左右竖线 + 底边）+ 一扇坐在地板上的小门 |
| `RESTART` 环形箭头 | 24 段折线采样的圆弧（缺口留在正上方）+ 沿切线接在末端的三角箭头 |
| `NEXT` 右箭头 | 一根短杆 + 一个三角头，与开始界面上的装饰箭头同款 |

环形箭头没有用 `pygame.draw.arc`：它的角度约定与屏幕坐标（y 轴向下）相反，容易把缺口画反；
自己采样既能保证方向正确，也方便直接拿到弧的端点来接箭头。

### 布局：先算宽度，再排位置

信息栏要从左到右塞下“回主界面 + 三块统计卡片 + 重新开始”，720 像素的窗口宽度必须精打细算：

```text
32  ⌂(48)  16  关卡(132)  12  剩余箭头(150)  12  失误(116)  14  ↻重新开始(156)  32
└────────────────────── 656 = 窗口宽 - 2 × HUD_PADDING ──────────────────────┘
```

失误卡片的右边界仍然由“重新开始按钮的左边”倒推（`hud_chip_rects()`），所以以后改按钮宽度、
文案长度时，间距会保持恒定；绘制与命中判定继续共用同一批 `*_rect()` 函数。

结算卡片底部改成一行两个等宽按钮（196×56 + 16 间距 = 408），整行在 460 宽的卡片里居中，
`_overlay_button_row()` 同时供绘制与点击判定使用。

### 按钮上的“图标 + 文字”

`_draw_button_content()` 把图标与文字当成一个整体算总宽再居中，而不是各自居中——否则
图标与文字之间会出现不等宽的空隙。图标尺寸统一 20 像素（`_BUTTON_ICON_SIZE`），
与文字间距 10 像素。

## 测试

本轮新增 21 项测试（共 99 项），删去 1 项被“再来一轮”取代的旧用例：

| 测试 | 验收点 |
| --- | --- |
| `test_every_level_has_a_back_to_menu_button_in_the_hud`（3 关参数化） | **每关**的游戏界面都能回到主界面，且回去后会话重置到第 1 关 |
| `test_won_level_has_a_back_to_menu_button_on_the_result_screen` | 通关界面的“回到主界面”可用 |
| `test_failed_level_has_a_back_to_menu_button_on_the_result_screen` | 失败界面的“回到主界面”可用 |
| `test_home_key_returns_to_the_start_screen` | `H` 键等价于点击该按钮 |
| `test_last_level_primary_button_starts_a_new_round` | 最后一关的主按钮是“再来一轮”，点击后从第 1 关重新开始 |
| `test_hud_home_button_is_inside_the_hud_and_clear_of_the_chips` | 图标按钮在信息栏内且不压统计卡片 |
| `test_overlay_button_row_is_centered_inside_the_card` | 结算卡片底部两个按钮并排、不重叠、整行居中 |
| `test_overlay_button_icon_follows_the_status` | 主按钮图标随状态变化（环形箭头 / 右箭头） |
| `test_every_icon_*`（4 项 × 3 图标） | 每个图标都真的画出像素、只用指定颜色、不越出图标框、随尺寸放大 |
| `test_icons_are_visually_distinct` | 三种图标不会画出同一张图 |

## 验证

```bash
uv run pytest -q              # 99 passed
uv run ruff check .           # All checks passed
uv run ruff format --check .  # 19 files already formatted
uv run ty check               # All checks passed
uv run python .preview/ui_frames.py   # 9 张图（新增 06-hud-home-hover、07-icons）
uv run python .preview/run_demo.py    # dummy 下跑真实主循环
```

`.preview/07-icons.png` 把三个图标按 16 / 24 / 32 三档尺寸排在深色底上逐档检查：
16 像素时房子的门会偏拥挤，因此界面里统一用 20 像素（图标按钮上放大到 22），
三档尺寸下的造型都能辨认。

## 后续事项接口

- 事项 7（辅助线）：与图标无关，直接从 `Board.draw()` 的“格子 → 箭头”之间插入即可。
- 若以后要加“设置”“暂停”等更多入口，信息栏右侧只剩一个按钮的位置，届时建议改成
  “图标按钮组”（`_draw_icon_button()` 已经可用）；`icons.py` 再加成员即可。
- 若决定改用图标字体：改 `draw_icon()` 一个函数，并在 `THIRD-PARTY.md` 登记字体许可。
