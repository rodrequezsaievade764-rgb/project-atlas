# -*- coding: utf-8 -*-
"""配置：默认值 → atlas.config.json → 命令行参数。"""
import json
import os
import string
import tempfile

from .scan import WINDOWS, norm, under

DEFAULTS = {
    "roots": [],              # 留空 = 自动：Windows 为所有本地固定磁盘 + 用户主目录；macOS / Linux 为用户主目录
    "max_depth": 7,           # 普通根目录往下扫几层
    "system_drive_depth": 3,  # Windows 系统盘只扫这么多层（系统目录本来就跳过）
    "home_depth": 6,          # 用户主目录往下扫几层
    "exclude": [],            # 不扫描的目录
    "github_users": [],       # 你的 GitHub / GitLab / Gitee 用户名或组织名，用来认出“自己的仓库”
    "groups": [],             # 自定义产品线：[{"name": "博客", "keywords": ["blog", "hexo"]}]
    "recents": True,          # 读取编辑器 / 编程代理的“最近打开”记录
    "anomalies": True,        # 检查乱码目录、散落文件等
    "git": True,              # 读取 git 状态（只读命令）
    "workers": 6,
    "discover_limit_s": 300,
    "analyze_limit_s": 900,
}


def fixed_drives():
    """Windows 本地固定磁盘（不含 U 盘、网络盘、光驱）。"""
    import ctypes
    k32 = ctypes.windll.kernel32
    mask = k32.GetLogicalDrives()
    out = []
    for i, letter in enumerate(string.ascii_uppercase):
        if mask >> i & 1:
            root = letter + ":\\"
            if k32.GetDriveTypeW(ctypes.c_wchar_p(root)) == 3:
                out.append(root)
    return out


def default_roots(cfg, home):
    if not WINDOWS:
        return [(home, cfg["home_depth"])]
    sysdrive = (os.environ.get("SystemDrive") or "C:").rstrip("\\") + "\\"
    roots = [(d, cfg["system_drive_depth"] if d.lower() == sysdrive.lower() else cfg["max_depth"])
             for d in fixed_drives()]
    return roots + [(home, cfg["home_depth"])]


def load(config_path=None, overrides=None):
    cfg = dict(DEFAULTS)
    path = config_path or ("atlas.config.json" if os.path.isfile("atlas.config.json") else None)
    if path:
        with open(path, encoding="utf-8") as f:
            user = json.load(f)
        cfg.update({k: v for k, v in user.items() if not k.startswith("_")})
        cfg["config_file"] = os.path.abspath(path)
    for k, v in (overrides or {}).items():
        if v is None:
            continue
        cfg[k] = list(cfg.get(k) or []) + list(v) if k == "exclude" else v
    return finalize(cfg)


def finalize(cfg):
    home = os.path.expanduser("~")
    roots = []
    for r in cfg["roots"] or []:
        if isinstance(r, (list, tuple)):
            roots.append((os.path.abspath(os.path.expanduser(r[0])), int(r[1])))
        else:
            roots.append((os.path.abspath(os.path.expanduser(r)), cfg["max_depth"]))
    roots = roots or default_roots(cfg, home)
    final, seen = [], set()
    for p, d in roots:
        n = norm(p)
        if n in seen:
            continue
        # 已经被另一个根目录在深度范围内完整覆盖的，不再单独扫
        if any(under(n, norm(q)) and e >= n.count(os.sep) - norm(q).rstrip(os.sep).count(os.sep) + d
               for q, e in roots):
            continue
        seen.add(n)
        final.append((p, d))
    home_n = norm(home)
    skip = {}
    for var in ("TEMP", "TMP", "TMPDIR"):
        if os.environ.get(var):
            skip[norm(os.environ[var])] = "系统临时目录"
    skip[norm(tempfile.gettempdir())] = "系统临时目录"
    for p in cfg["exclude"] or []:
        skip[norm(os.path.abspath(os.path.expanduser(p)))] = "用户排除"
    sysroot = (os.environ.get("SystemDrive") or "C:").rstrip("\\") + "\\" if WINDOWS else "/"
    cfg.update(roots=final, home=home, home_norm=home_n, system_roots={norm(sysroot)}, skip_paths=skip,
               home_scanned=any(norm(p) == home_n for p, _ in final),
               never_project={norm(p) for p, _ in final} | {home_n},
               github_users=[str(u).lower() for u in cfg["github_users"] or []],
               groups=[g for g in cfg["groups"] or [] if g.get("name") and g.get("keywords")])
    return cfg
