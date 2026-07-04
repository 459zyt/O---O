"""
level/level.py
关卡类 — 管理墙壁、道具、危险物、岩浆
使用 entities/wall.py 中的 Wall 对象
"""

import math
import pygame
from data_config import (
    TILE_SIZE, MAP_COLS, SCREEN_WIDTH, SCREEN_HEIGHT,
    LAVA_CONFIG, ITEM_CONFIG
)
from physics.geometry import line_intersect
from entities.wall import Wall

# 颜色常量
C_GREEN = (60, 220, 80)
C_RED = (255, 60, 40)
C_WHITE = (255, 255, 255)


class Level:
    """关卡：管理墙壁、道具、危险物、岩浆"""

    def __init__(self, layout, player_start, tile_size=TILE_SIZE):
        self.tile_size = tile_size
        self.cols = len(layout[0]) if layout else MAP_COLS
        self.rows = len(layout)
        self.width = self.cols * tile_size
        self.height = self.rows * tile_size
        self.player_start = player_start

        # 实体列表
        self.walls = []      # [Wall, ...]
        self.items = []      # [(rect, effect_type, value), ...]
        self.hazards = []    # [pygame.Rect, ...]

        # 岩浆
        self.lava_y = player_start[1] + LAVA_CONFIG["start_y_below_player"]
        self.lava_rise_speed = LAVA_CONFIG["rise_speed"]
        self.lava_timer = 0.0

        # 已消耗道具
        self.consumed_items = set()

        # 存档管理器
        from systems.checkpoint_manager import CheckpointManager
        self.checkpoint_manager = CheckpointManager()

        # 解析地图
        self._parse_layout(layout)

    def _parse_layout(self, layout):
        """解析符号地图 → Wall / Item / Hazard 对象"""
        for row_idx, row_str in enumerate(layout):
            for col_idx, char in enumerate(row_str):
                if char == '.':
                    continue

                x = col_idx * self.tile_size
                y = row_idx * self.tile_size

                if char == '#':
                    self.walls.append(Wall(x, y, self.tile_size, self.tile_size, "normal", isSolid=True))
                elif char == 'F':
                    self.walls.append(Wall(x, y, self.tile_size, self.tile_size, "fragile", isSolid=True))
                elif char == 'G':
                    self.walls.append(Wall(x, y, self.tile_size, self.tile_size, "goal", isSolid=True))
                elif char == 'H':
                    self.hazards.append(pygame.Rect(x, y, self.tile_size, self.tile_size))
                elif char == '+':
                    self.items.append((pygame.Rect(x, y, self.tile_size, self.tile_size),
                                       "LengthUp", ITEM_CONFIG["length_up"]["value"], None))
                elif char == '-':
                    self.items.append((pygame.Rect(x, y, self.tile_size, self.tile_size),
                                       "LengthDown", ITEM_CONFIG["length_down"]["value"], None))
                elif char == '>':
                    self.items.append((pygame.Rect(x, y, self.tile_size, self.tile_size),
                                       "SpeedUp", ITEM_CONFIG["speed_up"]["value"], None))
                elif char == '<':
                    self.items.append((pygame.Rect(x, y, self.tile_size, self.tile_size),
                                       "SpeedDown", ITEM_CONFIG["speed_down"]["value"], None))

    # ---- 查询 ----
    def get_wall_at_point(self, x, y, radius=0):
        """
        检查点是否在某个墙壁内。
        返回 (Wall对象, anchor_x, anchor_y) 或 None
        """
        for wall in self.walls:
            if not wall.active:
                continue
            if wall.contains_point(x, y, radius):
                ax, ay = wall.clamp_point(x, y)
                return (wall, ax, ay)
        return None

    def get_item_at_point(self, x, y, radius=0):
        """
        返回 (result_str, item_obj_or_None) 或 None。
        result_str: "item_LengthUp" | "item_KeyPair" 等
        item_obj: Item 对象（JSON 加载时）或 None（text-map 时）
        """
        for entry in self.items:
            rect = entry[0]
            etype = entry[1]
            item_obj = entry[3] if len(entry) >= 4 else None

            item_key = (rect.x, rect.y, etype)
            if item_key in self.consumed_items:
                continue
            # 精确碰撞：道具范围由地图设计师在 Tiled 中手动拖拽决定
            if rect.collidepoint(x, y):
                # 存档点和钥匙不加入 consumed_items——它们通过 item.active 控制可见性
                if etype not in ("Checkpoint", "KeyPair"):
                    self.consumed_items.add(item_key)
                return (f"item_{etype}", item_obj)
        return None

    def trigger_key_pair(self, key_pair_id):
        """
        触发某个 key_pair_id 对应的所有墙壁。

        遍历关卡中所有墙壁，找到 KeyPairSolidComponent 且 key_pair_id 匹配的墙，
        调用 component.on_key_collected() 永久切换虚实状态。
        """
        for wall in self.walls:
            comp = wall.get_component("key_pair_solid")
            if comp is None:
                continue
            if comp.key_pair_id == key_pair_id:
                comp.on_key_collected()

    def get_wall_by_id(self, wall_id):
        """根据 ID 查找墙壁对象"""
        for wall in self.walls:
            if wall.id == wall_id:
                return wall
        return None

    def apply_item_to_stick(self, stick, item):
        """
        处理道具触发。

        普通道具:  LengthUp / LengthDown / SpeedUp / SpeedDown → stick.apply_item()
        存档点:   Checkpoint → checkpoint_manager.activate_checkpoint()
        钥匙:    KeyPair → trigger_key_pair()
        """
        if item.effect == "Checkpoint":
            # 只有锚定在墙上时才能存档，空中碰到不记录
            if stick.state == "anchored":
                self.checkpoint_manager.activate_checkpoint(self, stick, item)
            return

        if item.effect == "KeyPair":
            if item.key_pair_id:
                self.trigger_key_pair(item.key_pair_id)
            if item.consume_on_trigger:
                item.active = False
            return

        stick.apply_item(item.effect, item.value)
        if item.consume_on_trigger:
            item.active = False

    def update_item_touch_triggers(self, stick):
        """
        每帧检测 OnTouch 类型道具（如存档点）。

        棍子任意部分碰到道具矩形即触发。
        """
        for entry in self.items:
            rect = entry[0]
            etype = entry[1]
            item_obj = entry[3] if len(entry) >= 4 else None

            if item_obj is None:
                continue
            if item_obj.effect != "Checkpoint":
                continue
            if item_obj.trigger_condition != "OnTouch":
                continue
            if not item_obj.active:
                continue

            # 只有锚定在墙上时才能存档（空中碰到不记录）
            if stick.state != "anchored":
                continue

            # 检测棍子碰撞
            if self._stick_touches_rect(stick, rect):
                self.apply_item_to_stick(stick, item_obj)

    def _stick_touches_rect(self, stick, rect):
        """检查棍子任意部分是否与矩形重叠"""
        segments = stick.get_all_segments()
        for seg in segments:
            if self._segment_rect_collision(seg, rect):
                return True
        return False

    def find_starting_wall(self):
        """找到离玩家出生点最近的墙壁，返回 (wall, anchor_x, anchor_y)"""
        if not self.walls:
            return None
        best = None
        best_dist = float('inf')
        px, py = self.player_start
        for wall in self.walls:
            if not wall.active:
                continue
            if wall.wall_type == "goal":
                continue
            ax, ay = wall.clamp_point(px, py)
            dist = (px - ax) ** 2 + (py - ay) ** 2
            if dist < best_dist:
                best_dist = dist
                best = (wall, ax, ay)
        return best

    def check_hazard_collision(self, stick):
        """检查棍子是否碰到任何危险物"""
        segments = stick.get_all_segments()
        for h_rect in self.hazards:
            for seg in segments:
                if self._segment_rect_collision(seg, h_rect):
                    return True
        return False

    def _segment_rect_collision(self, seg, rect):
        stype = seg[0]
        if stype == "circle":
            _, cx, cy, r = seg
            closest_x = max(rect.left, min(cx, rect.right))
            closest_y = max(rect.top, min(cy, rect.bottom))
            return math.sqrt((cx - closest_x) ** 2 + (cy - closest_y) ** 2) < r
        elif stype == "line":
            _, x0, y0, x1, y1, r = seg
            inflated = rect.inflate(r * 2, r * 2)
            if inflated.collidepoint(x0, y0) or inflated.collidepoint(x1, y1):
                return True
            lines = [
                (inflated.left, inflated.top, inflated.right, inflated.top),
                (inflated.right, inflated.top, inflated.right, inflated.bottom),
                (inflated.right, inflated.bottom, inflated.left, inflated.bottom),
                (inflated.left, inflated.bottom, inflated.left, inflated.top),
            ]
            for lx0, ly0, lx1, ly1 in lines:
                if line_intersect(x0, y0, x1, y1, lx0, ly0, lx1, ly1):
                    return True
        return False

    # ---- 更新 ----
    def update(self, dt, stick=None):
        """每帧更新：墙壁组件 → 岩浆 → 存档点检测 → OnTouch 道具检测"""
        for wall in self.walls:
            wall.update(dt)
        self.update_lava(dt)
        # 岩浆淹没存档点 → 存档失效
        if self.checkpoint_manager.has_checkpoint():
            self.checkpoint_manager.check_lava_submerged(self.lava_y)
        if stick is not None:
            self.update_item_touch_triggers(stick)

    # ---- 岩浆 ----
    def update_lava(self, dt):
        self.lava_y -= self.lava_rise_speed * dt
        self.lava_timer += dt

    def is_in_lava(self, stick):
        return stick.get_lowest_y() >= self.lava_y - LAVA_CONFIG["kill_margin"]

    # ---- 渲染 ----
    def draw(self, screen, camera_y, images):
        """绘制关卡 — 墙壁委托 Wall.draw()"""
        for wall in self.walls:
            wall.draw(screen, camera_y, images, self.tile_size)

        # 道具
        item_images = {
            "LengthUp": images.get("length_up"),
            "LengthDown": images.get("length_down"),
            "SpeedUp": images.get("speed_up"),
            "SpeedDown": images.get("speed_down"),
        }
        for entry in self.items:
            rect = entry[0]
            etype = entry[1]
            item_obj = entry[3] if len(entry) >= 4 else None

            item_key = (rect.x, rect.y, etype)
            if item_key in self.consumed_items:
                continue
            sx, sy = int(rect.x), int(rect.y - camera_y)
            if sy + self.tile_size < 0 or sy > SCREEN_HEIGHT:
                continue

            # KeyPair 钥匙：平铺贴图
            if etype == "KeyPair":
                key_img = images.get("key")
                if key_img:
                    iw, ih = key_img.get_width(), key_img.get_height()
                    for tx in range(sx, sx + rect.width, iw):
                        for ty in range(sy, sy + rect.height, ih):
                            screen.blit(key_img, (tx, ty))
                else:
                    pygame.draw.circle(screen, (255, 220, 60),
                                       (sx + rect.width // 2, sy + rect.height // 2),
                                       min(rect.width, rect.height) // 2 - 2)
                continue

            # Checkpoint 存档点：未激活/已激活两套贴图
            if etype == "Checkpoint":
                is_active = (item_obj and
                    self.checkpoint_manager.active_checkpoint_id == item_obj.checkpoint_id)
                cp_key = "checkpoint_on" if is_active else "checkpoint_off"
                cp_img = images.get(cp_key)
                if cp_img:
                    iw, ih = cp_img.get_width(), cp_img.get_height()
                    for tx in range(sx, sx + rect.width, iw):
                        for ty in range(sy, sy + rect.height, ih):
                            screen.blit(cp_img, (tx, ty))
                else:
                    color = (100, 255, 100) if is_active else (100, 200, 255)
                    pygame.draw.rect(screen, color, (sx, sy, rect.width, rect.height), border_radius=4)
                continue

            img = item_images.get(etype)
            if img:
                # 平铺贴图覆盖整个道具区域（设计师可拖拽任意尺寸）
                iw, ih = img.get_width(), img.get_height()
                for tx in range(sx, sx + rect.width, iw):
                    for ty in range(sy, sy + rect.height, ih):
                        screen.blit(img, (tx, ty))
            else:
                color_map = {"LengthUp": C_GREEN, "LengthDown": C_RED,
                             "SpeedUp": (60, 140, 255), "SpeedDown": (180, 100, 255)}
                pygame.draw.rect(screen, color_map.get(etype, C_WHITE),
                                 (sx + 4, sy + 4, rect.width - 8, rect.height - 8),
                                 border_radius=4)

        # 危险物
        hazard_img = images.get("hazard")
        for rect in self.hazards:
            sx, sy = int(rect.x), int(rect.y - camera_y)
            if sy + rect.height < 0 or sy > SCREEN_HEIGHT:
                continue
            if hazard_img:
                # 平铺贴图覆盖整个障碍物区域
                iw, ih = hazard_img.get_width(), hazard_img.get_height()
                for tx in range(sx, sx + rect.width, iw):
                    for ty in range(sy, sy + rect.height, ih):
                        screen.blit(hazard_img, (tx, ty))
            else:
                pygame.draw.circle(screen, C_RED,
                                   (sx + rect.width // 2, sy + rect.height // 2),
                                   min(rect.width, rect.height) // 2 - 2)

        # 岩浆
        self._draw_lava(screen, camera_y, images)

    def _draw_lava(self, screen, camera_y, images):
        lava_y_screen = int(self.lava_y - camera_y)
        if lava_y_screen > SCREEN_HEIGHT + 50:
            return
        lava_top = max(0, lava_y_screen)
        lava_height = SCREEN_HEIGHT - lava_top
        if lava_height <= 0:
            return

        lava_img = images.get("lava")
        if lava_img:
            lw, lh = lava_img.get_width(), lava_img.get_height()
            for y in range(lava_top, SCREEN_HEIGHT, lh):
                for x in range(0, SCREEN_WIDTH, lw):
                    screen.blit(lava_img, (x, y))
        else:
            for y in range(lava_top, SCREEN_HEIGHT):
                t = (y - lava_top) / max(1, lava_height)
                r, g, b = int(180 + 75 * t), int(30 + 100 * t), int(5 + 30 * t)
                pygame.draw.line(screen, (min(255, r), min(255, g), min(255, b)),
                                 (0, y), (SCREEN_WIDTH, y))

        if 0 < lava_top < SCREEN_HEIGHT:
            for i in range(15):
                alpha = 150 - i * 10
                if alpha <= 0:
                    break
                edge_y = lava_top - i
                if 0 <= edge_y < SCREEN_HEIGHT:
                    glow_surf = pygame.Surface((SCREEN_WIDTH, 1), pygame.SRCALPHA)
                    glow_surf.fill((255, 120, 30, alpha))
                    screen.blit(glow_surf, (0, edge_y))

        if lava_y_screen > SCREEN_HEIGHT - 100:
            intensity = (SCREEN_HEIGHT - lava_y_screen) / 100
            if intensity > 0:
                alpha = int(40 * intensity)
                vignette = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                for y in range(SCREEN_HEIGHT - 80, SCREEN_HEIGHT):
                    edge_alpha = int(alpha * (y - (SCREEN_HEIGHT - 80)) / 80)
                    pygame.draw.line(vignette, (255, 30, 10, edge_alpha), (0, y), (SCREEN_WIDTH, y))
                screen.blit(vignette, (0, 0))
