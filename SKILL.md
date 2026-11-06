---
name: hd2-gameplay-mod
description: |
  《绝地潜兵2》mod 的「许愿式」开发技能：玩法脚本 + 屏幕绘制/音效 + 模型/贴图替换，用户只要说想要什么效果，就能从零做出可安装的 mod。
  覆盖立项、Lua 5.1 玩法脚本、MDL3.gui 屏幕绘制（面板/文字/图形/图片）、MDL3.audio 音效（循环/音高/3D 定位/混响）、打包 .patch_N、静态门禁、部署、实机验证、归档发布；模型类覆盖护甲/头盔/武器/道具/贴图，用 Blender + HD2SDK 替换 unit 资源。
  Use when 用户说「给我做个 HD2 的 mod」「我想要个显示敌人血条的」「做个自动标记的」「改个准星」「绝地潜兵2 能不能加个 XX 提示」「HD2 玩法 mod」「HD2 脚本 mod」「MDL3 mod」「在屏幕上画个面板」「做个自定义 HUD 界面」「显示背包/护盾/飞行背包冷却」「加个音效提示」「3D 声音」「给 mod 配音乐」「MDL3.gui」「MDL3.audio」「Data Hub 0.6」「把 B-01 换成 XX」「做个护甲模型 mod」「换个武器外观」「人物模型替换」「HD2 模型 mod」「改贴图/换材质」「patch_0 怎么打」「Lua mod 加载不出来」「mod 进游戏没反应」「10月20日之后 mod 还能不能用」。
license: MIT
compatibility: Windows · Python 3.11+（零依赖）· Helldivers 2 PC/Steam · 玩法/GUI/音频路线需 MDL3 3.0.0-dev.41+（推荐 dev.43）· 模型路线需 Blender + HD2SDK · 可选 srkit / hd2-mod-cli
metadata:
  domain: hd2-modding
  kind: workflow
  verified-build: "26251122"
  verified-date: "2026-11-05"
  mdl3-version: "3.0.0-dev.43"
  hub-version: "0.6.0"
  gui-api: "1"
  audio-api: "2"
  doc-baseline: "MDL3 dev.43 包内 README_zh / MDL3_GUI_API_zh / MDL3_AUDIO_API_zh / hd2data_field_reference_v0_6_0（2026-11-06）"
---

# HD2 mod 开发 · 可执行技能（玩法 / GUI / 音频 / 模型）

> 证据分级：`【实测】` build 26251122 本机验证 · `【文档】` 上游文档写明 · `【推断】` 逆推未复验。
> **换 build 后**：`【实测】`/`【推断】` 两类按 §7.5 重跑，`【文档】` 回原页核对。
> **当前基线**：MDL3 3.0.0-dev.43（2026-11-06）+ Data Hub 0.6.0 + native bridge 0.4.5；GUI api 1、audio api 2。

---

## 0. 三十秒：先看这张表再动手

| 想做的 | 路线 | 判据 |
|---|---|---|
| HUD 提示、提前量、信息显示、键位、QoL | **A. Lua 玩法脚本**（§6.1） | 每帧跑逻辑、读单位/世界状态 |
| 屏幕上面板/文字/图形/图片、自定义 HUD 外观 | **A + gui**（§6.1.6） | `MDL3.gui` 画布，纯脚本，不用 Blender |
| mod 自带音效、循环/音高、3D 定位声、环境混响 | **A + audio**（§6.1.7） | `MDL3.audio`，离线编码后打进 patch |
| 换护甲/头盔/武器/道具**外观** | **B1. 模型替换**（§6.2） | 换 unit 的 mesh/material，不改逻辑 |
| 只换贴图/颜色/材质参数 | **B2. 贴图材质**（§6.2） | 不动模型 |
| 已有护甲 mod 改到另一套甲 | **B3. 护甲互换/Retag**（§6.2） | 只换目标 unit |
| 替换游戏**原有**音效/音乐 | **B4b. wwise 替换**（§6.2） | 换 bank/stream，需重打包 |
| 改伤害/冷却/弹容/护甲等**数值** | **C. 数值表**（§6.3，只指路） | 社区工具有，本技能不重造 |
| 读游戏数据 | **A 的子能力**（§6.1.5） | `HD2Data` → `stingray` → 原生 FFI（脚本侧不可得） |

**dev.43 改变了三条判断**（2026-11-06）：
1. 屏幕绘制不再需要自己拼 `Gui` 图元，也不依赖 CSL —— 走 `MDL3.gui`，自带参数校验、生命周期、4K 缩放。
2. mod 音效不再必须做 wwise bank —— `MDL3.audio` 直接播你带进来的 PCM/ADPCM，还能 3D 定位与混响。
3. 数据面更宽：背包状态、增强剂/状态效果、大厅信息（Hub 0.6.0）；多了就能做"飞行背包冷却条""护盾剩余""队友增强剂"这类以前做不了的 HUD。

**默认起点**：先问"改的是**行为**还是**外观**"。行为 → A；外观 → B；都不像 → C。
模型路线不写 Lua、不需要 MDL3，改的是资源，装完**必须重启游戏**。

---

## 0.5 许愿模式：别人只说「我想要个 XX」时怎么接

这一节是给 AI 的行为准则。用户不懂模块路径、加载器、patch 编号，也不需要装 Python。

### 只问三件事，问完就开工

| 问什么 | 用来定 | 例子 |
|---|---|---|
| 屏幕上多什么/少什么？ | UI 还是逻辑 | 「准星旁边显示提前量」 |
| 什么时候出现？ | 触发条件 | 「锁定飞行目标时」 |
| 怎么算做成了？ | 验收标准 | 「打空中目标时准星跟着走」 |

**不要问**：加载器、模块路径、要不要 hook、manifest 怎么写。这些是你的活。

### 然后全自动跑完，只在两个点找用户

```
doctor → new → 写 src/main.lua → build → check → install
  ↑                                        ↓
差环境才找用户                      告诉用户点 Deploy
```

1. `python tools/hd2mod.py doctor` —— 差什么就直说，**不要硬做**。
2. 从"想要的效果"映射路线（见下表）。
3. `new` 起工程 → 写 `src/main.lua` → `build` → `check`（必须全绿）。
4. `install` → 用**人话**告诉用户下一步。

### 交付话术

> ✅「装好了。进游戏按 ESC 打开 **MDL 设置**，列表里有个「XX」，打开它，然后打一只飞行怪试试。」
> ❌「模块路径 mods/x/y，file_id 0x…，已过 murmur64 校验。」（用户不关心）

### 愿望 → 可行性对照

| 用户这么说 | 能做吗 | 走哪 |
|---|---|---|
| 显示血量/弹药/队友/敌人数量 | ✅ | A，读 `HD2Data` |
| 准星、提前量、屏幕标记、距离 | ✅ | A，`HD2Data` + `MDL3.gui` |
| 屏幕上多一个面板/文字/图标/进度条 | ✅ | A + `MDL3.gui` 画布（§6.1.6） |
| 显示背包状态/护盾值/飞行背包冷却 | ✅ | A，`D.backpacks()`（§6.1.5） |
| 显示队友增强剂/自己身上的状态效果 | ✅ | A，`D.buffs()` |
| 做一个漂亮的图片/贴图界面 | ✅ | `MDL3.gui` + `gui_assets.py` 打包 PNG |
| 加音效提示、循环 BGM、按距离远近 | ✅ | A + `MDL3.audio`（§6.1.7） |
| 按键触发动作/快捷开关 | ✅ | A，选项 + 引擎 API |
| 敌人高亮/标记/测距/提前量 | ✅ | A：读单位位置 + `Gui` 画，本地生效 |
| 自动瞄准/自动开枪 | ⚠️ 只能做"提示" | 读位置可以；替你扣扳机要写输入，接口只读 |
| 换成游戏原生没有的音效文件（mp3） | ⚠️ 要先转码 | 转 PCM16 WAV / ADPCM 再上传 |
| 改伤害/冷却/弹容/无敌等**数值** | ⚠️ 能做，但不走脚本 | C（社区工具），本技能只给边界 |

**做不到就直说**，并给"能做的最接近版本"。不要用"应该可以"糊过去。

---

## 0.6 模型类许愿：别人说「把 XX 换成 YY」时怎么接

AI 不能凭空生成能进游戏的绑定模型。但可以把 80% 脏活做完：查 archive、判可行性、预检素材、出计划、收编 SDK 导出、打包、门禁、部署、排错。Blender 里的对齐/切权重/接材质仍需人（或按脚本）做。

### 只问四件事

| 问什么 | 用来定 | 例子 |
|---|---|---|
| 换哪件？ | 目标 archive / unit | 「B-01 战术甲」「AR-61 步枪」 |
| 换成什么？ | 模型来源与可行性 | 「这个 FBX」「这张图」「把这个 mod 改到另一套甲」 |
| 什么体型/视角？ | 护甲体型、第一人称 | 「Brawny」「第三人称正常，第一人称不穿模」 |
| 怎么算成？ | 验收 | 「装备界面能看到、跑动不穿模」 |

**不要问**：archive ID、unit ID、材质槽、LOD、patch 编号。

### 先做可行性判定（30 秒）

| 用户给的 | 能做吗 | 怎么做 |
|---|---|---|
| 已绑骨、A-Pose 人形（FBX/GLB） | ✅ 护甲/头盔 | §6.2 护甲流程 |
| 没骨骼的静态模型 | ⚠️ 只能武器/道具/静态件 | 不要承诺"自动绑骨" |
| MMD 模型（PMX） | ✅ 但要转 | MMD Tools 导 FBX，或 MMD2HD2 Studio |
| 只有参考图/文字 | ❌ 不能直接做 | 需先找/做模型 |
| 已有护甲 mod 换目标甲 | ✅ | Avatar Rig 或 HD2 Retagger |
| 想改敌人/NPC 模型 | ⚠️ 高风险 | 同骨架替换，先小范围验证 |
| 文生 3D 模型 | ⚠️ 只能静态件/武器外形 | 需重拓扑、展 UV、做材质 |
| 想让队友也看到 | ❌ | 本地资源 mod 做不到 |

### 第一次做：从最小可行开始

按失败成本从低到高：**贴图替换**（10 分钟验通 archive/材质/部署）→ **头盔或静态件**（验 Save Units/重启）→ **单件护甲（胸甲）**（验切分/权重/接缝）→ **整套护甲**。
每一步都跑 `adopt → build → check → install`，不要攒到最后一次测。

### 全自动跑完，只在这几个点找用户

```
doctor → lookup → new --kind model → 预检模型
  ↑                                    ↓
差环境才找用户              有 FAIL 就告诉用户补什么
                                       ↓
                （用户在 Blender 里按 PLAN.md 做，导出 zip）
                                       ↓
                adopt → build → check → install → 重启游戏 → 看装备界面
```

### 交付话术

> ✅「包做好了，已放进 mod 库。打开管理器勾选它 → Deploy → **重启游戏** → 去装备界面看 B-01。资源 mod 不能游戏内热开关。」
> ❌「patch_0 的 unit 资源 ID 是 0x…，gpu_resources 51 MB，已过 TOC 校验。」

### 模型类"做不到"的说法

- 「模型没有骨骼，护甲路线做不了：要么先绑定（给你 Blender 检查清单），要么退成头盔/背包/武器这类静态件。」
- 「这套甲有 Brawny/Lean 两种体型，你只做了一个；另一个要么补，要么 README 写明只支持一种。」
- 「"让队友也看到"本地资源 mod 做不到。」

---

## 0.7 武器替换（最常用的模型路线）

> 按钮级细节见 `SKILL.md §6.2 B1`。武器比护甲简单：**不需要 Avatar Rig，也不要求全身骨骼**；但握把、枪口、瞄具、弹匣、LOD 都有坑。

### 先定"做到哪一层"

| 层级 | 做什么 | 效果 | 适合 |
|---|---|---|---|
| **L1 外观级** | 整枪绑 `boss`，只换外形 | 能拿能开火；枪机/弹匣不一定动 | 第一次做、静态武器、手枪 |
| **L2 功能件** | 按原版顶点组绑 `bolt`/`charging_handle` 等 | 枪机/拉机柄矢量动画正常 | 多数步枪/冲锋枪 |
| **L3 完整** | 调 `attach_muzzle`/`attach_optic`/`attach_mag`/`IK_left` 等 | 瞄具/下挂/弹匣/换弹都对 | 有配件/换弹细节 |

**建议**：第一条从 L1 开始跑通"能拿、能开火、能进游戏"，第二条再做 L2。

### 只问五件事

换哪把（目标 archive/unit）· 换成什么（模型来源）· 做到哪层（L1/L2/L3）· LOD/视角（第一人称要不要）· 怎么算成（验收）。

**遇到「破裂者」「Breaker」这种系列名，必须现场确认子型号**——中文名与英文缩写不是一一对应，改错 unit 的表现是「游戏里这把枪完全没变」：

| 中文名 | 英文名 | archive | unit |
|---|---|---|---|
| SG-225 破裂者 | SG-225 Breaker | `c5a05d09369d0670` | `5050852199397921576` |
| SG-225SP 千发百中「破裂者」 | Breaker Spray & Pray | `c5a05d09369d0670` | `7073132068558755510` |
| SG-225IE 高燃「破裂者」 | Breaker Incendiary | `2fe755e42b659f64` | `13918995818598980231` |

基础型与 SP **同 archive、不同 unit**，只改一个另一个不变。中文名查 `helldivers.wiki.gg/zh` 最可靠。

### 最小可行流程

```
lookup 目标武器 → new --kind model --target-kind weapon → 预检模型
→ 导入 unit → 对齐握把 → 试装（只存 unit）→ 绑 boss/原版顶点组
→ 材质 → LOD → Save Units → Export Patch → adopt → build → check → install → 重启
```

**武器验收四问**：右手握持正确、枪不浮空？枪托/枪管不穿模？第一人称（LOD0）与第三人称（LOD1）都正常？枪口火光、瞄具、弹匣位置对不对？

### 换完枪原版配件外露（必踩，先看这个）

新枪装上后原版**弹匣/枪口件/瞄具浮在新枪外面**——它们是独立 unit，不随主模型消失。R-4 案例里默认弹匣、制退器、瞄具三个全是独立 unit，其中两个在 friendlynames 里**没有名字**。处理顺序：

1. **收 unit**（首选）：`Load(uid) → 只留 lod0 → Merge at Center → Save Unit`，AutoLods 自动补 LOD；换弹动画照播、属性照生效。
2. **挪挂点**（辅助）：注意方向性——`attach_mag`/`attach_underbarrel` 上的东西**向下生长**，要藏得高不是藏得深；`attach_muzzle` 必须留在实际枪口（火光/弹道）。
3. 同一 unit ID 可能同时在主 archive 和配件 archive，patch 按 ID 覆盖，收一次即可。
4. **共用件绝对不能收**（同 archive 其他武器还在用）：先渲染形状确认身份再动手。

完整清单、判定方法与「全局配件隐藏前置」见 `SKILL.md §0.7`。

---

## 0.8 MDL3 dev.43 新能力（2026-11-06，先说清哪些是新东西）

| 能力 | 入口 | 判断版本 | 一句话 |
|---|---|---|---|
| 屏幕绘制 | `MDL3.gui` / `MDL.gui` | `gui.api >= 1` | 矩形/描边/线/三角/圆/文字/图片，参数校验 + 自动清理 + 4K 自适应 |
| 音效播放 | `MDL3.audio` | `audio.api >= 1`（句柄/缓冲 API 1；暂停循环 3D 混响要 `>= 2`） | 带自己的音频资源，不用 wwise bank |
| 3D 定位音频 | `audio play{pos=}` / `{unit=,node=}` | `audio.api >= 2` | 距离衰减 + 左右声道 + 可选多普勒 |
| 混响 | `audio.environment(ns, preset)` | `audio.api >= 2` | 14 个预设 + 自定义；**所有 mod 合计最多 3 种不同设置** |
| 背包数据 | `D.backpacks()` | Hub `>= 0.6.0` | 补给/守卫犬/护盾/跳包/悬浮/传送/炸弹背包 |
| 增强剂与状态 | `D.buffs()` | Hub `>= 0.5.0` | 每人 booster + effects（含层数、剩余时间） |
| 大厅信息 | `D.lobby()` / `D.lobby_search()` | Hub `>= 0.5.0` | 房间 props、搜索列表；账号已脱敏成 `L1/L2` |
| 图片转资源 | `For Modder/gui_assets.py` | dev.41+ 包内 | PNG → patch + gpu_resources + stream |

**诊断窗口的两个变化**（影响排错判断）：① EAC 拦 MDL3 时**不再把游戏卡成"未响应"**；② 诊断窗口**不再自动检查证书**，推荐用 `MDL3-EAC-Fix-Kit-1.0.2`；③ 日志改成"每一步先落盘再执行"，卡住时能看到停在哪一步。

**新约束，先记住再写代码**：

- 文字依赖 MDL3 的原生界面服务；证书/原生服务没起来时**形状和图片照常、文字不显示**，`canvas:status().font == false`。
- 图片**只有已部署的 mod 能显示**（MDL 库里热启动、未部署 → `missing_image` + 日志 `image not loaded`）。
- 混响全局只有 3 个槽；第 4 个 mod 调 `environment` 会先返回 `true` 再在日志里 `reverb slots full`，它保持原环境。
- 未接受的播放请求**不会补播**，`play()` 返回句柄只代表本帧已提交。

---

## 1. 适用范围

### 1.1 适用

- **玩法增强**（单/联机）：信息展示、瞄准辅助、状态监控、操作 QoL、界面重排。**纯 Lua 5.1**，不依赖 LuaJIT。
- **屏幕绘制**：`MDL3.gui` 画布——面板、进度条、文字（自动换行/对齐）、线/圆/三角、PNG 图片；分辨率无关，mod 关闭自动清除。
- **mod 自带音效**：`MDL3.audio`——PCM16/ADPCM、循环、暂停、音高、3D 定位、混响；不需要做 wwise bank。
- **读游戏数据**：`HD2Data` 字段（含 0.6.0 的背包/增强剂/大厅）、`stingray` 对象（单位/世界/相机）、实时事件订阅。
- **模型/资源替换**：护甲、头盔、武器、背包、道具、贴图、材质、**游戏原有音频**——Blender + HD2SDK 改 unit，打包 `.patch_N`（+ `.stream`/`.gpu_resources`）；护甲互换/旧 mod 改目标用 Avatar Rig 法或 HD2 Retagger。
- 数值表调整（只给边界与指路）；发布形态可被 `hd2-mod-cli`、Arsenal、Echelon、HD2MM 任一管理器导入。

### 1.2 技术边界（做不到的事，不是不许做的事）

| 想做的 | 现实 | 出路 |
|---|---|---|
| 脚本里 `require('ffi')` 读内存 | 游戏 VM 已移除 `ffi`/`bit`/`jit`，编译期失败 | 走 `HD2Data`/`stingray`，§6.1.5 |
| 新建游戏里没有的 unit / 自造骨架 | 模型 mod 是**替换**，不是新增 | 选现有 unit 替换；骨架用 HD2 Avatar Rig |
| 静态模型"自动绑骨" | 没有可靠通用自动绑骨，硬做权重会崩 | Blender 绑定/权重传递，或退成静态件 |
| 改动画/状态机 | 属于动画路线，模型路线只保证外观 | 外观先做，动画另开任务 |
| 自己塞 native DLL | 未签名 `577`、签名不在名单 `193`、自签进 `LocalMachine\Root` 仍 `577`【文档】 | 用 MDL3 已签名的桥 |
| 关掉/骗过 EAC | 本技能不覆盖，也没有可靠做法 | — |
| 让改动对同一局其他人生效 | 需联网侧配合；且是 10-20 换 EAC 的直接动因 | 只做本地侧 |

**dev.43 新增能力的边界**（都是 `MDL3.gui` / `MDL3.audio` 明确不提供的，别承诺）：

| 想做的 | 现实 | 出路 |
|---|---|---|
| 世界坐标 → 屏幕坐标 | `MDL3.gui` **不提供**（要相机投影） | 自己用 `stingray` 相机算，或改用 `D.aim().screen` 的准星坐标 |
| 把面板贴在 3D 世界里 | 不支持，只有 2D 覆盖层 | 画 2D 标记指向目标方向 |
| 点击 / 拖动界面 | 不支持鼠标输入 | 用按键 + 选项菜单 |
| 自定义字体 | 不支持，用游戏菜单字体 | 用图片画字（`gui_assets.py`） |
| 运行中把 PNG 变成贴图 | 引擎不支持，必须离线转 | `gui_assets.py` 预转，随 mod 部署 |
| 3D 声音被墙遮挡 | 只做方向 + 距离衰减 + 可选多普勒 | 接受近似，或改用 2D 音效 |
| 超过 3 种混响 | 全局上限，第 4 个静默失败 | 复用预设、共用相同参数 |

> 唯一需要自己权衡的是**封号风险**：Arrowhead 从未发布安全 mod 名单，社区列表与管理器标签都不算官方认证。只在本机生效的读数据/HUD 类改动，与"影响同一局其他人"的改动，风险不是一个量级。

---

## 2. 现状更正（2026-11-05，必读）

网上绝大多数教程停留在 **10 月 20 日之前**，照做必失败。详见 `SKILL.md §2`。

### 2.1 反作弊：不是"一直有 EAC"，是 10-20 才换过来

| 时间 | 事件 |
|---|---|
| 10-20 之前 | **nProtect GameGuard**；所有"关 EAC 才能 mod"的教程说的是错的系统 |
| 10-19 | Arrowhead 公告要换反作弊 |
| **10-20** | **7.2.0 上线，GameGuard → Easy Anti-Cheat (EAC)**，并追加额外安全工具 |
| 10-22 | 7.2.1 修"squad 进出崩溃" |
| 10-27 | 官方发布启动崩溃清理指引（清残留 mod/注入器/GameGuard 文件/校验文件） |

**关键更正**：EAC 上线**没有**拦下 Lua mod。mod 大面积失效的真实原因是同一次更新把 **Lua 运行时从 LuaJIT 换成内置 PUC-Rio Lua 5.1**：

- `ffi`/`bit`/`jit` 从**游戏 VM** 消失 → 脚本层拿不到 `ffi`，对所有加载器成立。
- 但"读内存"**没完全死**：MDL3 自带 FFI，用**签名 native 桥**在宿主侧读，再经 Data Hub 供给脚本。老 FFI mod 不是永久失效，是**必须按新 API 重写**（作者原话：*Need to update, Cause I rebuild the api*）。见 §2.2.1。
- `core/wwise/lua/wwise_flow_callbacks` 被移除 → 依赖它的 Bingus Shared Loader 加载链断裂。
- 游戏**仍然**从 mod 加载启动脚本、**仍然**每帧跑 Lua update —— 这是新加载器能工作的缝隙。

### 2.2 现在能跑什么、不能跑什么

| 类别 | 状态 | 说明 |
|---|---|---|
| 纯 Lua 5.1（只用游戏 Lua API） | ✅ | units / lights / lines / 屏幕文字 / 按键 / 网络字段 |
| `require('ffi')` / `bit` / `jit` / `goto` / LuaJIT 字节码 | ❌ | 游戏 VM 内无这些库，编译期失败，任何加载器一样 |
| 读游戏私有数据（血量/弹药/敌人/事件） | ✅ | 走 `HD2Data`；老 mod 需重写 API |
| 写回游戏数据（改内存/改状态） | ⚠️ 只读 | MDL3 预览版关了写入；改数值走路线 C |
| 资源/模型替换（贴图、材质、音频、护甲、头盔、武器、道具） | ✅ | `.patch_N`，与 Lua 运行时无关；模型走 Blender + HD2SDK，装完必须重启 |
| 盘上数值表 `.dl_bin` | ✅ | 需解封密钥 + 重算哈希，§6.3 |
| 未签名 native DLL | ❌ | EAC 签名校验（MDL3 的桥是已签名例外） |

#### 2.2.1 `ffi` 有两层，不要混为一谈

| 层 | 10-20 之后 | 谁受影响 |
|---|---|---|
| **脚本层**：`.lua` 里 `require('ffi')`/`bit`/`jit` | ❌ 彻底没有 | 所有直接调 ffi 的脚本，**任何加载器都救不了** |
| **加载器层**：MDL3 的签名 native 桥，宿主侧用 FFI 读内存 | ✅ MDL3 预览版具备 | 数据经 `HD2Data` 以字段形式给脚本，**只读** |

- "老 FFI mod 丢进来就能跑"错（API 重建过，须按 Data Hub 字段重写）；"任何加载器都救不回来"也错（MDL3 恢复的是**读**能力，不是脚本里的 `ffi`）。**写能力没开放**（作者：预览版纯读取），改数值走路线 C。
- 迁移成本看它**读什么**：只读血条/弹药/HUD → 可行；要改数值/状态 → 回路线 B/C。

> 一句话：**`ffi` 从脚本里消失了，MDL3 把"读"接了回来；"写"没接，要用就走数值表。**

### 2.3 加载器生态（会互相打架，只能有一个占启动槽）

| 加载器 | 状态 | 定位 |
|---|---|---|
| **MDL3**（dev.43 预览 + HD2 Data Hub 0.6.0，桥 DLL 0.4.5） | ✅ 新生态主力 | **游戏内**管理：开关/重载/报错/帧耗时；**自带 FFI**（只读）；**`MDL3.gui` 绘图 + `MDL3.audio` 音效**；**不替代 mod 管理器** |
| **Chef Shared Loader**（1.4.x） | ✅ | 多 mod 并存、独立沙箱、F9 统一选项菜单、崩溃保护 |
| **Boot Mod Loader** | ✅ | 老牌共享加载器，0.13.0+ 可与 Chef 交接 |
| **Bingus Shared Loader** | ⚠️ | v20 在本版本不启动；v21 需别的加载器接管 |
| **VeganSquid Lua 加载器 0.11.0** | ✅ | 10-27 发布，替代启动脚本，兼容 `-- HD2-Addon:` |

**铁律**：游戏只有**一个**启动脚本槽。多个同时部署 = 只有优先级最高的生效，其余"装了但没跑"。

### 2.4 MDL3 的四个必须知道的约束【文档】

1. **必须先装中间证书**：`mdl_native_bridge.dll` 是签名组件（dev.43 仍是 0.4.5，DLL 未变），EAC 校验证书链。缺证书 → 没有「MDL3 设置」页，或报 **error 193 / "不受信任的系统文件"**。修：包内 `MDL3-EAC-Fix-Kit-1.0.2` → `2_FIX_CERT_ADMIN.bat`（装 Certum Code Signing 2021 CA）→ **重启电脑**；仍不行再 `3_REPAIR_EAC_ADMIN.bat`。**不关闭任何安全功能，也不要关杀毒/加白名单**。
   - dev.43 起：诊断窗口**不再自动检查证书**，改为推荐修复包；EAC 拦截时**不再把游戏卡成"未响应"**；进游戏后也可按 **F1** 装证书（有机器会卡，卡了就用修复包）。
2. **必须最高优先级**：MDL3 自带启动脚本，自带 boot 的 mod 排在它后面会让 MDL3 不启动。
3. **预览版纯读取**：Data Hub 只读；且 patch 文件**超过 512 个**读不全（保护性上限）。
4. **两条与 dev.43 新接口绑定的资源限制**：混响**全局最多 3 种不同设置**（参数完全相同可共用）；`MDL3.gui` 文字依赖原生界面服务（`status().font`），证书没装好时**只有文字消失**，别当成画错了。

> 路径注意：用户名含系统语言不支持字母（英文系统上的中文/西里尔用户名）时，MDL3 文件在 `C:\ProgramData\MDL3`、设置与本地 mod 在 `C:\ProgramData\MDL\Helldivers2`；中文系统上的中文用户名不受影响。菜单显示异常时可在 `%LOCALAPPDATA%\MDL\Helldivers2\MDL.cfg` 的 `ui` 表加 `incremental_draw = false,`。

---

## 3. 三条路线 · 路由判据

路由见 §0 表：行为 → A（§6.1，唯一能改"行为"的路线）；外观 → B1–B4（§6.2）；数值 → C（§6.3）。B 不改 Lua、不需要 MDL3，装完必须重启。

**屏幕绘制（`MDL3.gui`）和音效（`MDL3.audio`）属于路线 A**，不是独立的第四条路线：它们只是脚本里的两个能力，跟着 `src/main.lua` 一起打包、一起开关。要"换掉游戏原版枪声/音乐"才落到 B4b。

**混合 mod 允许**：一个包可同时含 Lua 与模型/贴图，但 **MDL3 只能开关脚本部分**；资源部分标 `LAUNCH ONLY`，仍需管理器部署 + 重启。

---

## 4. 会毁掉成果的错误（工程清单）

> 不是规矩，是踩出来的坑。**P0 = 毁数据/毁库/白干；P1 = 一定失败；P2 = 浪费时间。**

### P0 · 不可逆

| # | 别这么干 | 后果 | 自检 |
|---|---|---|---|
| **1** | **游戏运行中**部署/替换/删除 `data/` 下 patch | 文件被占用 → 部署半途失败 / 读到半个包 → 崩溃或静默损坏 | `tasklist \| findstr /i helldivers` 必须为空 |
| **2** | 直接编辑**游戏目录里**的 `9ba626afa44a3aa3.patch_N` | 管理器用**硬链接**部署，那就是库文件的第二个名字 → 改的是库，所有引用一起坏 | 只改库里的文件，改完重新 deploy |
| **3** | 往唯一启动脚本槽里塞**第二个加载器** | 只有一个生效，症状是"mod 时灵时不灵"，极难排查 | 只选一个；`hd2qd lua` 看归属 |
| **4** | 改 `.dl_bin` 后**不重算内容哈希**就重封 | 启动 `0xC000000D`，或静默不生效（更糟） | 走 §6.3 哈希闸门 |
| **5** | 改已发布 mod 的 `manifest.Guid` | 管理器认成另一个 mod，新旧双份共存互相覆盖 | Guid 生成一次永久冻结 |
| **6** | 把 **HD2 Data Hub 打包进自己的 mod** | 重复 Data Hub，与 MDL3 自带的冲突 | 依赖写 README，不打包 |
| **7** | 同时用两个管理器部署 | 互相覆盖部署记录，归属错乱 | 只用一个；换管理器先 `purge` |
| **8** | 库里已有同名目录还硬装 | 覆盖旧版或别人的 mod | `install` 默认拒绝，确认要覆盖再加 `--force` |
| **M1** | SDK **Write Patch** 直接写游戏 `data/` 不先清场 | 覆盖已部署的 `patch_0`，别的 mod 一起坏 | 写前备份 `data/*.patch_*` 或先 `purge`；导出后删掉 SDK 写的那份 |
| **M2** | SDK 写的 patch 留在 `data/`，又用管理器部署同一套 | 双份 patch、编号冲突、改了没效果 | 导出 zip 后清掉 SDK 产物，再走管理器 |
| **M3** | 只做 Brawny 或只做 Lean 就宣称"整套甲可用" | 另一种体型看不到/错位 | 补另一种体型，或 README 写明 |

### P1 · 一定失败

| # | 错误 | 症状 | 正确做法 |
|---|---|---|---|
| **9** | 写 `ffi`/`bit`/`jit`/`goto`/发 LuaJIT 字节码 | 编译期失败（VM 是 PUC 5.1） | 读数据走 §6.1.5 |
| **10** | 资源 `file_id` ≠ `murmur64(模块路径)` | 包里有脚本，加载器找不到/静默不执行 | `check` 会算；改 `file_id` 时三处同步 |
| **11** | 首行 `-- HD2-Addon:` 与真实模块路径不一致 | 被别的加载器抢走或跳过 | 必须**逐字符**等于 `mods/<作者>/<名字>` |
| **12** | `manifest.Options[].Include` 指向不存在的文件夹 | 部署 0 文件或报缺文件 | `check` 会比对 |
| **13** | 跨 option 文件夹连续编号 `patch_0/1/2` | 管理器**重新编号**，你写的被覆盖、内容错位 | 每个 option **各自从 `patch_0` 开始** |
| **14** | 模块路径用中文/空格/大写 | 哈希与路径在部分加载器上不一致 | 只用 `[a-z0-9_]` |
| **15** | 把游戏内部偏移/绝对地址写进脚本 | 每次更新必崩，且崩在别人机器上 | 只用公开 API 与 Data Hub 字段 |
| **16** | patch 超过 512 个 | MDL3 读不全（保护性上限，dev.43 仍在） | 合并资源，控制包数 |

#### GUI / 音频路线追加的 P1（dev.41+）

| # | 错误 | 症状 | 正确做法 |
|---|---|---|---|
| **G1** | 不用 `MDL3.gui`，自己拼裸 `Gui` 图元 | 参数错一个就**整局崩溃**；`Gui.resolution()` 返回两个值，直接当宽用必错位 | 一律走 `gui.canvas()`；裸 `Gui` 只作 dev.41 之前的兜底 |
| **G2** | 每帧改文字内容或位置 | 该画布**整个重建**，比它层级高的画布也跟着重建 → 掉帧 | 变化的数字放**单独的高层画布**，刷新降到 1 Hz |
| **G3** | 静态面板和每帧变化的数字画在同一画布 | 静态部分被反复重建，白烧性能 | 静态 `layer=40`、动态 `layer=60`，分开画布 |
| **G4** | 一个 mod 开超过 16 个画布 / 单画布超 4000 图元 | 超出部分**静默丢弃**（只写日志） | 合并画布；图元复用；先算数量再画 |
| **G5** | 依赖 `Gui.update_text` / `Gui.bitmap_uv` / 对无贴图材质 `set_texture` | 崩溃或完全无效 | `MDL3.gui` 已避开这三个，别自己回去调 |
| **G6** | 在 MDL 库里**热启动未部署**的 mod 测图片 | `status().missing_image` 有名字、日志 `image not loaded` | 必须经管理器 Deploy（`Include: ["data"]`）后再测 |
| **G7** | PNG 边长非 2 的幂 / 尺寸大 | 未压缩 RGBA 带全 mip：512²≈1.3 MB，4096 上限 | 64/128/256 为主；一张图别超 512² |
| **G8** | 文字不显示就当画布写错 | 实际是 `canvas:status().font == false`（原生界面服务没起来） | 先装证书/修 EAC，形状图片会先正常 |
| **A1** | 同一 ns 里混不同采样率/声道/编码 | `define_format` 或 `upload` 失败 | 一个 ns 一种不可变格式；换格式先 `release(ns)` |
| **A2** | 改 voice 池形状前不 `release` | `pool()` 返回 false | 改池/换格式：`release(ns)` → 重新 `define_format`/`pool` |
| **A3** | 同一 key 换了内容再上传 | 被拒（同 key 内容不可变） | 换内容就换 key 名 |
| **A4** | 认为 `play()` 返回真就等于出声 | 只代表本帧已提交；voice 满直接返回 `false`，**不排队不补播** | 检查返回值；关键提示做降级（HUD 文字兜底） |
| **A5** | 每个 mod 都自定义一套混响 | 全局 3 槽用尽，第 4 个静默失败（`reverb slots full`） | 优先用 14 个预设；参数完全一致可共用；不用就别调 |
| **A6** | 单音效过大 | 单文件 ≤ 约 9 MiB / 12000000 base64 字符 | 剪短、降采样、或改 ADPCM |
| **A7** | `on_disable` 不 `release(ns)` | 占着配额和混响槽，其它 mod 拿不到 | 停用必 `release(ns)` |
| **A8** | 3D 定位声用立体声素材 | 先被混成单声道再定位，带宽白花 | 3D 声源用单声道素材 |

#### 模型 / 武器路线追加的 P1

| # | 错误 | 症状 | 正确做法 |
|---|---|---|---|
| **M4** | `Force 3 UV Sets` 关着，mesh 只有 1 个 UVMap | 模型**完全不可见** | 开 `Force 3 UV Sets`（复制到 2/3 套） |
| **M5** | 材质槽数量超过目标 unit | 启动即崩/装备界面崩 | 不超过原版槽数；多套贴图并 atlas |
| **M6** | 只 Save Units，没 Save Materials | 模型在，材质/贴图不显示 | 开 `Save Textures with Material`；原版材质也要 Save |
| **M7** | 只改 LOD0（LOD 相关 unit） | 某些部件/子弹/弹夹消失 | 关 `Auto LODs`，逐 LOD 复制属性/减面 |
| **M8** | 没骨骼/没权重就上护甲 | 拉伸、扭曲、原地不动 | 先绑 HD2 骨架 + 权重传递；上臂绑 `shoulder_twist` |
| **M9** | 合并法里 UV 层不叫 `UVMap` | 材质错乱/不可见 | 合并前重命名为 `UVMap` |
| **M10** | 带形态键/未应用缩放就 Save | 导出失败或尺寸不对 | 应用/删除形态键，`Ctrl+A` 应用缩放 |
| **M11** | 贴图不是正方形/不是 2 的幂，或法线用 DirectX | 黑紫、拉伸、加载失败 | 512/1024/2048/4096 正方形；OpenGL 法线 |
| **M12** | 头盔去护甲 archive 找（或反之） | 做完没变化 | 头盔与护甲在不同 archive，分别加载 |
| **M13** | 用旧 ID Swapping 做护甲互换 | 每个新 patch 都要重做，易冲突 | 用 Avatar Rig 法（§6.2 B3） |
| **M14** | 拿别人的模型/贴图直接发布 | 版权投诉/下架 | 只用有授权素材，README 写 `THIRD_PARTY.md` |
| **M15** | 握把没对齐/缩放没应用/原点错 | 枪浮空、巨大像玩具、枪托穿模 | 对齐原版握把；`Ctrl+A`；复制原点 |
| **M16** | `attach_muzzle` 没对准 | 枪口火光/弹道起点歪 | Edit Mode 移动骨骼，或改枪管长度 |
| **M17** | `attach_optic`/`sight` 没对准 | 瞄具浮空/军械库渲染错位 | 移动骨骼；确认瞄具是否独立 unit |
| **M18** | 弹匣没挂 `attach_mag`/位置没调 | 换弹穿模/弹匣飞出去 | Child Of 挂 `attach_mag`；Edit Mode 移动后重存 |
| **M19** | 想保留枪机/拉机柄动作却整枪绑 `boss` | 枪机不动、拉机柄不跟手 | 按原版顶点组绑 `bolt`/`charging_handle` |
| **M20** | 把「千发百中/SP/高燃」当同一个 unit | 游戏里那把枪**完全没变** | 见 §0.7 子型号表 |
| **M21** | 脚本写死 `MeshInfoIndex == 8` 选 LOD0 | 静默改到 LOD1，细节降一档 | 按 `*_lod0` 选，兜底取顶点最多 |
| **M22** | 用 SP 的包围盒做缩放基准 | 整枪拉长约 7%（含鸭嘴枪口/弹鼓） | 用基础型机匣长度 `0.9161 m` |
| **M23** | 换整枪后不动 `attach_*` 骨骼 | 原版枪口配件全露、瞄具/弹鼓半露 | 收进新模型，或对准新枪口/顶面/弹匣井（`weapon-pipeline.md` §5.9） |
| **M24** | 想靠挪 `attach_mag` 藏弹鼓 | 弹鼓 0.28 m 高，塞不进枪身，从下方穿出 | 直接收弹匣 unit 网格（LOD0 全选 → Merge at Center → 1 顶点 0 面） |

### P2 · 会浪费时间

| # | 错误 | 说明 |
|---|---|---|
| **17** | 在"已经装了一堆 mod"的环境上做基线测试 | 分不清自己坏了还是别人冲突 |
| **18** | 不记 build 号就宣称"能用" | 下次更新无法判断回归还是环境变了 |
| **19** | 不保留可复现构建（源码 + 打包参数） | 只能改二进制，等于不可维护 |
| **20** | 用第三方 `verify` 通过就认为"容器完全正确" | 只验资源层；`srkit pack` 还会留陈旧的"自身长度"字段【实测】 |
| **21** | 在 Git Bash 里用 `/tmp/xxx` 传路径给 Windows Python | Git Bash 的 `/tmp` ≠ Python 的 `C://tmp`，报文件不存在【实测】 |

---

## 5. 标准作业流程（Step 0–8）

> 顺序不可调换。每步有**合格判据**与**停的条件**。

### Step 0 · 立项卡（5 分钟，不写代码）

```
玩法目标：<一句话，例：给飞行目标显示提前量准星>
改动边界：<只读 / 只画 / 不改他人状态>
依赖：    <MDL3 / Chef / 无>
失败样子：<怎么算没做成>
```

**停**：说不清"玩家看到什么变化" → 回去问，不要开始写。

### Step 1 · 环境体检

```bash
python tools/hd2mod.py doctor
```

正常输出：`[ OK ]` 游戏目录 / build 26251122 / 反作弊 EAC 已就位 / mod 库 / 管理器数据 / 加载器；`[ -- ] srkit 未配置`（Lua 路线不需要）。

找不到游戏/库：

```bash
python tools/hd2mod.py set-game "X:/Steam/steamapps/common/Helldivers 2"
python tools/hd2mod.py set-lib  "X:/HD2 Mods"
```

路径记到 `~/.hd2-gameplay-mod/config.json`。**还要确认游戏已退出**：

```bash
tasklist | findstr /i "helldivers" || echo "OK: 游戏未运行"
```

**合格**：`doctor` 通过，且 build 号记下来了。

### Step 2 · 选载体 + 定模块路径

- 格式 `mods/<作者>/<名字>`，全小写、下划线分隔。例：`mods/aabc/anti_air`。**发布后不可改**（改了等于新 mod，资源 ID 也变）。
- 立刻算资源 ID 并记下来：

```bash
python -m srkit hash "mods/<作者>/<名字>"
# mods/aabc/anti_air   murmur64=0x37FCC0A04812EAB6 murmur32=0x37FCC0A048
```

### Step 3 · 建工程

```bash
python tools/hd2mod.py new \
  --author <作者> --name <名字> --title "<显示名>" --out "<库>/_src/<名字>"
```

`--author`/`--name` 只用小写字母数字下划线（会进模块路径）。`--out` 建议放库旁 `_src`，与部署库分开。产出：

```
<名字>/
├── manifest.json          # 管理器识别（Guid 已生成，永久冻结）
├── mod.project.json       # 构建参数（module 就是 mod 身份）
├── README.md              # 依赖声明（必须写）
├── CHANGELOG.md
├── src/main.lua           # 你只改这个
└── dist/                  # build 之后才有
```

### Step 4 · 写脚本（路线 A 的核心）

只改 `src/main.lua`，骨架已带首行声明与生命周期，**不要动第一行**：

```lua
-- HD2-Addon: mods/<作者>/<名字>
local M = {}

function M.on_enable(context)  end   -- context.settings / context.log
function M.on_update(context, dt) end -- 每帧；dt 秒
function M.on_disable() end           -- 释放自己创建的一切

return M
```

细节（上下文、选项、nil 纪律）见 `SKILL.md §6.1.4` 与 §7.1。

### Step 5 · 打包

```bash
python tools/hd2mod.py build "<工程目录>" --zip
```

内部做的事（**不依赖 srkit**）：① 校验首行声明 == `mod.project.json.module`；② `file_id = murmur64(module)`；③ 按已知格式生成单 lua 资源的 `9ba626afa44a3aa3.patch_0`；④ 落到 `dist/<ModName>/<Option>/`；⑤ 复制 manifest/README/CHANGELOG/cover。

**合格**：产物字节数 = `192 + 8 + 脚本字节数`；`file_id` == 模块路径哈希。
这条路已与真实可加载包**逐字节比对**（同输入→同字节），并用 srkit 交叉验证（`list` 认得出 ID，`check` 往返一致）。

### Step 6 · 静态门禁（不通过别部署）

```bash
python tools/hd2mod.py check "<工程目录>"
```

| 检查 | 判据 |
|---|---|
| 声明 vs 路径 | 首行 `-- HD2-Addon:` == `mod.project.json.module` |
| 资源 ID | `file_id == murmur64(module)` |
| 包自洽 | 头部自长度 == 实际文件长度；payload 长度 == 脚本长度 |
| manifest | Guid 合法；Name/Version/Options 齐全 |
| 数量 | patch ≤ 512（MDL3 上限） |
| Lua 5.1 | 无 ffi/bit/jit/goto/位运算/BOM |
| 编码 | UTF-8 无 BOM |
| 体积 | 单脚本 ≤ 4 MB（Chef 上限） |
| 伴生文件 | 有 `data/` 就必有 `data/*.patch_N` + `.gpu_resources` + `.stream` 三件套；manifest 含 `"Include": ["data"]` |
| GUI 用法 | 取 `gui` 前判了 `nil` 与 `gui.api`；`on_disable` 里 `destroy()` 了每个画布；`image` 名与 `images.txt` 一致 |
| 音频用法 | 取 `audio` 前判了 `nil`；`play` 的 `false, reason` 有分支；`on_disable` 调了 `release(ns)`；同 ns 的 WAV 参数一致 |

### Step 7 · 部署与实机验证

```bash
python tools/hd2mod.py install "<工程目录>"
```

它会：把 `dist/` 成品复制进库 → 有 `hd2qd` 就 `add`+`deploy` → 否则打印"拖进管理器点 Deploy"。
> 用户只需记住：**打开管理器 → 勾选新 mod → Deploy → 进游戏按 ESC**。

实机四问逐条记录：① 加载器认到了吗（MDL3 菜单 / Chef F9）？② 有报错吗（`%LOCALAPPDATA%\MDL3\Logs\MDL3.log`、`%APPDATA%\Arrowhead\Helldivers2\boot_mod_loader.log`）？③ 效果对了吗（对 Step 0 的"失败样子"比）？④ 关掉能干净退出吗（无残留绘制、无帧耗时上升）？

带 GUI/音频的包再加三问：⑤ 画布内容对得上吗（`cv:status()` 的 `items`/`font`/`missing_image`）？⑥ 帧耗时有没有涨（HUD 静态不动时不该涨；涨了就是每帧重建）？⑦ 关掉后还有声音/图形残留吗（没有 `release`/`destroy` 就会残留）。

### Step 8 · 归档

见 §10。**没归档等于没做完**，下次更新无法复现。

### 5.9 模型路线（B）的 Step 0–8

> 与 Lua 流程**并行**，不要混。不写 `src/main.lua`，不需要 MDL3。细节见 `SKILL.md §6.2`。

| Step | 做什么 | 命令/判据 | 停的条件 |
|---|---|---|---|
| **0** | 立项卡：换哪件/换成什么/体型/验收 | 写进 `PLAN.md` | 说不清"进游戏看到什么" → 停 |
| **1** | 环境体检 | `doctor`；Blender + HD2SDK 就绪 | 缺 Blender/SDK → 先装 |
| **2** | 查目标 archive | `lookup "B-01"` | 搜不到 → 让用户在 SDK 里用英文名搜 |
| **3** | 建模型工程 | `new --kind model --target-kind armor` | 目标类型/体型没定 → 停 |
| **4** | 素材预检 | `blender -b --python tools/blender_preflight.py -- "模型"` | 有 `[FAIL]`（无骨骼/无 UV）→ 先补 |
| **5** | Blender 里做外观 | 按 `PLAN.md`：导入 unit → 对齐 → 切分 → 权重 → 材质 → Save Units | 没对齐/权重裂 → 不写 patch |
| **6** | 导出并收编 | SDK `Export Patch` → `adopt <工程> --from <zip>` | 没有 patch/解析失败 → 停 |
| **7** | 打包 + 门禁 | `build --zip` → `check` 全绿 | 缺伴生文件/没 unit → 修 |
| **8** | 部署 + 实机四问 | `install` → Deploy → **重启游戏** → 装备界面/第一/第三人称/LOD | 不可见/拉伸 → §9 |

**模型路线合格判据**：`check` 输出 `门禁通过：模型工程` 且 `unit` ≥ 1；装备界面能看到新外观（非透明/原版/黑紫）；第三人称不扭曲、第一人称不穿模；关掉能恢复原版。

> **武器替换**把 Step 4–6 换成：对齐握把 → 试装（只存 unit）→ 绑 `boss`/原版顶点组 → 调 `attach_muzzle`/`attach_optic`/`attach_mag`；其余相同（`SKILL.md §6.2 B1`）。

---

## 6. 三条路线的具体配方

### 6.1 路线 A · Lua 玩法脚本

#### 6.1.1 包结构

```
<ModName>/
├── manifest.json
└── Core/                                  ← 名字随意，但要与 manifest 的 Include 一致
    └── 9ba626afa44a3aa3.patch_0           ← 文件名固定，编号由管理器重排
```

`manifest.json` 最小可用：

```json
{
  "Guid": "8f3c1e2a-9b4d-4c7e-8a51-2d6f0c9b1e33",
  "Name": "我的玩法 MOD v1.0.0",
  "Description": "一句话说明 + 依赖声明（需 MDL3 / 或无需加载器）",
  "Version": 1,
  "IconPath": "cover.jpg",
  "Options": [
    { "Name": "核心 / Core", "Description": "必选", "Include": ["Core"] }
  ]
}
```

- `Version` 是 **manifest 语法版本，固定 `1`**，不是 mod 版本号；对外版本写进 `Name`。
- `Guid` 用 UUIDv4，**生成一次永不改**。
- `Options` 可多个，各对应一个文件夹，就是安装时的勾选项；`Image` 可选。

#### 6.1.2 资源 ID 规则（最容易错的一条）

`.patch_0` 里 `lua` 资源的 `file_id` **必须**等于 `murmur64("mods/<作者>/<名字>")`。引擎按名字解析资源，名字→ID 就是 murmur64；不匹配等于"资源存在但没人叫得出名字"。
`srkit list` 里 `name` 列为空是正常的 —— 这个包没有名字表，名字由 ID 反推。

#### 6.1.3 手工打包（只在排错时用）

正常路径是 `hd2mod.py build`，**不需要 srkit**。手工解包/改三处（`package.json` 的 `file_id`+`resource_dir`、`resource.json` 的 `file_id`、`lua_<16位大写ID>` 目录名）/重打/验证的完整命令与字节结构见 `SKILL.md §6.1.3`。

**两个 srkit 行为**【实测】：① `pack` 按 16 字节对齐 → 产物长度与原件不同，判据是 `verify`（资源层）与 `list`（ID 层），不是 `cmp`；② `pack` **保留源包的"自身长度"字段**（头部 `0x20`）→ 重打后尺寸变了字段还是旧值。所以 **Lua 包优先用 `hd2mod.py build`**。

#### 6.1.4 脚本契约【推断，已在一个实机可用 mod 上验证】

模块返回一个表，加载器按名字调：

| 成员 | 何时调 | 你要做什么 |
|---|---|---|
| `on_enable(context)` | 启用时 | 读 `context.settings`、注册选项、建状态 |
| `on_update(context, dt)` | 每帧 | 主逻辑；`dt` 秒，**必须判 `dt>0 and dt<1`** |
| `on_disable()` | 停用时 | 销毁 GUI、清表、置 nil |
| `diagnostics()` | 排错时 | 返回一张可打印的表 |

可用全局（用 `rawget(_G, ...)` 取，直接索引缺失会抛错）：

| 全局 | 用途 |
|---|---|
| `stingray` | 引擎 API 表（§7.2） |
| `HD2Data` | **Data Hub**：MDL3 用 FFI 读出的数据（血量/弹药/敌人/事件），只读（§6.1.5） |
| `MDL3` | 加载器句柄，判断"我是不是在 MDL3 下跑" |
| `MDL` | 含 `MDL.i18n.code`（语言码），做中英双语 |
| `ModOptionsMenu` | 选项菜单；`provider == 'MDL'` 时才有 `register_option`/`get` |

**为什么必须 `rawget`**：换加载器时这些全局可能不存在，直接 `MDL3.xxx` 会 nil 索引崩在别人机器上。

#### 6.1.5 读游戏数据的三条路径

10-20 之后 `ffi` 从脚本 VM 消失，但**读内存这件事本身没被禁** —— MDL3 靠自己的签名 native 桥把读能力接回来，只是入口变了。

| 路径 | 拿到什么 | 稳定性 | 什么时候用 |
|---|---|---|---|
| **1. `HD2Data`** | 血量、弹药、队友、武器、战略配备、打击、事件 | 最高，官方维护 | **优先**，字段够用就别绕 |
| **2. `stingray`** | 引擎对象：单位、世界、相机、GUI | 高，接口可能随版本变 | Data Hub 没暴露的（按资源筛单位、算弹道） |
| **3. 原生 FFI** | 任意内存 | 低，脚本侧不可得 | 只有 MDL3 作者能扩 |

**路径 3 的现实**：`ffi` 是 MDL3 内部实现，脚本里 `rawget(_G,'ffi')` 拿不到。缺字段就两条路——去发布页提需求，或自己算（路径 2 常能凑出来）。自己编译 native DLL 塞进去走不通（`577`/`193`，见 §1.2）。

##### 路径 1：`HD2Data`

```lua
-- 不在顶层缓存：加载顺序不固定，Hub 被关掉后这个全局会消失
local function hub()
    local D = rawget(_G, 'HD2Data')
    if type(D) == 'table' and D.ready() then return D end
    return nil
end
```

三条硬规矩：① **每次用时再取**，不要 `local D = HD2Data` 放模块顶部；② **所有字段都可能是 `nil`**，必须判空；③ **第一次调用当帧返回 `nil`**，数据晚一帧；带租约的接口（`player`/`players`/`aim`）只在调用后 3 秒内每帧更新。

常用入口（Hub 0.6.0）：

| 调用 | 拿到什么 | 租约 |
|---|---|---|
| `D.player()` / `D.player_ammo()` | 血量、位姿、当前武器与弹药（`player_ammo` **只有一个返回值**） | `player`/`ammo`，3 秒 |
| `D.players(detail)` | 小队；`detail=true` 加武器/装备/手雷/针，0.5 起队友弹药也同步 | `players(_detail)` |
| `D.aim()` | `camera_point, impact, target, distance, camera, forward, screen{x,y,depth}, aiming` | `aim` |
| `D.stratagems()` / `D.stratagem_catalog(t)` | 战备剩余次数/冷却；目录含 `code` 指令序列 | `stratagems` |
| `D.backpacks()` | **0.6 新**：每人背包 `type/fill/low` + 分类型字段（见下） | `backpacks` |
| `D.buffs()` | **0.5**：`team` 增强剂 + `players[].booster/effects` | `buffs` |
| `D.lobby()` / `D.lobby_search()` | **0.5**：房间 props / 搜索结果（账号已脱敏为 `L1/L2`） | `lobby(_search)` |
| `D.strikes()` / `D.strike_catalog(k)` | 进行中的打击、打击目录 | `strikes` |
| `D.enemy_pool(refresh)` | 本站任务预测敌人池（静态分析结论，未实机对照） | 计算一次后缓存 |
| `D.mission()` | 当前任务信息 | `mission` |
| `D.build()` / `D.version()` / `D.api()` / `D.state()` / `D.diagnostics()` | 游戏 build、Hub 版本/接口版本、状态、排错快照 | 无 |
| `D.on(event, cb, opts)` | 16 个事件（`entity_spawned/damaged/died/killed`、`player_fired/hit/damage_dealt/kill_credited`、`explosion`、`stratagem_called/used`、`strike_started/ended`、`mission_started/ended`、`bughole_destroyed`）；`opts={owner,id,priority}`，回调连续错 25 次停用 | 只算被订阅的 |

`D.backpacks()` 的 `type` 与 `fill`（HUD 同款判定顺序，照抄别猜）：

| type | 是什么 | fill |
|---|---|---|
| `deposit` | 补给/弹药背包、供弹备弹包 | `count/max` |
| `guard_dog` | 守卫犬（含 `refills`、`drone.weapon.rounds/capacity/heat`、`docked`、`action`） | 弹量比或 `1-热量/上限` |
| `shield` / `directional_shield` | 护盾背包 / 定向护盾（`shield.value/max/up/broken/recharging`） | 破盾 0，否则 `max(1,value)/max` |
| `jump_pack` / `hover_pack` / `recharge` | 冷却或燃料类（跳包 `cooldown_left/ready/in_use`；悬浮 `fuel/ready/thrust`） | `1-剩余/上限` |
| `health` | 自带血量（防弹盾一类） | `health/health_max` |
| `warp_pack` | 传送背包（`heat/warn_at/cooling`） | `1-热量/100` |
| `explosive` / `other` | 炸弹背包（`explosive.remaining` 仅主人）/ 其余 | 1 |

字段清单在 `For Modder/hd2data_field_reference_v0_6_0.md`，**不要凭记忆写字段名**。`D.set_option('getters', false)` 可关掉"会调用游戏代码"的读取（0.5 起只剩 `grenades_max`/`stims_max`），用于排错。

##### 路径 2：`stingray`

```lua
local sr = rawget(_G, 'stingray')
if type(sr) ~= 'table' then return end

for _, u in pairs(sr.World.units(world) or {}) do
    if sr.Unit.alive(u) then
        local p = sr.Unit.world_position(u, 1)   -- 可能是 nil
        if p then ... end
    end
end
```

接口清单见 §7.2。**先 `type()` 判存在再调** —— 猜函数名不会编译报错，只会在运行期返回 `nil`。

#### 6.1.6 屏幕绘制：`MDL3.gui`（dev.41 起，api 1）

**先取接口，取不到就整段跳过**（不需要退化到裸 `Gui`，除非要兼容 dev.40 及更早）：

```lua
local function gui_api()
    local m = rawget(_G, 'MDL3'); if type(m) == 'table' and m.gui then return m.gui end
    local mdl = rawget(_G, 'MDL'); if type(mdl) == 'table' and mdl.gui then return mdl.gui end
end
local gui = gui_api()
if not gui or (gui.api or 0) < 1 then return end
```

| 调用 | 说明 |
|---|---|
| `gui.canvas({layer=0..99, units='reference'\|'pixels'})` | 建画布。默认 `layer=50`、`reference`（1080 高基准，4K 自动 ×2） |
| `cv:begin()` … `cv:finish()` | 两个之间画完整一帧；**内容不变重复画不会重新提交** |
| `cv:clear()` / `cv:show(false)` / `cv:destroy()` | 清空 / 隐藏 / 销毁 |
| `cv:screen()` | `{w, h, scale, pixel_w, pixel_h}`，**w/h 是本画布单位下的屏幕尺寸**（宽屏 > 1920） |
| `cv:measure(text, size)` | 一行文字宽度，用于右对齐/居中排版 |
| `cv:status()` | `{items, font, problem, missing_image}` |

图元（坐标原点左上、y 向下，单位=画布单位）：

| 方法 | 备注 |
|---|---|
| `rect(x, y, w, h, color)` | 实心矩形 |
| `frame(x, y, w, h, thickness, color)` | 向内描边 |
| `line(x1, y1, x2, y2, width, color)` | `width` 默认 2 |
| `triangle(x1, y1, x2, y2, x3, y3, color)` | 实心三角 |
| `circle(x, y, r, color, {segments=12..96, ring=粗细})` | 传 `ring` 就是圆环 |
| `text(str, x, y, {size, color, align='left'\|'center'\|'right', valign='top'\|'middle'\|'bottom', max_width, line_height})` | 返回整段宽高；`\n` 强制换行；`max_width` 中文按字、英文按词换行 |
| `image(name, x, y, w, h, {color})` | `name` = `mods/<作者>/<名字>/img/<文件名>`（无扩展名）；`color` 可着色/调透明度 |

颜色三种写法，通道 0–255，`a` 省略=255：`{r,g,b,a}`、`{r=,g=,b=,a=}`、`'#RRGGBB'` / `'#RRGGBBAA'`。

**能跑的完整 HUD 模板**（静态面板 1 个画布、血条 1 个、数字 1 Hz —— 这样才不会每帧重建）：

```lua
-- HD2-Addon: mods/me/hud_demo
local M = {}
local gui, cv_static, cv_bar, cv_text
local acc = 0

local function gui_api()
    local m = rawget(_G, 'MDL3'); if type(m) == 'table' and m.gui then return m.gui end
    local mdl = rawget(_G, 'MDL'); if type(mdl) == 'table' and mdl.gui then return mdl.gui end
end
local function hub()
    local D = rawget(_G, 'HD2Data')
    if type(D) == 'table' and D.ready() then return D end
end

function M.on_enable()
    gui = gui_api(); if not gui or (gui.api or 0) < 1 then return end
    cv_static = gui.canvas({layer = 40})
    cv_bar    = gui.canvas({layer = 60})
    cv_text   = gui.canvas({layer = 70})

    local s = cv_static:screen()
    cv_static:begin()
    cv_static:rect(24, 24, 360, 110, {10, 12, 16, 180})
    cv_static:frame(24, 24, 360, 110, 2, '#FFD500')
    cv_static:text('HD2 HUD DEMO', 40, 36, {size = 22, color = '#FFD500'})
    cv_static:image('mods/me/hud_demo/img/logo', 40, 70, 48, 48)   -- 图片要先 gui_assets 打包
    cv_static:text('screen ' .. s.w .. 'x' .. s.h, 340, 36, {size = 14, align = 'right', color = {120,120,120}})
    cv_static:finish()
end

function M.on_update(context, dt)
    if not cv_bar then return end
    if type(dt) ~= 'number' or dt <= 0 or dt > 1 then return end
    local D = hub(); if not D then return end
    local p = D.player(); if not p then return end

    local hp = p.health_frac or 0                        -- 0..1
    cv_bar:begin()                                       -- 每帧只动矩形：原地更新，不重建
    cv_bar:rect(40, 100, 328 * hp, 10, {150, 222, 120})
    cv_bar:finish()

    acc = acc + dt
    if acc < 1 then return end                           -- 文字 1 Hz 就够
    acc = 0
    local bps = D.backpacks() or {}
    local mine = bps[1]
    local extra = ''
    if mine and mine.backpack then
        local b = mine.backpack
        extra = string.format('  %s %.2f', tostring(b.type), tonumber(b.fill) or 1)
    end
    cv_text:begin()
    cv_text:text(string.format('HP %d/%d%s', p.health or 0, p.health_max or 0, extra),
                 40, 116, {size = 18, color = '#FFFFFF'})
    cv_text:finish()
end

function M.on_disable()
    if cv_static then cv_static:destroy() end
    if cv_bar then cv_bar:destroy() end
    if cv_text then cv_text:destroy() end
    cv_static, cv_bar, cv_text = nil, nil, nil
end

return M
```

**性能守则（照做，不然 HUD 一开就掉帧）**

1. 静态内容画一次，不要每帧重画；`begin/finish` 内容不变不会重新提交。
2. 只有**位置/大小/颜色**变化（血条、进度、跟随标记）→ 原地更新，随便每帧。
3. **文字内容或位置、图片位置、图元种类或数量变了 → 整个画布重建**，比它层级高的画布也重建。所以：数字进单独的高层画布 + 1 Hz。
4. 全局图元排序前约 790 个是精确的，超出共用最上层，**上下关系不保证**。层级用 40/60/70 这种留有间隙的值。
5. 每 mod ≤ 16 画布、每画布 ≤ 4000 图元，超出被丢弃并写日志。

**图片资源（必须离线转）**

```powershell
pip install pillow
python gui_assets.py --mod mods/me/hud_demo logo.png arrow.png --lua src/main.lua --out build
```

- 产出 `build/data/9ba626afa44a3aa3.patch_0` + `.gpu_resources` + `.stream`，把 `build/data` 放进 mod 包，manifest 写 `"Include": ["data"]`。
- 带 `--lua` 时脚本和图片打进**同一个 patch**；脚本首行必须 `-- HD2-Addon: mods/...`。
- `build/images.txt` 列出所有可用图片名；代码里写 `mods/me/hud_demo/img/<文件名>`（无扩展名）。
- 未压缩 RGBA + 全 mip：256² ≈ 340 KB，512² ≈ 1.3 MB；边长用 2 的幂，最大 4096。
- **只有已部署的 mod 能显示图片**；未部署热启动 → `missing_image` + 日志 `image not loaded`。

**验证**：进游戏先看静态面板 → 再看血条动 → 再看数字每秒变；`cv:status()` 里 `font=false` 说明文字依赖的原生服务没起来（先修证书），`items` 能看出是否超 4000。

#### 6.1.7 音效：`MDL3.audio`（api 2，dev.40 起；api 1 写法照常可用）

**资源准备**：PCM16 WAV（单/双声道，8–48 kHz）。同一 `ns` 下所有声音必须**同声道数、同采样率、同编码**。官方离线生成器 `tools/audio_assets.py` 生成 `sounds.lua`（内含 `sounds.format` 与 `sounds.sounds`）：

```powershell
python tools/audio_assets.py kill.wav hit.wav --out sounds.lua
python tools/audio_assets.py kill.wav hit.wav --codec adpcm --out sounds.lua   # MS-ADPCM，体积更小（512 samples/block）
```

> dev.43 的 `For Modder` 里**只带了 `gui_assets.py`，没有 `audio_assets.py`**。手上没有这个生成器时：向作者索取，或自己按 format 声明用 PCM16 做 base64（结构=声道/采样率/编码/block align，必须与上传数据严格一致；不要凭猜写 `format`，`define_format` 会拒）。`sounds.lua` 是纯 Lua 表，用 mod 自己的 `require('sounds')` 加载。

**生命周期**：`define_format` → `pool` → `upload`（每个 key）→ `ready` → `play`；结束时 `release(ns)`。资源可以在服务 ready 前注册，分块/续传/重连重传都由 MDL3 负责。

```lua
local sounds = require('sounds')
local ns = 'mods/me/hud_demo'
local audio

local function audio_api()
    local m = rawget(_G, 'MDL3'); if type(m) == 'table' and m.audio then return m.audio end
end

-- 并入 §6.1.6 的 M.on_enable 末尾调用；不要另起一个 M.on_enable 覆盖掉 GUI 初始化
local function setup_audio()
    audio = audio_api()
    if not audio or (audio.api or 0) < 1 then return end          -- 3D/混响要 >= 2
    assert(audio.define_format(ns, sounds.format))
    assert(audio.pool(ns, {kill = 4, hit = 4, ui = 1}))            -- 角色 -> voice 数
    for key, data in pairs(sounds.sounds) do
        assert(audio.upload(ns, key, data))                        -- data 是 base64 整段
    end
    if (audio.api or 0) >= 2 then
        audio.environment(ns, 'hangar')                            -- 预设；全局只有 3 个混响槽
        audio.listener('camera')                                   -- 默认就用 HD2Data.aim() 的相机
    end
end

function M.play_local(key, opts)
    if not audio then return nil, 'no audio api' end
    local h, why = audio.play(ns, key, opts)
    if not h then return nil, why end        -- voice 满/未就绪：不排队、不补播，自己决定降级
    return h
end

-- 并入 M.on_disable
local function teardown_audio()
    if audio then audio.release(ns) end      -- 必做：释放 voice、缓冲与混响槽
    audio = nil
end
```

| 方法 | 用途 |
|---|---|
| `state()` | `wait/starting/ready/failed/unavailable` + reason |
| `define_format(ns, fmt_b64)` | 一个 ns 一个不可变格式；换格式先 `release` |
| `pool(ns, roles)` | 角色→voice 数；改形状先 `release` |
| `upload(ns, key, b64, opts)` | 整段已编码音频；`opts` 只接受 `nil`/空表；同 key 内容不可变 |
| `ready(ns, key)` | 原生侧校验完成，可播 |
| `play(ns, key, opts)` | 成功返回**句柄**（正整数；api 1 的 `if play(...) then` 仍成立），失败 `false, reason` |
| `stop(ns, role?)` | 按角色或全停，保留资源 |
| `status(ns)` | free / keys_ready / failed / pool / accepted / dropped 等 |
| `release(ns)` | 异步销毁该 ns 的 voice、缓冲与混响占用 |

api 2 播放选项：`role`、`volume`、`loop`（`true` 无限 / 1..254 额外次数）、`paused`、`pitch`（0.5..2，变调变速）、`reverb`（0..100，3D 声音默认按距离自动）、`pos={x,y,z}`（米，给了就是 3D）、`unit`/`node`（跟随单位，单位失效停在最后位置）、`spatial={min=1, max=60, rolloff='inverse'|'linear', doppler=false}`。

句柄方法：`pause(h)` / `resume(h)` / `halt(h)`（只停这一个）、`set(h, {volume, pitch, reverb, pos, unit, node, spatial, loop=false})`、`info(h)`（`state, position, duration, loops, why, ns, key, role`，慢约 1 帧，保留最近 256 个结束句柄）。`master(ns, 0..100)` 调整个 mod 的总音量。

混响：`environment(ns, preset, overrides)`，预设 `room / small_room / large_room / hall / corridor / cave / hangar / arena / sewer / forest / mountains / plain / city / underwater`，`'off'`/`nil` 关闭。`overrides` 可改 `level, reflections, decay, room_size, density, diffusion, reflections_delay, reverb_delay, room, room_hf, hf_reference, low_eq_*, high_eq_*`（取值范围见 `MDL3_AUDIO_API_zh.md` §混响）；`presets()` 返回每个预设展开后的参数表。

**配额**：每 ns 512 MiB / 64 key / 12 voice；全局 16 ns / 512 MiB / 256 key / 64 voice；单音效 ≤ 12000000 base64 字符（≈9 MiB）；每步最多 32 个播放请求、64 个句柄操作、64 个位置更新；每次 `upload` 调用 ≤ 8192 base64 字符（分块由 MDL3 内部做）。上传文本总量超约 44M 字符后，已就绪音效的文本被释放，宿主重启后需**同 key 同内容重传**（`ready` 返回 `audio host restarted; upload this asset again`）。

**验证**：`audio.state()` 到 `ready` → `audio.ready(ns,'kill')` 真 → `play` 返回句柄 → `info(h).state=='playing'`；3D 声音走近走远听音量/左右变化；混响听尾音。日志里 `AUDIO_REQUEST_FAILED` 就是被拒（槽满/配额/未就绪）。

### 6.2 路线 B · 模型 / 资源替换

> 完整按钮、权重、材质、排错见 `SKILL.md §6.2`。不需要 srkit、Lua、MDL3；需要 **Blender + HD2SDK**。

#### B1 · 武器替换

> 完整按钮、顶点组、`attach_*`、弹匣、LOD 见 `SKILL.md §6.2 B1`。层级与验收见 §0.7。

**七步**

1. **清场 + 找 archive**：退出游戏，备份或 `purge` 游戏 `data/*.patch_*`；`hd2mod.py lookup "<武器名>"`（或 SDK `Search Found Archives`）。
2. **导入目标 unit**：星形图标 → New Patch → 导入目标 archive 的 unit；开 `Import LODs`；纯静态武器才开 `Import Static Meshes`。
3. **导入模型并对齐握把**：枪口朝前、握把对齐原版、缩放到同长度；**复制一份**再做试装。
4. **试装（L1）**：删原版顶点 → 模型全绑 `boss` → 移除自带材质 → `Ctrl+J` 合并 → **Save Units（只存 unit）** → Write Patch → 进游戏看握持/尺寸/穿模。
5. **定层级**：L1 整枪 `boss`；L2 按原版顶点组绑 `bolt`/`charging_handle`；L3 进 Edit Mode 调 `attach_muzzle`/`attach_underbarrel`/`attach_optic`/`sight`/`ejector`/`IK_left`/`attach_mag`。
6. **材质 + LOD**：武器首选 `Advanced`；`Auto LODs` 普通武器开，LOD 相关 unit 关并逐层改；LOD0 通常第一人称、LOD1 第三人称。
7. **Save Units → Export Patch → 收编打包**（见 B1b 第 9 步）。

**武器专属检查**：右手握持正确不浮空；枪托不穿身体；枪口火光/弹道看 `attach_muzzle`；瞄具浮空看 `attach_optic`/`sight`；弹匣错位看 `attach_mag`；枪机不动 = 只绑了 `boss`，回 L2；LOD 相关 unit（P-4 Senator、AC-8 背包）只改 LOD0 会丢部件/子弹；已有武器 mod 换目标用 SDK `Manually Load Patch` 加载旧 patch → 对齐新 target → 按原版组/材质重存（旧 unit 过期先 Retagger Update Old Mod）。

#### B1b · 护甲 / 头盔替换

> 完整流程见 `SKILL.md §5.9`（Step 0–8）与 §6.2 的 B1b / B2 / B3。

**九步**

1. **清场 + 找 archive**：退出游戏，备份或 `purge`；`lookup "<装备名>"`；**头盔和护甲在不同 archive**。
2. **导入目标 unit**：星形图标加载基础 archive → New Patch → 导入目标 archive 的 units；开 `Import Materials`/`Import LODs`；新手保留 `Remove Gore Meshes`。
3. **导入模型**：摆成 HD2 A-Pose，先整体缩放再局部对齐；复制一份再切。
4. **切分**：至少 6 件（左右臂、躯干、腰、左右腿）；按**权重 1.0 的位置**切，不按视觉切；接缝用 `Split by Selection` 或 Data Transfer 修法线。
5. **权重**：上臂绑 `shoulder_twist`（不是 `shoulder`）；接缝权重 1.0；软体渐变、硬体单骨 1.0；手指按 `thumb/index/middle/ring/pinky` + 1/2/3。
6. **材质**：SDK 里生成材质（护甲首选 `Advanced`），接贴图；槽数不超过原版。
7. **属性/原点/UV**：`Copy/Paste HD2 Properties` + `Cursor to Select` → `Origin to 3D Cursor`；合并法把 UV 层命名为 `UVMap`；不替换的部件 `Merge at Center` 留 1 顶点隐藏。
8. **Save Units → Write Patch → 测试 → Export Patch**。首次保存：`Force 3 UV Sets`、`Save Textures with Material`、`Generate Random Texture IDs`、`Patch Base Archive Only` 全开。
9. **收编打包**：

```bash
python tools/hd2mod.py adopt "<工程>" --from "<SDK导出的zip>"
python tools/hd2mod.py build "<工程>" --zip
python tools/hd2mod.py check "<工程>"      # 必须全绿
python tools/hd2mod.py install "<工程>"
```

多 option（护甲/头盔、不同皮肤/瞄具）：`adopt --option Core` / `--option Helmet`，`build` 按 `manifest.Options[].Include` 分别打包到 `dist/<Name>/<Include>/`。

**产物结构**

```
<ModName>/
├── manifest.json
├── README.md
├── cover.jpg
└── Core/
    ├── 9ba626afa44a3aa3.patch_0
    ├── 9ba626afa44a3aa3.patch_0.gpu_resources
    └── 9ba626afa44a3aa3.patch_0.stream
```

**铁律**：资源 ID 不能变（换的是内容不是身份）；`.stream`/`.gpu_resources` 必须与宿主 patch 同目录同前缀（少一个静默丢资源）；资源 mod 在 MDL3 里显示 `LAUNCH ONLY`，**不能**游戏内热开关，装完必须重启；**不要在游戏运行时** Write Patch/Deploy。

#### B2 · 只换贴图 / 材质

流程同 B1，只改 `material`/`texture`，不动 mesh：

- 贴图必须**正方形、2 的幂**；法线用 **OpenGL** 约定。
- `Advanced` 材质：Normal/AO/Roughness (R/G/B/A)、Metallic、Color/Emissive Mask。
- 只换颜色/粗糙度时，保持原材质模板与贴图尺寸最稳。
- 纯贴图包可以没有 unit：`new --kind model --target-kind texture`，`check` 不强制 unit。

#### B3 · 护甲互换 / 已有 mod 改目标

**Avatar Rig 法**（推荐，可重复打补丁）：

1. 加载 `Super Destroyer Interior 2`，导入 **Avatar Rig**，unit ID **`5556372446766824087`**。
2. 删掉 Rig 的灯光/mesh，只留骨架。
3. 导入 Armor A（外观）与 Armor B（目标）。
4. 把 B 的 Armature Modifier 指向 Avatar Rig。
5. A + B 合并 → 按 B 的材质选择 → 删除 B 的 mesh。
6. Weighted Normal → Apply；选 A，**以 B 的 ID Save Units**。
7. 用 HD2 原版材质时，**把 A 的材质一起保存**，否则不显示。

**HD2 Retagger**（不开 Blender）：读现有 patch → 检测原目标 → 选新目标 → 导出新 patch。复杂 mod 可能失败，先备份。

#### B4 · 音频

分两条完全不同的路，**先选路再动手**：

| 目标 | 走哪 | 代价 |
|---|---|---|
| 给 mod **加**自己的音效/提示音/循环声/3D 声 | **B4a `MDL3.audio`**（§6.1.7） | 纯脚本，随脚本一起热开关；不需要 Blender/wwise |
| **替换游戏原有**枪声/爆炸/音乐 | **B4b wwise 替换** | 改 bank/stream，走 `.patch_N`，装完重启 |

**B4a（首选，dev.40+）**：PCM16 WAV（或 ADPCM）→ 离线生成 `sounds.lua` → `define_format/pool/upload/ready/play`。步骤、配额、3D 与混响细节全在 §6.1.7。注意三点：同 ns 同格式、单音效 ≤ 约 9 MiB、混响全局 3 槽。

**B4b（替换原版）**：音频是 wwise bank/stream，替换后同样走 `.patch_N` 打包，**不要用模型流程硬套**（没有 unit/mesh 可 Save）。社区工具（HD2AudioMaker 一类）按其说明做，再用 `hd2mod.py inspect`/`check` 验证容器与 `.stream`/`.gpu_resources` 是否齐全。判据：进出任务不崩、目标音效真的变了、其它音效没被顶掉。

#### 深层排错才用 srkit

```bash
SRK="${HD2_SRKIT:-<srkit目录>}"
python -m srkit list "<游戏>/data" --type texture --limit 20
python -m srkit extract "<游戏 data 或某个 patch>" --id <resource-id> -o ./out
python -m srkit unpack "<源 archive>" -o ./ws --type texture
python -m srkit verify ./ws
python -m srkit pack ./ws -o ./build
```

> `srkit verify` 只保证**资源编码**可逆，不保证引擎/加载器接受；模型包优先用 SDK 导出，不要用 srkit 重造容器。

### 6.3 路线 C · 数值表（只指路，不重造）

社区已有成熟工具链，本技能不重写。只需知道边界与闸门：

| 环节 | 要点 |
|---|---|
| 载体 | `data/game/*.dl_bin`（松散加密文件），**不是** `.patch_N`，后者覆盖不了它 |
| 前置 | 需游戏内置 `recipient.pk`/`recipient.sk`；**本机 modtool 没有现成密钥**，按上游文档自行导出 |
| 闸门 | 改完必须重算 `MurmurHash64A(明文)` 并重新封装，否则 `0xC000000D` 或静默失效 |
| 换 build | 偏移类结论**逐 build 作废**，必须重跑基线；结构类可沿用 |
| 缓存污染 | 在"自己已部署 mod"状态下 dump，明文缓存被污染，之后所有判断全错 |

动手时读：`hd2-datamined/INDEX.md`（唯一索引入口，仓库自备）、`BUILDS.md`、`docs/boundaries/MEMORY-ACCESS-25988413.md`、同仓库 `skills/hd2-file-route-mod/SKILL.md`。

---

## 7. API / 工具约束

### 7.1 Lua 运行时约束（PUC Lua 5.1）

**可用**：`string`/`table`/`math`/`os.time` 等 5.1 标准库；`#`、`..`、`and/or`、闭包、元表。
**不可用（写了就编不过）**：

| 禁用 | 替代 |
|---|---|
| `ffi`/`bit`/`jit` | 脚本层没有；读数据走 §6.1.5；写内存只能等 MDL3 扩接口或走数值表 |
| `goto`/`::label::` | `while` + `break` 重构 |
| `//`、`<<`、`>>`、`&`、`\|`、`~`（位运算） | `math.floor(a/b)`、乘除 2 的幂 |
| `\z` 转义、`\u{}` | 拼接，或写 UTF-8 原字节 |
| LuaJIT 字节码（`\x1bLJ`） | 发源码 |
| 单函数 > 200 局部变量 / > 60 上值 | 拆函数、上值改表 |

**必须**：UTF-8 **无 BOM**；`dt` 判空判正；所有引擎返回值判 `nil`（大量接口会返回 nil）。

### 7.2 引擎 API（`stingray` 表）—— 已被实机 mod 用到的部分【实测】

| 命名空间 | 常用成员 | 说明 |
|---|---|---|
| `Vector3` | `x/y/z`、`distance`、构造 | 只取数值，**不要长期持有引擎向量**，转成 `{x,y,z}` |
| `Unit` | `alive`、`node`、`has_node`、`world_position`、`num_cameras`、`has_animation_state_machine` | `alive` 必须先判 |
| `World` | `units`、`units_by_resource`、`destroy_gui`、`debug_camera_pose` | `units_by_resource` 按资源找同类单位 |
| `Gui` | `triangle` 等图元 | 裸引擎绘图；用 **X/Z** 作屏幕坐标，layer 单独传参。**dev.41+ 一律改用 `MDL3.gui`**（§6.1.6） |
| `Application` | `worlds()` | 找当前世界 |
| `Camera` | 相机位姿 | 世界坐标 → 屏幕坐标 |

写之前先确认存在：`if type(sr.Unit.alive) ~= 'function' then return end`。**不要猜函数名** —— 猜错是运行期 nil，不是编译错误，极难定位。

### 7.3 工具约束

| 工具 | 是否必需 | 允许做什么 | 禁止做什么 |
|---|---|---|---|
| `tools/hd2mod.py` | **必需** | 体检/查 archive/建工程/收编/打包/门禁/安装 | 手改生成的 patch 字节 |
| `tools/blender_preflight.py` | 模型路线必需 | 只读检查模型（骨架/UV/权重/贴图） | 改模型、改游戏文件 |
| `hd2-mod-cli` | 必需（部署） | 导入/部署/回滚/库管理 | 与别的管理器并用 |
| **Blender** | 模型路线必需 | 导入/编辑/导出模型 | — |
| **HD2SDK: Community Edition** | 模型路线必需 | 读 archive/Save Units/Write/Export Patch | 打包进自己的 mod 二次分发 |
| `MDL3` | 视目标 | 游戏内管理、Data Hub 读取 | 打包进 mod、重复部署；资源 mod 不能热开关 |
| `srkit` | 可选（深层排错） | 解包/列资源/改字节/重打包/往返校验 | 用它的 `pack` 生成 Lua 包 |
| `hd2-datamined` | 可选（路线 C） | 读文档、跑离线工具 | 游戏运行时改盘上文件 |

> **Lua 包不用 srkit 打**：`srkit pack` 保留源包"自身长度"字段（头部 `0x20`），重打后尺寸变了字段还是旧值；本技能自带打包器已与真实包逐字节对齐。
> **模型包也不自己造容器**：多类型多条目易把 TOC 偏移或 `.gpu_resources` 对错；让 SDK 导出，本工具只做收编与校验。

**MDL3 分发限制【文档】**：非自由软件。**不得**二次上传/改包分发；**可以**做依赖它的 mod，但 README 必须写明依赖并链回官方发布页。不要打进整合包。

### 7.4 管理器（hd2-mod-cli）工作流适配

**路径不要写死**，全由 `doctor` 探测并记到 `~/.hd2-gameplay-mod/config.json`。

| 概念 | 说明 |
|---|---|
| 数据目录 | `%USERPROFILE%\.hd2-mod-cli`（`config.json`/`library.json`/`deployed.json`） |
| 库目录 | 由 `doctor` 找出（通常与游戏同盘 → **硬链接部署**，不占额外空间） |
| 游戏目录 | 由 `doctor` 从 Steam 库自动发现 |
| 排序语义 | **列表越靠下优先级越高**；加载器由 `loader` 单独选，部署时排在所有 mod 之后 |
| 部署单位 | `<游戏>/data/9ba626afa44a3aa3.patch_N`（N 由管理器连续重排） |

```bash
hd2qd list --files          # 看加载顺序与 patch 编号
hd2qd status                # 只显示"部署会做什么"，不改盘
hd2qd deploy --dry-run      # 同上，更细
hd2qd lua                   # 部署前 Lua 检查（启动脚本归属/哪些 mod 不会启动）
hd2qd lua-syntax <file>     # 该 Lua 能否在 PUC 5.1 上编译
hd2qd conflicts -v          # 多 mod 共用资源与优胜者
hd2qd purge --yes           # 恢复原版（只删游戏目录 patch，库不动）
hd2qd profile-new <名字>    # 建只含本 mod 的配置，做干净基线
```

> **干净基线**：`profile-new test --empty` → `profile-add <你的mod>` → `profile-use test`。这是唯一能排除"别人的 mod 干扰"的方法。

### 7.5 换 build / 换 SDK 后的复验清单

按顺序跑，任一步不过就停：

1. `python tools/selftest.py`（本技能自检，不依赖游戏）
2. `python tools/hd2mod.py doctor`（build/库/Blender/SDK）
3. 记录新 build 号，与 `verified-build` 对比
4. **Lua**：`hd2qd lua` 看是否仍被识别、`hd2qd lua-syntax` 看是否仍能编译
5. **产物**：`hd2mod.py inspect "<你的 patch>"`，看类型/条目是否还能解析
6. **模型**：Blender 里 `N` → **Modding** 是否还在；`New Patch` 是否还能写；导出一个旧工程 `check` 是否还能过
7. **GUI / 音频**（dev.41+）：脚本里打一行 `diagnostics()` 输出 `gui.api` 与 `audio.api`；`gui.api` 掉了就退回裸 `Gui` 或要求用户升级 MDL3；`audio.api < 2` 时不要调 `loop/pitch/pos/reverb`
8. **带图/带声的包**：`check` 看 `.gpu_resources`/`.stream` 是否齐全；实机确认图片不是 `missing_image`、`audio.state()` 到 `ready`
9. 实机跑 Step 7 四问（模型路线跑 §5.9 四问）

---

## 8. 常见误区

> 与 §4 的坑清单重叠的条目只在 §4 展开，这里只留认知层与流程层。

### 8.1 认知层

| 误区 | 事实 |
|---|---|
| "EAC 一直在，要先关 EAC 才能 mod" | 10-20 之前是 GameGuard；EAC 是新换的，且**不需要也不能关** |
| "EAC 把 Lua mod 封了" | 不是。是 LuaJIT 换成 PUC 5.1，脚本层 `ffi` 没了；纯 Lua 照样跑 |
| "装个加载器就能救回老 mod" | 半对：读能力被 MDL3 恢复，但 API 重建过，必须**重写** |
| "MDL3 没有 FFI，读内存彻底没戏" | 错。MDL3 **自带 FFI**，用签名桥在宿主侧读 |
| "MDL3 是 mod 管理器，装了就不用 Arsenal" | 不是。它只管**游戏内**开关与重载；装/部署仍靠管理器 |
| "MDL3 能改游戏数据" | 预览版**纯读取**，作者刻意如此 |
| "模型 mod 也要 MDL3" | 不用。模型改资源；资源包在 MDL3 里是 `LAUNCH ONLY` |
| "10-20 之后模型 mod 也死了" | 没有。死的只是脚本层 `ffi`；更新会让旧 unit 数据失效 |
| "装了管理器就能做模型" | 管理器只负责装；做模型要 Blender + HD2SDK |
| "AI 可以直接生成能进游戏的绑定模型" | 不能。AI 做流程/检查/打包 |
| "社区说安全就安全" | Arrowhead 从未发布安全名单，风险自负 |

### 8.2 技术层（补充项）

| 误区 | 事实 |
|---|---|
| "patch 编号我自己定" | 你的编号只是源文件夹里的顺序，部署时管理器**重排** |
| "`srkit verify` 过了就万事大吉" | 只证明资源编码可逆，不证明引擎接受 |
| "资源包的 `0x20` 自长度必须等于文件长" | 只对**单资源 Lua 包**成立；模型/贴图包该字段不可靠（实测 9.6 MB 包写成 60 MB） |
| "Lua 里 `print` 能看日志" | 能，但各加载器落到不同日志；自己写日志文件才可靠 |
| "`dt` 可以直接乘" | `dt` 可能 nil/0/异常大（切图、卡顿），必须夹紧 |

### 8.3 流程层

| 误区 | 事实 |
|---|---|
| "先写三千行再说" | 先用 20 行验证"能加载、能画一个点" |
| "先做整套甲再测试" | 先做一件（胸甲/头盔/一把枪）跑通全流程 |
| "在自己装满 mod 的环境里测就行" | 冲突与自身 bug 分不开，用 `profile-new` 建干净基线 |

---

## 9. 排错对照表

### 9.1 脚本 / 部署 / 加载器

| 症状 | 最可能原因 | 怎么查 | 怎么修 |
|---|---|---|---|
| 装了游戏里完全没反应 | 资源 ID 与模块路径不匹配 | `srkit list` 看 `file id`；`srkit hash` 对比 | 改 `file_id` 重新打包 |
| 加载器列表里有但不执行 | 首行声明与路径不一致/被抢槽 | 看加载器日志里的 `name` | 统一声明；只留一个加载器 |
| 进游戏就崩，删掉我的 mod 就好 | Lua 5.1 不兼容语法/`dt` 未判空/接口不存在 | `hd2qd lua-syntax`；逐段注释二分 | 按 §7.1 改 |
| 部署报错/部署一半 | 游戏还在运行 | `tasklist` | 退出游戏重部署 |
| 管理器的库也坏了 | 直接改了游戏目录里的 patch（硬链接） | `hd2qd status --verify` | 从备份/重新下载恢复库 |
| MDL3 菜单里没有「MDL3 设置」 | 缺 Certum 中间证书，EAC 拦了 native 组件 | 看是否 error 193 / "不受信任的系统文件" | `2_FIX_CERT_ADMIN.bat` → **重启** → 仍不行 `3_REPAIR_EAC_ADMIN.bat` |
| 两个 mod 只有一个生效 | 两个都占了启动槽 | `hd2qd lua` 看归属 | 只留一个加载器，其余改 addon |
| 资源 mod 在 MDL3 里不能开关 | 正常，标 `LAUNCH ONLY` | — | 回管理器部署 + 重启 |
| 我的 mod 在别人机器上崩 | 硬编码路径/用户目录/未判空 | 代码审查 | 只用引擎 API 与 Data Hub |
| 换 build 后全部失效 | 运行时/接口变了 | §7.5 清单 | 按结果重做，不要猜 |

### 9.2 GUI / 音频（dev.41+）

| 症状 | 最可能原因 | 怎么查 | 怎么修 |
|---|---|---|---|
| `gui` 为 `nil`，什么都不画 | MDL3 早于 dev.41，或没有 MDL3 | `rawget(_G,'MDL3')`、打印 `gui.api` | 升级 MDL3；或临时用裸 `Gui` 兜底 |
| 形状/图片正常，**文字不显示** | 原生界面服务没起来（证书/EAC） | `canvas:status().font` 与 `.problem` | 跑 EAC Fix Kit（§2.4） |
| 图片区域空白 | 未部署（MDL 库热启动）、名字写错、没打包 | `status().missing_image`、日志 `image not loaded`、`build/images.txt` | 经管理器 Deploy，manifest 加 `"Include": ["data"]` |
| 一画 HUD 就掉帧 | 每帧改文字/每帧重建画布 | 数一下每帧 `text/image` 调用 | 文字 1 Hz + 单独高层画布；只让矩形动 |
| 图元画了但没出现 | 超 4000 图元/16 画布被丢弃；层级 0–99 越界 | `status().items`、日志 | 拆画布，减少图元 |
| 面板顺序错乱 | 图元总数超约 790，超出部分共用最上层 | 估图元数 | 拆到不同 layer，减少总数 |
| 4K 下错位 | 混用 `units='pixels'` 与 `reference` | 看 canvas 选项 | 统一 `reference`，或统一按 `pixel_w/h` 算 |
| `audio.state()` 一直 `wait/starting` | 原生服务没接单 | `state()` 的 reason | 重启游戏；仍失败看 MDL3 日志 |
| `play()` 返回 `false` | voice 满 / 该 key 未 ready / 服务未 ready | `status(ns)` 的 free、keys_ready、dropped | 扩池、等 ready、关键提示做文字降级 |
| 声音听不到但返回句柄 | 只代表本帧已提交；设备/预算问题 | `info(h).state`、日志 | 看 `why`；降并发；确认 volume/master |
| 3D 声无方向/无衰减 | 没有可用 listener；素材是立体声 | `listener()` 设置；素材声道 | `listener('camera')` 或自己传 pos/forward/up；换单声道 |
| 混响没生效 | 全局 3 槽已满 | 日志 `AUDIO_REQUEST_FAILED … reverb slots full` | 复用预设、参数一致；不用就关掉 |
| 宿主重连后某音效失效 | 文本被释放 | `ready()` 返回 `audio host restarted; upload this asset again` | 同 key 同内容重传 |
| `upload` 被拒 | 同 ns 格式不一致 / 同 key 内容变了 / 超 9 MiB | 比对 format 与 WAV 参数 | 统一格式；换 key；压缩素材 |

### 9.3 模型 / 贴图 / 武器

| 症状 | 最可能原因 | 怎么查 | 怎么修 |
|---|---|---|---|
| 装完完全没变化 | patch 没部署/archive 错/option 没勾 | 管理器看部署文件；`inspect` | 重新部署；确认目标 archive |
| 模型透明/看不见 | `Force 3 UV Sets` 关且只有一个 UVMap；材质没保存；只导 LOD0 | 看 SDK 设置与 patch 里有无 material | 开 Force 3 UV Sets；Save Materials；补 LOD |
| 黑紫/亮色块 | 贴图尺寸或格式错；法线是 DirectX；节点没接 | 检查正方形/POT、OpenGL 法线、Advanced 节点 | 重导贴图/反相绿通道/重接节点 |
| 拉伸/关节扭曲 | 权重没刷好；A-Pose 没对齐；上臂绑了 `shoulder` | 看顶点组与姿势 | 重传权重；改绑 `shoulder_twist` |
| 接缝亮线/孔 | 切分方式不对；接缝权重不是 1.0；法线没修 | 看接缝权重；Data Transfer | 按权重切；权重归一；Data Transfer |
| 启动即崩 | 材质槽超过原版；patch 冲突；旧 unit 数据 | 只启用本 mod；看日志 | 减材质；purge；Retagger 更新 |
| 某些部件/子弹消失、远处闪烁不见 | LOD 相关 unit 只改了 LOD0；Auto LODs 覆盖；裁剪边界不对 | 看 LOD 页/逐层导入；切远距离观察 | 关 Auto LODs，逐 LOD 补；检查 culling |
| 只有一种体型生效 | 只替换了 Brawny 或 Lean | 看 body parts | 做另一体型，或 README 写明 |
| 头盔在 UI 里不显示 | 材质模板/槽位问题 | 换 Advanced；核对槽数 | 重做头盔材质 |
| 游戏更新后失效 | unit 数据/裁剪信息变了 | 对比 build；看是否崩溃 | Retagger Update Old Mod，或重做 |
| 帧数暴跌 | 高模铺满所有 LOD；贴图过大 | 看面数/贴图尺寸 | LOD2+ 减面；降贴图 |
| `inspect` 报缺 `.gpu_resources` | 导出时漏了伴生文件 | `inspect` | 回 SDK 重新 Export Patch，整包带走 |
| `check` 报类型计数不符 | patch 被手改过/导出不完整 | `inspect` 看类型表 | 重新导出，不要手改二进制 |
| 枪浮空/巨小、枪托穿模、枪口或瞄具歪、弹匣错位 | 握把/原点/缩放出错；`attach_*` 未对准（瞄具常是独立 unit） | 对比原版 grip；看骨骼与 vertex groups | 重新对齐 + 应用缩放 + 复制原点；Edit Mode 移骨骼或改枪管长度；弹匣 Child Of 挂 `attach_mag` |
| 枪机/拉机柄不动、快慢机穿帮 | 整枪只绑了 `boss` | 看 vertex groups | 按原版组绑 `bolt`/`charging_handle` |
| 第一人称手臂穿模 | LOD0/枪身位置 | 进游戏第一人称 | 调枪身/握把；检查 LOD0 |

---

## 10. 归档与发布规范

### 10.1 目录规范

```
D:\HD2 Mods\_src\<ModName>\        ← 源工程（永不直接放进库）
├── manifest.json
├── mod.project.json
├── README.md           依赖 / 兼容性 / 已知问题
├── CHANGELOG.md        每次改动一行
├── THIRD_PARTY.md      借用的代码与许可（没有就写"无"）
├── src/main.lua        （Lua 路线）
├── src/sounds.lua      （音频路线；audio_assets.py 生成，别手改）
├── assets/img/         （GUI 图片源 PNG；边长 2 的幂，≤4096）
├── assets/audio/       （音效源 WAV；PCM16，同组同声道/采样率）
├── patches/            （模型路线：SDK 导出的 patch + 伴生文件）
│   ├── 9ba626afa44a3aa3.patch_0
│   ├── 9ba626afa44a3aa3.patch_0.gpu_resources
│   └── SOURCE.json     adopt 记录来源/类型统计
├── PLAN.md             模型路线立项卡 + 闸门
├── assets/cover.jpg
└── dist/               build 之后才有

D:\HD2 Mods\<ModName>_<后缀>\      ← 部署库（由管理器 add 进来）
```

**带图/带声的额外产物**（都在 `build/`，不进 `src/`）：

| 产物 | 谁生成 | 注意 |
|---|---|---|
| `build/data/9ba626afa44a3aa3.patch_0` + `.gpu_resources` + `.stream` | `gui_assets.py` | manifest 加 `"Include": ["data"]`；代码里名字是 `mods/<作者>/<名字>/img/<文件名>`（无扩展名） |
| `build/images.txt` | `gui_assets.py` | 核对图片名清单，写错就是 `missing_image` |
| `src/sounds.lua` | `audio_assets.py` | dev.43 包内**未附带**该脚本；没有就自己按 format+sounds 结构写 |

**源工程与部署库分离**：库里放"可安装形态"，源工程放"可重建形态"。混在一起，一次误删就没了。
> 模型路线没有 `src/main.lua`，别为"统一"硬塞；`mod.project.json` 的 `kind: model` 决定 `build/check` 走资源分支。

### 10.2 版本与标识

| 项 | 规则 |
|---|---|
| `manifest.Guid` | UUIDv4，**生成一次永不修改** |
| `manifest.Version` | **manifest 语法版本，固定 `1`**，不是 mod 版本号 |
| 对外版本号 | SemVer 写进 `Name`/`Description`，例：`我的MOD v1.2.0` |
| 模块路径 | `mods/<作者>/<名字>`，全小写，**发布后冻结**（Lua 路线） |
| 模型目标 | 目标装备名/archive/体型/是否含头盔，写进 README 与 `PLAN.md` |
| 每次构建记录 | build 号 / SDK 版本 / patch sha256 / 资源类型统计 |

### 10.3 README 必含四项

`依赖 / 兼容性 / 已知问题 / 卸载`，缺一节别发。模板（斜杠后为模型路线换成的内容）：

```markdown
## 依赖
- 需要 MDL3 3.0.0-dev.41+（GUI）／dev.40+（音频）／推荐 dev.43 + Hub 0.6.0（官方发布页：<链接>）
- 纯模型/贴图包不需要 MDL3，管理器部署后**重启游戏**
- 不需要 HD2 Data Hub；制作需 Blender + HD2SDK 3.11.x（模型路线）
## 兼容性
- 验证 build：26251122（2026-11-05）
- 与其他加载器：仅可与 Chef Shared Loader 共存，不要同时启用 XX
- 目标：B-01 Tactical（archive 58e4bd4b2278d15c，Variation 1）；体型 Brawny/Lean/两者；含头盔 是/否（模型路线）
## 已知问题
- 例：仅支持 Brawny，Lean 会错位；第一人称手臂轻微穿插
## 卸载
停用/删除后重新部署即可；不写入任何用户目录。
```

### 10.4 发布包结构

zip 根目录**直接**放 `manifest.json`、`README.md`、`CHANGELOG.md`、`cover.jpg`，`Core/` 放 SDK 原样 patch + 伴生文件（目录形态见 B1b）。**不要多套一层**（部分管理器不认）；**不要改名/重打包**，`build` 只重排编号、不改字节。

### 10.5 回滚

| 场景 | 做法 |
|---|---|
| 只想临时关掉 | 管理器里禁用 → `deploy` |
| 恢复到完全原版 | `hd2qd purge --yes`（只删游戏目录 patch，库不动） |
| 退回上一版 | 保留上一版 zip → `hd2qd replace <mod> <旧zip>` |
| 想彻底隔离测试 | `profile-new` 建只含本 mod 的配置 |

---

## 11. 附录

### 11.1 工具清单

| 工具 | 路径 | 说明 |
|---|---|---|
| **本技能工具** | `tools/hd2mod.py` | 零依赖；`doctor/lookup/new/adopt/build/check/inspect/install/lint` |
| **素材预检** | `tools/blender_preflight.py` | 在 Blender 里只读检查模型（骨架/UV/权重/贴图） |
| **工具自检** | `tools/selftest.py` | 零依赖；不装游戏也能跑 |
| mod 管理器 | `hd2qd`（PATH）或 `HD2 Mod Quick Deploy.exe` | hd2-mod-cli；`doctor` 自动找 |
| **Blender** | 4.0–5.2 | 模型/贴图路线必需 |
| **HD2SDK: Community Edition** | GitHub release v3.11.1 | 模型/贴图路线必需；装进 Blender |
| MDL3 + Data Hub | 官方发布页 | dev.43 / Hub 0.6.0 / 桥 DLL 0.4.5，**必须最高优先级** |
| **图片转资源** | `For Modder/gui_assets.py`（dev.41+ 包内） | PNG → patch + gpu_resources + stream；需 pillow |
| **音频资源生成** | `audio_assets.py`（文档提到，dev.43 包内**未附带**） | WAV → `sounds.lua`（PCM16/ADPCM）；没有就向作者索取 |
| MDL3 EAC 修复包 | 随 MDL3 附带的 `MDL3-EAC-Fix-Kit-1.0.2.zip` | 菜单不出现 / 卡"未响应"时用；dev.43 起诊断窗口不再自动装证书 |
| 可选工具 | — | HD2SDK-AQ-Edition（中文改版，与 CE 二选一）· MMD2HD2 Studio（MMD→护甲，仍要查权重）· HD2 Retagger（换目标甲/修旧 unit）· srkit（深层排错才用）· hd2-datamined（路线 C 才用） |

> **只做 Lua**：一个 `hd2mod.py` + 一个管理器就够。**做模型**：再加 Blender + HD2SDK；srkit 不是必需品。

### 11.2 证据来源

- 【文档】MDL3 包内 `README_zh.md` + `For Modder/hd2data_field_reference_v0_6_0.md`；hd2-mod-cli / srkit README
- 【文档】MDL3 dev.43（2026-11-06）包内 `MDL3_GUI_API_zh.md`（gui api 1）、`MDL3_AUDIO_API_zh.md`（audio api 2）、`gui_assets.py`；README_zh 的 dev.43 变更（GUI/音频/3D/混响/Hub 0.6.0/诊断窗口修复）
- 【文档】MDL3 发布页（dev.36 至 dev.43 各版）：FFI support、预览版纯读取、不开源、FAQ 作者回复
- 【文档】HD2 Modding Wiki（Armor Replacement/Swapping、Anatomy、Materials、Textures、LOD Dependant Units、Manifest、SDK Functions；Weapon Replacement、Aligning Magazines、Bone Editing）
- 【文档】HD2SDK-CE v3.11.1（2026-10-28）README/release；`utils/constants.py` 资源类型 ID
- 【实测】build 26251122：srkit 往返、从零构造包、资源 ID 规则、已部署 mod 结构；真实容器解析 Kraber Apex（6 类型/34 条目/51 MB）、BR-14 QBZ191（6/22/40.9 MB）、Clear Visibility（material/entity patch）
- 【推断】实机可用 mod 脚本反推的生命周期契约；模型面数/帧数影响为社区经验

### 11.3 术语

| 词 | 含义 |
|---|---|
| patch 文件 | `<archive>.patch_N`，mod 的部署单位；基础 archive 是 `9ba626afa44a3aa3` |
| 启动脚本槽 | 游戏只跑一个 boot 脚本，谁占谁赢 |
| addon | 不占启动槽、由加载器启动的脚本，首行 `-- HD2-Addon:` |
| 模块路径 | `mods/<作者>/<名字>`，同时决定 Lua 资源 ID |
| Data Hub | MDL3 附带的只读数据接口层 |
| unit | 游戏里的模型单位；护甲/武器/道具都是一个或多个 unit |
| archive | 资源归档，如 `9ba626afa44a3aa3`；SDK 按 archive 加载/打补丁 |
| `.gpu_resources` | patch 的 GPU 数据伴生文件；有模型/贴图时常见 |
| `.stream` | patch 的流式数据伴生文件；大块音频/贴图常见 |
| LAUNCH ONLY | MDL3 中标记"只能靠管理器部署、不能游戏内开关" |
