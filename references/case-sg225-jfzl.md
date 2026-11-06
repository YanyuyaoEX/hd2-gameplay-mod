# 案例：SG-225SP 千发百中「破裂者」→ 飓风之龙（OBJ 静态模型，L1）

> 本技能第一次用 **Blender 脚本全自动** 跑通的武器替换案例。
> 目标：**SG-225SP 千发百中「破裂者」（Breaker Spray & Pray）** → 逆战「飓风之龙」OBJ。
> 结果：1 个 patch（28,215 字节）+ 52 MB `.gpu_resources`，含 1 unit / 2 material / 6 texture。

## 1. 输入

| 项 | 值 |
|---|---|
| 目标武器 | SG-225SP 千发百中「破裂者」（Breaker Spray & Pray） |
| 目标 archive | `c5a05d09369d0670`（与基础型 SG-225 共用） |
| 目标 unit | `7073132068558755510` |
| LOD0 MeshInfoIndex | **9**（基础型是 8，不要写死） |
| 目标材质槽 | 3 个（LOD0） |
| 目标顶点组 | `boss` / `charging_handle` / `fire_selector` / `bolt_carrier` / `attach_*` / `IK_*` / `ejector` … |
| 模型 | `飓风之龙.obj`，49,076 verts / 45,260 tris |
| 模型材质 | 3 个（lxg1/lxg2 有 color+normal，lxg3 只有 20 个面） |
| 贴图 | 2×2048² color + 2×2048² normal，另有一张未使用的 reticle |

## 2. 子型号辨识（这个案例踩过的坑）

中文名和英文缩写**不是一一对应**，必须落到 unit 上：

| 中文名 | 英文名 | archive | unit | 说明 |
|---|---|---|---|---|
| SG-225 破裂者 | SG-225 Breaker | `c5a05d09369d0670` | `5050852199397921576` | 基础型，LOD0 MII = 8 |
| **SG-225SP 千发百中「破裂者」** | SG-225SP Breaker Spray & Pray | `c5a05d09369d0670` | **`7073132068558755510`** | 本案例目标，LOD0 MII = **9** |
| SG-225IE 高燃「破裂者」 | SG-225IE Breaker Incendiary | `2fe755e42b659f64` | `13918995818598980231` | 独立 archive |

判定方法（按可靠性排序）：

1. **中文 wiki 搜中文名**：`helldivers.wiki.gg/zh` 搜索「千发百中」→ 命中
   `SG-225SP 千发百中“破裂者”`，页面里写明英文名与「标准破裂者的变体」。
2. **英文名搜 SDK 索引**：`hd2mod.py lookup "SG-225SP"` → 得 archive；
   再看 archive 里各 unit 的 `friendlynames.txt` 条目。
3. **看 unit 的 LOD0 包围盒**：SP 默认带鸭嘴枪口 + 弹鼓，Y 向比基础型长约 6.3 cm。

> 只改基础型 `505085…` 时，游戏里 **SG-225SP 完全不会变**——两个 unit 各自独立，
> 共用 archive 不代表共用 unit。

## 3. 坐标与对齐（实测）

- 模型长轴是 **Z**，枪口 +Z；目标长轴是 **Y**，枪口 +Y。
- **缩放基准要用基础型机匣长度 0.9161 m，不要用 SP 的 0.9793 m**：
  SP 的包围盒含默认鸭嘴枪口/弹鼓，按它缩放会把整枪拉长约 7%。
- 缩放：`0.9161 / 89.3005 = 0.0102586`。
- 旋转：`RotX(-90°)` 把 +Z→+Y；再 `RotY(180°)` 把上下翻正（枪身不颠倒）。
- 平移：按**基础型包围盒中心**对齐，得到 `(0.0171, 0.0615, 0.1104)`。
- 结果包围盒：`(-0.0522, -0.250, -0.0704)` ～ `(0.0865, 0.6661, 0.2244)`，
  参照：`(-0.0449, -0.25, -0.0624)` ～ `(0.0792, 0.6661, 0.2164)`。
- 握把低点簇在 Y≈-0.08，与目标 `IK_right`（Y=-0.0745）基本对齐；
  下方大块在 Y≈0.14–0.26，是护木/弹匣块，不是握把。

## 4. 材质

目标原材质是复杂 LUT/迷彩材质（14 个纹理槽），不适合直接套用 OBJ 的 UV。
改为创建 **2 个 Advanced 模板材质**：

| 材质 | Color | Normal/AO/Roughness | Metallic |
|---|---|---|---|
| body | `body_color.png` | `body_nar.png`（R/G 法线，B=255 AO，A=128 粗糙度） | `body_metal.png`（180 灰） |
| detail | `detail_color.png` | `detail_nar.png` | `detail_metal.png` |

- Advanced 的节点组输入名：`Normal/AO/Roughness`、`Metallic`、`Base Color/Emission Mask`。
- SDK 自动把 PNG 用 texconv 转成 DDS，并按模板只保存 3 个自定义纹理槽。
- 最终 patch 里：2 material + 6 texture（每个材质 3 张）。

## 5. 网格与保存

- 导入 OBJ（`forward_axis='Y', up_axis='Z'`），应用变换，按上述矩阵/平移对齐。
- **选 LOD0 不能按 `MeshInfoIndex == 8` 写死**：基础型是 8，SP 是 9。
  按对象名 `*_lod0` 选，兜底取顶点数最多的那个。
- 删除目标 LOD0 顶点，保留目标对象的 `Z_ObjectID / MeshInfoIndex / BoneInfoIndex` 和 Armature Modifier。
- 把 OBJ 的 3 个材质合并成 2 个（lxg3 的 20 个面并入 detail），与目标 2 个槽一致。
- 加入目标对象，全部顶点绑 `boss`（L1 外观级）。
- `ImportLods=True` 只用于拿到 LOD0；随后删除 LOD1–8 对象。
- `AutoLods=True`：保存时把 LOD0 复制到其余 LOD。
- 结果（v0.3.0）：`9ba626afa44a3aa3.patch_0` 56,019 字节，`gpu_resources` 52,347,216 字节，
  类型：unit 3 / bones 3 / state_machine 3 / animation 4 / material 2 / texture 6。
- 校验：patch 里的 unit `file_id` 必须等于目标 unit `7073132068558755510`；
  两个弹匣 unit 重新导入后应为 **1 顶点、0 面**。

## 6. 挂点骨骼（v0.2.0 修复）

原版枪口/瞄具/下挂/弹鼓都是**独立 unit**，按 SP 的挂点生成。换成飓风之龙后：

| 骨骼 | 原位置 | 症状 | 新位置 |
|---|---|---|---|
| `attach_muzzle` | `(0, 0.6661, 0.1494)` | 鸭嘴枪口全露、浮在枪口前 | `(0, 0.200, 0.050)` |
| `attach_optic` | `(0, 0.0739, 0.2111)` | 瞄具比新枪顶面（0.2244）低 1.3 cm，半陷 | `(0, 0.200, 0.050)` |
| `attach_mag` | `(0, 0.1559, 0.1243)` | 弹鼓穿在新枪弹鼓里，半露 | `(0, 0.200, 0.050)` |
| `attach_underbarrel` | `(0, 0.3967, 0.0356)` | 下挂悬空 | `(0, 0.200, 0.050)` |
| `sight` | `(0, -0.1000, 0.2292)` | 瞄准参考，不动 | 不变 |

选 `(0, 0.20, 0.05)` 的原因：这是新模型最厚的一段（弹鼓段 y 0.14–0.26、
z −0.07–0.176、宽 0.139），原版配件整个塞进去不会从缝里露出来。

实现（Blender）：

```python
HIDE = Vector((0.0, 0.200, 0.050))
for name in ("attach_muzzle", "attach_underbarrel", "attach_mag", "attach_optic"):
    eb = arm.data.edit_bones[name]
    delta = HIDE - eb.head
    eb.head = HIDE
    eb.tail = eb.tail + delta      # head/tail 一起移，保持朝向
```

- 只移 head 会改骨骼朝向，配件会歪。
- 保存 unit 后重新导入 patch 验证：四个骨骼都读回 `(0.0, 0.2, 0.05)`。
- 配件属性（弹容、散布、倍率）仍然生效，只是模型不显示。
- 想保留瞄具可见的版本：把 `attach_optic` 放到 `(0, 0.105, 0.2245)`（新枪顶面）。

### 6.1 弹匣/弹鼓：挂点藏不住，要收网格（v0.3.0）

弹鼓 unit `4457329115126715741`（`ltshotgun_drum_magazine`）的局部包围盒是
`(-0.0794, -0.0123, -0.2611) ~ (0.0794, 0.102, 0.0166)`——**高 0.277 m**，
原点在顶部。挂点不管放哪，它都会从新枪下方穿出来，所以不能靠挪骨骼解决。

做法：把这两个 unit 的网格收成 1 个顶点。

| unit | 名称 | 处理 |
|---|---|---|
| `4457329115126715741` | `ltshotgun_drum_magazine` | LOD0 全选 → Merge at Center → 1 顶点 0 面 |
| `7546010150065048137` | `n_box_magazine_extended` | 同上（局部高 0.30 m） |
| `13244374875764312301` | （无名，空 unit） | 本来就是 0 面，不用处理 |

- 这些弹匣 unit 就在武器自己的 archive 里，所以只影响 SG-225 系列。
- 收起后 patch 是 `unit 3 / bones 3 / state_machine 3 / animation 4`，体积 56 KB。
- 属性（弹容、换弹时间、人体工学）仍按配件生效；换弹动画照播，只是弹匣不可见。

## 7. 已知限制

- L1：整枪绑 `boss`，枪机/拉机柄/快慢机不跟随原版动画；枪能拿、能开火。
- 使用原版 SG-225SP 的动画、音效；`attach_*` 已重设，原版配件不显示（属性仍生效）。
- 替换后 SP 默认的鸭嘴枪口/弹鼓随原模型一起去掉（外观整枪替换的必然结果）。
- 握把/枪口位置是按包围盒对齐的，实机可能需要 ±1–2 cm 微调。
- 模型来自网络，发布前确认版权。

## 8. 复现命令（本机）

```bash
# 1) 整理模型到 ASCII 路径
#    原文：D:\BaiduNetdiskDownload\逆战未来飓风之龙\
#    目标：D:\HD2 Mods\_src\sg225_jfzl\assets\model\

# 2) Blender 脚本（本案例实际用的脚本）
#    SDK 启动会联网抓 hashlists 且无超时，国内会卡住；
#    给 addon 加 HD2SDK_OFFLINE=1 开关后用它跳过（见 references/platform-status.md）
HD2SDK_OFFLINE=1 "D:/HD2Tools/blender-4.0.2-windows-x64/blender.exe" -b \
  --factory-startup --python "D:/HD2 Mods/_src/sg225_jfzl/build_patch_mat.py"

# 3) 打包/门禁
python tools/hd2mod.py build "D:/HD2 Mods/_src/sg225_jfzl" --zip
python tools/hd2mod.py check "D:/HD2 Mods/_src/sg225_jfzl"
```

> 这个脚本是**案例专用**（硬编码目标 unit/材质/路径），不是通用工具。
> 但它证明了：静态 OBJ 武器 + 两个 Advanced 材质 + 包围盒对齐，
> 可以全自动生成可加载的 patch。
