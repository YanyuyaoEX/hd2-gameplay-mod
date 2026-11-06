# hd2-gameplay-mod

《绝地潜兵2》(Helldivers 2) **mod 开发技能** —— 给 AI 用的可执行作业手册，不是教程散文。

覆盖两条主线：

- **玩法 mod**：纯 Lua 5.1 脚本，做 HUD、提示、QoL、读游戏数据。
- **模型 / 贴图 mod**：用 Blender + HD2SDK 替换护甲、头盔、武器、道具、材质，
  导出 patch 后自动收编、打包、门禁、部署。

面向 2026-10-20 之后的真实环境：**EAC 已替换 GameGuard**、**LuaJIT 已换成 PUC Lua 5.1**、
MDL3 3.0.0 预览与 HD2 Data Hub 0.3.0 上线；模型路线则依赖 **HD2SDK v3.11.x**。

## 它解决什么问题

网上绝大多数 HD2 mod 教程停在 10 月 20 日之前，照做必失败：

- 说“要关 EAC”——那时根本没有 EAC，用的是 GameGuard。
- 说“Lua mod 被 EAC 封了”——不是。是 LuaJIT 被移除，脚本层的 `ffi` 没了。
- 说“装个加载器就能救回老 mod”——只说对一半。MDL3 **自带 FFI**（经签名 native 桥在宿主侧读），
  所以“读”的能力回来了；但 API 重建过，老 mod 必须按 HD2 Data Hub 的字段重写，不能直接丢进去跑。
- 模型教程散落在 wiki / 视频 / Discord，没人把 **“SDK 导出 → 收编 → 打包 → 门禁 → 部署”**
  这条链写成可执行流程。

本技能把这些更正写进流程，并把「一定失败的做法」列成可自检的工程坑清单。

## 内容

| 文件 | 作用 |
|---|---|
| `SKILL.md` | 主文档：范围、现状更正、路线路由、**工程坑清单**、Lua/模型两套流程、读数据三条路径、误区、排错、归档 |
| `references/model-pipeline.md` | **模型路线（通用/护甲）**：护甲/头盔/道具/贴图，Blender + HD2SDK 的具体按钮、权重、材质、LOD、排错 |
| `references/weapon-pipeline.md` | **武器替换专线**：L1/L2/L3 三层、握把对齐、`bolt`/`charging_handle`、LOD、`attach_muzzle`/`optic`/`mag`、弹匣、排错 |
| `references/case-sg225-jfzl.md` | 实战案例：SG-225 Breaker → 飓风之龙，含对齐矩阵、材质模板、patch 结构 |
| `references/platform-status.md` | 会过期的事实（EAC 时间线、加载器矩阵、MDL3 边界、SDK 版本），含重新核实触发条件 |
| `references/lua-contract.md` | 脚本生命周期契约、`context`、全局对象、引擎 API、三条纪律、最小样例 |
| `references/packaging.md` | `.patch_N` 容器结构（Lua + 多资源）、资源 ID 规则、伴生文件、部署语义、复验命令 |
| `tools/hd2mod.py` | 零依赖：体检 / 查 archive / 建工程 / 收编 SDK 导出 / 打包 / 门禁 / 检查 / 安装 |
| `tools/blender_preflight.py` | 在 Blender 里只读检查模型：骨架、UV、权重、贴图尺寸、面数 |
| `tools/selftest.py` | 零依赖自检：不看游戏也能验证工具链 |

## 快速开始（玩法 / Lua）

```bash
SKILL="<本技能目录>"

# 0) 体检：自动找游戏 / mod 库 / 管理器
python "$SKILL/tools/hd2mod.py" doctor

# 1) 建工程
python "$SKILL/tools/hd2mod.py" new \
  --author yourname --name mymod --title "我的玩法 MOD" \
  --out "<库>/_src/mymod"

# 2) 写 src/main.lua（只改这个文件）

# 3) 打包
python "$SKILL/tools/hd2mod.py" build "<工程目录>" --zip

# 4) 过门禁（全绿才能部署）
python "$SKILL/tools/hd2mod.py" check "<工程目录>"

# 5) 装进库并提示部署
python "$SKILL/tools/hd2mod.py" install "<工程目录>"
```

`hd2mod.py` 会自动把资源 ID 设成 `murmur64("mods/<作者>/<名字>")` —— 这是最容易错、
错了又不报错的一步。

## 快速开始（武器模型 / 主推）

```bash
# 0) 先装 Blender + HD2SDK，再体检
python tools/hd2mod.py doctor

# 1) 查目标武器的 archive（读本机 SDK 索引）
python tools/hd2mod.py lookup "AR-61"

# 2) 建武器工程
python tools/hd2mod.py new --kind model \
  --title "AR-61 换成 XX" --subject "AR-61 Tenderizer" \
  --target-kind weapon --out "<库>/_src/ar61_xx"

# 3) 预检要用的模型
blender -b --python tools/blender_preflight.py -- "C:/path/model.fbx" --target weapon

# 4) 在 Blender 里按 PLAN.md / references/weapon-pipeline.md 做
#    导入 unit → 对齐握把 → 试装 → 绑 boss/顶点组 → 材质/LOD
#    → Save Units → Write Patch → Export Patch

# 5) 收编 SDK 导出的 zip
python tools/hd2mod.py adopt "<工程目录>" --from "<SDK导出的zip>"

# 6) 打包 + 门禁 + 装库
python tools/hd2mod.py build "<工程目录>" --zip
python tools/hd2mod.py check "<工程目录>"
python tools/hd2mod.py install "<工程目录>"
```

护甲/头盔把 `--target-kind armor`、`lookup "B-01"` 换掉，流程看
`references/model-pipeline.md`。武器不需要 Avatar Rig，也不要求全身骨骼。

模型路线不会替你“生成”一个绑定模型；它负责查目标、判可行性、检查素材、收编导出、
打包、门禁、部署和排错。**装完必须重启游戏**，资源 mod 不能游戏内热开关。

## 依赖

**Lua 路线零依赖。** Python 3.11+ 标准库就够，打包器是内置的：

- 补丁容器由 `tools/hd2mod.py` 直接生成，已与真实可加载的 mod 包做过**逐字节比对**
- 并用第三方解析器 srkit 交叉验证（`srkit list` 认得出 ID，`srkit check` 往返一致）
- 不需要 srkit、不需要 Blender、不需要编译工具链

**模型路线**需要：

- Blender 4.0–5.2
- HD2SDK: Community Edition 3.11.x（装进 Blender）
- 一个 mod 管理器（Arsenal / HD2MM / hd2-mod-cli 任一）

| 组件 | 必需？ | 用途 |
|---|---|---|
| Python 3.11+ | 必需 | 跑 `hd2mod.py` / `selftest.py` |
| hd2-mod-cli / Arsenal / Echelon | 必需（部署） | 把 mod 装进游戏 |
| Blender + HD2SDK | 模型路线必需 | 改 unit 资源、导出 patch |
| MDL3 | Lua 路线可选 | 游戏内开关与读 Data Hub |
| srkit | 可选 | 深层排错/手工看 archive |
| hd2-datamined | 可选 | 改数值表时才要 |

## 自检

```bash
python tools/selftest.py
```

不需要游戏、Blender、srkit；会验证 Lua 包头、资源包解析、模型工程 new→adopt→build→check、
缺伴生文件拦截、lookup 索引。

## 给别人用

把整个目录丢给对方（或 `git clone`），然后对着 AI 说：

> 「用这个技能给我做个 HD2 的 mod，我想要 XXX」

或：

> 「用这个技能把 AR-61 换成这个模型，文件在 D:/models/xx.fbx」

AI 会自己跑 `doctor`、查 archive、建工程、检查模型、打包、过门禁、装库；
只在需要点 Deploy / 重启游戏时找对方。对方**不需要懂 Python、不需要命令行、
不需要知道什么是 patch**。

## 安装为可调用技能

```bash
cp -r . ~/.workbuddy/skills/hd2-gameplay-mod
```

之后在对话里说「做个 HD2 玩法 mod」「把 AR-61 换成这个模型」即可触发。

## 免责

- 与 Arrowhead Game Studios / Sony 无任何关联。
- 覆盖读游戏数据、Lua 玩法脚本、模型/贴图替换、数值表四条线；不覆盖绕过反作弊。
- 修改游戏文件可能违反服务条款；使用风险自负。Arrowhead 从未发布过“安全 mod 名单”。
- 模型/贴图素材的版权由使用者负责；不要分发没有授权的资产。

## 许可

MIT（`tools/` 与本仓库文档）。引用的第三方工具与文档各自遵循其原许可。
