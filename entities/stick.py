"""
entities/stick.py
O---O 棍子实体 — 物理、锚点切换、道具效果

重构后:
  - 存储 attached_wall 对象引用（而非字符串类型）
  - 存储 anchor_local_pos（锚点在墙壁上的局部坐标）
  - 支持 force_detach()（危险物 + 墙壁碎裂调用）
  - attached_wall_type 作为派生属性保持向后兼容
"""

import math
import pygame
from data_config import STICK_CONFIG, GRAVITY_CONFIG, SCREEN_WIDTH, SCREEN_HEIGHT

# 颜色常量（棍子渲染用）
C_GREEN = (60, 220, 80)
C_RED = (255, 60, 40)
C_STICK_BODY = (200, 200, 220)
C_STICK_ENDPOINT = (230, 230, 250)
C_STICK_OUTLINE = (120, 120, 150)
C_ANCHOR_GLOW = (100, 200, 255)


class Stick:
    """O---O 棍子实体，处理物理和锚点切换"""

    def __init__(self, x, y, angle, length=None, angular_speed=None):
        if length is None:
            length = STICK_CONFIG["length"]
        if angular_speed is None:
            angular_speed = math.radians(STICK_CONFIG["angular_speed"])

        self.length = length
        self.angular_speed = angular_speed  # 弧度/秒
        self.rotation_direction = 1  # 1=顺时针, -1=逆时针

        self.angle = angle  # 弧度
        self.center_x = x
        self.center_y = y
        self.velocity_x = 0.0
        self.velocity_y = 0.0

        # 锚点状态
        self.state = "airborne"  # "anchored" | "airborne"
        self.anchor_side = 0  # 0 或 1，哪一端是锚点

        # 锚点世界位置（向后兼容，每帧由 _update_anchored 更新）
        self.anchor_x = 0.0
        self.anchor_y = 0.0

        # --- 新：墙壁对象引用 ---
        self.attached_wall = None        # Wall 对象 或 None
        self.anchor_local_pos = None     # Vector2 | None — 锚点在墙壁局部坐标

        # 道具效果追踪
        self.base_angular_speed = self.angular_speed
        self.base_length = self.length

        # 端点半径
        self.endpoint_radius = STICK_CONFIG["left_endpoint_radius"]
        self.rod_radius = STICK_CONFIG["rod_radius"]

        # 闪烁计时器（用于视觉反馈）
        self.flash_timer = 0.0
        self.flash_color = None

    # ================================================================
    #  派生属性
    # ================================================================

    @property
    def attached_wall_type(self):
        """向后兼容：从 attached_wall 派生墙壁类型字符串"""
        if self.attached_wall is not None:
            return self.attached_wall.wall_type
        return None

    @attached_wall_type.setter
    def attached_wall_type(self, value):
        """设置墙壁类型 — 仅用于向后兼容（如 start_game 旧代码）"""
        pass  # no-op，实际类型由 attached_wall 决定

    @property
    def total_mass(self):
        """棍子总质量 — 供 UnstableComponent 计算力矩"""
        return (
            STICK_CONFIG["left_endpoint_mass"]
            + STICK_CONFIG["right_endpoint_mass"]
            + STICK_CONFIG["rod_mass"]
        )

    # ---- 端点计算 ----
    def _direction(self):
        """返回 direction 向量 (cos, sin)"""
        return (math.cos(self.angle), math.sin(self.angle))

    def get_endpoints(self):
        """返回 (end_0, end_1) 坐标，end_0 是 anchor_side=0 的端点"""
        dx, dy = self._direction()
        hl = self.length / 2
        if self.state == "anchored":
            if self.anchor_side == 0:
                e0 = (self.anchor_x, self.anchor_y)
                e1 = (self.anchor_x + self.length * dx,
                      self.anchor_y + self.length * dy)
            else:
                e1 = (self.anchor_x, self.anchor_y)
                e0 = (self.anchor_x - self.length * dx,
                      self.anchor_y - self.length * dy)
        else:
            e0 = (self.center_x + hl * dx, self.center_y + hl * dy)
            e1 = (self.center_x - hl * dx, self.center_y - hl * dy)
        return (e0, e1)

    def get_anchor_endpoint(self):
        """返回当前锚点端坐标"""
        e0, e1 = self.get_endpoints()
        return e0 if self.anchor_side == 0 else e1

    def get_free_endpoint(self):
        """返回当前自由端坐标"""
        e0, e1 = self.get_endpoints()
        return e1 if self.anchor_side == 0 else e0

    # ================================================================
    #  切换锚点（核心玩法逻辑）
    # ================================================================

    def switch_anchor(self, level):
        """
        按下空格时调用。切换锚点端，检测墙壁碰撞和道具。
        返回 (anchor_result, item_result_or_None) 元组。

        新版本逻辑:
          1. 旧墙壁 → on_anchor_detached()
          2. 检测新锚点是否命中墙壁
          3. 命中 → on_anchor_attached() → 已锚定
          4. 未命中 → 空中状态
        """
        free_end = self.get_free_endpoint()
        fx, fy = free_end

        new_anchor_side = 1 - self.anchor_side

        # 查询墙壁和道具
        wall_result = level.get_wall_at_point(fx, fy, self.endpoint_radius)
        item_result = level.get_item_at_point(fx, fy, self.endpoint_radius)

        anchor_result = None

        if wall_result is not None:
            wall, wall_x, wall_y = wall_result

            # === 从旧墙壁脱锚 ===
            was_airborne = (self.state == "airborne")
            self._detach_from_current_wall()

            # 脱锚可能触发了旧墙碎裂（脆弱墙）。如果新墙正是同一面墙，
            # 它已经在 _detach_from_current_wall 中被设为 active=False，
            # 此时应视为抓空而非重新抓住已碎的墙。
            if not wall.active:
                self.state = "airborne"
                self.anchor_side = new_anchor_side
                anchor_result = "anchor_miss"
                item_str = item_result[0] if item_result else None
                return (anchor_result, item_str)
            if self.state == "anchored":
                # 这不应该发生（刚 detach 了），但保守处理
                self._compute_airborne_velocity()

            # === 抓住新墙壁 ===
            self.state = "anchored"
            self.anchor_side = new_anchor_side

            if was_airborne:
                # 从空中抓墙：保持中心和角度不变，从中心反算锚点位置
                # 避免旋转轴从质心跳到锚点导致的视觉突变
                dx, dy = self._direction()
                hl = self.length / 2
                if self.anchor_side == 0:
                    self.anchor_x = self.center_x + hl * dx
                    self.anchor_y = self.center_y + hl * dy
                else:
                    self.anchor_x = self.center_x - hl * dx
                    self.anchor_y = self.center_y - hl * dy
                # 夹紧到墙壁内
                self.anchor_x, self.anchor_y = wall.clamp_point(self.anchor_x, self.anchor_y)
            else:
                # 从锚定切换锚定：锚点位置由墙壁决定
                self.anchor_x = wall_x
                self.anchor_y = wall_y
                self._update_center_from_anchor()

            self.attached_wall = wall
            self.anchor_local_pos = wall.world_to_local((self.anchor_x, self.anchor_y))

            # 通知墙壁组件（GoalComponent 发事件，UnstableComponent 记录锚点等）
            wall.on_anchor_attached(self, (self.anchor_x, self.anchor_y))

            self.velocity_x = 0.0
            self.velocity_y = 0.0

            # 判断事件类型
            if wall.has_component("goal") or wall.wall_type == "goal":
                anchor_result = "anchor_goal"
            elif wall.has_component("fragile") or wall.wall_type == "fragile":
                anchor_result = "anchor_fragile"
            else:
                anchor_result = "anchor_normal"
        else:
            # === 没有抓住墙壁 → 进入空中状态 ===
            if self.state == "anchored":
                self._compute_airborne_velocity()
                self._detach_from_current_wall()

            self.state = "airborne"
            self.anchor_side = new_anchor_side

            anchor_result = "anchor_miss"

        # item_result 现在是 (str, Item对象或None) 元组
        item_obj = item_result[1] if item_result else None
        item_str = item_result[0] if item_result else None

        # JSON-loaded 道具（有 item_obj）：统一走 level.apply_item_to_stick()
        # 这样 Tiled 中设置的自定义 value 才会生效（不走 ITEM_CONFIG 硬编码值）
        # 文本地图道具（item_obj=None）：走旧路径 Game._handle_game_event
        if item_obj is not None:
            level.apply_item_to_stick(self, item_obj)
            item_str = None  # 不传给 Game 处理

        return (anchor_result, item_str)

    # ================================================================
    #  强制脱锚（危险物 / 墙壁碎裂调用）
    # ================================================================

    def force_detach(self):
        """
        强制脱锚 — 由 Hazard.trigger() 和 Wall.break_wall() 调用。

        流程:
          1. 若不在锚定状态，直接返回（无操作）
          2. 计算质心线速度（保留旋转动量）
          3. 通知墙壁组件（FragileComponent 会碎裂）
          4. 切换到空中状态，清除墙壁引用
        """
        if self.state != "anchored":
            return

        # 计算质心线速度（保留锚定旋转的动量）
        self._compute_airborne_velocity()

        # 通知墙壁组件脱锚（FragileComponent, UnstableComponent 等）
        self._detach_from_current_wall()

        # 切换到空中状态
        self.state = "airborne"
        self.attached_wall = None
        self.anchor_local_pos = None

    # ---- 内部辅助 ----

    def _compute_airborne_velocity(self):
        """根据当前锚定旋转计算质心线速度"""
        hl = self.length / 2
        ang_vel = self.angular_speed * self.rotation_direction
        if self.anchor_side == 0:
            self.velocity_x = -hl * ang_vel * math.sin(self.angle)
            self.velocity_y = hl * ang_vel * math.cos(self.angle)
        else:
            self.velocity_x = hl * ang_vel * math.sin(self.angle)
            self.velocity_y = -hl * ang_vel * math.cos(self.angle)

    def _detach_from_current_wall(self):
        """通知当前墙壁组件：棍子离开了"""
        if self.attached_wall is not None:
            self.attached_wall.on_anchor_detached(self)
        self.attached_wall = None
        self.anchor_local_pos = None

    def _update_center_from_anchor(self):
        """从锚点位置重新计算质心"""
        dx, dy = self._direction()
        hl = self.length / 2
        if self.anchor_side == 0:
            self.center_x = self.anchor_x + hl * dx
            self.center_y = self.anchor_y + hl * dy
        else:
            self.center_x = self.anchor_x - hl * dx
            self.center_y = self.anchor_y - hl * dy

    # ---- 物理更新 ----
    def update(self, dt):
        self.flash_timer = max(0, self.flash_timer - dt)

        if self.state == "anchored":
            self._update_anchored(dt)
        else:
            self._update_airborne(dt)

    def _update_anchored(self, dt):
        """已锚定状态：自由端绕锚点旋转。如果墙壁移动/旋转，锚点跟随墙壁。"""
        ang_vel = self.angular_speed * self.rotation_direction
        self.angle += ang_vel * dt
        self.angle %= (2 * math.pi)

        # 如果墙壁可能移动/旋转，从墙壁局部坐标重新计算世界锚点
        if self.attached_wall is not None and self.anchor_local_pos is not None:
            new_pos = self.attached_wall.local_to_world(self.anchor_local_pos)
            self.anchor_x = new_pos.x
            self.anchor_y = new_pos.y

        self._update_center_from_anchor()

    def _update_airborne(self, dt):
        """空中飞行状态：质心受重力，绕质心旋转"""
        self.velocity_y += GRAVITY_CONFIG["gravity"] * dt

        self.center_x += self.velocity_x * dt
        self.center_y += self.velocity_y * dt

        ang_vel = self.angular_speed * self.rotation_direction
        self.angle += ang_vel * dt
        self.angle %= (2 * math.pi)

        self.velocity_x *= 0.999
        self.velocity_y *= 0.999

    # ---- 道具效果 ----
    def apply_item(self, effect_type, value):
        """应用道具效果"""
        if effect_type == "LengthUp":
            self.length = min(STICK_CONFIG["max_length"], self.length + value)
            if self.state == "anchored":
                self._update_center_from_anchor()
            self.flash_timer = 0.3
            self.flash_color = C_GREEN
        elif effect_type == "LengthDown":
            self.length = max(STICK_CONFIG["min_length"], self.length - value)
            if self.state == "anchored":
                self._update_center_from_anchor()
            self.flash_timer = 0.3
            self.flash_color = C_RED
        elif effect_type == "SpeedUp":
            self.angular_speed *= (1.0 + value)
            self.base_angular_speed = self.angular_speed
            self.flash_timer = 0.3
            self.flash_color = (60, 140, 255)
        elif effect_type == "SpeedDown":
            self.angular_speed *= (1.0 - value)
            self.angular_speed = max(math.radians(30), self.angular_speed)
            self.base_angular_speed = self.angular_speed
            self.flash_timer = 0.3
            self.flash_color = (180, 100, 255)
        elif effect_type == "Hazard":
            # 危险障碍物：强制脱锚
            if self.state == "anchored":
                self._compute_airborne_velocity()
                self._detach_from_current_wall()
                self.state = "airborne"
            self.flash_timer = 0.3
            self.flash_color = C_RED

    # ---- 碰撞检测辅助 ----
    def get_all_segments(self):
        """返回棍子的所有线段和圆，用于碰撞检测"""
        e0, e1 = self.get_endpoints()
        segments = []
        segments.append(("circle", e0[0], e0[1], self.endpoint_radius))
        segments.append(("circle", e1[0], e1[1], self.endpoint_radius))
        segments.append(("line", e0[0], e0[1], e1[0], e1[1], self.rod_radius))
        return segments

    def get_lowest_y(self):
        """返回棍子的最低 y 坐标（用于岩浆检测）"""
        e0, e1 = self.get_endpoints()
        return max(e0[1] + self.endpoint_radius,
                   e1[1] + self.endpoint_radius)

    def get_highest_y(self):
        """返回棍子的最高 y 坐标"""
        e0, e1 = self.get_endpoints()
        return min(e0[1] - self.endpoint_radius,
                   e1[1] - self.endpoint_radius)

    # ---- 渲染 ----
    def draw(self, screen, camera_y, images):
        """绘制棍子 — 使用杆/左球/右球贴图"""
        e0, e1 = self.get_endpoints()

        sx0, sy0 = int(e0[0]), int(e0[1] - camera_y)
        sx1, sy1 = int(e1[0]), int(e1[1] - camera_y)

        rod_img = images.get("rod")
        if rod_img:
            self._draw_rod_textured(screen, sx0, sy0, sx1, sy1, rod_img)
        else:
            pygame.draw.line(screen, C_STICK_BODY, (sx0, sy0), (sx1, sy1),
                             self.rod_radius * 2)

        if self.state == "anchored":
            anchor = (sx0, sy0) if self.anchor_side == 0 else (sx1, sy1)
            glow_radius = self.endpoint_radius + 6
            glow_surf = pygame.Surface((glow_radius * 4, glow_radius * 4), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (100, 200, 255, 80),
                               (glow_radius * 2, glow_radius * 2), glow_radius)
            screen.blit(glow_surf,
                        (anchor[0] - glow_radius * 2, anchor[1] - glow_radius * 2),
                        special_flags=pygame.BLEND_ALPHA_SDL2)

        left_ball = images.get("left_ball")
        right_ball = images.get("right_ball")
        flash = self.flash_timer > 0

        for i, (sx, sy) in enumerate([(sx0, sy0), (sx1, sy1)]):
            ball_img = left_ball if i == 0 else right_ball
            if ball_img:
                r = self.endpoint_radius
                scaled = pygame.transform.scale(ball_img, (r * 2 + 4, r * 2 + 4))
                screen.blit(scaled, (sx - r - 2, sy - r - 2))
            else:
                color = self.flash_color if flash else C_STICK_ENDPOINT
                pygame.draw.circle(screen, C_STICK_OUTLINE, (sx, sy), self.endpoint_radius)
                pygame.draw.circle(screen, color, (sx, sy), self.endpoint_radius - 2)

    def _draw_rod_textured(self, screen, x0, y0, x1, y1, rod_img):
        """使用纹理绘制棍体"""
        dx = x1 - x0
        dy = y1 - y0
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < 1:
            return
        angle_deg = math.degrees(math.atan2(dy, dx))
        rod_w = max(4, self.rod_radius * 2)
        scaled_rod = pygame.transform.scale(rod_img, (int(dist), int(rod_w)))
        rotated_rod = pygame.transform.rotate(scaled_rod, -angle_deg)
        rr = rotated_rod.get_rect()
        cx = (x0 + x1) / 2
        cy = (y0 + y1) / 2
        screen.blit(rotated_rod, (cx - rr.width / 2, cy - rr.height / 2))
