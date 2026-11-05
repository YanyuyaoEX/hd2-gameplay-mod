# Lua 脚本契约

> **证据等级**：本文件的接口名与调用方式，来自 `D:\HD2 Mods` 中一个**实机可用**的玩法 mod 的脚本反推
> （build 26251122 + MDL3 dev.36）。除语法规则外，其余标注 `【推断】`：结构与命名可信，
> **但上游没有公开的 API 文档**，换 build / 换加载器后必须实机复验。

## 1. 模块形态

脚本本质是一个 chunk，**必须 `return` 一个表**。加载器按名字调用它的成员：

```lua
-- HD2-Addon: mods/<作者>/<名字>     ← 必须是文件第一行，逐字符等于模块路径
local M = {}

function M.on_enable(context) end
function M.on_update(context, dt) end
function M.on_disable() end

return M
```

| 成员 | 调用时机 | 职责 | 注意 |
|---|---|---|---|
| `on_enable(context)` | 启用 / 重载 | 取 `context`、注册选项、建状态 | 可能被反复调用（重载），必须幂等 |
| `on_update(context, dt)` | 每帧 | 主逻辑 | `dt` 是秒；必须判空判正 |
| `on_disable()` | 停用 | 销毁 GUI / 清表 / 置 nil | 不释放会残留绘制与内存 |
| `diagnostics()` | 排错时 | 返回可打印的表 | 可选，但强烈建议有 |

**没有 `on_start`**。初始化放 `on_enable`。

## 2. `context`

| 字段 | 类型 | 用途 |
|---|---|---|
| `context.settings` | table | 持久化的设置表，跨会话保留 |
| `context.log` | function | 写日志；**用 `pcall` 包住**，加载器不同实现可能缺失 |
| `context.on_cleanup` | function? | 可选回调，注册你自己的清理 |

写法：

```lua
local ctx = nil
local function say(msg)
    if ctx and type(ctx.log) == "function" then pcall(ctx.log, tostring(msg)) end
end
```

## 3. 全局对象（必须用 `rawget`）

| 全局 | 内容 | 用途 |
|---|---|---|
| `stingray` | 引擎 API 表 | 单位 / 世界 / 绘制 / 相机 |
| `MDL3` | MDL3 句柄 | 判断"我是不是在 MDL3 下跑" |
| `MDL` | `MDL.i18n.code` 等 | 中英双语 |
| `ModOptionsMenu` | 选项菜单 | `provider == 'MDL'` 时才有 `register_option` / `get` |

```lua
local sr = rawget(_G, "stingray")
if type(sr) ~= "table" then return end
```

**为什么不能直接索引**：换加载器时这些全局可能不存在。`MDL3.xxx` 在 nil 上索引会直接抛错，
崩在别人机器上、且日志里只看到一行 "attempt to index a nil value"。

## 4. 选项与菜单【推断】

```lua
local menu, ids, defs = nil, {}, {}

local function option(key, spec)
    spec.mod = function() return "我的 MOD" end          -- 或字符串
    spec.mod_id = "mods/<作者>/<名字>"                    -- 必须等于模块路径
    defs[#defs + 1] = { key = key, id = "<前缀>_" .. key, spec = spec }
end

local function bind_menu()
    local cand = rawget(_G, "ModOptionsMenu")
    if cand == menu and menu then return end
    if type(cand) == "table" and cand.provider == "MDL"
        and type(cand.register_option) == "function" and type(cand.get) == "function" then
        menu = cand
    else
        menu = nil
    end
    ids = {}
    if menu then
        for _, d in ipairs(defs) do
            local okk, accepted = pcall(menu.register_option, d.id, d.spec)
            if okk and accepted then ids[d.key] = d.id end
        end
    end
end
```

`spec` 支持的形态（实测样本里出现过）：

| 字段 | 值 |
|---|---|
| `type` | `'toggle'` / `'choice'` |
| `label` | 字符串，或返回字符串的**函数**（做语言切换） |
| `description` | 同上 |
| `default` | 默认值 |
| `choices` | `type='choice'` 时的候选项数组 |

读取值要带兜底：

```lua
local cached = {}
local function value(key, default)
    if menu and ids[key] then
        local v = menu.get(ids[key])
        if v ~= nil then cached[key] = v; return v end
    end
    if cached[key] ~= nil then return cached[key] end
    local v = ctx.settings[key]
    if v == nil then return default end
    return v
end
```

## 5. 引擎 API（`stingray`）

以下成员在实机可用的玩法 mod 中被调用过：

| 命名空间 | 成员 | 语义 |
|---|---|---|
| `Vector3` | `x(v)` `y(v)` `z(v)` `distance` | 取分量 / 距离。**不要长期持有引擎向量**，立刻转成 `{x,y,z}` 表 |
| `Unit` | `alive(u)` | 单位是否存活。**任何取值前先判** |
| | `node(u, name)` / `has_node(u, name)` | 节点 id / 是否存在（如 `attach_hand_r`） |
| | `world_position(u, node)` | 节点世界坐标 |
| | `num_cameras(u)` / `has_animation_state_machine(u)` | 相机数 / 是否有状态机 |
| `World` | `units(w)` | 世界里所有单位 |
| | `units_by_resource(w, id)` | 按资源 id 找同类单位（找飞行器、找某类敌人） |
| | `destroy_gui(w, gui)` | 销毁自己创建的 GUI |
| | `debug_camera_pose(w)` | 相机位姿 |
| `Gui` | `triangle(gui, p1, p2, p3, color, layer)` | 2D 图元。**注意用 X/Z 作屏幕坐标，layer 单独传** |
| `Application` | `worlds()` | 世界列表 |
| `Camera` | 相机相关 | 世界坐标 → 屏幕坐标 |

**防御式写法**：

```lua
local function has(sr, path) -- 简单校验某个接口存在
    local cur = sr
    for part in path:gmatch("[%w_]+") do
        if type(cur) ~= "table" then return false end
        cur = cur[part]
    end
    return cur ~= nil
end
```

## 6. 三条纪律

### 6.1 `dt` 必须夹紧

```lua
if type(dt) ~= "number" or dt <= 0 or dt > 1 then return end
```

切图、卡顿、暂停恢复时 `dt` 可能是 0、nil 或几秒。直接用会让动画瞬移、积分爆炸。

### 6.2 一切都可能是 `nil`

引擎接口在对象已销毁时返回 `nil` 而不是抛错。**每一次取值都要判**：

```lua
local pos = sr.Unit.alive(u) and sr.Unit.world_position(u, 1) or nil
if not pos then return end
```

### 6.3 只读，不写

预览版 Data Hub 与引擎 API 都是**读**。不要试图通过返回值修改游戏状态
（写不进去，且会静默失败，浪费你几小时）。

**原因是接口只开了一半**：MDL3 自带 FFI，读已经通了，写没开。要改数值不要在这里死磕，
走盘上数值表（路线 C）——那是另一条完整通路，持久生效且不需要 native。

想读更多游戏私有数据（血量、弹药、敌人、事件）时，**脚本里没有 `ffi`**，
去 `For Modder/hd2data_field_reference_v0_3_0.md` 查字段，用 `D.player()` / `D.players()` /
`D.strikes()` 这类接口。Data Hub 没暴露的，再退到 `stingray` 引擎 API 自己算。

## 7. 最小可运行样例

> 骨架，接口名来自实测样本；**逐行实机验证仍由你完成**。

```lua
-- HD2-Addon: mods/demo/probe
local M = {}
local ctx, state

function M.on_enable(context)
    ctx = context
    ctx.settings = ctx.settings or {}
    state = { drawn = 0, errors = {} }
end

function M.on_update(context, dt)
    if not ctx or not state then return end
    if type(dt) ~= "number" or dt <= 0 or dt > 1 then return end

    local sr = rawget(_G, "stingray")
    if type(sr) ~= "table" then return end
    if type(sr.World) ~= "table" or type(sr.Unit) ~= "table" then return end

    local ok, err = pcall(function()
        local world = (sr.Application.worlds() or {})[1]
        if not world then return end
        -- 在这里读单位、算结果、调 sr.Gui.* 画出来
        state.drawn = state.drawn + 1
    end)
    if not ok then
        state.errors[#state.errors + 1] = tostring(err)
        if #state.errors > 5 then state.errors = {} end
    end
end

function M.on_disable()
    state = nil
    ctx = nil
end

function M.diagnostics()
    return { drawn = state and state.drawn or 0,
             errors = state and #state.errors or 0 }
end

return M
```

**为什么要 `pcall`**：玩法脚本每帧跑，一次未捕获的异常可能让加载器直接停掉你的 mod。
把主逻辑包起来，错误进表、下帧继续。

## 8. 排错顺序

1. 加载器认到了吗（MDL3 菜单 / Chef F9 列表）
2. `on_enable` 跑到了吗（写一条日志）
3. `on_update` 跑到了吗（计数并写日志）
4. 引擎接口拿到了吗（`type(sr.World)` 打日志）
5. 绘制调对了吗（先用固定坐标画一个点）

**逐层验证**，不要一次写完再看结果 —— 每帧脚本的失败是静默的，没有分层日志就无法定位。
