"""
systems/sound_manager.py
音效加载与播放管理器 + BGM 背景音乐
"""

import os
import random
import pygame


class SoundManager:
    """加载和管理音效 + BGM"""

    def __init__(self):
        self.sounds = {}
        self.enabled = True
        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
        except Exception:
            self.enabled = False
            print("警告：无法初始化音效系统")

    def load(self, name, path):
        """加载单个音效"""
        from data_config import get_path
        full = get_path(path)
        if self.enabled and os.path.exists(full):
            try:
                self.sounds[name] = pygame.mixer.Sound(full)
            except Exception:
                self.sounds[name] = None
        else:
            self.sounds[name] = None

    def play(self, name):
        """播放音效"""
        if self.enabled and name in self.sounds and self.sounds[name]:
            try:
                self.sounds[name].play()
            except Exception:
                pass

    def play_random(self, name, folder):
        """
        从文件夹中随机选一个 wav 播放。首次调用时加载文件夹中所有 wav。
        """
        if not self.enabled:
            return
        cache_key = f"_random_{name}"
        if cache_key not in self.sounds:
            from data_config import get_path
            resolved = get_path(folder)
            if os.path.isdir(resolved):
                pool = []
                for f in sorted(os.listdir(resolved)):
                    if f.lower().endswith('.wav'):
                        fp = os.path.join(resolved, f)
                        try:
                            pool.append(pygame.mixer.Sound(fp))
                        except Exception:
                            pass
                self.sounds[cache_key] = pool if pool else None
            else:
                self.sounds[cache_key] = None
        pool = self.sounds.get(cache_key)
        if pool:
            random.choice(pool).play()

    def load_all(self, sound_config):
        """从配置字典批量加载"""
        for name, path in sound_config.items():
            self.load(name, path)

    # ── BGM ──

    def play_bgm(self, path, loop=False):
        """播放背景音乐（MP3 等），loop=True 循环"""
        from data_config import get_path
        full = get_path(path)
        if self.enabled and os.path.exists(full):
            try:
                pygame.mixer.music.load(full)
                pygame.mixer.music.play(-1 if loop else 0)
            except Exception:
                pass

    def stop_bgm(self):
        """停止 BGM"""
        if self.enabled:
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
