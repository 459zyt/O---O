"""
systems/image_manager.py
图片加载管理器 — 支持 GIF 逐帧动画
"""

import os
import pygame


class GifAnimation:
    """GIF 动画 — 存储所有帧和帧间隔，按时间推进"""
    def __init__(self, frames, durations):
        self.frames = frames          # [pygame.Surface, ...]
        self.durations = durations    # [ms, ...] per frame
        self._elapsed = 0.0
        self._index = 0

    def update(self, dt):
        """推进动画时间，返回当前帧"""
        self._elapsed += dt
        frame_ms = self.durations[self._index] / 1000.0
        while self._elapsed >= frame_ms:
            self._elapsed -= frame_ms
            self._index = (self._index + 1) % len(self.frames)
            frame_ms = self.durations[self._index] / 1000.0
        return self.frames[self._index]

    @property
    def current_frame(self):
        """当前帧（不推进时间）"""
        return self.frames[self._index]

    def get_width(self):
        return self.frames[0].get_width() if self.frames else 1

    def get_height(self):
        return self.frames[0].get_height() if self.frames else 1


def _load_gif(path):
    """从 GIF 文件提取所有帧。失败直接报错，不静默吞错。"""
    from PIL import Image
    pil_img = Image.open(path)
    frames = []
    durations = []
    for i in range(pil_img.n_frames):
        pil_img.seek(i)
        duration = pil_img.info.get('duration', 100)
        rgba = pil_img.convert('RGBA')
        raw = rgba.tobytes('raw', 'RGBA')
        surf = pygame.image.fromstring(raw, rgba.size, 'RGBA')
        frames.append(surf)
        durations.append(max(duration, 20))
    return GifAnimation(frames, durations)


class ImageManager:
    """加载和管理图片素材（支持 GIF 动画）"""

    def __init__(self):
        self.images = {}
        self.animations = {}

    def load(self, name, path, scale=None):
        """加载图片。找不到文件或加载失败直接报错。"""
        from data_config import get_path
        full = get_path(path)
        if not os.path.exists(full):
            raise FileNotFoundError(f"[ImageManager] 素材不存在: {full}")
        if path.lower().endswith('.gif'):
            anim = _load_gif(full)
            self.animations[name] = anim
            self.images[name] = anim.frames[0]
            return
        img = pygame.image.load(full).convert_alpha()
        if scale:
            img = pygame.transform.scale(img, scale)
        self.images[name] = img

    def get(self, name):
        return self.images.get(name)

    def get_animation(self, name):
        return self.animations.get(name)

    def clear(self):
        self.images.clear()
        self.animations.clear()
