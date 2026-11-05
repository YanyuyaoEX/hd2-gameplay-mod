#!/usr/bin/env python3
"""hd2mod.py - HD2 玩法 mod 工具（零依赖，纯标准库）

    doctor                     体检：找游戏、找库、找管理器、看加载器
    new   --author --name ...  建工程
    build <project> [--zip]    打包成可导入的 dist/
    check <project>            静态门禁（全绿才允许部署）
    install <project>          放进 mod 库并提示部署
    lint  <file.lua>           Lua 5.1 兼容性检查

设计前提：**不依赖 srkit**。补丁容器由本文件直接生成，
已与真实可加载的 mod 包做过逐字节比对（同输入 → 同字节）。
srkit 只在路线 B（资源替换）需要，属于可选工具。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import uuid
import zipfile
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

CONFIG_DIR = Path(os.environ.get("HD2MOD_HOME") or (Path.home() / ".hd2-gameplay-mod"))
CONFIG_FILE = CONFIG_DIR / "config.json"

GUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                     r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
MODULE_RE = re.compile(r"^mods/[a-z0-9_]+/[a-z0-9_]+$")


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
    """只解析本工具生成的单资源包，用于门禁自检。"""
    if len(blob) < HEADER_SIZE + TYPE_SIZE + ENTRY_SIZE:
        raise ValueError("文件太小，不是有效的 patch 包")
    magic, ntype, nentry, _ = struct.unpack_from("<IIII", blob, 0)
    if magic != TOC_MAGIC:
        raise ValueError(f"magic 不对：0x{magic:08X}")
    self_size = struct.unpack_from("<I", blob, SELF_SIZE_OFFSET)[0]
    (file_id, type_id, toc_off, _s, _g, _u1, _u2,
     toc_size, _ss, _gs, _u3, _u4, _idx) = \
        struct.unpack_from("<QQQQQQQIIIIII", blob, HEADER_SIZE + TYPE_SIZE)
    payload = blob[toc_off:toc_off + toc_size]
    if len(payload) < 8:
        raise ValueError("payload 头不完整")
    size, unknown = struct.unpack_from("<II", payload, 0)
    script = payload[8:8 + size]
    return {"types": ntype, "entries": nentry, "self_size": self_size,
            "file_id": file_id, "type_id": type_id, "toc_offset": toc_off,
            "toc_size": toc_size, "declared_payload": size, "unknown": unknown,
            "script": script, "actual_size": len(blob)}


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


# ---------------------------------------------------------------- doctor

def pretty(p) -> str:
    """Windows 路径展示用：盘符大写、分隔符统一，避免 'd:\\steam' 这种别扭输出。"""
    if p is None:
        return "(none)"
    s = str(Path(p))
    if len(s) > 1 and s[1] == ":":
        s = s[0].upper() + s[1:]
    return s


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

    srkit = os.environ.get("HD2_SRKIT")
    if srkit and Path(srkit, "srkit").is_dir():
        ok(f"srkit      {srkit}（仅资源替换路线需要）")
    else:
        print("[ -- ] srkit      未配置（Lua 路线不需要；路线 B 才要）")

    print()
    if game:
        print("体检通过。下一步：new → 改 src/main.lua → build → check → install")
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
    author, name = args.author.strip().lower(), args.name.strip().lower()
    for v, what in ((author, "--author"), (name, "--name")):
        if not re.fullmatch(r"[a-z0-9_]+", v):
            die(f"{what} 只能用小写字母/数字/下划线（会进模块路径与哈希）")

    module = f"mods/{author}/{name}"
    out = Path(args.out)
    if (out / "manifest.json").exists():
        die(f"{out} 已存在 manifest.json，拒绝覆盖")

    (out / "src").mkdir(parents=True, exist_ok=True)
    (out / "assets").mkdir(exist_ok=True)
    identity = murmur64(module)

    write_json(out / "manifest.json", {
        "Guid": str(uuid.uuid4()),
        "Name": f"{args.title} v0.1.0",
        "Description": f"玩法 MOD。模块路径 {module}。"
                       + ("需要 MDL3 3.0.0-dev.36+。" if args.target == "mdl3" else "无需额外加载器。"),
        "Version": 1,
        "IconPath": "cover.jpg",
        "Options": [{"Name": "核心 / Core（必选）", "Description": "玩法脚本主体",
                     "Include": [args.option]}],
    })
    write_json(out / "mod.project.json", {
        "module": module, "option": args.option, "script": "src/main.lua",
        "target": args.target,
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


# ---------------------------------------------------------------- build

def cmd_build(args):
    proj = Path(args.project).resolve()
    manifest = read_json(proj / "manifest.json")
    project = read_json(proj / "mod.project.json")
    if not manifest or not project:
        die(f"{proj} 不是合法工程（缺 manifest.json 或 mod.project.json）")

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
    dist_name = re.sub(r"[^\w\-.]+", "_", manifest.get("Name", "mod")).strip("_") or "mod"
    dist = dist_root / dist_name
    (dist / option).mkdir(parents=True, exist_ok=True)
    (dist / option / PATCH_NAME).write_bytes(blob)

    for extra in ("manifest.json", "README.md", "CHANGELOG.md", "THIRD_PARTY.md"):
        if (proj / extra).is_file():
            shutil.copy2(proj / extra, dist / extra)
    cover = proj / "assets" / "cover.jpg"
    if cover.is_file():
        shutil.copy2(cover, dist / "cover.jpg")

    ok(f"打包完成：{dist / option / PATCH_NAME}  ({len(blob)} 字节)")
    print(f"       资源 ID : 0x{identity:016X}   模块 {module}")
    if args.zip:
        zp = dist_root / f"{dist_name}.zip"
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(dist.rglob("*")):
                if f.is_file():
                    z.write(f, f.relative_to(dist))
        ok(f"已打 zip：{zp}")
    print("       下一步：check → install")


# ---------------------------------------------------------------- check

def cmd_check(args):
    proj = Path(args.project).resolve()
    fails, warns = [], []
    manifest = read_json(proj / "manifest.json")
    project = read_json(proj / "mod.project.json")
    if not manifest or not project:
        die("不是合法工程")
    module = project["module"]

    if not GUID_RE.match(str(manifest.get("Guid", ""))):
        fails.append(f"manifest.Guid 不是合法 UUID：{manifest.get('Guid')!r}")
    if not str(manifest.get("Name", "")).strip():
        fails.append("manifest.Name 为空")
    if not isinstance(manifest.get("Version"), int):
        fails.append("manifest.Version 必须是整数")
    if not manifest.get("Options"):
        fails.append("manifest.Options 为空，管理器不会部署任何文件")
    for o in manifest.get("Options", []):
        if not o.get("Include"):
            fails.append(f"选项 {o.get('Name')!r} 没有 Include")

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
        if len(patches) > 512:
            fails.append(f"patch 文件 {len(patches)} 个，超过 MDL3 的 512 上限")
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


# ---------------------------------------------------------------- install

def cmd_install(args):
    proj = Path(args.project).resolve()
    dist = proj / "dist"
    if not dist.is_dir():
        die("还没有 dist/，先 build")
    bundle = next((d for d in dist.iterdir() if d.is_dir()), None)
    if not bundle:
        die("dist/ 里没有可导入的文件夹")

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
    ap = argparse.ArgumentParser(prog="hd2mod", description="HD2 玩法 mod 工具")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor", help="环境体检").set_defaults(func=cmd_doctor)
    p = sub.add_parser("set-game", help="手动指定游戏目录"); p.add_argument("path"); p.set_defaults(func=cmd_setgame)
    p = sub.add_parser("set-lib", help="手动指定 mod 库"); p.add_argument("path"); p.set_defaults(func=cmd_setlib)

    p = sub.add_parser("new", help="新建工程")
    p.add_argument("--author", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--option", default="Core")
    p.add_argument("--target", default="mdl3", choices=["mdl3", "none"])
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("build", help="打包")
    p.add_argument("project"); p.add_argument("--zip", action="store_true")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("check", help="静态门禁"); p.add_argument("project"); p.set_defaults(func=cmd_check)
    p = sub.add_parser("install", help="放进库并部署")
    p.add_argument("project"); p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_install)
    p = sub.add_parser("lint", help="Lua 5.1 检查"); p.add_argument("file"); p.set_defaults(func=cmd_lint)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
