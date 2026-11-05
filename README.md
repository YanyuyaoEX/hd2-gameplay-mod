# hd2-gameplay-mod

《绝地潜兵2》(Helldivers 2) **玩法类 mod** 开发技能 —— 给 AI 用的可执行作业手册，不是教程散文。

面向 2026-10-20 之后的真实环境：**EAC 已替换 GameGuard**、**LuaJIT 已换成 PUC Lua 5.1**、
MDL3 3.0.0 预览与 HD2 Data Hub 0.3.0 上线。

## 它解决什么问题

网上绝大多数 HD2 mod 教程停在 10 月 20 日之前，照做必失败：

- 说"要关 EAC"——那时根本没有 EAC，用的是 GameGuard。
- 说"Lua mod 被 EAC 封了"——不是。是 LuaJIT 被移除，脚本层的 `ffi` 没了。
- 说"装个加载器就能救回老 mod"——只说对一半。MDL3 **自带 FFI**（经签名 native 桥在宿主侧读），
  所以"读"的能力回来了；但 API 重建过，老 mod 必须按 HD2 Data Hub 的字段重写，不能直接丢进去跑。
  至于"写"，预览版是**纯读取**，没有正规途径。

本技能把这些更正写进流程，并把「一定失败的做法」列成可自检的红线清单。

## 内容

| 文件 | 作用 |
|---|---|
| `SKILL.md` | 主文档：适用范围、现状更正、三条路线路由、**红线清单**、8 步流程、API/工具约束、误区、排错、归档规范 |
| `references/platform-status.md` | 会过期的事实（EAC 时间线、加载器矩阵、MDL3 边界），含重新核实触发条件 |
| `references/lua-contract.md` | 脚本生命周期契约、`context`、全局对象、引擎 API、三条纪律、最小样例 |
| `references/packaging.md` | `.patch_N` 容器结构、资源 ID 规则、部署语义、复验命令、构建故障 |
| `tools/hd2mod.py` | 脚手架 / 打包 / 静态门禁 / Lua 5.1 检查 |

## 快速开始

```bash
SKILL="<本仓库路径>"

# 1) 建工程
python "$SKILL/tools/hd2mod.py" new \
  --author yourname --name mymod --title "我的玩法 MOD" \
  --out "D:/HD2 Mods/_src/mymod"

# 2) 写 src/main.lua（只改这个文件）

# 3) 打包
python "$SKILL/tools/hd2mod.py" build "D:/HD2 Mods/_src/mymod" --zip

# 4) 过门禁（全绿才能部署）
python "$SKILL/tools/hd2mod.py" check "D:/HD2 Mods/_src/mymod"

# 5) 用 hd2-mod-cli 导入 dist/ 下产物 → Deploy → 进游戏验
```

`hd2mod.py` 会自动把资源 ID 设成 `murmur64("mods/<作者>/<名字>")` —— 这是最容易错、
错了又不报错的一步。

## 依赖

- Windows，Python 3.11+（只用标准库）
- [srkit](https://github.com/)（解包/打包 Stingray 资源）—— 默认从
  `C:/Users/50709/Downloads/modtool/hd2-srkit-master` 找，可用 `HD2_SRKIT` 覆盖
- hd2-mod-cli（`hd2qd` / HD2 Mod Quick Deploy）作为部署侧

## 安装为可调用技能

```bash
cp -r . ~/.workbuddy/skills/hd2-gameplay-mod
```

之后在对话里说「做个 HD2 玩法 mod」「HD2 脚本 mod 怎么打包」即可触发。

## 免责

- 与 Arrowhead Game Studios / Sony 无任何关联。
- 只覆盖**不读写内存、不绕反作弊、不影响他人体验**的玩法增强。
- 修改游戏文件可能违反服务条款；使用风险自负。Arrowhead 从未发布过"安全 mod 名单"。

## 许可

MIT（`tools/` 与本仓库文档）。引用的第三方工具与文档各自遵循其原许可。
