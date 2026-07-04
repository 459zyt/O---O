"""
tools/tiled_converter.py
Tiled Map Editor JSON → game level.json 转换器

用法:
    python tools/tiled_converter.py maps/level1/level.tiled.json          # 转换单个
    python tools/tiled_converter.py --all                                 # 转换全部
    python tools/tiled_converter.py maps/level1/level.tiled.json --check  # 只校验不输出

设计原则:
  - 读取 Tiled 的 type 字段 (对应 Custom Class) 判断对象类型
  - 布尔属性自动生成对应组件配置
  - 强制校验 (E01-E12) 在导出时暴露错误
  - 对未知属性只警告不报错 (向前兼容)
"""

import json
import os
import sys
import math


# ================================================================
#  校验器
# ================================================================

class ConverterError(Exception):
    """转换器错误"""
    pass


class ConverterWarning:
    """转换器警告收集"""
    def __init__(self):
        self.warnings = []

    def add(self, code, message):
        self.warnings.append(f"[{code}] {message}")

    def report(self):
        for w in self.warnings:
            print(f"  ⚠ {w}")
        return len(self.warnings)


# ================================================================
#  属性转换辅助
# ================================================================

def _props_to_dict(properties):
    """Tiled properties 数组 → 普通字典"""
    result = {}
    for prop in properties:
        result[prop["name"]] = prop.get("value")
    return result


# ================================================================
#  主转换函数
# ================================================================

def convert_tiled_to_level(tiled_path, output_path=None, check_only=False):
    """
    将 Tiled JSON 转换为游戏 level.json

    参数
    ----
    tiled_path : str
        Tiled 导出的 .json 文件路径
    output_path : str | None
        输出路径，默认同目录 level.json
    check_only : bool
        True 时只校验不输出文件

    返回
    ----
    dict — 转换后的 level 数据
    """
    with open(tiled_path, "r", encoding="utf-8") as f:
        tiled = json.load(f)

    warnings = ConverterWarning()

    if output_path is None:
        output_path = os.path.join(os.path.dirname(tiled_path), "level.json")

    # ── 1. 地图属性 ──
    map_props = _props_to_dict(tiled.get("properties", []))

    level = {
        "version": 2,
        "level_id": map_props.get("level_id", os.path.basename(os.path.dirname(tiled_path))),
        "name": map_props.get("level_name", "Untitled"),
        "world": {
            "width": tiled.get("width", 20) * tiled.get("tilewidth", 32),
            "height": tiled.get("height", 35) * tiled.get("tileheight", 32),
            "tile_size": tiled.get("tilewidth", 32),
        },
        "background": map_props.get("background", ""),
        "music": map_props.get("music", ""),
        "player_start": {"x": 0, "y": 0, "angle": 270, "anchor_side": "left"},
        "lava": {
            "enabled": _to_bool(map_props.get("lava_enabled", True)),
            "gif": map_props.get("lava_gif", ""),
            "start_y": float(map_props.get("lava_start_y", 1200)),
            "rise_speed": float(map_props.get("lava_rise_speed", 30)),
            "alpha": int(map_props.get("lava_alpha", 160)),
        },
        "objects": [],
    }

    # ── 2. 先收集 Paths 层 ──
    paths = {}
    path_objects = []  # 用于重复 path_id 检测

    for layer in tiled.get("layers", []):
        if layer.get("name", "").lower() in ("paths", "path"):
            for obj in layer.get("objects", []):
                props = _props_to_dict(obj.get("properties", []))
                pid = props.get("path_id", "")
                if pid:
                    if pid in paths:
                        warnings.add("E04", f"Paths 层存在重复 path_id: {pid}")
                    paths[pid] = _convert_polyline(obj)
                    path_objects.append(pid)

    # ── 3. 解析各对象层 ──
    player_count = 0

    for layer in tiled.get("layers", []):
        layer_name = layer.get("name", "")
        layer_lower = layer_name.lower()

        for obj in layer.get("objects", []):
            # 获取 Tiled 的 type 字段 (Class 名称)
            obj_class = obj.get("type", "")
            props = _props_to_dict(obj.get("properties", []))

            # Player 层 → PlayerStart
            if layer_lower in ("player", "players", "spawn"):
                player_count += 1
                level["player_start"] = _convert_player_start(obj, props)
                continue

            # Walls 层 → Wall
            if layer_lower in ("walls", "wall") or obj_class == "Wall":
                wall_obj = _convert_wall(obj, props, paths, warnings)
                if wall_obj:
                    level["objects"].append(wall_obj)
                continue

            # Items 层 → Item
            if layer_lower in ("items", "item") or obj_class == "Item":
                item_obj = _convert_item(obj, props, warnings)
                if item_obj:
                    level["objects"].append(item_obj)
                continue

            # Hazards 层 → Hazard
            if layer_lower in ("hazards", "hazard") or obj_class == "Hazard":
                hazard_obj = _convert_hazard(obj, props, warnings)
                if hazard_obj:
                    level["objects"].append(hazard_obj)
                continue

            # Paths 层 → 已经处理
            if layer_lower in ("paths", "path") or obj_class == "Path":
                continue

            # 未知对象 — 只警告
            if obj_class and obj_class not in ("", "Wall", "Item", "Hazard", "PlayerStart", "Path"):
                warnings.add("E11", f"{layer_name} 层对象 id={obj.get('id')}: 未知 Class={obj_class}")

    # ── 4. 校验 ──
    if player_count != 1:
        warnings.add("E01", f"Player 层应有恰好 1 个出生点，当前 {player_count} 个")

    _validate_all(warnings, level, path_objects)

    n_warnings = warnings.report()
    if n_warnings > 0:
        print(f"  ⚠ 共 {n_warnings} 个警告")

    if check_only:
        print(f"  校验完成: {os.path.basename(tiled_path)}")
        return level

    # ── 5. 输出 ──
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(level, f, indent=2, ensure_ascii=False)

    walls = [o for o in level["objects"] if o["type"] == "wall"]
    items = [o for o in level["objects"] if o["type"] == "item"]
    hazards = [o for o in level["objects"] if o["type"] == "hazard"]
    print(f"  转换完成: {os.path.basename(tiled_path)} → {os.path.basename(output_path)}")
    print(f"  世界: {level['world']['width']}x{level['world']['height']} px")
    print(f"  墙壁: {len(walls)}, 道具: {len(items)}, 障碍物: {len(hazards)}")
    print(f"  出生点: ({level['player_start']['x']}, {level['player_start']['y']})")
    return level


# ================================================================
#  校验逻辑
# ================================================================

def _validate_all(warnings, level, path_ids):
    """执行全部校验规则 E01-E12"""
    for obj in level["objects"]:
        oid = obj.get("id", "?")
        ox, oy = obj.get("x", 0), obj.get("y", 0)
        loc = f"对象 id={oid} (x={ox}, y={oy})"

        if obj["type"] == "wall":
            comps = obj.get("components", {})

            # E02: moving 但没填 path_id
            if "moving" in comps and not comps["moving"].get("path"):
                warnings.add("E02", f"Walls 层 {loc}: moving=true 但未找到匹配的 path_id")

            # E05: key_pair_solid 但 key_pair_id 为空
            if "key_pair_solid" in comps:
                kid = comps["key_pair_solid"].get("key_pair_id", "")
                if not kid:
                    warnings.add("E05", f"Walls 层 {loc}: key_pair_solid=true 但 key_pair_id 为空")

            # E09: 没有 goal 墙 (按每一面检查, 最后汇总)
            pass

        elif obj["type"] == "item":
            effect = obj.get("effect", "")
            # E07: KeyPair 道具没有 key_pair_id
            if effect == "KeyPair" and not obj.get("key_pair_id"):
                warnings.add("E07", f"Items 层 {loc}: effect=KeyPair 但 key_pair_id 为空")

            # E10: Checkpoint consume_on_trigger=true
            if effect == "Checkpoint" and obj.get("consume_on_trigger", False):
                warnings.add("E10", f"Items 层 {loc}: Checkpoint 建议 consume_on_trigger=false")

            # E08: image 文件不存在
            img = obj.get("image", "")
            if img and not os.path.exists(img):
                warnings.add("E08", f"Items 层 {loc}: image 文件不存在: {img}")

        elif obj["type"] == "hazard":
            img = obj.get("image", "")
            if img and not os.path.exists(img):
                warnings.add("E08", f"Hazards 层 {loc}: image 文件不存在: {img}")

        elif obj["type"] == "wall":
            img = obj.get("image", "")
            if img and not os.path.exists(img):
                warnings.add("E08", f"Walls 层 {loc}: image 文件不存在: {img}")

    # E09: 需要至少一个 goal 墙
    goal_count = sum(1 for o in level["objects"]
                     if o["type"] == "wall" and ("goal" in o.get("components", {})))
    if goal_count == 0:
        warnings.add("E09", "地图中没有 goal 墙壁，将无法通关")

    # E06: 有 key_pair_id 的墙但没有对应钥匙
    key_wall_ids = set()
    for o in level["objects"]:
        if o["type"] == "wall" and "key_pair_solid" in o.get("components", {}):
            kid = o["components"]["key_pair_solid"].get("key_pair_id", "")
            if kid:
                key_wall_ids.add(kid)
    key_item_ids = set()
    for o in level["objects"]:
        if o["type"] == "item" and o.get("effect") == "KeyPair":
            kid = o.get("key_pair_id", "")
            if kid:
                key_item_ids.add(kid)
    for kwid in key_wall_ids:
        if kwid not in key_item_ids:
            warnings.add("E06", f"key_pair_id={kwid} 的墙壁存在，但没有对应钥匙道具")


# ================================================================
#  类型转换
# ================================================================

def _to_bool(val):
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in ("true", "1", "yes")
    return bool(val)


def _to_float(val, default=0.0):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


# ================================================================
#  对象转换函数
# ================================================================

def _convert_polyline(obj):
    """Polyline → 世界坐标点列表"""
    base_x = obj.get("x", 0)
    base_y = obj.get("y", 0)
    points = []
    for p in obj.get("polyline", []):
        points.append([base_x + p.get("x", 0), base_y + p.get("y", 0)])
    return points


def _convert_player_start(obj, props):
    return {
        "x": int(obj.get("x", 0)),
        "y": int(obj.get("y", 0)),
        "angle": _to_float(props.get("angle", 270), 270),
        "anchor_side": props.get("anchor_side", "left"),
        "stick_image": props.get("stick_image", ""),
        "left_ball_image": props.get("left_ball_image", ""),
        "right_ball_image": props.get("right_ball_image", ""),
        "ball_image": props.get("ball_image", ""),
    }


def _convert_wall(obj, props, paths, warnings):
    w = {
        "id": obj.get("name", f"wall_{obj.get('id', '?')}"),
        "type": "wall",
        "wall_type": props.get("wall_type", "normal"),
        "x": int(obj.get("x", 0)),
        "y": int(obj.get("y", 0)),
        "width": int(obj.get("width", 32)),
        "height": int(obj.get("height", 32)),
        "image_solid": props.get("image_solid", props.get("image", "")),
        "image_ghost": props.get("image_ghost", ""),
        "isSolid": _to_bool(props.get("isSolid", True)),
    }

    components = {}

    if _to_bool(props.get("fragile")):
        components["fragile"] = {
            "break_on_detach": _to_bool(props.get("break_on_detach", True))
        }

    if _to_bool(props.get("goal")):
        components["goal"] = {}

    if _to_bool(props.get("moving")):
        pid = props.get("path_id", "")
        mc = {
            "strategy": props.get("move_strategy", "loop"),
            "speed": _to_float(props.get("move_speed", 80)),
            "start_delay": _to_float(props.get("move_start_delay", 0)),
        }
        if pid and pid in paths:
            mc["path"] = paths[pid]
        elif pid:
            warnings.add("E03", f"Walls 层 {w['id']}: path_id={pid} 未找到对应 Path 对象")
        components["moving"] = mc

    if _to_bool(props.get("unstable")):
        components["unstable"] = {
            "max_tilt_angle": _to_float(props.get("max_tilt_angle", 35)),
            "tilt_direction": props.get("tilt_direction", "both"),
            "inertia": _to_float(props.get("inertia", 120)),
            "torque_scale": _to_float(props.get("torque_scale", 1.0)),
            "damping": _to_float(props.get("damping", 1.5)),
            "return_speed": _to_float(props.get("return_speed", 20)),
            "break_at_max_tilt": _to_bool(props.get("break_at_max_tilt", False)),
        }

    if _to_bool(props.get("beat_solid_switch")):
        components["beat_solid_switch"] = {
            "switchSecond": _to_float(props.get("switchSecond", 2.0)),
            "initial_delay": _to_float(props.get("initial_delay", 0.0)),
            "start_solid": _to_bool(props.get("start_solid", True)),
        }

    if _to_bool(props.get("key_pair_solid")):
        components["key_pair_solid"] = {
            "key_pair_id": props.get("key_pair_id", ""),
            "key_pair_result": props.get("key_pair_result", "solid"),
        }

    if components:
        w["components"] = components

    return w


def _convert_item(obj, props, warnings):
    effect = props.get("effect", "LengthUp")

    # prefab 映射：effect "LengthUp" → prefab "length_up"（供 loader effect_map 使用）
    _effect_to_prefab = {
        "LengthUp": "length_up", "LengthDown": "length_down",
        "SpeedUp": "speed_up", "SpeedDown": "speed_down",
        "KeyPair": "key", "Checkpoint": "checkpoint",
    }

    item = {
        "id": obj.get("name", f"item_{obj.get('id', '?')}"),
        "type": "item",
        "prefab": _effect_to_prefab.get(effect, "length_up"),
        "effect": effect,
        "x": int(obj.get("x", 0)),
        "y": int(obj.get("y", 0)),
        "width": int(obj.get("width", 32)),
        "height": int(obj.get("height", 32)),
        "image": props.get("image", ""),
        "value": _to_float(props.get("value", 20)),
        "trigger_condition": props.get("trigger_condition", "OnAnchor"),
        "consume_on_trigger": _to_bool(props.get("consume_on_trigger", True)),
    }

    if effect in ("KeyPair", "key"):
        item["key_pair_id"] = props.get("key_pair_id", "")

    if effect in ("Checkpoint", "checkpoint"):
        item["checkpoint_id"] = props.get("checkpoint_id", item["id"])
        # checkpoint 默认不消耗
        item["consume_on_trigger"] = _to_bool(props.get("consume_on_trigger", False))

    return item


def _convert_hazard(obj, props, warnings):
    return {
        "id": obj.get("name", f"hazard_{obj.get('id', '?')}"),
        "type": "hazard",
        "x": int(obj.get("x", 0)),
        "y": int(obj.get("y", 0)),
        "width": int(obj.get("width", 32)),
        "height": int(obj.get("height", 32)),
        "image": props.get("image", ""),
        "trigger_condition": props.get("trigger_condition", "OnTouch"),
    }


# ================================================================
#  CLI
# ================================================================

def convert_all_maps(base_dir="maps"):
    """转换 maps/ 下所有 level.tiled.json"""
    count = 0
    for root, dirs, files in os.walk(base_dir):
        if "_template" in root:
            continue
        if "level.tiled.json" in files:
            tiled_path = os.path.join(root, "level.tiled.json")
            print(f"\n转换: {tiled_path}")
            try:
                convert_tiled_to_level(tiled_path)
                count += 1
            except Exception as e:
                print(f"  错误: {e}")
    print(f"\n共转换 {count} 个关卡")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] == "--all":
        convert_all_maps()
    elif len(sys.argv) >= 2:
        tiled_path = sys.argv[1]
        check_only = "--check" in sys.argv
        if not os.path.exists(tiled_path):
            print(f"错误: 文件不存在: {tiled_path}")
            sys.exit(1)
        convert_tiled_to_level(tiled_path, check_only=check_only)
