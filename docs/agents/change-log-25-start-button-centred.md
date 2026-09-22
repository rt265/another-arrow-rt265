# 变更记录 25：开始界面“开始游戏”按钮改为竖直居中

本轮只动一处排版：开始界面（首屏）的主按钮**从“标题装饰下方”挪到整页竖直居中处**
（设计坐标 `y` 中心 340 → 360），其余界面与所有玩法代码未动。

## 1. 改法：一个常量

`src/another_arrow_rt265/ui.py`：

```python
# 主按钮行的中心：整页**竖直居中**（设计框的中线，720 / 2 = 360）。
_PAGE_HERO_BUTTON_Y: Final[int] = config.WINDOW_HEIGHT // 2
```

- 原来是写死的 `340`（“排在标题装饰与说明卡片之间”）。现在直接由
  `config.WINDOW_HEIGHT // 2` 推出来——**“竖直居中”这件事本身写在常量里**，
  而不是靠一个凑出来的数字；设计框高度将来若变，按钮仍然自动居中。
- 布局换算链不变：常量在设计坐标里 → `_hero_row_rects()` 算出设计坐标 →
  `start_button_rect()` / `menu_layout()` 统一 `viewport.map()` 到屏幕。
  因此窗口缩放时按钮依旧压在窗口中线上，绘制与命中判定仍共用同一份坐标。
- 受影响范围：只有 `MenuButtonPlacement.HERO` 那一行。`about` / `settings` 两个
  菜单页只用 `FOOTER` 按钮，位置**未变**（页脚仍在 632~688）。

改完的首屏自下而上：标题 126 / 副标题 194 / 箭头装饰 248（222~274）/
**主按钮中心 360（328~392，正好落在窗口中线上）** / 页脚 [设置][关于] 632~688。
主按钮与说明卡片起点（`_PAGE_SECTIONS_TOP = 420`）之间的间距从 48 变成 28，
仍然排得下；当前没有页面同时用 `HERO` 按钮与说明卡片，这条只是留着的扩展点。

## 2. 顺带同步的两处 docstring

- `MenuButtonPlacement.HERO`：`主按钮：整页竖直居中的那一行（在标题装饰与说明卡片之间）`；
- `_hero_row_rects()`：`返回主按钮行的区域（横向居中、整页竖直居中，设计坐标）`。

## 3. 测试：把产品规则换成“竖直居中”

`tests/test_ui.py` 的 `test_start_button_is_centered_above_the_footer_button` 改名为
`test_start_button_is_centred_on_the_page`，断言从“位于画面中上部”
（`button.centery < config.WINDOW_HEIGHT * 0.6`）改成**压在中线上**：

```python
assert button.centerx == config.WINDOW_WIDTH // 2
assert button.centery == config.WINDOW_HEIGHT // 2
assert button.bottom < footer.top  # 不压页脚
```

其余约束由既有的 `test_start_screen_footer_holds_the_settings_and_about_buttons`
（主按钮在页脚之上）与 `test_menu_pages_stay_centred_and_inside_the_design_box`
（各块不越界）继续覆盖，没有新增测试。

## 4. 验证

离屏渲染对照图（`.preview/start_button_y.py`，340 vs 360 各出一张 + 画窗口水平中线）
确认按钮中心与窗口中线重合、页脚与标题未受影响。

```bash
uv run pytest -q              # 486 passed
uv run ruff check .           # All checks passed!
uv run ruff format --check .  # 64 files already formatted
uv run ty check               # All checks passed!
```
