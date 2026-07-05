"""
core/game.py
O---O 游戏主类 — 流程控制、状态管理、主循环
"""

import math
import pygame

from data_config import (
    SCREEN_WIDTH, SCREEN_HEIGHT, FPS,
    STICK_CONFIG, PARTICLE_CONFIG, LAVA_CONFIG,
    SOUND_CONFIG, ITEM_CONFIG, TILE_SIZE, PARALLAX_RATIO
)
from core.game_state import GameState
from core.input_manager import InputManager
from core.event_bus import event_bus

from entities.stick import Stick
from level.level import Level
from level.level_loader import LevelLoader

from systems.camera import Camera, SeaCameraBob
from systems.image_manager import ImageManager
from systems.sound_manager import SoundManager
from systems.particle_system import ParticleSystem

import render as rdr

# 颜色常量（游戏对象渲染用）
C_BG = (15, 12, 25)
C_PARTICLE_SPARK = (255, 240, 100)


class Game:
    """O---O 游戏主类 — 只负责流程，不包含具体系统实现"""

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("O---O  -  一键攀登")
        self.clock = pygame.time.Clock()
        self.running = True
        self.state = GameState.MENU
        self.debug = False

        # 子系统
        self.input_mgr = InputManager()
        self.image_mgr = ImageManager()
        self.sound_mgr = SoundManager()
        self.particles = ParticleSystem()

        # UI
        self.fonts = rdr.FontManager()
        self.fonts.load()
        self.bubbles = rdr.BubbleManager()

        # 关卡进度
        self.current_level_id = "level1"

        # 菜单动画
        self.menu_time = 0.0
        self.menu_stick_angle = 0.0

        # 游戏对象（延迟创建）
        self.level = None
        self.stick = None
        self.camera = None
        self.sea_bob = SeaCameraBob()

        # 状态追踪
        self._prev_stick_state = None
        self.screen_shake = 0.0
        self.result_timer = 0.0
        self.pending_events = []
        self._menu_bgm_started = False
        self._game_bgm_started = False

        # 加载素材
        self._load_assets()

        # 连接事件总线
        self._setup_event_bus()

    # ---- 素材加载 ----
    def _load_assets(self):
        """加载音效和图片"""
        self.sound_mgr.load_all(SOUND_CONFIG)

        # 额外音效
        self.sound_mgr.load("fragile_grab", "arts/sounds/wall_attached/se_blockFall砖被抓住.wav")
        self.sound_mgr.load("fragile_break", "arts/sounds/wall_attached/se_blockAutoBreak砖破坏.wav")
        self.sound_mgr.load("hazard_touch", "arts/sounds/道具音效/碰到障碍.wav")
        self.sound_mgr.load("checkpoint_on", "arts/sounds/道具音效/se_激活检查点.wav")

        # Stick
        self.image_mgr.load("rod", "arts/stick/杆.png")
        self.image_mgr.load("left_ball", "arts/stick/左球.png")
        self.image_mgr.load("right_ball", "arts/stick/右球.png")
        # Walls
        self.image_mgr.load("normal_wall", "arts/walls/normal_wall.png")
        self.image_mgr.load("fragile_wall", "arts/walls/fragile_wall.png")
        self.image_mgr.load("goal_wall", "arts/walls/goal_wall.png")
        self.image_mgr.load("solid_ghost", "arts/walls/solid_ghost.png")
        self.image_mgr.load("solid_toggle", "arts/walls/solid_toggle.png")
        # Items
        self.image_mgr.load("hazard", "arts/items/hazard.png")
        self.image_mgr.load("length_up", "arts/items/length_up.png")
        self.image_mgr.load("length_down", "arts/items/length_down.png")
        self.image_mgr.load("speed_up", "arts/items/speed_up.png")
        self.image_mgr.load("speed_down", "arts/items/speed_down.png")
        self.image_mgr.load("key", "arts/items/key.png")
        self.image_mgr.load("checkpoint_off", "arts/items/checkpoint未激活.png")
        self.image_mgr.load("checkpoint_on", "arts/items/checkpoint已经激活.png")
        # Lava & background
        self.image_mgr.load("lava", "arts/lava/lava.gif")
        self.image_mgr.load("menu_bg", "arts/backgrounds/背景.png")
        self.image_mgr.load("level_bg", "arts/backgrounds/背景.png")
        self.image_mgr.load("sky", "arts/backgrounds/sky.png")

    def _setup_event_bus(self):
        """连接事件总线：音效、粒子、UI 气泡响应游戏事件"""
        event_bus.subscribe("anchor_success", self._on_anchor_success)
        event_bus.subscribe("anchor_fragile", self._on_anchor_fragile)
        event_bus.subscribe("anchor_miss", self._on_anchor_miss)
        event_bus.subscribe("goal_reached", self._on_goal_reached)
        event_bus.subscribe("hazard_triggered", self._on_hazard_triggered)
        event_bus.subscribe("wall_break", self._on_wall_break)
        event_bus.subscribe("checkpoint_activated", self._on_checkpoint)
        event_bus.subscribe("item_picked", self._on_item_picked)

    def _on_anchor_success(self, data):
        pos = data.get("position", (self.stick.center_x, self.stick.center_y))
        self.particles.emit_sparks(
            pos[0], pos[1],
            PARTICLE_CONFIG["anchor_spark_count"],
            C_PARTICLE_SPARK,
            PARTICLE_CONFIG["anchor_spark_speed"],
            PARTICLE_CONFIG["anchor_spark_lifetime"]
        )
        self.screen_shake = 0.08
        self.sound_mgr.play_random("anchor_attach", "arts/sounds/attach")
        self._spawn_bubble_at_stick("snap")

    def _on_anchor_fragile(self, data):
        pos = data.get("position", (self.stick.center_x, self.stick.center_y))
        self.particles.emit_sparks(pos[0], pos[1], 15, (180, 180, 200), 200, 0.4)
        self.sound_mgr.play("fragile_grab")
        self._spawn_bubble_at_stick("fragile")

    def _on_anchor_miss(self, data):
        self.particles.emit_sparks(
            self.stick.center_x, self.stick.center_y,
            6, (100, 100, 180), 120, 0.3
        )
        self.sound_mgr.play("anchor_miss")
        self._spawn_bubble_at_stick("miss")

    def _on_goal_reached(self, data):
        self.state = GameState.WIN
        self.result_timer = 0.0
        self.particles.emit_sparks(
            self.stick.anchor_x, self.stick.anchor_y,
            40, (255, 220, 60), 300, 1.0
        )
        self.sound_mgr.play("goal")
        self._spawn_bubble_at_stick("goal")

    def _on_hazard_triggered(self, data):
        self.particles.emit_sparks(
            self.stick.center_x, self.stick.center_y,
            15, (255, 60, 40), 250, 0.5
        )
        self.screen_shake = 0.2
        self.sound_mgr.play("hazard_touch")
        self._spawn_bubble_at_stick("hazard")

    def _on_wall_break(self, data):
        self.sound_mgr.play("fragile_break")
        pos = data.get("position", (0, 0))
        self.particles.emit_debris(pos[0], pos[1], 15,
                                    (150, 140, 120), 150, 0.5)

    def _on_checkpoint(self, data):
        self.sound_mgr.play("checkpoint_on")

    def _on_item_picked(self, data):
        etype = data.get("effect_type", "")
        val = data.get("value", 0)
        self.stick.apply_item(etype, val)
        bubble_map = {
            "LengthUp": "length_up", "LengthDown": "length_down",
            "SpeedUp": "speed_up", "SpeedDown": "speed_down",
        }
        btype = bubble_map.get(etype, "snap")
        self._spawn_bubble_at_stick(btype)
        self.sound_mgr.play(etype.lower())

    # ---- 关卡加载 ----
    def start_game(self, level_id=None):
        """初始化/重新开始游戏。不传 level_id 则从当前关卡开始。"""
        if level_id is None:
            level_id = self.current_level_id
        else:
            self.current_level_id = level_id
        try:
            self.level = LevelLoader.load(level_id)
        except Exception as e:
            print(f"从 maps/ 加载关卡失败: {e}，使用内置实验关卡")
            self.level = self._create_fallback_level()

        player_start = self.level.player_start

        # 自动找到离出生点最近的墙壁作为起始锚点
        start_info = self.level.find_starting_wall()
        if start_info is None:
            print("错误: 关卡没有找到可用墙壁，无法开始游戏！")
            self.state = GameState.MENU
            return
        starting_wall, anchor_x, anchor_y = start_info

        self.stick = Stick(
            x=anchor_x, y=anchor_y,
            angle=math.radians(90),
            length=STICK_CONFIG["length"],
            angular_speed=math.radians(STICK_CONFIG["angular_speed"])
        )
        self.stick.state = "anchored"
        self.stick.anchor_side = 0
        self.stick.anchor_x = anchor_x
        self.stick.anchor_y = anchor_y
        self.stick.rotation_direction = 1

        # 关联墙壁对象 + 设置局部锚点坐标
        self.stick.attached_wall = starting_wall
        self.stick.anchor_local_pos = starting_wall.world_to_local((anchor_x, anchor_y))
        # 通知墙壁组件（UnstableComponent 等需要记录锚点）
        starting_wall.on_anchor_attached(self.stick, (anchor_x, anchor_y))

        self.stick._update_center_from_anchor()

        self.camera = Camera(
            y=max(0, self.stick.center_y - SCREEN_HEIGHT * 0.45),
            map_height=self.level.height
        )

        self.level.lava_y = player_start[1] + LAVA_CONFIG["start_y_below_player"]

        self.particles.clear()
        self.bubbles.clear()
        self.pending_events.clear()
        self.screen_shake = 0.0
        self.result_timer = 0.0
        self._prev_stick_state = None
        self.state = GameState.PLAYING

        # BGM 只首次进入游戏时播放，重新开始时接着播不打断
        if not self._game_bgm_started:
            self._game_bgm_started = True
            self.sound_mgr.stop_bgm()
            self.sound_mgr.play_bgm("arts/sounds/main_theme/celeste_mello.mp3", loop=False)
        self.sound_mgr.play("game_start")

    def _handle_death(self, cause="lava"):
        """处理玩家死亡 — 优先从存档点恢复，无存档则走死亡流程"""
        if self.level.checkpoint_manager.has_checkpoint():
            self._restore_from_checkpoint()
            return

        # 无存档点：正常死亡
        self.state = GameState.DEAD
        self.result_timer = 0.0
        if cause == "lava":
            self.particles.emit_sparks(
                self.stick.center_x, self.stick.center_y,
                30, (255, 100, 30), 300, 0.8
            )
        self.sound_mgr.play("lava_death")

    def _restart_or_checkpoint(self):
        """R 键：从存档点恢复，无存档则从头开始"""
        if self.level is not None and self.level.checkpoint_manager.has_checkpoint():
            self._restore_from_checkpoint()
        else:
            self.start_game()

    def next_level(self):
        """进入下一关（level1 → level2 → level3 ...）"""
        import re, os
        match = re.match(r"level(\d+)", self.current_level_id)
        if match:
            n = int(match.group(1)) + 1
            next_id = f"level{n}"
            if os.path.exists(f"maps/{next_id}"):
                self.current_level_id = next_id
                self.start_game()
                return
        print(f"[Game] 没有下一关: {self.current_level_id}")

    def _restore_from_checkpoint(self):
        """从存档点恢复"""
        ok = self.level.checkpoint_manager.restore(
            self.level, self.stick, self.camera,
            self.level.consumed_items
        )
        if ok:
            self.state = GameState.PLAYING
            self.result_timer = 0.0
            self.screen_shake = 0.0
            self._prev_stick_state = None
            self.particles.clear()
            self.bubbles.clear()
            self.pending_events.clear()
            self.sound_mgr.play("game_start")
        else:
            self.start_game()

    def _create_fallback_level(self):
        """内置实验关卡（兜底用）— 使用 map.txt 同等格式"""
        layout = [
            "....................",
            "........G...........",
            "....................",
            ".....######.........",
            "....................",
            "....................",
            "..........######....",
            "....................",
            "....................",
            ".....######.........",
            "....................",
            "........+...........",
            "..........######....",
            "....................",
            "....................",
            ".....######.........",
            "....................",
            ".......H............",
            "..........######....",
            "....................",
            "....................",
            ".....######.........",
            "....................",
            "....................",
            "..........######....",
            "....................",
            "....................",
            ".....######.........",
            "....................",
            "....................",
            "..........######....",
            "....................",
            "....................",
            "....###########.....",
            "....................",
        ]
        return Level(layout, (288, 1072))

    # ---- 输入处理 ----
    def handle_events(self):
        """处理输入事件"""
        events = self.input_mgr.poll()
        for evt in events:
            if evt == "quit":
                self.running = False
            elif evt == "space":
                if self.state == GameState.MENU:
                    self.start_game()
                elif self.state == GameState.PLAYING:
                    self.queue_event("space")
                elif self.state == GameState.WIN:
                    self.next_level()
            elif evt == "test_level":
                if self.state == GameState.MENU:
                    self.current_level_id = "level_test"
                    self.start_game()
            elif evt == "toggle_debug":
                self.debug = not self.debug
            elif evt == "restart":
                if self.state in (GameState.WIN, GameState.DEAD):
                    self._restart_or_checkpoint()
                elif self.state == GameState.PLAYING:
                    self._restart_or_checkpoint()

    def queue_event(self, evt):
        """将事件加入队列"""
        self.pending_events.append(evt)

    # ---- 更新 ----
    def update(self, dt):
        """更新游戏逻辑"""
        if self.state == GameState.MENU:
            self.menu_time += dt
            self.menu_stick_angle += math.radians(120) * dt
            return

        if self.state in (GameState.WIN, GameState.DEAD):
            self.result_timer += dt
            self.particles.update(dt)
            self.bubbles.update(dt)
            return

        # PLAYING 状态 — 检测状态变化
        if self._prev_stick_state is not None:
            if self._prev_stick_state == "airborne" and self.stick.state == "anchored":
                self._spawn_bubble_at_stick("airborne")
        self._prev_stick_state = self.stick.state

        # 处理待处理事件
        for evt in self.pending_events:
            self._handle_game_event(evt)
        self.pending_events.clear()

        # 更新棍子
        self.stick.update(dt)

        # 检测危险障碍物
        if self.level.check_hazard_collision(self.stick):
            if self.stick.state == "anchored":
                self.stick.apply_item("Hazard", 0)
                event_bus.emit("hazard_triggered", {
                    "position": (self.stick.center_x, self.stick.center_y)
                })

        # 更新关卡（墙壁组件 + 岩浆 + OnTouch 道具）
        self.level.update(dt, self.stick)

        # 检测岩浆死亡
        if self.level.is_in_lava(self.stick):
            self._handle_death("lava")
            return

        # 检测掉落出地图底部
        if self.stick.get_lowest_y() > self.level.height + 100:
            self._handle_death("fall")
            return

        # 更新相机
        # 锚定时跟踪锚点端（固定不动），空中时跟踪质心
        if self.stick.state == "anchored":
            self.camera.set_target(self.stick.get_anchor_endpoint()[1])
        else:
            self.camera.set_target(self.stick.center_y)
        self.camera.update(dt)

        # 海上漂浮晃动 — 直接叠加到 camera.y / camera.bob_x
        self.sea_bob.update(dt)
        if self.level:
            stick_y = self.stick.get_anchor_endpoint()[1] if self.stick.state == "anchored" else self.stick.center_y
            bob_x, bob_y = self.sea_bob.get_offset(stick_y, self.level.lava_y + 90)
            self.camera.y += bob_y
            self.camera.bob_x = bob_x

        # 屏幕震动衰减
        if self.screen_shake > 0:
            self.screen_shake = max(0, self.screen_shake - dt)
            self.camera.apply_shake(self.screen_shake * 15)

        # 更新粒子和气泡
        self.particles.update(dt)
        self.bubbles.update(dt)

        # 推进 GIF 动画（岩浆等）
        for anim in self.image_mgr.animations.values():
            anim.update(dt)

    def _handle_game_event(self, evt):
        """处理游戏中的事件 — switch_anchor 返回 (锚点结果, 道具结果或None)"""
        if evt != "space" or self.state != GameState.PLAYING:
            return

        anchor_result, item_result = self.stick.switch_anchor(self.level)

        # 处理锚点事件
        if anchor_result == "anchor_goal":
            event_bus.emit("goal_reached", {
                "position": (self.stick.anchor_x, self.stick.anchor_y)
            })
        elif anchor_result == "anchor_normal":
            event_bus.emit("anchor_success", {
                "position": (self.stick.anchor_x, self.stick.anchor_y)
            })
        elif anchor_result == "anchor_fragile":
            event_bus.emit("anchor_fragile", {
                "position": (self.stick.anchor_x, self.stick.anchor_y)
            })
        elif anchor_result == "anchor_miss":
            event_bus.emit("anchor_miss", {})

        # 处理道具（即使抓住墙壁也会触发 — 支持道具与墙壁重叠）
        if item_result and item_result.startswith("item_"):
            effect_map = {
                "item_LengthUp": ("LengthUp", ITEM_CONFIG["length_up"]["value"]),
                "item_LengthDown": ("LengthDown", ITEM_CONFIG["length_down"]["value"]),
                "item_SpeedUp": ("SpeedUp", ITEM_CONFIG["speed_up"]["value"]),
                "item_SpeedDown": ("SpeedDown", ITEM_CONFIG["speed_down"]["value"]),
            }
            if item_result in effect_map:
                etype, val = effect_map[item_result]
                event_bus.emit("item_picked", {
                    "effect_type": etype,
                    "value": val
                })

    # ---- 气泡弹字辅助 ----
    def _world_to_screen(self, wx, wy):
        return self.camera.world_to_screen(wx, wy)

    def _spawn_bubble_at_stick(self, bubble_type):
        free = self.stick.get_free_endpoint()
        sx, sy = self._world_to_screen(free[0], free[1])
        sy -= 30
        self.bubbles.spawn(bubble_type, x=sx, y=sy,
                           screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)

    # ---- 渲染 ----
    def render(self):
        """主渲染函数 — 委托给 render.py"""
        screen_w, screen_h = SCREEN_WIDTH, SCREEN_HEIGHT
        now = pygame.time.get_ticks() / 1000.0

        if self.state == GameState.MENU:
            if not self._menu_bgm_started:
                self._menu_bgm_started = True
                self._game_bgm_started = False
                self.sound_mgr.play_bgm("arts/sounds/title_bgm/tide ambient.mp3", loop=True)
            self._draw_menu_bg()
            rdr.draw_main_menu_ui(self.screen, self.fonts, self.menu_time, screen_w, screen_h)
            rdr.draw_menu_stick_animation(self.screen, self.menu_stick_angle, self.menu_time, screen_w)
            self._draw_menu_wave()

        elif self.state == GameState.PLAYING:
            self._draw_game_scene()
            rdr.draw_game_ui(self.screen, self.fonts, self.stick, self.level,
                             self.camera.y, now, screen_w, screen_h, self.bubbles)

        elif self.state == GameState.WIN:
            self._draw_game_scene()
            rdr.draw_game_ui(self.screen, self.fonts, self.stick, self.level,
                             self.camera.y, now, screen_w, screen_h, self.bubbles)
            rdr.draw_win_overlay(self.screen, self.fonts, self.result_timer, screen_w, screen_h)

        elif self.state == GameState.DEAD:
            self._draw_game_scene()
            rdr.draw_game_ui(self.screen, self.fonts, self.stick, self.level,
                             self.camera.y, now, screen_w, screen_h, self.bubbles)
            rdr.draw_dead_overlay(self.screen, self.fonts, self.result_timer, screen_w, screen_h)

        if self.debug and self.state == GameState.PLAYING:
            rdr.draw_debug_overlay(self.screen, self.fonts, self, screen_w)

        pygame.display.flip()

    def _draw_game_scene(self):
        """绘制游戏场景（背景直接在屏幕，关卡/粒子/棍子通过偏移表面实现横向漂浮）"""
        self._draw_bg()
        camera_y = self.camera.y
        bob_x = int(self.camera.bob_x)
        tmp = pygame.Surface((SCREEN_WIDTH + abs(bob_x) * 2, SCREEN_HEIGHT), pygame.SRCALPHA)
        self.level.draw(tmp, camera_y, self.image_mgr.images, self.image_mgr)
        self.particles.draw(tmp, camera_y)
        self.stick.draw(tmp, camera_y, self.image_mgr.images)
        self.screen.blit(tmp, (bob_x, 0))

    def _draw_menu_bg(self):
        """菜单背景：天空 + 蓝色海难色调"""
        sky = self.image_mgr.get("sky")
        if sky:
            sky_h = int(sky.get_height() * SCREEN_WIDTH / sky.get_width())
            sky_scaled = pygame.transform.scale(sky, (SCREEN_WIDTH, sky_h))
            for y in range(0, SCREEN_HEIGHT, sky_h):
                self.screen.blit(sky_scaled, (0, y))
        else:
            self.screen.fill((10, 20, 50))  # 深蓝色

    def _draw_menu_wave(self):
        """菜单底部波浪 — 让玩家第一眼就知道要逃离什么"""
        wave_h = 150
        lava_img = None
        anim = self.image_mgr.get_animation("lava")
        if anim:
            lava_img = anim.current_frame
        if not lava_img:
            lava_img = self.image_mgr.get("lava")
        if lava_img:
            scaled = pygame.transform.scale(lava_img, (SCREEN_WIDTH, wave_h))
            self.screen.blit(scaled, (0, SCREEN_HEIGHT - wave_h))

    def _draw_bg(self):
        """绘制背景：远景以 PARALLAX_RATIO:1 慢速滚动，近景全速"""
        bg = self.image_mgr.get("level_bg")
        sky = self.image_mgr.get("sky")
        screen_w, screen_h = SCREEN_WIDTH, SCREEN_HEIGHT
        p_y = self.camera.y / PARALLAX_RATIO

        # 1. 天空无限平铺（远景速度）
        if sky:
            sky_h = int(sky.get_height() * SCREEN_WIDTH / sky.get_width())
            sky_scaled = pygame.transform.scale(sky, (SCREEN_WIDTH, sky_h))
            y = - (p_y % sky_h)
            while y < screen_h:
                self.screen.blit(sky_scaled, (0, int(y)))
                y += sky_h
        else:
            self.screen.fill(C_BG)

        # 2. 背景图底部对齐地图底部（远景速度）
        if bg:
            bg_h = int(bg.get_height() * SCREEN_WIDTH / bg.get_width())
            bg_scaled = pygame.transform.scale(bg, (SCREEN_WIDTH, bg_h))
            bg_screen_y = self.level.height / PARALLAX_RATIO - p_y
            self.screen.blit(bg_scaled, (0, bg_screen_y - bg_h))

    # ---- 主循环 ----
    def run(self):
        """主游戏循环"""
        while self.running:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.1)

            self.handle_events()
            self.update(dt)
            self.render()

        pygame.quit()
