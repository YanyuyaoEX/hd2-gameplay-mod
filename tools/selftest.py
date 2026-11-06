#!/usr/bin/env python3
"""hd2mod 自检：不依赖游戏、Blender、srkit。

    python tools/selftest.py

覆盖：
- Lua 单资源包的构造/解析/门禁
- 多类型资源包（模型/贴图）的解析
- 模型工程 new → adopt → build → check → inspect
- 缺伴生文件时门禁必须拦截
- lookup 读 SDK 索引
"""

from __future__ import annotations

import json
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "hd2mod.py"
sys.path.insert(0, str(ROOT / "tools"))

import hd2mod  # noqa: E402
import blender_preflight as bp  # noqa: E402

PASS, FAIL = 0, 0


def check(name: str, cond: bool, detail: str = ""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[ OK ] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}" + (f"  {detail}" if detail else ""))


def run(*args, expect: int = 0):
    r = subprocess.run([sys.executable, str(TOOL), *map(str, args)],
                       cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode != expect:
        print(out)
    check(f"CLI {' '.join(map(str, args))} → {expect}", r.returncode == expect,
          f"实际 {r.returncode}")
    return out


def build_asset_patch(entries) -> bytes:
    """entries: [(type_id, file_id, data, gpu_size, stream_size)]"""
    nentry = len(entries)
    order = []
    for tid, *_ in entries:
        if tid not in order:
            order.append(tid)
    counts = Counter(tid for tid, *_ in entries)
    ntype = len(order)

    table_end = hd2mod.HEADER_SIZE + ntype * hd2mod.TYPE_SIZE + nentry * hd2mod.ENTRY_SIZE
    off = hd2mod.align_up(table_end, 16)
    placed = []
    for tid, fid, data, gpu, stream in entries:
        payload = struct.pack("<II", len(data), 2) + data
        placed.append((tid, fid, off, len(payload), gpu, stream))
        off = hd2mod.align_up(off + len(payload), 16)
    total = off

    out = bytearray()
    out += struct.pack("<IIII", hd2mod.TOC_MAGIC, ntype, nentry, 0)
    unk = bytearray(56)
    struct.pack_into("<I", unk, 16, total)
    out += unk
    for tid in order:
        out += struct.pack("<QQQII", 0, tid, counts[tid], 16, 16)
    for idx, (tid, fid, toc, size, gpu, stream) in enumerate(placed):
        out += struct.pack("<QQQQQQQIIIIII", fid, tid, toc, 0, 0, 0, 0,
                           size, stream, gpu, 16, 16, idx)
    out += b"\0" * (hd2mod.align_up(len(out), 16) - len(out))
    for (tid, fid, toc, size, gpu, stream), (_, _, data, _, _) in zip(placed, entries):
        payload = struct.pack("<II", len(data), 2) + data
        out += payload
        out += b"\0" * (hd2mod.align_up(len(out), 16) - len(out))
    return bytes(out[:total])


def test_lua():
    blob = hd2mod.build_lua_patch(0x37FCC0A04812EAB6, b"return {}\n")
    info = hd2mod.parse_lua_patch(blob)
    check("Lua 包：ID 往返", info["file_id"] == 0x37FCC0A04812EAB6)
    check("Lua 包：脚本往返", info["script"] == b"return {}\n")
    check("Lua 包：自长度 == 文件长度", info["self_size"] == len(blob))
    check("Lua lint：goto 被拦", len(hd2mod.lint_lua("goto x")) == 1)
    check("Lua lint：普通代码不误报", not hd2mod.lint_lua("local a = 1\nreturn a"))


def test_asset_patch(tmp: Path):
    entries = [
        (0xE0A48D0BE9A7453F, 0x1111111111111111, b"unit", 0, 0),
        (0xEAC0B497876ADEDF, 0x2222222222222222, b"mat", 32, 0),
        (0xCD4238C6A0C69E32, 0x3333333333333333, b"tex", 16, 0),
    ]
    blob = build_asset_patch(entries)
    p = tmp / "9ba626afa44a3aa3.patch_0"
    p.write_bytes(blob)
    (tmp / (p.name + ".gpu_resources")).write_bytes(b"G" * 48)
    info, errs, warns = hd2mod.check_patch_file(p)
    check("资源包：解析成功", info is not None and not errs, str(errs))
    check("资源包：unit 计数", info and info["unit_count"] == 1)
    check("资源包：material/texture 计数",
          info and info["type_counts"].get("material") == 1
          and info["type_counts"].get("texture") == 1)


def test_model_flow(tmp: Path):
    proj = tmp / "proj"
    run("new", "--kind", "model", "--title", "Selftest Armor",
        "--subject", "B-01 Tactical", "--target-kind", "armor", "--out", proj)

    src = tmp / "sdk_out"
    src.mkdir()
    blob = build_asset_patch([
        (0xE0A48D0BE9A7453F, 0xAAAAAAAAAAAAAAAA, b"unit-data", 0, 0),
        (0xEAC0B497876ADEDF, 0xBBBBBBBBBBBBBBBB, b"mat-data", 64, 0),
    ])
    patch = src / "9ba626afa44a3aa3.patch_0"
    patch.write_bytes(blob)
    (src / (patch.name + ".gpu_resources")).write_bytes(b"G" * 64)

    run("adopt", proj, "--from", src)
    check("adopt：patch 已复制", (proj / "patches" / patch.name).is_file())
    check("adopt：伴生文件已复制",
          (proj / "patches" / (patch.name + ".gpu_resources")).is_file())
    check("adopt：SOURCE.json 已写", (proj / "patches" / "SOURCE.json").is_file())

    run("build", proj, "--zip")
    dist = proj / "dist"
    check("build：dist 有 patch", bool(list(dist.rglob("*.patch_0"))))
    check("build：dist 有伴生", bool(list(dist.rglob("*.gpu_resources"))))
    run("check", proj)
    out = run("inspect", dist, "--json")
    check("inspect --json 可解析", out.strip().startswith("["))

    # 删掉伴生文件后，门禁必须失败
    for f in dist.rglob("*.gpu_resources"):
        f.unlink()
    run("check", proj, expect=1)


def test_zip_adopt(tmp: Path):
    proj = tmp / "zip_proj"
    run("new", "--kind", "model", "--title", "Zip Armor",
        "--subject", "PH-56 Jaguar", "--target-kind", "armor", "--out", proj)
    blob = build_asset_patch([(0xE0A48D0BE9A7453F, 0xCCCCCCCCCCCCCCCC, b"u", 0, 0)])
    zpath = tmp / "sdk_export.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        z.writestr("Export/9ba626afa44a3aa3.patch_0", blob)
        z.writestr("Export/9ba626afa44a3aa3.patch_0.stream", b"")
    run("adopt", proj, "--from", zpath)
    check("zip adopt：保留子目录",
          (proj / "patches" / "Export" / "9ba626afa44a3aa3.patch_0").is_file())
    run("build", proj)
    run("check", proj)


def test_multi_option(tmp: Path):
    proj = tmp / "multi"
    run("new", "--kind", "model", "--title", "Multi Option",
        "--subject", "B-01 Tactical", "--target-kind", "armor", "--out", proj)
    mf = json.loads((proj / "manifest.json").read_text(encoding="utf-8"))
    mf["Options"].append({"Name": "Extra", "Description": "extra",
                          "Include": ["Extra"]})
    (proj / "manifest.json").write_text(json.dumps(mf, ensure_ascii=False, indent=1),
                                       encoding="utf-8")

    for name, fid in (("Core", 0xD1D1D1D1D1D1D1D1), ("Extra", 0xE2E2E2E2E2E2E2E2)):
        src = tmp / f"src_{name}"
        src.mkdir()
        (src / "9ba626afa44a3aa3.patch_0").write_bytes(
            build_asset_patch([(0xE0A48D0BE9A7453F, fid, b"u", 0, 0)]))
        run("adopt", proj, "--from", src, "--option", name)
    run("build", proj)
    run("check", proj)
    dist = proj / "dist"
    check("多 option：Core 有 patch", bool(list((dist).rglob("Core/*.patch_0"))))
    check("多 option：Extra 有 patch", bool(list((dist).rglob("Extra/*.patch_0"))))


def test_weapon_plan(tmp: Path):
    proj = tmp / "weapon"
    run("new", "--kind", "model", "--title", "Weapon Test",
        "--subject", "AR-61 Tenderizer", "--target-kind", "weapon", "--out", proj)
    text = (proj / "PLAN.md").read_text(encoding="utf-8")
    check("武器 PLAN：含层级", "做到哪一层" in text)
    check("武器 PLAN：含 attach 骨骼", "attach_" in text)
    check("武器 PLAN：含握把试装", "试装" in text)


def test_lookup(tmp: Path):
    sdk = tmp / "fake_sdk"
    (sdk / "hashlists").mkdir(parents=True)
    (sdk / "hashlists" / "archivehashes.json").write_text(json.dumps({
        "Armor": {"58e4bd4b2278d15c": "B-01 Tactical"},
        "Helmet": {"a856edff49cfdd95": "A-9 Helljumper"},
    }), encoding="utf-8")
    (sdk / "hashlists" / "friendlynames.txt").write_text(
        "13556064353924354700 Helmet B-01 Tactical (Variation 1)\n", encoding="utf-8")
    out = run("lookup", "B-01", "--sdk", sdk)
    check("lookup：命中 archive", "58e4bd4b2278d15c" in out)
    check("lookup：命中 friendlyname", "Helmet B-01 Tactical" in out)
    run("lookup", "不存在的装备", "--sdk", sdk, expect=1)


def test_preflight_helpers():
    check("预检：1024 是 2 的幂", bp.is_power_of_two(1024))
    check("预检：1000 不是 2 的幂", not bp.is_power_of_two(1000))
    check("预检：非正方形被拦", bp.texture_issue("x", 1024, 512) is not None)
    check("预检：1024 正方形通过", bp.texture_issue("x", 1024, 1024) is None)
    rep = bp.core_bone_report(["root", "spine1", "head"])
    check("预检：核心骨命中", len(rep["present"]) == 3 and rep["ratio"] > 0)
    inc = hd2mod._manifest_includes([
        {"Include": ["A"], "SubOptions": [{"Include": ["A/B"]}, {"Include": ["A/C"]}]},
        {"Include": ["D"]},
    ])
    check("manifest：递归收集 SubOptions Include", inc == ["A", "A/B", "A/C", "D"])


def main():
    print("== hd2mod selftest ==")
    test_lua()
    test_preflight_helpers()
    with tempfile.TemporaryDirectory(prefix="hd2mod_test_") as td:
        tmp = Path(td)
        t1 = tmp / "t1"; t1.mkdir()
        test_asset_patch(t1)
        t2 = tmp / "t2"; t2.mkdir()
        test_model_flow(t2)
        t3 = tmp / "t3"; t3.mkdir()
        test_zip_adopt(t3)
        t4 = tmp / "t4"; t4.mkdir()
        test_multi_option(t4)
        t5 = tmp / "t5"; t5.mkdir()
        test_lookup(t5)
        t6 = tmp / "t6"; t6.mkdir()
        test_weapon_plan(t6)
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
