# 变更记录 07：彩色箭头

对应 `docs/agents/basic-info.md` 中 Priority 第 9 条：**UI/UX 优化：彩色箭头**。

在此之前棋盘上的箭头全是同一种浅灰白色，14 支箭头铺在 6×6 的棋盘上时只能靠位置区分，
一眼看过去是一片“白点”。这一轮给每支箭头分配自己的主题色，并把选中 / 碰撞两种状态
改造成“在主题色上做加减”，让彩色不至于把原有的状态提示冲掉。

## 变更内容

| 文件 | 修改 |
| --- | --- |
| `src/another_arrow_rt265/palette.py` | **新增**：`theme_color()`（按格子位置取主题色）、`chip_color()` / `chip_border_color()` / `glyph_color()`（由主题色推导状态色）、`mix()`（颜色混合，比例自动夹到 `[0, 1]`） |
| `src/another_arrow_rt265/config.py` | 新增“彩色箭头”一节：`ARROW_PALETTE`（6 色）、`ARROW_PALETTE_ROW_STEP` 与 6 个混色比例；删除不再使用的 `COLOR_ARROW` / `COLOR_ARROW_SELECTED` / `COLOR_CHIP_SELECTED`；新增 `COLOR_ARROW_HIGHLIGHT`；`COLOR_SELECTION_RING` 由金色改为近白色；新增 `SELECTION_RING_SCALE` |
| `src/another_arrow_rt265/board.py` | 新增 `Board.arrow_color()`；`_draw_arrow()` 改为“圆片底色 + 圆片描边 + 主题色箭头”；`_draw_flying_arrow()` 沿用同一主题色；删掉私有的 `_mix()`，改用 `palette.mix()` |
| `tests/test_palette.py` | **新增** 52 项：调色板本身的合法性、取色规则、对比度（含 WCAG 阈值）、状态色推导、`mix()` 的边界 |
| `tests/test_board.py` | **新增** 4 项（含绘制）：颜色与格子绑定且整关稳定、每支箭头真的用自己的主题色画到像素上、选中 / 碰撞色由主题色推导、飞出动画沿用主题色 |
| `docs/agents/basic-info.md` | 事项 9 标注“（已实现）” |

## 关键设计

### 颜色怎么分配：绑定格子，而不是绑定“第几个箭头”

`palette.theme_color(row, col)` 的下标是

```text
(row × ARROW_PALETTE_ROW_STEP + col) mod len(ARROW_PALETTE)      # 3 × 行 + 列，对 6 取模
```

只跟行列有关，因此有两个好性质：

1. **整关稳定**：颜色不随“还剩几支箭头”变化——清掉别的箭头、点错了重新开始本关，
   剩下的箭头颜色都不会变，玩家不会以为颜色在传递什么信息；
2. **相邻必然不同色**：横向相邻下标差 1、纵向差 `ARROW_PALETTE_ROW_STEP`（3），
   只要这个步长不是调色板长度（6）的倍数，左右 / 上下相邻的箭头就不会撞色。
   `tests/test_palette.py` 在 12×12 的范围内把这个性质钉住了。

调色板取 6 色（珊瑚红 / 琥珀 / 薄荷 / 天蓝 / 薰衣草 / 樱粉），都是高饱和、高亮度的色，
在深色的棋盘格与底板上都能拉开对比度（测试按 WCAG 对“非文本图形”的 3.0 下限校验）。

**颜色不参与任何判定**：点击、阻挡、计分、通关都只看 `Arrow` 的行列与方向，颜色纯属视觉区分。
因此色弱玩家不会因为颜色而读不懂棋局，反而多了一条“这格和那格不是同一支箭头”的线索。

### 状态色：在主题色上做加减，不换颜色身份

选中 / 碰撞不再各用一套固定配色，而是由主题色推导：

| 状态 | 圆片底色 | 圆片描边 | 箭头 | 额外提示 |
| --- | --- | --- | --- | --- |
| 常态 | `COLOR_CHIP` 混入 22% 主题色 | 底色与主题色的中间值 | 主题色 | —— |
| 选中 | 常态底色再混入 30% 主题色（更亮、更饱和） | 同左推导 | 主题色向白提亮 18% | 近白色的呼吸环，画在圆片外沿之外 |
| 碰撞 | `COLOR_CHIP_BLOCKED` 混入 30% 主题色 | 同左推导 | 主题色向警示白染色 55% | 红色扩散环 + 前方火花 + 指向阻挡者的虚线 |

这样每支箭头在三种状态下都还是“原来那支箭头”：绿箭头被选中不会变成金色，被挡住也不会变成
纯红——状态的差别靠**亮度**和**环**表达。碰撞时箭头被“撞得发白”，和醒目的红环一起，
既保留了颜色身份又足够刺眼。

### 为什么选中环从金色改成近白色

原来的选中环是金色（`255, 203, 92`）。现在调色板里有一档琥珀色（`255, 184, 86`），金色环套在
琥珀箭头上几乎看不出来，而且彩色箭头本身已经很“花”，再加一种暖色容易和主题色混淆。
改成近白色（`238, 243, 252`）之后，环在 6 种主题色上都是同一个中性色，恒定的对比度也更好算。

呼吸环的基准半径从 `1.0 × 圆片半径` 提到 `1.07 × 圆片半径`：原来它和圆片自己的描边几乎重合，
看起来像“圆片描边变粗了”；移到外沿之外才读得出是“额外套了一圈”。

### 为什么圆片底色是压暗的主题色

如果圆片直接用主题色，箭头图形就会被同色底吃掉；如果圆片保持原来的深灰，彩色就只剩箭头那一点
面积，6 色凑在同一行会显得零碎。折中做法是**圆片底色 = 深色基准 + 约 1/4 的主题色**，再加一圈
提亮的主题色描边：既保住“亮箭头压在深底上”的原有层次（常态下箭头与圆片的对比度仍在 4:1 以上），
又让整支箭头看起来是彩色的。

## 测试

本轮新增 56 项测试（共 155 项）：

| 测试 | 验收点 |
| --- | --- |
| `test_palette_is_well_formed_and_has_enough_variety` | 调色板至少 4 色、无重复色、取值范围合法 |
| `test_neighbouring_arrows_never_share_a_color` | 12×12 网格内所有上下 / 左右相邻格子都不同色 |
| `test_theme_color_only_depends_on_the_cell_position` | 取色只与行列有关，且必定来自调色板 |
| `test_every_theme_color_stands_out_on_the_board`（6 项） | 每个主题色在棋盘格、底板、自家圆片上的对比度 ≥ 3.0 |
| `test_chip_border_separates_the_chip_from_the_cell`（6 项） | 圆片描边比底色亮，并且与棋盘格对比度 ≥ 2.0 |
| `test_arrow_stays_readable_in_every_state`（18 项） | 3 种状态 × 6 色，箭头与自家圆片的对比度都 ≥ 3.0 |
| `test_glyph_keeps_its_hue_in_every_state`（6 项） | 选中不改变通道排序；碰撞染白后主色通道不变 |
| `test_selected_and_blocked_glyphs_get_brighter`（6 项） | 选中 / 碰撞都比常态更亮，且落在主题色与目标色之间 |
| `test_selected_and_blocked_chips_are_brighter_than_the_normal_one`（6 项） | 选中 / 碰撞的圆片底色都比常态亮 |
| `test_mix_interpolates_and_clamps` | `mix()` 两端准确、比例越界被夹住 |
| `test_arrow_color_comes_from_the_palette_and_stays_stable` | 清掉若干箭头、重新构造本关后颜色布局完全一致 |
| `test_every_arrow_is_painted_in_its_own_theme_color` | 取格子中心像素：每支箭头真的画的是自己的主题色 |
| `test_selected_and_blocked_colors_are_derived_from_the_theme` | 碰撞 / 选中后像素颜色仍由主题色推导而来 |
| `test_flying_arrow_keeps_its_theme_color` | 飞出动画第 0 帧的像素就是该箭头的主题色 |

其中三项是**真正读像素**的测试（棋盘画在纯黑画布上，取格子中心——那个位置与箭头朝向无关，
必定落在箭头图形里），因此“配色只写在文档里、实际画出来还是旧颜色”这类问题跑一次测试就能发现。

## 验证

```bash
uv run pytest -q                    # 155 passed
uv run ruff check .                 # All checks passed
uv run ruff format --check .        # 21 files already formatted
uv run ty check                     # All checks passed
uv run python .preview/ui_frames.py # 10 张图（新增 08-selected-arrow）
uv run python .preview/run_demo.py  # dummy 下跑真实主循环
```

人工看图确认的三处：`02-level-three.png`（14 支箭头 6 色铺开，相邻不撞色）、
`03-mistake.png`（碰撞态：箭头撞得发白 + 红环 + 虚线指向阻挡者）、
`08-selected-arrow.png`（选中态：圆片更亮更饱和 + 白色呼吸环，与同色的常态箭头对比明显）。

## 后续事项接口

- 事项 11（辅助线）：颜色已经集中在 `palette.py`，辅助线可以取 `Board.arrow_color()`
  作为线的颜色，与箭头同色就不会多出一种视觉元素。
- 若以后要给调色板加色，只需往 `ARROW_PALETTE` 里加一项：取色步长（3）只要不是新长度的
  倍数，“相邻不同色”的测试就会继续通过。
- 颜色目前与关卡无关；如果希望每关有不同“色调”，可以在 `theme_color()` 上加一个关卡偏移量，
  改动点只有这一个函数。
