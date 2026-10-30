# -*- coding: utf-8 -*-
"""端到端测试：在临时目录里造一棵项目树，跑完整流程，检查分类和输出。只用标准库。"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from project_atlas.__main__ import main  # noqa: E402
from project_atlas.rules import collect_type  # noqa: E402


def touch(path, text="", size=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        if size:
            f.seek(size - 1)
            f.write(b"\0")
        else:
            f.write(text.encode("utf-8"))


def git(cwd, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.invalid")
    subprocess.run(["git"] + list(args), cwd=cwd, env=env, check=True, capture_output=True)


class RulesTest(unittest.TestCase):
    def test_collections(self):
        self.assertEqual(collect_type("backups"), "备份/归档")
        self.assertEqual(collect_type("blog-backup-2024"), "备份/归档")
        self.assertEqual(collect_type("tmp"), "临时/测试")
        self.assertEqual(collect_type("arxiv_scan_2026"), "研究/审查")
        self.assertEqual(collect_type("awesome-agents"), "技能/资料合集")
        self.assertEqual(collect_type("2024-05-01_10-30-00"), "自动生成的会话目录")

    def test_no_false_positives(self):
        for name in ("qr-scanner", "latest", "template", "boldly", "contest", "my-app", "01_工作"):
            self.assertIsNone(collect_type(name), name)

    def test_project_own_name_is_strict(self):
        self.assertIsNone(collect_type("code-review-bot", self_only=True))
        self.assertIsNone(collect_type("test-runner", self_only=True))
        self.assertEqual(collect_type("app-backup", self_only=True), "备份/归档")
        self.assertEqual(collect_type("build-tmp", self_only=True), "临时/测试")


class DescribeTest(unittest.TestCase):
    def test_package_json_unicode_escapes(self):
        from project_atlas.scan import describe
        d = tempfile.mkdtemp(prefix="atlas-desc-")
        try:
            touch(os.path.join(d, "package.json"), json.dumps({"description": "小店前台"}))  # 默认转义成 \uXXXX
            self.assertEqual(describe(d), "小店前台")
        finally:
            shutil.rmtree(d, ignore_errors=True)


class PipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="atlas-test-")
        cls.root = os.path.join(cls.tmp, "disk")
        r = cls.root
        touch(os.path.join(r, "shop-web", "package.json"), '{"name": "shop-web", "description": "A demo web shop"}')
        touch(os.path.join(r, "shop-web", "src", "index.ts"), "export {}")
        touch(os.path.join(r, "shop-web", "node_modules", "left-pad", "package.json"), "{}")
        touch(os.path.join(r, "shop-web", "node_modules", "big.bin"), size=2 * 1024 * 1024)
        touch(os.path.join(r, "work", "api-server", "pyproject.toml"), '[project]\nname = "api"\n')
        touch(os.path.join(r, "work", "api-server", "app.py"), "print(1)\n")
        touch(os.path.join(r, "notes-site", "index.html"), "<h1>hi</h1>")
        touch(os.path.join(r, "notes-site", "app.js"), "console.log(1)")
        touch(os.path.join(r, "backups", "shop-old", "package.json"), "{}")
        touch(os.path.join(r, "backups", "blog-2023", "package.json"), "{}")
        touch(os.path.join(r, "tmp", "run-1", "main.py"), "")
        touch(os.path.join(r, "research", "paper-notes", "notes.md"), "# notes")
        touch(os.path.join(r, "videos", "trip-edit", "draft_content.json"), "{}")
        cls.has_git = shutil.which("git") is not None
        if cls.has_git:
            api = os.path.join(r, "work", "api-server")
            git(api, "init", "-q")
            git(api, "add", "-A")
            git(api, "commit", "-q", "-m", "init")
            touch(os.path.join(api, "new_feature.py"), "x = 1\n")
        try:
            cls.bad = "项目".encode("utf-8").decode("gbk")
            os.makedirs(os.path.join(r, cls.bad, "data"))
        except (UnicodeError, OSError):
            cls.bad = None
        outside = os.path.join(cls.tmp, "outside", "secret-project")
        touch(os.path.join(outside, "package.json"), "{}")
        try:  # 扫描范围内放一个指向范围外项目的符号链接，扫描不应跟过去
            os.symlink(outside, os.path.join(r, "linked-project"), target_is_directory=True)
            cls.link = True
        except (OSError, NotImplementedError):
            cls.link = False
        cls.out = os.path.join(cls.tmp, "out")
        cls.code = main([r, "-o", cls.out, "--json", "--no-recents"])
        with open(os.path.join(cls.out, "atlas.json"), encoding="utf-8") as f:
            cls.data = json.load(f)
        cls.rows = {x["name"]: x for x in cls.data["rows"]}

    @classmethod
    def tearDownClass(cls):
        def unlock(func, path, _):
            os.chmod(path, 0o700)
            func(path)
        shutil.rmtree(cls.tmp, onerror=unlock)

    def test_exit_code(self):
        self.assertEqual(self.code, 0)

    def test_classification(self):
        expect = {"shop-web": "项目", "api-server": "项目", "notes-site": "项目", "backups": "备份/归档",
                  "tmp": "临时/测试", "research": "研究/审查", "trip-edit": "项目"}
        for name, typ in expect.items():
            self.assertIn(name, self.rows, name)
            self.assertEqual(self.rows[name]["type"], typ, name)

    def test_dependencies_are_not_projects(self):
        self.assertNotIn("left-pad", self.rows)
        self.assertNotIn("node_modules", self.rows)
        self.assertGreater(self.rows["shop-web"]["buckets"].get("依赖", 0), 2 * 1024 * 1024 - 1)
        self.assertEqual(self.rows["shop-web"]["desc"], "A demo web shop")

    def test_git_state(self):
        if not self.has_git:
            self.skipTest("git not installed")
        r = self.rows["api-server"]
        self.assertEqual(r["origin_code"], "local")
        self.assertEqual(r["risk"], "own")
        self.assertTrue(any(i.startswith("未提交改动") for i in r["issues"]), r["issues"])
        self.assertIn("git 无远端备份", r["issues"])

    def test_outputs(self):
        with open(os.path.join(self.out, "project-atlas.html"), encoding="utf-8") as f:
            html = f.read()
        self.assertIn('id="data"', html)
        self.assertNotIn("__DATA__", html)
        self.assertNotIn("__APP_JS__", html)
        self.assertTrue(os.path.isfile(os.path.join(self.out, "projects.csv")))

    def test_nothing_outside_the_scanned_root(self):
        root = os.path.normcase(self.root)
        for r in self.data["rows"]:
            self.assertTrue(os.path.normcase(r["path"]).startswith(root), r["path"])

    def test_scan_is_read_only(self):
        self.assertTrue(os.path.isfile(os.path.join(self.root, "tmp", "run-1", "main.py")))
        self.assertTrue(os.path.isdir(os.path.join(self.root, "shop-web", "node_modules")))

    def test_symlinks_are_not_followed(self):
        if not self.link:
            self.skipTest("cannot create symlinks on this system")
        self.assertNotIn("secret-project", self.rows)
        self.assertNotIn("linked-project", self.rows)

    def test_mojibake_detected(self):
        if not self.bad:
            self.skipTest("this filesystem cannot hold the test name")
        hits = [a for a in self.data["anomalies"] if a["type"] == "乱码目录"]
        self.assertTrue(any(a["decoded"].endswith("项目") for a in hits), hits)


if __name__ == "__main__":
    unittest.main()
