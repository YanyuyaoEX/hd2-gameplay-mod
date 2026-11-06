# 武器模型替换流水线

> **证据等级**：`【文档】` HD2 Modding Wiki（Weapon Replacement / LOD Dependant Units /
> Aligning Magazines / Materials / Textures）· `【实测】` 本机 build 26251122 对真实武器 mod
> 的容器解析 · `【推断】` 从社区教程与工具行为逆推，未逐项复验。
> **护甲/头盔**见 `model-pipeline.md`；本文件只讲武器。

---

## 0. 一句话

武器 mod = 替换目标 `weapon unit` 的 `mesh / material / texture`。
它**不要求你自己绑一套全身骨骼**：可以只做外观，也可以按原版顶点组保留枪机/弹匣/配件的动作。

> **实战案例**：SG-225 Breaker → 飓风之龙（OBJ 静态模型，L1），
> 已用 Blender 脚本全自动生成 1 unit / 2 material / 6 texture 的 patch，
> 详见 `references/case-sg225-jfzl.md`。案例里的对齐矩阵、材质模板、包围盒数字可直接参考。

---

## 1. 先定“做到哪一层”（许愿卡第一问）

| 层级 | 做什么 | 工作量 | 效果 | 适合 |
|---|---|---|---|---|
| **L1 外观级** | 整枪绑 `boss`，只换外形 | 低 | 枪能拿、能开火；枪机/弹匣/快慢机**不一定动** | 静态武器、手枪、道具、第一次做 |
| **L2 功能件** | 按原版顶点组绑 `bolt`、`charging_handle` 等 | 中 | 矢量动画（枪机前后、拉机柄）正常；旋转件可能穿帮 | 大多数步枪/冲锋枪 |
| **L3 完整** | 编辑 `attach_*` 骨骼、弹匣、配件、IK/抛壳 | 高 | 瞄具/下挂/弹匣/换弹都对齐 | 有瞄具/下挂/换弹细节的武器 |

**建议**：第一条武器 mod 从 **L1** 开始，跑通“能拿、能开火、能进游戏”；
第二条再做 **L2**；不要一上来追 L3。

---

## 2. 工具链

| 工具 | 作用 | 必需？ |
|---|---|---|
| Blender 4.0–5.2 | 导入/对齐/权重/材质 | ✅ |
| HD2SDK: Community Edition 3.11.x | 读 archive、Save Units、Write/Export Patch | ✅ |
| `hd2mod.py` | 查 archive、收编、打包、门禁、安装 | ✅ |
| `blender_preflight.py` | 模型预检 | ✅ 建议 |
| Avatar Rig | **武器路线不需要**（护甲才要） | ❌ |
| srkit | 深层排错才用 | 可选 |

---

## 3. 许愿卡：只问五件事

| 问什么 | 用来定 | 例子 |
|---|---|---|
| 换哪把？ | 目标 archive / unit | 「AR-61 Tenderizer」「这把 DMR」 |
| 换成什么？ | 模型来源 | 「这个 FBX」「STEP/OBJ」「参考图」 |
| 做到哪一层？ | L1 / L2 / L3 | 「只要外观」「枪机要动」「瞄具也要对」 |
| LOD / 视角？ | Auto LODs、第一人称 | 「第一人称也要看」「只做第三人称」 |
| 怎么算成？ | 验收 | 「右手握持、开火不穿模、枪口火光不歪」 |

**不要问**：archive ID、unit ID、顶点组名、LOD 编号、patch 编号。这些是你的活。

---

## 4. 素材要求

| 项 | L1 外观级 | L2/L3 功能件 |
|---|---|---|
| 骨骼 | **不需要**（整枪绑 `boss`） | 可用原版 unit 的 armature；按原版顶点组绑 |
| UV | 至少 1 层 | 至少 1 层 |
| 材质 | 至少 1 个；建议 `Advanced` | 同左 |
| 贴图 | 正方形、2 的幂、OpenGL 法线 | 同左 |
| 缩放 | `Ctrl+A` 应用；按原版尺寸对齐 | 同左 |
| 形态键 | 删除/应用（SDK 不导出） | 同左 |
| 面数 | 以原版同武器为参照；LOD2+ 减面 | 同左 |
| 朝向 | 枪口朝前、握把朝下；用原版模型做参照 | 同左 |

> 武器模型**不需要 A-Pose**，但要和原版武器的**握把位置、枪口方向、整体尺寸**对齐。
> 尺寸不对的表现是：枪看起来像玩具/巨大、枪托穿进身体、瞄具对不上。

---

## 5. 逐步流程

### 5.1 清场与 Setup

1. **退出游戏**。
2. Blender → SDK `Data Location` 指向游戏 `data` → 星形图标加载基础 archive → **New Patch**。
3. 每次重开 Blender 都要重新做 Setup【文档】。

> **P0**：SDK 的 **Write Patch 直接写游戏 `data/`**，会覆盖已部署的 patch。
> 写之前先备份 `data/*.patch_*`，或先 `purge` 清场；导出后把 SDK 写的那份删掉。

### 5.2 找目标武器 archive

```bash
python tools/hd2mod.py lookup "AR-61"
# Assault Rifle   d1968909ea085527   AR-61 Tenderizer
```

- 也可以在 SDK 的 **Search Found Archives** 里搜英文名/缩写。
- 同一把武器可能有多个变体/皮肤 archive；让用户确认是哪一版。
- 带瞄具/下挂的武器，可能不止一个 unit；先看 archive 里有哪些 unit。

**中文名 → unit 必须先对齐，别按“系列名”猜**：

| 中文名 | 英文名 | archive | unit |
|---|---|---|---|
| SG-225 破裂者 | SG-225 Breaker | `c5a05d09369d0670` | `5050852199397921576` |
| SG-225SP 千发百中「破裂者」 | SG-225SP Breaker Spray & Pray | `c5a05d09369d0670` | `7073132068558755510` |
| SG-225IE 高燃「破裂者」 | SG-225IE Breaker Incendiary | `2fe755e42b659f64` | `13918995818598980231` |

- 基础型和 SP **共用一个 archive，但是两个独立 unit**；只改一个，另一个不会变。
- 中文 wiki（`helldivers.wiki.gg/zh`）搜中文名最可靠，页面里会写英文名与所属系列。
- 用户说「破裂者」时，追问一句是 **基础 / 千发百中(SP) / 高燃(IE)** 哪一个。

### 5.3 导入目标 unit

1. 选中目标 archive → 导入要替换的 `unit`。
2. 导入设置：
   - `Import Materials`：开
   - `Import LODs`：开（除非你明确只改 LOD0）
   - `Import Static Meshes`：纯静态网格才开
   - `Remove Gore Meshes`：武器通常无关，保持默认
3. 先观察：unit 有几个 LOD、材质槽几个、顶点组有哪些。

**LOD0 的 `MeshInfoIndex` 不是固定值**：同一 archive 里基础型 SG-225 是 `8`，
SG-225SP 是 `9`。脚本里按对象名 `*_lod0` 选，兜底取顶点数最多的那个；
写死 `== 8` 会静默改到 LOD1，模型面数和细节都会降一档。

### 5.4 导入你的模型并对齐

1. 导入 FBX/OBJ/GLB。
2. 把**握把**对齐到原版握把；枪口朝前；整体缩放到与原版同长度。
3. **先复制一份模型**（`Shift+D`）再做试装，避免破坏原始模型【文档】。
4. 试装：
   - 删掉原版枪的所有顶点；
   - 把你的模型全部绑到 `boss`；
   - 移除你模型自带的材质；
   - 把你的 mesh `Ctrl+J` 合并到原版 mesh；
   - 右键 **Save Units**（只保存 unit，不保存材质/贴图）；
   - **Write Patch** → 进游戏看：
     - 右手握持是否正确；
     - 枪托是否穿进玩家；
     - 整体尺寸是否像真枪。

> 试装阶段只保存 unit。材质/贴图先别存，否则 patch 会变大且难排查。

### 5.5 替换网格 / 复制属性

有两种方式，二选一：

**A. 合并法**（试装时已经用了）

1. 原版 mesh 删顶点、清材质；
2. 你的 mesh 命名为 `UVMap` 的 UV 层（**必须**叫 `UVMap`，不能是 `Diffuse UV`）；
3. `Ctrl+J` 合并；
4. 得到“你的外形 + 原版 unit 身份/属性”。

**B. 属性复制法**

1. 选原版 unit → `Copy HD2 Properties`；
2. 选你的 mesh → `Paste HD2 Properties`；
3. 原点：原版 `Shift+S > Cursor to Selected`；你的 mesh `Set Origin > Origin to 3D Cursor`。

> 两种方法都要对**每个被替换的 unit** 做一遍。

### 5.6 权重：先看原版有什么组

进入 **Weight Paint** 模式，看原版 unit 的 vertex groups：

| 组名（示例） | 控制什么 |
|---|---|
| `boss` | 整枪根节点；L1 全绑这里 |
| `bolt` | 枪机前后 |
| `charging_handle` | 拉机柄 |
| 其他 | 弹匣释放、快慢机、扳机等，按原版为准 |

**不要凭空发明组名**。原版没有的组，绑了也不会动。

两类动画：

- **矢量型**（前后往复）：枪机、拉机柄。位置对了就能动【文档】。
- **旋转型**（原地转）：快慢机、弹匣卡笋。模型部件位置和原枪不同时，**必须改骨骼/动画**，
  否则会穿帮【文档】。

L1 外观级：整枪绑 `boss`，接受“枪机/弹匣不一定动”。
L2：按原版组把对应部件刷给 `bolt` / `charging_handle` 等。

### 5.7 材质 / 贴图

1. SDK 材质面板 → `+` → 选模板（武器首选 `Advanced`）。
2. 把你的 mesh 材质替换成 SDK 材质（下拉选同一个 ID）。
3. Advanced 节点：
   - Normal/AO/Roughness：R/G 法线、B AO、A Roughness；
   - Metallic：灰度；
   - Color/Emissive Mask：RGB 颜色、A 自发光遮罩。
4. 贴图正方形、2 的幂、OpenGL 法线。
5. 材质槽不要超过原版；多套贴图合并 atlas。

### 5.8 LOD

| 设置 | 什么时候用 |
|---|---|
| `Auto LODs` 开 | 普通武器，所有 LOD 用同一份 mesh |
| `Auto LODs` 关 | **LOD 相关 unit**（如 P-4 Senator、AC-8 背包） |

- LOD0 通常用于**第一人称**，LOD1 用于**第三人称**；LOD2+ 逐级减面【文档】。
- 某些 unit 的子弹/弹夹只在 LOD9–10 出现；只改 LOD0 会“子弹消失”。
- 手动改 LOD：复制 LOD0 → 粘贴目标 LOD 的 `BoneIndexInfo / MeshIndexInfo` 自定义属性；
  每个 LOD 的原点可能不同，逐个核对。
- 高模不要无脑铺满所有 LOD；LOD2 之后用 Decimate 减面，否则帧数会掉【推断】。

### 5.9 骨骼与配件（L1 也必须处理挂点）

**整枪替换时，枪口/瞄具/下挂/弹匣都是独立 unit**，按原版 `attach_*` 挂点生成。
新枪的长度/高度和原版不一样，就会出现：

| 症状 | 原因 | 修法 |
|---|---|---|
| 枪口配件「全露」、浮在枪管前 | `attach_muzzle` 在新枪口之外 | 把骨骼往里移到枪口端面或护木内部 |
| 瞄具「半露」、陷进枪身 | `attach_optic` 低于新枪顶面 | 抬到新枪最高点（+1~2 mm 余量） |
| 弹鼓/弹匣「半露」、穿进枪身 | `attach_mag` 落在新枪体内部 | 移到弹匣井底部；整枪替换建议直接藏 |
| 下挂/前握把悬空 | `attach_underbarrel` 不在护木下沿 | 对准护木底面，或藏进护木 |

**两种策略**：

- **A. 全部隐藏**（整枪替换最稳）：把 `attach_muzzle` / `attach_underbarrel` /
  `attach_optic` / `attach_mag` 的 **head + tail 一起平移**到新模型最厚的部位。
  配件属性照常生效，只是模型看不见。本案例统一放到弹鼓段中心 `(0, 0.20, 0.05)`。
- **B. 保留可见**：`attach_muzzle` 放到新枪口端面，`attach_optic` 放到顶面最高点，
  `attach_mag` 放到弹匣井底。适合新枪结构和原版接近的情况。

**平移要点**：

- 只改 `head` 不改 `tail` 会改变骨骼朝向，配件会歪；两个一起加同一个 delta。
- 改完必须保存 unit，再**重新导入 patch** 读一次骨骼坐标确认。
- `sight` 是瞄准参考，不要跟着藏；只动 `attach_optic`。

**体积大的配件不要靠挂点藏**：弹鼓 / 加长弹匣这类 20–30 cm 的件，塞不进枪身，
挪挂点只会让它从枪身下方穿出来。做法是把**配件 unit 本身收掉**：

```text
导入该 unit → 选 LOD0（`*_lod0`）→ 删掉其它 LOD 对象
→ Edit Mode 全选 → Merge at Center（1 顶点、0 面）→ Save Units
```

- 弹匣类 unit 通常在**武器自己的 archive** 里，名字形如 `ltshotgun_drum_magazine`、
  `n_box_magazine_extended`，所以只影响同一 archive 的武器（SG-225 / SG-225SP）。
- 一个 patch 可以带多个 unit：本案例 `unit 3 / bones 3 / state_machine 3 / animation 4`。
- 收起后配件属性照常生效，换弹动画照播，只是弹匣模型不可见。

导入 unit 的 armature，在 **Edit Mode** 里移动这些骨骼，让它们对准你的模型：

| 骨骼 | 作用 |
|---|---|
| `attach_muzzle` | 子弹生成点、枪口配件挂载 |
| `attach_underbarrel` | 下挂配件 |
| `attach_optic` / `sight` | 瞄具挂载 + 军械库渲染画面 |
| `ejector` / `numbers` | 弹壳抛出位置/方向 |
| `IK_left` | 左手位置（决定换弹/持枪姿态） |
| `attach_mag` | 弹匣挂载点 |

**保存前检查**：你的 mesh 必须有 **Armature Modifier**，且指向你编辑过的 armature【文档】。

**技巧**：

- 抛壳方向不对：改 `ejector` 骨骼朝向；把骨骼长度设 0.1 以上便于观察，调完恢复。
- `IK_left` 不能移到玩家物理上够不到的位置；用 `Display As > B-Bones` 观察，
  骨骼延伸方向 = 小指方向；`Roll` 决定手腕全局旋转。
- 瞄具浮空/对不上：先检查 `attach_optic`/`sight`，再看瞄具是不是独立 unit。

### 5.10 弹匣

武器和弹匣可能是**两个独立 rig**：

1. 给弹匣骨架加 **Child Of** 约束，Target 选武器骨架，Bone 选 `attach_mag`。
2. 角度不对：`R` → `X` → 输入 `90`（或 `-90`）。
3. 游戏内位置不对：回 Blender，**Edit Mode** 里移动弹匣；
   从 patch 里移除旧弹匣 unit，重新 Save Units → Write Patch。
4. 重复直到换弹动画不穿模。

### 5.11 保存与导出

1. 选中所有要保存的 mesh → **Save Units**。
2. 首次保存设置：
   - `Force 3 UV Sets`：**开**
   - `Save Textures with Material`：开
   - `Generate Random Texture IDs`：开
   - `Patch Base Archive Only`：开
   - `Auto LODs`：普通武器开；LOD 相关 unit 关
3. **Write Patch** → 进游戏测试；满意后 **Export Patch** 导出 zip。

### 5.12 收编打包

```bash
python tools/hd2mod.py new --kind model \
  --title "AR-61 换成 XX" --subject "AR-61 Tenderizer" \
  --target-kind weapon --out "<库>/_src/ar61_xx"

python tools/hd2mod.py adopt "<工程>" --from "<SDK导出的zip>"
python tools/hd2mod.py build "<工程>" --zip
python tools/hd2mod.py check "<工程>"
python tools/hd2mod.py install "<工程>"
```

多 option（不同皮肤/不同瞄具）用 `adopt --option <Include>`。

### 5.13 已有武器 mod 换目标（进阶）

如果你已经有一个武器 mod，只想让它替换另一把枪：

1. SDK 的 **Manually Load Patch** 加载旧 patch（或导入旧 mod 的 unit/mesh）。
2. 导入新目标武器的 unit。
3. 把旧 mesh 对齐到新目标的握把/枪口；按 §5.5–§5.11 复制属性、权重、材质、LOD。
4. Save Units 到新 target → Write/Export Patch。

注意：旧 mod 的 unit 数据可能随游戏更新过期；先用 Retagger 的 **Update Old Mod**
或按新 build 重做，不要直接硬套旧 patch。

---

## 6. 实机验收

- [ ] 右手握持正确，枪不浮空/不歪
- [ ] 枪托、枪管不穿模
- [ ] 第一人称（LOD0）和第三人称（LOD1）都正常
- [ ] 开火/换弹动作不扭曲；枪机/拉机柄按预期动（L2+）
- [ ] 枪口火光/弹道起点不歪
- [ ] 瞄具/下挂/弹匣位置正确（L3）
- [ ] 远距离 LOD 不消失、不闪烁
- [ ] 军械库图标/展示画面正常
- [ ] 卸载后恢复原版

---

## 7. 排错

| 症状 | 最可能原因 | 怎么查 | 怎么修 |
|---|---|---|---|
| 枪完全没变化 | patch 没部署 / archive 错 | 管理器看部署；`inspect` | 重新部署；确认 archive |
| 枪透明/看不见 | `Force 3 UV Sets` 关；材质没保存；只改 LOD0 | 看 SDK 设置/patch 资源 | 开 UV Sets；Save Materials；补 LOD |
| 枪浮空/握持歪 | 握把没对齐；原点错；缩放没应用 | 对比原版 grip/origin | 重新对齐；应用缩放；复制原点 |
| 枪巨大/像玩具 | 没按原版长度缩放 | 对比原版包围盒 | 重新缩放 |
| 枪托穿进身体 | 枪身太长/握把位置不对 | 第三人称开火 | 缩短枪托/后移握把 |
| 枪口火光/弹道歪 | `attach_muzzle` 没对齐；枪管长度不同 | 看枪口骨骼 | 移动 `attach_muzzle` 或改模型长度 |
| 瞄具浮空/对不上 | `attach_optic`/`sight` 没对齐；瞄具独立 unit | 看骨骼/unit | 移动骨骼；处理独立瞄具 |
| 弹匣穿模/换弹错位 | `attach_mag` 不对；弹匣没挂到武器 rig | Child Of / Edit Mode | 挂 `attach_mag`；移动弹匣；重存 |
| 枪机/拉机柄不动 | 整枪绑了 `boss`；没绑原版组 | 看 vertex groups | 按原版组绑 `bolt`/`charging_handle` |
| 快慢机穿帮 | 旋转型动画位置不同 | 看原版位置 | 改骨骼/动画，或接受穿帮 |
| 只有部分 LOD 消失 | LOD 相关 unit 没逐层改 | 看 LOD 页 | 关 Auto LODs，逐层补 |
| 黑紫/亮块 | 贴图尺寸/法线/材质节点 | 检查贴图 | 正方形/POT/OpenGL/重接 |
| 启动崩 | 材质槽超原版；patch 冲突；旧 unit 数据 | 只启用本 mod | 减材质；purge；Retagger |
| 第一人称手臂穿模 | LOD0/手臂模型/枪身位置 | 进游戏第一人称 | 调整枪身/握把；检查 LOD0 |
| 更新游戏后失效 | unit 数据/裁剪信息变了 | 对比 build | Retagger 更新或重做 |

---

## 8. 性能与发布

- **面数**：以原版同武器为参照；LOD2+ 减面。高模铺满所有 LOD 会掉帧【推断】。
- **贴图**：武器常用 1K–2K；4K 只在必要部位。真实武器 mod 的 `.gpu_resources`
  常见 **40–52 MB**（见 §9），不是异常。
- **patch 数**：一个武器 mod 通常 1 个基础 archive patch + 可能的动画/音频 patch；
  不必为了“干净”强行合并。
- **版权**：只用有授权的模型/贴图；`THIRD_PARTY.md` 写清楚。
- **发布**：manifest + patch + 伴生文件；资源 mod 在 MDL3 里是 `LAUNCH ONLY`，装完必须重启。

---

## 9. 真实武器 mod 的容器长什么样【实测】

| mod | patch | 类型 / 条目 | `.gpu_resources` |
|---|---|---|---|
| Kraber Apex（带音频） | 9,659,160 | unit 3 · bones 4 · state_machine 2 · animation 16 · material 2 · texture 7 | 51,625,712 |
| BR-14 → QBZ191 | 3,382,427 | unit 2 · bones 1 · state_machine 1 · animation 10 · material 2 · texture 6 | 40,949,198 |

结论：

- 武器 mod **不是只有一个 mesh**；通常会带 unit / material / texture，
  有动作的还会带 animation / state_machine。
- `check` 只要看到至少 1 个 unit 就算模型包；没有 animation 也可能是合法的静态武器。
- `.gpu_resources` 比 patch 大很多是正常的；不要因为“patch 只有 3 MB”就以为没打进去。

---

## 10. 证据来源

- HD2 Modding Wiki：Weapon Replacement / LOD Dependant Units / Aligning Magazines /
  Materials / Textures / Armor Anatomy（对照用）
- 本机真实武器 mod 容器解析（build 26251122）：Kraber Apex、BR-14 QBZ191
- HD2SDK: Community Edition v3.11.1 README / release
