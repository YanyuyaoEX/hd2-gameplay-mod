# 打包规范（`.patch_N` 容器）

> 本文件的容器数值在 build **26251122** 上实测；Blender/SDK 的 UI 流程见
> `references/model-pipeline.md`。换 build 后先用 §7 的复验命令过一遍。

## 1. 一个 mod 的物理形态

```
MyMod/                              ← 可被管理器导入的根
├── manifest.json                   ← 必须在根
├── README.md
├── cover.jpg
└── Core/                           ← 一个 option 文件夹
    ├── 9ba626afa44a3aa3.patch_0    ← Lua / 基础 archive 资源
    ├── 9ba626afa44a3aa3.patch_0.gpu_resources
    └── ee6b1ba7e22d71ed.patch_0    ← 贴图/场景可能 patch 别的 archive
```

- **文件夹名**随意，但必须与 `manifest.Options[].Include` 一致。
- **patch 文件名固定**为 `<archive>.patch_N`。`9ba626afa44a3aa3` 是**基础 archive**，
  不是你的 mod 的 id；模型/贴图/音频可能 patch 其他 archive（例如
  `ee6b1ba7e22d71ed`、`a193a00ce4bbd529`），**保留 SDK 导出的 archive 名**。
- **编号由管理器重排**。你在源文件夹里写的 `patch_0/1/2` 只是本地顺序；部署到游戏目录时，
  管理器按加载顺序 + option 顺序**重新连续编号**。
- `.stream` / `.gpu_resources` 必须与宿主 patch **同目录、同前缀**；不要改名。

## 2. 容器的字节结构（单 lua 资源）

头部固定 72 字节，类型表 32 字节/项，条目表 80 字节/项。

| 偏移 / 字段 | 值 | 说明 |
|---|---|---|
| `0x00 u32 magic` | `0xF0000011` (`4026531857`) | 固定 |
| `0x04 u32` | `1` | 类型数 |
| `0x08 u32` | `1` | 条目数 |
| `0x0C u32` | `0` | 未知，恒 0 |
| `0x10..0x48` | 56 字节 | 未知区 |
| **`0x20 u32`** | **本包总长度** | **自身尺寸字段**，必须等于文件实际字节数 |
| `0x48` 类型表 | `u64 unk1=0, u64 type_id, u64 文件数, u32 16, u32 16` | type_id = `0xA14E8DFA2CD117E2` |
| `0x68` 条目表 | `u64 file_id, u64 type_id, u64 toc_off, u64 stream_off, u64 gpu_off, u64 0, u64 0, u32 toc_size, u32 stream_size, u32 gpu_size, u32 16, u32 16, u32 entry_index=0` | 共 80 字节 |
| `0xC0` (=192) | toc blob 起点 | `align_up(0xB8, 16)` |
| 末尾 | **不补齐** | retail 包就是不补的 |

> **`0x20` 这个自尺寸字段是踩过的坑**：三个真实 Lua 包（85712 / 22128 / 2575152 字节）
> 的该字段都精确等于自己的文件长度【实测】。`srkit pack` 会**保留**源包的这个值，
> 重新打包后尺寸变了它不会更新 —— 所以 Lua 包用 `hd2mod.py build`，别用 `srkit pack`。
>
> **但这个等式只对“单资源 Lua 包”成立**。模型/贴图包的 `0x20` 字段并不可靠：
> Kraber Apex 的 patch 是 9,659,160 字节，字段却是 60,531,968；Clear Visibility 的
> NoFog patch 是 1,296 字节，字段是 1,024【实测】。所以门禁对资源包**不比对自尺寸**，
> 只检查 TOC 偏移/长度是否越界。

Lua 资源 blob 的结构（`srkit/resources/lua.py` 同源结论）：

```
u32 payload_size     源码字节数
u32 unknown          实测恒为 2
payload              UTF-8 Lua 源码（LuaJIT 字节码在本版本编译不过）
[trailing]           可选尾部字节
```

所以单资源包的字节数恒等于：`192 + 8 + 脚本字节数`。
（1421 字节的包 = 192 + 8 + 1221 字节脚本。）

## 2.1 多资源包（模型 / 贴图 / 场景）

模型 mod 的 patch 不是“一个 lua”，而是**多类型、多条目的资源包**。头部结构相同，
但类型表和条目表都是复数：

| 表 | 位置 | 每项大小 | 字段 |
|---|---|---|---|
| 类型表 | `0x48` 起，共 `ntype` 项 | 32 字节 | `u64 unk=0, u64 type_id, u64 条目数, u32 16, u32 16` |
| 条目表 | 类型表之后，共 `nentry` 项 | 80 字节 | `u64 file_id, u64 type_id, u64 toc_off, u64 stream_off, u64 gpu_off, u64 0, u64 0, u32 toc_size, u32 stream_size, u32 gpu_size, u32 16, u32 16, u32 index` |

实测（Kraber Apex 武器 mod，build 26251122）【实测】：

```
文件 9,659,160 字节 · 6 个类型 · 34 个条目
  unit          3
  bones         4
  state_machine 2
  animation    16
  material      2
  texture       7
gpu_resources 51,625,712 字节（51 MB）
```

所以：

- **类型和条目都可能很多**；`ntype=1, nentry=1` 只是 Lua 包的特例。
- 每个类型声明自己的条目数；门禁会核对“类型表声明的数量 == 条目表里该类型的实际数量”。
- 条目里的 `toc_off/toc_size` 必须落在 patch 文件内；`gpu_size` / `stream_size` 指向
  **外部伴生文件**，不在 patch 内。
- 同一个 `file_id` 可以出现在不同类型下（例如同一个 ID 既是 unit 又是 bones），
  唯一性要按 **(type_id, file_id)** 判断，不能只看 file_id。

### 类型 ID 速查

| type_id | 名称 | 说明 |
|---|---|---|
| `0xE0A48D0BE9A7453F` | unit | 模型单位（护甲/武器/道具的入口） |
| `0xC4F0F4BE7FB0C8D6` | composite_unit / geometry_group | SDK 常量叫 CompositeUnitID，类型表里也标 geometry_group；少见 |
| `0xCD4238C6A0C69E32` | texture | 贴图 |
| `0xEAC0B497876ADEDF` | material | 材质 |
| `0x18DEAD01056B72E9` | bones | 骨骼 |
| `0x931E336D7646CC26` | animation | 动画 |
| `0xA486D4045106165C` | state_machine | 状态机 |
| `0x5F7203C8F280DAB8` | physics | 物理 |
| `0xA8193123526FAD64` | particles | 粒子 |
| `0x535A7BD3E650D799` | wwise_bank | 音频 bank |
| `0xAF32095C82F2B070` | wwise_dep | 音频依赖 |
| `0x504B55235D21440E` | wwise_stream | 音频流 |
| `0x0D972BAB10B40FD3` | strings | 文本 |
| `0xA14E8DFA2CD117E2` | lua | Lua 脚本 |
| `0x9831CA893B0D087D` | entity | 实体/场景 |
| `0x46BC82AAE9AE0565` | xaml | UI |

> 这张表来自 HD2SDK 的 `utils/constants.py`（`UnitID / TexID / MaterialID ...`）【文档】；
> 与真实 patch 的解析结果交叉核对过【实测】。

## 3. 资源 ID 规则（最容易错）

```
file_id == murmur64("mods/<作者>/<名字>")
```

- 引擎按**名字**解析资源，名字 → ID 用的就是 murmur64。
- 包里没有名字表，`srkit list` 的 `name` 列为空是正常的：名字只能由 ID 反推。
- ID 不匹配的表现：**包能解析、资源在里面，但加载器找不到你的脚本**（静默，不报错）。

算（两条路，结果一样）：

```bash
# 路线 1：本技能自带（不需要任何依赖）
python -c "import sys;sys.path.insert(0,'tools');from hd2mod import murmur64;print(f'{murmur64(\"mods/aabc/anti_air\"):016X}')"

# 路线 2：有 srkit 时
python -m srkit hash "mods/aabc/anti_air"
# mods/aabc/anti_air   murmur64=0x37FCC0A04812EAB6 murmur32=0x37FCC0A048
```

手工改 ID 时要**同步三处**，漏一处就打回原形：

1. `package.json` → `entries[0].file_id`
2. `resource.json` → `file_id`
3. 资源目录名 → `lua_<16 位大写十六进制>`
4. 另外 `package.json` → `entries[0].resource_dir` 要指向新目录名

> `hd2mod.py build` 一次把四处都写对。手工改只用于排错学习。

## 4. 部署时发生什么

管理器把 `data/` 下的 patch 文件当成一个整体序列：

| 动作 | 说明 |
|---|---|
| 编号 | 按加载顺序重排为 `patch_0..patch_N` |
| 同盘 | **硬链接**（0 字节写入） |
| 异盘 | 复制 |
| 删除 | 只删游戏目录里的，库不动 |

**推论（P0 坑）**：游戏目录里的 patch 与库里是**同一个文件的两个名字**。
直接编辑游戏目录里的 patch = 改库。要改就改库，然后重新 deploy。

## 5. 资源类 mod 的附加文件

| 伴生文件 | 何时出现 | 规则 |
|---|---|---|
| `*.patch_N.stream` | 有流式数据（大块音频/贴图） | 与宿主 patch **同目录、同前缀**，一起走 |
| `*.patch_N.gpu_resources` | 有 GPU 资源（模型/贴图） | 同上 |

判断方法：解析 patch 的条目表，只要有一条 `gpu_size > 0` 就必须有 `.gpu_resources`；
有一条 `stream_size > 0` 就必须有 `.stream`。少一个 → 资源加载失败但**不报错**，
表现为“模型/贴图丢了”“紫问号”或某几个部件消失。

实测：

| mod | patch | `.gpu_resources` | `.stream` |
|---|---|---|---|
| Kraber Apex（武器） | 9,659,160 | 51,625,712 | 0 字节（存在） |
| Clear Visibility / NoFog（材质） | 1,296 | 27,664 | 无 |
| Kraber Audio（音频） | 3,288,368 | 无 | 无（音频在 patch 内） |

> 0 字节的 `.stream` 也可能是**必需的占位**，不要因为它是 0 就删掉。

## 6. 体积与数量上限

| 限制 | 值 | 来源 |
|---|---|---|
| 单脚本 | 4 MB（Chef） | Chef Shared Loader 1.2.1 限制 |
| patch 数量 | ~512（MDL3 dev.36） | 保护性措施，作者称后续放宽 |
| 资源 mod 的 patch 数 | 没有硬限，但越少越好 | 资源 mod 不走 MDL3；管理器部署仍会逐个排队 |
| 总包 | 无硬限，但越大部署越慢 | 实测武器包 51 MB `.gpu_resources` 可正常加载 |

> 资源 mod 在 MDL3 里是 `LAUNCH ONLY`，不参与 MDL3 的 512 读取上限；
> 但一个包里 patch 太多仍会拖慢部署、增加冲突面，能合并就合并。

## 7. 复验命令（换 build 后照抄）

```bash
# 0) 本技能自检（零依赖）
python tools/selftest.py

# 1) 门禁：Lua / 模型工程都走同一个命令
python tools/hd2mod.py check "<工程目录>"

# 2) 看 patch 里到底有什么（类型 / 条目 / 伴生文件）
python tools/hd2mod.py inspect "<某个 patch 或 dist 文件夹>"

# 下面这些需要 srkit（可选）；<游戏> 由 doctor 给出
SRK="${HD2_SRKIT:?先设 HD2_SRKIT 指向 srkit 目录}"
cd "$SRK"

# 3) srkit 自带自检（不是本技能的 selftest）
python tests/selftest.py

# 4) 游戏归档还能不能识别
python -m srkit info "<游戏>/data"

# 5) 你的产物：ID 对不对
python -m srkit list "<你的 patch_0>"

# 6) 你的产物：资源解码/重编码一致吗
python -m srkit check "<你的 patch_0>"
```

判读：

| 输出 | 含义 |
|---|---|
| `门禁通过` | ID、自长度、payload 长度全部自洽（Lua）；或类型/偏移/伴生文件自洽（资源） |
| `1 identical / 0 differing`（`verify`） | 资源层可逆，编码正确 |
| `差异 0 / 失败 0`（`check`） | 整包解码-重编码一致 |
| `no resource directory` | `resource_dir` 指错，或目录名与 ID 不一致 |
| `ID ≠ murmur64(module)` | 名字与身份不匹配，加载器找不到 |
| `头部自记长度 X ≠ 实际 Y` | **仅 Lua 单资源包**是错误；资源包的该字段不可靠，门禁不比对 |

## 8. 常见构建故障

| 现象 | 原因 | 修 |
|---|---|---|
| `pack` 报 `no resource directory` | `resource_dir` 与真实目录名不一致 | 改 `package.json`，或直接 `hd2mod.py build` |
| 产物比原件长/短几十字节 | 16 字节对齐 | 正常，不要用 `cmp` 判断 |
| 进游戏没反应 | ID 与模块路径不匹配 | `srkit list` + `srkit hash` 对比 |
| 加载器报 `name` 是空 / 找不到 | 首行声明与 ID 不一致 | 两者都改成同一个 `mods/x/y` |
| 资源显示紫问号 | 缺 `.stream` / `.gpu_resources` | 补齐伴生文件 |
| 部署后游戏崩 | 游戏运行时部署 / 半个包 | 退出游戏，`purge` 后重新 deploy |
