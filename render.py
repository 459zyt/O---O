"""
render.py
O---O UI 与视觉特效渲染模块

设计目标：
1. 所有字体、颜色、UI 特效参数集中管理
2. 美术设计师可以通过修改本文件调整 UI 风格
3. 游戏逻辑代码不直接处理文字特效
4. 音游感 + 唯美感 + 极简锚点主题
"""

import math
import random
import os
import pygame

# ============================================================
# 字体路径配置
# ============================================================

FONT_PATHS = {
    # 主标题字体：Bodoni Moda SemiBold — 优雅衬线体，钢琴般的质感
    "title": "arts/fonts/BodoniModa-SemiBold.ttf",

    # 备用标题字体
    "title_alt": "arts/fonts/BodoniModa-SemiBold.ttf",

    # 数字与游戏内 UI 字体
    "ui": "arts/fonts/BodoniModa-Medium.ttf",

    # 中文提示字体：Noto Sans SC Light
    "cn": "arts/fonts/NotoSansSC-Light.ttf",

    # 优雅副标题字体
    "elegant": "arts/fonts/BodoniModa-Regular.ttf",
}

# 系统回退（仅在项目字体缺失时使用）
_FALLBACK_FONTS = {
    "title":   ["C:/Windows/Fonts/bahnschrift.ttf", "C:/Windows/Fonts/arial.ttf"],
    "title_alt": ["C:/Windows/Fonts/bahnschrift.ttf", "C:/Windows/Fonts/arial.ttf"],
    "ui":      ["C:/Windows/Fonts/consola.ttf", "C:/Windows/Fonts/arial.ttf"],
    "cn":      ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"],
    "elegant": ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"],
}


def _resolve_font_path(key):
    """解析字体路径：项目字体 > 系统回退"""
    custom = FONT_PATHS.get(key, "")
    if custom and os.path.exists(custom):
        return custom
    for fb in _FALLBACK_FONTS.get(key, []):
        if os.path.exists(fb):
            return fb
    return None


# ============================================================
# 颜色配置 (UI 专用 — 游戏对象颜色保留在 main.py / data_config)
# ============================================================

COLORS = {
    "pure_white": (240, 248, 255),
    "ice_cyan": (100, 220, 255),
    "neon_cyan": (0, 200, 255),
    "soft_purple": (150, 160, 255),
    "deep_navy": (5, 15, 40),
    "lava_orange": (60, 160, 255),
    "danger_red": (255, 80, 60),
    "goal_gold": (100, 220, 255),
    "piano_black": (5, 10, 30),
    "piano_white": (230, 240, 250),
    "miss_gray": (100, 140, 170),
    "snap_green": (100, 230, 200),
    "speed_blue": (80, 180, 255),
    "slow_purple": (160, 140, 255),
    "longer_green": (100, 220, 180),
    "shorter_red": (255, 140, 120),
    "overlay_dark": (5, 15, 40),
    "overlay_dead": (10, 20, 60),
}


# ============================================================
# 特效参数
# ============================================================

EFFECT_CONFIG = {
    "neon_pulse": {
        "base_alpha": 80,
        "pulse_strength": 120,
        "pulse_speed": 3.0,
        "glow_offsets": [14, 9, 5, 2],
        "primary_glow": "ice_cyan",
        "secondary_glow": "soft_purple",
        "flicker_chance": 0.015,
        "flicker_strength": 0.35,
    },

    "soft_blink": {
        "min_alpha": 90,
        "max_alpha": 230,
        "blink_speed": 2.0,
    },

    "rhythm_flash": {
        "duration": 0.45,
        "max_scale": 1.18,
        "fade_speed": 4.0,
        "flash_color": "neon_cyan",
    },

    "piano_shine": {
        "shine_speed": 120,
        "shine_width": 80,
        "shine_alpha": 90,
        "base_color": "piano_white",
        "line_color": "ice_cyan",
    },

    "danger_flicker": {
        "flicker_speed": 18.0,
        "jitter_amount": 3,
        "warning_color": "danger_red",
        "glow_color": "lava_orange",
    },
}

# ============================================================
# 气泡弹字配置
# ============================================================

BUBBLE_CONFIG = {
    "snap": {       # 成功抓住墙壁
        "texts": ["SNAP!!", "ANCHOR!", "GOT IT!"],
        "color": "snap_green",
        "glow_color": "neon_cyan",
        "lifetime": 0.9,
        "float_speed": 80,
        "start_scale": 0.4,
        "peak_scale": 1.25,
        "font_key": "bubble_large",
        "shake": False,
    },
    "miss": {       # 抓空
        "texts": ["Oopz!!", "MISS!", "whoops—"],
        "color": "miss_gray",
        "glow_color": None,
        "lifetime": 0.75,
        "float_speed": 30,
        "start_scale": 0.5,
        "peak_scale": 1.05,
        "font_key": "bubble_medium",
        "shake": False,
    },
    "airborne": {   # 进入空中飞行
        "texts": ["Wheee—", "FLYING!", "air time~"],
        "color": "soft_purple",
        "glow_color": "soft_purple",
        "lifetime": 1.1,
        "float_speed": 50,
        "start_scale": 0.5,
        "peak_scale": 1.15,
        "font_key": "bubble_medium",
        "shake": False,
    },
    "goal": {       # 到达终点
        "texts": ["CLEAR!!", "GOAL!!", "ARRIVED!"],
        "color": "goal_gold",
        "glow_color": "goal_gold",
        "lifetime": 1.8,
        "float_speed": 100,
        "start_scale": 0.0,
        "peak_scale": 1.6,
        "font_key": "bubble_xl",
        "shake": True,
    },
    "fragile": {    # 抓住易碎墙壁
        "texts": ["CRACK!", "fragile..."],
        "color": "lava_orange",
        "glow_color": "lava_orange",
        "lifetime": 0.8,
        "float_speed": 60,
        "start_scale": 0.4,
        "peak_scale": 1.2,
        "font_key": "bubble_medium",
        "shake": True,
    },
    "hazard": {     # 碰到危险物
        "texts": ["BREAK!!", "OUCH!"],
        "color": "danger_red",
        "glow_color": "danger_red",
        "lifetime": 0.9,
        "float_speed": 80,
        "start_scale": 0.3,
        "peak_scale": 1.35,
        "font_key": "bubble_large",
        "shake": True,
    },
    "length_up": {  # 长度增加
        "texts": ["Longer!", "STRETCH!"],
        "color": "longer_green",
        "glow_color": "longer_green",
        "lifetime": 0.85,
        "float_speed": 70,
        "start_scale": 0.4,
        "peak_scale": 1.2,
        "font_key": "bubble_medium",
        "shake": False,
    },
    "length_down": {  # 长度缩短
        "texts": ["Shorter!", "COMPACT!"],
        "color": "shorter_red",
        "glow_color": "shorter_red",
        "lifetime": 0.85,
        "float_speed": 70,
        "start_scale": 0.4,
        "peak_scale": 1.2,
        "font_key": "bubble_medium",
        "shake": False,
    },
    "speed_up": {   # 转速增加
        "texts": ["Faster!!", "SPEED UP!", "ZIP!"],
        "color": "speed_blue",
        "glow_color": "neon_cyan",
        "lifetime": 0.85,
        "float_speed": 75,
        "start_scale": 0.3,
        "peak_scale": 1.25,
        "font_key": "bubble_large",
        "shake": False,
    },
    "speed_down": {  # 转速降低
        "texts": ["Slower...", "chill~"],
        "color": "slow_purple",
        "glow_color": "soft_purple",
        "lifetime": 0.85,
        "float_speed": 55,
        "start_scale": 0.4,
        "peak_scale": 1.1,
        "font_key": "bubble_medium",
        "shake": False,
    },
    "lava_warning": {  # 岩浆接近
        "texts": ["WAVE!!"],
        "color": (80, 180, 255),
        "color": "danger_red",
        "glow_color": "lava_orange",
        "lifetime": 0.6,
        "float_speed": 40,
        "start_scale": 0.6,
        "peak_scale": 1.2,
        "font_key": "bubble_large",
        "shake": True,
    },
}


# ============================================================
# 字体管理器
# ============================================================

class FontManager:
    """加载并缓存所有 UI 字体"""

    def __init__(self):
        self.fonts = {}
        self._default = None  # 安全回退字体

    def _safe_font(self, path, size):
        """安全创建字体 — 优先用指定路径，回退到系统字体"""
        if path and os.path.exists(path):
            try:
                return pygame.font.Font(path, size)
            except Exception:
                pass
        # 回退：用系统字体名
        name = self._default if self._default else "consolas"
        try:
            return pygame.font.SysFont(name, size)
        except Exception:
            return pygame.font.Font(None, size)

    def _ensure_default(self):
        """确保至少有一个可用系统字体作为兜底"""
        if self._default is not None:
            return
        for candidate in ["consolas", "bahnschrift", "segoeui", "arial"]:
            try:
                test = pygame.font.SysFont(candidate, 24)
                test.render("TEST", True, (255, 255, 255))
                self._default = candidate
                return
            except Exception:
                continue
        self._default = None

    def load(self):
        """加载所有字体"""
        self._ensure_default()

        sizes = {
            "title_xl": ("title", 100),
            "title_large": ("title", 80),
            "title_medium": ("title", 56),
            "title_small": ("title", 40),
            "ui_large": ("ui", 42),
            "ui_medium": ("ui", 30),
            "ui_small": ("ui", 22),
            "ui_tiny": ("ui", 16),
            "cn_large": ("cn", 36),
            "cn_medium": ("cn", 28),
            "cn_small": ("cn", 22),
            "cn_tiny": ("cn", 16),
            "elegant": ("elegant", 34),
            "elegant_small": ("elegant", 24),
            "bubble_xl": ("title", 52),
            "bubble_large": ("title", 42),
            "bubble_medium": ("title", 32),
            "bubble_small": ("title", 24),
        }

        for name, (font_key, size) in sizes.items():
            path = _resolve_font_path(font_key)
            self.fonts[name] = self._safe_font(path, size)

    def get(self, name):
        """获取字体，不存在则返回安全回退字体"""
        if name in self.fonts:
            return self.fonts[name]
        return self._safe_font(None, 24)


# ============================================================
# 颜色快捷函数
# ============================================================

def c(name):
    """快捷取色"""
    return COLORS.get(name, (255, 255, 255))


# ============================================================
# 气泡弹字系统 (Bubble Text)
# ============================================================

class BubbleText:
    """单个气泡弹字 — 从屏幕位置浮起、缩放、淡出"""

    __slots__ = (
        'text', 'x', 'y', 'color', 'glow_color', 'lifetime',
        'age', 'float_speed', 'start_scale', 'peak_scale',
        'font_key', 'shake', '_dead', '_shakes'
    )

    def __init__(self, text, x, y, bubble_type="snap"):
        cfg = BUBBLE_CONFIG.get(bubble_type, BUBBLE_CONFIG["snap"])
        self.text = text
        self.x = float(x)
        self.y = float(y)
        self.color = cfg["color"]
        self.glow_color = cfg["glow_color"]
        self.lifetime = cfg["lifetime"]
        self.age = 0.0
        self.float_speed = cfg["float_speed"]
        self.start_scale = cfg["start_scale"]
        self.peak_scale = cfg["peak_scale"]
        self.font_key = cfg["font_key"]
        self.shake = cfg["shake"]
        self._dead = False
        self._shakes = [(0, 0)]

    @property
    def dead(self):
        return self._dead

    def update(self, dt):
        self.age += dt
        if self.age >= self.lifetime:
            self._dead = True
            return
        # 上浮
        self.y -= self.float_speed * dt
        # 抖动
        if self.shake and self.age < 0.25:
            self._shakes = [
                (random.uniform(-4, 4), random.uniform(-3, 3))
                for _ in range(3)
            ]
        else:
            self._shakes = [(0, 0)]

    def progress(self):
        """返回 0~1 的动画进度"""
        return min(1.0, self.age / self.lifetime)

    def current_scale(self):
        """根据进度计算当前缩放"""
        p = self.progress()
        # 前 20% 时间：从 start_scale 弹到 peak_scale
        if p < 0.2:
            t = p / 0.2
            # ease-out bounce
            bounce = 1.0 - (1.0 - t) ** 3
            return self.start_scale + (self.peak_scale - self.start_scale) * bounce
        else:
            # 剩余时间：保持在 peak 附近，慢慢缩小淡出
            decay = (p - 0.2) / 0.8
            return self.peak_scale * (1.0 - decay * 0.3)

    def current_alpha(self):
        """根据进度计算透明度"""
        p = self.progress()
        if p < 0.1:
            return int(255 * (p / 0.1))
        elif p > 0.7:
            return int(255 * (1.0 - (p - 0.7) / 0.3))
        else:
            return 255

    def draw(self, screen, font_manager):
        """绘制气泡"""
        font = font_manager.get(self.font_key)
        alpha = self.current_alpha()
        if alpha <= 5:
            return

        scale = self.current_scale()
        sx, sy = self._shakes[-1]

        color_rgb = c(self.color)
        text_surf = font.render(self.text, True, color_rgb)

        w = int(text_surf.get_width() * scale)
        h = int(text_surf.get_height() * scale)
        if w <= 0 or h <= 0:
            return

        scaled = pygame.transform.smoothscale(text_surf, (w, h))
        scaled.set_alpha(alpha)

        # 发光层
        if self.glow_color:
            glow_rgb = c(self.glow_color)
            glow_surf = font.render(self.text, True, glow_rgb)
            gw = int(glow_surf.get_width() * scale * 1.3)
            gh = int(glow_surf.get_height() * scale * 1.3)
            if gw > 0 and gh > 0:
                glow_scaled = pygame.transform.smoothscale(glow_surf, (gw, gh))
                glow_scaled.set_alpha(alpha // 3)
                gr = glow_scaled.get_rect(center=(int(self.x + sx), int(self.y + sy)))
                screen.blit(glow_scaled, gr)

        rect = scaled.get_rect(center=(int(self.x + sx), int(self.y + sy)))
        screen.blit(scaled, rect)


class BubbleManager:
    """管理所有气泡弹字"""

    def __init__(self):
        self.bubbles = []

    def spawn(self, bubble_type, x=None, y=None, screen_width=800, screen_height=600):
        """生成一个气泡"""
        cfg = BUBBLE_CONFIG.get(bubble_type)
        if cfg is None:
            return

        text = random.choice(cfg["texts"])
        if x is None:
            x = screen_width // 2
        if y is None:
            y = screen_height // 2 - 40

        bubble = BubbleText(text, x, y, bubble_type)
        self.bubbles.append(bubble)
        return bubble

    def update(self, dt):
        for b in self.bubbles:
            b.update(dt)
        self.bubbles = [b for b in self.bubbles if not b.dead]

    def draw(self, screen, font_manager):
        for b in self.bubbles:
            b.draw(screen, font_manager)

    def clear(self):
        self.bubbles.clear()


# ============================================================
# 基础绘制工具
# ============================================================

def _blit_center(screen, surface, center_pos):
    """居中 blit"""
    rect = surface.get_rect(center=center_pos)
    screen.blit(surface, rect)
    return rect


# ============================================================
# 普通文字
# ============================================================

def draw_text(screen, text, font, pos, text_color="pure_white", center=False, alpha=255):
    """绘制普通单色文字"""
    surface = font.render(text, True, c(text_color))
    surface.set_alpha(alpha)
    if center:
        return _blit_center(screen, surface, pos)
    else:
        screen.blit(surface, pos)
        return surface.get_rect(topleft=pos)


# ============================================================
# 霓虹脉冲文字 (NeonPulse)
# ============================================================

def draw_neon_text(screen, text, font, center_pos, time_seconds,
                   text_color="pure_white", soft=False):
    """霓虹脉冲发光标题"""
    cfg = EFFECT_CONFIG["neon_pulse"]

    pulse = (math.sin(time_seconds * cfg["pulse_speed"]) + 1.0) / 2.0
    glow_alpha = cfg["base_alpha"] + int(pulse * cfg["pulse_strength"])

    if soft:
        glow_alpha = glow_alpha // 2

    if random.random() < cfg["flicker_chance"]:
        glow_alpha = int(glow_alpha * cfg["flicker_strength"])

    primary = c(cfg["primary_glow"])
    secondary = c(cfg["secondary_glow"])

    # 二级紫色大光晕
    for offset in cfg["glow_offsets"]:
        glow = font.render(text, True, secondary)
        glow.set_alpha(max(8, glow_alpha // (offset + 1)))
        for dx, dy in [
            (-offset, 0), (offset, 0), (0, -offset), (0, offset),
            (-offset, -offset), (offset, -offset), (-offset, offset), (offset, offset)
        ]:
            rect = glow.get_rect(center=(center_pos[0] + dx, center_pos[1] + dy))
            screen.blit(glow, rect)

    # 青蓝主光晕
    for offset in cfg["glow_offsets"][1:]:
        glow = font.render(text, True, primary)
        glow.set_alpha(max(15, glow_alpha // max(1, offset // 2)))
        for dx, dy in [(-offset, 0), (offset, 0), (0, -offset), (0, offset)]:
            rect = glow.get_rect(center=(center_pos[0] + dx, center_pos[1] + dy))
            screen.blit(glow, rect)

    # 主文字
    main_surf = font.render(text, True, c(text_color))
    rect = main_surf.get_rect(center=center_pos)
    screen.blit(main_surf, rect)

    return rect


# ============================================================
# 柔和闪烁文字 (SoftBlink)
# ============================================================

def draw_soft_blink_text(screen, text, font, center_pos, time_seconds,
                         text_color="pure_white"):
    """呼吸灯式柔和闪烁"""
    cfg = EFFECT_CONFIG["soft_blink"]
    t = (math.sin(time_seconds * cfg["blink_speed"]) + 1.0) / 2.0
    alpha = int(cfg["min_alpha"] + t * (cfg["max_alpha"] - cfg["min_alpha"]))

    surface = font.render(text, True, c(text_color))
    surface.set_alpha(alpha)

    rect = surface.get_rect(center=center_pos)
    screen.blit(surface, rect)
    return rect


# ============================================================
# 节奏闪光文字 (RhythmFlash)
# ============================================================

def draw_rhythm_flash_text(screen, text, font, center_pos, elapsed_time,
                           text_color="pure_white"):
    """短暂爆发闪光文字"""
    cfg = EFFECT_CONFIG["rhythm_flash"]
    if elapsed_time > cfg["duration"]:
        return None

    progress = elapsed_time / cfg["duration"]
    alpha = int(255 * (1.0 - progress))
    scale = 1.0 + (cfg["max_scale"] - 1.0) * (1.0 - progress)

    base = font.render(text, True, c(text_color))
    glow = font.render(text, True, c(cfg["flash_color"]))

    width = int(base.get_width() * scale)
    height = int(base.get_height() * scale)
    if width <= 0 or height <= 0:
        return None

    base = pygame.transform.smoothscale(base, (width, height))
    gw = int(width + 16)
    gh = int(height + 16)
    glow = pygame.transform.smoothscale(glow, (gw, gh))

    glow.set_alpha(alpha // 2)
    base.set_alpha(alpha)

    glow_rect = glow.get_rect(center=center_pos)
    base_rect = base.get_rect(center=center_pos)
    screen.blit(glow, glow_rect)
    screen.blit(base, base_rect)

    return base_rect


# ============================================================
# 钢琴高光文字 (PianoShine)
# ============================================================

def draw_piano_shine_text(screen, text, font, center_pos, time_seconds):
    """优雅钢琴高光扫过"""
    cfg = EFFECT_CONFIG["piano_shine"]

    # 阴影
    shadow = font.render(text, True, (20, 20, 24))
    shadow_rect = shadow.get_rect(center=(center_pos[0] + 2, center_pos[1] + 2))
    screen.blit(shadow, shadow_rect)

    # 主文字
    base = font.render(text, True, c(cfg["base_color"]))
    rect = base.get_rect(center=center_pos)
    screen.blit(base, rect)

    # 下方细线
    line_y = rect.bottom + 8
    pygame.draw.line(
        screen, c(cfg["line_color"]),
        (rect.left, line_y), (rect.right, line_y), 1
    )

    # 高光扫线
    shine_x = (rect.left
               + int((time_seconds * cfg["shine_speed"]) % (rect.width + cfg["shine_width"]))
               - cfg["shine_width"])

    shine_surface = pygame.Surface((cfg["shine_width"], rect.height), pygame.SRCALPHA)
    pygame.draw.polygon(
        shine_surface,
        (255, 255, 255, cfg["shine_alpha"]),
        [
            (cfg["shine_width"] // 2, 0),
            (cfg["shine_width"], 0),
            (cfg["shine_width"] // 2, rect.height),
            (0, rect.height),
        ]
    )

    clipped = screen.get_clip()
    screen.set_clip(rect)
    screen.blit(shine_surface, (shine_x, rect.top))
    screen.set_clip(clipped)

    return rect


# ============================================================
# 危险闪烁文字 (DangerFlicker)
# ============================================================

def draw_danger_text(screen, text, font, center_pos, time_seconds):
    """红橙危险闪烁 + 抖动"""
    cfg = EFFECT_CONFIG["danger_flicker"]

    flicker = abs(math.sin(time_seconds * cfg["flicker_speed"]))
    alpha = int(120 + flicker * 135)

    jitter = cfg["jitter_amount"]
    ox = random.randint(-jitter, jitter)
    oy = random.randint(-jitter, jitter)

    glow = font.render(text, True, c(cfg["glow_color"]))
    glow.set_alpha(alpha // 2)

    main_surf = font.render(text, True, c(cfg["warning_color"]))
    main_surf.set_alpha(alpha)

    for dx, dy in [(-4, 0), (4, 0), (0, -4), (0, 4)]:
        gr = glow.get_rect(center=(center_pos[0] + dx + ox, center_pos[1] + dy + oy))
        screen.blit(glow, gr)

    rect = main_surf.get_rect(center=(center_pos[0] + ox, center_pos[1] + oy))
    screen.blit(main_surf, rect)

    return rect


# ============================================================
# UI 页面绘制函数
# ============================================================

def draw_main_menu_ui(screen, fonts, time_seconds, screen_w, screen_h):
    """绘制主菜单 UI"""
    # 背景
    screen.fill(c("deep_navy"))

    # 标题 — 霓虹脉冲，微微浮动
    float_y = int(math.sin(time_seconds * 1.5) * 8)
    draw_neon_text(
        screen,
        "O---O",
        fonts.get("title_xl"),
        (screen_w // 2, screen_h // 2 - 100 + float_y),
        time_seconds,
        text_color="pure_white"
    )

    # 副标题 + 操作提示
    draw_text(
        screen,
        "ANCHOR CLIMBER",
        fonts.get("ui_small"),
        (screen_w // 2, screen_h // 2 - 50),
        text_color="ice_cyan",
        center=True
    )
    draw_text(
        screen,
        "SWITCH ANCHOR TO CLIMB",
        fonts.get("ui_tiny"),
        (screen_w // 2, screen_h // 2 - 20),
        text_color="miss_gray",
        center=True
    )

    # 装饰线
    line_y = screen_h // 2 - 10
    line_w = 120
    cx = screen_w // 2
    alpha = int(100 + 40 * math.sin(time_seconds * 2.0))
    line_surf = pygame.Surface((line_w, 1), pygame.SRCALPHA)
    line_surf.fill((*c("ice_cyan"), alpha))
    screen.blit(line_surf, (cx - line_w // 2, line_y))

    # 操作提示 — 浮动动画
    float_offset = int(math.sin(time_seconds * 2.5) * 6)
    base_y = screen_h - 120

    # SPACE — START / ANCHOR（霓虹脉冲）
    draw_neon_text(
        screen,
        "SPACE  -  START",
        fonts.get("title_medium"),
        (screen_w // 2, base_y + float_offset),
        time_seconds,
        text_color="ice_cyan",
        soft=True
    )

    # R — RETRY（柔和闪烁）
    draw_soft_blink_text(
        screen,
        "R  -  RETRY",
        fonts.get("ui_medium"),
        (screen_w // 2, base_y + 40 + float_offset),
        time_seconds,
        text_color="pure_white"
    )

    # 版本信息
    draw_text(
        screen,
        "v0.2",
        fonts.get("ui_tiny"),
        (screen_w - 50, screen_h - 22),
        text_color="miss_gray"
    )


def draw_game_ui(screen, fonts, stick, level, camera_y, time_seconds,
                 screen_w, screen_h, bubble_mgr):
    """绘制游戏内 HUD （极简）"""
    # 右上角：关卡编号
    draw_text(
        screen,
        "STAGE 01",
        fonts.get("ui_small"),
        (screen_w - 24, 20),
        text_color="pure_white",
        center=False,
        alpha=180
    )

    # 左上角：攀登高度
    height_m = max(0, int((level.height - stick.center_y) / 10))
    draw_text(
        screen,
        f"HEIGHT {height_m}M",
        fonts.get("ui_small"),
        (24, 20),
        text_color="pure_white",
        center=False,
        alpha=180
    )

    # 岩浆接近警告 — 蓝色 "WAVE!!" 气泡
    stick_top = stick.get_highest_y()
    lava_dist = stick_top - level.lava_y
    if 0 < lava_dist < 250:
        intensity = max(0, (250 - lava_dist) / 250)
        if intensity > 0.6 and random.random() < 0.02:
            bubble_mgr.spawn(
                "lava_warning",
                x=screen_w // 2 + random.uniform(-60, 60),
                y=screen_h - 50 + random.uniform(-30, 10),
                screen_width=screen_w,
                screen_height=screen_h
            )

    # 绘制所有气泡弹字
    bubble_mgr.draw(screen, fonts)


def draw_win_overlay(screen, fonts, time_seconds, screen_w, screen_h):
    """胜利结算界面"""
    # 暗色覆盖
    overlay = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
    overlay.fill((*c("overlay_dark"), 170))
    screen.blit(overlay, (0, 0))

    # 主标题 — 金色霓虹
    draw_neon_text(
        screen,
        "STAGE CLEAR",
        fonts.get("title_large"),
        (screen_w // 2, screen_h // 2 - 70),
        time_seconds,
        text_color="goal_gold",
        soft=True
    )

    # 优雅副标题
    draw_piano_shine_text(
        screen,
        "Anchor Secured",
        fonts.get("elegant"),
        (screen_w // 2, screen_h // 2 + 10),
        time_seconds
    )

    # 操作提示
    draw_soft_blink_text(
        screen,
        "SPACE  -  NEXT LEVEL",
        fonts.get("ui_medium"),
        (screen_w // 2, screen_h // 2 + 80),
        time_seconds
    )
    draw_text(
        screen,
        "R  -  RETRY",
        fonts.get("ui_small"),
        (screen_w // 2, screen_h // 2 + 130),
        text_color="pure_white",
        center=True,
        alpha=180
    )


def draw_dead_overlay(screen, fonts, time_seconds, screen_w, screen_h):
    """死亡结算界面"""
    # 暗红覆盖
    overlay = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
    overlay.fill((*c("overlay_dead"), 180))
    screen.blit(overlay, (0, 0))

    # 标题
    draw_danger_text(
        screen,
        "SINK",
        fonts.get("title_large"),
        (screen_w // 2, screen_h // 2 - 50),
        time_seconds
    )

    # PRESS R
    draw_soft_blink_text(
        screen,
        "PRESS  R  TO RETRY",
        fonts.get("ui_medium"),
        (screen_w // 2, screen_h // 2 + 60),
        time_seconds,
        text_color="miss_gray"
    )


def draw_debug_overlay(screen, fonts, game, screen_w):
    """绘制调试信息 (F3)"""
    lines = [
        f"FPS: {int(game.clock.get_fps())}",
        f"State: {game.stick.state}",
        f"Anchor side: {game.stick.anchor_side}",
        f"Angle: {math.degrees(game.stick.angle):.0f}",
        f"Center: ({game.stick.center_x:.0f}, {game.stick.center_y:.0f})",
        f"Velocity: ({game.stick.velocity_x:.0f}, {game.stick.velocity_y:.0f})",
        f"Lava Y: {game.level.lava_y:.0f}",
        f"Camera Y: {game.camera.y:.0f}",
        f"Particles: {len(game.particles.particles)}",
        f"Bubbles: {len(game.bubbles.bubbles)}",
    ]
    for i, line in enumerate(lines):
        text = fonts.get("ui_tiny").render(line, True, (200, 200, 100))
        screen.blit(text, (screen_w - 280, 10 + i * 18))


# ============================================================
# 菜单棍子动画
# ============================================================

def draw_menu_stick_animation(screen, angle, time_seconds, screen_w):
    """绘制菜单页的旋转棍子动画"""
    cx, cy = screen_w // 2, 340
    length = 100
    dx = math.cos(angle) * length / 2
    dy = math.sin(angle) * length / 2
    e0 = (int(cx + dx), int(cy + dy))
    e1 = (int(cx - dx), int(cy - dy))

    stick_body = (200, 200, 220)
    stick_outline = (120, 120, 150)
    stick_endpoint = (230, 230, 250)

    # 棍体
    pygame.draw.line(screen, stick_outline, e0, e1, 9)
    pygame.draw.line(screen, stick_body, e0, e1, 7)
    # 端点
    for ex, ey in [e0, e1]:
        pygame.draw.circle(screen, stick_outline, (ex, ey), 14)
        pygame.draw.circle(screen, stick_endpoint, (ex, ey), 11)
        pygame.draw.circle(screen, (255, 255, 255, 80), (ex - 3, ey - 3), 4)

    # 锚点端高亮
    anchor = e0 if math.sin(time_seconds * 3) > 0 else e1
    glow_r = 20 + int(abs(math.sin(time_seconds * 3)) * 8)
    glow_surf = pygame.Surface((glow_r * 4, glow_r * 4), pygame.SRCALPHA)
    pygame.draw.circle(glow_surf, (100, 200, 255, 60),
                       (glow_r * 2, glow_r * 2), glow_r)
    screen.blit(glow_surf, (anchor[0] - glow_r * 2, anchor[1] - glow_r * 2))
