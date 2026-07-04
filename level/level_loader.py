"""
level/level_loader.py
关卡加载器 — 支持三种地图格式:
  1. level.json       — Tiled 转换后的对象格式（推荐）
  2. map.txt+meta.json — ASCII 字符地图（旧格式，兼容）
  3. 内置兜底地图

加载关卡后自动在 arts/needs/ 生成背景图片需求文件，
供美术设计师参考，避免绘制错误尺寸的图片。
"""

import os
import json
import pygame

from data_config import (
    TILE_SIZE, MAP_COLS, SCREEN_WIDTH, SCREEN_HEIGHT,
    LAVA_CONFIG, ITEM_CONFIG
)
from level.level import Level
from entities.wall import Wall


class LevelLoader:
    """关卡加载器 — 优先加载 level.json，回退到 map.txt"""

    @staticmethod
    def load(level_id):
        """加载指定关卡。直接读取 Tiled 的 level.tiled.json，内存中转换。"""
        folder = f"maps/{level_id}"
        tiled_path = os.path.join(folder, "level.tiled.json")

        # 1. 主路径：Tiled 地图文件
        if os.path.exists(tiled_path):
            from tools.tiled_converter import convert_tiled_to_level
            data = convert_tiled_to_level(tiled_path)  # 内存转换，不写盘
            level = LevelLoader._build_from_data(data)
            return level

        # 2. 回退：ASCII 文本地图
        map_path = os.path.join(folder, "map.txt")
        meta_path = os.path.join(folder, "meta.json")
        if os.path.exists(map_path):
            level, meta = LevelLoader._load_from_txt(map_path, meta_path, level_id)
            return level

        raise FileNotFoundError(
            f"关卡文件不存在: {tiled_path}\n"
            f"请在 Tiled 中创建地图并保存为 level.tiled.json"
        )

    # ================================================================
    #  从内存数据构建关卡（Tiled 转换后直接使用，无需落盘 level.json）
    # ================================================================

    @staticmethod
    def _build_from_data(data):
        """从 converter 返回的 dict 直接构建 Level 对象"""
        world = data.get("world", {})
        tile_size = world.get("tile_size", TILE_SIZE)
        width = world.get("width", MAP_COLS * tile_size)
        height = world.get("height", 35 * tile_size)

        ps = data.get("player_start", {})
        player_start = (ps.get("x", 0), ps.get("y", 0))

        cols = max(1, width // tile_size)
        rows = max(1, height // tile_size)
        empty_layout = ["." * cols] * rows
        level = Level(empty_layout, player_start, tile_size)
        level.width = width
        level.height = height

        level.walls.clear()
        level.items.clear()
        level.hazards.clear()

        lava_cfg = data.get("lava", {})
        if lava_cfg.get("enabled", True):
            level.lava_y = player_start[1] + lava_cfg.get(
                "start_y_below_player", LAVA_CONFIG["start_y_below_player"])
            level.lava_rise_speed = lava_cfg.get("rise_speed", LAVA_CONFIG["rise_speed"])

        for obj in data.get("objects", []):
            obj_type = obj.get("type", "")
            if obj_type == "wall":
                LevelLoader._add_wall_from_json(level, obj)
            elif obj_type == "item":
                LevelLoader._add_item_from_json(level, obj)
            elif obj_type == "hazard":
                LevelLoader._add_hazard_from_json(level, obj)

        return level

    @staticmethod
    def _add_wall_from_json(level, obj):
        x = obj.get("x", 0); y = obj.get("y", 0)
        w = obj.get("width", TILE_SIZE); h = obj.get("height", TILE_SIZE)
        prefab = obj.get("prefab", "normal_wall")
        components = obj.get("components", {})
        is_solid = obj.get("isSolid", True)

        type_map = {"normal_wall": "normal", "fragile_wall": "fragile", "goal_wall": "goal"}
        wall_type = type_map.get(prefab, "normal")
        if "goal" in components: wall_type = "goal"
        if "fragile" in components: wall_type = "fragile"

        wall = Wall(x, y, w, h, wall_type, isSolid=is_solid)

        # 自定义外观（设计师在 Tiled 中选图）
        wall.appearance_solid = obj.get("image_solid", "")
        wall.appearance_ghost = obj.get("image_ghost", "")

        # === 装配组件（核心：Tiled 属性 → 游戏行为） ===
        from entities.wall import create_component

        # prefab 自动兜底
        if prefab == "fragile_wall" and "fragile" not in components:
            wall.add_component("fragile", create_component("fragile"))
        if prefab == "goal_wall" and "goal" not in components:
            wall.add_component("goal", create_component("goal"))

        # JSON 中显式声明的组件
        for comp_name, comp_cfg in components.items():
            component = create_component(comp_name, comp_cfg)
            wall.add_component(comp_name, component)

        level.walls.append(wall)

    @staticmethod
    def _add_item_from_json(level, obj):
        x = obj.get("x", 0); y = obj.get("y", 0)
        w = obj.get("width", TILE_SIZE); h = obj.get("height", TILE_SIZE)
        prefab = obj.get("prefab", "length_up")
        effect = obj.get("effect", prefab)

        # KeyPair 钥匙道具：不从 ITEM_CONFIG 取值，使用 JSON 中的自定义属性
        if effect == "KeyPair" or prefab == "key":
            from entities.item import Item
            item = Item({
                "id": obj.get("id", f"key_{obj.get('key_pair_id', '?')}"),
                "position": [int(x), int(y)],
                "width": int(w), "height": int(h),
                "effect": "KeyPair",
                "prefab": "key",
                "key_pair_id": obj.get("key_pair_id", ""),
                "trigger_condition": obj.get("trigger_condition", "OnAnchor"),
                "consume_on_trigger": obj.get("consume_on_trigger", True),
            })
            level.items.append((pygame.Rect(int(x), int(y), int(w), int(h)),
                               "KeyPair", 0, item))
            return

        # 存档点道具
        if effect == "Checkpoint" or prefab == "checkpoint":
            from entities.item import Item
            item = Item({
                "id": obj.get("id", f"checkpoint_{obj.get('checkpoint_id', '?')}"),
                "position": [int(x), int(y)],
                "width": int(w), "height": int(h),
                "effect": "Checkpoint",
                "prefab": "checkpoint",
                "checkpoint_id": obj.get("checkpoint_id", item_id := f"cp_{x}_{y}"),
                "trigger_condition": obj.get("trigger_condition", "OnTouch"),
                "consume_on_trigger": obj.get("consume_on_trigger", False),
            })
            level.items.append((pygame.Rect(int(x), int(y), int(w), int(h)),
                               "Checkpoint", 0, item))
            return

        effect_map = {
            "length_up": ("LengthUp", ITEM_CONFIG["length_up"]["value"]),
            "length_down": ("LengthDown", ITEM_CONFIG["length_down"]["value"]),
            "speed_up": ("SpeedUp", ITEM_CONFIG["speed_up"]["value"]),
            "speed_down": ("SpeedDown", ITEM_CONFIG["speed_down"]["value"]),
        }
        if prefab in effect_map:
            etype, value = effect_map[prefab]
            level.items.append((pygame.Rect(int(x), int(y), int(w), int(h)), etype, value))

    @staticmethod
    def _add_hazard_from_json(level, obj):
        x = obj.get("x", 0); y = obj.get("y", 0)
        w = obj.get("width", TILE_SIZE); h = obj.get("height", TILE_SIZE)
        level.hazards.append(pygame.Rect(int(x), int(y), int(w), int(h)))

    # ================================================================
    #  map.txt 加载（ASCII 格式，旧格式兼容）
    # ================================================================

    @staticmethod
    def _load_from_txt(map_path, meta_path, level_id):
        """从 map.txt + meta.json 加载关卡，返回 (level, meta_dict)"""
        layout = LevelLoader._load_map_txt(map_path)
        meta = LevelLoader._load_meta(meta_path)

        tile_size = meta.get("tile_size", TILE_SIZE)
        player_start = tuple(meta.get("player_start", (0, 0)))

        level = Level(layout, player_start, tile_size)

        if "lava" in meta:
            lava_cfg = meta["lava"]
            if "start_y_below_player" in lava_cfg:
                level.lava_y = player_start[1] + lava_cfg["start_y_below_player"]
            if "rise_speed" in lava_cfg:
                level.lava_rise_speed = lava_cfg["rise_speed"]

        # 统一 meta
        meta.setdefault("level_id", level_id)
        meta.setdefault("name", level_id)

        return level, meta

    @staticmethod
    def _load_map_txt(path):
        if not os.path.exists(path):
            raise FileNotFoundError(f"地图文件不存在: {path}")
        with open(path, "r", encoding="utf-8") as f:
            lines = [line.rstrip("\n").rstrip("\r") for line in f if line.strip()]
        if not lines:
            raise ValueError(f"地图文件为空: {path}")
        max_len = max(len(line) for line in lines)
        return [line.ljust(max_len, '.') for line in lines]

    @staticmethod
    def _load_meta(path):
        if not os.path.exists(path):
            print(f"警告: meta.json 不存在 ({path})，使用默认配置")
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
