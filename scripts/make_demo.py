# -*- coding: utf-8 -*-
"""造一棵虚构的示例目录树，用来演示和截图（README 里的截图就是这样生成的）。

用法：
    python scripts/make_demo.py demo-tree
    python -m project_atlas demo-tree -c demo-tree/atlas.config.json --no-recents --open
"""
import json
import os
import subprocess
import sys
import time

DAY = 86400
SEP = os.sep
IDENTITY = {"GIT_AUTHOR_NAME": "Demo", "GIT_AUTHOR_EMAIL": "demo@example.invalid",
            "GIT_COMMITTER_NAME": "Demo", "GIT_COMMITTER_EMAIL": "demo@example.invalid"}


def js(obj):
    return json.dumps(obj, ensure_ascii=False)


def put(root, rel, text="", size=None, age=0.0):
    p = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        if size:
            f.truncate(size)  # 占位大文件，写入很快
        else:
            f.write(text.encode("utf-8"))
    t = time.time() - age * DAY
    os.utime(p, (t, t))


def repo(path, age, remote=None, pushed=True, dirty=()):
    when = "%d +0000" % (time.time() - age * DAY)
    env = dict(os.environ, GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when, **IDENTITY)

    def git(*args):
        subprocess.run(["git"] + list(args), cwd=path, env=env, check=True, capture_output=True)

    git("init", "-q")
    git("add", "-A")
    git("commit", "-q", "-m", "first version")
    if remote:
        git("remote", "add", "origin", remote)
        if pushed:
            git("update-ref", "refs/remotes/origin/HEAD", "HEAD")
    for rel in dirty:
        put(path, rel, "// work in progress\n")


def make(root):
    j = os.path.join
    put(root, "work/shop-web/package.json", js({"name": "shop-web", "description": "小店前台：商品页、购物车和下单"}), age=3)
    put(root, "work/shop-web/.gitignore", "node_modules/\n", age=3)
    put(root, "work/shop-web/src/App.tsx", "export default function App() { return null }\n", age=3)
    put(root, "work/shop-web/node_modules/react/index.js", size=180 * 2 ** 20, age=40)
    repo(j(root, "work", "shop-web"), 3, "https://github.com/your-name/shop-web.git", pushed=False,
         dirty=["src/Cart.tsx", "src/Checkout.tsx"])
    put(root, "work/api-server/pyproject.toml", '[project]\nname = "api-server"\ndescription = "订单和库存接口"\n', age=12)
    put(root, "work/api-server/app/main.py", "print('ok')\n", age=12)
    repo(j(root, "work", "api-server"), 12, "https://github.com/your-name/api-server.git")
    put(root, "work/mobile-app/pubspec.yaml", "name: mobile_app\ndescription: 会员小程序的移动端\n", age=150)
    put(root, "work/mobile-app/lib/main.dart", "void main() {}\n", age=150)
    put(root, "personal/blog/package.json", js({"name": "blog", "description": "个人博客"}), age=20)
    put(root, "personal/blog/source/hello.md", "# Hello\n", age=20)
    repo(j(root, "personal", "blog"), 20, dirty=["source/draft.md"])
    put(root, "personal/notes/.obsidian/app.json", "{}", age=1)
    put(root, "personal/notes/收件箱.md", "- [ ] 整理照片\n", age=1)
    put(root, "personal/videos/japan-trip/japan-trip.prproj", size=3 * 2 ** 20, age=60)
    put(root, "personal/videos/japan-trip/footage/day1.mp4", size=900 * 2 ** 20, age=60)
    put(root, "learning/rust-book/Cargo.toml", '[package]\nname = "rust-book"\ndescription = "跟着书写的练习"\n', age=95)
    put(root, "learning/rust-book/src/main.rs", "fn main() {}\n", age=95)
    for i, name in enumerate(("two_sum", "binary_search", "dijkstra", "lru_cache")):
        put(root, "learning/algorithms/%s.py" % name, "def solve(): pass\n", age=40 + i)
    put(root, "opensource/markdown-parser/package.json", js({"name": "markdown-parser"}), age=200)
    put(root, "opensource/markdown-parser/src/index.js", "module.exports = {}\n", age=200)
    repo(j(root, "opensource", "markdown-parser"), 200, "https://github.com/someone-else/markdown-parser.git",
         dirty=["src/table.js"])
    put(root, "ml/sentiment-model/requirements.txt", "torch\n", age=33)
    put(root, "ml/sentiment-model/train.py", "print('train')\n", age=33)
    put(root, "ml/sentiment-model/models/model.safetensors", size=420 * 2 ** 20, age=33)
    put(root, "old-laptop/shop-web/package.json", js({"name": "shop-web"}), age=400)
    put(root, "backups/blog-2023/package.json", "{}", age=300)
    put(root, "backups/api-server-v1/pyproject.toml", "", age=280)
    for tag in ("a1b2c3d4", "e5f6a7b8", "9c0d1e2f"):
        put(root, "tmp/build-%s/out.js" % tag, "", size=12 * 2 ** 20, age=50)
    put(root, "research/llm-papers/notes.md", "# 读论文笔记\n", age=70)
    put(root, "research/llm-papers/plot.py", "print('plot')\n", age=70)
    for word in ("照片", "资料", "文档"):  # 一个乱码目录：UTF-8 名字被当成 GBK 解码后写盘
        try:
            put(root, word.encode("utf-8").decode("gbk") + "/readme.txt", "", age=100)
            break
        except (UnicodeError, OSError):
            continue
    groups = [{"name": n, "keywords": [SEP + k + SEP]} for n, k in
              (("工作项目", "work"), ("个人", "personal"), ("学习", "learning"), ("开源与参考", "opensource"),
               ("机器学习", "ml"))]
    with open(j(root, "atlas.config.json"), "w", encoding="utf-8") as f:
        json.dump({"github_users": ["your-name"], "groups": groups}, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    target = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "demo-tree")
    if os.path.exists(target) and os.listdir(target):
        sys.exit("目标目录不是空的：%s" % target)
    make(target)
    print("示例目录已生成：" + target)
    print("运行：python -m project_atlas %s -c %s --no-recents --open" % (target, os.path.join(target, "atlas.config.json")))
