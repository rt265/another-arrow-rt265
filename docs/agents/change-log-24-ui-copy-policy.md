# 变更记录 24：界面文案规则——不写多余的说明文字

本轮**不改玩法、不改界面外观**，只把一条产品决定写进代码约定与测试：**界面不写多余的
说明文字**。触发点是设置界面的说明卡片与提示行——它们是用户**有意删除**的，
但上一轮的测试还要求它们存在，于是 `uv run pytest -q` 有 3 条失败。

## 1. 问题：代码与测试对“设置页该有什么”说法不一致

`git log` 显示 `settings_page()` 从来没有 `sections` / `hint`（`change-log-22` 把这两个
写成“已实现”，是那一轮的记述失准）。但 `tests/test_ui.py` / `tests/test_game.py` 里有 3 条
测试要求它们存在：

| 失败测试 | 报错 |
| --- | --- |
| `test_settings_page_switch_states_reach_the_layout` | `IndexError: tuple index out of range`（`layout.sections[0]`） |
| `test_settings_page_hint_points_at_the_in_game_shortcut` | `AssertionError: 设置页要有页脚提示行` |
| `test_settings_screen_ignores_board_clicks_and_in_game_shortcuts` | `IndexError: tuple index out of range`（拿卡片中心当“空白处”点） |

用户裁定：**文案是人为删掉的**，规则是“以后任何界面都不要多余的说明文字，除非用户要求”。
因此要改的是**测试与文档**，不是代码。

## 2. 改法：测试对齐产品决定

- `tests/test_ui.py`：
  - `test_settings_page_switch_states_reach_the_layout` 去掉“开关排在说明卡片上面”那条断言，
    改成“两行开关按顺序自上而下排开”（`music.bottom < sound.top`）；
  - `test_settings_page_hint_points_at_the_in_game_shortcut` **删掉**，替换为
    `test_settings_page_keeps_no_explanatory_text`：断言 `sections == ()`、`hint is None`
    （页面描述与布局两侧都查），与开始界面的 `test_start_screen_keeps_no_rule_text` 同型；
  - `test_menu_page_hint_fits_inside_its_box` 原本遍历 `MENU_PAGES` 找 `hint`，现在没有页面
    用它，那条测试会**空转**（全被 `continue` 跳过）。改成用合成的
    `ui.MenuPage(..., hint=...)` 把机制本身钉住（两条参数化文案），将来用户真的要求加一行
    提示时宽度仍有判据。
- `tests/test_game.py`：`test_settings_screen_ignores_board_clicks_and_in_game_shortcuts`
  原来点“说明卡片中心”验证设置页不吃棋盘点击，现在改点**第一行开关上方 20px 的空白带**
  （`first_toggle.top - 20`）——同样既不压开关也不压按钮，验证效果不变。
- `src/another_arrow_rt265/ui.py`：`settings_page()` 的 docstring 写明“页面刻意只有控件，
  不放说明卡片、也不放提示行”，避免后继 Agent 又把文案补回来。

`MenuPage.hint` / `MenuLayout.hint` **机制保留**（它现在是（重新）没有使用者的扩展点，
和 `decorations` 一样），这样将来用户明确要求某页加一行说明时不必重写排版代码。

## 3. 把规则写进 Agent 文档

- `AGENTS.md` 新增 **UI Copy Notice** 一节：除非用户明确要求，任何界面都不要加解释性文案；
  菜单页只放控件与必要读数；**用户删除文案是有意为之**，发现“文档说该有、代码里没有”时
  先当成产品决定，改文档与测试而不是改代码。
- `docs/agents/basic-info.md` 新增 **UI Copy** 一节，说明设置页没有卡片与提示行这条现状，
  并指向 `change-log-22` 里那处失准的记述。

## 4. 验证

```bash
uv run pytest -q          # 486 passed
uv run ruff check .       # All checks passed!
uv run ruff format --check .  # 63 files already formatted
uv run ty check           # All checks passed!
```

## 5. 教训

- Agent 的自述（“477 passed”“已实现说明卡片与提示行”）与仓库实际状态可能不一致；
  接手时要**先跑一次测试**，再读文档。
- 文档 / 变更记录里写的东西不等于当前产品要求：用户删掉的东西，作者不解释就当作
  “还没做完”，实际可能是有意为之。**默认改文档与测试**，只有用户确认后才改代码。
