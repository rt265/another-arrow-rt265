"""背景音乐与音效的加载与播放测试。

素材“真的在、而且只有声明过的那些”由 ``tests/test_resources.py`` 按目录核对；
这里测 :class:`~another_arrow_rt265.audio.Audio` 的行为：素材真能解码、每个音效都能
载入、音乐只起一次循环，以及**没有声卡 / 没有素材时安静退化**——游戏能不能玩
不取决于声音，因此这些路径一条异常都不该抛。

测试跑在 SDL 的 dummy 驱动上（见 ``conftest.py``），不会真的发出声音。
"""

from __future__ import annotations

import pygame
import pytest

from another_arrow_rt265 import audio, config, resources


@pytest.fixture(autouse=True)
def mixer_ready() -> None:
    """直接构造 ``pygame.mixer.Sound`` 之前，混音器得先初始化。"""
    if pygame.mixer.get_init() is None:
        pygame.mixer.init()


def test_the_bundled_sounds_really_decode() -> None:
    """文件在还不够：SDL_mixer 得真能解开它（格式 / 编码坏掉会在这里露出来）。"""
    for cue in audio.Cue:
        path = resources.sound_path(cue.value)
        assert path is not None, cue

        assert pygame.mixer.Sound(str(path)).get_length() > 0.0, cue

    # 音乐走流式通道、不进内存，因此只确认 SDL_mixer 解得开它。
    music = resources.sound_path(audio.MUSIC)
    assert music is not None
    pygame.mixer.music.load(str(music))


def test_audio_loads_every_cue_and_the_music() -> None:
    player = audio.Audio()

    assert player.loaded_cues == frozenset(audio.Cue)
    assert player.music_ready is True


def test_playing_a_cue_reports_that_it_played() -> None:
    player = audio.Audio()

    for cue in audio.Cue:
        assert player.play(cue) is True, cue


def test_the_music_loops_and_is_never_restarted() -> None:
    """``start_music()`` 幂等：已经在播时不会从头重播（否则每次切画面音乐都会跳）。"""
    player = audio.Audio()
    player.stop_music()

    assert player.start_music() is True, "停掉之后应该能重新起播"
    assert player.start_music() is False, "已经在播时不该再起一次"


def test_music_is_quieter_than_the_sound_effects() -> None:
    """音乐是长时间循环的底噪，音效是短促反馈：前者要让位给后者。"""
    assert 0.0 < config.MUSIC_VOLUME < config.SOUND_VOLUME <= 1.0


# ---------------------------------------------------------------- 优雅退化


def test_missing_sound_files_are_silent(monkeypatch: pytest.MonkeyPatch) -> None:
    """素材没随程序分发时，整块音频退化成空操作（而不是崩在启动那一刻）。"""
    monkeypatch.setattr(resources, "sound_path", lambda name: None)

    player = audio.Audio()

    assert player.loaded_cues == frozenset()
    assert player.music_ready is False
    assert player.play(audio.Cue.BUTTON) is False
    assert player.start_music() is False
    player.stop_music()


def test_no_mixer_at_all_is_silent(monkeypatch: pytest.MonkeyPatch) -> None:
    """没有声卡（headless / CI）时同样只是没有声音。"""

    def broken_init(*args: object, **kwargs: object) -> None:
        raise pygame.error("no audio device")

    monkeypatch.setattr(pygame.mixer, "get_init", lambda: None)
    monkeypatch.setattr(pygame.mixer, "init", broken_init)

    player = audio.Audio()

    assert player.loaded_cues == frozenset()
    assert player.music_ready is False
    assert player.play(audio.Cue.LEVEL_FAILED) is False
    player.start_music()
    player.stop_music()
