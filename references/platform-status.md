# 平台现状（2026-11-05）

> 这份文件只记录**会过期的事实**。每条都写了「什么时候必须重新核实」。
> 主文档 `SKILL.md` 里的结论若与本文件冲突，**以本文件为准**；本文件过期时，先更新这里，再回头改主文档。

## 1. 时间线

| 日期 | 事件 | 对 mod 的影响 |
|---|---|---|
| 2026-10-20 之前 | 反作弊是 **nProtect GameGuard**；Lua 运行时是 **LuaJIT** | `ffi` 可用，内存类 mod 存在 |
| 2026-10-19 | Arrowhead 公告将切换到 EAC | — |
| **2026-10-20** | **7.2.0：GameGuard → EAC**；Lua 运行时改为内置 **PUC-Rio Lua 5.1** | `ffi`/`bit`/`jit` 消失；`core/wwise/lua/wwise_flow_callbacks` 被移除 |
| 2026-10-22 | 7.2.1 修 squad 进出崩溃 | — |
| 2026-10-27 | 官方发布启动崩溃清理指引；同日社区 Lua 加载器 0.11.0 发布 | 生态开始恢复 |
| 2026-11-01 | Chef Shared Loader 1.4.x 迭代；MDL3 修复包 1.0.2 | — |
| 2026-11-05 | 本机验证：build **26251122**，MDL3 **3.0.0-dev.36**，Data Hub **0.3.0** | — |

## 2. 必须记住的三条更正

### 2.1 EAC 不是"一直都有"

2026-10-20 之前 HD2 用 GameGuard。网上大量"关掉 EAC 才能装 mod""EAC 会扫 mod 目录"的说法，
要么是别的游戏的经验，要么是 GameGuard 时代的误传。**照做会得出错误结论**。

### 2.2 EAC 没有封杀 Lua mod

同一次更新里真正的杀手是 **LuaJIT → PUC 5.1**：

- `ffi` 没了 → 所有读写游戏内存的 mod 永久失效，**任何加载器都无法恢复**。
- `bit`、`jit` 没了 → 依赖位运算/字节码的脚本编译期就失败。
- 被 Bingus Shared Loader 依赖的 boot 脚本被删 → 旧加载链断裂。

而游戏**仍然**从 mod 加载启动脚本、**仍然**每帧跑 Lua update —— 这就是新加载器（Chef / BML / MDL3）能工作的缝隙。

**推论**：判断一个老 mod 还能不能用，看它**有没有用 `ffi`**，而不是看它"是不是 Lua mod"。

### 2.3 EAC 会拦的是 **native 组件**，不是数据文件

实测与社区记录一致的结论：

| 情况 | 结果 |
|---|---|
| 未签名 DLL | `577` |
| 已签名但不在允许名单 | `193` |
| 自签名并装进 `LocalMachine\Root` | 仍然 `577` |
| 正规 CA 签发 + 中间证书在系统证书库 | 通过 |

MDL3 的 `mdl_native_bridge.dll` 走的是最后一条。缺 **Certum Code Signing 2021 CA** 中间证书时，
链验证失败 → 报 `193` 或"不受信任的系统文件" → 游戏里看不到「MDL3 设置」页。

修复（**不关闭任何安全功能**）：

1. 包内 `MDL3-EAC-Fix-Kit-1.0.2.zip` 整个解压
2. `1_CHECK.bat`（只读，桌面生成 TrustCheck 报告）
3. `2_FIX_CERT_ADMIN.bat`（管理员）→ **重启电脑** → 进游戏看
4. 仍有问题：`3_REPAIR_EAC_ADMIN.bat`（管理员，走 EAC 自带"修复服务"）
5. 要撤销：`9_UNDO_CERT_ADMIN.bat`

> 官方说明明确：关杀毒、加白名单、换安装目录、重装 MDL3 **都无效**，不需要做。

## 3. 加载器现状

| 加载器 | 当前状态 | 占启动槽 | 备注 |
|---|---|---|---|
| **MDL3 3.0.0-dev.36** | 可用（预览） | 是 | 游戏内管理；自带 FFI 读取（经 Data Hub）；**纯读取**；patch > 512 读不全 |
| **Chef Shared Loader 1.4.x** | 可用 | 是 | 多 mod 沙箱、F9 菜单、崩溃保护；可接管 BML / Bingus v21 的 mod |
| **Boot Mod Loader 0.13.0+** | 可用 | 是 | 可与 Chef 交接（Chef-only mod 交给 Chef 启） |
| **Bingus Shared Loader** | v20 在本版本不启动；v21 需别的加载器接管 | 是 | 历史包袱，不建议新项目依赖 |
| **VeganSquid Lua 加载器 0.11.0** | 可用 | 是 | 2026-10-27 发布；兼容 `-- HD2-Addon:` 声明 |

**规则**：启动槽只有一个。谁优先级最高谁生效，其余"装了不跑"。

## 4. MDL3 的边界（写 mod 前必须知道）

| 项 | 结论 |
|---|---|
| 它是什么 | 游戏内 mod 管理器 + 加载器，不是 mod 安装器 |
| 能做什么 | 游戏内启动/停止/重载脚本、显示状态与报错、帧耗时、安全模式、选项菜单 |
| 不能做什么 | 安装/部署 mod；改游戏数据（预览版纯读取） |
| 资源类 mod | 显示 `LAUNCH ONLY`，必须回管理器部署 + 重启 |
| 混合 mod | 游戏内只能开关脚本部分 |
| 分发 | **非自由软件**，禁止二次分发/改包；依赖它的 mod 必须链回官方发布页 |
| patch 上限 | 约 512 个（保护性措施，后续版本可能放宽） |
| Data Hub | 随包附带，单独开关；**不要打包进自己的 mod** |

## 5. 本机环境快照

| 项 | 值 |
|---|---|
| 游戏目录 | `D:\Steam\steamapps\common\Helldivers 2` |
| build | `26251122` |
| EAC | `EasyAntiCheat\` + `start_protected_game.exe` 存在 |
| mod 库 | `D:\HD2 Mods`（与游戏同盘 → 硬链接部署） |
| 管理器 | `C:\Users\50709\Desktop\HD2 Mod Quick Deploy.exe`（hd2-mod-cli） |
| 管理器数据 | `%USERPROFILE%\.hd2-mod-cli\` |
| 工具根 | `C:\Users\50709\Downloads\modtool` |

## 6. 重新核实的触发条件

出现以下任一情况，**先回来更新本文件**，再动代码：

- Steam 更新了 HD2（build 号变了）
- MDL3 / Chef / BML 发了新版本
- 加载器菜单里出现"unsupported"
- 你自己或用户的 mod 在"昨天还能跑"的情况下失效
- Arrowhead 再发反作弊或 mod 相关公告

核实渠道（按可信度排序）：

1. 游戏内实测 + 本地日志（`%LOCALAPPDATA%\MDL3\Logs\MDL3.log`、`%APPDATA%\Arrowhead\Helldivers2\boot_mod_loader.log`）
2. MDL3 官方发布页（含 README、FAQ、评论区作者回复）
3. 加载器作者页面（Chef / BML / VeganSquid）
4. `hd2-mod-cli` README（管理器行为与 Lua 检查）
5. 社区论坛 —— **只作线索，不作依据**
