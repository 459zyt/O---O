"""
core/input_manager.py
输入管理器 — 将 Pygame 事件转换为游戏内部事件
"""

import pygame


class InputManager:
    """将 Pygame 原始事件转换为游戏内部事件名"""

    KEY_MAP = {
        pygame.K_SPACE: "space",
        pygame.K_ESCAPE: "quit",
        pygame.K_F3: "toggle_debug",
        pygame.K_r: "restart",
        pygame.K_p: "test_level",
    }

    def poll(self):
        """轮询事件，返回游戏内部事件名列表"""
        events = []

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                events.append("quit")

            elif event.type == pygame.KEYDOWN:
                mapped = self.KEY_MAP.get(event.key)
                if mapped:
                    events.append(mapped)

        return events
