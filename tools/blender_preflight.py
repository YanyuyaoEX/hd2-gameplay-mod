#!/usr/bin/env python3
"""Blender 侧素材预检（只读，不改模型）。

用法（在 Blender 里跑，不是在系统 Python 里跑）：

    blender -b --python tools/blender_preflight.py -- "C:/path/model.fbx"
    blender -b --python tools/blender_preflight.py -- "C:/path/model.blend" --target armor --json "C:/path/report.json"

支持：.fbx / .obj / .glb / .gltf / .blend / .stl / .ply
不支持：.pmx（先装 MMD Tools 导出 FBX，或用 MMD2HD2）

它回答四个问题：
1. 有没有 mesh / 骨架 / 权重 / UV / 材质？
2. 骨架是否命中 HD2 护甲的核心骨？
3. 贴图是不是正方形、2 的幂？
4. 有没有形态键、未应用缩放、面数过高等会卡住流程的问题？

注意：这是**启发式**预检，不替代在 SDK 里导入目标 unit 后的实际对齐。
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

# 与 hd2mod.py 保持一致；预检脚本不 import hd2mod，避免 Blender 里路径问题
CORE_BONES = [
    "root", "spine1", "spine2", "neck", "head",
    "l_clavicle", "r_clavicle", "l_shoulder", "r_shoulder",
    "l_shoulder_twist", "r_shoulder_twist",
    "l_hand", "r_hand", "l_thigh", "r_thigh", "l_foot", "r_foot",
]


def is_power_of_two(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def texture_issue(name: str, w: int, h: int) -> str | None:
    if w <= 0 or h <= 0:
        return f"贴图 {name} 尺寸无效：{w}x{h}"
    if w != h:
        return f"贴图 {name} 不是正方形：{w}x{h}"
    if not is_power_of_two(w):
        return f"贴图 {name} 不是 2 的幂：{w}x{h}"
    return None


def core_bone_report(bones) -> dict:
    present = [b for b in CORE_BONES if b in set(bones)]
    missing = [b for b in CORE_BONES if b not in set(bones)]
    return {"present": present, "missing": missing,
            "ratio": len(present) / len(CORE_BONES) if CORE_BONES else 0.0}


def _parse_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []
    ap = argparse.ArgumentParser(prog="blender_preflight")
    ap.add_argument("model")
    ap.add_argument("--target", default="armor",
                    choices=["armor", "helmet", "weapon", "prop", "texture", "other"])
    ap.add_argument("--json", dest="json_path")
    ap.add_argument("--max-tris", type=int, default=150000,
                    help="超过这个三角面数给性能警告（默认 150000）")
    return ap.parse_args(argv)


def _import_model(bpy, path: Path):
    ext = path.suffix.lower()
    if ext == ".blend":
        bpy.ops.wm.open_mainfile(filepath=str(path))
        return
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path))
    elif ext == ".obj":
        if hasattr(bpy.ops.wm, "obj_import"):
            bpy.ops.wm.obj_import(filepath=str(path))
        else:
            bpy.ops.import_scene.obj(filepath=str(path))
    elif ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif ext == ".stl":
        if hasattr(bpy.ops.wm, "stl_import"):
            bpy.ops.wm.stl_import(filepath=str(path))
        else:
            bpy.ops.import_mesh.stl(filepath=str(path))
    elif ext == ".ply":
        if hasattr(bpy.ops.wm, "ply_import"):
            bpy.ops.wm.ply_import(filepath=str(path))
        else:
            bpy.ops.import_mesh.ply(filepath=str(path))
    elif ext == ".pmx":
        raise RuntimeError("PMX 需要 MMD Tools；请先在 Blender 里导出 FBX，或用 MMD2HD2")
    else:
        raise RuntimeError(f"不支持的格式：{ext}（支持 fbx/obj/glb/gltf/blend/stl/ply）")


def _collect(bpy, max_tris: int):
    report = {
        "meshes": 0, "verts": 0, "tris": 0,
        "materials": 0, "uv_layers": [], "vertex_groups": 0,
        "shape_keys": False, "armatures": [], "bones": [],
        "unapplied_scale": [], "images": [], "actions": 0,
        "dimensions": None, "errors": [], "warns": [],
    }
    mins = [1e9, 1e9, 1e9]
    maxs = [-1e9, -1e9, -1e9]
    material_names = set()

    for obj in bpy.context.scene.objects:
        if obj.type == "MESH":
            report["meshes"] += 1
            mesh = obj.data
            report["verts"] += len(mesh.vertices)
            try:
                mesh.calc_loop_triangles()
                report["tris"] += len(mesh.loop_triangles)
            except Exception:
                pass
            for m in mesh.materials:
                if m:
                    material_names.add(m.name)
            for uv in mesh.uv_layers:
                if uv.name not in report["uv_layers"]:
                    report["uv_layers"].append(uv.name)
            report["vertex_groups"] += len(obj.vertex_groups)
            if mesh.shape_keys:
                report["shape_keys"] = True
            if any(abs(s - 1.0) > 1e-3 for s in obj.scale):
                report["unapplied_scale"].append(obj.name)
            for corner in obj.bound_box:
                world = obj.matrix_world @ __import__("mathutils").Vector(corner)
                for i in range(3):
                    mins[i] = min(mins[i], world[i])
                    maxs[i] = max(maxs[i], world[i])
        elif obj.type == "ARMATURE":
            report["armatures"].append(obj.name)
            for b in obj.data.bones:
                if b.name not in report["bones"]:
                    report["bones"].append(b.name)

    report["materials"] = len(material_names)
    if mins[0] < 1e9:
        report["dimensions"] = [round(maxs[i] - mins[i], 4) for i in range(3)]
    report["actions"] = len(bpy.data.actions)

    for img in bpy.data.images:
        if img.name in ("Render Result", "Viewer Node"):
            continue
        if not img.size[0] or not img.size[1]:
            continue
        report["images"].append({
            "name": img.name, "width": img.size[0], "height": img.size[1],
            "filepath": img.filepath,
        })

    # ---- 判定
    if report["meshes"] == 0:
        report["errors"].append("没有 mesh 物体")
    if report["tris"] > max_tris:
        report["warns"].append(
            f"三角面 {report['tris']:,} 超过 {max_tris:,}；高模会拖帧，LOD2+ 记得减面")
    if report["materials"] == 0:
        report["warns"].append("没有材质；SDK 里要生成材质才能显示")
    if report["materials"] > 8:
        report["warns"].append(
            f"材质 {report['materials']} 个；确认目标 unit 的材质槽够用（超槽可能启动即崩）")
    if not report["uv_layers"]:
        report["errors"].append("没有 UV 层；模型不可见/贴图无法显示")
    elif "UVMap" not in report["uv_layers"]:
        report["warns"].append(
            f"UV 层命名是 {report['uv_layers']}；用合并法时要重命名为 UVMap")
    if report["shape_keys"]:
        report["warns"].append("有形态键；SDK 不导出，先应用/删除")
    if report["unapplied_scale"]:
        report["warns"].append(
            f"有未应用缩放：{', '.join(report['unapplied_scale'][:5])}；先 Ctrl+A 应用")
    if report["armatures"] and report["vertex_groups"] == 0:
        report["warns"].append("有骨架但没有顶点组；权重为空，模型会不动/拉伸")

    for img in report["images"]:
        issue = texture_issue(img["name"], img["width"], img["height"])
        if issue:
            report["warns"].append(issue)

    return report


def main():
    args = _parse_args()
    try:
        import bpy  # noqa: F401
    except ImportError:
        print("[FAIL] 这个脚本必须在 Blender 里运行：", file=sys.stderr)
        print('       blender -b --python tools/blender_preflight.py -- "model.fbx"', file=sys.stderr)
        return 2

    path = Path(args.model)
    if not path.is_file():
        print(f"[FAIL] 文件不存在：{path}", file=sys.stderr)
        return 2

    try:
        _import_model(bpy, path)
    except Exception as e:
        print(f"[FAIL] 导入失败：{e}", file=sys.stderr)
        return 2

    report = _collect(bpy, args.max_tris)
    bone = core_bone_report(report["bones"])
    report["core_bones"] = bone

    if not report["armatures"]:
        if args.target in ("armor", "helmet"):
            report["errors"].append("没有骨架：护甲/头盔路线需要先绑定到 HD2 骨架")
        elif args.target == "weapon":
            report["warns"].append(
                "没有骨架：L1 外观级可以（整枪绑 boss）；"
                "要保留枪机/拉机柄/弹匣动作，需按原版顶点组绑（L2/L3）")
        else:
            report["warns"].append("没有骨架：只能做静态道具/武器（或先绑定）")
    elif bone["ratio"] < 0.5:
        report["warns"].append(
            f"核心 HD2 骨命中 {len(bone['present'])}/{len(CORE_BONES)}；"
            "需要重定向/权重传递（Avatar Rig）")

    print(f"\n== 预检：{path.name} ==")
    print(f"目标类型：{args.target}")
    print(f"mesh {report['meshes']} · 顶点 {report['verts']:,} · 三角 {report['tris']:,}")
    print(f"材质 {report['materials']} · UV {report['uv_layers']} · 顶点组 {report['vertex_groups']}")
    print(f"骨架 {len(report['armatures'])} · 骨骼 {len(report['bones'])} · "
          f"核心骨 {len(bone['present'])}/{len(CORE_BONES)}")
    if report["dimensions"]:
        print(f"包围盒（米）：{report['dimensions']}")
    print(f"贴图 {len(report['images'])} · 动作 {report['actions']}")

    for e in report["errors"]:
        print(f"[FAIL] {e}")
    for w in report["warns"]:
        print(f"[WARN] {w}")
    if not report["errors"]:
        print("[ OK ] 预检通过；下一步是在 SDK 里导入目标 unit 并对齐。")

    if args.json_path:
        outp = Path(args.json_path)
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[ OK ] 报告写入：{outp}")

    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
