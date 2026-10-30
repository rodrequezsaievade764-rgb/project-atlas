# -*- coding: utf-8 -*-
"""本机上下文（只读）：编辑器 / 编程代理的“最近打开”记录，以及常见的磁盘异常。"""
import glob
import json
import os
import re
import shutil
import sqlite3
import string
import sys
import tempfile
import urllib.parse
from pathlib import Path

from .scan import WINDOWS, listdir, walk

HOME = os.path.expanduser("~")


def app_dirs():
    if WINDOWS:
        return [os.environ.get("APPDATA") or os.path.join(HOME, "AppData", "Roaming")]
    if sys.platform == "darwin":
        return [os.path.join(HOME, "Library", "Application Support")]
    return [os.environ.get("XDG_CONFIG_HOME") or os.path.join(HOME, ".config")]


def to_path(uri):
    p = (uri or "").strip().strip('"')
    if not p:
        return None
    if p.startswith("file://"):
        p = urllib.parse.unquote(urllib.parse.urlparse(p).path)
        if WINDOWS and re.match(r"^/[A-Za-z]:", p):
            p = p[1:]
    elif "://" in p:
        return None  # 远程工作区（SSH / WSL / 容器）
    if WINDOWS and re.match(r"^/[A-Za-z]/", p):
        p = p[1] + ":" + p[2:]  # Git Bash 风格的 /d/work
    p = os.path.normpath(p)
    if p.lower().endswith((".code-workspace", ".json")) or os.path.isfile(p):
        p = os.path.dirname(p)
    if WINDOWS and re.match(r"^[a-z]:", p):
        p = p[0].upper() + p[1:]
    return p if len(p) > 3 else None


class Recents:
    def __init__(self):
        self.items = {}

    def add(self, path, source, ts=None, count=1):
        p = to_path(path) if path else None
        if not p:
            return
        r = self.items.setdefault(p, {"sources": {}, "last": 0})
        r["sources"][source] = r["sources"].get(source, 0) + count
        r["last"] = max(r["last"], ts or 0)

    def result(self):
        return [{"path": p, "sources": v["sources"], "last": v["last"] or None, "exists": os.path.isdir(p)}
                for p, v in self.items.items()]


def vscode_family(rec):
    """VS Code 以及基于它的编辑器（Cursor、Windsurf、VSCodium……）。"""
    for base in app_dirs():
        for user in glob.glob(os.path.join(base, "*", "User")):
            app = os.path.basename(os.path.dirname(user))
            db = os.path.join(user, "globalStorage", "state.vscdb")
            if os.path.isfile(db):
                tmp = os.path.join(tempfile.gettempdir(), "project-atlas-%d.vscdb" % os.getpid())
                try:
                    shutil.copy2(db, tmp)  # 复制一份再读，不碰编辑器正在用的数据库
                    con = sqlite3.connect(Path(tmp).as_uri() + "?immutable=1", uri=True)
                    row = con.execute("select value from ItemTable where key='history.recentlyOpenedPathsList'"
                                      ).fetchone()
                    con.close()
                    for e in (json.loads(row[0]).get("entries", []) if row else []):
                        rec.add(e.get("folderUri") or (e.get("workspace") or {}).get("configPath"), app)
                except (OSError, sqlite3.Error, ValueError, AttributeError):
                    pass
                finally:
                    if os.path.exists(tmp):
                        os.remove(tmp)
            for wj in glob.glob(os.path.join(user, "workspaceStorage", "*", "workspace.json")):
                try:
                    with open(wj, encoding="utf-8") as f:
                        d = json.load(f)
                    folder = os.path.dirname(wj)
                    sv = os.path.join(folder, "state.vscdb")
                    ts = max(os.path.getmtime(folder), os.path.getmtime(sv) if os.path.exists(sv) else 0)
                    rec.add(d.get("folder") or d.get("workspace"), app, ts)
                except (OSError, ValueError, AttributeError):
                    pass


def jetbrains(rec):
    pats = []
    for b in app_dirs():
        pats += [os.path.join(b, "JetBrains", "*", "options", "recentProjects.xml"),
                 os.path.join(b, "Google", "AndroidStudio*", "options", "recentProjects.xml")]
    for xml in [x for p in pats for x in glob.glob(p)]:
        prod = os.path.basename(os.path.dirname(os.path.dirname(xml)))
        try:
            with open(xml, encoding="utf-8", errors="replace") as f:
                txt = f.read()
        except OSError:
            continue
        for m in re.finditer(r'<entry key="([^"]+)">(.*?)</entry>', txt, re.S):
            ts = re.search(r'name="projectOpenTimestamp" value="(\d+)"', m.group(2))
            rec.add(m.group(1).replace("$USER_HOME$", HOME), prod, int(ts.group(1)) / 1000 if ts else None)


def _cwd(jsonl, lines):
    try:
        with open(jsonl, encoding="utf-8", errors="replace") as f:
            for _ in range(lines):
                m = re.search(r'"cwd"\s*:\s*"((?:[^"\\]|\\.)*)"', f.readline())
                if m:
                    return json.loads('"' + m.group(1) + '"')
    except (OSError, ValueError):
        pass
    return None


def agents(rec):
    """命令行编程代理：Claude Code、Codex。"""
    claude = [c for c in (os.environ.get("CLAUDE_CONFIG_DIR"), os.path.join(HOME, ".claude")) if c]
    for cfg in [HOME] + claude:
        try:
            with open(os.path.join(cfg, ".claude.json"), encoding="utf-8") as f:
                for p in json.load(f).get("projects") or {}:
                    rec.add(p, "Claude Code")
        except (OSError, ValueError, AttributeError):
            pass
    for c in claude:
        for pdir in glob.glob(os.path.join(c, "projects", "*")):
            logs = sorted(glob.glob(os.path.join(pdir, "*.jsonl")), key=os.path.getmtime)
            if logs:
                rec.add(_cwd(logs[-1], 30), "Claude Code", os.path.getmtime(logs[-1]), len(logs))
    files = []  # 设置过 CODEX_HOME 的话，新旧两个位置都可能有记录
    for codex in dict.fromkeys(c for c in (os.environ.get("CODEX_HOME"), os.path.join(HOME, ".codex")) if c):
        for sub in ("sessions", "archived_sessions"):
            files += glob.glob(os.path.join(codex, sub, "**", "*.jsonl"), recursive=True)
    for f in sorted(files, key=os.path.getmtime)[-3000:]:
        rec.add(_cwd(f, 3), "Codex", os.path.getmtime(f))


def collect_recents():
    rec = Recents()
    for fn in (vscode_family, jetbrains, agents):
        try:
            fn(rec)
        except Exception:  # 某个工具的记录格式变了，不影响其它
            pass
    return rec.result()


SYS_FILE = re.compile(r"^(ntuser|desktop\.ini|thumbs\.db|\.ds_store|pagefile|hiberfil|swapfile|dumpstack|bootmgr|"
                      r"bootnxt|iconcache|\.localized)", re.I)


def quick(path):
    st = walk(path, set(), cap=150000)
    return {"size": st["size"], "files": st["files"], "mtime": st["mtime"] or None}


def sample(path, maxd=3, limit=8):
    out, queue = [], [(path, 0)]
    while queue and len(out) < limit:
        q, d = queue.pop(0)
        dirs, files = listdir(q)
        if not dirs or d >= maxd:
            out.append(os.path.relpath(q, path) + ("（%d 个文件）" % len(files) if files else ""))
            continue
        queue.extend((x.path, d + 1) for x in dirs)
    return out


def mojibake(name):
    """UTF-8 名字被当成 GBK / Latin-1 解码后写盘产生的乱码；能还原就返回原名。"""
    for enc in ("gbk", "cp1252", "latin-1"):
        try:
            fixed = name.encode(enc).decode("utf-8")
        except (UnicodeError, LookupError):
            continue
        if fixed != name and re.search(r"[^\x00-\x7f]", fixed):
            return fixed
    return None


def collect_anomalies(cfg):
    out, seen = [], set()
    bases = [p for p, _ in cfg["roots"]]
    for root in list(bases):
        dirs, _ = listdir(root)
        bases += [d.path for d in (dirs or [])[:300]]
    for base in bases:
        dirs, _ = listdir(base)
        for d in dirs or []:
            if d.path in seen:
                continue
            seen.add(d.path)
            fixed = mojibake(d.name)
            esc = urllib.parse.unquote(d.name.replace("%%", "%")) if re.search(r"%[0-9A-Fa-f]{2}", d.name) else None
            if fixed:
                target = os.path.join(base, fixed)
                out.append(dict({"type": "乱码目录", "path": d.path, "decoded": target,
                                 "target_exists": os.path.isdir(target), "children": sample(d.path),
                                 "note": "某个程序把 UTF-8 路径当成 GBK / Latin-1 写盘了，内容本该在“本该在”的位置"},
                                **quick(d.path)))
            elif esc and esc != d.name and re.search(r"[^\x00-\x7f]", esc):
                out.append(dict({"type": "转义残留目录", "path": d.path, "decoded": os.path.join(base, esc),
                                 "target_exists": os.path.isdir(os.path.join(base, esc)),
                                 "children": sample(d.path), "note": "目录名是被 URL / 命令行转义过的文字"},
                                **quick(d.path)))
    if WINDOWS:
        letters = [c for c in string.ascii_lowercase if os.path.isdir(c + ":\\")]
        for root, _ in cfg["roots"]:
            if not re.match(r"^[A-Za-z]:\\$", root):
                continue
            for name in letters + ["usr", "tmp"]:
                p = os.path.join(root, name)
                if not os.path.isdir(p) or os.path.islink(p):
                    continue
                if name == "usr" and not (os.path.isdir(os.path.join(p, "share")) or os.path.isdir(os.path.join(p, "bin"))):
                    continue
                out.append(dict({"type": "疑似路径误转换", "path": p, "children": sample(p),
                                 "note": "Git Bash / MSYS 里的 /%s/… 路径被原生程序当成了相对路径。"
                                         "如果是你自己建的目录，可以忽略" % name}, **quick(p)))
    places = [(cfg["home"], "用户主目录")] if cfg["home_scanned"] else []
    if WINDOWS:
        places += [(p, p + " 根目录") for p, _ in cfg["roots"] if re.match(r"^[A-Za-z]:\\$", p)]
    for base, label in places:
        _, files = listdir(base)
        loose = []
        for f in files or []:
            if SYS_FILE.match(f.name) or (base == cfg["home"] and f.name.startswith(".")):
                continue
            try:
                s = f.stat(follow_symlinks=False)
            except OSError:
                continue
            loose.append({"name": f.name, "size": s.st_size, "mtime": s.st_mtime})
        if loose:
            loose.sort(key=lambda x: -x["size"])
            out.append({"type": "散落文件", "path": base, "label": label, "count": len(loose),
                        "size": sum(x["size"] for x in loose), "files": loose[:60]})
    nm = os.path.join(cfg["home"], "node_modules")
    if cfg["home_scanned"] and os.path.isdir(nm) and os.path.isfile(os.path.join(cfg["home"], "package.json")):
        out.append(dict({"type": "主目录 npm 残留", "path": nm,
                         "note": "在用户主目录直接运行 npm install 留下的 package.json + node_modules"}, **quick(nm)))
    return out
