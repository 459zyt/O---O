"""
entities/item.py
Item 道具实体
"""

import pygame
from data_config import TILE_SIZE


class Item:
    """道具实体 — 可使用 Rect 碰撞检测，支持与墙壁重叠"""

    def __init__(self, config):
        self.id = config.get("id", "item_?")
        pos = config.get("position", [0, 0])
        self.x = pos[0] if isinstance(pos, (list, tuple)) else pos.x
        self.y = pos[1] if isinstance(pos, (list, tuple)) else pos.y
        self.width = config.get("width", config.get("size", TILE_SIZE))
        self.height = config.get("height", config.get("size", TILE_SIZE))

        self.effect = config.get("effect", config.get("prefab", "length_up"))
        self.prefab = config.get("prefab", "length_up")
        self.value = config.get("value", 0)
        self.trigger_condition = config.get("trigger_condition", "OnAnchor")

        # key_pair 钥匙 ID — 用于触发对应墙壁的 KeyPairSolidComponent
        self.key_pair_id = config.get("key_pair_id")

        # 存档点 ID — prefab="checkpoint" 时使用
        self.checkpoint_id = config.get("checkpoint_id", self.id)

        # 是否触发后消失
        # checkpoint 默认不消失；其他道具默认消失
        is_checkpoint = (self.effect == "Checkpoint" or self.prefab == "checkpoint")
        self.consume_on_trigger = config.get("consume_on_trigger", not is_checkpoint)

        self.active = True
        self.appearance = config.get("appearance")

    @property
    def center(self):
        """道具中心点 — 用于 key_pair 粒子流等"""
        return (self.x + self.width / 2, self.y + self.height / 2)

    @property
    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), int(self.width), int(self.height))

    def contains_point(self, x, y):
        return self.rect.collidepoint(x, y)

    def consume(self):
        """消耗道具"""
        self.active = False

    def apply_to_stick(self, stick):
        """应用道具效果到棍子"""
        if not self.active:
            return
        stick.apply_item(self.effect, self.value)
        self.active = False

    def __repr__(self):
        return f"Item(id={self.id}, effect={self.effect}, pos=({self.x},{self.y}), active={self.active})"
