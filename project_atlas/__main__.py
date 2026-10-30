# -*- coding: utf-8 -*-
"""命令行入口：python -m project_atlas [要扫描的目录 ...]"""
import argparse
import os
import sys
import time
import webbrowser
from pathlib import Path

from . import __version__
from .build import build
from .config import load
from .context import collect_anomalies, collect_recents
from .organize import organize
from .scan import analyze, discover, norm


def parse(argv):
    ap = argparse.ArgumentParser(prog="project-atlas", description="只读扫描本机所有项目，生成一个离线可看的总览页面。")
    ap.add_argument("roots", nargs="*", help="要扫描的目录（不填 = 所有本地磁盘 + 用户主目录）")
    ap.add_argument("-o", "--out", default="output", help="结果输出目录（默认 ./output）")
    ap.add_argument("-c", "--config", help="配置文件（默认读取当前目录下的 atlas.config.json）")
    ap.add_argument("--depth", type=int, help="往下扫描的层数（默认 7，用户主目录 6）")
    ap.add_argument("--exclude", action="append", metavar="DIR", help="不扫描的目录，可重复")
    ap.add_argument("--no-recents", action="store_true", help="不读取编辑器的“最近打开”记录")
    ap.add_argument("--no-git", action="store_true", help="不运行 git 命令")
    ap.add_argument("--json", action="store_true", help="另外输出 atlas.json（原始数据）")
    ap.add_argument("--open", action="store_true", help="完成后用浏览器打开总览页")
    ap.add_argument("--version", action="version", version="%(prog)s " + __version__)
    return ap.parse_args(argv)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    a = parse(argv)
    overrides = {"exclude": a.exclude, "recents": False if a.no_recents else None, "git": False if a.no_git else None}
    if a.roots:
        overrides["roots"] = a.roots
    if a.depth:
        overrides.update(max_depth=a.depth, home_depth=a.depth)
    cfg = load(a.config, overrides)
    out_dir = os.path.abspath(a.out)
    cfg["skip_paths"][norm(out_dir)] = "工具输出目录"
    t0 = time.time()
    print("Project Atlas %s · 只读扫描，不会修改、移动或删除任何文件" % __version__)
    print("扫描范围：" + "，".join("%s（%d 层）" % r for r in cfg["roots"]))
    raw = discover(cfg)
    print("[1/4] 找到 %d 个候选目录（看过 %d 个目录，%.0f 秒）" % (
        len(raw["candidates"]), raw["stats"]["dirs_visited"], raw["stats"]["seconds"]))
    recents = collect_recents() if cfg["recents"] else []
    org = organize(raw, recents, cfg)
    print("[2/4] 归并成 %d 个条目、%d 个分组" % (len(org["entries"]), len(org["containers"])))
    results = analyze(cfg, org["entries"])
    print("[3/4] 已统计大小和 git 状态")
    anomalies = collect_anomalies(cfg) if cfg["anomalies"] else []
    rows, files = build(cfg, raw, org, results, anomalies, out_dir, a.json)
    size = sum(r["size"] or 0 for r in rows) / 2 ** 30
    print("[4/4] 完成：%d 个条目，共 %.1f GB，用时 %.0f 秒" % (len(rows), size, time.time() - t0))
    for f in files:
        print("  " + f)
    if a.open:
        webbrowser.open(Path(files[0]).as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
