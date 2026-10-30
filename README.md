# 项目总览 · Project Atlas

只读扫描电脑上的所有项目，生成一个离线打开的总览页面：每个项目在哪、多大、最后什么时候动过、git 有没有没提交的改动、有没有异地备份。

适合项目散落在好几个盘、好几个文件夹里，已经记不清“到底有多少个项目、哪些还在用、哪些没备份”的情况。

![按分组查看](docs/screenshot-groups.png)

## 特点

- **只读**：不修改、不移动、不删除任何文件；不跟随符号链接 / junction；不读取 OneDrive 等云盘的云端占位文件（读取会触发下载）。
- **离线**：结果是一个单文件 HTML，加一份 CSV。不联网、不上传任何东西。
- **零依赖**：只用 Python 标准库，Windows / macOS / Linux 通用。
- **认得出项目**：git、Node、Python、Rust、Go、Java、.NET、C/C++、Flutter、Godot、Unity、Xcode、Docker、Obsidian 笔记库、剪映草稿，以及只有散装脚本、只有 AI / IDE 配置（`.cursor`、`.claude`、`.vscode`……）的文件夹。
- **不刷屏**：备份、临时、测试、调研、技能合集这类“同类一大堆”的目录自动折叠成一个合集；`node_modules`、虚拟环境、缓存不会被当成项目。
- **指出问题**：没提交的改动、没有远端的仓库、别人仓库上的本地改动、同名副本、乱码目录、散落在根目录的大文件、编辑器“最近打开”里已经失效的记录。

## 快速开始

需要 Python 3.9 或更高版本（[下载](https://www.python.org/downloads/)），不用安装任何第三方库。

1. 下载本仓库（右上角 Code → Download ZIP，或 `git clone`）。
2. 运行：
   - **Windows**：双击 `run.bat`
   - **macOS / Linux**：在终端运行 `./run.sh`
3. 扫描完成后浏览器会自动打开 `output/project-atlas.html`。

默认扫描所有本地磁盘和用户主目录（Windows 系统盘只看 3 层，系统目录跳过），一般几十秒到几分钟。

### 命令行

```bash
python -m project_atlas                     # 扫描所有本地磁盘 + 用户主目录
python -m project_atlas D:\work ~/code      # 只扫描指定目录
python -m project_atlas --exclude D:\Games --open
pip install .  &&  project-atlas --help     # 也可以安装成命令
```

| 参数 | 作用 |
|---|---|
| `目录 ...` | 要扫描的目录，不填 = 所有本地磁盘 + 用户主目录 |
| `-o, --out` | 结果输出目录，默认 `./output` |
| `-c, --config` | 配置文件，默认读取当前目录的 `atlas.config.json` |
| `--depth N` | 往下扫描的层数（默认 7，用户主目录 6） |
| `--exclude DIR` | 不扫描的目录，可以写多次 |
| `--no-recents` | 不读取编辑器的“最近打开”记录 |
| `--no-git` | 不运行任何 git 命令 |
| `--json` | 另外输出 `atlas.json` 原始数据 |
| `--open` | 完成后用浏览器打开 |

## 页面里有什么

| 视图 | 内容 |
|---|---|
| 按位置 / 按分组 | 默认按所在文件夹分组；配置了 `groups` 后按你定义的产品线分。每组列出全部条目，点名称看详情 |
| 全部清单 | 搜索、按类型 / 状态 / 根目录筛选、按大小或最后活动排序 |
| 目录全景 | 每个根目录和分组目录下的每一个子目录都标明是什么：项目、分组、软件、跳过或其他，保证没有漏掉的 |
| 问题与建议 | 有丢失风险的仓库、别人仓库上的改动、失效的“最近打开”记录、异常目录、同名副本、可清理候选、可重新生成的依赖 |
| 软件与跳过 | 被识别为软件 / 运行环境的目录，以及跳过的目录和原因 |

![问题与建议](docs/screenshot-issues.png)

同时会生成 `projects.csv`，可以直接用 Excel 打开。

## 配置

把 `atlas.config.example.json` 复制为 `atlas.config.json`，按需修改。所有字段都可以不写。

```json
{
  "roots": ["D:\\", "~/code", ["E:\\archive", 3]],
  "exclude": ["D:\\Games"],
  "github_users": ["your-github-name"],
  "groups": [
    {"name": "个人网站", "keywords": ["blog", "site"]},
    {"name": "机器学习", "keywords": ["model", "train"]}
  ]
}
```

- `roots`：要扫描的目录；可以写成 `[目录, 层数]`。
- `github_users`：你的 GitHub / GitLab / Gitee 用户名或组织名。填了以后，页面能区分“自己仓库没推送的改动”和“别人仓库上的本地改动”。
- `groups`：按路径关键词把条目归到产品线，没命中的归到“其他”；不配置就按所在位置分组。
- 其它：`max_depth`、`home_depth`、`system_drive_depth`、`recents`、`anomalies`、`git`、`workers`。

`atlas.config.json` 已经在 `.gitignore` 里，不会被提交。

## 怎么判断的

- **项目**：目录里有 `.git`、`package.json`、`pyproject.toml`、`Cargo.toml`、`go.mod`、`*.sln` 等工程文件，扫描到这里就停，不再往下。
- **散装项目**：没有工程文件，但有几个代码文件或 AI / IDE 配置。
- **合集**：路径上出现 backup、archive、tmp、temp、test、research、review、awesome、技能、备份、临时、测试、调研 等字样，从最外层那一级折叠成一条。项目自己的名字只认明确的副本 / 临时写法，所以 `code-review-bot`、`test-runner` 这类项目不受影响。
- **最后活动**：文件修改时间、最后一次提交、编辑器最后打开时间中最新的一个；日志、数据库这类程序自己会写的文件不算。

规则都在 [`project_atlas/rules.py`](project_atlas/rules.py)，可以按自己的习惯改。

## 隐私与安全

- 只读取：文件名、大小、修改时间；`README` / `package.json` / `pyproject.toml` 开头几 KB（生成一句话说明）；只读的 git 命令（`log`、`status`、`rev-list`、`remote`，不 fetch、不 push）；编辑器本地的“最近打开”记录（VS Code 及其衍生编辑器、JetBrains、Claude Code、Codex，可用 `--no-recents` 关闭）。
- 远端地址里的账号 / 令牌会被去掉，不会出现在结果里。
- `git status` 会执行仓库自己配置的过滤器（例如 Git LFS）。扫描来路不明的下载目录时，可以加 `--no-git`。
- git 不信任的目录（属主不是当前用户）会标出来，不会绕过 git 的这项保护。
- **生成的页面包含你电脑上的路径和项目名，分享前注意**。`output/` 已经在 `.gitignore` 里。

## 常见问题

**扫描太慢？** 用 `--exclude` 排除放游戏、影音、模型的大目录，或者用 `--depth` 少扫几层。超出时限的目录会标出来，不会卡死。

**macOS 弹出“访问文稿 / 下载”的权限提示？** 允许就能扫描这些目录；拒绝的目录会被跳过。

**某个项目没被认出来？** 在 `rules.py` 的 `TERMINAL` 里加上它的标志文件，或者把它所在的目录写进 `roots`。

## 开发

```bash
python -m unittest discover -s tests -v        # 测试
python scripts/make_demo.py demo-tree          # 造一棵虚构的示例目录树（README 里的截图就是这样来的）
python -m project_atlas demo-tree -c demo-tree/atlas.config.json --no-recents --open
```

## English

Project Atlas does a read-only scan of your disks and renders one offline HTML page that lists every project on the machine: where it lives, how big it is, when it was last touched, whether its git repo has uncommitted or unpushed work, and whether it has an off-machine backup. Backup / temp / test folders are folded into single entries, and the page also flags duplicate copies, stray files, garbled folder names and stale "recently opened" records.

Pure Python standard library, Windows / macOS / Linux, Python 3.9+. It never modifies, moves or deletes files, never follows symlinks, never reads cloud placeholder files and never touches the network. Run `run.bat` (Windows) or `./run.sh` (macOS / Linux), or `python -m project_atlas [dirs...]`. Output: `output/project-atlas.html` and `output/projects.csv`. The interface is in Chinese.

## License

[MIT](LICENSE)
