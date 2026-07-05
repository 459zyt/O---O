"""
systems/camera.py
平滑跟随相机系统 — 带死区（dead zone），避免微小抖动和边界跳变
"""

import random
import math
from data_config import SCREEN_HEIGHT, CAMERA_VIEW_RATIO


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def smoothstep(x):
    x = clamp(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


class Camera:
    """
    平滑跟随相机 + 海上漂浮偏移。
    """

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


class SeaCameraBob:
    """
    海上漂浮摄像机偏移。
    横向始终固定晃动；纵向离海浪越近晃动越强越快。
    """

    def __init__(self):
        self.time = 0.0
        self.x_waves = [
            (1.00, 0.10, 0.0),
            (0.45, 0.17, 1.7),
            (0.25, 0.031, 4.2),
            (0.15, 0.23, 2.4),
        ]
        self.y_waves = [
            (1.00, 0.16, 0.8),
            (0.50, 0.29, 2.1),
            (0.25, 0.43, 4.6),
        ]
        self.max_x_amp = 40.0
        self.max_y_amp = 20.0
        self.vertical_influence_distance = 400.0
        self.y_speed_min = 0.75
        self.y_speed_max = 1.80
        self.y_amp_gamma = 1.3

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
        r = smoothstep(1.0 - d / self.vertical_influence_distance)
        x_norm = self._sum_waves(self.x_waves, 1.0)
        offset_x = self.max_x_amp * x_norm
        amp_y = self.max_y_amp * (r ** self.y_amp_gamma)
        speed_y = self.y_speed_min + (self.y_speed_max - self.y_speed_min) * r
        y_norm = self._sum_waves(self.y_waves, speed_y)
        offset_y = amp_y * y_norm
        return offset_x, offset_y


import math


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def smoothstep(x):
    """
    平滑插值函数。

    作用：
        把 0~1 的线性变化变得更自然。
        用在这里是为了让“离海浪越近越晃”不是突然开始，而是渐渐增强。

    美术一般不需要改这个函数。
    """
    x = clamp(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


class SeaCameraBob:
    """
    海上漂浮摄像机偏移。

    用途：
        给摄像机增加类似“船在海上漂浮”的轻微晃动。

    效果规则：
        1. 横向 X 轴：
            - 始终存在。
            - 最大左右漂移约为 max_x_amp 像素。
            - 波形、频率和相位固定。
            - 用来模拟海面上的横向摇摆。

        2. 纵向 Y 轴：
            - 根据 current_height - sea_wave_height 控制。
            - 离海浪越近，上下晃动越明显。
            - 离海浪越近，上下晃动越快。
            - 最大上下漂移约为 max_y_amp 像素。

    注意：
        这里的 amp 表示“最大视觉偏移幅度”，不是严格统计意义上的方差。
    """

    def __init__(self):
        self.time = 0.0

        # ============================================================
        # 美术可调参数 1：横向海浪波形
        # ============================================================
        #
        # x_waves 控制摄像机左右漂浮的感觉。
        #
        # 每一项格式：
        #     (weight, frequency_hz, phase_rad)
        #
        # 参数说明：
        #
        # weight:
        #     该层波的权重。
        #     越大，这层波对最终横向晃动影响越大。
        #
        # frequency_hz:
        #     频率，单位 Hz，即“每秒振动几次”。
        #     例如：
        #         0.10 表示约 10 秒一个周期。
        #         0.20 表示约 5 秒一个周期。
        #
        #     改大：
        #         左右晃动更快，更紧张。
        #
        #     改小：
        #         左右晃动更慢，更像大船慢慢漂。
        #
        # phase_rad:
        #     相位，单位弧度。
        #     用来错开几层波的起始位置，避免看起来像机械重复。
        #
        #     美术可以改，但一般不用频繁调整。
        #     推荐范围：0.0 ~ 6.28
        #
        # 推荐调法：
        #     如果想更“平稳”：
        #         降低高频波的 weight，例如第三、第四项。
        #
        #     如果想更“海上摇晃明显”：
        #         增大第一项 weight，或者增大 max_x_amp。
        #
        self.x_waves = [
            (1.00, 0.10, 0.0),   # 主横摆：最主要的大幅慢速左右漂移，周期约 10 秒
            (0.45, 0.17, 1.7),   # 副横摆：增加一点中速变化，避免太单调，周期约 5.9 秒
            (0.25, 0.031, 4.2),  # 超慢变化：让整体晃动长期不完全重复，周期约 32 秒
            (0.15, 0.23, 2.4),   # 细小快波：增加轻微颠簸感，周期约 4.3 秒
        ]

        # ============================================================
        # 美术可调参数 2：纵向海浪波形
        # ============================================================
        #
        # y_waves 控制摄像机上下漂浮的感觉。
        #
        # 每一项格式同样是：
        #     (weight, base_frequency_hz, phase_rad)
        #
        # 注意：
        #     这里的 base_frequency_hz 是“基础频率”。
        #     实际频率还会乘以 speed_y。
        #
        # 也就是说：
        #     离海浪越近，speed_y 越大，上下晃动越快。
        #
        # 推荐调法：
        #     如果觉得靠近海浪时太抖：
        #         降低第三项 weight，或者降低 y_speed_max。
        #
        #     如果觉得上下漂浮不明显：
        #         增大 max_y_amp，或者增大第一项 weight。
        #
        self.y_waves = [
            (1.00, 0.16, 0.8),   # 主纵摆：主要的上下浮动，基础周期约 6.25 秒
            (0.50, 0.29, 2.1),   # 中速纵摆：让上下漂浮更自然，基础周期约 3.45 秒
            (0.25, 0.43, 4.6),   # 快速细波：靠近海浪时会更明显，基础周期约 2.33 秒
        ]

        # ============================================================
        # 美术可调参数 3：最大横向漂移幅度
        # ============================================================
        #
        # max_x_amp:
        #     摄像机左右漂移的最大视觉幅度，单位：像素。
        #
        # 当前值：
        #     40.0 表示摄像机最多大约左右偏移 40px。
        #
        # 改大：
        #     海上漂浮感更强，但也更容易让玩家晕。
        #
        # 改小：
        #     画面更稳定，漂浮感更弱。
        #
        # 推荐范围：
        #     轻微漂浮：10 ~ 20
        #     明显海浪：30 ~ 40
        #     强烈风暴：50 ~ 80
        #
        self.max_x_amp = 40.0

        # ============================================================
        # 美术可调参数 4：最大纵向漂移幅度
        # ============================================================
        #
        # max_y_amp:
        #     摄像机上下漂移的最大视觉幅度，单位：像素。
        #
        # 当前值：
        #     20.0 表示靠近海浪时，摄像机最多大约上下偏移 20px。
        #
        # 改大：
        #     靠近海浪时上下颠簸更明显。
        #
        # 改小：
        #     画面更稳。
        #
        # 推荐范围：
        #     轻微：5 ~ 10
        #     标准：15 ~ 20
        #     强烈：25 ~ 40
        #
        self.max_y_amp = 20.0

        # ============================================================
        # 美术可调参数 5：纵向漂浮影响距离
        # ============================================================
        #
        # vertical_influence_distance:
        #     控制玩家/摄像机离海浪多远时，还会受到纵向漂浮影响。
        #
        # 单位：
        #     像素。
        #
        # 当前值：
        #     400.0 表示：
        #         离海浪 400px 以内，纵向漂浮会逐渐增强；
        #         离海浪超过 400px，纵向漂浮基本消失。
        #
        # 改大：
        #     玩家离海浪较远时也会感觉到上下漂浮。
        #     适合大海浪、风暴关卡。
        #
        # 改小：
        #     只有靠近海浪时才明显上下漂浮。
        #     适合普通关卡。
        #
        # 推荐范围：
        #     普通：250 ~ 400
        #     明显压迫：400 ~ 700
        #     风暴/海啸：700 ~ 1000
        #
        self.vertical_influence_distance = 400.0

        # ============================================================
        # 美术可调参数 6：远离海浪时的纵向速度倍率
        # ============================================================
        #
        # y_speed_min:
        #     当玩家离海浪很远时，纵向上下漂浮的速度倍率。
        #
        # 当前值：
        #     0.75 表示远处上下漂浮速度为基础速度的 75%。
        #
        # 改大：
        #     远离海浪时也有较明显的上下浮动速度。
        #
        # 改小：
        #     远离海浪时更平稳。
        #
        # 推荐范围：
        #     0.3 ~ 1.0
        #
        self.y_speed_min = 0.75

        # ============================================================
        # 美术可调参数 7：靠近海浪时的纵向速度倍率
        # ============================================================
        #
        # y_speed_max:
        #     当玩家非常靠近海浪时，纵向上下漂浮的速度倍率。
        #
        # 当前值：
        #     1.80 表示靠近海浪时，上下漂浮速度为基础速度的 180%。
        #
        # 改大：
        #     靠近海浪时抖动更快，更紧张。
        #
        # 改小：
        #     靠近海浪时仍然比较平稳。
        #
        # 推荐范围：
        #     平静海面：1.0 ~ 1.4
        #     普通海浪：1.5 ~ 2.0
        #     风暴海浪：2.0 ~ 3.0
        #
        # 注意：
        #     太大容易让画面变得烦躁，不建议超过 3.0。
        #
        self.y_speed_max = 1.80

        # ============================================================
        # 美术可调参数 8：纵向幅度衰减曲线
        # ============================================================
        #
        # y_amp_gamma:
        #     控制纵向漂浮幅度随距离变化的曲线。
        #
        # 公式大致是：
        #     amp_y = max_y_amp * r ** y_amp_gamma
        #
        # 其中：
        #     r = 0 表示离海浪很远
        #     r = 1 表示非常靠近海浪
        #
        # 改大：
        #     远处更稳定，只有非常靠近海浪才明显上下晃。
        #
        # 改小：
        #     中远距离也会更早出现上下晃动。
        #
        # 推荐值：
        #     0.7 ~ 1.0：
        #         纵向晃动出现得早，压迫感强。
        #
        #     1.2 ~ 1.5：
        #         自然海面漂浮，推荐默认。
        #
        #     2.0 以上：
        #         只有贴近海浪才明显晃。
        #
        self.y_amp_gamma = 1.3

    def update(self, dt):
        """
        更新时间。

        参数：
            dt:
                每帧经过的时间，单位：秒。

        美术一般不需要改这里。
        """
        self.time += dt

    def _sum_waves(self, waves, speed_scale=1.0):
        """
        把多层正弦波叠加起来。

        参数：
            waves:
                波形参数列表。
                每项为：
                    (weight, frequency_hz, phase_rad)

            speed_scale:
                速度倍率。
                横向通常固定为 1.0。
                纵向会根据离海浪距离变化。

        返回：
            一个大约在 -1 到 1 之间变化的数。

        美术一般只需要改 __init__ 里的参数，不需要改这里。
        """
        total = 0.0
        weight_sum = 0.0

        for weight, freq, phase in waves:
            total += weight * math.sin(
                2.0 * math.pi * freq * speed_scale * self.time + phase
            )
            weight_sum += abs(weight)

        if weight_sum <= 0.0001:
            return 0.0

        # 归一化到大约 [-1, 1]。
        # 这样 max_x_amp / max_y_amp 可以比较直观地理解为“最大偏移像素”。
        return total / weight_sum

    def get_offset(self, current_height, sea_wave_height):
        """
        计算当前摄像机海浪漂浮偏移。

        参数：
            current_height:
                当前玩家或摄像机的高度位置。
                通常可以传 player.y 或 camera.y。

            sea_wave_height:
                当前海浪高度。
                通常可以传 lava.y、sea.y 或 wave_surface_y。

        返回：
            (offset_x, offset_y)

            offset_x:
                摄像机横向偏移。
                加到基础 camera.x 上。

            offset_y:
                摄像机纵向偏移。
                加到基础 camera.y 上。

        用法示例：
            bob_x, bob_y = sea_camera_bob.get_offset(player.y, sea.y)
            camera.x = base_camera_x + bob_x
            camera.y = base_camera_y + bob_y
        """

        # ============================================================
        # 距离海浪高度
        # ============================================================
        #
        # d 表示当前高度和海浪高度之间的距离。
        #
        # 当前写法：
        #     d = current_height - sea_wave_height
        #
        # 如果你的游戏坐标系是 pygame 默认坐标：
        #     y 越大越靠下。
        #
        # 如果发现效果反了，例如：
        #     离海浪越远反而越晃，
        # 可以把这里改成：
        #     d = sea_wave_height - current_height
        #
        # 或者直接使用绝对距离：
        #     d = abs(current_height - sea_wave_height)
        #
        d = current_height - sea_wave_height

        # 如果 d 为负，说明已经低于或进入海浪影响区。
        # 这里直接视为距离为 0，也就是最强影响。
        d = max(0.0, d)

        # ============================================================
        # 距离影响因子 r
        # ============================================================
        #
        # r 的意义：
        #     r = 0.0  → 离海浪很远，纵向漂浮几乎没有
        #     r = 1.0  → 非常靠近海浪，纵向漂浮最强
        #
        # vertical_influence_distance 越大，r 衰减越慢。
        #
        r = 1.0 - d / self.vertical_influence_distance
        r = smoothstep(r)

        # ============================================================
        # 横向固定漂移
        # ============================================================
        #
        # 横向不受海浪距离影响，始终使用固定幅度和固定速度。
        #
        x_norm = self._sum_waves(self.x_waves, speed_scale=1.0)
        offset_x = self.max_x_amp * x_norm

        # ============================================================
        # 纵向距离相关漂移
        # ============================================================
        #
        # amp_y:
        #     当前纵向最大漂移幅度。
        #     离海浪越近，amp_y 越接近 max_y_amp。
        #
        # speed_y:
        #     当前纵向波动速度倍率。
        #     离海浪越近，speed_y 越接近 y_speed_max。
        #
        amp_y = self.max_y_amp * (r ** self.y_amp_gamma)
        speed_y = self.y_speed_min + (self.y_speed_max - self.y_speed_min) * r

        y_norm = self._sum_waves(self.y_waves, speed_scale=speed_y)
        offset_y = amp_y * y_norm

        return offset_x, offset_y
