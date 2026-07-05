"""
systems/camera.py
平滑跟随相机系统 — 死区 + 海上漂浮晃动
"""

import random
import math
from data_config import SCREEN_HEIGHT, CAMERA_VIEW_RATIO


# ================================================================
#  工具函数
# ================================================================

def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def smoothstep(x):
    x = clamp(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


# ================================================================
#  Camera
# ================================================================

class Camera:
    """平滑跟随相机 + 海上漂浮偏移"""

    def __init__(self, y, map_height, dead_zone=80):
        self.y = y
        self.target_y = y
        self.map_height = map_height
        self.smooth_speed = 5.0
        self.dead_zone = dead_zone
        self.bob_x = 0.0
        self.bob_y = 0.0

    def set_target(self, follow_y):
        """玩家在屏幕 CAMERA_VIEW_RATIO 处（0.6=偏下，上方留60%空间）"""
        ideal = follow_y - SCREEN_HEIGHT * CAMERA_VIEW_RATIO
        max_y = max(0, self.map_height - SCREEN_HEIGHT)
        ideal = max(0.0, min(ideal, max_y))
        if abs(ideal - self.target_y) > self.dead_zone:
            self.target_y = ideal

    def update(self, dt):
        diff = self.target_y - self.y
        self.y += diff * min(1.0, self.smooth_speed * dt)

    def apply_shake(self, amount=5):
        self.y += random.uniform(-amount, amount)

    def world_to_screen(self, world_x, world_y):
        return (int(world_x + self.bob_x), int(world_y - self.y + self.bob_y))


# ================================================================
#  SeaCameraBob — 海上漂浮参数（全部可调参数放在最前面）
# ================================================================

class SeaCameraBob:
    """
    海上漂浮摄像机偏移。
    横向始终固定晃动；纵向离海浪越近晃动越强越快。

    每个正弦波参数说明：
      (权重大小, 频率Hz, 初始相位弧度)
      - 权重大小: 这个波对最终晃动的贡献比例，越大越明显
      - 频率Hz:   每秒振动次数，越大越快。0.10≈10秒一圈，0.50≈2秒一圈
      - 相位:     波从哪个弧度开始，让多层波错开，避免机械重复
    """

    # ═══════════════════════════════════════════════════════════════
    #  横向波 X1 — 主横摆（最主要的大幅慢速左右漂移）
    #  周期约 10 秒，决定漂浮的基本节奏
    # ═══════════════════════════════════════════════════════════════
    X1_WEIGHT = 1.00   # 权重大小
    X1_FREQ   = 0.10   # 频率 Hz
    X1_PHASE  = 0.0    # 初始相位弧度

    # ═══════════════════════════════════════════════════════════════
    #  横向波 X2 — 副横摆（中速变化，让漂浮不单调）
    #  周期约 5.9 秒
    # ═══════════════════════════════════════════════════════════════
    X2_WEIGHT = 0.45
    X2_FREQ   = 0.17
    X2_PHASE  = 1.7

    # ═══════════════════════════════════════════════════════════════
    #  横向波 X3 — 超慢变化（让晃动长期不完全重复）
    #  周期约 32 秒
    # ═══════════════════════════════════════════════════════════════
    X3_WEIGHT = 0.25
    X3_FREQ   = 0.031
    X3_PHASE  = 4.2

    # ═══════════════════════════════════════════════════════════════
    #  横向波 X4 — 细小快波（增加轻微颠簸感）
    #  周期约 4.3 秒
    # ═══════════════════════════════════════════════════════════════
    X4_WEIGHT = 0.15
    X4_FREQ   = 0.23
    X4_PHASE  = 2.4

    # ═══════════════════════════════════════════════════════════════
    #  纵向波 Y1 — 主纵摆（主要的上下浮动）
    #  基础周期约 6.25 秒，靠近海浪时会加速
    # ═══════════════════════════════════════════════════════════════
    Y1_WEIGHT = 1.00
    Y1_FREQ   = 0.16
    Y1_PHASE  = 0.8

    # ═══════════════════════════════════════════════════════════════
    #  纵向波 Y2 — 中速纵摆（让上下漂浮更自然）
    #  基础周期约 3.45 秒
    # ═══════════════════════════════════════════════════════════════
    Y2_WEIGHT = 0.50
    Y2_FREQ   = 0.29
    Y2_PHASE  = 2.1

    # ═══════════════════════════════════════════════════════════════
    #  纵向波 Y3 — 快速细波（靠近海浪时最明显）
    #  基础周期约 2.33 秒
    # ═══════════════════════════════════════════════════════════════
    Y3_WEIGHT = 0.25
    Y3_FREQ   = 0.43
    Y3_PHASE  = 4.6

    # ═══════════════════════════════════════════════════════════════
    #  幅度参数
    # ═══════════════════════════════════════════════════════════════
    MAX_X_AMP = 40.0   # 横向最大漂移像素（始终生效）
    MAX_Y_AMP = 20.0   # 纵向最大漂移像素（靠近海浪时才达到）

    # ═══════════════════════════════════════════════════════════════
    #  纵向衰减 — 离海浪越远晃动越小
    #  intensity = DECAY ^ d （d=距离海浪的像素数）
    #  DECAY 越小衰减越快，0.998 表示每 100px 减弱约 18%
    # ═══════════════════════════════════════════════════════════════
    DECAY = 0.998   # 衰减系数（0~1，<1 越远越弱）

    # ================================================================
    #  以下为逻辑代码，美术一般不需要修改
    # ================================================================

    def __init__(self):
        self.time = 0.0
        # 从类常量组装波形列表
        self.x_waves = [
            (self.X1_WEIGHT, self.X1_FREQ, self.X1_PHASE),
            (self.X2_WEIGHT, self.X2_FREQ, self.X2_PHASE),
            (self.X3_WEIGHT, self.X3_FREQ, self.X3_PHASE),
            (self.X4_WEIGHT, self.X4_FREQ, self.X4_PHASE),
        ]
        self.y_waves = [
            (self.Y1_WEIGHT, self.Y1_FREQ, self.Y1_PHASE),
            (self.Y2_WEIGHT, self.Y2_FREQ, self.Y2_PHASE),
            (self.Y3_WEIGHT, self.Y3_FREQ, self.Y3_PHASE),
        ]

    def update(self, dt):
        self.time += dt

    def _sum_waves(self, waves, speed_scale=1.0):
        total = 0.0
        weight_sum = 0.0
        for weight, freq, phase in waves:
            total += weight * math.sin(2.0 * math.pi * freq * speed_scale * self.time + phase)
            weight_sum += abs(weight)
        return total / max(weight_sum, 0.0001)

    def get_offset(self, current_height, sea_wave_height):
        d = max(0.0, current_height - sea_wave_height)
        # 衰减：intensity = DECAY ^ d，距离越远越弱
        intensity = self.DECAY ** d

        x_norm = self._sum_waves(self.x_waves, 1.0)
        offset_x = self.MAX_X_AMP * x_norm

        amp_y = self.MAX_Y_AMP * intensity
        speed_y = intensity
        y_norm = self._sum_waves(self.y_waves, speed_y)
        offset_y = amp_y * y_norm

        return offset_x, offset_y
