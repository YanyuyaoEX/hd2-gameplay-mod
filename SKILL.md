---
name: hd2-gameplay-mod
description: |
  《绝地潜兵2》玩法 mod 的「许愿式」开发技能：用户只要说想要什么效果，就能从零做出一个可安装的 mod。
  覆盖立项、写 Lua 5.1 玩法脚本、打包 .patch_N、静态门禁、部署、实机验证、归档发布全流程。
  Use when 用户说「给我做个 HD2 的 mod」「我想要个显示敌人血条的」「做个自动标记的」「改个准星」
  「绝地潜兵2 能不能加个 XX 提示」「HD2 玩法 mod」「HD2 脚本 mod」「MDL3 mod」
  「patch_0 怎么打」「Lua mod 加载不出来」「mod 进游戏没反应」「10月20日之后 mod 还能不能用」。
  ⚠ 只做「不读写内存、不绕反作弊、不影响他人体验」的玩法增强；红线清单见 §4，越线即停。
license: MIT
compatibility: Windows · Python 3.11+（零依赖）· Helldivers 2 PC/Steam · 可选 hd2-mod-cli / srkit
metadata:
  domain: hd2-modding
  kind: workflow
  verified-build: "26251122"
  verified-date: "2026-11-05"
  self-contained: "true"
---

# HD2 玩法 mod 开发 · 可执行技能

> **本文件的效力等级**：结论按证据分级标注 —— `【实测】` 本机 build 26251122 亲手验证过 ·
> `【文档】` 上游自带文档写明 · `【推断】` 从工作样本逆推，尚未实机复验。
> **换 build 后**：`【实测】` 与 `【推断】` 两类必须重跑 §7.5 的复验清单，`【文档】` 类要回原页核对。

---

## 0. 三十秒：先看这张表再动手

| 你想做的东西 | 走哪条路线 | 一句话判据 |
|---|---|---|
| HUD 提示、提前量、信息显示、键位、QoL 逻辑 | **A. Lua 玩法脚本**（主线，§6.1） | 逻辑要**每帧跑**、要读单位/世界状态 |
| 换贴图、模型、材质、音效 | **B. 资源替换**（§6.2） | 只换资源本体，不改变玩法逻辑 |
| 改伤害/冷却/弹容/护甲等**数值** | **C. 数值表**（§6.3，只指路不重造） | 社区已有工具，本技能不重写 |
| 读写游戏内存、注入 DLL、绕反作弊 | **不做**（§4 红线 1–4） | 10-20 之后技术上已死，且违规 |

**默认起点**：`90%` 的「玩法 mod」= 路线 A。先跑 §5 的 Step 0–2，别急着写代码。

---

## 0.5 许愿模式：别人只说「我想要个 XX」时怎么接

这一节是**给 AI 的行为准则**。用户不需要懂模块路径、加载器、patch 编号，也不需要装 Python。

### 只问三件事，问完就开工

| 问什么 | 用来定 | 例子 |
|---|---|---|
| 你想要屏幕上多什么 / 少什么？ | 是 UI 还是逻辑 | 「想让准星旁边显示提前量」 |
| 什么时候出现？ | 触发条件 | 「锁定飞行目标的时候」 |
| 怎么算做成了？ | 验收标准 | 「打空中的目标时，准星会跟着它走」 |

**不要问**：用什么加载器、模块路径叫什么、要不要 hook、manifest 怎么写。这些是你的活，不是用户的。

### 然后全自动跑完，只在两个点找用户

```
doctor  →  new  →  写 src/main.lua  →  build  →  check  →  install
   ↑                                                          ↓
 差环境才找用户                                      告诉用户点 Deploy
```

1. `python tools/hd2mod.py doctor` —— 游戏没装、库找不到，就直说差什么，**不要硬做**。
2. 从"想要的效果"映射到路线（见下表）。
3. `new` 起工程 → 写 `src/main.lua` → `build` → `check`（必须全绿）。
4. `install` → 然后用**人话**告诉用户下一步。

### 交付话术

> ✅「装好了。进游戏按 ESC 打开 **MDL 设置**，列表里应该有个「XX」，打开它，然后打一只飞行怪试试。」
>
> ❌「模块路径 mods/x/y，file_id 0x…，已通过 murmur64 校验。」（用户不关心，也看不懂）

### 愿望 → 可行性对照

| 用户这么说 | 能做吗 | 走哪 |
|---|---|---|
| 显示血量 / 弹药 / 队友状态 / 敌人数量 | ✅ | 路线 A，读 `HD2Data` |
| 准星、提前量、屏幕标记、距离显示 | ✅ | 路线 A，`HD2Data` + `Gui` |
| 按键触发某个动作 / 快捷开关 | ✅ | 路线 A，选项 + 引擎 API |
| 换个贴图 / 音效 / 模型 | ✅ | 路线 B |
| 改伤害、冷却、弹容这些**数值** | ⚠️ 能做，但不走脚本 | 路线 C（社区工具），本技能只给边界 |
| 自动瞄准 / 自动开枪 / 透视 / 无限弹药 / 无敌 | ❌ | 红线 §1.2、§4 |
| 让队友也看到我改的东西 | ❌ | 影响他人 |

**做不到就直说**，并给一个"能做的最接近的版本"。不要用"应该可以"糊过去。

---

## 1. 适用范围

### 1.1 适用

- 单人或联机的**玩法增强**：信息展示、瞄准辅助提示、状态监控、操作 QoL、界面重排。
- **纯 Lua 5.1 脚本**（不依赖 LuaJIT），通过社区加载器在游戏内运行。
- **资源层替换**：贴图 / 材质 / 模型 / 骨骼 / 音频，打包为 `.patch_N` 归档。
- 对**数值表**做调整（本技能给边界与指路，不重造工具链）。
- 发布形态：可被 `hd2-mod-cli`、Arsenal、Echelon、HD2MM 任一管理器导入的标准 mod 包。

### 1.2 不适用（见到就停，不要"想办法"）

| 不做 | 原因 |
|---|---|
| 在**自己的脚本里**用 `ffi` / `bit` / `jit` 读写内存 | 游戏 VM 已移除这三个库；脚本层写 `require('ffi')` 必失败。**只读数据请走 MDL3 Data Hub**，见 §2.2.1 |
| 用**未签名**的 native DLL 扩展能力 | 未签名 `577`、签名但不在名单 `193`、自签装进 `LocalMachine\Root` 仍 `577`【文档】。MDL3 的桥是**已签名**组件，属于例外，不能照抄 |
| 关闭 / 绕过 / 欺骗 EAC | 违反 ToS，且有封号风险；本技能不提供任何此类方法 |
| 联机作弊、影响他人体验的数值改动 | 10-20 换 EAC 的**直接动因**就是这类 mod |
| 解锁付费内容、破解 | 法律与平台风险 |
| 修改他人存档 / 网络协议 | 同上 |

> 判断口径：**"这个改动会不会让同一局里的其他人体验变差？"** 会 → 不做。
> Arrowhead 的公开口径是"不影响他人的外观与非玩法 mod 可以存在"，但**从未发布过安全名单**；
> 社区列表、管理器的状态标签都不等于官方认证。

---

## 2. 现状更正（2026-11-05，必读）

网上绝大多数 HD2 mod 教程停留在 **10 月 20 日之前**，直接照做必然失败。以下是更正后的事实。

### 2.1 反作弊：不是"一直有 EAC"，是 10-20 才换过来

| 时间 | 事件 |
|---|---|
| 2026-10-20 之前 | 游戏用 **nProtect GameGuard**。所有"关掉 EAC 才能 mod"的教程，说的是错的系统 |
| 2026-10-19 | Arrowhead 公告要换反作弊 |
| **2026-10-20** | **7.2.0 上线，GameGuard → Easy Anti-Cheat (EAC)**，并追加额外安全工具 |
| 2026-10-22 | 7.2.1 修"squad 进出崩溃" |
| 2026-10-27 | 官方发布启动崩溃清理指引（清残留 mod / 注入器 / GameGuard 文件 / 校验文件） |

**关键更正**：EAC 上线并**没有**拦下 Lua mod（社区排查与加载器作者的公开说明一致）。
mod 大面积失效的真实原因是同一次更新里 **Lua 运行时从 LuaJIT 换成了内置 PUC-Rio Lua 5.1**：

- `ffi` / `bit` / `jit` 三个库从**游戏 VM** 里消失 → 脚本层再也拿不到 `ffi`。这一条对**所有**加载器成立。
- 但"读内存"**没有完全死**：MDL3 自带 FFI，用自己的**签名 native 桥**在宿主侧读游戏数据，再经 Data Hub 供给脚本。
  所以老 FFI mod 不是"永久失效"，是**必须按新 API 重写**（作者原话：*Need to update, Cause I rebuild the api*）。详见 §2.2.1。
- `core/wwise/lua/wwise_flow_callbacks` 这个被 Bingus Shared Loader 依赖的脚本被移除 → 基于它的加载链断裂。
- 游戏**仍然**从 mod 加载启动脚本，**仍然**每帧跑 Lua 的 update → 这是新加载器能工作的缝隙。

### 2.2 现在能跑什么、不能跑什么

| 类别 | 状态 | 说明 |
|---|---|---|
| 纯 Lua 5.1 脚本（只用游戏 Lua API） | ✅ 可用 | units / lights / lines / 屏幕文字 / 按键 / 网络字段 |
| 脚本里 `require('ffi')` | ❌ 不可用 | 游戏 VM 无此库，所有加载器都一样 |
| 读游戏私有数据（血量/弹药/敌人/事件…） | ✅ 可用（只读） | 走 **MDL3 Data Hub**，需要重写，不能直接跑老 mod |
| 写回游戏数据（改内存/改状态） | ❌ 不可用 | MDL3 预览版**纯读取**；这是作者的刻意设计 |
| `goto` / `bit` 运算 / LuaJIT 字节码 | ❌ 不可用 | 编译期就失败 |
| 资源替换（贴图/模型/音频） | ✅ 可用 | 走 `.patch_N`，与 Lua 运行时无关 |
| 盘上数值表 `.dl_bin` | ✅ 可用 | 需解封密钥 + 重算内容哈希，见 §6.3 |
| 未签名 native DLL | ❌ 不可用 | EAC 签名校验（MDL3 的桥是已签名的例外） |

#### 2.2.1 `ffi` 有两层，不要混为一谈

这是最容易写错、也最容易误判"老 mod 还能不能用"的一点。

| 层 | 10-20 之后 | 谁受影响 |
|---|---|---|
| **脚本层**：你的 `.lua` 里 `require('ffi')` / `bit` / `jit` | ❌ 彻底没有 | 所有直接调 ffi 的脚本，**任何加载器都救不了** |
| **加载器层**：MDL3 的签名 native 桥，宿主侧用 FFI 读内存 | ✅ MDL3 预览版具备 | 数据经 `HD2Data` 以字段形式给脚本，**只读** |

推论：

1. **"老 FFI mod 直接丢进来就能跑"是错的** —— API 重建过，必须按 Data Hub 字段重写。
2. **"任何加载器都救不回来"也是错的** —— MDL3 就是那个例外，它恢复的是**读能力**，不是脚本里的 `ffi`。
3. **写能力仍然没有** —— 预览版纯读取是作者的安全设计（"MDL3 预览版被设计为纯读取"），不要指望绕过。
4. 判断一个老 mod 的迁移成本：看它**读什么**。只读血条/弹药/HUD → 迁移到 Data Hub 可行；
   要改数值/改状态 → 这条路在当前版本走不通，回到路线 B/C。

> 一句话记忆：**`ffi` 从你的脚本里消失了，但 MDL3 替你把"读"接了回来，而且只接回了"读"。**

### 2.3 加载器生态（会互相打架，只能有一个占启动槽）

| 加载器 | 状态 | 定位 |
|---|---|---|
| **MDL3**（dev.36 预览 + HD2 Data Hub 0.3.0） | ✅ 新生态主力 | **游戏内**管理 mod：开关、重载、报错、帧耗时；**自带 FFI**（只读，经 Data Hub 给脚本）；**不替代 mod 管理器** |
| **Chef Shared Loader**（1.4.x） | ✅ 可用 | 多 mod 并存、独立沙箱、F9 统一选项菜单、崩溃保护 |
| **Boot Mod Loader** | ✅ 可用 | 老牌共享加载器，0.13.0+ 可与 Chef 交接 |
| **Bingus Shared Loader** | ⚠️ v20 在本版本不启动；v21 需别的加载器接管 | 历史包袱 |
| **VeganSquid Lua 加载器 0.11.0** | ✅ 可用 | 10-27 发布，替代启动脚本，兼容 `-- HD2-Addon:` 声明 |

**铁律**：游戏只有**一个**启动脚本槽位。多个加载器同时部署 = 只有优先级最高的那个生效，其余"看起来装了但没跑"。

### 2.4 MDL3 的三个必须知道的约束【文档】

1. **必须先装中间证书**：MDL3 的 `mdl_native_bridge.dll` 是签名组件，EAC 校验其证书链。
   缺证书 → 进游戏没有「MDL3 设置」页，或报 **error 193 / "不受信任的系统文件"**。
   修法：按包内 `MDL3-EAC-Fix-Kit-1.0.2` → `2_FIX_CERT_ADMIN.bat`（装 Certum Code Signing 2021 CA）→ **重启电脑**；
   仍不行再 `3_REPAIR_EAC_ADMIN.bat`（EAC 修复服务）。**这一步不关闭任何安全功能，也不要关杀毒/加白名单**。
2. **必须最高优先级**：MDL3 自带启动脚本，自带 boot 的 mod 排在它后面会让 MDL3 不启动。
3. **预览版是纯读取**：Data Hub 只提供读，不能写回游戏数据；且 patch 文件**超过 512 个**读不全
   （作者在发布页回复中确认这是保护性上限，后续版本会放宽）。

---

## 3. 三条路线 · 路由判据

```
目标是什么？
├─ 每帧要跑逻辑 / 要读单位与世界状态 / 要画 HUD
│    └─→ 路线 A：Lua 玩法脚本        §6.1   （唯一能改"行为"的路线）
├─ 只是把某个贴图/模型/音效换掉
│    └─→ 路线 B：资源替换            §6.2
└─ 只是把某个数值改大改小（伤害/冷却/弹容）
     └─→ 路线 C：数值表              §6.3   （社区工具，本技能只给边界）
```

**混合 mod 是允许的**：一个包可以同时含 Lua 脚本与资源。但要知道 **MDL3 在游戏内只能开关脚本部分**，
资源部分标 `LAUNCH ONLY`，仍需回管理器部署 + 重启。

---

## 4. 绝对不能犯的错误（红线清单）

> 这一节是本技能的核心。每条都给 **触发条件 / 后果 / 自检方法**。
> **P0 = 会造成不可逆后果或封号；P1 = 一定会失败；P2 = 会浪费大量时间。**

### P0 · 不可逆 / 违规

| # | 绝对不能做 | 后果 | 自检 |
|---|---|---|---|
| **1** | 在**游戏运行中**部署、替换、删除 `data/` 下的 patch 文件 | 文件被占用 → 部署半途失败 / 游戏读到半个包 → 崩溃或静默损坏 | `tasklist \| findstr /i helldivers` 必须为空 |
| **2** | 直接编辑**游戏目录里**的 `9ba626afa44a3aa3.patch_N` | 管理器用**硬链接**部署，游戏目录里的文件就是库文件的第二个名字 → 你改的是库，所有引用它的配置一起坏 | 只改库（`D:\HD2 Mods\...`），改完重新 deploy |
| **3** | 往唯一的启动脚本槽里**塞第二个加载器** | 只有一个生效，另一个"装了不跑"，症状是"mod 时灵时不灵"，极难排查 | 只选一个加载器；`hd2qd lua` 看启动脚本归属 |
| **4** | 写 `ffi` / `bit` / `jit` / `goto` / LuaJIT 字节码 | 10-20 之后编译期必失败。脚本层无替代，**必须重写**；只读数据可迁到 Data Hub | `python tools/hd2mod.py lint <脚本>`，`forbidden=0` |
| **5** | 自签名 DLL、注入进程、**自己**改游戏内存、关/绕 EAC | 封号风险；技术上 `577`/`193` 两条路都堵死。**读数据请用 Data Hub，不要自己动手** | 代码里出现 `ffi`、`LoadLibrary`、`OpenProcess` 即停 |
| **6** | 改 `.dl_bin` 后**不重算内容哈希**就重封 | 启动 `0xC000000D`，或静默不生效（更糟） | 走 §6.3 的哈希闸门，不手改字节 |
| **7** | 改已发布 mod 的 `manifest.Guid` | 管理器认成**另一个 mod**，新旧双份共存、互相覆盖 | Guid 生成一次，永久冻结 |
| **8** | 把 **HD2 Data Hub 打包进自己的 mod** | 重复 Data Hub，与 MDL3 自带的那份冲突 | 依赖写在 README，**不打包** |
| **9** | 同时用两个管理器部署（Arsenal + hd2qd / Echelon…） | 互相覆盖对方的部署记录，文件归属错乱 | 只用一个；换管理器先 `purge` |
| **10** | 做"影响同一局其他玩家"的改动 | 违反 ToS，也正是本轮 EAC 打击目标 | §1.2 的判断口径 |

### P1 · 一定失败

| # | 错误 | 症状 | 正确做法 |
|---|---|---|---|
| **11** | 资源 `file_id` ≠ `murmur64(模块路径)` | 包里明明有脚本，加载器找不到 / 静默不执行 | `hd2mod.py check` 会算；改 `file_id` 时三处要同步 |
| **12** | 首行声明 `-- HD2-Addon:` 与真实模块路径不一致 | 被别的加载器抢走或直接跳过 | 声明必须**逐字符**等于 `mods/<作者>/<名字>` |
| **13** | `manifest.Options[].Include` 指向不存在的文件夹 | 管理器部署 0 个文件，或报缺文件 | `check` 逐项比对大小写 |
| **14** | 跨 option 文件夹连续编号 `patch_0/1/2` | 管理器会**重新编号**，你写的编号被覆盖，内容错位 | 每个 option 文件夹**各自从 `patch_0` 开始** |
| **15** | 用中文 / 空格 / 大写做**模块路径** | 哈希与路径在部分加载器上不一致 | 模块路径只用 `[a-z0-9_]` |
| **16** | 发 LuaJIT 字节码（`\x1bLJ` 开头） | 加载即失败 | 只发 UTF-8 源码 |
| **17** | 依赖游戏内部偏移 / 内存地址 | 每次更新必崩，且崩在别人机器上 | 只用公开 API 与 Data Hub 字段 |
| **18** | patch 文件超过 512 个 | MDL3 读不全（dev.36 保护性上限） | 合并资源，控制包数 |

### P2 · 会浪费大量时间

| # | 错误 | 说明 |
|---|---|---|
| **19** | 在"已经装了一堆 mod"的环境上做基线测试 | 分不清是自己坏了还是别人冲突 |
| **20** | 不记 build 号就宣称"能用" | 下一次更新后无法判断是回归还是环境变了 |
| **21** | 不保留可复现构建（源码 + 打包参数） | 只能改二进制，等于不可维护 |
| **22** | 用第三方 `verify` 通过就认为"容器完全正确" | 它只验资源层；`srkit pack` 还会留下陈旧的"自身长度"字段【实测】 |
| **23** | 在 Git Bash 里用 `/tmp/xxx` 传路径给 Windows Python | Git Bash 的 `/tmp` ≠ Python 的 `C:\tmp`，会报文件不存在【实测】 |

---

## 5. 标准作业流程（Step 0–8）

> 顺序不可调换。每一步都有**合格判据**与**停的条件**。

### Step 0 · 立项卡（5 分钟，不写代码）

写清楚四行，缺一行就停：

```
玩法目标：<一句话，例：给飞行目标显示提前量准星>
改动边界：<只读 / 只画 / 不改他人状态>
依赖：    <MDL3 / Chef / 无>
失败样子：<怎么算没做成>
```

**停的条件**：说不清"玩家看到什么变化" → 回去问，不要开始写。

### Step 1 · 环境体检

一条命令搞定，**不要手写路径**（会自动找 Steam 库、mod 库、管理器）：

```bash
python tools/hd2mod.py doctor
```

正常输出长这样：

```
[ OK ] 游戏目录   <自动发现>
[ OK ] 游戏 build 26251122
[ OK ] 反作弊     EAC 已就位
[ OK ] mod 库     <自动发现>（与游戏同盘，部署走硬链接）
[ OK ] 管理器数据 <自动发现>
[ OK ] 加载器     MDL3：启用
[ -- ] srkit      未配置（Lua 路线不需要）
```

找不到游戏/库时：

```bash
python tools/hd2mod.py set-game "X:/Steam/steamapps/common/Helldivers 2"
python tools/hd2mod.py set-lib  "X:/HD2 Mods"
```

路径会记到 `~/.hd2-gameplay-mod/config.json`，下次不用再给。

**还要确认一件事**：游戏必须已退出（部署时才需要，但养成习惯）。

```bash
tasklist | findstr /i "helldivers" || echo "OK: 游戏未运行"
```

**合格判据**：`doctor` 通过，且 build 号记下来了。

### Step 2 · 选载体 + 定模块路径

- 模块路径格式：`mods/<作者>/<名字>`，全小写、下划线分隔。例：`mods/aabc/anti_air`
- **一旦发布不可改**（改了等于新 mod，且资源 ID 变）。
- 用 `srkit hash` 立刻算出资源 ID 并记下来：

```bash
python -m srkit hash "mods/<作者>/<名字>"
# mods/aabc/anti_air   murmur64=0x37FCC0A04812EAB6 murmur32=0x37FCC0A048
```

### Step 3 · 建工程

```bash
python tools/hd2mod.py new \
  --author <作者> --name <名字> --title "<显示名>" --out "<库>/_src/<名字>"
```

`--author` 和 `--name` 只用小写字母/数字/下划线（会进模块路径，发布后不能改）。
`--out` 建议放在 mod 库旁的 `_src`，与部署库分开。

产出：

```
<名字>/
├── manifest.json          # 管理器识别用（Guid 已生成，永久冻结）
├── mod.project.json       # 构建参数（module 就是这个 mod 的身份）
├── README.md              # 依赖声明（必须写）
├── CHANGELOG.md
├── src/main.lua           # 你只改这个
└── dist/                  # build 之后才有
```

### Step 4 · 写脚本（路线 A 的核心）

只改 `src/main.lua`。骨架已经带好首行声明与生命周期，**不要动第一行**。

写法约束（细节见 §7）：

```lua
-- HD2-Addon: mods/<作者>/<名字>
local M = {}

function M.on_enable(context)  end   -- 拿到 context.settings / context.log
function M.on_update(context, dt) end -- 每帧；dt 秒
function M.on_disable() end           -- 释放自己创建的一切
return M
```

### Step 5 · 打包

```bash
python tools/hd2mod.py build "<工程目录>" --zip
```

内部做的事（**不依赖 srkit**，容器由工具自己生成）：

1. 校验首行声明 == `mod.project.json.module`
2. `file_id = murmur64(module)`
3. 按已知格式生成单 lua 资源的 `9ba626afa44a3aa3.patch_0`
4. 落到 `dist/<ModName>/<Option>/`
5. 复制 manifest / README / CHANGELOG / cover

**合格判据**：产物字节数 = `192 + 8 + 脚本字节数`；`file_id` 等于模块路径哈希。

> 这条路已经和真实可加载的 mod 包做过**逐字节比对**（同输入 → 同字节），
> 并用第三方解析器 srkit 交叉验证过（`srkit list` 认得出 ID，`srkit check` 往返一致）。

### Step 6 · 静态门禁（不通过不许部署）

```bash
python tools/hd2mod.py check "<工程目录>"
```

必须全绿：

| 检查 | 判据 |
|---|---|
| 声明 vs 路径 | 首行 `-- HD2-Addon:` == `mod.project.json.module` |
| 资源 ID | `file_id == murmur64(module)` |
| 包自洽 | 头部记录的自长度 == 实际文件长度；payload 长度 == 脚本长度 |
| manifest | Guid 合法；Name / Version / Options 齐全 |
| 数量 | patch ≤ 512（MDL3 上限） |
| Lua 5.1 | 无 ffi/bit/jit/goto/位运算/BOM |
| 编码 | UTF-8 无 BOM |
| 体积 | 单脚本 ≤ 4 MB（Chef 上限） |

### Step 7 · 部署与实机验证

```bash
python tools/hd2mod.py install "<工程目录>"
```

这个命令会：把 `dist/` 下的成品复制进 mod 库 → 有 `hd2qd` 就直接 `add` + `deploy` →
没有就打印"拖进管理器点 Deploy"两步。

> 用户只需要记住一件事：**打开管理器 → 勾选新 mod → Deploy → 进游戏按 ESC**。

实机四问，逐条记录：

1. 加载器认到了吗？（MDL3 菜单里有条目 / Chef 的 F9 里有）
2. 有报错吗？（`%LOCALAPPDATA%\MDL3\Logs\MDL3.log`、`%APPDATA%\Arrowhead\Helldivers2\boot_mod_loader.log`）
3. 玩法效果对了吗？（对着 Step 0 的"失败样子"逐条比）
4. 关掉能干净退出吗？（`on_disable` 后无残留绘制、无帧耗时上升）

### Step 8 · 归档

见 §10。**没归档等于没做完** —— 下次更新你无法复现。

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

- `Version` 是**整数**，用于管理器判断新旧；对外版本号写进 `Name`。
- `Guid` 用 UUIDv4，**生成一次永不改**。
- `Options` 可以有多个，每个对应一个文件夹；这就是安装时的勾选项。

#### 6.1.2 资源 ID 规则（最容易错的一条）

`.patch_0` 里那条 `lua` 资源的 `file_id` **必须**等于 `murmur64("mods/<作者>/<名字>")`。

- 引擎按名字解析资源，名字→ID 就是 murmur64；不匹配等于"资源存在但没人叫得出名字"。
- `srkit list` 里 `name` 列显示为空是正常的 —— 这个包里没有名字表，名字由 ID 反推。

#### 6.1.3 手工打包（只在排错时用）

正常路径是 `hd2mod.py build`，**不需要 srkit**。下面这套只在"我要看看包里到底有什么"时用。

```bash
# 1) 解开看结构（学习格式，不要发布别人的内容）
python -m srkit unpack "<某个 lua mod 的 patch_0>" -o "<ws>"

# 2) 改 script.lua，并同步三处：
#    package.json  → entries[0].file_id / entries[0].resource_dir
#    resource.json → file_id
#    目录名        → lua_<新ID 的 16 位大写十六进制>

# 3) 打包
python -m srkit pack "<ws>" -o "<out>"

# 4) 验证资源层（不是容器层）
python -m srkit verify "<ws>"                            # 1 identical 才算编码正确
python -m srkit list "<out>/9ba626afa44a3aa3.patch_0"    # 看 ID 对不对
```

**两个必须知道的 srkit 行为**【实测】：

1. `pack` 会把容器按 16 字节对齐 → 产物长度与原件不同。判据是 `verify`（资源层）与 `list`（ID 层），不是 `cmp`。
2. `pack` **保留源包的"自身长度"字段**（头部 `0x20`）→ 重打包后尺寸变了，那个字段还是旧值。
   本技能自带的打包器会正确写入，所以 **Lua 包优先用 `hd2mod.py build`**。

#### 6.1.4 脚本契约【推断，已在一个实机可用 mod 上验证】

模块返回一个表，加载器按名字调：

| 成员 | 何时调 | 你要做什么 |
|---|---|---|
| `on_enable(context)` | 启用时 | 读 `context.settings`、注册选项、建状态 |
| `on_update(context, dt)` | 每帧 | 主逻辑；`dt` 单位秒，**必须判 `dt>0 and dt<1`** |
| `on_disable()` | 停用时 | 销毁 GUI、清表、置 nil |
| `diagnostics()` | 排错时 | 返回一张可打印的表 |

可用的全局（用 `rawget(_G, ...)` 取，不要直接索引，缺失会抛错）：

| 全局 | 用途 |
|---|---|
| `stingray` | 引擎 API 表（见 §7.2） |
| `HD2Data` | **Data Hub**：MDL3 用 FFI 读出来的游戏数据（血量/弹药/敌人/事件），只读。见 §6.1.5 |
| `MDL3` | 加载器句柄，用来判断"我是不是在 MDL3 下跑" |
| `MDL` | 含 `MDL.i18n.code`（语言码），做中英双语 |
| `ModOptionsMenu` | 选项菜单；`provider == 'MDL'` 时才有 `register_option` / `get` |

**为什么必须 `rawget`**：换加载器时这些全局可能不存在，直接 `MDL3.xxx` 会 nil 索引崩在别人机器上。

#### 6.1.5 用 Data Hub 读游戏数据（而不是用 ffi）

这是 10-20 之后"读内存"的**唯一正规途径**：脚本层没有 `ffi`，MDL3 用自己的签名 native 桥读，再以字段形式给你。

```lua
-- 不在顶层缓存：加载顺序不固定，Hub 被关掉后这个全局会消失
local function hub()
    local D = rawget(_G, 'HD2Data')
    if D and D.ready() then return D end
    return nil
end
```

三条硬规矩（来自官方字段参考）：

1. **每次用时再取**，不要 `local D = HD2Data` 放在模块顶部。
2. **所有字段都可能是 `nil`**（这一帧读不到或数值不合理），必须判空。
3. **第一次调用当帧返回 `nil`**，数据晚一帧；带租约的接口（`player` / `players` / `aim` 等）只在调用后 3 秒内每帧更新。

常用入口：`D.player()`、`D.player_ammo()`（**只有一个返回值**）、`D.players(detail)`、
`D.stratagems()`、`D.aim()`、`D.strikes()`、`D.mission()`、`D.on(event, cb, opts)`。
字段清单在 `For Modder/hd2data_field_reference_v0_3_0.md`，**不要凭记忆写字段名**。

> `D.set_option('getters', false)` 可以关掉"会调用游戏代码"的那部分读取，用于排错。

### 6.2 路线 B · 资源替换

```bash
# 路线 B 才需要 srkit；Lua 路线完全用不到
SRK="${HD2_SRKIT:-<srkit目录>}"

# 1) 从游戏里定位并解出目标资源（<游戏> 由 doctor 给出）
python -m srkit list "<游戏>/data" --type texture --limit 20
python -m srkit extract "<游戏 data 或某个 patch>" --id <resource-id> -o ./out

# 2) 解包成工作区
python -m srkit unpack "<源 archive>" -o ./ws --type texture

# 3) 换 payload（保持尺寸/格式一致最稳）
# 4) 往返验证
python -m srkit verify ./ws

# 5) 打包成 mod 归档
python -m srkit pack ./ws -o ./build
```

约束：

- **资源 ID 不能变**：换的是内容，不是身份。
- `.stream` / `.gpu_resources` 必须跟着它的 `patch_N` 一起走（同目录同名前缀）。
- 改尺寸/格式前先确认引擎接受（`verify` 只保证编码正确，不保证引擎满意）。
- 资源 mod 在 MDL3 里显示 `LAUNCH ONLY`，**不能**游戏内热开关。

### 6.3 路线 C · 数值表（只指路，不重造）

社区已有成熟工具链，**本技能不重写这部分**。你只需要知道边界与闸门：

| 环节 | 要点 |
|---|---|
| 载体 | `data/game/*.dl_bin`（松散加密文件），**不是** `.patch_N`，后者覆盖不了它 |
| 前置 | 需要游戏内置的 `recipient.pk` / `recipient.sk`；**本机 modtool 里没有现成密钥**，需按上游文档自行导出 |
| 闸门 | 改完必须重算 `MurmurHash64A(明文)` 并重新封装，否则 `0xC000000D` 或静默失效 |
| 换 build | 偏移类结论**逐 build 作废**，必须重跑基线对照；结构类结论可沿用 |
| 缓存污染 | 一旦在"自己已部署 mod"的状态下 dump，明文缓存被污染，之后所有"变没变"判断全错 |

需要动手时，直接读：

- `hd2-datamined/INDEX.md`（唯一索引入口；仓库自备，不在本技能内）
- 同目录 `BUILDS.md`（换 build 三步）、`docs/boundaries/MEMORY-ACCESS-25988413.md`（为什么内存路线死路）
- 同仓库 `skills/hd2-file-route-mod/SKILL.md`（方法论文档）

---

## 7. API / 工具约束

### 7.1 Lua 运行时约束（PUC Lua 5.1）

**可用**：`string` / `table` / `math` / `os.time` 等 5.1 标准库；`#`、`..`、`and/or`、闭包、元表。
**不可用（写了就编不过）**：

| 禁用 | 替代 |
|---|---|
| `ffi` / `bit` / `jit` | 脚本层无替代。**读数据走 MDL3 Data Hub**（§2.2.1）；要写内存 → 当前无解，改设计 |
| `goto` / `::label::` | 用 `while` + `break` 重构 |
| `//`、`<<`、`>>`、`&`、`|`、`~`（位运算） | `math.floor(a/b)`、乘除 2 的幂 |
| `\z` 转义、`\u{}` | 拼接，或写 UTF-8 原字节 |
| LuaJIT 字节码（`\x1bLJ`） | 发源码 |
| 单函数 > 200 局部变量 / > 60 上值 | 拆函数、上值改表 |

**必须**：UTF-8 **无 BOM**；`dt` 判空判正；所有引擎返回值判 `nil`（引擎大量接口会返回 nil）。

### 7.2 引擎 API（`stingray` 表）—— 已被实机 mod 用到的部分【实测】

| 命名空间 | 常用成员 | 说明 |
|---|---|---|
| `Vector3` | `x/y/z`、`distance`、构造 | 只取数值，**不要长期持有引擎向量**，转成 `{x,y,z}` 表 |
| `Unit` | `alive`、`node`、`has_node`、`world_position`、`num_cameras`、`has_animation_state_machine` | 单位查询；`alive` 必须先判 |
| `World` | `units`、`units_by_resource`、`destroy_gui`、`debug_camera_pose` | 世界级枚举；`units_by_resource` 用于按资源找同类单位 |
| `Gui` | `triangle` 等图元 | 2D 绘制；注意它用 **X/Z** 作屏幕坐标，layer 单独传参 |
| `Application` | `worlds()` | 找当前世界 |
| `Camera` | 相机位姿 | 世界坐标 → 屏幕坐标 |

写之前先确认接口存在：`if type(sr.Unit.alive) ~= 'function' then return end`。
**不要**猜函数名 —— 猜错的表现是运行期 nil，不是编译错误，极难定位。

### 7.3 工具约束

| 工具 | 是否必需 | 允许做什么 | 禁止做什么 |
|---|---|---|---|
| `tools/hd2mod.py` | **必需** | 体检 / 建工程 / 打包 / 门禁 / 安装 | 手改生成的 patch 字节 |
| `hd2-mod-cli` | 必需（部署） | 导入 / 部署 / 回滚 / 库管理 | 与别的管理器并用 |
| `MDL3` | 视目标 | 游戏内管理、Data Hub 读取 | 打包进自己的 mod、重复部署 |
| `srkit` | **可选**（只有路线 B 要） | 解包 / 列资源 / 改字节 / 重打包 / 往返校验 | 用它的 `pack` 生成 Lua 包（会留陈旧长度字段） |
| `hd2-datamined` | 可选（只有路线 C 要） | 读文档、跑离线工具 | 在游戏运行时改盘上文件 |

> **为什么 Lua 包不用 srkit 打**：`srkit pack` 会保留源包的"自身长度"字段（头部 `0x20`），
> 重新打包后尺寸变了、字段还是旧值。本技能自带的打包器会正确写入，且已与真实包逐字节对齐。

**MDL3 分发限制【文档】**：非自由软件。**不得**二次上传/改包分发；**可以**做依赖它的 mod，但必须在 README 写明依赖并链回官方发布页。不要把 MDL3 打进你的整合包。

### 7.4 管理器（hd2-mod-cli）工作流适配

**路径不要写死**，全部由 `doctor` 探测并记到 `~/.hd2-gameplay-mod/config.json`。

| 概念 | 说明 |
|---|---|
| 数据目录 | `%USERPROFILE%\.hd2-mod-cli`（`config.json` / `library.json` / `deployed.json`） |
| 库目录 | 由 `doctor` 找出（通常与游戏同盘 → **硬链接部署**，不占额外空间） |
| 游戏目录 | 由 `doctor` 从 Steam 库自动发现 |
| 排序语义 | **列表越靠下优先级越高**；加载器由 `loader` 单独选择，部署时排在所有 mod 之后 |
| 部署单位 | `<游戏>/data/9ba626afa44a3aa3.patch_N`（N 由管理器连续重排） |

常用（若 `hd2qd` 未在 PATH，用 GUI 的同等功能）：

```bash
hd2qd list --files          # 看加载顺序与 patch 编号
hd2qd status                # 只显示"部署会做什么"，不改盘
hd2qd deploy --dry-run      # 同上，更细
hd2qd lua                   # 部署前 Lua 检查（启动脚本归属 / 哪些 mod 不会启动）
hd2qd lua-syntax <file>     # 该 Lua 能否在本版本 PUC 5.1 上编译
hd2qd conflicts -v          # 多 mod 共用资源与优胜者
hd2qd purge --yes           # 恢复原版（只删游戏目录 patch，库不动）
hd2qd profile-new <名字>    # 建一个只含本 mod 的配置，做干净基线
```

> **干净基线测试**：`profile-new test --empty` → `profile-add <你的mod>` → `profile-use test`。
> 这是唯一能排除"别人的 mod 干扰"的方法。

### 7.5 换 build 后的复验清单

游戏更新后，按顺序跑，任一步不过就停：

1. `python tests/selftest.py`（srkit 自检）
2. `python -m srkit info "<游戏>/data"`（归档形态还认不认；<游戏> 由 doctor 给出）
3. 记录新 build 号，与 `verified-build` 对比
4. 你自己的 mod：`hd2qd lua` 看是否仍被识别、`hd2qd lua-syntax` 看是否仍能编译
5. `srkit list` 你的 `patch_0`，确认 `file_id` 仍等于 `murmur64(module)`
6. 实机跑一次 Step 7 的四问

---

## 8. 常见误区

### 8.1 认知层

| 误区 | 事实 |
|---|---|
| "EAC 一直在，所以要先关 EAC 才能 mod" | 10-20 之前是 GameGuard。EAC 是新换的，且**不需要也不能关** |
| "EAC 把 Lua mod 封了" | 不是。是 LuaJIT 被换成 PUC 5.1，脚本层的 `ffi` 没了。纯 Lua 脚本照样能跑 |
| "装个加载器就能救回老 mod" | 半对半错：**读**的能力被 MDL3 恢复了（经 Data Hub），但 API 重建过，老 mod 必须**重写**才能跑，不能直接丢进去 |
| "MDL3 没有 FFI，所以读内存彻底没戏" | 错。MDL3 **自带 FFI**（作者原话），用自己的签名 native 桥在宿主侧读；脚本只是不能直接 `require('ffi')` |
| "MDL3 是 mod 管理器，装了就不用 Arsenal 了" | 不是。MDL3 只管**游戏内**开关与重载；装/部署仍要靠管理器 |
| "MDL3 能改游戏数据" | 预览版**纯读取**，作者刻意如此设计。只给读，不给写 |
| "社区说安全就安全" | Arrowhead 从未发布安全名单；风险自负 |

### 8.2 技术层

| 误区 | 事实 |
|---|---|
| "patch 文件编号我自己定" | 你的编号只是源文件夹里的顺序，部署时管理器**重排** |
| "资源 ID 随便填，反正能读出来" | 引擎按名字哈希找资源，ID 错 = 找不到 |
| "`srkit verify` 过了就万事大吉" | 只证明**资源编码**可逆，不证明引擎/加载器接受 |
| "改完直接覆盖游戏目录里的 patch" | 硬链接，你改的是库 |
| "Lua 里 `print` 能看日志" | 能，但不同加载器落到不同日志；写自己的日志文件才是可靠手段 |
| "`dt` 可以直接乘" | `dt` 可能是 nil / 0 / 异常大（切图、卡顿），必须夹紧 |

### 8.3 流程层

| 误区 | 事实 |
|---|---|
| "先写三千行再说" | 先用 20 行验证"能加载、能画一个点"，再往上堆 |
| "在自己装满 mod 的环境里测就行" | 冲突与自身 bug 分不开，用 `profile-new` 建干净基线 |
| "能跑就不用记 build" | 下次更新你无法判断是回归还是环境变了 |

---

## 9. 排错对照表

| 症状 | 最可能原因 | 怎么查 | 怎么修 |
|---|---|---|---|
| mod 装了，游戏里完全没反应 | 资源 ID 与模块路径不匹配 | `srkit list` 看 `file id`；`srkit hash` 对比 | 改 `file_id` 重新打包 |
| 加载器列表里有，但不执行 | 首行声明与路径不一致 / 被别的加载器抢槽 | 看加载器日志里的 `name` | 统一声明；只留一个加载器 |
| 进游戏就崩，删掉我的 mod 就好 | Lua 5.1 不兼容语法 / `dt` 未判空 / 引擎接口不存在 | `hd2qd lua-syntax`；逐段注释二分 | 按 §7.1 改 |
| 部署报错 / 部署一半 | 游戏还在运行 | `tasklist` | 退出游戏重部署 |
| 改完管理器的库也坏了 | 直接改了游戏目录里的 patch（硬链接） | `hd2qd status --verify` | 从备份/重新下载恢复库 |
| MDL3 菜单里没有「MDL3 设置」 | 缺 Certum 中间证书，EAC 拦了 native 组件 | 看是否 error 193 / "不受信任的系统文件" | `2_FIX_CERT_ADMIN.bat` → **重启** → 仍不行 `3_REPAIR_EAC_ADMIN.bat` |
| 两个 mod 只有一个生效 | 两个都占了启动槽 | `hd2qd lua` 看启动脚本归属 | 只留一个加载器，其余改成 addon |
| 资源 mod 在 MDL3 里不能开关 | 正常。资源标 `LAUNCH ONLY` | — | 回管理器部署 + 重启 |
| 我的 mod 在别人机器上崩 | 用了硬编码路径 / 用户目录 / 未判空 | 代码审查 | 只用引擎 API 与 Data Hub |
| 换 build 后全部失效 | 运行时/接口变了 | §7.5 清单 | 按结果重做，不要猜 |

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
├── src/main.lua
├── assets/cover.jpg
└── build/Core/9ba626afa44a3aa3.patch_0

D:\HD2 Mods\<ModName>_<后缀>\      ← 部署库（由管理器 add 进来）
```

**源工程与部署库分离**：库里放的是"可安装形态"，源工程放的是"可重建形态"。混在一起，一次误删就没了。

### 10.2 版本与标识

| 项 | 规则 |
|---|---|
| `manifest.Guid` | UUIDv4，**生成一次，永不修改** |
| `manifest.Version` | 整数，每次发布 +1（管理器用它判新旧） |
| 对外版本号 | SemVer 写进 `Name`/`Description`，例：`我的MOD v1.2.0` |
| 模块路径 | `mods/<作者>/<名字>`，全小写，**发布后冻结** |
| 每次构建记录 | build 号 / srkit 版本 / 脚本 sha256 / patch sha256 |

### 10.3 README 必含四项

```markdown
## 依赖
- 需要 MDL3 3.0.0-dev.36+（官方发布页：<链接>）
- 不需要 HD2 Data Hub

## 兼容性
- 验证 build：26251122（2026-11-05）
- 与其他加载器：仅可在 Chef Shared Loader 下共存，不要同时启用 XX

## 已知问题
- ...

## 卸载
停用并重新部署即可；不写入任何用户目录。
```

### 10.4 发布包结构

```
<ModName>-v1.2.0.zip
├── manifest.json
├── README.md
├── CHANGELOG.md
├── cover.jpg
└── Core/9ba626afa44a3aa3.patch_0
```

zip 根目录**直接**放 `manifest.json`（不要多套一层文件夹，部分管理器不认）。

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
| **本技能工具** | `tools/hd2mod.py` | 零依赖；`doctor/new/build/check/install/lint` |
| mod 管理器 | `hd2qd`（PATH）或 `HD2 Mod Quick Deploy.exe` | hd2-mod-cli；`doctor` 会自动找 |
| MDL3 + Data Hub | 官方发布页下载 | dev.36 / Hub 0.3.0，**必须放最高优先级** |
| MDL3 EAC 修复包 | 随 MDL3 包附带 `MDL3-EAC-Fix-Kit-*.zip` | 菜单不出现时用 |
| srkit | 可选，自备 | 只有路线 B 需要 |
| hd2-datamined | 可选，自备 | 只有路线 C 需要 |

> 除本技能工具外，其它都不是必需品。**只做路线 A 的话，一个 `hd2mod.py` 加一个管理器就够了。**

### 11.2 证据来源

- `【文档】` MDL3 包内 `README_zh.md`、`For Modder/hd2data_field_reference_v0_3_0.md`；hd2-mod-cli 仓库 README；srkit README
- `【文档】` MDL3 官方发布页（dev.36）§2.2 "FFI support"、§3.1 "预览版是纯读取"、§10 "为什么不开源"、§11 FAQ 作者回复
- `【实测】` 本机 build 26251122：srkit 往返、从零构造包、资源 ID 规则、已部署 mod 结构
- `【推断】` 从 `D:\HD2 Mods` 中一个实机可用 mod 的脚本反推的生命周期契约

### 11.3 术语

| 词 | 含义 |
|---|---|
| patch 文件 | `9ba626afa44a3aa3.patch_N`，mod 的部署单位；文件名固定，编号由管理器排 |
| 启动脚本槽 | 游戏只跑一个 boot 脚本，谁占谁赢 |
| addon | 不占启动槽、由加载器启动的脚本，首行声明 `-- HD2-Addon:` |
| 模块路径 | `mods/<作者>/<名字>`，同时决定资源 ID |
| Data Hub | MDL3 附带的只读数据接口层 |
| LAUNCH ONLY | MDL3 中标记"只能靠管理器部署、不能游戏内开关"（资源类） |
