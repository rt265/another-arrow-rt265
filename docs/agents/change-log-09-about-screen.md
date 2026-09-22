# 变更记录 09：“关于”界面与菜单页接口

对应 `docs/agents/basic-info.md` 中 Priority 第 10 条：**UI 优化：添加“关于界面”，预留后续其他界面的接口**。

这一轮加了两样东西：一个给玩家看的“关于”界面，以及一套“菜单页”的描述式接口，
让以后新增界面（关卡选择、设置……）只需要写一份页面数据，而不是再抄一遍排版与事件分发。

## 变更内容

| 文件 | 修改 |
| --- | --- |
| `src/another_arrow_rt265/ui.py` | 新增菜单页描述（`MenuSection` / `MenuButtonPlacement` / `MenuButton` / `MenuPage` / `MenuLayout`）与通用排版 `menu_layout()`、通用绘制 `draw_menu_page()`；开始界面改为数据驱动的 `start_page()`，新增 `about_page()` 与 `draw_about_screen()`；`_draw_rules_panel()` 泛化为 `_draw_section_panel()`（高度按正文行数推出来）；新增 `about_button_rect()` / `about_back_button_rect()`；开始界面整体上移并新增提示行与页脚“关于”按钮 |
| `src/another_arrow_rt265/game.py` | `Scene` 新增 `ABOUT`；点击改为按菜单页描述命中（`_handle_menu_click()`）；新增 `show_about()` 与动作表 `_run_action()`；`_run_primary_action()` 改读 `MenuPage.default_action()`；`H` 键在菜单页也生效 |
| `src/another_arrow_rt265/config.py` | 新增 `VERSION`（“关于”界面显示的版本号，与 `pyproject.toml` 一致） |
| `src/another_arrow_rt265/icons.py` | `Icon` 新增 `INFO` 与 `_draw_info()`（圆圈 + 点 + 竖杆，依旧是纯几何绘制） |
| `tests/test_ui.py` | **新增** 9 项：菜单页内容都在窗口内且不重叠、两个页面共用同一个页脚按钮位置、按钮来自页面描述、每行文字放得下卡片、卡片文案跟会话走、默认按钮、关于界面绘制 / 铺满整屏、两张页面画出来必须不同 |
| `tests/test_game.py` | **新增** 7 项：页脚“关于”进关于界面、返回按钮 / Enter / `H` 回开始界面、关于界面不响应棋盘与游戏内快捷键、关于界面整帧绘制、声明的动作都已接线 |
| `tests/test_config.py` | **新增** 1 项：`config.VERSION` 与 `pyproject.toml` 的 `version` 一致 |
| `.preview/ui_frames.py` | 新增 `11-about.png` / `11-about-hover.png`，图标表改为按图标数自动增高（现在是 4 种图标） |
| `.preview/run_demo.py` | 主循环冒烟先走一遍“开始界面 → 关于界面 → 返回”，再进关卡 |
| `docs/agents/basic-info.md` | 事项 10 标注“（已实现）” |

## 关键设计

### 菜单页是“数据”，不是“代码”

新增的四个描述对象把所有页面的公共结构抽了出来：

| 对象 | 说明 |
| --- | --- |
| `MenuSection` | 一块说明卡片：小标题 + 若干行正文；`height` 按行数推出来（3 行 = 158px，与旧的“玩法”卡片同高） |
| `MenuButton` | 一个按钮：`action` 动作名 + 文案 + 图标 + 是否主按钮 + 摆放位置 |
| `MenuButtonPlacement` | 摆放位置：`HERO`（标题装饰下方、卡片之前）/ `FOOTER`（卡片之后、贴住页面底部） |
| `MenuPage` | 一整页：标题、副标题、说明卡片、按钮、是否画方向箭头装饰、提示行；`default_action()` 给出 Enter / 空格该触发哪个按钮 |

排版只算一次：`menu_layout(page)` 返回 `MenuLayout`（卡片区域 + 提示行 + 每个按钮的区域），
**绘制（`draw_menu_page`）与命中判定（`Game._handle_menu_click`）读的是同一份结果**，
因此不存在“按钮画在这里、判定算在那里”的错位——这也是原来 `ui.py` 里“几何只有一份”的
约定（见 `board_area()` / `hud_home_button_rect()` 等）在菜单页上的延续。

页脚按钮是**贴底**排的，不是跟在内容后面：所以开始界面的“关于”与关于界面的“返回主界面”
落在完全同一个坐标（`tests/test_ui.py::test_menu_pages_share_the_same_footer_button_spot`），
翻页时按钮不会跳。

### 界面 ↔ 逻辑的唯一接口：动作名

按钮不带回调函数，只声明一个动作名（`"start"` / `"about"` / `"home"`），
由 `Game._run_action()` 的动作表分发：

```python
actions = {"start": self.start, "about": self.show_about, "home": self.return_to_start}
```

好处有三个：`ui` 不必导入 `Game`（不会绕成循环依赖）；命中判定与绘制共用同一份按钮描述；
动作名写错时**立刻报错**（`KeyError: 未注册的菜单动作：…`）而不是“点了没反应”静默失效。
`tests/test_game.py::test_every_declared_menu_action_is_wired` 会把所有页面声明的动作都跑一遍，
顺带检查未注册的动作确实会抛错。

于是新增一个界面的步骤是固定的三步：

1. 在 `ui.py` 里写一个 `MenuPage`（照抄 `about_page()` 的形状）；
2. 在 `game.py` 的 `Scene` 里加一个成员，并在 `_menu_page()`（取页面描述）与 `_draw()`
   （选绘制函数）各补一行；
3. 在 `_run_action()` 的动作表里补上按钮的 `action`。

两个页面时 `_menu_page()` 还是 `if/elif`；页面多起来之后把它换成
`{Scene.ABOUT: ui.about_page, ...}` 的字典即可，调用方不用改。

### “关于”界面上放什么、不放什么

页面只有两块卡片，信息都来自已经有单一来源的地方，不新增需要手工维护的副本：

| 内容 | 来源 |
| --- | --- |
| 玩法与操作 3 行（其中玩法 3 条） | `_RULES`（与开始界面“玩法”卡片同一份常量） |
| 版本号 | `config.VERSION`（`tests/test_config.py` 钉住它与 `pyproject.toml` 一致） |
| 关卡总数 / 失误上限 | `Session.total_levels` / `Session.max_mistakes`，与开始界面页脚提示行同源，改关卡后自动跟着变 |
| 技术栈与“图标与箭头全部由代码绘制，未使用第三方素材” | 项目的实际做法（`THIRD-PARTY.md` 仍为空，符合 AGENTS.md 的 Copyright Notice） |

刻意没放的东西：作者邮箱、开源协议全文、构建命令。这些属于仓库文档（`README.md`）的读者，
不是玩家的关切；界面上的每一行都要挤占卡片宽度（`test_menu_page_text_fits_inside_its_section`
就是为“加字之前先看这里”准备的）。

### 开始界面为什么整体上移

原来的开始界面从标题 140 一路排到“玩法”卡片 468~626，底部只剩 94px，
放不下新增的提示行 + 页脚按钮。于是把整段内容上移，重新排成：

| 区块 | 位置（y） |
| --- | --- |
| 大标题 / 副标题 | 126 / 194 |
| 方向箭头装饰（52px 圆牌） | 248 |
| 主按钮“开始游戏”（264×64） | 308 ~ 372 |
| “玩法”卡片（540×158） | 420 ~ 578 |
| 提示行“共 N 关 · 每关最多 M 次失误”（16 号灰字） | 586 ~ 610 |
| 页脚“关于”按钮（196×56） | 632 ~ 688 |

关于界面复用同一套骨架：标题 / 副标题同高，没有主按钮时卡片从 272 开始（272~430、448~606），
页脚按钮同样落在 632~688。

提示行是这一轮唯一新增的“动态文字”：它报的是**关卡总数与失误上限**，
既是给玩家的信息，也让 `draw_start_screen(surface, session, mouse)` 这个既有签名
重新有了意义（`session` 现在真的被用上了，之前是只签名不用）。

### 键位：`H` 统一为“回主界面”，`R` / `←` `→` 仍只在关卡里

| 按键 | 开始 / 关于界面 | 游戏画面 |
| --- | --- | --- |
| `Esc` | 退出程序 | 退出程序 |
| `Enter` / 空格 | 页面默认按钮（开始游戏 / 返回主界面） | 结算时“下一关 / 重试本关”，进行中不响应 |
| `H` | 回开始界面（本轮新增） | 回开始界面 |
| `R` | 不响应 | 重开本关 |
| `←` `→` | 不响应 | 切换关卡（开发用） |

`H` = “回到主界面”在两个菜单页上都说得通（开始界面按了等于原地不动），
而 `R`、左右方向键会改变进度，留在关卡里更安全。

### `INFO` 图标

“关于”按钮上的图标依旧是几何绘制（圆圈描边 + 一个圆点 + 一根竖杆），
没有引入字体或图片：一是 `assets/` 在包外，用图标字体要额外配 Nuitka 的
`include-data-dir` 和 exe 同级目录定位；二是图标颜色要跟着按钮的悬停态走。
`tests/test_icons.py` 的参数化测试会自动覆盖新图标（描边不出外接框、颜色单一、随尺寸缩放）。

## 测试

本轮新增 21 项（共 196 项）：17 项显式测试，外加 `test_icons.py` 里 4 个
以 `list(icons.Icon)` 参数化的用例多出的 4 个 `INFO` 实例。

| 测试 | 验收点 |
| --- | --- |
| `test_menu_pages_stack_their_blocks_inside_the_window` | 两张菜单页的卡片 / 提示行 / 按钮都在窗口内且互不重叠 |
| `test_menu_pages_share_the_same_footer_button_spot` | 两个页面的页脚按钮坐标完全相同、居中 |
| `test_menu_page_buttons_come_from_the_page_description` | 可点按钮集合 = 页面声明的 `action` 集合 |
| `test_menu_page_text_fits_inside_its_section` | 真实渲染量宽，卡片每行都放得下（含“99 关 / 9 次”的极端数字） |
| `test_menu_pages_report_content_from_the_session` | 卡片与提示行里的关卡数 / 失误上限跟会话走 |
| `test_menu_pages_pick_a_default_action_for_enter` | 开始 → `start`，关于 → `home` |
| `test_draw_about_screen_renders_without_error` / `..._covers_the_whole_window` | 关于界面可绘制，且连背景一起铺满整屏 |
| `test_menu_pages_are_visually_distinct` | 两张页面不能画出同一张图（防止画错页面） |
| `test_start_screen_footer_opens_the_about_screen` | 页脚“关于” → `Scene.ABOUT` |
| `test_about_screen_back_button_returns_to_the_start_screen` | 返回按钮 → `Scene.START` |
| `test_enter_returns_from_the_about_screen` / `test_h_key_returns_from_the_about_screen` | `Enter`、`H` 都能回到开始界面 |
| `test_about_screen_ignores_board_and_in_game_shortcuts` | 关于界面点棋盘、按 `R` / `→` 都不改状态 |
| `test_draw_renders_the_about_screen_frame` | `Game._draw()` 走关于界面分支不出错 |
| `test_every_declared_menu_action_is_wired` | 所有声明的动作都能分发；未注册动作显式 `KeyError` |
| `test_version_matches_pyproject` | `config.VERSION` 与本项目元数据一致 |

## 验证

```bash
uv run pytest -q                    # 196 passed
uv run ruff check .                 # All checks passed
uv run ruff format --check .        # 22 files already formatted
uv run ty check                     # All checks passed
uv run python .preview/ui_frames.py # 14 张图（新增 11-about / 11-about-hover）
uv run python .preview/run_demo.py  # 本关用时 0.604s，主循环冒烟通过
```

人工看图确认了三处：`11-about.png`（两块卡片 + 页脚“返回主界面”）、
`00-start.png`（整体上移后的开始界面、提示行与页脚的“关于”按钮）、
`07-icons.png`（新增的 `INFO` 图标在 16 / 24 / 32px 三档下都能认出是“i”）。

## 后续事项接口

- 事项 8（第一关交互式教程）：教程本身是一个新的 `Scene`，可以直接用
  `MenuPage` 描述“标题 + 说明卡片 + 按钮”，也可以只借 `MenuButton` 与动作表——
  引导层不需要新的排版代码。
- 事项 12（关卡选择的配置自由度）：关卡选择页是典型的“卡片列表”页面，
  现有的 `MenuSection` 表达不了“可点的关卡格子”，届时再加一个 `MenuGrid` 之类的
  描述对象即可；`menu_layout()` 与 `_run_action()` 的形态不用变。
- 设置页（音量、配色方案）同样按“三步”接入；若需要开关控件，
  建议新增 `MenuToggle` 而不是把 `MenuButton` 改成多用途。
