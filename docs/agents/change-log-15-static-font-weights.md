# 变更记录 15：换成静态字重字体（用三个字重撑起界面层级）

对应 `docs/agents/basic-info.md` 中 Priority 第 13 条：**UI 优化：优化图标、字体等素材的显示效果**，
是 `change-log-13-bundled-font.md` 的下一轮（那一轮解决了“字体跟着程序走”，这一轮解决“字体只有一个字重”）。

以前随程序分发的是 **Noto Sans CJK SC 可变字重**（`NotoSansCJKsc-VF.otf`，29.3 MB）。问题是
**SDL_ttf 根本不认可变字体的轴**：它只会渲染字体里的默认实例，那 29 MB 实际上只换来一个
字重。界面里所有文字于是只能靠字号区分层级，标题不够“重”、次要说明不够“轻”。

这一轮改成随程序分发**三个静态字重**（Light / Regular / Bold，共 48.2 MB），
`resources.font_path(weight)` 按字重定位文件，`ui` 里每个文字角色都显式声明自己的字号与字重。

## 变更内容

| 文件 | 修改 |
| --- | --- |
| `src/another_arrow_rt265/assets/fonts/NotoSansCJKsc-{Light,Regular,Bold}.otf` | **新增**：三个静态字重，原样使用、未做子集化或改名 |
| `src/another_arrow_rt265/assets/fonts/NotoSansCJKsc-{Black,DemiLight,Medium,Thin}.otf` | **删除**：不随程序分发的字重，留在包内会被 `--include-package-data` 塞进 wheel 与产物（白占 62 MB） |
| `src/another_arrow_rt265/assets/fonts/NotoSansCJKsc-VF.otf` | **删除**：换静态字重后不再需要（见“为什么放弃可变字体”） |
| `src/another_arrow_rt265/resources.py` | 新增 `FontWeight`（`StrEnum`）/ `BUNDLED_WEIGHTS` / `DEFAULT_WEIGHT` / `FONT_DIRECTORY` / `FONT_STEM` / `font_file_name()` / `font_parts()`；`font_path(weight=Regular)` 取代原来的 `FONT_PARTS` 常量 |
| `src/another_arrow_rt265/ui.py` | 新增 `_TextStyle`（字号 + 字重，`font()` 取字体）与 11 个 `_TEXT_*` 样式常量，替换原来的 `_FONT_*` 字号常量；`_font(size, weight)` 支持字重；`_draw_button_content(font_size=...)` 改成 `style=` |
| `src/another_arrow_rt265/ui.py` | `_SECTION_WIDTH` 540 → **576**：换字体后拉丁字形变宽，原来的说明卡片放不下最宽的一行（见“连带修好的排版”） |
| `THIRD-PARTY.md` | 英文声明里的文件清单从 1 个可变字体改为 3 个静态字重 |
| `tests/test_resources.py` | 定位与用字体的测试全面按字重参数化，新增“三个字重真的是三种字形”“三个字重都被界面用上了”“少了某个字重时降级到 Regular”“包内字体目录与声明一致（含数量）” |
| `tests/test_ui.py`、`tests/test_tutorial.py` | 排版量尺改用 `ui._TEXT_*` 样式（`ui._TEXT_RULE.font()` 等） |
| `.preview/font_check.py` | 改成并排渲染三个内置字重 + 系统字体 + pygame 默认字体，便于一眼看出字重是否真的不同 |
| `.preview/probe_resources.py` | 逐个字重打印定位结果 |

## 关键设计

### 为什么放弃可变字体

Noto CJK 有两套发行版：可变字重（一个 29.3 MB 的 `-VF.otf`）和七个静态字重（每个约 15～17 MB）。
可变那套更小，但**用不上**：SDL_ttf（pygame 的字体后端）不提供选择 `wght` 轴的接口，
永远只会画出字体里的默认实例。也就是说包里的 29 MB 只能得到“一个字重”，
想要标题更重、次要文字更轻，还是得再带别的文件。

换成静态字重后，`pygame.font.Font(路径, 字号)` 就是全部开销：

| 方案 | 体积 | 可用字重 |
| --- | --- | --- |
| 可变字重（原方案） | 29.3 MB | 1（默认实例，轴调不了） |
| 静态字重（本方案） | 48.2 MB | 3（Light 15.9 / Regular 16.0 / Bold 16.6） |

多花 19 MB 换两个真正能用的字重层级，值得；剩下四个字重（Black / DemiLight / Medium / Thin）
没有用武之地，因此**不进包**——包内多一个文件就会被 Nuitka 的 `--include-package-data`
原样搬进产物，`tests/test_resources.py` 里有一条测试钉住“包内 `.otf` 恰好是声明过的那三个”。

### 字重映射：Bold 管强调，Regular 管正文，Light 只管“退到背景里”的文字

界面层级由**字号**与**字重**两层共同表达，两者分工明确：字号决定“这是什么”（标题 / 数值 /
正文 / 标签），字重决定“该多用力看它”。映射表就在 `ui.py` 的 `_TEXT_*` 常量里，改之前先想清楚
那处文字是主角还是配角：

| 字重 | 用在哪 | 样式常量 |
| --- | --- | --- |
| Bold | 大标题、结算标题、HUD 数值、按钮文字、卡片小标题、教程步骤读数 | `_TEXT_HERO` / `_TEXT_TITLE` / `_TEXT_VALUE` / `_TEXT_BUTTON` / `_TEXT_SECTION_TITLE` / `_TEXT_PROGRESS` |
| Regular | 正文、卡片正文、教程指引、HUD 小标题、辅助线开关、紧凑按钮 | `_TEXT_BODY` / `_TEXT_RULE` / `_TEXT_LABEL` |
| Light | 英文副标题、页脚提示行（本来就该弱化的文字） | `_TEXT_SUBTITLE` / `_TEXT_HINT` |

`_TextStyle` 是 `frozen` 的 `dataclass`，`font()` 直接落到带缓存的 `_font(size, weight)`，
所以样式常量本身没有副作用，测试也能拿它当量尺（`ui._TEXT_RULE.font().render(...)` 量出来的宽度
就是界面真正会画出来的宽度）。

### 降级链：先降字重，再降字体

`ui._font(size, weight)` 的兜底顺序是**请求的字重 → Regular → 系统 CJK 字体 → pygame 内置字体**：

- 少了 `Light.otf` 只会让次要文字变成 Regular，界面其余部分不受影响（`test_a_missing_weight_falls_back_to_the_regular_one`）；
- 三个文件都丢光才退到系统字体，这时用 `Font.set_bold()` 近似 Bold，中文最差是方块字但结构完整。

### 连带修好的排版

换字体后有一条既有测试立刻报警：`test_menu_page_text_fits_inside_its_section` 说关于界面的
`GitHub Repo: https://...` 那一行放不下了。原因不是布局，是**这套静态字体的拉丁字形比可变字体的
默认实例宽**（同一行字在 17 号下从 453px 变成 474px；汉字宽度完全一致）。
说明卡片的可用文字宽度是 540 − 28×2 − 22 = 462px，因此把 `_SECTION_WIDTH` 提到 576（两侧各留 72px），
让内容继续完整显示，而不是去删产品文案。

## 验证

```powershell
uv run pytest -q                      # 345 passed
uv run ruff check . ; uv run ruff format --check . ; uv run ty check
uv run python .preview/font_check.py  # 三个字重并排：Light 细 / Regular 中 / Bold 粗
uv run python .preview/ui_frames.py   # 21 张界面截图，人工看排版
uv run python .preview/run_demo.py    # dummy 驱动下跑真实主循环冒烟
uv build --wheel                      # wheel 内自带三个字重
uv run python -m nuitka --project     # 打包：数据文件校验通过，产物 79.6 MB / 75 文件（原 31.7 MB）
& .preview/capture_dist.ps1           # 产物冒烟：标题 Another Arrow、关窗退出码 0
```

`font_check.py` 的输出（同一行字、同为 24 号，三个文件的宽度与墨量都不同，证明不是同一个文件的三份拷贝）：

```text
Light              size=(685, 35) ink=23975
Regular            size=(690, 35) ink=24150
Bold               size=(701, 35) ink=24535
system             size=(700, 32) ink=22400
pygame default     size=(303, 16) ink=5454
```

`uv build --wheel` 的产物里能看到（未压缩 49.8 MB）：

```text
another_arrow_rt265/assets/fonts/LICENSE
another_arrow_rt265/assets/fonts/NotoSansCJKsc-Bold.otf
another_arrow_rt265/assets/fonts/NotoSansCJKsc-Light.otf
another_arrow_rt265/assets/fonts/NotoSansCJKsc-Regular.otf
```

`uv run python -m nuitka --project` 的数据文件校验同样通过，日志里逐个文件确认：

```text
Nuitka-Options: Included data file 'another_arrow_rt265\assets\fonts\LICENSE' due to package 'another_arrow_rt265' package data.
Nuitka-Options: Included data file 'another_arrow_rt265\assets\fonts\NotoSansCJKsc-Bold.otf' due to package 'another_arrow_rt265' package data.
Nuitka-Options: Included data file 'another_arrow_rt265\assets\fonts\NotoSansCJKsc-Light.otf' due to package 'another_arrow_rt265' package data.
Nuitka-Options: Included data file 'another_arrow_rt265\assets\fonts\NotoSansCJKsc-Regular.otf' due to package 'another_arrow_rt265' package data.
```

产物内的定位用 `probe_resources.py` 的 standalone 探针复核（三个字重全部命中产物内部的副本，
中文渲染 ink=8750，pygame 默认字体对照 ink=1404）：

```text
PACKAGE_DIRECTORY = ...\probe_resources.dist\another_arrow_rt265
font_path(Light)   = ...\another_arrow_rt265\assets\fonts\NotoSansCJKsc-Light.otf exists = True
font_path(Regular) = ...\another_arrow_rt265\assets\fonts\NotoSansCJKsc-Regular.otf exists = True
font_path(Bold)    = ...\another_arrow_rt265\assets\fonts\NotoSansCJKsc-Bold.otf exists = True
```

## 后续

- 图标仍是 `icons.py` 里的几何绘制，本轮没动（`THIRD-PARTY.md` 里也因此只有字体这一项）。
- 若以后要加第四个字重，注意三处联动：`resources.FontWeight` → `assets/fonts/` 里的文件 →
  `THIRD-PARTY.md`；`tests/test_resources.py::test_ui_styles_use_every_bundled_weight`
  会拒绝“打了包却没人用”的字重。
