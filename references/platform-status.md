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
| 2026-10-28 | **HD2SDK: Community Edition v3.11.1** | 模型/贴图路线的主力工具；支持 Blender 4.0–5.2 |
| 2026-10-15 | HD2SDK-AQ-Edition v2.5.6（中文改版） | 可选：额外材质模板、PNG/TGA 自动转 DDS、ZIP 导出 |

## 2. 必须记住的三条更正

### 2.1 EAC 不是"一直都有"

2026-10-20 之前 HD2 用 GameGuard。网上大量"关掉 EAC 才能装 mod""EAC 会扫 mod 目录"的说法，
要么是别的游戏的经验，要么是 GameGuard 时代的误传。**照做会得出错误结论**。

### 2.2 EAC 没有封杀 Lua mod

同一次更新里真正的杀手是 **LuaJIT → PUC 5.1**：

- **脚本层**：`ffi` 从游戏 VM 里消失 → `.lua` 里 `require('ffi')` 必失败，这一条对所有加载器成立。
- **加载器层**：MDL3 **自带 FFI**（作者原话："MDL3 带有 FFI，可以读取游戏本身不对 MOD 开放的数据"），
  用自己的**签名 native 桥**在宿主侧读，再经 HD2 Data Hub 把字段给脚本。所以"读"恢复了，"写"没有。
- `bit`、`jit` 没了 → 依赖位运算/字节码的脚本编译期就失败。
- 被 Bingus Shared Loader 依赖的 boot 脚本被删 → 旧加载链断裂。

而游戏**仍然**从 mod 加载启动脚本、**仍然**每帧跑 Lua update —— 这就是新加载器（Chef / BML / MDL3）能工作的缝隙。

**推论（两条，缺一不可）**：

1. 判断一个老 mod 还能不能用，先看它**要不要写内存**：只读 → 可迁移到 Data Hub；要写 → 当前版本无解。
2. 就算只读，也**不能直接跑** —— API 重建过，作者回复原话是 *"Need to update, Cause I rebuild the api"*。
   所以"装了 MDL3 老 ffi mod 就能复活"和"任何加载器都救不回来"**两种说法都是错的**。

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
| **MDL3 3.0.0-dev.36** | 可用（预览） | 是 | 游戏内管理；**自带 FFI**（只读，经 Data Hub 给脚本）；patch > 512 读不全 |
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
| **FFI** | **自带 FFI**（作者原话："MDL3 带有 FFI，可以读取游戏本身不对 MOD 开放的数据"）。宿主侧读，经 Data Hub 给脚本；**脚本内不能 `require('ffi')`** |
| 不做什么 | 安装/部署 mod；界面里没有写数据入口（预览版只读） |
| 资源类 mod | 显示 `LAUNCH ONLY`，必须回管理器部署 + 重启 |
| 混合 mod | 游戏内只能开关脚本部分 |
| 分发 | **非自由软件**，禁止二次分发/改包；依赖它的 mod 必须链回官方发布页 |
| patch 上限 | 约 512 个（保护性措施，后续版本可能放宽） |
| Data Hub | 随包附带，单独开关；**不要打包进自己的 mod** |

## 4.5 模型 / 资源 mod 的现状（与 Lua 路线分开看）

模型 mod 不经过 Lua VM，也不依赖 MDL3；10-20 的运行时变更对它**没有直接影响**：

| 项 | 结论 | 证据 |
|---|---|---|
| 护甲 / 头盔 / 武器 / 贴图替换 | ✅ 仍可用 | 社区持续更新；本机有可运行的武器模型 mod |
| 制作工具 | Blender + **HD2SDK CE v3.11.1** | GitHub release 2026-10-28 |
| 部署 | 管理器部署 + **重启** | 资源 mod 在 MDL3 里标 `LAUNCH ONLY` |
| 游戏内热开关 | ❌ | MDL3 只能开关脚本部分 |
| 多 mod 冲突 | 同一 `(type, resource_id)` 后加载者赢 | 用干净配置排查 |
| 游戏更新后失效 | 常见：unit 数据/裁剪信息变了 | 用 HD2 Retagger 的 Update Old Mod 尝试修复 |
| 反作弊 | 客户端外观改动通常不触发 EAC，但非官方保证 | SDK README 免责声明 + 社区实践 |

**与 Lua 路线的分工**：

- 只改外观 → 模型路线（本文件 §4.5 + `model-pipeline.md`）。
- 要改行为/HUD/读数据 → Lua 路线（`SKILL.md` §6.1）。
- 两者可以同一个包里共存，但资源部分仍需重启，MDL3 只能开关脚本部分。

### 4.6 SDK 启动会联网，且两个请求没有超时

`HD2SDK-CommunityEdition/__init__.py` 在 `register()` 里固定做三件事：

| 调用 | 超时 | 不处理会怎样 |
|---|---|---|
| `CheckAddonUpToDate()` | 5 s | 慢，但会过 |
| `UpdateArchiveHashes()` | **无** | 卡在 `api.github.com` / `raw.githubusercontent.com`，headless 构建永久挂住 |
| `UpdateFriendlyNames()` | **无** | 同上 |

国内网络下 `blender -b` 会**看起来像卡死**（CPU 接近 0、日志停在
`Checking If Addon is up to date...`）。处理办法（二选一）：

1. **给本地 addon 打补丁**（推荐，一次性）：
   两个 `requests.get(...)` 加 `timeout=5`，并在函数开头加
   `if os.environ.get("HD2SDK_OFFLINE") == "1": return`；
   之后所有 headless 构建都用 `HD2SDK_OFFLINE=1 blender -b ...`。
2. 用不可达代理强制快速失败：`HTTPS_PROXY=http://127.0.0.1:9`（不总是生效）。

加超时不影响 GUI 正常使用；只是断网时不再挂死。

## 5. 环境由 `doctor` 探测，不要写死

不同人的游戏目录、mod 库、管理器位置都不一样。**任何文档里都不要写死路径**，
统一跑：

```bash
python tools/hd2mod.py doctor
```

它会自动：

| 找什么 | 怎么找 |
|---|---|
| 游戏目录 | 配置缓存 → `HD2_GAME` → Steam 注册表 → `libraryfolders.vdf` 遍历所有库 |
| 游戏 build | 同级 `appmanifest_553850.acf` 的 `buildid` |
| mod 库 | 配置缓存 → `HD2_LIB` → 游戏同盘的 `HD2 Mods` → 常见盘符 |
| 管理器 | `hd2qd` 在 PATH？→ `%USERPROFILE%\.hd2-mod-cli` 有库数据？→ 桌面的 GUI |
| 加载器 | 读管理器的 `library.json`，列出 MDL3 / Chef / BML / Bingus 及启用状态 |
| Blender | `HD2_BLENDER` → 配置 → PATH → `Program Files/Blender Foundation` 等常见目录 |
| HD2SDK | `HD2_SDK` → 配置 → `%APPDATA%/Blender Foundation/Blender/*/scripts/addons/*` → extensions |

探测到的路径会写进 `~/.hd2-gameplay-mod/config.json`，下次直接复用。
找不到时用 `set-game` / `set-lib` / `set-sdk` 手动指定一次即可。

> 参考基线（作者机器，仅作对照，**不要当作通用路径**）：
> build `26251122` · EAC 已就位 · 库与游戏同盘 · MDL3 启用 · `hd2qd` 未进 PATH（走 GUI）。

## 6. 重新核实的触发条件

出现以下任一情况，**先回来更新本文件**，再动代码：

- Steam 更新了 HD2（build 号变了）
- MDL3 / Chef / BML 发了新版本
- Blender / HD2SDK 发了新版本（尤其是 major / 4.1+ API 变更）
- 加载器菜单里出现"unsupported"
- 你自己或用户的 mod 在"昨天还能跑"的情况下失效
- 模型/贴图 mod 出现“只有本版本崩”“部件消失”“装备界面崩”
- Arrowhead 再发反作弊或 mod 相关公告

核实渠道（按可信度排序）：

1. 游戏内实测 + 本地日志（`%LOCALAPPDATA%\MDL3\Logs\MDL3.log`、`%APPDATA%\Arrowhead\Helldivers2\boot_mod_loader.log`）
2. MDL3 官方发布页（含 README、FAQ、评论区作者回复）
3. 加载器作者页面（Chef / BML / VeganSquid）
4. `hd2-mod-cli` README（管理器行为与 Lua 检查）
5. 社区论坛 —— **只作线索，不作依据**
