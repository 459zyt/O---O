"""
data_config.py
O---O 游戏统一配置文件
所有核心数值、素材路径、音效路径都在此配置
"""

import math

# =========================
# 屏幕配置
# =========================
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60

# 视差滚动比 — 远景滚动速度 = 近景 / PARALLAX_RATIO
# 5 = 玩家爬 500px，背景只移动 100px
PARALLAX_RATIO = 5

# =========================
# 地图格子配置
# =========================
TILE_SIZE = 32
MAP_COLS = 20  # 地图宽度（格子数）
MAP_ROWS = 35  # 地图高度（格子数）
GAME_AREA_X = (SCREEN_WIDTH - MAP_COLS * TILE_SIZE) // 2  # 游戏区域左边距

# =========================
# 颜色定义（海难主题 — 蓝色调）
# =========================
COLOR_BG = (10, 20, 50)
COLOR_MENU_BG = (5, 15, 40)
COLOR_LAVA_GLOW = (60, 140, 255, 30)
COLOR_WHITE = (220, 235, 255)
COLOR_GRAY = (140, 160, 190)
COLOR_DARK = (15, 30, 60)
COLOR_GOLD = (80, 200, 255)
COLOR_RED = (255, 100, 80)
COLOR_GREEN = (60, 220, 80)
COLOR_BLUE = (60, 140, 255)

# =========================
# 棍子默认配置
# =========================
STICK_CONFIG = {
    "left_endpoint_mass": 1.0,
    "left_endpoint_radius": 12,
    "right_endpoint_mass": 1.0,
    "right_endpoint_radius": 12,
    "rod_mass": 2.0,
    "rod_radius": 4,
    "length": 120,  # 初始棍长（像素）
    "angular_speed": 180,  # 度/秒
    "min_length": 70,
    "max_length": 220,
}

# =========================
# 重力配置
# =========================
GRAVITY_CONFIG = {
    "gravity": 600,  # 像素/秒²（pygame坐标系，y轴向下为正）
}

# =========================
# 岩浆配置
# =========================
LAVA_CONFIG = {
    "start_y_below_player": 200,  # 岩浆初始位置：玩家下方多少像素
    "rise_speed": 25,  # 像素/秒
    "kill_margin": 10,
}

# =========================
# 墙壁默认配置
# =========================
WALL_CONFIG = {
    "default_length": TILE_SIZE,
    "normal_appearance": "arts/walls/normal_wall.png",
    "fragile_appearance": "arts/walls/fragile_wall.png",
    "goal_appearance": "arts/walls/goal_wall.png",
}

# =========================
# 道具配置
# =========================
ITEM_CONFIG = {
    "length_up": {
        "effect": "LengthUp",
        "value": 30,
        "appearance": "arts/items/length_up.png",
    },
    "length_down": {
        "effect": "LengthDown",
        "value": 30,
        "appearance": "arts/items/length_down.png",
    },
    "speed_up": {
        "effect": "SpeedUp",
        "value": 0.3,  # 倍率增加
        "appearance": "arts/items/speed_up.png",
    },
    "speed_down": {
        "effect": "SpeedDown",
        "value": 0.3,
        "appearance": "arts/items/speed_down.png",
    },
    "hazard": {
        "effect": "Hazard",
        "appearance": "arts/items/hazard.png",
    },
}

# =========================
# 音效配置
# =========================
SOUND_CONFIG = {
    "anchor_success": "arts/sounds/anchor_success.wav",
    "anchor_miss": "arts/sounds/anchor_miss.wav",
    "anchor_fragile": "arts/sounds/anchor_fragile.wav",
    "wall_break": "arts/sounds/wall_break.wav",
    "goal": "arts/sounds/goal.wav",
    "hazard": "arts/sounds/hazard.wav",
    "length_up": "arts/sounds/length_up.wav",
    "length_down": "arts/sounds/length_down.wav",
    "speed_up": "arts/sounds/speed_up.wav",
    "speed_down": "arts/sounds/speed_down.wav",
    "lava_death": "arts/sounds/lava_death.wav",
    "game_start": "arts/sounds/game_start.wav",
    "restart": "arts/sounds/restart.wav",
}

# =========================
# 地图符号配置
# =========================
TILE_SYMBOL_CONFIG = {
    "#": "normal_wall",
    "F": "fragile_wall",
    "G": "goal_wall",
    "H": "hazard",
    "+": "length_up",
    "-": "length_down",
    ">": "speed_up",
    "<": "speed_down",
    ".": "empty",
}

# =========================
# 粒子效果配置
# =========================
PARTICLE_CONFIG = {
    "anchor_spark_count": 12,
    "anchor_spark_lifetime": 0.4,
    "anchor_spark_speed": 200,
    "wall_break_count": 20,
    "wall_break_lifetime": 0.6,
}
