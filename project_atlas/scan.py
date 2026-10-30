# -*- coding: utf-8 -*-
"""只读扫描：找出项目根目录，统计每个项目的大小、最后改动、技术栈和 git 状态。

不修改、不移动、不删除任何文件；不跟随符号链接 / junction；不读取云端占位文件（避免触发下载）。
"""
import os
import re
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from .rules import (BUCKET, BUNDLE_EXT, CLOUD, CODE_EXT, CREATIVE_EXT, CREATIVE_NAME, HOME_SKIP, LANG,
                    MEDIA_EXT, NOISE_EXT, SHELL_EXT, SKIP_ANY, SYSTEM_ROOT_SKIP, TERMINAL, TERMINAL_EXT,
                    UNINSTALL, WEAK_MARKERS, collect_type, user_place)

WINDOWS = os.name == "nt"
NO_WINDOW = 0x08000000 if WINDOWS else 0
ATTR_SKIP = 0x400 | 0x1000 | 0x40000 | 0x400000  # reparse / offline / recall-on-open / recall-on-access


def norm(p):
    return os.path.normcase(os.path.normpath(p))


def under(child, parent):
    """child 是否在 parent 里面（两者都已 norm）。"""
    return child != parent and child.startswith(parent.rstrip(os.sep) + os.sep)


def is_link(entry):
    try:
        if entry.is_symlink() or (hasattr(entry, "is_junction") and entry.is_junction()):
            return True
        if WINDOWS:
            return bool(getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0) & 0x400)
        return False
    except OSError:
        return True


def listdir(path):
    dirs, files = [], []
    try:
        with os.scandir(path) as it:
            for e in it:
                try:
                    (dirs if e.is_dir(follow_symlinks=False) else files).append(e)
                except OSError:
                    pass
    except OSError:
        return None, None
    return dirs, files


def classify(dirs, files, min_code=3):
    """返回 (kind, markers)，kind 为 terminal / venv / app / weak / None。"""
    dn = {d.name.lower() for d in dirs}
    fn = {f.name.lower() for f in files}
    mk = {TERMINAL[n] for n in dn | fn if n in TERMINAL}
    mk |= {TERMINAL_EXT[os.path.splitext(n)[1]] for n in dn | fn if os.path.splitext(n)[1] in TERMINAL_EXT}
    if mk:
        return "terminal", sorted(mk)
    if "pyvenv.cfg" in fn or "conda-meta" in dn or sum(n.endswith(".dist-info") for n in dn) >= 2:
        return "venv", ["Python 环境/库"]
    exe = any(n.endswith(".exe") for n in fn)
    dll = sum(n.endswith(".dll") for n in fn)
    shims = sum(n.endswith(".cmd") for n in fn)
    if any(UNINSTALL.match(n) for n in fn) or "product-info.json" in fn or (exe and dll >= 3) \
            or ({"bin", "lib"} <= dn and bool({"include", "share", "libexec", "pkg"} & dn)) \
            or {"common7", "msbuild"} <= dn or ("node_modules" in dn and "package.json" not in fn and shims >= 3):
        return "app", ["软件/工具"]
    weak = ["技能包"] if "skill.md" in fn else []
    if (dn | fn) & WEAK_MARKERS:
        weak.append("AI/IDE 配置")
    ncode = sum(os.path.splitext(n)[1] in CODE_EXT for n in fn)
    nshell = sum(os.path.splitext(n)[1] in SHELL_EXT for n in fn)
    if ncode - nshell >= min_code or ncode >= 3:  # 只有启动脚本的目录至少要 3 个才算
        weak.append("散装代码×%d" % ncode)
    if any(os.path.splitext(n)[1] in CREATIVE_EXT for n in fn):
        weak.append("创作工程")
    return ("weak", weak) if weak else (None, [])


def skip_reason(entry, depth, root, cfg):
    """不进入这个目录的原因；None 表示照常扫描。"""
    n = entry.name.lower()
    full = norm(entry.path)
    if is_link(entry):
        return "链接 / 云端占位"
    if full in cfg["skip_paths"]:
        return cfg["skip_paths"][full]
    if n in CLOUD or n.startswith("onedrive"):
        return "云同步盘（不读取，避免触发下载）"
    if n in SKIP_ANY or n in ("appdata", "application data") or n.endswith(BUNDLE_EXT):
        return "依赖 / 缓存 / 系统"
    if depth == 1 and root in cfg["system_roots"] and n in SYSTEM_ROOT_SKIP:
        if n in ("users", "home") and not cfg["home_scanned"]:
            return None
        return "系统目录"
    if depth == 1 and root == cfg["home_norm"] and (n.startswith(".") or n in HOME_SKIP):
        return "程序数据 / 工具配置"
    return None


def _visit(path, depth, dirs, files, cands, apps):
    """识别一个目录；返回 True 表示到此为止、不再往下扫。"""
    name = os.path.basename(path.rstrip(os.sep)) or path
    here = user_place(os.path.basename(os.path.dirname(path.rstrip(os.sep))), depth)
    kind, mk = classify(dirs, files, 1 if here else 3)
    rec = {"path": path, "markers": mk, "depth": depth}
    if kind == "terminal":
        cands.append(dict(rec, kind="terminal"))
        return True
    if kind in ("venv", "app"):
        if depth <= 3:
            apps.append({"path": path, "kind": kind})
        return True
    if kind == "weak":
        cands.append(dict(rec, kind="weak"))
    elif CREATIVE_NAME.search(name) and (here or sum(
            os.path.splitext(f.name)[1].lower() in MEDIA_EXT for f in files) >= 3):
        cands.append(dict(rec, kind="weak", markers=["素材/作品"]))
    elif here and collect_type(name):
        cands.append(dict(rec, kind="weak", markers=[collect_type(name)]))
    return False


def discover(cfg, progress=print):
    t0 = time.time()
    cands, apps, skipped, seen = [], [], [], 0
    for root_path, maxd in cfg["roots"]:
        if not os.path.isdir(root_path):
            skipped.append({"path": root_path, "why": "根目录不存在"})
            continue
        root = norm(root_path)
        stack = [(root_path, 0)]
        while stack:
            path, depth = stack.pop()
            if time.time() - t0 > cfg["discover_limit_s"]:
                skipped.append({"path": path, "why": "超出扫描时限，未展开"})
                continue
            dirs, files = listdir(path)
            seen += 1
            if dirs is None:
                if 0 < depth <= 3:
                    skipped.append({"path": path, "why": "无权限"})
                continue
            if norm(path) not in cfg["never_project"] and _visit(path, depth, dirs, files, cands, apps):
                continue
            if depth >= maxd:
                continue
            for d in dirs:
                why = skip_reason(d, depth + 1, root, cfg)
                if why:
                    if depth + 1 <= 2 or why.startswith(("云同步", "用户排除", "系统临时", "工具输出")):
                        skipped.append({"path": d.path, "why": why})
                    continue
                stack.append((d.path, depth + 1))
            if seen % 20000 == 0:
                progress("  已看过 %d 个目录……" % seen)
    uniq = {}
    for c in cands:
        uniq.setdefault(norm(c["path"]), c)
    stats = {"dirs_visited": seen, "seconds": round(time.time() - t0, 1), "candidates": len(uniq)}
    return {"stats": stats, "candidates": list(uniq.values()), "apps": apps, "skipped": skipped}


def walk(root, exclude, cap=400000):
    """有上限的子树遍历：大小、文件数、最后改动、各类占用、扩展名、里面的 git 仓库。"""
    st = {"size": 0, "files": 0, "buckets": {}, "ext": {}, "mtime": 0.0, "nested_git": [], "capped": False}
    stack, n = [(root, None, 0)], 0
    while stack:
        path, bucket, depth = stack.pop()
        try:
            it = os.scandir(path)
        except OSError:
            continue
        with it:
            for e in it:
                n += 1
                if n > cap:
                    st["capped"] = True
                    return st
                try:
                    if is_link(e):
                        continue
                    if e.is_dir(follow_symlinks=False):
                        if norm(e.path) in exclude:
                            continue
                        low = e.name.lower()
                        if low == ".git" and depth > 0:
                            st["nested_git"].append(os.path.relpath(path, root))
                        stack.append((e.path, bucket or BUCKET.get(low), depth + 1))
                        continue
                    s = e.stat(follow_symlinks=False)
                except OSError:
                    continue
                st["size"] += s.st_size
                st["files"] += 1
                if bucket:
                    st["buckets"][bucket] = st["buckets"].get(bucket, 0) + s.st_size
                    continue
                ext = os.path.splitext(e.name)[1].lower()
                st["ext"][ext] = st["ext"].get(ext, 0) + 1
                if ext not in NOISE_EXT and s.st_mtime > st["mtime"]:
                    st["mtime"] = s.st_mtime
    return st


GIT = shutil.which("git")
GIT_ENV = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0", LC_ALL="C")


def run_git(path, *args, timeout=25):
    """只读 git 命令，返回 (returncode, stdout, stderr)。不 fetch、不联网。"""
    try:
        r = subprocess.run([GIT, "-c", "core.fsmonitor=false", "-c", "core.quotepath=false", "-C", path] + list(args),
                           capture_output=True, timeout=timeout, env=GIT_ENV, creationflags=NO_WINDOW)
        return r.returncode, r.stdout.decode("utf-8", "replace").strip(), r.stderr.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except OSError as err:
        return -2, "", str(err)


def git_info(path):
    if not GIT:
        return {"unavailable": True}
    rc, _, err = run_git(path, "rev-parse", "--git-dir")
    if rc != 0:
        return {"untrusted": True} if "dubious ownership" in err or "safe.directory" in err else {"broken": True}
    g = {}
    rc, out, _ = run_git(path, "log", "-1", "--format=%ct%x1f%s")
    if rc == 0 and out:
        ct, _, subject = out.partition("\x1f")
        g["last_commit"] = int(ct) if ct.isdigit() else None
        g["subject"] = subject[:120]
    g["branch"] = run_git(path, "rev-parse", "--abbrev-ref", "HEAD")[1] or None
    g["commits"] = run_git(path, "rev-list", "--count", "HEAD")[1] or None
    remotes = run_git(path, "remote")[1].split()
    url = run_git(path, "remote", "get-url", "origin" if "origin" in remotes else remotes[0])[1] if remotes else ""
    g["remote"] = re.sub(r"//[^/@\s]+@", "//", url) or None  # 去掉地址里的账号 / 令牌
    rc, out, _ = run_git(path, "status", "--porcelain", "-unormal", timeout=60)
    g["dirty"] = len([ln for ln in out.splitlines() if ln.strip()]) if rc == 0 else None
    g["unpushed"] = None
    if remotes:
        rc, out, _ = run_git(path, "rev-list", "--count", "HEAD", "--not", "--remotes")
        g["unpushed"] = int(out) if rc == 0 and out.isdigit() else None
    return g


def head(path, n=4096):
    try:
        if getattr(os.stat(path), "st_file_attributes", 0) & ATTR_SKIP:
            return ""  # 云端占位文件：不读，避免触发下载
        with open(path, "rb") as f:
            return f.read(n).decode("utf-8", "replace")
    except OSError:
        return ""


README = ("README.md", "README_CN.md", "README.zh-CN.md", "README.zh.md", "readme.md", "Readme.md",
          "README.rst", "README.txt", "readme.txt", "说明.md", "说明.txt")


def describe(path):
    """一句话说明：package.json / pyproject.toml / Cargo.toml 的 description，或 README 第一段。"""
    for fname, pat in (("package.json", r'"description"\s*:\s*"([^"]{2,200})"'),
                       ("pyproject.toml", r'^description\s*=\s*["\']([^"\']{2,200})["\']'),
                       ("Cargo.toml", r'^description\s*=\s*"([^"]{2,200})"')):
        m = re.search(pat, head(os.path.join(path, fname)), re.M)
        if m:
            return m.group(1).strip()
    for fname in README:
        title = None
        for line in head(os.path.join(path, fname)).splitlines():
            s = line.strip()
            if not s or s.startswith(("<", "[!", "![", "```", "|", "---", "===", ">", "..")) or "shields.io" in s:
                continue
            if s.startswith("#"):
                title = title or s.lstrip("# ").strip()
                continue
            return re.sub(r"[*_`]", "", s)[:120]
        if title:
            return title[:120]
    return ""


def analyze_one(entry, exclude, use_git=True):
    p = entry["path"]
    st = walk(p, exclude)
    agg = {}
    for ext, cnt in st.pop("ext").items():
        if ext in LANG:
            agg[LANG[ext]] = agg.get(LANG[ext], 0) + cnt
    ranked = sorted(agg, key=lambda k: -agg[k])
    st["langs"] = [k for k in ranked if k not in ("Markdown", "JSON")][:3] or ranked[:1]
    st["desc"] = describe(p)
    dotgit = os.path.join(p, ".git")
    st["git"] = None
    if os.path.exists(dotgit):
        st["git"] = git_info(p) if use_git else {"skipped": True}
        if os.path.isfile(dotgit) and "branch" in st["git"]:
            st["git"]["worktree_of"] = head(dotgit, 512).replace("gitdir:", "").strip()
    return st


def analyze(cfg, entries, progress=print):
    t0 = time.time()
    keys = sorted(norm(e["path"]) for e in entries)
    results = {}
    with ThreadPoolExecutor(cfg["workers"]) as ex:
        futs = {}
        for e in entries:
            me = norm(e["path"])
            futs[ex.submit(analyze_one, e, {k for k in keys if under(k, me)}, cfg["git"])] = e["path"]
        for i, f in enumerate(as_completed(futs), 1):
            try:
                results[futs[f]] = f.result()
            except Exception as err:  # 单个目录出错不影响其它
                results[futs[f]] = {"error": repr(err)}
            if i % 50 == 0:
                progress("  已统计 %d / %d" % (i, len(futs)))
            if time.time() - t0 > cfg["analyze_limit_s"]:
                for g in futs:
                    g.cancel()
                break
    for e in entries:
        results.setdefault(e["path"], {"pending": True})
    return results
