"""背景音乐与音效。

素材随程序分发，放在包内的 ``assets/sounds/``（定位方式见 :mod:`another_arrow_rt265.resources`），
由 :class:`Audio` 统一加载。两条播放路径分开：

- **背景音乐**走 ``pygame.mixer.music``，流式解码、循环播放（素材有好几 MB，
  不适合整个读进内存），窗口一打开就开始放；
- **音效**走 ``pygame.mixer.Sound``，构造时就全部载入内存（都是几十 KB 的短音频，
  播放那一瞬间才解码会听出延迟）。

音频是**可选**的：没有声卡（headless / CI）、素材没随程序分发、格式不被 SDL_mixer
支持时，:class:`Audio` 会安静地退化成“什么都不播”，而不是让游戏崩在启动那一刻。
游戏能不能玩不取决于声音，因此这里不抛异常，只用返回值 / :attr:`Audio.loaded_cues`
告诉调用方“这一声到底响了没有”。

音频还可以**分别关掉**（事项 17）：:attr:`Audio.music_enabled` 与
:attr:`Audio.sound_enabled` 就是“设置”界面里那两个开关，关掉之后
:meth:`Audio.play` 与 :meth:`Audio.start_music` 直接返回 ``False``——静音是
在**播放层**拦下的，所以界面代码不必到处写 ``if 声音开着``。两个开关只活在
本次运行里（不落盘），关掉程序后恢复默认的“两项都开”。

音效与界面动作是**一对一**的：:class:`Cue` 的每个成员都对应 ``assets/sounds/`` 里的
一个文件（枚举值就是文件主名），由 ``tests/test_audio.py`` 与 ``tests/test_resources.py``
钉住“声明的每一声都有实物”。本模块只依赖 pygame 的混音器、不碰窗口，因此可以单独测。
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

import pygame

from another_arrow_rt265 import config, resources


class Cue(StrEnum):
    """游戏里会用到的音效（枚举值 = ``assets/sounds/`` 里的文件主名）。"""

    BUTTON = "button"
    """界面操作：按钮、开关、快捷键。"""

    ARROW_FLY = "arrow-fly"
    """箭头前方畅通，飞出棋盘。"""

    ARROW_COLLIDE = "arrow-collide"
    """箭头前方被挡住，撞了上去（教程里那次演示撞墙也会响）。"""

    LEVEL_CLEARED = "level-wim"
    """本关通关。素材文件名如此（``win`` 的笔误），为不改动开发者提供的素材而沿用。"""

    LEVEL_FAILED = "level-fail"
    """失误次数耗尽，本关失败。"""


#: 背景音乐的文件主名：循环播放，从窗口打开放到程序退出。
MUSIC: Final[str] = "background"


class Audio:
    """随程序分发的背景音乐与音效的播放器。

    构造时初始化混音器并载入素材；任何一步失败都只是“没有声音”，不影响游戏逻辑。
    音量来自 :mod:`another_arrow_rt265.config`，音乐与音效各一条；两个播放开关
    （:attr:`music_enabled` / :attr:`sound_enabled`）默认都开着。
    """

    def __init__(
        self,
        *,
        music_volume: float = config.MUSIC_VOLUME,
        sound_volume: float = config.SOUND_VOLUME,
    ) -> None:
        """载入素材。

        Args:
            music_volume: 背景音乐音量（0.0 ~ 1.0）。
            sound_volume: 音效音量（0.0 ~ 1.0）。
        """
        self._sounds: dict[Cue, pygame.mixer.Sound] = {}
        self._music_ready = False
        self._music_enabled = True
        self._sound_enabled = True
        self._music_volume = music_volume
        self._sound_volume = sound_volume
        self._load()

    @property
    def loaded_cues(self) -> frozenset[Cue]:
        """已成功载入的音效集合；没有声卡或素材缺失时是空集。"""
        return frozenset(self._sounds)

    @property
    def music_ready(self) -> bool:
        """背景音乐是否装载好、可以播放。"""
        return self._music_ready

    @property
    def music_enabled(self) -> bool:
        """背景音乐是否允许播放（“设置”界面里的音乐开关）。"""
        return self._music_enabled

    @music_enabled.setter
    def music_enabled(self, enabled: bool) -> None:
        """开关背景音乐：关掉立刻停，打开立刻从头续上。"""
        self._music_enabled = enabled
        if enabled:
            self.start_music()
        else:
            self.stop_music()

    @property
    def sound_enabled(self) -> bool:
        """音效是否允许播放（“设置”界面里的音效开关）。"""
        return self._sound_enabled

    @sound_enabled.setter
    def sound_enabled(self, enabled: bool) -> None:
        """开关音效：只记状态，不需要停什么（音效都是短音，播完就没了）。"""
        self._sound_enabled = enabled

    def play(self, cue: Cue) -> bool:
        """播放一个音效。

        Returns:
            是否真的响了。``False`` 有三种情形：音效开关关着、这一声的素材没载入成功
            （缺文件、无声卡或格式不支持）。调用方照常往下走即可。
        """
        if not self._sound_enabled:
            return False
        sound = self._sounds.get(cue)
        if sound is None:
            return False
        sound.play()
        return True

    def start_music(self) -> bool:
        """开始循环播放背景音乐。

        Returns:
            本次调用是否真的起了播放。已经在播、或者音乐开关关着时返回 ``False``，
            并且**从头重播也不会发生**——这个方法可以放心地重复调用。
        """
        if not self._music_enabled or not self._music_ready:
            return False
        if pygame.mixer.music.get_busy():
            return False
        pygame.mixer.music.play(loops=-1)
        return True

    def stop_music(self) -> None:
        """停止背景音乐（没有装载成功时什么也不做）。"""
        if self._music_ready:
            pygame.mixer.music.stop()

    # ------------------------------------------------------------ 载入

    def _load(self) -> None:
        """打开混音器、载入全部音效与背景音乐。"""
        if not self._open_mixer():
            return
        for cue in Cue:
            sound = self._load_sound(cue)
            if sound is not None:
                self._sounds[cue] = sound
        self._load_music()

    @staticmethod
    def _open_mixer() -> bool:
        """确保混音器可用。

        ``pygame.init()`` 通常已经开好了混音器，此时什么都不用做；没有声卡时它会
        静默跳过混音器初始化，于是这里再试一次并接住异常。
        """
        if pygame.mixer.get_init() is not None:
            return True
        try:
            pygame.mixer.init()
        except pygame.error:
            return False
        return pygame.mixer.get_init() is not None

    def _load_sound(self, cue: Cue) -> pygame.mixer.Sound | None:
        """载入单个音效；素材缺失或解码失败时返回 ``None``。"""
        path = resources.sound_path(cue.value)
        if path is None:
            return None
        try:
            sound = pygame.mixer.Sound(str(path))
        except (pygame.error, OSError):
            return None
        sound.set_volume(self._sound_volume)
        return sound

    def _load_music(self) -> None:
        """把背景音乐挂到 ``pygame.mixer.music`` 上（只装载，不播放）。"""
        path = resources.sound_path(MUSIC)
        if path is None:
            return
        try:
            pygame.mixer.music.load(str(path))
        except (pygame.error, OSError):
            return
        pygame.mixer.music.set_volume(self._music_volume)
        self._music_ready = True
