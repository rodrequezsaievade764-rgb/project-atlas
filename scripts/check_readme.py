# -*- coding: utf-8 -*-
"""文档核对：README 里写的数字是否和代码一致。

    python scripts/check_readme.py          # 只检查，不一致返回 1
    python scripts/check_readme.py --write  # 顺手把「目录」一节的行数改成实际值

检查项：每个文件的行数、标志文件数量、测试数量、版本号、配置默认值、体积。

本来应该是 `python -m unittest discover` 之后顺手跑一下的东西——所以放进 CI，
改了代码忘了改 README，CI 会直接报红，不靠人记。
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
README = ("README.md", "README.en.md")


def out(cmd, **kw):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, **kw).stdout


def tracked():
    return [f for f in out(["git", "ls-files"]).split() if os.path.isfile(os.path.join(ROOT, f))]


def wc(path):
    with open(os.path.join(ROOT, path), "rb") as f:
        return f.read().count(b"\n")


def run_tests():
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=ROOT,
                       capture_output=True, text=True)
    m = re.search(r"Ran (\d+) tests?", r.stderr + r.stdout)
    return (int(m.group(1)) if m else None, r.returncode == 0), r.stderr


def kib(paths):
    return sum(os.path.getsize(os.path.join(ROOT, p)) for p in paths) / 1024.0


def _show(v):
    """README 里写的默认值：布尔用小写 true / false。"""
    return ("true" if v else "false") if isinstance(v, bool) else str(v)


def write_line_counts(files):
    """把「目录」代码块里每行开头的行号改成实际行数。"""
    for name in README:
        path = os.path.join(ROOT, name)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        blocks = re.findall(r"```text\n(.*?)```", text, re.S)
        if not blocks:
            continue
        block = blocks[-1]
        new = block
        for f in files:
            new = re.sub(r"(?m)^(\s*\S+\s+)(\d+)(\s+行)", lambda m, f=f: m.group(1) + str(wc(f)) + m.group(3)
                         if os.path.basename(f) in m.group(1) or f in m.group(1) else m.group(0), new)
            new = re.sub(r"(?m)^(\s*\S+\s+)(\d+)( lines)", lambda m, f=f: m.group(1) + str(wc(f)) + m.group(3)
                         if os.path.basename(f) in m.group(1) or f in m.group(1) else m.group(0), new)
        if new != block:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text.replace(block, new))
            print("已更新 %s 里的行数" % name)


def main(write=False):
    from project_atlas import __version__, config, rules
    files = tracked()
    code = [f for f in files if re.search(r"\.(py|js|html|yml|bat|sh|toml|json|md)$", f)
            and not f.startswith("docs/") and f not in README]
    if write:
        write_line_counts(code)
    errors = []
    for name in README:
        with open(os.path.join(ROOT, name), encoding="utf-8") as f:
            text = f.read()
        # 1) 目录一节的行数
        blocks = re.findall(r"```text\n(.*?)```", text, re.S)
        for line in (blocks[-1].splitlines() if blocks else []):
            m = re.match(r"\s*(\S+)\s+(\d+)\s+(?:行|lines)", line)
            if not m:
                continue
            hit = m.group(1)
            match = [f for f in code if hit in f or f.endswith(hit)]
            if match and int(m.group(2)) != wc(match[0]):
                errors.append("%s：%s 写的是 %s 行，实际 %d 行" % (name, hit, m.group(2), wc(match[0])))
        # 2) 标志文件数量与总数
        for num in re.findall(r"(\d+) 种标志文件|(\d+) marker files", text):
            pass
        for pattern, real, what in ((r"(\d+) 种标志文件", len(rules.TERMINAL), "标志文件"),
                                    (r"(\d+) 种标志扩展名", len(rules.TERMINAL_EXT), "标志扩展名"),
                                    (r"(\d+) marker files", len(rules.TERMINAL), "marker files"),
                                    (r"(\d+) marker extensions", len(rules.TERMINAL_EXT), "marker extensions")):
            for n in re.findall(pattern, text):
                if int(n) != real:
                    errors.append("%s：%s 写的是 %s，实际 %d" % (name, what, n, real))
        for n in re.findall(r"共 (\d+) 种", text):
            total = len(rules.TERMINAL) + len(rules.TERMINAL_EXT)
            if int(n) != total:
                errors.append("%s：正常标志总数写的是 %s，实际 %d" % (name, n, total))
        (n_tests, ok), log = run_tests()
        for n in re.findall(r"Ran (\d+) tests", text):
            if n_tests and int(n) != n_tests:
                errors.append("%s：测试数量写的是 %s，实际 %d" % (name, n, n_tests))
        for n in re.findall(r"(\d+) 个测试", text):
            if n_tests and int(n) != n_tests:
                errors.append("%s：测试数量写的是 %s，实际 %d" % (name, n, n_tests))
        # 3) 版本号
        if __version__ not in text:
            errors.append("%s：没有出现版本号 %s" % (name, __version__))
        # 4) 配置默认值：README 表格里 `` `key` | `默认值` ``
        for key, val in config.DEFAULTS.items():
            if isinstance(val, (list, str)):
                continue
            m = re.search(r"\|\s*`%s`\s*\|\s*`?([\w.]+)`?\s*\|" % re.escape(key), text)
            if m and _show(val) != m.group(1).lower():
                errors.append("%s：%s 的默认值写的是 %s，实际 %s" % (name, key, m.group(1), _show(val)))
    # 5) 体积
    pkg = kib([f for f in files if f.startswith("project_atlas/")])
    shots = kib([f for f in files if f.endswith(".png")])
    for name in README:
        with open(os.path.join(ROOT, name), encoding="utf-8") as f:
            text = f.read()
        for m in re.finditer(r"(\d+\.\d) KiB", text):
            v = float(m.group(1))
            if abs(v - pkg) > 0.6 and abs(v - shots) > 0.6:
                errors.append("%s：体积写的是 %s KiB，实际程序 %.1f / 截图 %.1f" % (name, m.group(1), pkg, shots))
    # 6) 版本唯一来源
    hits = out(["git", "grep", "-n", "-F", '"%s"' % __version__]).strip().splitlines()
    bad = [h for h in hits if "project_atlas/__init__.py" not in h and not h.startswith("README")]
    if bad:
        errors.append("版本号不止一个来源：%s" % bad)
    if errors:
        print("README 和代码不一致（%d 处）：" % len(errors))
        for e in errors:
            print("  - " + e)
        print("\n改完代码请顺手改 README，或者运行 python scripts/check_readme.py --write\n")
        return 1
    print("README 与代码一致：%d 个文件、%d 个测试、%d 种标志（%d 文件 + %d 扩展名）、版本 %s" % (
        len(files), n_tests, len(rules.TERMINAL) + len(rules.TERMINAL_EXT), len(rules.TERMINAL),
        len(rules.TERMINAL_EXT), __version__))
    return 0


if __name__ == "__main__":
    sys.exit(main(write="--write" in sys.argv))
