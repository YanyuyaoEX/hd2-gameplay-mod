#!/usr/bin/env python3
"""hd2mod.py - HD2 gameplay mod 脚手架 / 构建 / 静态门禁

子命令
    new    <--author> <--name> <--title> <--out>   建工程
    build  <project> [--zip]                        打包成可导入的 dist/
    check  <project>                                静态门禁（全绿才允许部署）
    lint   <file.lua>                               Lua 5.1 兼容性启发式检查

只依赖标准库 + srkit（modtool 内，无需 pip 安装）。
srkit 路径：环境变量 HD2_SRKIT，或默认 toolroot。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
import zipfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_SRKIT = r"C:/Users/50709/Downloads/modtool/hd2-srkit-master"
PATCH_NAME = "9ba626afa44a3aa3.patch_0"
LUA_TYPE_ID = "11623383793923069922"

# 单 lua 资源包的容器骨架。取自 build 26251122 的实测样本，换 build 后需重新取样。
UNK4_HEX = ("0000000000000000000000000000000015600200"
            "0000000000000000000000000000000000000000000000000000000000000000"
            "0000000000000000")

GUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                     r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
MODULE_RE = re.compile(r"^mods/[a-z0-9_]+/[a-z0-9_]+$")


# --------------------------------------------------------------------------
# 基础工具
# --------------------------------------------------------------------------

def srkit_root() -> Path:
    raw = os.environ.get("HD2_SRKIT") or DEFAULT_SRKIT
    p = Path(raw)
    if not (p / "srkit").is_dir():
        die(f"找不到 srkit：{p}\n用 HD2_SRKIT 环境变量指向 hd2-srkit-master 目录。")
    return p


def die(msg: str) -> "NoReturn":
    print(f"[FAIL] {msg}")
    raise SystemExit(1)


def ok(msg: str) -> None:
    print(f"[ OK ] {msg}")


def warn(msg: str) -> None:
    print(f"[WARN] {msg}")


def srkit(args: list[str]) -> str:
    root = srkit_root()
    proc = subprocess.run([sys.executable, "-m", "srkit", *args], cwd=str(root),
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        die(f"srkit {' '.join(args)} 失败：\n{proc.stdout}\n{proc.stderr}")
    return proc.stdout


def murmur64(name: str) -> int:
    out = srkit(["hash", name])
    m = re.search(r"murmur64=0x([0-9A-Fa-f]+)", out)
    if not m:
        die(f"无法从 srkit hash 输出解析 murmur64：{out!r}")
    return int(m.group(1), 16)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------
# Lua 源码扫描：把字符串与注释抹成空格，只留代码，避免误报
# --------------------------------------------------------------------------

def strip_lua(src: str) -> str:
    out = list(src)
    i, n = 0, len(src)

    def blank(a: int, b: int) -> None:
        for k in range(a, min(b, n)):
            if out[k] != "\n":
                out[k] = " "

    while i < n:
        c = src[i]
        # 注释
        if src.startswith("--", i):
            if src.startswith("--[[", i) or src.startswith("--[=", i):
                m = re.match(r"--\[(=*)\[", src[i:])
                if m:
                    close = "]" + m.group(1) + "]"
                    end = src.find(close, i + len(m.group(0)))
                    end = n if end < 0 else end + len(close)
                    blank(i, end)
                    i = end
                    continue
            end = src.find("\n", i)
            end = n if end < 0 else end
            blank(i, end)
            i = end
            continue
        # 长字符串
        if c == "[":
            m = re.match(r"\[(=*)\[", src[i:])
            if m:
                close = "]" + m.group(1) + "]"
                end = src.find(close, i + len(m.group(0)))
                end = n if end < 0 else end + len(close)
                blank(i, end)
                i = end
                continue
        # 短字符串
        if c in "'\"":
            j = i + 1
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == c:
                    j += 1
                    break
                j += 1
            blank(i, j)
            i = j
            continue
        i += 1
    return "".join(out)


FORBIDDEN = [
    (r"\bffi\b", "ffi：10-20 后不存在，内存读写路线已死"),
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


def lint_lua(text: str) -> list[tuple[int, str, str]]:
    """返回 [(行号, 规则说明, 该行原文)]"""
    issues: list[tuple[int, str, str]] = []
    code = strip_lua(text)
    lines = code.splitlines()
    raw_lines = text.splitlines()
    for idx, line in enumerate(lines, 1):
        for pattern, desc in FORBIDDEN:
            if re.search(pattern, line):
                issues.append((idx, desc, raw_lines[idx - 1].strip()[:100]))
    return issues


# --------------------------------------------------------------------------
# new
# --------------------------------------------------------------------------

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
    -- 在这里写玩法逻辑：先判 sr.Unit.alive / 接口存在，再取值
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

PROJECT_TEMPLATE = {
    "module": "",
    "option": "Core",
    "script": "src/main.lua",
    "target": "mdl3",
    "srkit": "",
}

MANIFEST_TEMPLATE = {
    "Guid": "",
    "Name": "",
    "Description": "",
    "Version": 1,
    "IconPath": "cover.jpg",
    "Options": [
        {
            "Name": "核心 / Core（必选）",
            "Description": "玩法脚本主体",
            "Include": ["Core"],
        }
    ],
}


def cmd_new(args) -> None:
    author = args.author.strip().lower()
    name = args.name.strip().lower()
    if not re.fullmatch(r"[a-z0-9_]+", author) or not re.fullmatch(r"[a-z0-9_]+", name):
        die("--author / --name 只能用小写字母、数字、下划线（会进模块路径与哈希）")

    module = f"mods/{author}/{name}"
    out = Path(args.out)
    if (out / "manifest.json").exists():
        die(f"{out} 已存在 manifest.json，拒绝覆盖。换一个 --out 或先手动清理。")

    (out / "src").mkdir(parents=True, exist_ok=True)
    (out / "assets").mkdir(exist_ok=True)

    identity = murmur64(module)
    write_json(out / "manifest.json", {
        **MANIFEST_TEMPLATE,
        "Guid": str(uuid.uuid4()),
        "Name": f"{args.title} v0.1.0",
        "Description": f"玩法 MOD。模块路径 {module}。"
                       f"{'需要 MDL3 3.0.0-dev.36+。' if args.target == 'mdl3' else '无需额外加载器。'}",
    })
    write_json(out / "mod.project.json", {**PROJECT_TEMPLATE, "module": module,
                                           "option": args.option, "target": args.target})
    (out / "src" / "main.lua").write_text(
        SCRIPT_TEMPLATE.format(module=module, title=args.title), encoding="utf-8", newline="\n")
    (out / "CHANGELOG.md").write_text(
        "# CHANGELOG\n\n## v0.1.0\n- 初始骨架\n", encoding="utf-8", newline="\n")
    (out / "README.md").write_text(
        f"# {args.title}\n\n"
        f"## 依赖\n- {'需要 MDL3 3.0.0-dev.36+（官方发布页：<填链接>）' if args.target == 'mdl3' else '无'}\n\n"
        f"## 兼容性\n- 验证 build：<填 build 号>\n- 加载器：<填>\n\n"
        f"## 已知问题\n- 暂无\n\n"
        f"## 卸载\n停用并重新部署即可，不写入任何用户目录。\n",
        encoding="utf-8", newline="\n")

    ok(f"工程已建：{out}")
    print(f"       模块路径 : {module}")
    print(f"       资源 ID  : 0x{identity:016X}")
    print(f"       Guid     : (已写入 manifest.json，永久冻结)")
    print(f"       下一步   : 编辑 src/main.lua → hd2mod.py build \"{out}\"")


# --------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------

def cmd_build(args) -> None:
    proj = Path(args.project).resolve()
    manifest = read_json(proj / "manifest.json")
    project = read_json(proj / "mod.project.json")

    module = project["module"]
    if not MODULE_RE.match(module):
        die(f"mod.project.json 的 module 不合规：{module}（应形如 mods/author/name）")
    option = project.get("option", "Core")
    script_rel = project.get("script", "src/main.lua")
    src = proj / script_rel
    if not src.is_file():
        die(f"找不到脚本：{src}")

    if not any(option == o.get("Include", [None])[0] or option in o.get("Include", [])
               for o in manifest.get("Options", [])):
        die(f"manifest.Options 里没有包含 {option} 的项，先对齐再打包")

    text = src.read_text(encoding="utf-8-sig")
    first = text.splitlines()[0].strip() if text else ""
    if first != f"-- HD2-Addon: {module}":
        die(f"首行声明与模块路径不一致\n  期望：-- HD2-Addon: {module}\n  实际：{first or '(空)'}")

    identity = murmur64(module)
    tag = f"lua_{identity:016X}"

    build = proj / "build"
    ws = build / ".ws"
    out = build / ".out"
    for p in (ws, out):
        if p.exists():
            shutil.rmtree(p)

    pkg = ws / "pkg"
    res = pkg / "resources" / tag
    res.mkdir(parents=True, exist_ok=True)

    write_json(ws / "manifest.json", {
        "format": "srkit/workspace", "version": 1,
        "source": {"path": "", "kind": "loose"},
        "filters": {"packages": None, "types": None, "file_ids": None,
                    "gpu": True, "stream": True, "raw": False},
        "packages": [{"name": PATCH_NAME, "directory": "pkg", "entries": 1, "unpacked": 1}],
    })
    write_json(pkg / "package.json", {
        "format": "srkit/package", "name": PATCH_NAME, "magic": 4026531857, "unknown": 0,
        "unk4_data_hex": UNK4_HEX,
        "types": [{"type_id": LUA_TYPE_ID, "type_name": "lua", "num_files": 1,
                   "unk1": "0", "unk2": 16, "unk3": 16}],
        "entries": [{
            "file_id": str(identity), "type_id": LUA_TYPE_ID, "type_name": "lua",
            "resource_dir": f"resources/{tag}", "toc_data_offset": 192,
            "stream_offset": 0, "gpu_resource_offset": 0,
            "unknown1": "0", "unknown2": "0", "unknown3": 16, "unknown4": 16,
            "entry_index": 0, "declared_toc_size": 0,
            "declared_gpu_size": 0, "declared_stream_size": 0,
        }],
        "companions": {"gpu": False, "stream": False},
    })
    write_json(res / "resource.json", {
        "format": "srkit/lua", "type_id": LUA_TYPE_ID, "type_name": "lua",
        "file_id": str(identity), "payload_size": 0, "unknown": 2, "content": "text",
        "trailing_bytes": 0,
        "payloads": [{"name": "script.lua", "size": 0, "editable": True,
                      "view": False, "note": "Lua source", "sha256": ""}],
    })
    (res / "script.lua").write_text(text, encoding="utf-8", newline="\n")

    srkit(["pack", str(ws), "-o", str(out)])
    produced = out / PATCH_NAME
    if not produced.is_file():
        die(f"srkit pack 没有产出 {PATCH_NAME}")

    dist_name = re.sub(r"[^\w\-.]+", "_", manifest.get("Name", "mod")).strip("_") or "mod"
    dist = proj / "dist" / dist_name
    if (proj / "dist").exists():
        shutil.rmtree(proj / "dist")
    (dist / option).mkdir(parents=True, exist_ok=True)
    shutil.copy2(produced, dist / option / PATCH_NAME)

    for extra in ("manifest.json", "README.md", "CHANGELOG.md", "THIRD_PARTY.md"):
        if (proj / extra).is_file():
            shutil.copy2(proj / extra, dist / extra)
    cover = proj / "assets" / "cover.jpg"
    if cover.is_file():
        shutil.copy2(cover, dist / "cover.jpg")

    ok(f"打包完成：{dist / option / PATCH_NAME}")
    print(f"       资源 ID : 0x{identity:016X}  模块 {module}")

    if args.zip:
        zip_path = proj / "dist" / f"{dist_name}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(dist.rglob("*")):
                if f.is_file():
                    z.write(f, f.relative_to(dist))
        ok(f"已打 zip：{zip_path}")

    print("       下一步：hd2mod.py check 过门禁后再部署")


# --------------------------------------------------------------------------
# check
# --------------------------------------------------------------------------

def find_patches(root: Path) -> list[Path]:
    return sorted([p for p in root.rglob("*.patch_*") if p.is_file()])


def cmd_check(args) -> None:
    proj = Path(args.project).resolve()
    fails: list[str] = []
    warns: list[str] = []

    manifest = read_json(proj / "manifest.json")
    project = read_json(proj / "mod.project.json")
    module = project["module"]

    # --- manifest ---
    guid = str(manifest.get("Guid", ""))
    if not GUID_RE.match(guid):
        fails.append(f"manifest.Guid 不是合法 UUID：{guid!r}")
    if not str(manifest.get("Name", "")).strip():
        fails.append("manifest.Name 为空")
    if not isinstance(manifest.get("Version"), int):
        fails.append("manifest.Version 必须是整数")
    options = manifest.get("Options") or []
    if not options:
        fails.append("manifest.Options 为空，管理器不会部署任何文件")
    for opt in options:
        inc = opt.get("Include") or []
        if not inc:
            fails.append(f"manifest 选项 {opt.get('Name')!r} 没有 Include")
        for folder in inc:
            if not (proj / folder).is_dir() and not (proj / "dist").exists():
                warns.append(f"Include 目录尚不存在（build 后才会生成）：{folder}")

    # --- 模块路径 ---
    if not MODULE_RE.match(module):
        fails.append(f"模块路径不合规：{module}")
    identity = murmur64(module) if MODULE_RE.match(module) else 0

    # --- 脚本声明 ---
    src = proj / project.get("script", "src/main.lua")
    if src.is_file():
        raw = src.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            fails.append("脚本带 UTF-8 BOM，PUC 5.1 会编译失败")
        if raw.startswith(b"\x1bLJ"):
            fails.append("脚本是 LuaJIT 字节码，本版本无法加载")
        text = raw.decode("utf-8", "replace")
        first = text.splitlines()[0].strip() if text else ""
        if first != f"-- HD2-Addon: {module}":
            fails.append(f"首行声明不匹配\n        期望 -- HD2-Addon: {module}\n        实际 {first or '(空)'}")
        if len(raw) > 4 * 1024 * 1024:
            fails.append(f"脚本 {len(raw)} 字节，超过 Chef 的 4 MB 上限")

        issues = lint_lua(text)
        if issues:
            fails.append(f"Lua 5.1 兼容性：{len(issues)} 处")
            for ln, desc, snippet in issues[:10]:
                fails.append(f"        L{ln}: {desc}  |  {snippet}")

    # --- 产物 ---
    dist_root = proj / "dist"
    patches = find_patches(dist_root if dist_root.is_dir() else proj)
    if not patches:
        warns.append("还没有 build 产物（先跑 build）")
    else:
        if len(patches) > 512:
            fails.append(f"patch 文件 {len(patches)} 个，超过 MDL3 的 512 上限")
        for p in patches:
            info = srkit(["list", str(p)])
            row = next((l for l in info.splitlines() if l.startswith("lua")), "")
            if not row:
                fails.append(f"{p.name} 里没有 lua 资源")
                continue
            cols = row.split()
            got = int(cols[1], 16)
            if got != identity:
                fails.append(f"{p.name} 的资源 ID 0x{got:016X} ≠ murmur64(module) 0x{identity:016X}")

    print()
    for w in warns:
        warn(w)
    if fails:
        for f in fails:
            print(f"[FAIL] {f}")
        print(f"\n门禁未通过：{len(fails)} 项失败")
        raise SystemExit(1)
    ok(f"门禁通过：{module}  (0x{identity:016X})")
    if patches:
        ok(f"产物 {len(patches)} 个 patch，ID 与声明一致")


# --------------------------------------------------------------------------
# lint
# --------------------------------------------------------------------------

def cmd_lint(args) -> None:
    src = Path(args.file)
    raw = src.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        print("[FAIL] 文件带 UTF-8 BOM")
        raise SystemExit(1)
    text = raw.decode("utf-8", "replace")
    issues = lint_lua(text)
    if not issues:
        ok(f"{src.name}：未发现 5.1 不兼容构造（启发式，最终以 hd2qd lua-syntax 为准）")
        return
    for ln, desc, snippet in issues:
        print(f"[FAIL] L{ln}: {desc}\n         {snippet}")
    print(f"\n{len(issues)} 处问题")
    raise SystemExit(1)


# --------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(prog="hd2mod", description="HD2 gameplay mod 工具")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("new", help="新建工程")
    p.add_argument("--author", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--option", default="Core")
    p.add_argument("--target", default="mdl3", choices=["mdl3", "none"])
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("build", help="打包")
    p.add_argument("project")
    p.add_argument("--zip", action="store_true")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("check", help="静态门禁")
    p.add_argument("project")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("lint", help="Lua 5.1 检查")
    p.add_argument("file")
    p.set_defaults(func=cmd_lint)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
