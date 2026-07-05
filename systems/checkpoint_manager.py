"""
systems/checkpoint_manager.py
存档点管理器 — 记录和恢复关卡运行状态

存档点不是新实体类。存档点复用 Item（effect="Checkpoint"）。
本类只负责创建 snapshot 和从 snapshot 恢复。
"""

from physics.vector import Vector2


class CheckpointManager:
    """
    存档点管理器。

    同一时间只有一个激活存档点，新存档点覆盖旧存档点。
    死亡 / 按 R → 从激活存档点恢复
    按 ESC → 清空存档，从头开始
    """

    def __init__(self):
        self.active_checkpoint_id = None
        self.snapshot = None
        self.checkpoint_y = None  # 存档点 Y 坐标，用于岩浆淹没检测

    def has_checkpoint(self):
        return self.snapshot is not None

    def clear(self):
        self.active_checkpoint_id = None
        self.snapshot = None
        self.checkpoint_y = None

    # ================================================================
    #  激活存档点
    # ================================================================

    def activate_checkpoint(self, level, stick, checkpoint_item):
        """激活存档点。返回 True 表示是新激活（与当前不同），False 表示重复触发。"""
        is_new = (self.active_checkpoint_id != checkpoint_item.checkpoint_id)
        self.active_checkpoint_id = checkpoint_item.checkpoint_id
        self.checkpoint_y = checkpoint_item.y + checkpoint_item.height
        self.snapshot = self.create_snapshot(level, stick)
        return is_new

    def check_lava_submerged(self, lava_y):
        """如果岩浆淹没存档点，清除存档"""
        if self.checkpoint_y is not None and lava_y <= self.checkpoint_y:
            self.clear()
            return True
        return False

    # ================================================================
    #  创建 snapshot
    # ================================================================

    def create_snapshot(self, level, stick):
        return {
            "checkpoint_id": self.active_checkpoint_id,
            "stick": self._snapshot_stick(stick),
            "walls": self._snapshot_walls(level.walls),
            "items": self._snapshot_items(level.items),
            "lava": self._snapshot_lava(level),
        }

    def _snapshot_stick(self, stick):
        return {
            "length": stick.length,
            "angular_speed": stick.angular_speed,
            "rotation_direction": stick.rotation_direction,
            "angle": stick.angle,
            "center_x": stick.center_x,
            "center_y": stick.center_y,
            "velocity_x": stick.velocity_x,
            "velocity_y": stick.velocity_y,
            "state": stick.state,
            "anchor_side": stick.anchor_side,
            "anchor_x": stick.anchor_x,
            "anchor_y": stick.anchor_y,
            "base_angular_speed": stick.base_angular_speed,
            "base_length": stick.base_length,
            # 墙壁引用 → 记录 ID，恢复时重新查找
            "attached_wall_id": stick.attached_wall.id if stick.attached_wall else None,
            "anchor_local_pos": [
                stick.anchor_local_pos.x,
                stick.anchor_local_pos.y
            ] if stick.anchor_local_pos else None,
        }

    def _snapshot_walls(self, walls):
        data = {}
        for wall in walls:
            wd = {
                "active": wall.active,
                "wall_type": wall.wall_type,
                "isSolid": wall.isSolid,
                "solid_locked": wall.solid_locked,
                "appearance_solid": wall.appearance_solid,
                "appearance_ghost": wall.appearance_ghost,
                "x": wall.x, "y": wall.y,
                "width": wall.width, "height": wall.height,
                "angle": wall.angle,
                "components": {},
            }
            for name, comp in wall.components.items():
                if name == "moving":
                    st = comp.move_strategy
                    wd["components"]["moving"] = {
                        "elapsed": getattr(st, "_elapsed", 0.0),
                        "finished": getattr(st, "finished", False),
                    }
                elif name == "unstable":
                    wd["components"]["unstable"] = {
                        "tilt_angle": comp.tilt_angle,
                        "angular_velocity": comp.angular_velocity,
                        "angular_acceleration": comp.angular_acceleration,
                    }
                elif name == "beat_solid_switch":
                    wd["components"]["beat_solid_switch"] = {
                        "timer": comp.timer,
                        "initial_delay": comp.initial_delay,
                        "started": comp.started,
                    }
                elif name == "key_pair_solid":
                    wd["components"]["key_pair_solid"] = {
                        "triggered": comp.triggered,
                    }
            data[wall.id] = wd
        return data

    def _snapshot_items(self, items):
        data = {}
        for entry in items:
            rect = entry[0]
            etype = entry[1]
            item_obj = entry[3] if len(entry) >= 4 else None
            item_id = item_obj.id if item_obj else f"{rect.x}_{rect.y}_{etype}"
            item_key = (rect.x, rect.y, etype)
            # 通过 consumed_items 判断是否已消耗
            data[item_id] = {
                "rect_x": rect.x, "rect_y": rect.y,
                "rect_w": rect.width, "rect_h": rect.height,
                "etype": etype,
                "has_item_obj": item_obj is not None,
                "active": item_obj.active if item_obj else True,
                "key_pair_id": item_obj.key_pair_id if item_obj else None,
                "checkpoint_id": item_obj.checkpoint_id if item_obj else None,
                "consume_on_trigger": item_obj.consume_on_trigger if item_obj else True,
                "item_key": list(item_key),
            }
        return data

    def _snapshot_lava(self, level):
        return {
            "y": level.lava_y,
            "rise_speed": level.lava_rise_speed,
        }

    # ================================================================
    #  恢复
    # ================================================================

    def restore(self, level, stick, camera=None, consumed_items=None):
        """
        从当前存档点恢复。无 snapshot 则返回 False。

        恢复顺序：先墙壁，再道具，再岩浆，最后棍子
        （棍子需要从墙壁 ID 重新查找 attached_wall）
        """
        if self.snapshot is None:
            return False

        snap = self.snapshot

        self._restore_walls(level.walls, snap.get("walls", {}))
        self._restore_items(level, snap.get("items", {}), consumed_items)
        self._restore_lava(level, snap.get("lava", {}))
        self._restore_stick(level, stick, snap.get("stick", {}))

        # 相机：直接设 target 和 y，让下一帧自然过渡
        if camera is not None:
            cam_y = level.lava_y  # fallback
            camera.y = max(0, stick.center_y - 350)
            camera.target_y = camera.y

        return True

    def _restore_walls(self, walls, data):
        wall_by_id = {w.id: w for w in walls}
        for wid, wd in data.items():
            w = wall_by_id.get(wid)
            if w is None:
                continue

            w.active = wd["active"]
            w.wall_type = wd.get("wall_type", w.wall_type)
            w.prefab = f"{w.wall_type}_wall"
            w.isSolid = wd.get("isSolid", True)
            w.solid_locked = wd.get("solid_locked", False)
            w.appearance_solid = wd.get("appearance_solid", "")
            w.appearance_ghost = wd.get("appearance_ghost", "")
            w.x = wd["x"]; w.y = wd["y"]
            w.width = wd["width"]; w.height = wd["height"]
            w.angle = wd.get("angle", 0.0)
            w._rect_dirty = True

            comp_data = wd.get("components", {})
            for name, state in comp_data.items():
                comp = w.get_component(name)
                if comp is None:
                    continue

                if name == "moving":
                    st = comp.move_strategy
                    if st:
                        st._elapsed = state.get("elapsed", 0.0)
                        if hasattr(st, "finished"):
                            st.finished = state.get("finished", False)

                elif name == "unstable":
                    comp.tilt_angle = state.get("tilt_angle", 0.0)
                    comp.angular_velocity = state.get("angular_velocity", 0.0)
                    comp.angular_acceleration = state.get("angular_acceleration", 0.0)
                    comp.attached_stick = None
                    comp.anchor_local_pos = None

                elif name == "beat_solid_switch":
                    comp.timer = state.get("timer", 0.0)
                    comp.initial_delay = state.get("initial_delay", 0.0)
                    comp.started = state.get("started", True)

                elif name == "key_pair_solid":
                    comp.triggered = state.get("triggered", False)

    def _restore_items(self, level, data, consumed_items):
        # 重建 item entry 列表
        for entry in level.items:
            rect = entry[0]
            etype = entry[1]
            item_obj = entry[3] if len(entry) >= 4 else None
            item_id = item_obj.id if item_obj else f"{rect.x}_{rect.y}_{etype}"

            if item_id in data:
                sd = data[item_id]
                # 恢复 item_obj 状态
                if item_obj:
                    item_obj.active = sd.get("active", True)
                # 恢复 consumed_items
                item_key = tuple(sd.get("item_key", [rect.x, rect.y, etype]))
                if consumed_items is not None:
                    if sd.get("active", True) is False:
                        consumed_items.add(item_key)
                    elif item_key in consumed_items:
                        consumed_items.discard(item_key)

    def _restore_lava(self, level, data):
        if "y" in data:
            level.lava_y = data["y"]
        if "rise_speed" in data:
            level.lava_rise_speed = data["rise_speed"]

    def _restore_stick(self, level, stick, data):
        stick.length = data.get("length", stick.length)
        stick.angular_speed = data.get("angular_speed", stick.angular_speed)
        stick.rotation_direction = data.get("rotation_direction", stick.rotation_direction)
        stick.angle = data.get("angle", stick.angle)
        stick.center_x = data.get("center_x", stick.center_x)
        stick.center_y = data.get("center_y", stick.center_y)
        stick.velocity_x = data.get("velocity_x", 0.0)
        stick.velocity_y = data.get("velocity_y", 0.0)
        stick.state = data.get("state", stick.state)
        stick.anchor_side = data.get("anchor_side", stick.anchor_side)
        stick.anchor_x = data.get("anchor_x", stick.anchor_x)
        stick.anchor_y = data.get("anchor_y", stick.anchor_y)
        stick.base_angular_speed = data.get("base_angular_speed", stick.angular_speed)
        stick.base_length = data.get("base_length", stick.length)

        # 清理旧引用
        stick.attached_wall = None
        stick.anchor_local_pos = None

        # 重新关联墙壁
        attached_wall_id = data.get("attached_wall_id")
        anchor_local = data.get("anchor_local_pos")
        if attached_wall_id and anchor_local:
            wall = level.get_wall_by_id(attached_wall_id)
            if wall and wall.active:
                stick.attached_wall = wall
                stick.anchor_local_pos = Vector2(anchor_local[0], anchor_local[1])
                wall.on_anchor_attached(stick, (stick.anchor_x, stick.anchor_y))
            else:
                # 墙壁已消失 → 安全降级为空中状态
                stick.state = "airborne"
