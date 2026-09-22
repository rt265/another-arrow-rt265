# 变更记录 22：设置界面与音乐 / 音效开关（事项 17）

本轮把上一轮的音频接上开关：新增一张**设置菜单页**，两个滑动开关分别控制背景音乐与音效，
开关状态存在窗口上（`Game.audio`），不随关卡、重开或回主界面重置。

## 1. 设置是一张菜单页，不是新造的画面

`ui.py` 早就写好了扩展点（“新增一个界面只需要写一个 `MenuPage` 常量，再在动作表里补一行”），
本轮兑现它，并顺带把说明卡片之外需要的第二种内容块补上：

- `MenuToggle(action, label, enabled)` —— 一个开关行：`action` 交给 `Game._run_action` 分发，
  `label` 是左侧文字，`enabled` 是**当前取值**；
- `MenuPage.toggles` 与 `MenuLayout.toggles` —— 与 `sections` / `buttons` 同级的第三种块；
- `settings_page(music_enabled, sound_enabled)`（`functools.cache`）—— 页面描述是
  **“内容 + 当前取值”**：开关画成开还是关属于页面内容，所以状态一变就换一份页面，
  四种组合各留一份；
- 排版照旧只有一处：`_stack_toggles()` 与 `_stack_sections()` 同一套排法（同宽 576、间距 18），
  开关行排在说明卡片上面，于是“开关行 + 卡片”竖着排下来左边缘是齐的。

设置页的各块（720×720 设计框）：标题 126 / 副标题 194 / 开关行 272~344 与 362~434 /
说明卡片 452~580 / 提示行 588~612 / 页脚“返回”632~688。

**说明卡片只讲“两个开关是什么关系”，不讲玩法**（玩法仍然只由第 1 关的教程承担）；
页脚提示行是产品里第一次用到 `MenuPage.hint`，用来放两条“元信息”：
游戏里怎么再打开这一页（`S`）、设置能活多久（不落盘）。新增
`test_menu_page_hint_fits_inside_its_box` 把提示行的宽度钉住。

## 2. 开关组件从此只有一份

“开关”原本只出现在右下角的“辅助线”胶囊里，代码也就长在 `draw_guide_toggle()` 里。
本轮把它抽成共享组件：

- `_draw_switch_row(surface, row, label, enabled, mouse, *, style, padding)` ——
  整行的样子（底板 + 文字 + 轨道 + 滑块）都在这里；
- `_switch_track_rect(row, padding)` —— 轨道的几何；
- `config` 里的常量也一并改名归类：`GUIDE_TOGGLE_TRACK_SIZE` / `_KNOB_RADIUS` /
  `_TRACK_ON` / `_TRACK_OFF` / `_KNOB_ON` / `_KNOB_OFF` / `GUIDE_TOGGLE_PADDING`
  → `SWITCH_TRACK_SIZE` / `SWITCH_KNOB_RADIUS` / `SWITCH_TRACK_ON` / `SWITCH_TRACK_OFF` /
  `SWITCH_KNOB_ON` / `SWITCH_KNOB_OFF` / `SWITCH_PADDING`（新开一节“滑动开关”）。

两处只有字号与左右留白不同（角落里是 15 号 + 12px，设置行是 20 号 + 28px，与说明卡片的小标题
对齐），因此传参解决。辅助线开关的绘制结果**逐像素不变**——既有的
`test_draw_guide_toggle_shows_both_positions` / `test_guide_toggle_knob_edges_are_anti_aliased`
不加修改地继续通过，就是这次抽取的判据。

## 3. 静音拦在播放层

`audio.Audio` 新增两个属性，它们就是设置页上那两个开关：

```python
player.music_enabled = (
    False  # setter 里直接 stop_music()；打开时 start_music() 立刻续上
)
player.sound_enabled = False  # play() 从此一律返回 False
```

要点是**判断只有一处**：`play()` 与 `start_music()` 自己看开关，
所以界面代码不必到处写 `if 声音开着`；`start_music()` 幂等的老承诺照旧
（关着时返回 `False`、不会起播；开着且已在播时也不会从头重播）。

## 4. 入口与“从哪儿来回哪儿去”

- **开始界面页脚**：[设置] [关于] 并排贴底（`_home_footer_rects()`）。开始界面因此是唯一
  一个有**两个**页脚按钮的页面；“开始游戏”仍然是画面正中唯一的主按钮。新增图标
  `Icon.SETTINGS`（齿轮：一圈粗环 + 八颗圆头齿）与 `Icon.BACK`（`Icon.NEXT` 的水平镜像，
  用作设置页的“返回”）。图标测试是按 `list(icons.Icon)` 参数化的，新图标自动纳入
  “画得出、颜色对、有抗锯齿”三条检查。
- **游戏中 `S` 键**：`_toggle_settings()`，开着就关上、关着就打开（与页脚按钮同一个动作）。
  之所以要给游戏里留入口：中途想静音不必退回主界面——而 `return_to_start()` 是会
  `load_level(0)` 的，退回去就等于放弃当前这一关。
- **`Scene.SETTINGS` 记得自己是从哪儿来的**：`show_settings()` 记下 `_return_scene`，
  `leave_settings()` 原样切回去，**完全不碰会话**。因此“游戏中 → 设置 → 返回”之后，
  关卡、箭头、失误、计时与教程进度都还在；`_update()` 只在 `Scene.PLAYING` 推进会话，
  所以在设置页停留多久都不会计入关卡用时（这是现成的性质，不是新加的规则）。

## 5. 设置不落盘

开关只活在本次运行里，关掉程序重开就是“两项都开”。这一点写在设置页的提示行里
（“设置关闭程序后恢复默认”），而不是让玩家自己发现。要落盘就得决定配置文件的位置
（`%APPDATA%` / exe 同级 / 包内）、格式与读写失败策略，属于另一件事，本轮不做。

## 变更内容

| 文件 | 修改 |
| --- | --- |
| `src/another_arrow_rt265/audio.py` | 新增 `music_enabled` / `sound_enabled`（含 setter：关掉立刻停、打开立刻续）；`play()` / `start_music()` 尊重开关；模块 docstring 补上“可分别关掉、只在本次运行有效” |
| `src/another_arrow_rt265/config.py` | 开关常量改名归入新的一节“滑动开关”（`SWITCH_*`） |
| `src/another_arrow_rt265/icons.py` | 新增 `Icon.SETTINGS`（齿轮）与 `Icon.BACK`（左箭头）及分发 |
| `src/another_arrow_rt265/ui.py` | 新增 `MenuToggle` / `MenuPage.toggles` / `MenuLayout.toggles` / `settings_page()` / `draw_settings_screen()` / `settings_button_rect()` / `settings_back_button_rect()` / `_stack_toggles()` / `_draw_menu_toggle()`；抽出 `_draw_switch_row()` / `_switch_track_rect()`（`draw_guide_toggle()` 改为调用它）；开始界面页脚改为两个按钮；`draw_menu_page()` 画开关行；`menu_layout()` 排开关行 |
| `src/another_arrow_rt265/game.py` | 新增 `Scene.SETTINGS`、`show_settings()` / `leave_settings()` / `toggle_music()` / `toggle_sound()` / `_toggle_settings()`；`_menu_page()` 与 `_draw()` 各补一个分支；`_handle_menu_click()` 先判开关再判按钮；动作表补 `settings` / `settings-back` / `toggle-music` / `toggle-sound`；`S` 键 |
| `tests/test_audio.py` | 新增“音乐 / 音效开关”一节（4 条）：默认都开、关掉音效后 `play()` 一律不响、关音乐停播且不能起播、打开后续上、音效开关不动音乐 |
| `tests/test_ui.py` | 新增 10 条（其中 1 条重写自旧用例，净 +9）：开始界面页脚的“设置 / 关于”、页脚行位置、设置页的页面内容 / 取值进布局 / 与辅助线开关共用组件 / 提示行文案与宽度 / 绘制与整屏覆盖、两种档位的像素判据；`MENU_PAGES` 常量把设置页纳入既有的布局 / 缩放 / 页面区分遍历 |
| `tests/test_icons.py` | 未改；但 5 条按 `list(icons.Icon)` 参数化的用例每个多出 2 个图标，共 +10 条 |
| `tests/test_game.py` | 新增“设置界面”一节（10 条）：按钮 / Enter / `S` 三条进出路径、开关翻转互不影响、中途进设置不丢进度且不计时、设置页不吃棋盘点击与游戏快捷键、开关这一下有按钮音、开关不随关卡重置、设置画面画得出来；`_RecordingAudio` 改为调用 `super().__init__()`（替身也走真实现，因此开关这些真逻辑还在）；`test_every_declared_menu_action_is_wired` 把开关动作一并覆盖 |
| `docs/agents/change-log-22-audio-settings.md` | 新增本文件 |
| `.preview/capture_dist.ps1` | **顺带修好截图**（不进版本库，仅本地工具）：之前抓的是“屏幕上窗口那块区域”，游戏窗口被浏览器 / 编辑器压住时抓到的是压在上面的窗口；现在先用 `SetWindowPos` 临时置顶、置顶后再量一次窗口位置，并用 `PrintWindow(PW_RENDERFULLCONTENT)` 让窗口自己画到位图上（失败才退回按屏幕区域拷贝）；同一个 pwsh 会话里重复跑不再因 `Win` 类型已存在而报错 |

### 被改掉的那条旧测试

`test_menu_pages_share_the_same_footer_button_spot` 断言“开始界面的页脚按钮与关于界面的
返回按钮位置相同”。开始界面现在有两个页脚按钮，两者不可能同时居中，因此这条测试的
**产品前提变了**。它被重写为 `test_menu_pages_put_their_footer_buttons_on_the_same_row`：
逐页检查“页脚按钮整行居中”，再检查“各页页脚落在同一条底线上”——保留了原意
（返回 / 次要入口不会跳来跳去），只是承认了开始界面有两个入口这件事。

`test_menu_page_buttons_come_from_the_page_description` 补上 `"settings"` 与设置页的
`"settings-back"`；`test_menu_page_text_fits_inside_its_section` / 缩放与“页面互不相同”
两条改为遍历 `MENU_PAGES`，以后加页面不用再逐条改。

## 验证

- `uv run pytest -q` → **477 passed**（上轮 444，新增 33 条：`test_audio.py` +4、`test_ui.py` +9、
  `test_game.py` +10、`test_icons.py` 的多图标参数化 +10）；
- `uv run ruff check .` / `uv run ruff format --check .` / `uv run ty check` 通过
  （`ty` 抓到一个 `tuple[Rect, Rect]` 与 `tuple[Rect, ...]` 的注解不一致，已按解包写清楚）；
- 真实声卡下实测：`start_music()=True` → `music_enabled=False` 后 `get_busy()=False`、
  `start_music()=False` → 打开后 `get_busy()=True`；`sound_enabled=False` 时
  `play(BUTTON)=False`，打开后恢复 `True`；
- `.preview/settings_frames.py`（新，临时脚本）离屏渲染设置页两种档位、悬停态与开始界面，
  人工核对排版（开关行与卡片左右对齐、提示行不压页脚、齿轮与返回箭头形状正常）；
- **重新打包** `uv run python -m nuitka --project` 后用 `.preview/capture_dist.ps1` 冒烟：
  窗口标题 `Another Arrow`、截图里能看到新的“设置 / 关于”两个页脚按钮，关窗退出码 0；
- `.preview/run_demo.py` 在 dummy 驱动下跑完整主循环，无异常。

## 后续维护

- **加一个设置项**：给 `settings_page()` 补一个 `MenuToggle`，在 `Game` 上补一个 `toggle_*`
  方法并登记进动作表即可；开关本身不必再画一遍。
- 需要“记住设置”时，落盘放在 `Game` 一侧（`Audio` 只认当前取值），
  并给读写失败一条静默退回默认值的退路——与本项目“音频不可用也只是没声音”的
  兜底风格一致。
- `MenuPage.hint` 现在有真实使用者了，提示行的宽度由
  `test_menu_page_hint_fits_inside_its_box` 守着。
