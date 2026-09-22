# 变更记录 21：引入背景音乐与音效（事项 16）

本轮把开发者提供的 6 个音频素材接进游戏：窗口一打开就循环放背景音乐，操作与规则事件各配
一声音效。素材本身不动（文件名、内容都保持原样），新增的是**播放层**与**接线**。

## 素材

`src/another_arrow_rt265/assets/sounds/`（包内，来源与许可见 `THIRD-PARTY.md`）：

| 文件 | 时长 | 用途（`audio.Cue`） |
| --- | --- | --- |
| `button.mp3` | 0.13s | `BUTTON`：按钮、开关、快捷键 |
| `arrow-fly.mp3` | 1.15s | `ARROW_FLY`：箭头前方畅通，飞出棋盘 |
| `arrow-collide.mp3` | 1.57s | `ARROW_COLLIDE`：箭头前方被挡住 |
| `level-wim.mp3` | 1.93s | `LEVEL_CLEARED`：本关通关 |
| `level-fail.mp3` | 0.63s | `LEVEL_FAILED`：失误耗尽，本关失败 |
| `background.mp3` | 3.6MB | 背景音乐（`audio.MUSIC`），循环播放 |

`level-wim.mp3` 的文件名是原文如此（`win` 的笔误）。**没有改名**：素材由开发者提供，
Agent 只调用资源；笔误在 `audio.Cue.LEVEL_CLEARED` 的 docstring 与该枚举值里说明清楚，
测试按真实文件名核对，改不改名都不影响代码。

## 新增的两层

### 1. `resources.py`：素材定位扩展到音频

与字体同规矩，只是换了个子目录与后缀：

```python
SOUND_DIRECTORY = "sounds"
SOUND_SUFFIX = ".mp3"
sound_file_name(name) -> "button.mp3"
sound_parts(name)      -> ("sounds", "button.mp3")
sound_path(name)       -> Path | None      # 复用 asset_path()，找不到返回 None
```

放在**包内**的原因与字体完全一致：`uv_build` 的 wheel 只收 `src/<包>/` 下的文件，
Nuitka 的 `--project` 又要求“wheel 里的非 Python 文件 == 命令行声明的数据文件”，
所以 `pyproject.toml` 里依旧**不能**写 `include-data-dir`（`test_nuitka_options_declare_no_extra_data_files`
仍然钉着这一点），音频靠 `--include-package-data=another_arrow_rt265` 自动搬运。

### 2. `audio.py`：`Cue` + `Audio`

- `Cue`（`StrEnum`）的**枚举值就是文件主名**，因此“游戏里共有几声”与“目录里有哪些文件”
  是同一份声明，不可能各说各话；
- `Audio` 构造时载入全部音效（几十 KB 的短音频，播放那一刻才解码会有延迟）与背景音乐
  （几 MB，走 `pygame.mixer.music` 流式播放，不进内存）；
- 两条音量分开：`config.MUSIC_VOLUME = 0.35`（长时间循环的底噪，压低）、
  `config.SOUND_VOLUME = 0.7`（短促反馈，要听清）。

**音频是可选功能**：没有声卡（headless / CI）、素材没随程序分发、格式不被 SDL_mixer 支持时，
`Audio` 退化成“什么都不播”而不是抛异常——游戏能不能玩不取决于声音。因此：

- `_open_mixer()` 接住 `pygame.error`，`_load_sound()` / `_load_music()` 也接住
  `pygame.error` 与 `OSError`；
- 用返回值（`play()` / `start_music()` 返回这个动作有没有真的发生）与只读属性
  （`loaded_cues` / `music_ready`）告诉调用方“这一声到底响了没有”，而不是静默吞掉所有信息；
- `start_music()` **幂等**：已经在播时返回 `False` 并且不从头重播（否则每次切画面音乐都会跳一下）。

## `Game` 的接线

一条原则：**声音是旁白，不是规则**。`session` / `board` 对音频一无所知，全部音效都在
`game.py` 里按“看见了什么、结果是什么”放出去——因此 `Session` 仍然可以脱离窗口与声卡测试。

| 事件 | 音效 | 落点 |
| --- | --- | --- |
| 窗口打开 | 背景音乐（循环、只起一次） | `Game.__init__` |
| 菜单按钮 / 结算按钮 / 信息栏按钮 / 开关 / 教程跳过 | `BUTTON` | `_run_action()`（菜单）、`_handle_click()` 的各分支 |
| `H` / `R` / `G` / ←→ 快捷键 | `BUTTON` | `_handle_key()`（`Esc` 除外） |
| 点中前方畅通的箭头 | `ARROW_FLY` | `_click_board()` 收到 `ClickResult.CLEARED` |
| 点中前方被挡的箭头 | `ARROW_COLLIDE` | 同上，`ClickResult.BLOCKED`（教程里那次演示撞墙也会响，规则上仍不扣失误） |
| 点空 / 结算界面上的无效点击 | 不响 | `ClickResult.MISS` 与进行中按 Enter 都不给反馈 |
| 本关通关 | `LEVEL_CLEARED` | `_sync_audio_status()` |
| 本关失败 | `LEVEL_FAILED` | `_sync_audio_status()` |

**通关 / 失败为什么用“状态变化”而不是就地播**：这两个状态可能由点击（第 3 次撞墙当帧
就变 `FAILED`）或刷新（飞出动画播完后的结算停顿里才变 `LEVEL_CLEARED`）定下来，就地播会
漏掉一半。`Game` 记住 `_last_status`，在 `_click_board()` 与 `_update()` 之后各核对一次，
只在**变了**的那一帧放一声；重开本关 / 换关是 `FAILED|LEVEL_CLEARED → PLAYING`，安静地翻过去，
不会把上一关的结算声再放一遍。测试里直接驱动 `session.update()`（绕过 `game._update`）的用例
因此不会触发音效——这也正是分层想要的：测试可以完全关掉声音。

## 测试

新增 `tests/test_audio.py`（7 条）与 `tests/test_resources.py` 的“音频素材”一节（14 条），
`tests/test_game.py` 补一节“音乐与音效”（12 条），共 33 条：

- **素材与声明一致**：`Cue` 每个成员都有文件；`assets/sounds` 目录内容与
  `[cue.value for cue in Cue] + [MUSIC]` 恰好相等（不多不少）；素材落在包内；
  文件名写法只有 `assets/sounds/<名称>.mp3` 一处定义。断言的是**真实文件**，不是文档。
- **素材真的能用**：`pygame.mixer.Sound(path).get_length() > 0`，音乐能被
  `pygame.mixer.music.load()` 解开——只断言“文件存在”会漏掉坏编码。
- **优雅退化**：`monkeypatch` 让 `resources.sound_path` 一律返回 `None`，
  以及让 `pygame.mixer.get_init()/init()` 表现为“没有声卡”，两条路径都必须只是没有声音。
- **接线对不对**：`test_game.py` 用一个 `_RecordingAudio(Audio)` 替身（覆盖
  `play()` / `start_music()`，只记账不发声）塞进 `Game(audio_player=...)`，
  然后断言“点这个箭头 → 恰好这一声”“点空 → 一声都没有”“按钮那几下没有落到棋盘上”
  “失败只响一声”“换关不重放结算声”“进行中按 Enter 不响”。

`Game.__init__` 因此多了一个只给测试用的关键字参数 `audio_player`（不传就新建真实的
`Audio`），而不是让测试去猴补丁替换内部属性。

## 验证

- `uv run pytest -q` → **444 passed**（上轮 411，新增 33 条）；
- `uv run ruff check .` / `uv run ruff format --check .` / `uv run ty check` 全通过；
- 真实声卡（非 dummy）下 `Audio()` 实测：`mixer=(44100, -16, 2)`、5 个音效全部载入、
  `music_ready=True`、`start_music()=True`、`play(ARROW_FLY)=True`；
- `.preview/run_demo.py` 在 dummy 驱动下跑完整主循环，无异常；
- **重新打包** `uv run python -m nuitka --project`：构建日志逐条列出
  `Included data file 'another_arrow_rt265\assets\sounds\*.mp3'`，产物内 6 个音频都在；
  `.preview/capture_dist.ps1` 冒烟通过（窗口标题 `Another Arrow`，关窗退出码 0）。

## 后续（事项 17 的接口）

事项 17 要做“允许开关音乐和音效”。届时需要的是一个真实的**静音开关**：在 `Audio` 上
加 `music_enabled` / `sound_enabled`（`play()` 与 `start_music()` 先看开关），
界面沿用现成的开关组件（右下角“辅助线”那颗胶囊的样式），状态存在 `Game` 上而不是
`Session` 上——与 `show_guides` 同理，它是窗口级的显示 / 声音偏好，不随关卡重置。
本轮的 `play() -> bool` / `start_music() -> bool` 返回值已经把这个模式铺好了。
