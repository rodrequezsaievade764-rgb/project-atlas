# -*- coding: utf-8 -*-
"""把扫描到的候选目录归并成「条目」。

1. 备份 / 临时 / 研究 / 技能合集这类“同类一大堆”的目录，按路径上最外层命中的那一级折叠成一个合集；
2. 有工程标记（.git、package.json、pyproject.toml……）的目录 = 项目；
3. 只有散装代码 / AI·IDE 配置的目录：名字像分组（projects、代码、编号分类……）或下面有 ≥3 个独立项目 → 当分组，
   否则当项目，里面的散装子目录并入它；
4. 编辑器最近打开过、但扫描没覆盖到的目录补进来；已经不存在的记为失效记录。
"""
import os
import re

from .rules import CATEGORY, CONTAINER, GENERIC, collect_type
from .scan import norm, under

SEP = os.sep
RAND = re.compile(r"^(.+?)[-_]([a-z0-9]{6,12})$", re.I)
TEMP_HINT = re.compile(r"[\\/](temp|tmp)[\\/]|~1[\\/]temp", re.I)
SHELL_DIRS = ("Desktop", "Documents", "Downloads", "Pictures", "Videos", "Music", "Movies")


def nearest(n, table):
    best = None
    for k in table:
        if under(n, k) and (best is None or len(k) > len(best)):
            best = k
    return best


def collection_of(path, cfg, terminal):
    """路径上（根目录以下）最外层命中合集规则的那一级。项目自己的名字只认明确的副本 / 临时写法。"""
    root = nearest(norm(path), cfg["never_project"])
    if root is None:
        return None, None
    cut = len(root.rstrip(SEP))
    parts = path[cut + 1:].split(SEP) if len(path) > cut + 1 else []
    acc = path[:cut]
    for i, comp in enumerate(parts):
        acc = acc + SEP + comp
        typ = collect_type(comp, self_only=terminal and i == len(parts) - 1)
        if typ:
            return acc, typ
    return None, None


def random_clusters(cands):
    """同一目录下 ≥3 个“同前缀 + 随机后缀”的兄弟目录（临时目录生成器的产物）。"""
    groups = {}
    for c in cands:
        p = c["path"].rstrip(SEP)
        m = RAND.match(os.path.basename(p))
        if m and re.search(r"\d", m.group(2)):
            groups.setdefault((norm(os.path.dirname(p)), m.group(1).lower()), []).append(norm(p))
    return {x for v in groups.values() if len(v) >= 3 for x in v}


def new_entry(path, kind, markers=(), ctype=None, parent=None):
    return {"path": path, "name": os.path.basename(path.rstrip(SEP)) or path, "kind": kind, "ctype": ctype,
            "markers": list(markers), "children": [], "parent": parent, "recent": None}


def absorb(e, c):
    if norm(c["path"]) != norm(e["path"]):
        e["children"].append(c["path"][len(e["path"].rstrip(SEP)) + 1:])


def merge_recent(target, r):
    cur = target.get("recent") or {"sources": {}, "last": 0, "paths": []}
    for s, k in r["sources"].items():
        cur["sources"][s] = cur["sources"].get(s, 0) + k
    cur["last"] = max(cur["last"] or 0, r["last"] or 0)
    cur["paths"].append(r["path"])
    target["recent"] = cur


def guess(path, pool):
    """猜失效路径现在在哪：先按最后两级目录名匹配，再按目录名匹配（通用名不猜）。"""
    parts = norm(path).split(SEP)
    tail2 = [p for p in pool if norm(p).split(SEP)[-2:] == parts[-2:]]
    if tail2 or parts[-1] in GENERIC:
        return tail2[:3]
    return [p for p in pool if norm(p).split(SEP)[-1] == parts[-1]][:3]


def organize(raw, recents, cfg):
    cands = sorted(raw["candidates"], key=lambda c: (c["path"].count(SEP), norm(c["path"])))
    keys = [norm(c["path"]) for c in cands]
    rand = random_clusters(cands)
    entries, containers = {}, {}
    for c in cands:
        p, n = c["path"], norm(c["path"])
        anc = nearest(n, entries)
        cr, typ = collection_of(p, cfg, c["kind"] == "terminal")
        if cr is None and n in rand:
            cr, typ = p, "临时/测试"
        if anc:
            inside = cr is not None and under(norm(cr), anc)
            if entries[anc]["kind"] == "collection" or c["kind"] == "weak" or inside:
                absorb(entries[anc], c)
                continue
        parent = entries[anc]["path"] if anc else None
        if cr:
            key = norm(cr)
            if key not in entries:
                entries[key] = new_entry(cr, "collection", ctype=typ, parent=parent)
            absorb(entries[key], c)
            continue
        if c["kind"] == "terminal":
            entries[n] = new_entry(p, "terminal", c["markers"], parent=parent)
            continue
        below = [k for k in keys if under(k, n)]
        loose = sum(int(m.split("×")[1]) for m in c["markers"] if m.startswith("散装代码×"))
        real = {k[len(n.rstrip(SEP)) + 1:].split(SEP)[0] for k in below}
        real = {b for b in real if b not in GENERIC and not b.startswith(".")}
        name = os.path.basename(p.rstrip(SEP))
        if CATEGORY.match(name) or (below and (CONTAINER.search(name) or (loose < 10 and len(real) >= 3))):
            containers[n] = {"path": p, "loose_code": loose, "markers": c["markers"], "recent": None}
            continue
        entries[n] = new_entry(p, "weak", c["markers"], parent=parent)

    stale = []
    shell = {norm(os.path.join(cfg["home"], d)) for d in SHELL_DIRS}
    for r in sorted(recents, key=lambda r: r["path"].count(SEP)):
        n = norm(r["path"])
        if not r["exists"]:
            if not TEMP_HINT.search(r["path"]):
                stale.append(dict(r))
            continue
        if n in cfg["never_project"] or any(n == s or under(n, s) for s in cfg["skip_paths"]):
            continue
        own = n if n in entries else nearest(n, entries)
        if own:
            merge_recent(entries[own], r)
        elif n in containers:
            merge_recent(containers[n], r)
        elif n in shell or any(under(k, n) for k in entries):
            containers.setdefault(n, {"path": r["path"], "loose_code": 0, "markers": [], "recent": None})
            merge_recent(containers[n], r)
        else:
            entries[n] = new_entry(r["path"], "recent", ["最近打开"])
            merge_recent(entries[n], r)
    for e in entries.values():
        cont = nearest(norm(e["path"]), containers)
        e["container"] = containers[cont]["path"] if cont else os.path.dirname(e["path"].rstrip(SEP))
        e["child_count"] = len(e["children"])
        e["children"] = sorted(e["children"])[:300]
    pool = list(dict.fromkeys(x["path"] for x in list(entries.values()) + list(containers.values())
                              + raw["candidates"] if os.path.isdir(x["path"])))
    for s in stale:
        s["guess"] = guess(s["path"], pool)
    return {"entries": sorted(entries.values(), key=lambda e: norm(e["path"])),
            "containers": sorted(containers.values(), key=lambda c: norm(c["path"])),
            "stale": stale, "panorama": panorama(raw, entries, containers, cfg)}


def panorama(raw, entries, containers, cfg):
    """每个根目录和分组目录下的一级子目录各是什么，保证每个目录都有交代。"""
    apps = {norm(a["path"]): a["kind"] for a in raw["apps"]}
    skipped = {norm(s["path"]): s["why"] for s in raw["skipped"]}
    parents = [p for p, _ in cfg["roots"]] + [c["path"] for c in containers.values()]
    out = []
    for parent in dict.fromkeys(parents):
        try:
            names = sorted(os.listdir(parent), key=str.lower)
        except OSError:
            continue
        rows = []
        for nm in names:
            full = os.path.join(parent, nm)
            if not os.path.isdir(full):
                continue
            n = norm(full)
            if n in entries:
                st = "项目:" + (entries[n]["ctype"] or "项目")
            elif n in containers:
                st = "分组"
            elif nearest(n, entries):
                st = "在项目内"
            elif n in apps:
                st = "软件/环境" if apps[n] == "app" else "Python 环境"
            elif n in skipped:
                st = "跳过:" + skipped[n]
            else:
                inner = sum(1 for k in entries if under(k, n))
                if inner:
                    st = "含 %d 个项目" % inner
                elif any(under(a, n) for a in apps):
                    st = "软件/环境(在子目录)"
                else:
                    st = "其他(资料/媒体/程序数据)"
            rows.append({"name": nm, "status": st})
        out.append({"parent": parent, "rows": rows})
    return out
