# 模型类 mod 流水线（护甲 / 头盔 / 武器 / 道具 / 贴图）

> **证据等级**：`【文档】` HD2 Modding Wiki / HD2SDK 仓库与 release（2026-11 抓取）·
> `【实测】` 本机 build 26251122 上对真实模型/贴图 mod 的容器逐字节解析 ·
> `【推断】` 从社区教程与工具行为逆推，尚未逐项复验。
> **本文件不重复 Lua 路线的内容**；模型 mod 不需要 MDL3，也不写 Lua。

---

## 0. 一句话

模型 mod = 在 Blender 里用 **HD2SDK** 打开目标 archive，把目标 `unit` 的
`mesh / material / texture` 换成你的内容，**Save Units → Write Patch → Export Patch**，
再把导出的 `*.patch_N`（连同 `.stream` / `.gpu_resources`）按 `manifest.json` 打包。

它改的是**资源**，不是脚本：

- 不需要 MDL3、不需要 Data Hub、不需要 Lua。
- 在 MDL3 里会显示 `LAUNCH ONLY`，**不能游戏内热开关**；必须用管理器部署 + 重启游戏。
- 客户端外观改动，风险仍由用户判断；Arrowhead 从未发布“安全 mod 名单”。

---

## 1. 先判可行性：哪些“许愿”能接

| 用户想要 | 能做吗 | 路线 | 关键前提 |
|---|---|---|---|
| 把某套甲换成二次元角色 / 自定义模型 | ✅ | 护甲替换（§5） | 模型**已绑定骨骼**、A-Pose、能对上 HD2 骨架 |
| 只换头盔 | ✅ | 头盔替换（§5.11） | 头盔与护甲在**不同 archive**，要分别加载 |
| 把 A 甲的外观搬到 B 甲上 | ✅ | 护甲互换（§6） | 用 Avatar Rig；可重复打补丁 |
| 换武器外观（枪模） | ✅ | `weapon-pipeline.md` | 注意 LOD、握把对齐、枪机/拉机柄顶点组、`attach_*` 骨骼 |
| 换背包 / 披风 / 道具 / 静态摆件 | ✅ | 静态网格（§7.4） | 静态网格无 LOD、材质槽更自由 |
| 只换贴图 / 改颜色 | ✅ | 贴图路线（§8） | 正方形、2 的幂、OpenGL 法线 |
| 改敌人 / NPC 模型 | ⚠️ | 同骨架替换 | 需要对应骨架与动画；失败率高，先做小范围 |
| 换动画 | ⚠️ | 动画替换 | 本技能只给边界，不展开 |
| 让队友也看到 | ❌ | — | 本地资源 mod 做不到 |
| 改数值 / 改判定 | ❌ | 走数值表 | 不是模型路线 |

**做不到就直说**，并给“最接近的可行版本”：
例如用户给的是**没有骨骼的静态模型**，护甲路线做不了；可以退成
“先只换头盔/背包/武器”或“先做贴图”，不要承诺“自动绑骨”。

---

## 2. 工具链

| 工具 | 版本 / 获取 | 必需？ | 用途 |
|---|---|---|---|
| **Blender** | 4.0–5.2（见下方注意） | ✅ | 打开 archive、导入模型、权重、材质 |
| **HD2SDK: Community Edition** | v3.11.1（2026-10-28） | ✅ | Blender 插件：读 archive、Save Units、Write/Export Patch |
| **texconv** | SDK 自带 `deps/` | ✅（随 SDK） | PNG/TGA → DDS |
| **HD2SDK-AQ-Edition** | 中文改版，v2.5.6（2026-10-15） | 可选 | 额外材质模板、PNG/TGA 自动转 DDS、Patch 重命名/ZIP 导出 |
| **MMD2HD2 Studio** | Blender 4.0 插件 | 可选 | MMD 模型快速转 HD2 护甲；省时间，但权重/比例仍需检查 |
| **HD2 Retagger** | 独立工具 | 可选 | 把已有护甲 mod 改到另一套甲；修复旧 mod 的 Unit 数据 |
| **本技能 `hd2mod.py`** | 随技能 | ✅ | 查 archive、收编 SDK 导出、打包、门禁、安装 |

### Blender 版本注意【文档】

- 当前 README 写支持 **Blender 4.0 to 5.2**。
- 4.1 时代曾有 API 变更导致插件失效的历史问题；装完先验证 `N` 面板。
- 不出现就换 Blender 4.0 复现，不要一上来就怀疑游戏。

> 同一个 Blender 会话**只能启用一个 SDK**（CE 与 AQ 不要同时开）。

### SDK 安装（最短路径）

1. 下载 `HD2SDK-CommunityEditionV3-11-1.zip`。
2. Blender → `Edit > Preferences > Add-ons > Install...` → 选 zip → 勾选启用。
3. 3D 视图按 `N` → **Modding** → **Settings** → `Data Location` 指向
   `<Steam>/steamapps/common/Helldivers 2/data`。
4. 点星形图标加载基础 archive `9ba626afa44a3aa3`。
5. 点 **New Patch**。每次重开 Blender 都要重新做 4–5。

> SDK 3.11.1 改为在 `data` 里找 `settings.ini` 判断游戏路径【文档】；
> 非 Steam 安装也能用。

---

## 3. 许愿卡：只问四件事

| 问什么 | 用来定 | 例子 |
|---|---|---|
| 换哪件？ | 目标 archive / unit | 「B-01 战术甲」「AR-61 步枪」「这个头盔」 |
| 换成什么？ | 模型来源与可行性 | 「这个 FBX」「参考图」「把现有 mod 改到另一套甲」 |
| 什么体型 / 视角？ | 护甲体型、第一人称 | 「Brawny」「第三人称为主，但第一人称也要对」 |
| 怎么算成？ | 验收标准 | 「装备界面能看到、跑动不穿模、队友看不出异常」 |

**不要问**：archive ID、unit ID、材质槽、LOD、patch 编号。这些是你的活。

先把答案写进 `PLAN.md` 的立项卡，再开工。**说不清“进游戏看到什么变化”就停**。

---

## 4. 素材预检（在动游戏之前）

### 4.1 硬性要求

| 项 | 护甲 / 头盔 | 武器 / 静态道具 |
|---|---|---|
| 骨骼 | **必须已绑定**，能对上 HD2 Avatar 骨架 | 可无骨骼（静态网格） |
| 姿势 | **A-Pose**，与导入的 HD2 模型大致对齐 | 握把/枪身对齐 |
| UV | 至少 1 层，合并法要求命名 **`UVMap`** | 至少 1 层 |
| 权重 | 有 vertex groups，接缝权重 1.0 | 静态可全绑 `boss`；有动画的按部件绑 |
| 材质 | 数量不超过目标 unit 的材质槽 | 静态网格限制较少 |
| 贴图 | 正方形、2 的幂（512/1024/2048/4096） | 同上 |
| 变换 | `Ctrl+A` 应用缩放/旋转 | 同上 |
| 形态键 | 删除或应用（SDK 不导出） | 同上 |

### 4.2 预检脚本

```bash
blender -b --python tools/blender_preflight.py -- "C:/path/model.fbx" --json "C:/path/preflight.json"
```

只读检查，不改模型。输出：

- mesh 数 / 顶点 / 三角面 / 材质数 / UV 层 / 顶点组 / 形态键
- 骨架与核心 HD2 骨骼命中率
- 贴图尺寸是否正方形、是否 2 的幂
- 未应用的缩放、缺 UV、无权重、面数偏高等警告

**判据**：`[FAIL]` 必须先解决；`[WARN]` 可以带病开工，但要知道后果。

### 4.3 模型来源与版权

- 只用**用户自己有权使用**的模型；不要从游戏里 rip 别人的资产再分发。
- 二次元/MMD 模型通常有作者许可限制；发布前看原作者的 redistribution 条款。
- Nexus 的 mod 权限各不相同；移植别人的模型前先问作者。
- 本技能只做工具链，不提供受版权保护的模型资源。

---

## 5. 护甲替换（最常用）

> 目标：把一套甲（或其中若干 body part）的外观换成你的模型。
> 下面按钮名来自 HD2 Modding Wiki 的 Armor Replacement 页【文档】。

### 5.1 清场

1. **退出游戏**（部署/写 patch 时文件被占用会半途失败）。
2. 记下当前 build 号；如果是“已经装了一堆 mod”的环境，先用管理器建一个**只含本 mod 的干净配置**。
3. 打开 Blender → SDK `Data Location` 指向游戏 `data` → 星形图标 → **New Patch**。

> **P0**：SDK 的 **Write Patch 直接写游戏 `data/`**，可能覆盖已部署的 patch。
> 写之前先备份 `data/*.patch_*`，或先 `purge` 清场；写完导出后把 SDK 写的那份删掉。

### 5.2 找目标 archive

- SDK 的 **Search Found Archives** 直接搜装备名。
- 或者先在本技能里查：

```bash
python tools/hd2mod.py lookup "B-01"
# Armor   58e4bd4b2278d15c   B-01 Tactical (Variation 1)
# Armor   562a45e9bc984eb9   B-01 Tactical (Variation 2)
# Helmet  fd109bfeeed36726   B-01 Tactical (Variation 1)
```

- **同一套甲可能有多个 Variation / archive**；让用户确认是哪一版，或在 SDK 里逐一看外观。
- **头盔和护甲在不同 archive**，两件都要换就两个都加载。
- 有些护甲有多个 archive/变体；以 SDK 搜索结果为准。

### 5.3 导入目标 unit

1. 选中目标 archive → 把所有 `units` 导入 Blender。
2. 导入设置建议：
   - `Import Materials`：**开**
   - `Import LODs`：开（除非你明确只改 LOD0）
   - `Remove Gore Meshes`：**新手保持开**（改 mesh 会破坏原版 gibs）
   - `Import Static Meshes`：只有静态部件时才开
   - `Make Collections`：开，方便按部件管理
3. 导入后先别动，观察每个 unit 的材质槽数量、UV 层、顶点组。

### 5.4 导入你的模型并对齐

1. 导入 FBX/OBJ/GLB（MMD 先转 FBX，或用 MMD2HD2）。
2. 摆成 **HD2 A-Pose**，与目标甲大致重合；先做**整体缩放**，再做局部。
3. 复制一份模型再开始切割（`Shift+D`），保留原始未切版本。

### 5.5 切分：按权重切，不按视觉切

**至少 6 个主要部件**：

```
Left Arm / Right Arm / Torso / Waist / Left Leg / Right Leg
```

其余按套装有无：肩甲、胸挂、腰挂、大腿挂件、连接件（脖子/下背）。

- 切割位置选在**某根骨权重为 1.0 的地方**，例如大腿骨与腰部共享处。
- 切割后接缝有亮边：用 `Mesh > Split by Selection` 再分离；
  或加 **Data Transfer** 修改器（Source 选原 mesh → Face Corner Data → Custom Normals → Apply）。

### 5.6 权重

| 规则 | 说明 |
|---|---|
| 上臂不要绑 `l_shoulder / r_shoulder` | 绑 **`l_shoulder_twist / r_shoulder_twist`**（wiki 旧称 shoulder roll） |
| 接缝处共享骨权重 = **1.0** | 边缘只能绑单一骨骼，否则动作时裂开 |
| 软体（布/皮肤）渐变权重 | 自然弯曲 |
| 硬体（金属/背包）单骨 1.0 | 不跟随布料拉伸 |
| 手指命名 | `thumb/index/middle/ring/pinky` + `1/2/3` 节 |
| 脖子骨 | 技术上存在，游戏基本不用 |

权重来源：Blender 的 `Transfer Weights`、Robust Weight Transfer 插件，
或把模型自带骨架的顶点组重命名/混合到 HD2 骨架。

### 5.7 材质与贴图

1. SDK 材质面板 → `+` → 选模板（见 §8.1）。
2. 把你的 mesh 材质替换成 SDK 生成的材质（下拉选同一个 ID）。
3. 按模板要求接贴图；Advanced 的三个节点别接错（§8.2）。
4. **材质数量不要超过目标 unit**；超过在旧权重/旧 SDK 下会启动即崩【文档】。

### 5.8 复制属性与原点（决定“能不能生效”）

**方法 A：Copy/Paste HD2 Properties**

1. 选原版部件 → 右键 **Copy HD2 Properties**
2. 选你的部件 → 右键 **Paste HD2 Properties**
3. 复制原点：选原版 → `Shift+S > Cursor to Select`；选你的 → 右键
   `Set Origin > Origin to 3D Cursor`

**方法 B：合并法**

1. 选原版部件 → 编辑模式 → 删除全部顶点 → 移除所有材质
2. 选你的部件 → 再 `Ctrl` 选原版 → `Ctrl+J`
3. **合并前必须把你的 UV 层命名为 `UVMap`**（`Diffuse UV` 之类会出问题）

### 5.9 隐藏不需要的原版部件

套装里不替换的部件会叠在你的模型上。把它变不可见：

1. 选原版部件 → 编辑模式 → `A` 全选 → `M > Merge at Center`
2. 至少留 **1 个顶点**（SDK 不能保存 0 顶点 unit；游戏不渲染 <3 顶点的面）

### 5.10 保存与写 patch

1. `A` 全选所有要保存的部件（包括被隐藏的）。
2. 右键 **Save Units**。
3. 首次保存按目标选设置（§9.1）。
4. **Write Patch** → 进游戏测试；或 **Export Patch** 导出 zip 给本技能打包。

> 测试阶段可以只 Save Units + Write Patch；要发布时用 **Export Patch**，
> 避免把测试 patch 留在游戏 `data/` 里。

### 5.11 头盔

- 头盔是**单独 archive**，流程与护甲相同。
- 头盔常带脖子/下背骨骼；权重只涂 `head` 通常就够（按实际 unit 的顶点组为准）。
- 可以把头盔和护甲写进**同一个 patch**：保存时开自动重命名，或分别保存后一起导出。
- 头盔在 UI 里加载失败：检查材质模板是否用了 `Advanced`，以及材质槽数量。

### 5.12 微接缝

权重正确但接缝有 1 像素亮孔：

1. 选接缝 edge loop → `E` 挤出 → 缩进另一个部件内部 → 缩小藏起来。
2. 挤出会打乱法线 → 用 **Data Transfer** 修 Custom Normals。
3. 再 Save Units 测试。

### 5.13 护甲验收清单

- [ ] 装备界面能看到新外观（不是原版 / 不是透明）
- [ ] 第三人称跑动、蹲、爬、表情动作不扭曲
- [ ] 第一人称手臂/武器不穿模
- [ ] 披风、背包、肩甲不穿插
- [ ] 目标体型（Brawny/Lean）正确
- [ ] 关掉 mod 后能恢复原版（管理器 purge/redeploy）

---

## 6. 护甲互换（A 甲外观 → B 甲）

> 适合“我已经有一套做好的甲，想让它替换另一套”。比从零做省事。
> 该方法可重复打补丁（repatched），优于旧 ID Swapping【文档】。

1. 加载 **Super Destroyer Interior 2** archive，导入 **Avatar Rig**，
   unit ID **`5556372446766824087`**。
2. 删除 Rig 上附带的灯光和 mesh，只留 armature。
3. 导入 Armor A（源外观）和 Armor B（目标）的 mesh。
4. 选 Armor B 的 mesh → Modifier → 把 **Armature** 的 Object 改成 Avatar Rig。
5. 选 A 和 B → `Ctrl+J` 合并 → 材质面板按 B 的材质 `Select` → 删除 B 的 mesh。
   结果：只剩 A 的 mesh，但带 B 的属性与原点。
6. 加 **Weighted Normal** 修改器 → 调参数 → Apply（修 SDK 导入的“黏土感”）。
7. 选 A → **以 B 的 ID Save Units**。
8. 如果用的是 HD2 原版材质，**还要把 A 的材质一起保存**，否则游戏里完全不显示。
9. Write/Export Patch → 测试；对其余部件重复。

**注意**：

- 不要用旧 **ID Swapping**（`Z_SwapID`），已被 Avatar Method 取代【文档】。
- 移植会继承目标甲的 Primary LUT；颜色不对要单独改 LUT。
- HD2 Retagger 可以自动做“换目标甲”，但复杂 mod 仍可能失败；先备份。

---

## 7. 武器 / 静态道具

> **武器替换的完整流程**（L1/L2/L3、握把对齐、`bolt`/`charging_handle`、LOD、
> `attach_muzzle` / `attach_optic` / `attach_mag`、弹匣、排错）见
> `references/weapon-pipeline.md`。这里只保留速查。

### 7.1 武器替换

1. 加载目标武器 archive → 导入要替换的 unit。
2. 导入你的枪模 → 对齐**握把**（先复制一份再试装）。
3. 只 Save Units 做一次“试装”：确认右手持握、枪托不穿模、尺寸合理。
4. 删掉原版枪的顶点（或按 §5.8 合并法保留属性/原点）。
5. 权重：
   - 整枪可先全绑 `boss`；
   - 枪机/拉机柄/弹匣等按原版 vertex groups 绑；
   - 旋转类动画（快慢机、弹匣卡笋）需要改骨骼/动画，位置不对会穿帮。
6. 材质：按 §8 做；武器常用 `Advanced` 或 `Basic+`。
7. LOD：见 §7.2。
8. Write Patch → 试装 → 微调 → 再补材质/贴图。

### 7.2 LOD（决定“远看会不会消失/掉帧”）

| 设置 | 什么时候用 |
|---|---|
| `Auto LODs` 开 | 普通武器，所有 LOD 用同一份 mesh |
| `Auto LODs` 关 | **LOD 相关 unit**（如 P-4 Senator、AC-8 背包），必须逐 LOD 改 |

- LOD0 通常用于**第一人称**，LOD1 用于**第三人称**；LOD2+ 逐级减面。
- 某些 unit 的子弹/弹夹只在 LOD9–10 出现；只改 LOD0 会“子弹消失”。
- 手动改 LOD：复制 LOD0 → 粘贴目标 LOD 的 `BoneIndexInfo / MeshIndexInfo` 自定义属性；
  每个 LOD 的原点可能不同，逐个核对。
- 高模不要无脑铺满所有 LOD；LOD2 之后用 Decimate 减面，否则帧数会掉【推断】。

### 7.3 静态网格

- 背包、披风、道具、场景摆件：导入时开 `Import Static Meshes`。
- 静态网格没有 LOD、材质槽限制更少，全部绑 `root` 或对应骨骼即可。
- 仍然是“替换某个 unit 的资源”，只是没有骨骼动画。

### 7.4 武器验收

- [ ] 第一人称持握、开火、换弹动作正常
- [ ] 第三人称背面/侧面不穿模
- [ ] 枪口位置合理（火光/弹道不歪）
- [ ] 远距离 LOD 不消失、不闪烁
- [ ] 机瞄/瞄准镜视野不被遮挡

---

## 8. 材质与贴图

### 8.1 材质模板（preset）怎么选

| 模板 | 优点 | 缺点 | 适合 |
|---|---|---|---|
| **Advanced** | 金属、最强自发光、选择界面可见、不闪 | 无环境叠加、无透明、贴图复杂 | **护甲/武器首选** |
| **Basic** | 金属、环境叠加 | 选择界面不可见、无自发光 | 场景/道具 |
| **Basic+** | 金属、选择界面可见 | 无自发光、武器上可能闪 | 武器备选 |
| **Translucent** | 支持 alpha（头发/贴花） | 无自发光、选择界面不可见 | 头发、薄纱 |
| **Alpha Clip / Alpha Clip+** | 透明/多色自发光 | 选择界面不可见、无环境叠加 | 硬边透明 |
| **Original** | 选择界面可见 | 无金属、自发光弱 | 兼容旧 mod |
| **Emissive** | 自发光强 | 无金属、选择界面不可见 | 发光件 |
| **LUT** | 原版材质系统、能力强 | 门槛高 | 高级换色 |

### 8.2 Advanced 的三个节点

| 节点 | 通道 |
|---|---|
| Normal/AO/Roughness (RGBA) | R=法线 X，G=法线 Y，B=AO，A=Roughness |
| Metallic（灰度） | 0=非金属，255=全金属 |
| Color/Emissive Mask (RGBA) | RGB=颜色，A=自发光遮罩 |

- 自发光默认关闭；在 SDK 材质属性里设 `Emissive Color` + `Emissive Intensity`（0–100）。
- **没有自发光遮罩会让整个 mesh 发光**；不需要发光就用普通颜色贴图。
- 材质参数在“新建 patch”后要重设；把数值记在 `PLAN.md`。

### 8.3 贴图规则

| 规则 | 说明 |
|---|---|
| 正方形 | 512×512、1024×1024、2048×2048、4096×4096 |
| 2 的幂 | 非 2 的幂会出问题 |
| 法线 | **OpenGL** 约定；DirectX 法线要反相绿通道 |
| Roughness / Gloss | 互为反相 |
| AO | 可省略，全白也可 |
| 格式 | SDK 可用 PNG/TGA，保存时转 DDS；也可直接给 DDS |
| DDS（可选） | 8.8.8.8 RGBA 24bpp、Premultiplied Alpha 关、DX10 Header 开 |

### 8.4 材质数量

- 目标 unit 有几个材质槽，你的 mesh 最好就有几个；**不要超**。
- 旧权重/旧 SDK 下超槽会**启动即崩**；新 SDK 也建议不超。
- 需要更多贴图时，把多套贴图合并成一张 **texture atlas**，而不是加材质槽。

---

## 9. 从 SDK 导出到可安装包

### 9.1 Save Units 相关设置

| 设置 | 建议 | 说明 |
|---|---|---|
| `Force 3 UV Sets` | **开** | 关且 mesh 只有 1 个 UVMap → 游戏里**不可见**【文档】 |
| `Force 1 Group` | 开 | 只保留一个顶点组，丢掉无用的 `1_#/2_#` |
| `Auto LODs` | 普通 mod 开；LOD 相关 unit 关 | 见 §7.2 |
| `Save Textures with Material` | 开 | 材质和贴图一起进 patch |
| `Generate Random Texture IDs` | 开 | 防止贴图 ID 冲突互相覆盖 |
| `Save only Custom Textures` | 开 | 不把原版贴图重复打包 |
| `Save Non-SDK Materials` | 按需 | 把原版材质带到另一个 mesh |
| `Patch Base Archive Only` | 开 | patch 写进 `9ba626afa44a3aa3` |
| `Legacy Weight Names` | 新项目关 | 旧 `0_1` 命名才开 |
| `Merge Armatures` | 护甲套装开 | 多个 unit 合并到一个骨架 |

### 9.2 物理形态

```
<ModName>/
├── manifest.json
├── README.md
├── cover.jpg
├── Core/
│   ├── 9ba626afa44a3aa3.patch_0
│   ├── 9ba626afa44a3aa3.patch_0.gpu_resources   ← 有 GPU 数据时
│   └── 9ba626afa44a3aa3.patch_0.stream          ← 有流式数据时
└── (可选) 其他 option 文件夹
```

- patch 文件名固定 `<archive>.patch_N`；`9ba626afa44a3aa3` 是基础 archive，
  不是你的 mod ID。
- **不是所有 patch 都用基础 archive**：贴图/场景/音频可能 patch
  `ee6b1ba7e22d71ed`、`a193a00ce4bbd529` 等。保留 SDK 导出的 archive 名。
- `.stream` / `.gpu_resources` 与宿主 patch **同目录同前缀**；少一个会资源丢失但不报错。
- 一个 option 内，每个 archive 的编号从 `0` 连续；管理器部署时会再重排。

### 9.3 用本技能收编

SDK 的 `Export Patch` 会导出 zip。把它交给工具：

```bash
# 1) 建模型工程（不需要 --author/--name）
python tools/hd2mod.py new --kind model \
  --title "B-01 换成 XX" --subject "B-01 Tactical" \
  --target-kind armor --out "D:/HD2 Mods/_src/b01_xx"

# 2) 把 SDK 导出的 zip / 文件夹收编进 patches/
python tools/hd2mod.py adopt "<工程目录>" --from "<SDK导出的zip>"

# 3) 打包 + 门禁
python tools/hd2mod.py build "<工程目录>" --zip
python tools/hd2mod.py check "<工程目录>"

# 4) 装库
python tools/hd2mod.py install "<工程目录>"
```

`adopt` 会：

- 只收 `*.patch_*` 与其 `.stream` / `.gpu_resources`；
- 校验容器（magic、类型表、条目表、偏移）；
- 统计 unit / material / texture 数量；
- 写 `patches/SOURCE.json` 记录来源，方便下次复现。

**多 option**（例如“护甲 / 头盔”分开勾选）：

```bash
python tools/hd2mod.py adopt "<工程>" --from "<护甲zip>" --option Core
python tools/hd2mod.py adopt "<工程>" --from "<头盔zip>" --option Helmet
python tools/hd2mod.py build "<工程>" --zip
```

`build` 会按 `manifest.Options[].Include` 分别找 `patches/<Include>/`，
生成 `dist/<Name>/<Include>/`。`SubOptions` 的 Include 也会递归收集；
单 option 的扁平 `patches/` 仍然兼容。

`check` 会拦：缺伴生文件、偏移越界、类型计数不符、重复资源、没有 Unit 资源、
manifest 缺字段、option 指向不存在的文件夹、patch 编号不连续（dist）。

### 9.4 manifest

```json
{
  "Version": 1,
  "Guid": "24cb6a0c-08f8-4281-89b9-22ea8dcf8a95",
  "Name": "B-01 换成 XX v0.1.0",
  "Description": "替换 B-01 Tactical 外观；需要管理器部署后重启。",
  "IconPath": "cover.jpg",
  "Options": [
    {
      "Name": "核心 / Core（必选）",
      "Description": "护甲 + 头盔补丁",
      "Image": "cover.jpg",
      "Include": ["Core"]
    }
  ]
}
```

- `Version` 是 **manifest 语法版本，固定 1**，不是 mod 版本号；mod 版本写 `Name`。
- `Guid` 生成一次，永不改。
- `SubOptions` 互斥；同一时间只能选一个。
- zip 根目录直接放 `manifest.json`，不要多套一层文件夹。

### 9.5 部署

- 资源 mod 在 MDL3 里是 `LAUNCH ONLY`：**不能游戏内开关**。
- 用 Arsenal / HD2MM / hd2-mod-cli 任一管理器部署 → **重启游戏**。
- 部署前退出游戏；管理器用硬链接时，直接改游戏目录的 patch = 改库（P0）。
- 两个 mod 改同一个 `(type, resource_id)` 会冲突，后加载的赢；用干净配置排查。

---

## 10. 实机验收（逐条记录）

1. **装备界面**：图标/模型是否显示新外观？透明/黑紫/原版？
2. **第一人称**：手臂、武器、瞄准镜是否正常？
3. **第三人称**：跑、蹲、爬、表情动作是否扭曲/穿模？
4. **体型**：Brawny / Lean 是否都正确？只做了一种就记录。
5. **附件**：披风、背包、肩甲、腰挂是否穿插？
6. **性能**：帧数是否明显下降？切 LOD 是否闪烁？
7. **卸载**：管理器禁用 → 重新部署 → 是否恢复原版？
8. **多人**：只影响本地外观；队友看到的仍是他们自己的资源。

---

## 11. 排错对照

| 症状 | 最可能原因 | 怎么查 | 怎么修 |
|---|---|---|---|
| 进游戏完全没变化 | patch 没部署 / archive 错 / option 没勾 | 管理器看部署文件；`hd2mod.py inspect` | 重新部署；确认 option |
| 模型透明/看不见 | `Force 3 UV Sets` 关且只有一个 UVMap；材质没保存；只导了 LOD0 | 看 SDK 设置；看 patch 里有没有 material | 开 Force 3 UV Sets；Save Materials；补 LOD |
| 黑紫/亮块 | 贴图格式/尺寸不对；法线方向错；材质节点没接 | 检查正方形/POT、OpenGL 法线、Advanced 节点 | 重导贴图/反相绿通道/重接节点 |
| 模型拉伸/关节扭曲 | 权重没刷好；A-Pose 没对齐；用了 shoulder 而不是 shoulder_twist | 看顶点组与姿势 | 重传权重；改绑 shoulder_twist |
| 接缝有亮线/孔 | 切分方式不对；接缝权重不是 1.0；法线没修 | 看接缝权重；Data Transfer | 按权重切；权重归一；Data Transfer |
| 启动即崩 | 材质槽超过原版；patch 冲突；游戏更新后 unit 数据不兼容 | 只启用本 mod；看日志 | 减材质；purge；用 Retagger 更新 |
| 某些部件消失 | 该 unit 需要逐 LOD 改；Auto LODs 覆盖了 | 看 LOD 相关 unit | 关 Auto LODs，逐 LOD 补 |
| 只有一种体型生效 | 只替换了 Brawny 或 Lean | 看 body parts | 做另一体型，或说明只支持一种 |
| 头盔 UI 不显示 | 材质模板/槽位问题 | 换 Advanced；核对槽数 | 重做头盔材质 |
| 更新游戏后失效 | unit 数据/裁剪信息变了 | 对比 build；看是否崩溃 | 用 Retagger 的 Update Old Mod，或重做 |
| 远处闪烁/消失 | LOD 未改/裁剪边界不对 | 切远距离观察 | 补 LOD；检查 culling |
| 帧数暴跌 | 高模铺满所有 LOD；贴图过大 | 看面数/贴图尺寸 | 减面 LOD2+；降贴图 |

---

## 12. 性能与发布

- **面数**：没有官方上限；以目标 unit 同部位的面数为参照。高模铺满所有 LOD
  会明显掉帧【推断】；LOD2 之后用 Decimate。
- **贴图**：护甲常用 1K–2K；4K 只在必要部位用。贴图越大会让 `.gpu_resources` 暴涨。
- **patch 数**：一个 mod 的 patch 数尽量少；超过 512 会影响 MDL3 读取（资源 mod 不走 MDL3，
  但管理器/加载链仍可能受影响）。
- **体积**：发布 zip 前删掉测试用的多余 patch/贴图；保留 `SOURCE.json` 记录来源。
- **版权**：模型/贴图/音效的授权写进 `README` 的 `THIRD_PARTY.md`；没有就写“无”。
- **风险**：客户端外观 mod 通常不触发 EAC，但这不是官方保证；不要做影响他人的改动。

---

## 13. 换 build / 换 SDK 后的复验

1. `python tools/hd2mod.py doctor`：看 build、Blender、SDK 版本。
2. Blender 里 `N` → **Modding** 是否还在；`New Patch` 是否还能写。
3. 打开一个旧 patch：`python tools/hd2mod.py inspect "<patch>"`，类型/条目是否还能解析。
4. 进游戏看：装备界面、第一人称、第三人称、LOD。
5. 记录新 build 号与 SDK 版本到 `README` / `CHANGELOG`。
6. 如果 unit 数据结构变了（崩溃/缺件），优先用 Retagger 的 Update Old Mod；
   仍不行就按新 unit 重做，不要硬改二进制。

### 证据来源

- HD2 Modding Wiki：Armor Replacement / Armor Swapping / Anatomy / Body Parts /
  Materials / Textures / LOD Dependant Units / Manifest / SDK Functions / Settings
- HD2SDK-CommunityEdition v3.11.1 release 与 README
- 本机真实 mod 容器解析：Kraber Apex（34 资源，6 类型）、Clear Visibility（材质/实体 patch）
- 社区工具：HD2 Retagger、MMD2HD2 Studio、HD2SDK-AQ-Edition
