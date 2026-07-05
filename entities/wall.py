"""
entities/wall.py
Wall 墙壁实体 — 统一墙壁系统

======================================================================
  架构设计
======================================================================

  墙壁系统采用 "实体 + 组件 + 策略" 三层架构:

    Wall (实体)
    ├── 基础属性: 位置、尺寸、类型、旋转
    ├── 碰撞检测: contains_point / clamp_point
    ├── 坐标转换: world_to_local / local_to_world (支持旋转)
    ├── 渲染: draw (支持任意尺寸矩形 + 贴图平铺)
    │
    └── components (组件 — 墙壁的"能力")
        ├── FragileComponent  : 脆弱 — 脱锚后碎裂
        ├── GoalComponent     : 终点 — 抓住通关
        ├── MovingComponent   : 移动 — 持有 MoveStrategy
        │   │
        │   └── move_strategy (策略 — 移动的"方式")
        │       ├── LoopMoveStrategy      循环绕圈
        │       ├── PingPongMoveStrategy  来回往返
        │       └── OneShotMoveStrategy   单次到达即停
        │
        └── UnstableComponent: 不稳定 — 抓住后倾斜, 离开后回正

======================================================================
  使用示例
======================================================================

  # 普通墙
  w = Wall(160, 96, 32, 32, "normal")

  # 组合墙: 脆弱 + 移动 + 不稳定
  w = Wall(320, 560, 160, 32, "normal")
  w.add_component("fragile", create_component("fragile"))
  w.add_component("moving", create_component("moving", {
      "strategy": "pingpong", "speed": 80,
      "path": [[320,560], [480,560], [480,420]]
  }))
  w.add_component("unstable", create_component("unstable", {
      "max_tilt_angle": 45, "inertia": 90
  }))

  # 终点墙
  w = Wall(256, 32, 32, 32, "goal")
"""

import math
import pygame
from physics.vector import Vector2
from physics.geometry import clamp, move_towards


# ================================================================
#  移动策略 (MoveStrategy)
# ================================================================
#
#  策略模式: 把"怎么移动"从 MovingComponent 中抽离出来。
#  同一种 MovingComponent 可以绑定不同策略:
#    Loop      → 永远绕圈
#    PingPong  → 来回往返
#    OneShot   → 走到终点就停
#
#  每种策略更新墙壁的 x/y 坐标，MovingComponent 只负责每帧调用
#  strategy.update(dt, wall)。
# ================================================================


class MoveStrategy:
    """
    移动策略基类。

    参数
    ----
    path_points : list[list[float,float]]
        路径点列表，如 [[0,0], [100,0], [100,100]]
    move_speed : float
        移动速度（像素/秒），默认 80。
    """

    def __init__(self, path_points, move_speed=80):
        self.path = [Vector2(p) for p in path_points]
        self.move_speed = move_speed
        self._elapsed = 0.0

    def update(self, dt, wall):
        raise NotImplementedError

    @staticmethod
    def _calc_total(path, loop):
        """计算路径总长度。loop=True 时计入首尾闭合段。"""
        total = 0.0
        n = len(path)
        for i in range(n):
            j = (i + 1) % n if loop else i + 1
            if j < n:
                total += (path[j] - path[i]).length()
        return max(total, 0.0001)

    @staticmethod
    def _move_along(wall, dist, path, loop):
        """
        沿路径走到距离 dist 处，写入 wall.x / wall.y。
        """
        accumulated = 0.0
        n = len(path)
        for i in range(n):
            j = (i + 1) % n if loop else i + 1
            if j >= n:
                break
            seg_len = (path[j] - path[i]).length()
            if accumulated + seg_len >= dist:
                t = (dist - accumulated) / max(seg_len, 0.0001)
                wall.x = path[i].x + (path[j].x - path[i].x) * t
                wall.y = path[i].y + (path[j].y - path[i].y) * t
                return
            accumulated += seg_len


class PingPongMoveStrategy(MoveStrategy):
    """
    来回移动策略 — 到达终点后反向走回起点。

    路径 A → B → C → B → A → B → C → ...
    内部将路径扩展为往返序列: path + path[-2:0:-1]

    示例::
        PingPongMoveStrategy([[0,0], [200,0], [200,100]], move_speed=60)
        # (0,0)→(200,0)→(200,100)→(200,0)→(0,0)→(200,0)→...
    """

    def __init__(self, path_points, move_speed=80):
        super().__init__(path_points, move_speed)
        if len(self.path) >= 2:
            # 构建往返路径: A→B→C→B→A（包含最后一段 A 保证无缝循环）
            self._full_path = self.path + self.path[-2::-1]
        else:
            self._full_path = self.path[:]
        self._total = MoveStrategy._calc_total(self._full_path, loop=False)

    def update(self, dt, wall):
        if len(self._full_path) < 2:
            return
        self._elapsed += dt
        dist = (self._elapsed * self.move_speed) % self._total
        MoveStrategy._move_along(wall, dist, self._full_path, loop=False)


class OneShotMoveStrategy(MoveStrategy):
    """
    触发式单次移动 — 棍子抓住墙壁后才开始移动，到终点停止。

    初始停在路径起点。trigger() 被调用后才开始沿路径移动一次。
    路径 A → B → C → 停止。

    示例::
        OneShotMoveStrategy([[320,560], [320,200]], move_speed=120)
        # 墙壁停在 (320,560)，棍子抓住后移向 (320,200)
    """

    def __init__(self, path_points, move_speed=80):
        super().__init__(path_points, move_speed)
        self.triggered = False  # 是否已被触发
        self.finished = False   # 是否已到达终点

    def trigger(self):
        """棍子抓住墙壁时调用，启动移动"""
        self.triggered = True

    def update(self, dt, wall):
        if not self.triggered or self.finished or len(self.path) < 2:
            return
        self._elapsed += dt
        total = MoveStrategy._calc_total(self.path, loop=False)
        max_dist = self.move_speed * self._elapsed
        if max_dist >= total:
            wall.x = self.path[-1].x
            wall.y = self.path[-1].y
            self.finished = True
            return
        MoveStrategy._move_along(wall, max_dist, self.path, loop=False)


# ================================================================
#  墙壁组件 (WallComponent)
# ================================================================
#
#  组件模式: 墙壁的"能力"通过添加 Component 获得。
#  不是:  FragileWall(MovingWall(UnstableWall))
#  而是:  Wall + FragileComponent + MovingComponent + UnstableComponent
#
#  每个组件通过 self.owner 访问所属的 Wall 对象。
#  组件之间可以协作: 例如 UnstableComponent 检测 attached_stick
#  来判断是否有棍子抓着这面墙。
# ================================================================


class WallComponent:
    """
    墙壁组件基类 — 所有组件接口。

    生命周期钩子:
      update(dt)              每帧更新
      on_anchor_attached()    棍子抓住时
      on_anchor_detached()    棍子离开时

    属性:
      self.owner : Wall | None
          所属墙壁，由 Wall.add_component() 自动设置。
    """

    def __init__(self):
        self.owner = None

    def update(self, dt):
        """每帧更新。子类重写以实现行为。"""
        pass

    def on_anchor_attached(self, stick, world_pos):
        """
        棍子的锚点抓住这面墙时调用。

        参数
        ----
        stick : Stick
            抓住墙壁的棍子对象
        world_pos : (float, float)
            锚点在世界坐标系中的位置
        """
        pass

    def on_anchor_detached(self, stick):
        """
        棍子的锚点离开这面墙时调用。

        参数
        ----
        stick : Stick
            离开墙壁的棍子对象
        """
        pass


class FragileComponent(WallComponent):
    """
    脆弱组件 — 锚点离开后墙壁自动碎裂。

    参数
    ----
    break_on_detach : bool
        是否在脱锚时碎裂，默认 True。
        设为 False 时组件不执行任何操作（相当于禁用）。

    生命周期:
      棍子抓住 → 棍子离开 → on_anchor_detached() → wall.break_wall()
    """

    def __init__(self, break_on_detach=True):
        super().__init__()
        self.break_on_detach = break_on_detach

    def on_anchor_detached(self, stick):
        if self.break_on_detach and self.owner is not None:
            self.owner.break_wall()


class GoalComponent(WallComponent):
    """
    终点组件 — 棍子抓住后触发通关。

    不直接修改游戏状态，而是通过 EventBus 发布 "goal_reached" 事件。
    Game 类监听该事件后切换到 WIN 状态。

    数据:
      event_data = {"stick": stick, "wall": self.owner, "position": world_pos}
    """

    def on_anchor_attached(self, stick, world_pos):
        from core.event_bus import event_bus
        event_bus.emit("goal_reached", {
            "stick": stick,
            "wall": self.owner,
            "position": world_pos,
        })


class MovingComponent(WallComponent):
    """
    移动组件 — 每帧按 MoveStrategy 更新墙壁位置。

    持有: MoveStrategy 实例（PingPong 或 OneShot）

    update() 流程:
      if move_strategy exists and owner exists:
          move_strategy.update(dt, self.owner)

    棍子抓住时触发 OneShotMoveStrategy:
      on_anchor_attached() → strategy.trigger()
    """

    def __init__(self, move_strategy=None):
        super().__init__()
        self.move_strategy = move_strategy

    def update(self, dt):
        if self.move_strategy is not None and self.owner is not None:
            self.move_strategy.update(dt, self.owner)

    def on_anchor_attached(self, stick, world_pos):
        """棍子抓住时触发 OneShot 策略"""
        if hasattr(self.move_strategy, 'trigger'):
            self.move_strategy.trigger()


class UnstableComponent(WallComponent):
    """
    不稳定组件 — 棍子抓住后墙壁根据力臂倾斜，离开后缓慢回正。

    ======  物理模型  ======

    当棍子抓住墙壁时:
      1. 计算抓点相对墙壁中心的偏移 → 力臂长度
      2. 棍子重量 × 力臂 → 力矩
      3. 力矩 / 转动惯量 → 角加速度
      4. 角速度积分 → 倾斜角度

    当棍子离开后:
      5. 角速度 = 0
      6. 角度以 return_speed 的速度缓慢回正到 0°

    ======  参数说明  ======

    max_tilt_angle : float
        最大倾斜角度（度），默认 35°。
        墙壁倾斜不会超过此值。

    tilt_direction : str
        倾斜方向限制: "both" | "clockwise" | "counter_clockwise"。
        "both" = 两端都可以倾斜。
        "clockwise" = 只允许顺时针（pygame 中 y↓，顺时针 = 正向）。

    inertia : float
        转动惯量，默认 120。
        越大越难倾斜（需要更多力矩才能产生角加速度）。
        类似质量在直线运动中的作用。

    torque_scale : float
        力矩缩放系数，默认 1.0。
        >1 倾斜更快，<1 倾斜更慢。

    damping : float
        角速度阻尼系数，默认 1.5。
        每帧: angular_velocity -= angular_velocity * damping * dt
        值越大，倾斜后越快稳定。

    return_speed : float
        无锚点时回正速度（度/秒），默认 20。
        设为 0 则永远不回正（保持倾斜）。

    break_at_max_tilt : bool
        达到最大倾斜后是否碎裂，默认 False。
    """

    def __init__(self, config=None):
        super().__init__()
        cfg = config or {}

        # ---- 配置参数 ----
        self.max_tilt_angle = math.radians(cfg.get("max_tilt_angle", 35))
        self.tilt_direction = cfg.get("tilt_direction", "both")
        self.inertia = cfg.get("inertia", 120.0)
        self.torque_scale = cfg.get("torque_scale", 1.0)
        self.damping = cfg.get("damping", 1.5)
        self.return_speed = math.radians(cfg.get("return_speed", 20))
        self.break_at_max_tilt = cfg.get("break_at_max_tilt", False)

        # ---- 运行时状态 ----
        self.tilt_angle = math.radians(cfg.get("tilt_angle", 0))
        self.angular_velocity = cfg.get("angular_velocity", 0.0)
        self.angular_acceleration = 0.0

        # 当前抓住此墙的棍子（用于计算力矩）
        self.attached_stick = None
        # 锚点在墙壁局部坐标中的位置（用于计算力臂）
        self.anchor_local_pos = None

    # ---- 生命周期钩子 ----

    def on_anchor_attached(self, stick, world_pos):
        """
        棍子抓住时记录: 哪个棍子、在墙壁上的哪个局部位置。
        这些信息用于后续 update() 中计算力矩。
        """
        self.attached_stick = stick
        # world → local: 世界锚点 → 墙壁局部坐标
        self.anchor_local_pos = self.owner.world_to_local(world_pos)

    def on_anchor_detached(self, stick):
        """棍子离开时清空追踪。"""
        if self.attached_stick == stick:
            self.attached_stick = None
            self.anchor_local_pos = None

    # ---- 每帧更新 ----

    def update(self, dt):
        """
        物理更新:

        有棍子抓着 → 计算力矩 → 角加速度 → 角速度 → 倾斜角
        无棍子     → 缓慢回正到 0°
        """
        if self.attached_stick is not None:
            # === 有棍子抓着：墙壁受重力矩影响倾斜 ===
            torque = self._compute_torque()
            # τ = I·α  →  α = τ / I
            self.angular_acceleration = torque / max(self.inertia, 0.0001)
            # ω += α·dt
            self.angular_velocity += self.angular_acceleration * dt
        else:
            # === 无棍子：缓慢回正 ===
            self.angular_acceleration = 0.0
            if self.return_speed > 0:
                self.tilt_angle = move_towards(
                    self.tilt_angle, 0.0, self.return_speed * dt
                )

        # 阻尼衰减: ω -= ω·damping·dt
        self.angular_velocity -= self.angular_velocity * self.damping * dt

        # 角度积分: θ += ω·dt
        self.tilt_angle += self.angular_velocity * dt

        # ---- 限制最大倾斜 ----
        if abs(self.tilt_angle) > self.max_tilt_angle:
            # 夹紧到 ±max_tilt_angle
            self.tilt_angle = (
                self.max_tilt_angle if self.tilt_angle > 0
                else -self.max_tilt_angle
            )
            self.angular_velocity = 0.0  # 撞到极限后速度归零
            # 如果配置为 "达到最大倾斜后碎裂"
            if self.break_at_max_tilt and self.owner is not None:
                self.owner.break_wall()

        # 应用到墙壁的角度
        if self.owner is not None:
            self.owner.angle = self.tilt_angle

    def _compute_torque(self):
        """
        计算棍子对墙壁产生的力矩。

        公式:
          torque = offset × stick_weight × torque_scale

        其中:
          offset = anchor_local_pos.x / (wall.length/2)
                   归一化到 [-1, 1]，1 = 抓在最右端
          stick_weight = stick.total_mass × 9.8

        力矩为正 → 顺时针倾斜
        力矩为负 → 逆时针倾斜
        """
        if self.attached_stick is None or self.anchor_local_pos is None:
            return 0.0
        if self.owner is None:
            return 0.0

        # 力臂偏移（归一化）
        half = self.owner.length / 2
        offset = clamp(
            self.anchor_local_pos.x / max(half, 0.0001),
            -1.0, 1.0  # 夹在 [-1, 1]
        )

        # 棍子重量
        weight = getattr(self.attached_stick, 'total_mass', 1.0) * 9.8

        # 力矩
        torque = offset * weight * self.torque_scale

        # 方向限制
        if self.tilt_direction == "clockwise":
            return max(0.0, torque)   # 只允许顺时针（正值）
        elif self.tilt_direction == "counter_clockwise":
            return min(0.0, torque)   # 只允许逆时针（负值）
        return torque  # both: 两个方向都允许


# ================================================================
#  节拍式虚实切换组件
# ================================================================

class BeatSolidSwitchComponent(WallComponent):
    """
    节拍式实体 / 虚体切换组件。

    让墙壁按照固定周期在实体墙和虚体墙之间切换。

    配置项
    ----
    switchSecond : float
        每隔多少秒切换一次（推荐 ≥1.0）。
    switchScend : float
        兼容错误拼写。如果没配置 switchSecond 则读此项。
    initial_delay : float
        初始延迟多少秒后开始切换。
    start_solid : bool | None
        初始实体状态。None=不强制，True=初始实体，False=初始虚体。

    注意：如果墙壁 solid_locked=True，本组件不再切换。
    """

    def __init__(self, cfg=None):
        super().__init__()
        cfg = cfg or {}

        self.switchSecond = float(
            cfg.get("switchSecond", cfg.get("switchScend", 1.0))
        )
        self.initial_delay = float(cfg.get("initial_delay", 0.0))
        self.start_solid = cfg.get("start_solid", None)

        self.timer = 0.0
        self.started = False

    def update(self, dt):
        if self.owner is None:
            return
        if not self.owner.active:
            return
        if self.owner.solid_locked:
            return

        if not self.started:
            self.started = True
            if self.start_solid is not None:
                self.owner.setSolid(bool(self.start_solid), locked=False)

        self.timer += dt

        # 初始延迟阶段
        if self.initial_delay > 0:
            if self.timer < self.initial_delay:
                return
            self.timer = 0.0
            self.initial_delay = 0.0

        # 周期切换
        if self.timer >= self.switchSecond:
            self.timer -= self.switchSecond
            self.owner.switchSolid()


# ================================================================
#  钥匙配对虚实切换组件
# ================================================================

class KeyPairSolidComponent(WallComponent):
    """
    钥匙配对实体 / 虚体切换组件。

    墙壁绑定一个 key_pair_id。当对应钥匙被收集后，
    调用 on_key_collected() 永久切换墙壁虚实状态。

    配置项
    ----
    key_pair_id : str
        绑定的钥匙 ID
    key_pair_result : str
        "solid" → 永久变实体
        "ghost" → 永久变虚体
        "toggle" → 切换一次后永久锁定

    运行时状态
    ----
    triggered : bool
        是否已被触发（只触发一次）
    """

    def __init__(self, cfg=None):
        super().__init__()
        cfg = cfg or {}

        self.key_pair_id = cfg.get("key_pair_id", "")
        self.key_pair_result = cfg.get("key_pair_result", "solid")
        self.triggered = False

    def on_key_collected(self):
        """对应钥匙被收集时调用。"""
        if self.owner is None:
            return
        if self.triggered:
            return
        self.triggered = True

        if self.key_pair_result == "solid":
            self.owner.setSolid(True, locked=True)
        elif self.key_pair_result == "ghost":
            self.owner.setSolid(False, locked=True)
        elif self.key_pair_result == "toggle":
            self.owner.solid_locked = False
            self.owner.switchSolid()
            self.owner.solid_locked = True
        else:
            self.owner.setSolid(True, locked=True)


# ================================================================
#  贴图加载辅助
# ================================================================

# 自定义贴图缓存 — {wall_id: (path, Surface)}，path 变了重新加载
_custom_img_cache = {}


def _try_load_image(path):
    """
    加载贴图。从项目根的 arts/ 搜索，兼容 Tiled 存储的旧路径。
    先按文件名精确匹配，失败则按文件名关键词模糊匹配（处理文件改名）。
    """
    import os as _os
    if not path:
        return None

    # 剥离所有路径前缀，只取文件名
    filename = _os.path.basename(path)
    if not filename:
        return None

    from data_config import get_path
    arts_dir = get_path("arts")

    def _search_and_load(target_name):
        if not _os.path.isdir(arts_dir):
            return None
        for root, _dirs, files in _os.walk(arts_dir):
            if target_name in files:
                try:
                    return pygame.image.load(
                        _os.path.join(root, target_name)).convert_alpha()
                except Exception:
                    continue
        return None

    # 1. 精确文件名匹配
    result = _search_and_load(filename)
    if result:
        return result

    # 2. 模糊匹配：文件名关键词（如 checkpoint.png → checkpoint未激活.png）
    stem = _os.path.splitext(filename)[0].lower()
    if _os.path.isdir(arts_dir):
        for root, _dirs, files in _os.walk(arts_dir):
            for f in files:
                f_stem = _os.path.splitext(f)[0].lower()
                if stem in f_stem or f_stem in stem:
                    try:
                        return pygame.image.load(
                            _os.path.join(root, f)).convert_alpha()
                    except Exception:
                        continue

    # 设计师未自定义贴图 → 返回 None，draw() 用默认贴图
    return None


# ================================================================
#  组件工厂
# ================================================================

def create_component(name, cfg=None):
    """
    按名称创建墙壁组件。

    参数
    ----
    name : str
        组件名: "fragile" | "goal" | "moving" | "unstable"
    cfg : dict | None
        组件配置字典，不同的组件有不同的配置项。

    返回
    ----
    WallComponent 子类实例

    示例::
        # 脆弱组件
        create_component("fragile")
        create_component("fragile", {"break_on_detach": False})

        # 终点组件
        create_component("goal")

        # 移动组件（循环）
        create_component("moving", {
            "strategy": "loop", "speed": 80,
            "path": [[0,0], [200,0]]
        })

        # 移动组件（来回）
        create_component("moving", {
            "strategy": "pingpong", "speed": 60,
            "path": [[320,560], [480,560], [480,420]]
        })

        # 不稳定组件
        create_component("unstable", {
            "max_tilt_angle": 45, "inertia": 90,
            "torque_scale": 1.5, "break_at_max_tilt": True
        })
    """
    cfg = cfg or {}

    if name == "fragile":
        return FragileComponent(cfg.get("break_on_detach", True))

    if name == "goal":
        return GoalComponent()

    if name == "moving":
        strategy_type = cfg.get("strategy", "pingpong")
        speed = cfg.get("speed", 80)
        abs_path = cfg.get("path", [])  # path[0]=墙壁中心, path[1..n]=绝对目标位置

        if strategy_type == "once":
            return MovingComponent(OneShotMoveStrategy(abs_path, speed))
        else:
            return MovingComponent(PingPongMoveStrategy(abs_path, speed))

    if name == "unstable":
        return UnstableComponent(cfg)

    if name == "beat_solid_switch":
        return BeatSolidSwitchComponent(cfg)

    if name == "key_pair_solid":
        return KeyPairSolidComponent(cfg)

    raise ValueError(f"Unknown wall component: {name}")


# ================================================================
#  Wall 墙壁实体
# ================================================================

class Wall:
    """
    墙壁实体 — 统一墙壁系统。

    ======  坐标系  ======

    墙壁使用左上角 (x, y) + (width, height) 定义矩形区域。
    也提供中心坐标和尺寸的别名:
      wall.position  → 墙壁中心 (Vector2)
      wall.length    → width 别名
      wall.thickness → height 别名

    ======  墙壁类型  ======

    wall_type 决定了碰撞返回值和默认外观:
      "normal"  普通墙壁 — 抓住后稳定锚定
      "fragile" 脆弱墙壁 — 抓住后锚定，离开后碎裂
      "goal"    终点墙壁 — 抓住即通关

    ======  组件系统  ======

    通过 add_component() 给墙壁添加能力:
      wall.add_component("fragile", create_component("fragile"))
      wall.add_component("moving",  create_component("moving", {...}))
      wall.add_component("unstable", create_component("unstable", {...}))

    组件间通过 component.owner 访问墙壁，通过 has_component() 查询能力。

    ======  渲染  ======

    draw() 方法支持任意尺寸的墙壁。贴图会被平铺 (tile) 覆盖
    整个矩形区域，而不是只画一次。这意味着:
      - 32×32 的墙: 贴图放一次
      - 192×32 的墙: 贴图水平重复 6 次
      - 64×64 的墙: 贴图 2×2 平铺

    终点墙壁还会画金色发光边框动画。

    ======  碰撞检测  ======

    contains_point(px, py, radius):
      先找到矩形内离点最近的位置 (cx, cy)，
      再判断点与 (cx, cy) 的距离是否 ≤ radius + 2。
      这相当于把矩形膨胀了 radius 像素后的圆角矩形碰撞。

    clamp_point(px, py):
      将点夹在矩形内部，缩进 1px。
      保证返回的锚点一定在墙壁内部。
    """

    # __slots__ 减少内存开销，每个 Wall 实例只有这些属性
    __slots__ = (
        'id', 'x', 'y', 'width', 'height', 'wall_type',
        'angle', 'active', 'prefab',

        # 自定义外观贴图（设计师在 Tiled 中通过 file 选择器指定）
        'appearance_solid',   # 实线墙贴图（isSolid=True）
        'appearance_ghost',   # 虚线墙贴图（isSolid=False）

        # 是否是实体墙。
        # True  = 实线墙，可以被棍子抓住。
        # False = 虚线墙，不能被棍子抓住。
        'isSolid',

        # 是否已经永久锁定实体状态。
        # 例如 key_pair 钥匙触发后，墙永久变成实体/虚体。
        # 此时 BeatSolidSwitchComponent 不再切换它。
        'solid_locked',

        'components', '_rect_cache', '_rect_dirty',
    )

    def __init__(self, x, y, width, height, wall_type="normal", wall_id=None,
                 isSolid=True):
        """
        创建墙壁。

        参数
        ----
        x, y : float
            墙壁左上角在世界坐标中的位置（像素）
        width, height : float
            墙壁的宽度和高度（像素）
        wall_type : str
            墙壁类型: "normal" | "fragile" | "goal"
        wall_id : str | None
            墙壁唯一标识，不传则自动生成 "wall_<memory_id>"
        isSolid : bool
            是否是实体墙。True=实线墙可抓，False=虚线墙不可抓。
        """
        # ---- 标识 ----
        self.id = wall_id or f"wall_{id(self)}"

        # ---- 位置和尺寸 ----
        self.x = float(x)
        self.y = float(y)
        self.width = float(width)
        self.height = float(height)

        # ---- 类型 ----
        # "normal" | "fragile" | "goal"
        self.wall_type = wall_type

        # ---- 旋转（弧度） ----
        # 由 UnstableComponent 或 MovingComponent 修改
        self.angle = 0.0

        # ---- 状态 ----
        # break_wall() 将 active 设为 False
        self.active = True

        # ---- 实线 / 虚线状态 ----
        # isSolid=True  → 实线墙，可以被棍子抓住
        # isSolid=False → 虚线墙，不能被棍子抓住
        self.isSolid = bool(isSolid)

        # ---- 锁定状态 ----
        # solid_locked=True 表示墙壁状态被永久锁定
        # 此时节拍式切换组件不再改变它
        self.solid_locked = False

        # ---- 外观 ----
        # 贴图路径（可选）— 设计师在 Tiled 中通过 file 选择器指定
        self.appearance_solid = ""   # 实线墙贴图路径（isSolid=True 时使用）
        self.appearance_ghost = ""   # 虚线墙贴图路径（isSolid=False 时使用）
        # 预制体名（如 "normal_wall"）
        self.prefab = f"{wall_type}_wall"

        # ---- 组件 ----
        # 字典: {"fragile": FragileComponent, "moving": MovingComponent, ...}
        self.components = {}

        # ---- Rect 缓存 ----
        # 避免每帧创建 pygame.Rect 对象
        self._rect_cache = None
        self._rect_dirty = True

    # ============================================================
    #  属性 (Properties)
    # ============================================================

    @property
    def length(self):
        """墙壁长度（width 别名，语义更清晰）"""
        return self.width

    @property
    def thickness(self):
        """墙壁厚度（height 别名，语义更清晰）"""
        return self.height

    @property
    def position(self):
        """
        墙壁中心的世界坐标。

        Returns
        -------
        Vector2
            (x + width/2, y + height/2)
        """
        return Vector2(self.x + self.width / 2, self.y + self.height / 2)

    @property
    def rect(self):
        """
        墙壁的 pygame.Rect（带缓存）。

        只在墙壁位置/尺寸变化时重新创建。
        由 update() 标记 _rect_dirty = True 触发重建。
        """
        if self._rect_dirty:
            self._rect_cache = pygame.Rect(
                int(self.x), int(self.y),
                int(self.width), int(self.height)
            )
            self._rect_dirty = False
        return self._rect_cache

    # ============================================================
    #  组件管理
    # ============================================================

    def add_component(self, name, component):
        """
        添加组件，自动设置 component.owner = self。

        示例::
            wall.add_component("fragile", FragileComponent())
            wall.add_component("unstable", UnstableComponent({"max_tilt_angle": 45}))
        """
        self.components[name] = component
        component.owner = self  # 反向引用，让组件能访问墙壁

    def has_component(self, name):
        """
        检查是否有某个组件。

        示例::
            if wall.has_component("goal"):
                print("这面墙是终点!")
        """
        return name in self.components

    def get_component(self, name):
        """
        获取组件，不存在返回 None。

        示例::
            moving = wall.get_component("moving")
            if moving:
                moving.move_strategy.move_speed = 120
        """
        return self.components.get(name)

    # ============================================================
    #  生命周期
    # ============================================================

    def update(self, dt):
        """
        每帧更新。标记 rect 缓存为脏，然后更新所有组件。

        调用顺序:
          1. 标记 _rect_dirty（位置可能被组件改变）
          2. 遍历所有组件的 update(dt)
        """
        if not self.active:
            return
        self._rect_dirty = True  # 组件可能改变了位置/角度
        for comp in self.components.values():
            comp.update(dt)

    def on_anchor_attached(self, stick, world_pos):
        """
        棍子锚点抓住此墙时调用。
        通知所有组件: on_anchor_attached(stick, world_pos)

        参数
        ----
        stick : Stick
            抓住墙壁的棍子
        world_pos : (float, float)
            锚点在世界坐标中的位置
        """
        for comp in self.components.values():
            comp.on_anchor_attached(stick, world_pos)

    def on_anchor_detached(self, stick):
        """
        棍子锚点离开此墙时调用。
        通知所有组件: on_anchor_detached(stick)

        参数
        ----
        stick : Stick
            离开墙壁的棍子
        """
        for comp in self.components.values():
            comp.on_anchor_detached(stick)

    def break_wall(self):
        """
        墙壁碎裂。设置 active = False，并强制所有抓在此墙上的棍子脱锚。

        由以下情况触发:
          - FragileComponent: 棍子离开后自动碎裂
          - UnstableComponent: 倾斜超过最大角且 break_at_max_tilt=True
          - 外部调用: wall.break_wall()
        """
        if not self.active:
            return
        self.active = False

        # 事件：墙壁碎裂 → 音效 + 粒子
        from core.event_bus import event_bus
        event_bus.emit("wall_break", {"position": (self.x + self.width/2, self.y + self.height/2)})

        # 通知所有组件中抓着此墙的棍子强制脱锚
        for comp in self.components.values():
            if hasattr(comp, "attached_stick") and comp.attached_stick is not None:
                comp.attached_stick.force_detach()

    # ============================================================
    #  实线 / 虚线切换
    # ============================================================

    def switchSolid(self):
        """
        切换墙壁的实体 / 虚体状态。

        实体墙 → 虚体墙
        虚体墙 → 实体墙

        注意：
        - active=False（已碎裂）的墙不切换
        - solid_locked=True（被钥匙永久锁定）的墙不切换
        """
        if not self.active:
            return
        if self.solid_locked:
            return
        self.isSolid = not self.isSolid

    def setSolid(self, value, locked=False):
        """
        直接设置墙壁为实体墙或虚体墙。

        参数
        ----
        value : bool
            True=实体墙可抓，False=虚体墙不可抓
        locked : bool
            是否永久锁定该状态。锁定后 BeatSolidSwitchComponent 不再切换。
        """
        if not self.active:
            return
        self.isSolid = bool(value)
        if locked:
            self.solid_locked = True

    # ============================================================
    #  碰撞检测
    # ============================================================

    def contains_point(self, px, py, radius=0):
        """
        检查点 (px, py) 是否可以被锚定在此墙壁上。

        仅在以下条件全部满足时返回 True:
          1. 墙壁 active=True（未碎裂）
          2. 墙壁 isSolid=True（实线墙）
          3. 点在墙壁矩形范围内（含半径容差）

        虚线墙 (isSolid=False) 不能被抓住。

        参数
        ----
        px, py : float
            世界坐标中的点
        radius : float
            容差半径（像素），默认为 0。
            传入棍子端点半径可以实现"端点碰到墙壁边缘也视为抓住"。

        返回
        ----
        bool
        """
        if not self.active:
            return False
        if not self.isSolid:
            return False

        r = self.rect
        # 将点夹到矩形边界内
        cx = clamp(px, r.left, r.right)
        cy = clamp(py, r.top, r.bottom)
        # 欧几里得距离 ≤ 半径容差 + 2px 固定容差
        return math.sqrt((px - cx) ** 2 + (py - cy) ** 2) <= radius + 2

    def clamp_point(self, px, py):
        """
        将点 (px, py) 夹在墙壁内部，返回夹紧后的坐标。

        用于计算锚点位置: 棍子端点可能在墙壁外面，但锚点必须在墙壁内部。

        参数
        ----
        px, py : float
            输入点坐标

        返回
        ----
        (float, float)
            夹紧后的坐标，保证在 rect 内部且距边缘 ≥ 1px
        """
        r = self.rect
        return (
            clamp(px, r.left + 1, r.right - 1),
            clamp(py, r.top + 1, r.bottom - 1),
        )

    # ============================================================
    #  坐标转换（支持旋转）
    # ============================================================

    def world_to_local(self, point):
        """
        世界坐标 → 墙壁局部坐标。

        局部坐标系以墙壁中心为原点，x 轴沿墙壁长度方向。
        如果墙壁有旋转（angle ≠ 0），会自动应用逆旋转。

        用途: UnstableComponent 需要知道锚点在墙上的局部位置，
        以计算力臂长度。

        参数
        ----
        point : (float, float) | Vector2
            世界坐标中的点

        返回
        ----
        Vector2
            墙壁局部坐标
        """
        # 解析输入
        px, py = (point.x, point.y) if hasattr(point, 'x') else (point[0], point[1])
        # 相对中心偏移
        cx, cy = self.x + self.width / 2, self.y + self.height / 2
        dx, dy = px - cx, py - cy
        # 逆旋转（世界 → 局部）
        if self.angle != 0:
            cos_a, sin_a = math.cos(-self.angle), math.sin(-self.angle)
            return Vector2(
                dx * cos_a - dy * sin_a,
                dx * sin_a + dy * cos_a
            )
        return Vector2(dx, dy)

    def local_to_world(self, local):
        """
        墙壁局部坐标 → 世界坐标。

        用途: 将锚点在墙壁上的局部位置转回世界坐标，
        以计算锚定状态下棍子的位置。

        参数
        ----
        local : Vector2
            墙壁局部坐标

        返回
        ----
        Vector2
            世界坐标
        """
        cx, cy = self.x + self.width / 2, self.y + self.height / 2
        if self.angle != 0:
            # 正向旋转（局部 → 世界）
            cos_a, sin_a = math.cos(self.angle), math.sin(self.angle)
            wx = local.x * cos_a - local.y * sin_a
            wy = local.x * sin_a + local.y * cos_a
            return Vector2(cx + wx, cy + wy)
        return Vector2(cx + local.x, cy + local.y)

    # ============================================================
    #  渲染
    # ============================================================

    def draw(self, screen, camera_y, images, tile_size=32):
        """
        绘制墙壁 — 贴图平铺覆盖整个矩形区域。

        与旧实现（只画一次 32×32）不同，本方法将贴图在矩形内
        重复平铺，确保任意尺寸的墙壁都能正确显示。

        流程:
          1. 视野裁剪（完全在屏幕外的墙壁不画）
          2. 如果有贴图: 以贴图尺寸为步长，水平+垂直平铺
          3. 如果无贴图: 用纯色填充 + 边框

        终点墙壁额外绘制金色发光边框动画。

        参数
        ----
        screen : pygame.Surface
            渲染目标
        camera_y : float
            相机 Y 偏移（世界坐标），用于 world → screen 转换
        images : dict
            贴图字典，key 如 "normal_wall", "fragile_wall", "goal_wall"
        tile_size : int
            默认贴图大小（不参与平铺步长，仅作保留参数）
        """
        if not self.active:
            return

        # === 虚线墙：半透明虚线绘制 ===
        if not self.isSolid:
            self._draw_ghost_wall(screen, camera_y, images)
            return

        # wall_type → image key（设计师未自定义时使用默认贴图）
        _default_imgs = {
            "normal": "normal_wall",
            "fragile": "fragile_wall",
            "goal": "goal_wall",
        }
        img = images.get(_default_imgs.get(self.wall_type, "normal_wall"))

        # 世界坐标 → 屏幕坐标
        sx = int(self.x)
        sy = int(self.y - camera_y)
        w, h = int(self.width), int(self.height)

        # 视野裁剪: 完全在屏幕外就不画
        screen_h = screen.get_height()
        if sy + h < 0 or sy > screen_h:
            return

        # 优先使用设计师自定义贴图（Tiled image_solid 属性）
        custom_img = None
        if self.appearance_solid:
            cached = _custom_img_cache.get(self.id)
            if cached is not None and cached[0] == self.appearance_solid:
                custom_img = cached[1]
            else:
                custom_img = _try_load_image(self.appearance_solid)
                if custom_img:
                    _custom_img_cache[self.id] = (self.appearance_solid, custom_img)

        draw_img = custom_img or img
        if draw_img:
            # === 贴图平铺 ===
            iw, ih = draw_img.get_width(), draw_img.get_height()
            for tx in range(sx, sx + w, iw):
                for ty in range(sy, sy + h, ih):
                    screen.blit(draw_img, (tx, ty))
        else:
            # === 纯色兜底 ===
            colors = {
                "normal": (100, 85, 70),   # 棕色
                "fragile": (130, 120, 110), # 浅灰棕
                "goal": (180, 150, 40),     # 金色
            }
            pygame.draw.rect(screen, colors.get(self.wall_type, (100, 100, 100)),
                             (sx, sy, w, h))
            pygame.draw.rect(screen, (60, 50, 40), (sx, sy, w, h), 1)

        # === 终点墙壁发光动画 ===
        if self.wall_type == "goal":
            # 发光强度随时间正弦波动
            import math as _m
            glow_alpha = int(60 + 40 * _m.sin(pygame.time.get_ticks() / 1000.0 * 3))
            glow = pygame.Surface((w + 8, h + 8), pygame.SRCALPHA)
            glow.fill((255, 220, 60, glow_alpha))  # 金色半透明
            screen.blit(glow, (sx - 4, sy - 4))

    def _draw_ghost_wall(self, screen, camera_y, images=None):
        """
        绘制虚线墙 / 虚体墙。

        特点：
        - 仍然显示在地图中
        - 不能被棍子抓住
        - 若有自定义 ghost 贴图，使用半透明贴图；否则淡蓝填充 + 虚线边框
        """
        sx = int(self.x)
        sy = int(self.y - camera_y)
        w = int(self.width)
        h = int(self.height)

        screen_h = screen.get_height()
        if sy + h < 0 or sy > screen_h:
            return

        # 优先使用设计师自定义 ghost 贴图
        ghost_img = None
        if self.appearance_ghost and images is not None:
            cache_key = f"_ghost_{self.id}"
            cached = _custom_img_cache.get(cache_key)
            if cached is not None and cached[0] == self.appearance_ghost:
                ghost_img = cached[1]
            else:
                ghost_img = _try_load_image(self.appearance_ghost)
                if ghost_img:
                    _custom_img_cache[cache_key] = (self.appearance_ghost, ghost_img)

        if ghost_img:
            # 半透明平铺自定义贴图
            ghost_surf = pygame.Surface((w, h), pygame.SRCALPHA)
            iw, ih = ghost_img.get_width(), ghost_img.get_height()
            for tx in range(0, w, iw):
                for ty in range(0, h, ih):
                    ghost_surf.blit(ghost_img, (tx, ty))
            ghost_surf.set_alpha(128)  # 透明度 0.5
            screen.blit(ghost_surf, (sx, sy))
            # 仍画虚线边框
            color = (150, 210, 255, 140)
            dash = 8; gap = 6
            x = sx
            while x < sx + w:
                end_x = min(x + dash, sx + w)
                pygame.draw.line(screen, color, (x, sy), (end_x, sy), 2)
                pygame.draw.line(screen, color, (x, sy + h), (end_x, sy + h), 2)
                x += dash + gap
            y = sy
            while y < sy + h:
                end_y = min(y + dash, sy + h)
                pygame.draw.line(screen, color, (sx, y), (sx, end_y), 2)
                pygame.draw.line(screen, color, (sx + w, y), (sx + w, end_y), 2)
                y += dash + gap
            return

        # 兜底：淡蓝色半透明填充 + 虚线边框
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        surf.fill((120, 180, 255, 128))  # 透明度 0.5
        screen.blit(surf, (sx, sy))

        color = (150, 210, 255, 140)
        dash = 8
        gap = 6

        x = sx
        while x < sx + w:
            end_x = min(x + dash, sx + w)
            pygame.draw.line(screen, color, (x, sy), (end_x, sy), 2)
            pygame.draw.line(screen, color, (x, sy + h), (end_x, sy + h), 2)
            x += dash + gap

        y = sy
        while y < sy + h:
            end_y = min(y + dash, sy + h)
            pygame.draw.line(screen, color, (sx, y), (sx, end_y), 2)
            pygame.draw.line(screen, color, (sx + w, y), (sx + w, end_y), 2)
            y += dash + gap

    def __repr__(self):
        """调试用字符串表示"""
        comps = ",".join(self.components.keys()) if self.components else "-"
        return (
            f"Wall({self.id}, {self.wall_type}, "
            f"{int(self.width)}x{int(self.height)} "
            f"@ ({int(self.x)},{int(self.y)}), "
            f"[{comps}])"
        )
