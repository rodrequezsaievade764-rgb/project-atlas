# -*- coding: utf-8 -*-
"""分类规则：哪些目录算项目、哪些折叠成合集、哪些直接跳过。

全部是启发式规则，集中放在这里，方便按自己的习惯调整。改完重新扫描一次即可生效。
"""
import re

# ------------------------------------------------------------------ 项目标记
# 目录里出现这些文件 / 子目录 = 项目根目录，扫描到这里就不再往下
TERMINAL = {
    ".git": "git", "package.json": "Node", "pyproject.toml": "Python", "setup.py": "Python",
    "requirements.txt": "Python", "pipfile": "Python", "environment.yml": "Python", "cargo.toml": "Rust",
    "go.mod": "Go", "pom.xml": "Java", "build.gradle": "Java", "build.gradle.kts": "Kotlin",
    "cmakelists.txt": "C/C++", "makefile": "Make", "composer.json": "PHP", "gemfile": "Ruby",
    "pubspec.yaml": "Flutter", "deno.json": "Deno", "mix.exs": "Elixir", "package.swift": "Swift",
    "project.godot": "Godot", "projectsettings": "Unity", "project.config.json": "微信小程序",
    ".obsidian": "Obsidian 笔记库", "dockerfile": "Docker", "docker-compose.yml": "Docker",
    "compose.yaml": "Docker", "tauri.conf.json": "Tauri", "src-tauri": "Tauri",
    "draft_content.json": "剪映草稿", "draft_meta_info.json": "剪映草稿",
}
# 按扩展名识别的工程文件（Xcode 工程本身是目录）
TERMINAL_EXT = {".sln": "C#/.NET", ".csproj": "C#/.NET", ".vcxproj": "C/C++", ".uproject": "Unreal",
                ".xcodeproj": "Xcode", ".xcworkspace": "Xcode"}
# 弱信号：说明“这里可能有代码”，但不停止往下扫
WEAK_MARKERS = {".cursor", ".claude", ".vscode", ".idea", ".windsurf", ".trae", ".kiro", ".codex", ".continue",
                "agents.md", "claude.md", "gemini.md", ".cursorrules", ".windsurfrules"}
CODE_EXT = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".vue", ".svelte", ".go", ".rs", ".java",
            ".kt", ".scala", ".c", ".cc", ".cpp", ".h", ".hpp", ".cs", ".rb", ".php", ".lua", ".swift",
            ".dart", ".ex", ".zig", ".r", ".jl", ".sql", ".html", ".ipynb", ".asm", ".gd",
            ".ps1", ".bat", ".cmd", ".sh"}
SHELL_EXT = {".ps1", ".bat", ".cmd", ".sh"}
CREATIVE_EXT = {".prproj", ".aep", ".drp", ".blend", ".kdenlive", ".veg", ".fcpxml", ".psd", ".kra", ".clip",
                ".fig", ".sketch", ".xd", ".afdesign", ".logicx", ".flp", ".als"}
MEDIA_EXT = {".mp4", ".mov", ".mkv", ".avi", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".wav", ".mp3",
             ".flac", ".srt"}
UNINSTALL = re.compile(r"^(unins\d*|uninstall.*|卸载.*)\.exe$", re.I)

# ------------------------------------------------------------------ 跳过
# 任何层级都不进入：依赖、缓存、版本库内部、回收站
SKIP_ANY = {"$recycle.bin", "recycler", "system volume information", "config.msi", "node_modules", ".git", ".hg",
            ".svn", "__pycache__", ".venv", "venv", "env", ".tox", ".nox", ".mypy_cache", ".pytest_cache",
            ".ruff_cache", ".next", ".nuxt", ".turbo", ".parcel-cache", ".svelte-kit", "site-packages",
            ".gradle", ".m2", ".pnpm-store", "pnpm-store", ".npm", ".yarn", "npm-cache", "pip-cache", "uv-cache",
            "huggingface", "modelscope", "cache", ".cache", "caches", "steamapps", "windows kits",
            "wechat files", "xwechat_files", "tencent files"}
# 云同步盘：不读取（读取云端占位文件会触发下载）。另外所有以 onedrive 开头的目录也跳过
CLOUD = {"icloud drive", "dropbox", "google drive", "baidunetdisk", "百度网盘", "坚果云", "nutstore",
         "wps cloud files", "wpsdrive", "迅雷云盘", "quarkclouddrive", "阿里云盘"}
# 系统盘根目录下一层的系统目录（Windows 的 C:\ 和 macOS / Linux 的 /）
SYSTEM_ROOT_SKIP = {
    "windows", "program files", "program files (x86)", "programdata", "users", "$windows.~bt", "$windows.~ws",
    "$winreagent", "recovery", "perflogs", "msocache", "documents and settings", "intel", "amd", "nvidia",
    "drivers", "onedrivetemp", "xboxgames", "windowsapps",
    "home", "proc", "sys", "dev", "run", "usr", "bin", "sbin", "lib", "lib32", "lib64", "libx32", "etc", "var",
    "boot", "snap", "srv", "mnt", "lost+found", "system", "library", "applications", "private", "cores"}
# 用户主目录下一层：程序数据和包管理器目录（另外所有以 . 开头的目录也跳过）
HOME_SKIP = {"appdata", "application data", "local settings", "library", "snap", "scoop", "go"}
# macOS 的“包”目录：看起来是文件，实际是目录
BUNDLE_EXT = (".app", ".photoslibrary", ".musiclibrary", ".tvlibrary", ".bundle", ".framework", ".plugin", ".kext")

# ------------------------------------------------------------------ 统计大小时的分类
BUCKET = {"node_modules": "依赖", ".venv": "依赖", "venv": "依赖", "env": "依赖", "site-packages": "依赖",
          "python_embeded": "依赖", "vendor": "依赖", ".pnpm-store": "依赖", "pods": "依赖", ".git": "git",
          "dist": "构建", "build": "构建", "target": "构建", ".next": "构建", "out": "构建", "obj": "构建",
          "deriveddata": "构建", "__pycache__": "缓存", ".cache": "缓存", ".pytest_cache": "缓存",
          ".mypy_cache": "缓存", ".turbo": "缓存", ".gradle": "缓存", "models": "模型", "checkpoints": "模型",
          "weights": "模型", "logs": "日志", "log": "日志"}
# 这些文件改了不算“项目有改动”（程序运行时自己会写）
NOISE_EXT = {".log", ".tmp", ".lock", ".db", ".db-wal", ".db-shm", ".sqlite", ".sqlite-wal", ".pyc", ".etl"}
LANG = {".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript", ".js": "JavaScript", ".jsx": "JavaScript",
        ".mjs": "JavaScript", ".cjs": "JavaScript", ".vue": "Vue", ".svelte": "Svelte", ".go": "Go", ".rs": "Rust",
        ".java": "Java", ".kt": "Kotlin", ".scala": "Scala", ".c": "C", ".cpp": "C++", ".cc": "C++", ".h": "C/C++",
        ".hpp": "C++", ".cs": "C#", ".rb": "Ruby", ".php": "PHP", ".lua": "Lua", ".dart": "Dart", ".swift": "Swift",
        ".ex": "Elixir", ".zig": "Zig", ".r": "R", ".jl": "Julia", ".ps1": "PowerShell", ".bat": "批处理",
        ".cmd": "批处理", ".sh": "Shell", ".html": "HTML", ".css": "CSS", ".ipynb": "Notebook", ".sql": "SQL",
        ".gd": "GDScript", ".asm": "汇编", ".md": "Markdown", ".json": "JSON"}

# ------------------------------------------------------------------ 合集与分组
_L, _R = r"(?<![a-z])", r"(?![a-z])"   # 英文单词边界（数字、- _ 都算边界）
# 编号分类目录（01_工作、02 学习、3-归档）：只当分组，不当项目、不当合集
CATEGORY = re.compile(r"^\d{1,2}[ ._-]\D")
# “同类一大堆”的目录：按路径上最外层命中的那一级折叠成一个合集。列表顺序 = 优先级
COLLECT = [
    ("备份/归档", re.compile(_L + r"(backups?|archives?|archived|snapshots?|historical|bak|old|orig)" + _R +
                         r"|备份|归档|旧版|历史版本|副本|- copy$", re.I)),
    ("临时/测试", re.compile(_L + r"(tmp|temp|temporary|scratch|sandbox|playground|probe|e2e|tests?|trials?|"
                         r"verify|verification)" + _R + r"|pytest|临时|测试", re.I)),
    ("研究/审查", re.compile(_L + r"(research|reviews?|study|studies|audits?|inspection|scans?|scout|"
                         r"evaluation|evals?)" + _R + r"|调研|审查|研究|评测", re.I)),
    ("技能/资料合集", re.compile(r"skills?" + _R + r"|awesome|合集|技能|学习资料|cheatsheets?", re.I)),
    ("自动生成的会话目录", re.compile(r"^\d{4}-?\d{2}-?\d{2}[-_ T]\d{2}[-_:]?\d{2}([-_:]?\d{2})?$")),
]
# 项目自己的名字只认这几种“明确是副本 / 临时”的写法（code-review-bot、test-runner 这类正经项目不受影响）
SELF_STRONG = [
    ("备份/归档", re.compile(_L + r"(backups?|bak|snapshots?)" + _R + r"|备份|副本$|- copy$", re.I)),
    ("临时/测试", re.compile(_L + r"(tmp|temp|scratch)" + _R + r"|临时", re.I)),
]
# 名字像“装项目的文件夹”→ 当分组
CONTAINER = re.compile(r"^\d{1,2}[ ._-]\D|projects$|^(project|code|codes|coding|repos?|repositories|git|github|"
                       r"gitlab|workspaces?|workplace|work|dev|develop|development|src|source|sources|"
                       r"desktop|documents|downloads|my documents|我的项目|项目|代码|工程|源码|作品集|桌面|文档|下载)$",
                       re.I)
# 项目内部常见的子目录名：判断“下面有几个独立项目”时不算数
GENERIC = {"src", "lib", "libs", "core", "scripts", "script", "tests", "test", "docs", "doc", "tools", "tool",
           "app", "apps", "web", "server", "client", "frontend", "backend", "api", "data", "assets", "static",
           "templates", "config", "configs", "notes", "bin", "examples", "example", "demo", "utils", "common",
           "modules", "packages", "plugins", "components", "public", "resources", "res", "build", "dist",
           "output", "outputs", "logs", "models", "skills", "workspace", "runtime"}
# 作品 / 素材类目录名
CREATIVE_NAME = re.compile(r"作品|漫剧|视频|剪辑|口播|直播|海报|设计|素材|video|footage|film", re.I)


def user_place(parent_name, depth):
    """“按名字认”的浅层规则只在用户放东西的地方生效：根目录下一级，或分类目录 / 项目文件夹下一级。"""
    return depth == 1 or (depth == 2 and bool(CATEGORY.match(parent_name) or CONTAINER.search(parent_name)))


def collect_type(name, self_only=False):
    """目录名属于哪类合集；self_only=True 时只认明确的副本 / 临时写法。"""
    if CATEGORY.match(name):
        return None
    for typ, rx in (SELF_STRONG if self_only else COLLECT):
        if rx.search(name):
            return typ
    return None
