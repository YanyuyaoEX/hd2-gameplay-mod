#!/usr/bin/env python3
"""hd2mod.py - HD2 mod 工具（零依赖，纯标准库）

    doctor                     体检：游戏 / 库 / 管理器 / 加载器 / Blender / SDK
    lookup <关键词>            查装备对应的 archive ID（读本机 HD2SDK 索引）
    new  --kind lua|model ...  建工程（玩法脚本 / 模型替换）
    adopt <project> --from X   收编 HD2SDK 导出的 patch（zip / 文件夹 / 单文件）
    build <project> [--zip]    打包成可导入的 dist/
    check <project>            静态门禁（全绿才允许部署）
    inspect <patch|文件夹>     看 patch 里有哪些资源类型/条目/伴生文件
    install <project>          放进 mod 库并提示部署
    lint <file.lua>            Lua 5.1 兼容性检查

设计前提：**不依赖 srkit**。Lua 补丁容器由本文件直接生成；
模型/贴图补丁由 HD2SDK 生成，本工具负责收编、校验、打包与部署。
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import uuid
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------- 常量

TOC_MAGIC = 0xF0000011
LUA_TYPE_ID = 0xA14E8DFA2CD117E2
PATCH_NAME = "9ba626afa44a3aa3.patch_0"
HEADER_SIZE = 0x48          # 72
TYPE_SIZE = 0x20            # 32
ENTRY_SIZE = 0x50           # 80
TOC_BLOB_ALIGN = 16
SELF_SIZE_OFFSET = 0x20     # 头部里记录"本包总长度"的 u32
MAX_PATCHES = 512

ARCHIVE_PATCH_RE = re.compile(r"^(?P<archive>[0-9a-fA-F]+)\.patch_(?P<num>\d+)$")
GUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                     r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
MODULE_RE = re.compile(r"^mods/[a-z0-9_]+/[a-z0-9_]+$")

# HD2SDK utils/constants.py 的类型 ID（2026-11 抓取）
TYPE_NAMES = {
    0x18DEAD01056B72E9: "bones",
    0xE0A48D0BE9A7453F: "unit",
    0xC4F0F4BE7FB0C8D6: "composite_unit",
    0xCD4238C6A0C69E32: "texture",
    0xEAC0B497876ADEDF: "material",
    0x931E336D7646CC26: "animation",
    0xA486D4045106165C: "state_machine",
    0x5F7203C8F280DAB8: "physics",
    0xA8193123526FAD64: "particles",
    0x535A7BD3E650D799: "wwise_bank",
    0xAF32095C82F2B070: "wwise_dep",
    0x504B55235D21440E: "wwise_stream",
    0xD50A8B7E1C82B110: "wwise_metadata",
    0x0D972BAB10B40FD3: "strings",
    0xA14E8DFA2CD117E2: "lua",
    0x9831CA893B0D087D: "entity",
    0x46BC82AAE9AE0565: "xaml",
    0xAB2F78E885F513C6: "prefab",
    0x2A690FD348FE9AC5: "level",
    0xAA5965F03029FA18: "bik",
    0x9EFE0A916AAE7880: "font",
    0xD7014A50477953E0: "cloth",
    0xFE73C7DCFF8A7CA5: "shading_environment",
    0x82645835E6B73232: "config",
    0xAD9C6D9ED1E5E77A: "package",
    0x250E0A11AC8E26F8: "shading_environment_mapping",
    0xF7505933166D6755: "vector_field",
    0x92D3EE038EEB610D: "flow",
    0x27862FE24795319C: "render_config",
    0x3B1FA9E8F6BAC374: "network_config",
    0xB277B11FE4A61D37: "mouse_cursor",
    0x7910103158FC1DE9: "renderable",
    0x9E5C3CC74575AEB5: "shader_library_group",
    0xE5EE32A477239A93: "shader_library",
    0x05106B81DCD58A13: "runtime_font",
    0x1D59BD6687DB6B33: "ragdoll_profile",
    0x2A0A70ACFE476E1D: "ah_bin",
    0x57A13425279979D7: "ik_skeleton",
    0x5FDD5FE391076F9F: "wwise_properties",
    0x6592B918E67F082C: "havok_ai_properties",
    0x9199BB50B6896F02: "texture_atlas",
    0xB8FD4D2CEDE20ED7: "geleta",
    0xE3F2851035957AF5: "hash_lookup",
    0xE985C5F61C169997: "speedtree",
    0xF7A09F8BB35A1D49: "havok_physics_properties",
    0xFCAAF813B4D3CC1E: "camera_shake",
    0x5EE65304478F8DB5: "bik2",
}

# 护甲/头盔骨架的核心骨（用于预检脚本与文档；不是全部骨骼）
CORE_BONES = [
    "root", "spine1", "spine2", "neck", "head",
    "l_clavicle", "r_clavicle", "l_shoulder", "r_shoulder",
    "l_shoulder_twist", "r_shoulder_twist",
    "l_hand", "r_hand", "l_thigh", "r_thigh", "l_foot", "r_foot",
]

CONFIG_DIR = Path(os.environ.get("HD2MOD_HOME") or (Path.home() / ".hd2-gameplay-mod"))
CONFIG_FILE = CONFIG_DIR / "config.json"


# ---------------------------------------------------------------- 基础

def ok(msg): print(f"[ OK ] {msg}")
def warn(msg): print(f"[WARN] {msg}")
def bad(msg): print(f"[FAIL] {msg}")


def die(msg: str):
    bad(msg)
    raise SystemExit(1)


def read_json(p: Path, default=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def write_json(p: Path, data) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def align_up(v: int, a: int) -> int:
    return (v + a - 1) // a * a


def pretty(p) -> str:
    """Windows 路径展示用：盘符大写、分隔符统一。"""
    if p is None:
        return "(none)"
    s = str(Path(p))
    if len(s) > 1 and s[1] == ":":
        s = s[0].upper() + s[1:]
    return s


def type_name(type_id: int) -> str:
    return TYPE_NAMES.get(type_id, f"type_0x{type_id:016X}")


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} GB"


# ---------------------------------------------------------------- 哈希
# MurmurHash64A，与引擎的 murmur_hash_64 一致（seed=0）

_M64 = (1 << 64) - 1


def murmur64(data, seed: int = 0) -> int:
    if isinstance(data, str):
        data = data.encode("utf-8")
    m, r = 0xC6A4A7935BD1E995, 47
    h = (seed ^ ((m * len(data)) & _M64)) & _M64
    body = (len(data) // 8) * 8
    for pos in range(0, body, 8):
        k = int.from_bytes(data[pos:pos + 8], "little")
        k = (k * m) & _M64
        k ^= k >> r
        k = (k * m) & _M64
        h ^= k
        h = (h * m) & _M64
    tail = len(data) & 7
    for i, shift in ((7, 48), (6, 40), (5, 32), (4, 24), (3, 16), (2, 8)):
        if tail >= i:
            h ^= data[body + i - 1] << shift
    if tail >= 1:
        h ^= data[body]
        h = (h * m) & _M64
    h ^= h >> r
    h = (h * m) & _M64
    h ^= h >> r
    return h


# ---------------------------------------------------------------- 容器

def build_lua_patch(file_id: int, script: bytes) -> bytes:
    """生成单 lua 资源的 .patch_0。

    与真实 mod 包逐字节一致：头部 0x20 处记录本包总长度，末尾不补齐
    （retail 包就是不补齐的；srkit 会补到 16 字节并保留陈旧长度，别混用）。
    """
    payload = struct.pack("<II", len(script), 2) + script
    toc_off = align_up(HEADER_SIZE + TYPE_SIZE + ENTRY_SIZE, TOC_BLOB_ALIGN)
    total = toc_off + len(payload)

    out = bytearray()
    out += struct.pack("<IIII", TOC_MAGIC, 1, 1, 0)
    unk4 = bytearray(56)
    struct.pack_into("<I", unk4, 16, total)
    out += unk4
    out += struct.pack("<QQQII", 0, LUA_TYPE_ID, 1, 16, 16)
    out += struct.pack("<QQQQQQQIIIIII", file_id, LUA_TYPE_ID,
                       toc_off, 0, 0, 0, 0, len(payload), 0, 0, 16, 16, 0)
    out += b"\0" * (toc_off - len(out))
    out += payload
    return bytes(out)


def parse_lua_patch(blob: bytes) -> dict:
    """解析单 lua 资源包（本工具生成的格式），用于 Lua 门禁自检。"""
    info = parse_patch(blob)
    lua_entries = [e for e in info["entries"] if e["type_id"] == LUA_TYPE_ID]
    if len(lua_entries) != 1:
        raise ValueError(f"不是单 lua 资源包（lua 条目 {len(lua_entries)} 个）")
    e = lua_entries[0]
    payload = blob[e["toc_off"]:e["toc_off"] + e["toc_size"]]
    if len(payload) < 8:
        raise ValueError("payload 头不完整")
    size, unknown = struct.unpack_from("<II", payload, 0)
    script = payload[8:8 + size]
    info.update({"file_id": e["file_id"], "toc_offset": e["toc_off"],
                 "toc_size": e["toc_size"], "declared_payload": size,
                 "unknown": unknown, "script": script,
                 "actual_size": len(blob)})
    return info


def parse_patch(blob: bytes) -> dict:
    """通用 patch 解析：支持单 lua、多类型模型/贴图包。

    只做结构解析与边界检查，不解释每种资源的 payload。
    """
    if len(blob) < HEADER_SIZE + TYPE_SIZE + ENTRY_SIZE:
        raise ValueError("文件太小，不是有效的 patch 包")
    magic, ntype, nentry, unk = struct.unpack_from("<IIII", blob, 0)
    if magic != TOC_MAGIC:
        raise ValueError(f"magic 不对：0x{magic:08X}")
    if not (1 <= ntype <= 4096):
        raise ValueError(f"类型数异常：{ntype}")
    if not (1 <= nentry <= 200000):
        raise ValueError(f"条目数异常：{nentry}")
    table_end = HEADER_SIZE + ntype * TYPE_SIZE + nentry * ENTRY_SIZE
    if len(blob) < table_end:
        raise ValueError(f"头部/表被截断：需要 {table_end} 字节，实际 {len(blob)}")

    self_size = struct.unpack_from("<I", blob, SELF_SIZE_OFFSET)[0]

    types = []
    off = HEADER_SIZE
    for i in range(ntype):
        unk1, tid, count, a, b = struct.unpack_from("<QQQII", blob, off)
        types.append({"index": i, "type_id": tid, "count": count,
                      "unk": unk1, "a": a, "b": b})
        off += TYPE_SIZE

    entries = []
    for i in range(nentry):
        (fid, tid, toc, stream, gpu, u1, u2,
         toc_size, stream_size, gpu_size, x1, x2, idx) = \
            struct.unpack_from("<QQQQQQQIIIIII", blob, off)
        entries.append({
            "index": i, "file_id": fid, "type_id": tid,
            "toc_off": toc, "stream_off": stream, "gpu_off": gpu,
            "toc_size": toc_size, "stream_size": stream_size,
            "gpu_size": gpu_size, "entry_index": idx,
        })
        off += ENTRY_SIZE

    actual_counts = Counter(e["type_id"] for e in entries)
    type_counts_ok = all(actual_counts.get(t["type_id"], 0) == t["count"] for t in types)
    declared_total = sum(t["count"] for t in types)

    overlaps = []
    ranges = sorted((e["toc_off"], e["toc_off"] + e["toc_size"], e["index"])
                    for e in entries if e["toc_size"] > 0)
    for (a_start, a_end, a_idx), (b_start, b_end, b_idx) in zip(ranges, ranges[1:]):
        if b_start < a_end:
            overlaps.append((a_idx, b_idx))

    max_toc_end = max((e["toc_off"] + e["toc_size"] for e in entries), default=0)
    return {
        "magic": magic, "types": types, "entries": entries,
        "self_size": self_size, "actual_size": len(blob),
        "type_counts": dict(Counter(type_name(e["type_id"]) for e in entries)),
        "type_counts_ok": type_counts_ok,
        "declared_total": declared_total,
        "overlaps": overlaps, "max_toc_end": max_toc_end,
        "unit_count": actual_counts.get(0xE0A48D0BE9A7453F, 0) +
                      actual_counts.get(0xC4F0F4BE7FB0C8D6, 0),
    }


def iter_patch_files(root: Path) -> list:
    root = Path(root)
    if root.is_file():
        return [root] if ARCHIVE_PATCH_RE.match(root.name) else []
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*")
                  if p.is_file() and ARCHIVE_PATCH_RE.match(p.name))


def group_patches(files) -> dict:
    groups = {}
    for f in files:
        m = ARCHIVE_PATCH_RE.match(f.name)
        groups.setdefault(m.group("archive").lower(), []).append((int(m.group("num")), f))
    return groups


def check_patch_file(path: Path, require_sidecars: bool = True):
    """解析并检查一个 patch 文件，返回 (info, errors, warns)。"""
    path = Path(path)
    errors, warns = [], []
    try:
        blob = path.read_bytes()
        info = parse_patch(blob)
    except Exception as e:
        return None, [f"{path.name} 解析失败：{e}"], []

    if not info["type_counts_ok"]:
        errors.append(f"{path.name} 类型表声明的数量与条目表不一致"
                      f"（声明 {info['declared_total']}，实际 {len(info['entries'])}）")
    if info["overlaps"]:
        pairs = ", ".join(f"{a}/{b}" for a, b in info["overlaps"][:5])
        errors.append(f"{path.name} 条目 TOC 区间重叠：{pairs}")
    if info["max_toc_end"] > info["actual_size"]:
        errors.append(f"{path.name} TOC 越界：最大结束 {info['max_toc_end']} > 文件 {info['actual_size']}")
    # 注意：0x20 的“自记长度”在真实资源包里并不可靠（可能大于或小于文件长度），
    # 不能作为门禁判据；只有本工具生成的单 lua 包才在 Lua 门禁里比对它。

    need_gpu = any(e["gpu_size"] > 0 for e in info["entries"])
    need_stream = any(e["stream_size"] > 0 for e in info["entries"])
    gpu = path.with_name(path.name + ".gpu_resources")
    stream = path.with_name(path.name + ".stream")
    info["gpu_path"] = gpu if gpu.is_file() else None
    info["stream_path"] = stream if stream.is_file() else None
    info["gpu_file_size"] = gpu.stat().st_size if gpu.is_file() else 0
    info["stream_file_size"] = stream.stat().st_size if stream.is_file() else 0
    info["needs_gpu"] = need_gpu
    info["needs_stream"] = need_stream

    if require_sidecars:
        if need_gpu and not gpu.is_file():
            errors.append(f"{path.name} 有条目需要 GPU 数据，但缺 {path.name}.gpu_resources")
        if need_stream and not stream.is_file():
            errors.append(f"{path.name} 有条目需要流式数据，但缺 {path.name}.stream")
        if gpu.is_file() and gpu.stat().st_size > 0 and not need_gpu:
            warns.append(f"{path.name} 带非空 .gpu_resources，但条目里没有 gpu_size > 0")
        if stream.is_file() and stream.stat().st_size > 0 and not need_stream:
            warns.append(f"{path.name} 带非空 .stream，但条目里没有 stream_size > 0")
    return info, errors, warns


def print_patch_info(path: Path, info: dict):
    print(f"\n{path.name}")
    print(f"  文件 {info['actual_size']:,} 字节 · 头部自记 {info['self_size']:,}")
    print(f"  类型 {len(info['types'])} · 条目 {len(info['entries'])}")
    print("  资源：" + " · ".join(f"{k} {v}" for k, v in sorted(info["type_counts"].items())))
    if info.get("needs_gpu") or info.get("needs_stream"):
        parts = []
        if info.get("needs_gpu"):
            parts.append(f".gpu_resources {info['gpu_file_size']:,}"
                         + ("" if info.get("gpu_path") else "（缺）"))
        if info.get("needs_stream"):
            parts.append(f".stream {info['stream_file_size']:,}"
                         + ("" if info.get("stream_path") else "（缺）"))
        print("  伴生：" + " · ".join(parts))
    big = sorted(info["entries"], key=lambda e: e["toc_size"], reverse=True)[:5]
    if big:
        print("  最大条目：")
        for e in big:
            print(f"    {type_name(e['type_id']):14} 0x{e['file_id']:016X}  {e['toc_size']:,} 字节")


# ---------------------------------------------------------------- 环境探测

def _steam_roots() -> list:
    roots = []
    if os.name == "nt":
        try:
            import winreg
            for hive, key, name in (
                (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
            ):
                try:
                    with winreg.OpenKey(hive, key) as k:
                        p = Path(winreg.QueryValueEx(k, name)[0])
                        if p.is_dir():
                            roots.append(p)
                except OSError:
                    pass
        except ImportError:
            pass
    for guess in ("C:/Program Files (x86)/Steam", "C:/Program Files/Steam",
                  "D:/Steam", "E:/Steam", "F:/Steam"):
        p = Path(guess)
        if p.is_dir():
            roots.append(p)
    seen, uniq = set(), []
    for p in roots:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def _library_dirs(steam: Path) -> list:
    out = [steam]
    vdf = steam / "steamapps" / "libraryfolders.vdf"
    if vdf.is_file():
        try:
            text = vdf.read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(r'"path"\s*"([^"]+)"', text):
                p = Path(m.group(1).replace("\\\\", "\\"))
                if p.is_dir() and p not in out:
                    out.append(p)
        except OSError:
            pass
    return out


def find_game():
    cfg = read_json(CONFIG_FILE, {}) or {}
    for cand in (os.environ.get("HD2_GAME"), cfg.get("game_dir")):
        if cand and (Path(cand) / "data" / "game").is_dir():
            return Path(cand)
    for steam in _steam_roots():
        for lib in _library_dirs(steam):
            p = lib / "steamapps" / "common" / "Helldivers 2"
            if (p / "data" / "game").is_dir():
                return p
    return None


def game_build(game: Path):
    acf = game.parent.parent / "appmanifest_553850.acf"
    if acf.is_file():
        m = re.search(r'"buildid"\s*"(\d+)"',
                      acf.read_text(encoding="utf-8", errors="replace"))
        if m:
            return m.group(1)
    return None


def find_library(game):
    # 环境变量优先级高于缓存：临时改库、多库切换都靠它
    for cand in (os.environ.get("HD2_LIB"), (read_json(CONFIG_FILE, {}) or {}).get("library_dir")):
        if cand:
            return Path(cand)
    if game:
        p = Path(game.drive + "\\") / "HD2 Mods"
        if p.is_dir():
            return p
    for guess in ("D:/HD2 Mods", "E:/HD2 Mods", "C:/HD2 Mods"):
        p = Path(guess)
        if p.is_dir():
            return p
    return None


def find_manager() -> dict:
    info = {"cli": shutil.which("hd2qd"), "home": None, "gui": None}
    up = Path(os.environ.get("USERPROFILE") or Path.home())
    home = up / ".hd2-mod-cli"
    if (home / "library.json").is_file():
        info["home"] = home
    p = up / "Desktop" / "HD2 Mod Quick Deploy.exe"
    if p.is_file():
        info["gui"] = p
    else:
        p = up / "Desktop" / "HD2.Mod.Quick.Deploy.exe"
        if p.is_file():
            info["gui"] = p
    return info


def loader_report(manager_home) -> list:
    if not manager_home:
        return []
    lib = read_json(manager_home / "library.json", {}) or {}
    rows, seen = [], set()
    for m in lib.get("mods", []):
        low = ((m.get("name") or "") + " " + (m.get("path") or "")).lower()
        for key, label in (("mdl3", "MDL3"), ("chef", "Chef"),
                           ("boot mod loader", "BML"), ("bingus", "Bingus")):
            if key in low:
                state = "启用" if m.get("enabled") else "停用"
                if (label, state) not in seen:
                    seen.add((label, state))
                    rows.append((label, state))
                break
    return rows


def load_config() -> dict:
    return read_json(CONFIG_FILE, {}) or {}


def save_config(cfg: dict) -> None:
    write_json(CONFIG_FILE, cfg)


def resolve_paths() -> dict:
    game = find_game()
    lib = find_library(game)
    if game:
        cfg = load_config()
        changed = False
        if cfg.get("game_dir") != str(game):
            cfg["game_dir"] = str(game); changed = True
        if lib and cfg.get("library_dir") != str(lib):
            cfg["library_dir"] = str(lib); changed = True
        if changed:
            save_config(cfg)
    return {"game": game, "library": lib, "manager": find_manager(),
            "build": game_build(game) if game else None}


def find_blender():
    cfg = load_config()
    cands = []
    for cand in (os.environ.get("HD2_BLENDER"), cfg.get("blender_exe")):
        if cand and Path(cand).is_file():
            cands.append(Path(cand))
    which = shutil.which("blender")
    if which:
        cands.append(Path(which))
    patterns = [
        "C:/Program Files/Blender Foundation/Blender */blender.exe",
        "D:/Program Files/Blender Foundation/Blender */blender.exe",
        "E:/Program Files/Blender Foundation/Blender */blender.exe",
        str(Path(os.environ.get("LOCALAPPDATA") or "") /
            "Programs/Blender Foundation/Blender */blender.exe"),
        "C:/Program Files/Steam/steamapps/common/Blender/blender.exe",
    ]
    for pat in patterns:
        try:
            cands.extend(Path(p) for p in glob.glob(pat))
        except Exception:
            pass
    seen, uniq = set(), []
    for p in cands:
        try:
            rp = p.resolve()
        except OSError:
            continue
        if rp not in seen and rp.is_file():
            seen.add(rp)
            uniq.append(rp)
    # 目录名里带版本号，按字符串倒序基本能把新版本排前面
    uniq.sort(key=lambda p: str(p).lower(), reverse=True)
    return uniq[0] if uniq else None


def blender_version(exe):
    if not exe:
        return None
    try:
        r = subprocess.run([str(exe), "--version"], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=8)
        m = re.search(r"Blender\s+(\d+\.\d+(?:\.\d+)?)", (r.stdout or "") + (r.stderr or ""))
        if m:
            return m.group(1)
    except Exception:
        pass
    m = re.search(r"Blender\s+(\d+\.\d+)", str(exe))
    return m.group(1) if m else None


def _sdk_dirs():
    cfg = load_config()
    cands = []
    for cand in (os.environ.get("HD2_SDK"), cfg.get("sdk_dir")):
        if cand:
            cands.append(Path(cand))
    appdata = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    base = appdata / "Blender Foundation" / "Blender"
    if base.is_dir():
        for ver in base.iterdir():
            if not ver.is_dir():
                continue
            for pat in ("scripts/addons/*", "extensions/*/*", "extensions/*"):
                try:
                    cands.extend(ver.glob(pat))
                except OSError:
                    pass
    docs = Path(os.environ.get("USERPROFILE") or Path.home()) / "Documents" / "Blender"
    if docs.is_dir():
        for pat in ("*/scripts/addons/*", "*/extensions/*/*"):
            try:
                cands.extend(docs.glob(pat))
            except OSError:
                pass
    out, seen = [], set()
    for p in cands:
        try:
            rp = p.resolve()
        except OSError:
            continue
        if rp in seen or not rp.is_dir():
            continue
        name = rp.name.lower()
        if any(k in name for k in ("hd2sdk", "helldivers2", "io_scene_helldivers2")):
            seen.add(rp)
            out.append(rp)
    # CE 优先于 AQ
    out.sort(key=lambda p: (("aq" in p.name.lower()), str(p).lower()))
    return out


def find_sdk():
    for p in _sdk_dirs():
        if (p / "hashlists" / "archivehashes.json").is_file() or (p / "__init__.py").is_file():
            return p
    return None


def sdk_version(sdk):
    if not sdk:
        return None
    for name in ("blender_manifest.toml", "version.py", "__init__.py"):
        p = Path(sdk) / name
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if name == "blender_manifest.toml":
            m = re.search(r'^\s*version\s*=\s*"([^"]+)"', text, re.M)
            if m:
                return m.group(1)
        m = re.search(r'__version__\s*=\s*["\']([^"\']+)', text)
        if m:
            return m.group(1)
        m = re.search(r'"version"\s*:\s*\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)\)', text)
        if m:
            return ".".join(m.groups())
    return "?"


def game_running():
    """游戏是否在运行。用字节匹配，避开中文 Windows 的 tasklist 编码问题。"""
    try:
        if os.name == "nt":
            r = subprocess.run(["tasklist", "/NH"], capture_output=True, timeout=10)
            return b"helldivers2.exe" in (r.stdout or b"").lower()
        r = subprocess.run(["pgrep", "-f", "helldivers2"], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def game_patch_stats(game):
    if not game:
        return 0, 0
    data = Path(game) / "data"
    if not data.is_dir():
        return 0, 0
    files = [p for p in data.iterdir() if p.is_file() and ARCHIVE_PATCH_RE.match(p.name)]
    return len(files), sum(p.stat().st_size for p in files)


# ---------------------------------------------------------------- doctor

def cmd_doctor(args):
    paths = resolve_paths()
    game, lib, mgr, build = paths["game"], paths["library"], paths["manager"], paths["build"]

    if game:
        ok(f"游戏目录   {pretty(game)}")
        if build:
            ok(f"游戏 build {build}")
        else:
            warn("找不到 buildid（appmanifest_553850.acf），不影响打包")
        if (game / "EasyAntiCheat").is_dir():
            ok("反作弊     EAC 已就位（10-20 之后的新常态）")
        if game_running():
            warn("游戏正在运行：部署/写 patch 前必须退出")
        n, total = game_patch_stats(game)
        if n:
            print(f"[ -- ] data patch {n} 个（共 {human_size(total)}）；SDK Write Patch 会改写它们，先备份/清场")
    else:
        bad("找不到游戏目录。用 doctor 的同级命令：set-game <路径>")

    if lib:
        same = game and lib.drive.lower() == game.drive.lower()
        ok(f"mod 库     {pretty(lib)}" + ("（与游戏同盘，部署走硬链接）" if same else "（异盘，部署走复制）"))
    else:
        warn("找不到 mod 库；build 后手动导入管理器即可")

    if mgr["cli"]:
        ok(f"管理器 CLI {pretty(mgr['cli'])}")
    elif mgr["home"]:
        ok(f"管理器数据 {pretty(mgr['home'])}（GUI 模式，CLI 未进 PATH）")
    elif mgr["gui"]:
        warn(f"只找到 GUI：{pretty(mgr['gui'])}（可能还没部署过）")
    else:
        warn("没找到 hd2-mod-cli；用 Arsenal / Echelon 导入 dist/ 也行")

    for label, state in loader_report(mgr["home"]):
        (ok if state == "启用" else warn)(f"加载器     {label}：{state}")

    blender = find_blender()
    if blender:
        bv = blender_version(blender)
        ok(f"Blender    {bv or '?'}  {pretty(blender)}")
    else:
        print("[ -- ] Blender    未找到（只有模型/贴图路线需要）")

    sdk = find_sdk()
    if sdk:
        ok(f"HD2SDK     {sdk_version(sdk)}  {pretty(sdk)}")
    else:
        print("[ -- ] HD2SDK     未找到（模型/贴图路线需要；用 set-sdk <路径> 指定）")

    if blender and sdk:
        ok("模型路线   就绪（Blender + HD2SDK）")
    elif game:
        print("[ -- ] 模型路线   还差 Blender 或 HD2SDK；Lua 路线不受影响")

    srkit = os.environ.get("HD2_SRKIT")
    if srkit and Path(srkit, "srkit").is_dir():
        ok(f"srkit      {srkit}（仅资源替换路线需要）")
    else:
        print("[ -- ] srkit      未配置（Lua / 模型路线都不需要）")

    print()
    if game:
        print("体检通过。Lua：new → 改 src/main.lua → build → check → install")
        print("        模型：lookup → new --kind model → （Blender）→ adopt → build → check → install")
    else:
        print("先补上标 [FAIL] 的项，再开工。")
    return 0 if game else 1


def cmd_setgame(args):
    p = Path(args.path)
    if not (p / "data" / "game").is_dir():
        die(f"{p} 不像游戏根目录（应含 data/game）")
    cfg = load_config(); cfg["game_dir"] = str(p); save_config(cfg)
    ok(f"已记住游戏目录：{p}")


def cmd_setlib(args):
    p = Path(args.path)
    p.mkdir(parents=True, exist_ok=True)
    cfg = load_config(); cfg["library_dir"] = str(p); save_config(cfg)
    ok(f"已记住 mod 库：{p}")


def cmd_setsdk(args):
    p = Path(args.path)
    if not ((p / "hashlists").is_dir() or (p / "__init__.py").is_file()):
        die(f"{p} 不像 HD2SDK 插件目录（应含 hashlists/ 或 __init__.py）")
    cfg = load_config(); cfg["sdk_dir"] = str(p); save_config(cfg)
    ok(f"已记住 HD2SDK：{p}（版本 {sdk_version(p)}）")


# ---------------------------------------------------------------- Lua 扫描

def strip_lua(src: str) -> str:
    out = list(src)
    i, n = 0, len(src)

    def blank(a, b):
        for k in range(a, min(b, n)):
            if out[k] != "\n":
                out[k] = " "

    while i < n:
        c = src[i]
        if src.startswith("--", i):
            m = re.match(r"--\[(=*)\[", src[i:])
            if m:
                close = "]" + m.group(1) + "]"
                end = src.find(close, i + len(m.group(0)))
                end = n if end < 0 else end + len(close)
                blank(i, end); i = end; continue
            end = src.find("\n", i)
            end = n if end < 0 else end
            blank(i, end); i = end; continue
        if c == "[":
            m = re.match(r"\[(=*)\[", src[i:])
            if m:
                close = "]" + m.group(1) + "]"
                end = src.find(close, i + len(m.group(0)))
                end = n if end < 0 else end + len(close)
                blank(i, end); i = end; continue
        if c in "'\"":
            j = i + 1
            while j < n:
                if src[j] == "\\":
                    j += 2; continue
                if src[j] == c:
                    j += 1; break
                j += 1
            blank(i, j); i = j; continue
        i += 1
    return "".join(out)


FORBIDDEN = [
    (r"\bffi\b", "ffi：脚本层没有这个库。读数据请走 MDL3 的 HD2Data"),
    (r"\bbit\s*\.", "bit 库：已被移除"),
    (r"\bjit\s*\.", "jit 库：已被移除"),
    (r"\bgoto\b", "goto：PUC 5.1 不支持（5.2+ 语法）"),
    (r"::\s*[A-Za-z_]\w*\s*::", "标签 ::label::：PUC 5.1 不支持"),
    (r"//", "整除 //：Lua 5.3+ 语法，改用 math.floor(a/b)"),
    (r"<<|>>", "位移运算：5.3+ 语法"),
    (r"(?<![&])&(?![&])", "位与 &：5.3+ 语法"),
    (r"\|", "位或 |：5.3+ 语法"),
    (r"[^~]~(?!=)", "按位取反 ~：5.3+ 语法（~= 不算）"),
    (r"\\z", "\\z 转义：5.2+ 语法"),
    (r"\\u\{", "\\u{} 转义：5.3+ 语法"),
]


def lint_lua(text: str):
    issues = []
    code = strip_lua(text)
    raw = text.splitlines()
    for idx, line in enumerate(code.splitlines(), 1):
        for pattern, desc in FORBIDDEN:
            if re.search(pattern, line):
                issues.append((idx, desc, raw[idx - 1].strip()[:100]))
    return issues


# ---------------------------------------------------------------- new

SCRIPT_TEMPLATE = """-- HD2-Addon: {module}
-- {title}
-- 运行时：PUC Lua 5.1（无 ffi / bit / jit / goto）
-- 契约：on_enable(context) / on_update(context, dt) / on_disable()

local M = {{}}

local ctx = nil
local state = nil

local function engine()
    local sr = rawget(_G, "stingray")
    if type(sr) ~= "table" then return nil end
    return sr
end

local function hub()
    local D = rawget(_G, "HD2Data")
    if type(D) == "table" and D.ready() then return D end
    return nil
end

local function say(msg)
    if ctx and type(ctx.log) == "function" then pcall(ctx.log, tostring(msg)) end
end

function M.on_enable(context)
    ctx = context
    ctx.settings = ctx.settings or {{}}
    state = {{ frames = 0 }}
    say("ENABLED")
end

function M.on_update(context, dt)
    if not ctx or not state then return end
    if type(dt) ~= "number" or dt <= 0 or dt > 1 then return end
    state.frames = state.frames + 1

    local sr = engine()
    if not sr then return end
    -- 玩法逻辑写这里。取值前先判：sr.Unit.alive(u) / if not v then return end
end

function M.on_disable()
    state = nil
    ctx = nil
end

function M.diagnostics()
    return {{ frames = state and state.frames or 0 }}
end

return M
"""


def cmd_new(args):
    kind = (args.kind or "lua").lower()
    out = Path(args.out)
    if (out / "manifest.json").exists():
        die(f"{out} 已存在 manifest.json，拒绝覆盖")

    if kind == "lua":
        author, name = (args.author or "").strip().lower(), (args.name or "").strip().lower()
        for v, what in ((author, "--author"), (name, "--name")):
            if not re.fullmatch(r"[a-z0-9_]+", v):
                die(f"{what} 只能用小写字母/数字/下划线（会进模块路径与哈希）")
        module = f"mods/{author}/{name}"
        (out / "src").mkdir(parents=True, exist_ok=True)
        (out / "assets").mkdir(exist_ok=True)
        identity = murmur64(module)

        write_json(out / "manifest.json", {
            "Version": 1,
            "Guid": str(uuid.uuid4()),
            "Name": f"{args.title} v0.1.0",
            "Description": f"玩法 MOD。模块路径 {module}。"
                           + ("需要 MDL3 3.0.0-dev.36+。" if args.target == "mdl3" else "无需额外加载器。"),
            "IconPath": "cover.jpg",
            "Options": [{"Name": "核心 / Core（必选）", "Description": "玩法脚本主体",
                         "Include": [args.option]}],
        })
        write_json(out / "mod.project.json", {
            "kind": "lua", "module": module, "option": args.option,
            "script": "src/main.lua", "target": args.target,
        })
        (out / "src" / "main.lua").write_text(
            SCRIPT_TEMPLATE.format(module=module, title=args.title), encoding="utf-8", newline="\n")
        (out / "CHANGELOG.md").write_text("# CHANGELOG\n\n## v0.1.0\n- 初始骨架\n",
                                          encoding="utf-8", newline="\n")
        (out / "README.md").write_text(
            f"# {args.title}\n\n## 依赖\n- "
            + ("需要 MDL3 3.0.0-dev.36+（官方发布页：<填链接>）" if args.target == "mdl3" else "无")
            + "\n\n## 兼容性\n- 验证 build：<填 build 号>\n- 加载器：<填>\n\n"
              "## 已知问题\n- 暂无\n\n## 卸载\n停用并重新部署即可，不写入任何用户目录。\n",
            encoding="utf-8", newline="\n")

        ok(f"工程已建：{out}")
        print(f"       模块路径 : {module}")
        print(f"       资源 ID  : 0x{identity:016X}")
        print("       下一步   : 改 src/main.lua → build")
        return

    if kind == "model":
        subject = args.subject or args.title
        target_kind = (args.target_kind or "armor").lower()
        label = "贴图/材质替换 MOD" if target_kind == "texture" else "模型替换 MOD"
        (out / "patches").mkdir(parents=True, exist_ok=True)
        (out / "assets").mkdir(exist_ok=True)
        write_json(out / "manifest.json", {
            "Version": 1,
            "Guid": str(uuid.uuid4()),
            "Name": f"{args.title} v0.1.0",
            "Description": f"{label}：{subject}。安装不需要加载器；用管理器部署后重启游戏。",
            "IconPath": "cover.jpg",
            "Options": [{"Name": "核心 / Core（必选）", "Description": "模型 / 材质 / 贴图补丁",
                         "Include": [args.option]}],
        })
        write_json(out / "mod.project.json", {
            "kind": "model", "option": args.option, "patches_dir": "patches",
            "subject": subject, "target_kind": target_kind,
        })
        (out / "README.md").write_text(
            f"# {args.title}\n\n## 依赖\n"
            "- 安装：不需要 MDL3 / 加载器；用 mod 管理器部署后重启游戏。\n"
            "- 制作：Blender + HD2SDK（Community Edition 3.11.x）。\n\n"
            f"## 兼容性\n- 验证 build：<填 build 号>\n- 目标：{subject}\n"
            f"- 类型：{target_kind}\n- 体型：<Brawny / Lean / 两者>\n\n"
            "## 已知问题\n- <填>\n\n## 卸载\n管理器禁用/删除后重新部署；不写入任何用户目录。\n",
            encoding="utf-8", newline="\n")
        (out / "CHANGELOG.md").write_text("# CHANGELOG\n\n## v0.1.0\n- 初始骨架\n",
                                          encoding="utf-8", newline="\n")
        if target_kind == "weapon":
            plan_text = f"""# {args.title} · 武器制作计划

## 立项卡
- 目标武器：{subject}
- 目标 archive：<用 `hd2mod.py lookup "{subject}"` 填>
- 模型来源：<FBX/OBJ/GLB 路径>
- 做到哪一层：<L1 外观 / L2 功能件 / L3 完整>
- LOD：<Auto LODs / 逐层>
- 配件：<无 / 瞄具 / 下挂 / 弹匣>
- 验收：<右手握持、开火不穿模、第一/第三人称、枪口火光不歪>

## 闸门
- [ ] 素材预检通过（`tools/blender_preflight.py --target weapon`）
- [ ] SDK 导入目标 unit，确认 archive 正确
- [ ] 对齐握把 + 试装（只保存 unit）
- [ ] 绑 `boss` / 原版顶点组；需要时调 `attach_*` 骨骼
- [ ] 材质 + LOD（Auto LODs 或逐层）
- [ ] Save Units → Write Patch → Export Patch
- [ ] `hd2mod.py adopt` → `build` → `check`
- [ ] `install` → 进游戏验收（握持 / 开火 / 第一人称 / 第三人称 / LOD）

## 已知风险
- <枪浮空 / 枪托穿模 / 枪机不动 / 瞄具歪 / 弹匣穿模 / 版权>
"""
        else:
            plan_text = f"""# {args.title} · 制作计划

## 立项卡
- 目标装备：{subject}
- 目标 archive：<用 `hd2mod.py lookup "{subject}"` 填>
- 替换范围：<整套 / 仅胸甲 / 头盔 / 贴图>
- 目标类型：{target_kind}
- 模型来源：<FBX/OBJ/GLB 路径；或“现有 mod 改目标”>
- 体型：<Brawny / Lean / 两者>
- 验收：<进游戏看到什么变化；哪几个动作不能穿模>

## 闸门
- [ ] 素材预检通过（`tools/blender_preflight.py`）
- [ ] SDK 导入目标 unit，确认 archive 正确
- [ ] 对齐 A-Pose / 切分 / 权重 / 材质
- [ ] Save Units → Write Patch → Export Patch
- [ ] `hd2mod.py adopt` → `build` → `check`
- [ ] `install` → 进游戏验收（装备界面 / 第一人称 / 第三人称 / LOD）

## 已知风险
- <只支持一种体型 / 没有骨骼 / 材质槽不够 / 版权限制>
"""
        (out / "PLAN.md").write_text(plan_text, encoding="utf-8", newline="\n")

        ok(f"模型工程已建：{out}")
        print(f"       目标     : {subject}（{target_kind}）")
        print("       下一步   : 先跑 lookup 找 archive → 在 Blender 里做 → 回来 adopt")
        return

    die(f"未知 kind：{kind}（支持 lua / model）")


# ---------------------------------------------------------------- build

def _dist_path(proj: Path, manifest: dict) -> Path:
    dist_name = re.sub(r"[^\w\-.]+", "_", manifest.get("Name", "mod")).strip("_") or "mod"
    return proj / "dist" / dist_name


def _copy_common(proj: Path, dist: Path) -> None:
    for extra in ("manifest.json", "README.md", "CHANGELOG.md", "THIRD_PARTY.md"):
        if (proj / extra).is_file():
            shutil.copy2(proj / extra, dist / extra)
    cover = proj / "assets" / "cover.jpg"
    if cover.is_file():
        shutil.copy2(cover, dist / "cover.jpg")


def _zip_dist(proj: Path, dist: Path) -> Path:
    zp = proj / "dist" / f"{dist.name}.zip"
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(dist.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(dist))
    return zp


def build_lua_project(proj: Path, manifest: dict, project: dict, args) -> None:
    module = project["module"]
    if not MODULE_RE.match(module):
        die(f"module 不合规：{module}")
    option = project.get("option", "Core")
    if not any(option in (o.get("Include") or []) for o in manifest.get("Options", [])):
        die(f"manifest.Options 里没有包含 {option} 的项")

    src = proj / project.get("script", "src/main.lua")
    if not src.is_file():
        die(f"找不到脚本：{src}")
    raw = src.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        die("脚本带 UTF-8 BOM，PUC 5.1 会编译失败")
    if raw.startswith(b"\x1bLJ"):
        die("脚本是 LuaJIT 字节码，本版本无法加载")
    text = raw.decode("utf-8")
    first = text.splitlines()[0].strip() if text else ""
    if first != f"-- HD2-Addon: {module}":
        die(f"首行声明与模块路径不一致\n  期望：-- HD2-Addon: {module}\n  实际：{first or '(空)'}")

    identity = murmur64(module)
    blob = build_lua_patch(identity, raw)

    dist_root = proj / "dist"
    if dist_root.exists():
        shutil.rmtree(dist_root)
    dist = _dist_path(proj, manifest)
    (dist / option).mkdir(parents=True, exist_ok=True)
    (dist / option / PATCH_NAME).write_bytes(blob)
    _copy_common(proj, dist)

    ok(f"打包完成：{dist / option / PATCH_NAME}  ({len(blob)} 字节)")
    print(f"       资源 ID : 0x{identity:016X}   模块 {module}")
    if args.zip:
        zp = _zip_dist(proj, dist)
        ok(f"已打 zip：{zp}")
    print("       下一步：check → install")


def build_model_project(proj: Path, manifest: dict, project: dict, args) -> None:
    patches_dir = proj / project.get("patches_dir", "patches")
    flat_files = iter_patch_files(patches_dir)
    options = manifest.get("Options", [])
    if not options:
        die("manifest.Options 为空，不知道要打包哪个文件夹")

    # 先校验所有来源，避免打一半才发现坏包
    includes = _manifest_includes(options)
    flat_ok = bool(flat_files) and len(options) == 1 and len(includes) == 1
    plan = []  # (include, files)
    for inc in includes:
        src_dir = patches_dir / inc
        if src_dir.is_dir():
            files = iter_patch_files(src_dir)
        elif flat_ok:
            files = flat_files
        else:
            die(f"缺少 option「{inc}」的 patch。\n"
                f"       把 SDK 导出收编到 {patches_dir / inc}/，或加 --option {inc}")
        if not files:
            die(f"{src_dir if src_dir.is_dir() else patches_dir} 里没有 patch。\n"
                "       先在 Blender 里 Save Units → Write Patch → Export Patch，\n"
                "       再运行：hd2mod.py adopt <工程> --from <导出zip或文件夹>")
        for f in files:
            info, errs, warns = check_patch_file(f)
            if errs:
                for e in errs:
                    bad(e)
                die(f"{f.name} 不合格，未打包")
            for w in warns:
                warn(w)
        groups = group_patches(files)
        for archive, items in groups.items():
            nums = [n for n, _ in items]
            if len(set(nums)) != len(nums):
                die(f"archive {archive} 有重复的 patch 编号：{sorted(nums)}")
        plan.append((inc, files))

    dist_root = proj / "dist"
    if dist_root.exists():
        shutil.rmtree(dist_root)
    dist = _dist_path(proj, manifest)

    total_files = 0
    total_bytes = 0
    for inc, files in plan:
        outdir = dist / inc
        outdir.mkdir(parents=True, exist_ok=True)
        groups = group_patches(files)
        for archive, items in sorted(groups.items()):
            for idx, (num, src) in enumerate(sorted(items, key=lambda x: x[0])):
                dst = outdir / f"{archive}.patch_{idx}"
                shutil.copy2(src, dst)
                total_files += 1
                total_bytes += dst.stat().st_size
                for suffix in (".stream", ".gpu_resources"):
                    side = src.with_name(src.name + suffix)
                    if side.is_file():
                        shutil.copy2(side, dst.with_name(dst.name + suffix))
    _copy_common(proj, dist)

    ok(f"打包完成：{dist}  ({total_files} 个 patch，{human_size(total_bytes)})")
    for inc, files in plan:
        print(f"       {inc}: {len(files)} 个 patch")
    if args.zip:
        zp = _zip_dist(proj, dist)
        ok(f"已打 zip：{zp}")
    print("       下一步：check → install")


def cmd_build(args):
    proj = Path(args.project).resolve()
    manifest = read_json(proj / "manifest.json")
    project = read_json(proj / "mod.project.json")
    if not manifest or not project:
        die(f"{proj} 不是合法工程（缺 manifest.json 或 mod.project.json）")
    kind = project.get("kind", "lua")
    if kind == "lua":
        build_lua_project(proj, manifest, project, args)
    elif kind == "model":
        build_model_project(proj, manifest, project, args)
    else:
        die(f"未知工程类型：{kind}")


# ---------------------------------------------------------------- check

def _manifest_includes(options) -> list:
    """递归收集 Options / SubOptions 的 Include（去重、保序）。"""
    out = []
    for o in options or []:
        for inc in o.get("Include") or []:
            if inc not in out:
                out.append(inc)
        for sub in o.get("SubOptions") or []:
            for inc in sub.get("Include") or []:
                if inc not in out:
                    out.append(inc)
    return out


def check_manifest_fields(manifest: dict, errors: list, warns: list) -> None:
    if not GUID_RE.match(str(manifest.get("Guid", ""))):
        errors.append(f"manifest.Guid 不是合法 UUID：{manifest.get('Guid')!r}")
    if not str(manifest.get("Name", "")).strip():
        errors.append("manifest.Name 为空")
    version = manifest.get("Version")
    if not (isinstance(version, int) or (isinstance(version, str) and version.strip() == "1")):
        errors.append("manifest.Version 必须是 1（manifest 语法版本，不是 mod 版本号）")
    if not manifest.get("Options"):
        errors.append("manifest.Options 为空，管理器不会部署任何文件")
    for o in manifest.get("Options", []):
        if not o.get("Include"):
            errors.append(f"选项 {o.get('Name')!r} 没有 Include")
    icon = manifest.get("IconPath")
    if icon and not str(icon).strip():
        warns.append("manifest.IconPath 是空字符串")


def check_lua_project(proj: Path, manifest: dict, project: dict) -> None:
    fails, warns = [], []
    check_manifest_fields(manifest, fails, warns)
    module = project["module"]

    if not MODULE_RE.match(module):
        fails.append(f"模块路径不合规：{module}")
    identity = murmur64(module) if MODULE_RE.match(module) else 0

    src = proj / project.get("script", "src/main.lua")
    if src.is_file():
        raw = src.read_bytes()
        text = raw.decode("utf-8", "replace")
        first = text.splitlines()[0].strip() if text else ""
        if first != f"-- HD2-Addon: {module}":
            fails.append(f"首行声明不匹配：{first or '(空)'}")
        if len(raw) > 4 * 1024 * 1024:
            fails.append(f"脚本 {len(raw)} 字节，超过 Chef 的 4 MB 上限")
        issues = lint_lua(text)
        if issues:
            fails.append(f"Lua 5.1 兼容性：{len(issues)} 处")
            for ln, desc, snip in issues[:10]:
                fails.append(f"        L{ln}: {desc}  |  {snip}")

    dist_root = proj / "dist"
    patches = sorted(p for p in dist_root.rglob("*.patch_*") if p.is_file()) if dist_root.exists() else []
    if not patches:
        warns.append("还没有 build 产物")
    else:
        if len(patches) > MAX_PATCHES:
            fails.append(f"patch 文件 {len(patches)} 个，超过 MDL3 的 {MAX_PATCHES} 上限")
        for p in patches:
            try:
                info = parse_lua_patch(p.read_bytes())
            except Exception as e:
                fails.append(f"{p.name} 解析失败：{e}")
                continue
            if info["file_id"] != identity:
                fails.append(f"{p.name} 资源 ID 0x{info['file_id']:016X} ≠ murmur64(module) 0x{identity:016X}")
            if info["self_size"] != info["actual_size"]:
                fails.append(f"{p.name} 头部自记长度 {info['self_size']} ≠ 实际 {info['actual_size']}")
            if info["declared_payload"] != len(info["script"]):
                fails.append(f"{p.name} payload 长度声明不一致")

    print()
    for w in warns:
        warn(w)
    if fails:
        for f in fails:
            bad(f)
        print(f"\n门禁未通过：{len(fails)} 项失败")
        raise SystemExit(1)
    ok(f"门禁通过：{module}  (0x{identity:016X})")
    if patches:
        ok(f"产物 {len(patches)} 个，ID / 长度 / payload 全部自洽")


def _check_option_patches(folder: Path, errors: list, warns: list) -> list:
    files = iter_patch_files(folder)
    if not files:
        errors.append(f"{folder} 里没有 patch")
        return []
    infos = []
    for f in files:
        info, errs, ws = check_patch_file(f)
        if errs:
            errors.extend(errs)
            continue
        warns.extend(ws)
        info["path"] = f
        infos.append(info)

    groups = group_patches(files)
    for archive, items in groups.items():
        nums = sorted(n for n, _ in items)
        if nums != list(range(len(nums))):
            warns.append(f"{folder.name}/{archive}: patch 编号不是从 0 连续（{nums}）；build 会重排")

    seen = {}
    for info in infos:
        for e in info["entries"]:
            key = (e["type_id"], e["file_id"])
            if key in seen:
                warns.append(
                    f"资源重复：{type_name(e['type_id'])} 0x{e['file_id']:016X} "
                    f"同时出现在 {seen[key]} 和 {info['path'].name}（后加载者赢）")
            else:
                seen[key] = info["path"].name
    return infos


def check_model_project(proj: Path, manifest: dict, project: dict) -> None:
    fails, warns = [], []
    check_manifest_fields(manifest, fails, warns)
    target_kind = (project.get("target_kind") or "armor").lower()

    patches_dir = proj / project.get("patches_dir", "patches")
    options = manifest.get("Options", [])
    includes = _manifest_includes(options)
    source_infos = []
    if patches_dir.is_dir():
        subdirs = [patches_dir / inc for inc in includes if (patches_dir / inc).is_dir()]
        if subdirs:
            for inc in includes:
                d = patches_dir / inc
                if d.is_dir():
                    source_infos.extend(_check_option_patches(d, fails, warns))
                else:
                    fails.append(f"缺少 option「{inc}」的来源目录：{d}")
        else:
            source_infos = _check_option_patches(patches_dir, fails, warns)
            if len(includes) > 1:
                fails.append("多个 Include 但 patches/ 是扁平结构；请改成 patches/<Include>/ 子目录")
    if not source_infos and not fails:
        fails.append(f"{patches_dir} 里没有 patch")

    dist_root = proj / "dist"
    dist_infos = []
    if dist_root.exists():
        bundles = [d for d in dist_root.iterdir() if d.is_dir()]
        if not bundles:
            warns.append("dist/ 里没有可导入的文件夹")
        else:
            bundle = bundles[0]
            for inc in includes:
                folder = bundle / inc
                if not folder.is_dir():
                    fails.append(f"Include「{inc}」在 dist 里不存在")
                    continue
                dist_infos.extend(_check_option_patches(folder, fails, warns))
    else:
        warns.append("还没有 build 产物")

    infos = dist_infos or source_infos
    if infos:
        units = sum(i["unit_count"] for i in infos)
        mats = sum(i["type_counts"].get("material", 0) for i in infos)
        texs = sum(i["type_counts"].get("texture", 0) for i in infos)
        print(f"\n资源统计：unit {units} · material {mats} · texture {texs} · patch {len(infos)}")
        if units == 0 and target_kind in ("armor", "helmet", "weapon", "prop"):
            fails.append(f"没有任何 unit 资源；target_kind={target_kind} 但看起来不是模型替换包")
        if target_kind in ("armor", "helmet", "weapon", "prop"):
            if mats == 0:
                warns.append("没有 material 资源：游戏里可能显示灰模/默认材质")
            if texs == 0:
                warns.append("没有 texture 资源：确认是否复用了原版材质，否则贴图会缺")
        if len(infos) > MAX_PATCHES:
            warns.append(f"patch 数量 {len(infos)} 超过 {MAX_PATCHES}；资源 mod 不走 MDL3，但部署会变慢")

    readme = (proj / "README.md")
    if readme.is_file():
        text = readme.read_text(encoding="utf-8", errors="replace")
        if "<填" in text:
            warns.append("README 里还有 <填...> 占位符，发布前补齐")
    plan = proj / "PLAN.md"
    if plan.is_file():
        text = plan.read_text(encoding="utf-8", errors="replace")
        if "<用 `hd2mod.py lookup" in text or "<FBX" in text:
            warns.append("PLAN.md 的立项卡还没填完")

    print()
    for w in warns:
        warn(w)
    if fails:
        for f in fails:
            bad(f)
        print(f"\n门禁未通过：{len(fails)} 项失败")
        raise SystemExit(1)
    ok(f"门禁通过：模型工程  ({len(infos)} 个 patch)")


def cmd_check(args):
    proj = Path(args.project).resolve()
    manifest = read_json(proj / "manifest.json")
    project = read_json(proj / "mod.project.json")
    if not manifest or not project:
        die("不是合法工程")
    kind = project.get("kind", "lua")
    if kind == "lua":
        check_lua_project(proj, manifest, project)
    elif kind == "model":
        check_model_project(proj, manifest, project)
    else:
        die(f"未知工程类型：{kind}")


# ---------------------------------------------------------------- adopt

def _allowed_zip_member(name: str) -> bool:
    base = Path(name.replace("\\", "/")).name
    return bool(ARCHIVE_PATCH_RE.match(base)) or base.endswith(".stream") \
        or base.endswith(".gpu_resources")


def _extract_patch_zip(zip_path: Path, outdir: Path) -> list:
    outdir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            if info.is_dir() or not _allowed_zip_member(info.filename):
                continue
            rel = Path(info.filename.replace("\\", "/"))
            if rel.is_absolute() or ".." in rel.parts:
                continue
            target = outdir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(info))
    return iter_patch_files(outdir)


def cmd_adopt(args):
    proj = Path(args.project).resolve()
    project = read_json(proj / "mod.project.json")
    if not project:
        die(f"{proj} 不是合法工程")
    if project.get("kind", "lua") != "model":
        die("adopt 只用于模型/贴图工程（kind=model）")

    src = Path(args.source)
    if not src.exists():
        die(f"来源不存在：{src}")

    tmp = None
    try:
        if src.is_dir():
            root = src
            files = iter_patch_files(root)
            rel_base = root
        elif src.suffix.lower() == ".zip":
            tmp = Path(tempfile.mkdtemp(prefix="hd2adopt_"))
            files = _extract_patch_zip(src, tmp)
            root = tmp
            rel_base = tmp
        elif src.is_file() and ARCHIVE_PATCH_RE.match(src.name):
            root = src.parent
            files = [src]
            rel_base = root
        else:
            die("--from 需要是 patch 文件、包含 patch 的文件夹，或 SDK 导出的 zip")

        if not files:
            die("来源里没有找到 *.patch_N")

        # 一个工程只收一个 option；zip 里如果带了多个 option，编号会撞
        for archive, items in group_patches(files).items():
            nums = [n for n, _ in items]
            if len(set(nums)) != len(nums):
                die(f"来源里 archive {archive} 有重复编号（{sorted(nums)}）。\n"
                    "       看起来包含多个 option；请一次只 adopt 一个 option 文件夹。")

        summaries = []
        for f in files:
            info, errs, warns = check_patch_file(f)
            if errs:
                for e in errs:
                    bad(e)
                die(f"{f.name} 不合格，已停止（没有复制任何文件）")
            for w in warns:
                warn(w)
            summaries.append({
                "file": str(f.relative_to(rel_base)),
                "size": info["actual_size"],
                "types": info["type_counts"],
                "units": info["unit_count"],
            })

        dest = proj / "patches"
        option = getattr(args, "option", None)
        if option:
            manifest = read_json(proj / "manifest.json", {}) or {}
            valid = set(_manifest_includes(manifest.get("Options", [])))
            if option not in valid:
                die(f"option「{option}」不在 manifest 的 Include 里；"
                    f"可选：{', '.join(sorted(valid)) or '(空)'}")
            dest = dest / option
        if dest.exists() and any(dest.iterdir()):
            if not args.force:
                die(f"{dest} 里已有文件。确认要覆盖就加 --force。")
            shutil.rmtree(dest)
        dest.mkdir(parents=True, exist_ok=True)

        copied = 0
        for f in files:
            rel = f.relative_to(rel_base)
            d = dest / rel
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, d)
            copied += 1
            for suffix in (".stream", ".gpu_resources"):
                side = f.with_name(f.name + suffix)
                if side.is_file():
                    shutil.copy2(side, d.with_name(d.name + suffix))

        write_json(dest / "SOURCE.json", {
            "adopted_at": datetime.now(timezone.utc).isoformat(),
            "source": str(src),
            "patches": summaries,
        })

        ok(f"已收编 {copied} 个 patch → {dest}")
        for s in summaries:
            types = " · ".join(f"{k} {v}" for k, v in sorted(s["types"].items()))
            print(f"       {s['file']}  ({human_size(s['size'])})  {types}")
        print("       下一步：build → check")
    finally:
        if tmp and tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------- inspect

def cmd_inspect(args):
    rows = []
    for raw in args.paths:
        path = Path(raw)
        files = iter_patch_files(path)
        if not files:
            bad(f"{path} 里没有 *.patch_N")
            continue
        for f in files:
            info, errs, warns = check_patch_file(f)
            if info:
                rows.append({
                    "path": str(f),
                    "size": info["actual_size"],
                    "self_size": info["self_size"],
                    "types": info["type_counts"],
                    "entries": len(info["entries"]),
                    "units": info["unit_count"],
                    "needs_gpu": info["needs_gpu"],
                    "gpu_file_size": info["gpu_file_size"],
                    "needs_stream": info["needs_stream"],
                    "stream_file_size": info["stream_file_size"],
                    "type_counts_ok": info["type_counts_ok"],
                    "overlaps": info["overlaps"],
                    "max_toc_end": info["max_toc_end"],
                })
                if not args.json:
                    print_patch_info(f, info)
                for e in errs:
                    bad(e)
                for w in warns:
                    warn(w)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
    return 0 if rows else 1


# ---------------------------------------------------------------- lookup

def cmd_lookup(args):
    sdk = Path(args.sdk) if args.sdk else find_sdk()
    if not sdk:
        warn("没找到 HD2SDK。模型路线需要它；装好后重试，或用 set-sdk <插件目录> 指定。")
        print("       也可以在 Blender 的 SDK 里用 Search Found Archives 搜英文名。")
        return 1

    index_path = sdk / "hashlists" / "archivehashes.json"
    hits = []
    if index_path.is_file():
        data = read_json(index_path, {}) or {}
        q = args.query.strip().lower()
        for cat, items in data.items():
            if args.category and args.category.lower() not in cat.lower():
                continue
            if not isinstance(items, dict):
                continue
            for archive, name in items.items():
                if q in str(name).lower() or q in str(archive).lower():
                    hits.append((cat, str(archive), str(name)))

    friendly = sdk / "hashlists" / "friendlynames.txt"
    if friendly.is_file() and not args.category:
        q = args.query.strip().lower()
        for line in friendly.read_text(encoding="utf-8", errors="replace").splitlines():
            parts = line.strip().split(" ", 1)
            if len(parts) != 2:
                continue
            rid, name = parts
            if q in name.lower() or q == rid.lower():
                hits.append(("unit/entry", rid, name))

    # 去重 + 限量
    seen, uniq = set(), []
    for h in hits:
        if h not in seen:
            seen.add(h)
            uniq.append(h)
    uniq = uniq[:args.limit]

    if args.json:
        print(json.dumps([{"category": c, "id": i, "name": n} for c, i, n in uniq],
                         ensure_ascii=False, indent=1))
        return 0 if uniq else 1

    if not uniq:
        warn(f"没搜到「{args.query}」。换英文名/缩写，或在 SDK 里用 Search Found Archives。")
        return 1

    for cat, rid, name in uniq:
        print(f"{cat:16} {rid:>20}  {name}")
    print(f"\n共 {len(uniq)} 条。Archive ID 填进 SDK 的搜索/手动加载；unit ID 在导入后看 Custom Properties。")
    return 0


# ---------------------------------------------------------------- install

def cmd_install(args):
    proj = Path(args.project).resolve()
    dist = proj / "dist"
    if not dist.is_dir():
        die("还没有 dist/，先 build")
    bundle = next((d for d in dist.iterdir() if d.is_dir()), None)
    if not bundle:
        die("dist/ 里没有可导入的文件夹")

    if game_running() and not args.allow_running:
        die("游戏正在运行。部署时文件被占用会半途失败；退出游戏后重试，"
            "或确认风险后加 --allow-running。")

    lib = find_library(find_game())
    if lib:
        target = lib / bundle.name
        if target.exists():
            if not args.force:
                die(f"库里已经有同名目录：{target}\n"
                    f"       可能是一个已存在的 mod。确认要覆盖就加 --force，或改个 --title。")
            shutil.rmtree(target)
        shutil.copytree(bundle, target)
        ok(f"已放进 mod 库：{target}")
    else:
        warn("没找到 mod 库，跳过复制；直接把 dist/ 下的文件夹拖进管理器即可")

    cli = shutil.which("hd2qd")
    if cli and lib:
        print("\n正在用 hd2qd 部署…")
        for cmd in (["add", str(lib / bundle.name), "--whole"], ["deploy"]):
            r = subprocess.run([cli, *cmd], capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            print((r.stdout or "").strip())
            if r.returncode != 0:
                warn(f"hd2qd {' '.join(cmd)} 返回 {r.returncode}：{(r.stderr or '').strip()}")
                break
    else:
        print("\n手动两步：")
        print("  1) 打开 HD2 Mod Quick Deploy（或 Arsenal），把上面那个文件夹拖进去")
        print("  2) 勾选它 → Deploy")

    project = read_json(proj / "mod.project.json", {}) or {}
    if project.get("kind") == "model":
        print("\n然后：重启游戏 → 去装备界面看外观。资源 mod 不能游戏内热开关。")
    else:
        print("\n然后进游戏：ESC → MDL 设置，确认列表里有它。")


# ---------------------------------------------------------------- lint

def cmd_lint(args):
    raw = Path(args.file).read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        die("文件带 UTF-8 BOM")
    text = raw.decode("utf-8", "replace")
    issues = lint_lua(text)
    if not issues:
        ok(f"{Path(args.file).name}：未发现 5.1 不兼容构造（启发式）")
        return
    for ln, desc, snip in issues:
        bad(f"L{ln}: {desc}\n         {snip}")
    print(f"\n{len(issues)} 处问题")
    raise SystemExit(1)


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(prog="hd2mod", description="HD2 mod 工具（玩法 / 模型）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor", help="环境体检").set_defaults(func=cmd_doctor)
    p = sub.add_parser("set-game", help="手动指定游戏目录"); p.add_argument("path"); p.set_defaults(func=cmd_setgame)
    p = sub.add_parser("set-lib", help="手动指定 mod 库"); p.add_argument("path"); p.set_defaults(func=cmd_setlib)
    p = sub.add_parser("set-sdk", help="手动指定 HD2SDK 插件目录"); p.add_argument("path"); p.set_defaults(func=cmd_setsdk)

    p = sub.add_parser("lookup", help="查装备对应的 archive ID")
    p.add_argument("query")
    p.add_argument("--category", help="只看某个分类，如 Armor / Helmet / Assault Rifle")
    p.add_argument("--limit", type=int, default=40)
    p.add_argument("--sdk", help="指定 HD2SDK 插件目录")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_lookup)

    p = sub.add_parser("new", help="新建工程")
    p.add_argument("--kind", default="lua", choices=["lua", "model"])
    p.add_argument("--author")
    p.add_argument("--name")
    p.add_argument("--title", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--option", default="Core")
    p.add_argument("--target", default="mdl3", choices=["mdl3", "none"])
    p.add_argument("--subject", help="模型工程的目标装备名")
    p.add_argument("--target-kind", default="armor",
                   choices=["armor", "helmet", "weapon", "prop", "texture", "other"])
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("adopt", help="收编 HD2SDK 导出的 patch")
    p.add_argument("project")
    p.add_argument("--from", dest="source", required=True)
    p.add_argument("--option", help="收进 patches/<Include>/（多 option 工程用）")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_adopt)

    p = sub.add_parser("build", help="打包")
    p.add_argument("project"); p.add_argument("--zip", action="store_true")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("check", help="静态门禁"); p.add_argument("project"); p.set_defaults(func=cmd_check)

    p = sub.add_parser("inspect", help="查看 patch 内容")
    p.add_argument("paths", nargs="+")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_inspect)

    p = sub.add_parser("install", help="放进库并部署")
    p.add_argument("project")
    p.add_argument("--force", action="store_true")
    p.add_argument("--allow-running", action="store_true",
                   help="游戏正在运行也继续（不推荐）")
    p.set_defaults(func=cmd_install)

    p = sub.add_parser("lint", help="Lua 5.1 检查"); p.add_argument("file"); p.set_defaults(func=cmd_lint)

    args = ap.parse_args()
    rc = args.func(args)
    if isinstance(rc, int):
        raise SystemExit(rc)


if __name__ == "__main__":
    main()
