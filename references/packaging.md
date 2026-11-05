# 打包规范（`.patch_N` 容器）

> 本文件所有数值均在 build **26251122** 上实测。换 build 后先用 §7 的复验命令过一遍。

## 1. 一个 mod 的物理形态

```
MyMod/                              ← 可被管理器导入的根
├── manifest.json                   ← 必须在根
├── README.md
├── cover.jpg
└── Core/                           ← 一个 option 文件夹
    └── 9ba626afa44a3aa3.patch_0    ← 文件名固定
```

- **文件夹名**随意，但必须与 `manifest.Options[].Include` 一致。
- **patch 文件名固定**为 `9ba626afa44a3aa3.patch_N`。`9ba626afa44a3aa3` 是所有 mod 共用的包名，
  不是你的 mod 的 id —— 不要改。
- **编号由管理器重排**。你在源文件夹里写的 `patch_0/1/2` 只是本地顺序；部署到游戏目录时，
  管理器按加载顺序 + option 顺序**重新连续编号**。

## 2. 容器的字节结构（单 lua 资源）

| 字段 | 值 | 说明 |
|---|---|---|
| `magic` | `4026531857` (`0xF0000011`) | 固定 |
| `types[0].type_id` | `11623383793923069922` (`0xA14E8DFA2CD117E2`) | lua 资源类型 |
| `types[0].unk2/unk3` | `16 / 16` | 实测样本值 |
| `entries[0].unknown3/unknown4` | `16 / 16` | 实测样本值 |
| `entries[0].toc_data_offset` | `192` | 1 类型 + 1 条目时的头部长度 |
| 资源 blob 头 | `u32 payload_size` + `u32 unknown(=2)` | 之后才是 Lua 源码 |
| 容器对齐 | 16 字节 | `pack` 会对齐，**所以产物长度通常与原件不同** |

Lua 资源 blob 的结构（`srkit/resources/lua.py` 同源结论）：

```
u32 payload_size     源码字节数
u32 unknown          实测恒为 2
payload              UTF-8 Lua 源码（或 LuaJIT 字节码，本版本禁止）
[trailing]           可选尾部字节
```

## 3. 资源 ID 规则（最容易错）

```
file_id == murmur64("mods/<作者>/<名字>")
```

- 引擎按**名字**解析资源，名字 → ID 用的就是 murmur64。
- 包里没有名字表，`srkit list` 的 `name` 列为空是正常的：名字只能由 ID 反推。
- ID 不匹配的表现：**包能解析、资源在里面，但加载器找不到你的脚本**（静默，不报错）。

算：

```bash
cd "C:/Users/50709/Downloads/modtool/hd2-srkit-master"
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

**推论（P0 红线）**：游戏目录里的 patch 与库里是**同一个文件的两个名字**。
直接编辑游戏目录里的 patch = 改库。要改就改库，然后重新 deploy。

## 5. 资源类 mod 的附加文件

| 伴生文件 | 何时出现 | 规则 |
|---|---|---|
| `*.patch_N.stream` | 有流式数据（贴图/音频大块） | 与宿主 patch **同目录、同前缀**，一起走 |
| `*.patch_N.gpu_resources` | 有 GPU 资源 | 同上 |

少一个 → 资源加载失败但**不报错**，表现为"模型/贴图丢了"或"紫问号"。

## 6. 体积与数量上限

| 限制 | 值 | 来源 |
|---|---|---|
| 单脚本 | 4 MB（Chef） | Chef Shared Loader 1.2.1 限制 |
| patch 数量 | ~512（MDL3 dev.36） | 保护性措施，作者称后续放宽 |
| 总包 | 无硬限，但越大部署越慢 | — |

## 7. 复验命令（换 build 后照抄）

```bash
SRK="C:/Users/50709/Downloads/modtool/hd2-srkit-master"
cd "$SRK"

# 1) 工具自检
python tests/selftest.py

# 2) 游戏归档还能不能识别
python -m srkit info "D:/Steam/steamapps/common/Helldivers 2/data"

# 3) 你的产物：ID 对不对
python -m srkit list "<你的 patch_0>"

# 4) 你的产物：资源解码/重编码一致吗
python -m srkit verify "<你的 ws 或 patch>"

# 5) 整包解码检查
python -m srkit check "<你的 patch_0>"
```

判读：

| 输出 | 含义 |
|---|---|
| `1 identical / 0 differing` | 资源层可逆，编码正确 |
| `差异 0 / 失败 0`（`check`） | 整包解码-重编码一致 |
| `no resource directory` | `resource_dir` 指错，或目录名与 ID 不一致 |
| `ID ≠ murmur64(module)` | 名字与身份不匹配，加载器找不到 |

## 8. 常见构建故障

| 现象 | 原因 | 修 |
|---|---|---|
| `pack` 报 `no resource directory` | `resource_dir` 与真实目录名不一致 | 改 `package.json`，或直接 `hd2mod.py build` |
| 产物比原件长/短几十字节 | 16 字节对齐 | 正常，不要用 `cmp` 判断 |
| 进游戏没反应 | ID 与模块路径不匹配 | `srkit list` + `srkit hash` 对比 |
| 加载器报 `name` 是空 / 找不到 | 首行声明与 ID 不一致 | 两者都改成同一个 `mods/x/y` |
| 资源显示紫问号 | 缺 `.stream` / `.gpu_resources` | 补齐伴生文件 |
| 部署后游戏崩 | 游戏运行时部署 / 半个包 | 退出游戏，`purge` 后重新 deploy |
