# 如何使用 Tiled 绘制 O---O 地图

本指南面向**地图设计师**，从零开始教你用 Tiled Map Editor 为 O---O 游戏创建关卡。不需要写任何代码。

---

## 一、安装与打开项目

### 1. 安装 Tiled

官网下载安装：https://www.mapeditor.org/ （免费开源，支持 Windows / Mac / Linux）

### 2. 打开项目

```
启动 Tiled → 文件 → 打开项目 → 选择 oopz.tiled-project
```

打开后你会看到：
- **左侧**：项目面板，显示 `maps/`、`tiled/templates/` 目录
- **右侧**：模板面板，可以拖拽预配置好的物体

> `oopz.tiled-project` 是项目配置文件。打开它后，Tiled 自动加载所有下拉菜单（枚举）和物体属性面板（类）。**每次设计关卡都从这里打开。**

---

## 二、创建新关卡

### 第一步：复制模板

```
在左侧项目面板中：
  右键 maps/_template/ → 复制
  粘贴到 maps/ → 重命名为你的关卡名（如 level2）
```

### 第二步：打开关卡文件

```
双击 maps/level2/level.tiled.json
```

你会看到一个 20×35 格的空白地图，已经建好了 7 个图层。

---

## 三、六个枚举（下拉菜单）

以下是设计关卡时所有的下拉菜单选项。选中对应属性后，在右侧属性面板中直接下拉选择，不需要手打。

| 枚举名 | 用于 | 可选项 |
|--------|------|--------|
| **WallType** | 墙壁类型 | `normal` / `fragile` / `goal` |
| **MoveStrategy** | 移动方式 | `loop`（循环绕圈）/ `pingpong`（来回往返）/ `once`（走到终点停） |
| **TriggerCondition** | 触发方式 | `OnAnchor`（抓住触发）/ `OnTouch`（碰到触发） |
| **TiltDirection** | 倾斜方向 | `both`（双向）/ `clockwise`（顺时针）/ `counter_clockwise`（逆时针） |
| **KeyPairResult** | 钥匙效果 | `solid`（变实体）/ `ghost`（变虚体）/ `toggle`（切换一次） |
| **ItemEffect** | 道具效果 | `LengthUp` / `LengthDown` / `SpeedUp` / `SpeedDown` / `KeyPair` / `Checkpoint` |

---

## 四、五个类（物体类型）

每个图层放对应的物体，选中物体后在右侧属性面板的 **Type 下拉框** 选择类名。

### 1. Wall（墙壁）

| 怎么用 | 说明 |
|--------|------|
| **放在哪** | `Walls` 图层 |
| **怎么画** | 工具栏选"插入矩形"，在画布上拖拽 |
| **Type 下拉** | 选 `Wall` |
| **默认尺寸** | 建议宽度 ≥ 64px，厚度 32px |

**属性面板会出现的配置：**

| 属性 | 交互 | 说明 |
|------|------|------|
| `wall_type` | 下拉 | `normal`=普通 / `fragile`=脆弱 / `goal`=终点 |
| `isSolid` | 复选框 | 初始是实体墙还是虚线墙 |
| `fragile` | 复选框 | 勾选后，锚点离开墙壁即碎裂 |
| `goal` | 复选框 | 勾选后，抓住即通关 |
| `moving` | 复选框 | 勾选后，墙壁沿路径移动 |
| `move_strategy` | 下拉 | `loop`/`pingpong`/`once` |
| `move_speed` | 数字 | 移动速度（像素/秒），推荐 40~120 |
| `path_id` | 文本框 | 匹配 Paths 层的路径名称 |
| `unstable` | 复选框 | 勾选后，抓住后墙壁会倾斜 |
| `max_tilt_angle` | 数字 | 最大倾斜角度（度），默认 35 |
| `tilt_direction` | 下拉 | 倾斜方向限制 |
| `beat_solid_switch` | 复选框 | 勾选后，墙壁周期性虚实切换 |
| `switchSecond` | 数字 | 切换周期（秒），推荐 ≥1.0 |
| `key_pair_solid` | 复选框 | 勾选后，由钥匙控制虚实 |
| `key_pair_id` | 文本框 | 匹配钥匙道具的 ID |
| `key_pair_result` | 下拉 | `solid`=钥匙后变实体 / `ghost`=变虚体 / `toggle`=切换 |

**所有能力可以任意组合**，例如：
- `fragile` + `moving` = 会移动的脆弱墙
- `moving` + `unstable` = 移动且倾斜的墙
- `beat_solid_switch` + `moving` = 节拍移动墙
- `key_pair_solid` + `goal` = 钥匙解锁的终点墙

---

### 2. Item（道具）

| 怎么用 | 说明 |
|--------|------|
| **放在哪** | `Items` 图层 |
| **怎么画** | 工具栏选"插入矩形"，拖拽 |
| **Type 下拉** | 选 `Item` |
| **关键规则** | 道具矩形可以（且通常应该）**直接叠放在墙壁矩形上面**，互不排斥 |

**属性面板配置：**

| 属性 | 交互 | 说明 |
|------|------|------|
| `effect` | 下拉 | 道具效果，6 选 1 |
| `value` | 数字 | 效果数值（长度变化量/速度倍率） |
| `trigger_condition` | 下拉 | `OnAnchor`=抓住触发 / `OnTouch`=碰到触发 |
| `consume_on_trigger` | 复选框 | 触发后是否消失 |
| `key_pair_id` | 文本框 | 仅 effect=KeyPair 时填写 |
| `checkpoint_id` | 文本框 | 仅 effect=Checkpoint 时填写 |

**各道具推荐配置：**

| effect | trigger_condition | consume | value | 说明 |
|--------|-------------------|---------|-------|------|
| `LengthUp` | OnAnchor | ✅ | 20 | 抓住后棍子变长 |
| `LengthDown` | OnAnchor | ✅ | 20 | 抓住后棍子变短 |
| `SpeedUp` | OnAnchor | ✅ | 0.2 | 抓住后转速变快 |
| `SpeedDown` | OnAnchor | ✅ | 0.2 | 抓住后转速变慢 |
| `KeyPair` | OnAnchor | ✅ | - | 抓住后触发对应墙壁 |
| `Checkpoint` | OnTouch | ❌ | - | 经过即存档 |

---

### 3. Hazard（障碍物）

| 怎么用 | 说明 |
|--------|------|
| **放在哪** | `Hazards` 图层 |
| **怎么画** | 工具栏选"插入矩形"，拖拽 |
| **Type 下拉** | 选 `Hazard` |

棍子任意部分碰到障碍物 → 立即脱锚，进入失控飞行。可与墙壁重叠制造"危险平台"。

---

### 4. PlayerStart（玩家出生点）

| 怎么用 | 说明 |
|--------|------|
| **放在哪** | `Player` 图层 |
| **怎么画** | 工具栏选"插入点对象"，在画布上点击 |
| **Type 下拉** | 选 `PlayerStart` |
| **数量** | 每张地图**必须有且只有一个** |

| 属性 | 说明 |
|------|------|
| `angle` | 棍子初始角度（度），默认 270=指向上方 |
| `anchor_side` | 初始锚点端，默认 `left` |

---

### 5. Path（移动路径）

| 怎么用 | 说明 |
|--------|------|
| **放在哪** | `Paths` 图层 |
| **怎么画** | 工具栏选"插入折线"，在画布上依次点击路径点，按 Enter 完成 |
| **Type 下拉** | 选 `Path` |
| **关键规则** | `path_id` 必须与对应移动墙的 `path_id` **完全一致** |

---

## 五、图层结构总览

图层从下到上（底 → 顶）：

| 图层 | 放什么 | 物体类型 |
|------|--------|---------|
| `Player` | 出生点 | Point + Class=PlayerStart |
| `Walls` | 所有墙壁 | Rectangle + Class=Wall |
| `Items` | 道具 | Rectangle + Class=Item |
| `Hazards` | 障碍物 | Rectangle + Class=Hazard |
| `Paths` | 移动路径 | Polyline + Class=Path |
| `Triggers` | 触发区（可选） | Rectangle |
| `Decorations` | 装饰（不参与逻辑） | 任意 |

---

## 六、关卡属性设置

菜单 `地图 → 地图属性 → 自定义属性`：

| 属性 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `level_id` | string | 关卡 ID | `level2` |
| `level_name` | string | 关卡名称 | `第二关` |
| `background` | file | 背景图路径（可选） | `arts/backgrounds/level_02_bg.png` |
| `music` | file | 背景音乐路径（可选） | `arts/sounds/bgm_level2.ogg` |
| `lava_enabled` | bool | 是否启用岩浆 | `true` |
| `lava_start_y` | float | 岩浆初始高度（世界Y） | `1200` |
| `lava_rise_speed` | float | 岩浆上升速度（px/s） | `30` |

---

## 七、实战示例：制作一面会移动的脆弱墙

### 目标

创建一面长 160px、厚 32px 的脆弱墙，在 (320, 560) 到 (480, 420) 之间来回移动。

### 步骤

**1. 打开模板关卡**

```
项目面板 → 双击 maps/_template/level.tiled.json
```

**2. 画墙壁**

```
选中 Walls 图层 → 工具栏"插入矩形" → 在画布上拖出 160×32 的矩形
```

**3. 配置墙壁属性**

```
选中矩形 → 右侧属性面板：
  Type 下拉              → 选 Wall
  wall_type 下拉         → 选 fragile
  勾选 fragile 复选框
  勾选 moving 复选框
  move_strategy 下拉     → 选 pingpong
  move_speed             → 填 60
  path_id                → 填 path_wall_move_01
```

**4. 画移动路径**

```
选中 Paths 图层 → 工具栏"插入折线"
依次点击三个点：
  点1: (320, 560) — 墙壁当前位置
  点2: (480, 560)
  点3: (480, 420)
按 Enter 完成

选中这条折线 → 右侧属性面板：
  Type 下拉              → 选 Path
  path_id                → 填 path_wall_move_01（与墙壁一致！）
```

**5. 放终点墙**

```
选中 Walls 图层 → 拖一个矩形在关卡顶部
  Type → Wall
  wall_type → goal
  勾选 goal
```

**6. 放出生点**

```
选中 Player 图层 → 工具栏"插入点" → 在地图下方点击
  Type → PlayerStart
  angle → 270
```

**7. 保存并测试**

```
Ctrl+S 保存到 maps/level2/level.tiled.json
按 F5 直接运行游戏测试
```

---

## 八、更多示例

### 节拍虚实墙

```
Walls 层拖矩形
  Type → Wall
  勾选 beat_solid_switch
  switchSecond → 2.0
  isSolid → 勾选（初始为实体墙）
→ 每 2 秒自动切换实体/虚体
```

### 钥匙解锁终点墙

```
Walls 层拖矩形（放在终点附近）
  Type → Wall
  wall_type → goal
  勾选 goal
  勾选 key_pair_solid
  key_pair_id → key_final
  key_pair_result → solid
  isSolid → 不勾选（初始为虚线墙）

Items 层拖矩形（放在关卡前半段）
  Type → Item
  effect → KeyPair
  key_pair_id → key_final
  trigger_condition → OnAnchor
→ 玩家拿到钥匙后，终点墙从虚线变实体，可通关
```

### 存档点

```
Items 层拖 64×64 矩形
  Type → Item
  effect → Checkpoint
  trigger_condition → OnTouch
  consume_on_trigger → 不勾选
  checkpoint_id → cp_001
→ 玩家经过自动存档，死亡后从这里复活
```

---

## 九、从模板拖拽（更快的方式）

右侧模板面板中已经做好了常用模板，直接拖到画布上即可：

| 模板 | 拖出来是什么 |
|------|-------------|
| Normal Wall | 160×32 普通实体墙 |
| Fragile Wall | 160×32 脆弱墙 |
| Goal Wall | 96×32 终点墙 |
| Moving Wall | 160×32 移动墙（pingpong） |
| Unstable Wall | 160×32 不稳定墙 |
| Beat Solid Wall | 160×32 节拍虚实墙 |
| Ghost Wall | 160×32 虚线墙 |
| KeyPair -> Solid | 160×32 钥匙解锁实体墙 |
| KeyPair -> Ghost | 160×32 钥匙解锁虚体墙 |
| Length Up | 32×32 增长道具 |
| Speed Up | 32×32 加速道具 |
| Key | 32×32 钥匙 |
| Checkpoint | 64×64 存档点 |
| Spike | 32×32 障碍物 |
| Player Start | 点对象出生点 |
| Path | 折线路径 |

拖出后，属性都已经预设好，你只需要调整位置、尺寸和个别属性。

---

## 十、快捷操作

| 操作 | 方法 |
|------|------|
| 复制物体 | 选中 + Ctrl+D |
| 多选 | 按住 Shift 点击 |
| 保存 | Ctrl+S |
| 测试游戏 | F5 |
| 切换图层 | 点击图层面板 |
| 缩放画布 | Ctrl+滚轮 |

---

## 十一、常见问题

**Q: 道具可以和墙壁放在同一个位置吗？**
可以，把道具矩形直接拖到墙壁矩形上即可。游戏里检测到端点同时碰到墙壁和道具时，两者都会触发。

**Q: 墙壁可以不按 32px 格对齐吗？**
可以。矩形对象支持任意像素尺寸和位置，不限于格子。

**Q: 移动墙的路径第一个点必须和墙壁重合吗？**
建议是的，否则墙壁会在开始移动时"跳"到路径第一个点。

**Q: 为什么拖模板报错？**
确保当前选中的图层和模板类型匹配：Wall 模板拖到 Walls 层，Item 模板拖到 Items 层。

**Q: 如何看到背景图需要的尺寸？**
运行一次游戏后，`arts/needs/` 文件夹下会自动生成 `levelX_needs.txt`，里面有精确的背景图尺寸建议。
