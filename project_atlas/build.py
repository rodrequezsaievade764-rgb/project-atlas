# -*- coding: utf-8 -*-
"""生成结果：把条目和统计合成总览页面 project-atlas.html、清单 projects.csv（可选 atlas.json）。"""
import csv
import json
import os
import re
import time
from collections import Counter, defaultdict

from . import __version__
from .scan import norm, under

DAY = 86400
WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
DOWNLOAD = re.compile(r"(-dl|download|downloads|install|installer|setup|安装包?)$", re.I)
HOSTED = re.compile(r"(github\.com|gitlab\.com|gitee\.com|bitbucket\.org|codeberg\.org)[:/]+([^/\s]+)/", re.I)
NO_DUP = {"tmp", "temp", ".tmp", "backups", "backup", "_backup", "research", "_review", "tools", "package", "cli",
          "web", "plugins", "workspace", "skills", "scripts", "app", "data", "src", "test", "tests", "docs"}
LABELS = {"broken": "本地文件夹（空 .git）", "untrusted": "git 仓库（属主不同，未读取）",
          "unavailable": "git 仓库（没装 git，未读取）", "skipped": "git 仓库（按设置未读取）",
          "worktree": "git 工作树", "local": "本地 git（无远端）", "localremote": "本地 git（远端在本机）",
          "own": "自己的仓库", "other": "别人的仓库（克隆）", "remote": "有远端的仓库", "otherhost": "克隆（其他平台）",
          "src": "下载的源码", "folder": "本地文件夹"}


def origin_of(name, path, g, cfg):
    """返回 (代码, 显示文字)。"""
    if g is not None:
        for k in ("broken", "untrusted", "unavailable", "skipped"):
            if g.get(k):
                return k, LABELS[k]
        if g.get("worktree_of"):
            return "worktree", LABELS["worktree"]
        url = g.get("remote") or ""
        if not url:
            return "local", LABELS["local"]
        if re.match(r"^([A-Za-z]:[/\\]|/|\.\.?[/\\]|file:)", url):
            return "localremote", LABELS["localremote"]
        hits = HOSTED.findall(url)
        if hits:
            owner = hits[-1][1].lower()
            if cfg["github_users"]:
                return ("own", LABELS["own"]) if owner in cfg["github_users"] else ("other", LABELS["other"])
            host = {"github": "GitHub", "gitlab": "GitLab", "gitee": "Gitee", "bitbucket": "Bitbucket",
                    "codeberg": "Codeberg"}.get(hits[-1][0].split(".")[0].lower(), hits[-1][0])
            return "remote", "%s 上 %s 的仓库" % (host, hits[-1][1])
        return "otherhost", LABELS["otherhost"]
    if re.search(r"[-_](main|master)$", name, re.I) or "_download" in path.lower():
        return "src", LABELS["src"]
    return "folder", LABELS["folder"]


def type_of(e):
    if e["kind"] == "collection":
        return e["ctype"]
    mk = set(e["markers"])
    if "Obsidian 笔记库" in mk:
        return "笔记库"
    if DOWNLOAD.search(e["name"]):
        return "下载/安装包"
    if mk & {"素材/作品", "创作工程"}:
        return "作品/素材"
    return "项目"


def status_of(t, now):
    if not t:
        return "未知"
    d = (now - t) / DAY
    return "活跃" if d <= 7 else "近期" if d <= 30 else "休眠" if d <= 90 else "冷"


def risk_of(t, code, g):
    """own = 自己的改动没有异地备份；mod = 别人仓库上的本地改动；unknown = 分不清是谁的仓库但有未保存改动。"""
    if t not in ("项目", "作品/素材", "笔记库") or not g or "branch" not in g:
        return None
    changed = bool(g.get("dirty") or g.get("unpushed"))
    if code in ("local", "localremote") or (code == "own" and changed):
        return "own"
    if code == "other" and g.get("dirty"):
        return "mod"
    if code in ("remote", "otherhost") and changed:
        return "unknown"
    return None


def advice_of(t, st, code, risk):
    if risk == "own":
        return "先提交，再推送到远端或做一份异地备份"
    if risk == "mod":
        return "更新这个仓库前，先备份你的本地改动"
    if risk == "unknown":
        return "确认这些改动要不要保留"
    if t == "临时/测试":
        return "近期在用，先别动" if st == "活跃" else "可清理（需确认）"
    if t == "备份/归档":
        return "核对后只留需要的版本"
    if t == "自动生成的会话目录":
        return "保留" if st == "活跃" else "旧的可清理（需确认）"
    if t == "研究/审查":
        return "可打包归档" if st in ("休眠", "冷") else "保留"
    if t == "下载/安装包":
        return "装好后可删"
    if code in ("other", "src") and st in ("休眠", "冷"):
        return "不用可删（能重新下载）"
    return "可归档" if st == "冷" else "保留"


def dup_key(name):
    k = re.sub(r"[-_](main|master)$", "", name.lower())
    return None if k in NO_DUP else k


def root_of(path, cfg):
    hits = [p for p, _ in cfg["roots"] if norm(path) == norm(p) or under(norm(path), norm(p))]
    return max(hits, key=len) if hits else "其他位置"


def group_of(e, cfg):
    if cfg["groups"]:
        low = e["path"].lower()
        for g in cfg["groups"]:
            if any(str(k).lower() in low for k in g["keywords"]):
                return g["name"]
        return "其他（未归类）"
    return e.get("container") or os.path.dirname(e["path"])


def build_rows(org, results, cfg, now):
    counts = Counter(dup_key(e["name"]) for e in org["entries"] if type_of(e) != "临时/测试")
    rows = []
    for e in org["entries"]:
        a = results.get(e["path"], {"pending": True})
        g = a.get("git")
        t = type_of(e)
        code, label = origin_of(e["name"], e["path"], g, cfg)
        last = max(a.get("mtime") or 0, (g or {}).get("last_commit") or 0, (e.get("recent") or {}).get("last") or 0)
        st = status_of(last, now)
        risk = risk_of(t, code, g)
        issues = []
        if g:
            if g.get("broken"):
                issues.append("空的 .git 目录（实际没有版本管理）")
            elif g.get("untrusted"):
                issues.append("git 不信任这个目录（属主不同），没读状态")
            elif "branch" in g:
                if g.get("dirty") is None:
                    issues.append("git 状态读取超时 / 失败")
                elif g["dirty"]:
                    issues.append("%s %d 个" % ("本地改动" if code == "other" else "未提交改动", g["dirty"]))
                if g.get("unpushed"):
                    issues.append("未推送提交 %d 个" % g["unpushed"])
                if code == "local":
                    issues.append("git 无远端备份")
                elif code == "localremote":
                    issues.append("远端在本机，无异地备份")
        k = dup_key(e["name"])
        if k and counts[k] > 1:
            issues.append("同名副本 ×%d" % counts[k])
        if a.get("pending"):
            issues.append("未统计完（超出时限）")
        if a.get("error"):
            issues.append("统计出错")
        if a.get("capped"):
            issues.append("文件太多，大小为下限")
        rows.append({"name": e["name"], "path": e["path"], "drive": root_of(e["path"], cfg), "group": group_of(e, cfg),
                     "type": t, "origin": label, "origin_code": code, "risk": risk, "langs": a.get("langs") or [],
                     "markers": e["markers"], "size": a.get("size"), "files": a.get("files"),
                     "capped": a.get("capped", False), "buckets": a.get("buckets") or {}, "last": last or None,
                     "status": st, "issues": issues, "advice": advice_of(t, st, code, risk), "desc": a.get("desc") or "",
                     "container": e.get("container"), "git": g, "recent": e.get("recent"), "parent": e.get("parent"),
                     "child_count": e.get("child_count", 0), "children": (e.get("children") or [])[:150],
                     "nested_git": (a.get("nested_git") or [])[:30]})
    dups = defaultdict(list)
    for r in rows:
        k = dup_key(r["name"])
        if k and counts[k] > 1 and r["type"] != "临时/测试":
            dups[r["name"].lower()].append(r["path"])
    return rows, [{"name": k, "paths": v} for k, v in sorted(dups.items())]


def write_csv(rows, path):
    cols = ["名称", "路径", "分组", "类型", "来源", "技术栈", "大小(MB)", "文件数", "最后活动", "状态", "Git分支", "远端",
            "未提交", "未推送", "问题", "建议", "说明"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in sorted(rows, key=lambda r: (r["group"], r["path"].lower())):
            g = r["git"] or {}
            w.writerow([r["name"], r["path"], r["group"], r["type"], r["origin"], " / ".join(r["langs"]),
                        round((r["size"] or 0) / 2 ** 20, 1), r["files"] or "",
                        time.strftime("%Y-%m-%d", time.localtime(r["last"])) if r["last"] else "", r["status"],
                        g.get("branch") or "", g.get("remote") or "", g.get("dirty") or "", g.get("unpushed") or "",
                        "；".join(r["issues"]), r["advice"], r["desc"]])


def _read(name):
    with open(os.path.join(WEB, name), encoding="utf-8") as f:
        return f.read()


def build(cfg, raw, org, results, anomalies, out_dir, want_json=False):
    now = time.time()
    rows, dups = build_rows(org, results, cfg, now)
    data = {"generated": now, "version": __version__, "sep": os.sep, "roots": [p for p, _ in cfg["roots"]],
            "group_mode": "custom" if cfg["groups"] else "location", "scan": raw["stats"], "rows": rows, "dups": dups,
            "containers": org["containers"], "panorama": org["panorama"], "stale": org["stale"],
            "anomalies": anomalies, "apps": raw["apps"], "skipped": raw["skipped"]}
    blob = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    js = _read("app_core.js") + "\n" + _read("app_views.js")
    html = _read("template.html").replace("__APP_JS__", js).replace("__DATA__", blob)
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "project-atlas.html")
    with open(out + ".tmp", "w", encoding="utf-8") as f:
        f.write(html)
    os.replace(out + ".tmp", out)
    files = [out, os.path.join(out_dir, "projects.csv")]
    write_csv(rows, files[1])
    if want_json:
        files.append(os.path.join(out_dir, "atlas.json"))
        with open(files[2], "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
    return rows, files
