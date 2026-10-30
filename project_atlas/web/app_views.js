/* 项目总览 · 页面逻辑（二）：概览数字、提醒、按分组、目录全景、问题与建议、软件与跳过 */
var STANDALONE = document.documentElement.classList.contains("standalone");
function sum(rows) { return rows.reduce(function (s, r) { return s + (r.size || 0); }, 0); }
function anomaly(type) { return D.anomalies.filter(function (a) { return a.type === type; }); }
function pathCell(r) { return h(r.name) + '<span class="path mono">' + h(r.path) + "</span>"; }
function mono(path) { return '<span class="mono">' + h(path) + "</span>"; }
function td(cells) { return "<tr>" + cells.map(function (c) { return "<td>" + c + "</td>"; }).join("") + "</tr>"; }
function table(headers, rows) {
  return '<div class="scroll"><table><thead><tr>' + headers.map(function (x) { return '<th scope="col">' + x + "</th>"; })
    .join("") + "</tr></thead><tbody>" + (rows.join("") || '<tr><td colspan="' + headers.length +
    '" class="mut">无</td></tr>') + "</tbody></table></div>";
}

function renderStats() {
  var R = D.rows, groups = {};
  R.forEach(function (r) { groups[r.group] = 1; });
  var proj = R.filter(function (r) { return /^(项目|作品\/素材|笔记库)$/.test(r.type); });
  var clean = R.filter(cleanable);
  var tiles = [
    [R.length, "个条目，其中项目/作品 " + proj.length + " 个"],
    [Object.keys(groups).length, D.group_mode === "custom" ? "个分组" : "个位置"],
    [size(sum(R)), "条目总占用"],
    [R.filter(function (r) { return r.status === "活跃"; }).length, "个 7 天内有改动"],
    [R.filter(ownRisk).length, "个自己的 git 仓库有丢失风险"],
    [size(sum(clean)), "可清理候选（" + clean.length + " 项）"]];
  $("stats").innerHTML = tiles.map(function (t) {
    return '<div class="tile"><b>' + h(t[0]) + "</b><span>" + h(t[1]) + "</span></div>"; }).join("");
}

function renderAlerts() {
  var L = [];
  var unk = D.rows.filter(unknownRisk);
  if (unk.length) L.push([0, unk.length + " 个有远端的仓库有未提交 / 未推送的改动（在配置里填 github_users 能分清哪些是自己的）"]);
  var own = D.rows.filter(ownRisk), mod = D.rows.filter(thirdMod);
  if (own.length) L.push([1, own.length + " 个自己的 git 仓库有未提交改动或没有异地备份：" +
    own.map(function (r) { return r.name; }).join("、")]);
  if (mod.length) L.push([0, mod.length + " 个第三方克隆上有你的本地改动，更新前要先备份：" +
    mod.map(function (r) { return r.name; }).join("、")]);
  anomaly("乱码目录").forEach(function (a) {
    L.push([1, "乱码目录 " + a.path + "（本该在 " + a.decoded + "，里面有 " + a.files + " 个文件）"]); });
  var ms = anomaly("疑似路径误转换");
  if (ms.length) L.push([0, ms.length + " 个疑似路径误转换留下的目录（" +
    ms.map(function (a) { return a.path; }).join("、") + "），共 " + size(ms.reduce(function (s, a) { return s + a.size; }, 0))]);
  anomaly("散落文件").forEach(function (a) { if (a.count) L.push([0, a.label + "散落着 " + a.count + " 个文件，共 " + size(a.size)]); });
  if (D.dups.length) L.push([0, D.dups.length + " 组同名副本（" + D.dups.slice(0, 5).map(function (d) { return d.name; })
    .join("、") + " 等）"]);
  if (D.stale.length) L.push([0, D.stale.length + " 条 IDE / 代理的“最近打开”记录指向已不存在的目录"]);
  $("alerts").innerHTML = L.slice(0, 8).map(function (x) {
    return '<li class="' + (x[0] ? "hi" : "") + '">' + h(x[1]) + "</li>"; }).join("") +
    '<li><button class="linkish" data-tab="t-issues">查看全部问题与建议 →</button></li>';
}

function renderGroups() {
  var by = {};
  D.rows.forEach(function (r) { (by[r.group] = by[r.group] || []).push(r); });
  var names = Object.keys(by).sort(function (a, b) {
    if (a.indexOf("其他") === 0) return 1;
    if (b.indexOf("其他") === 0) return -1;
    return by[b].length - by[a].length;
  });
  var head = "<thead><tr>" + ["名称 / 路径", "类型", "来源 / 技术栈", "大小", "最后活动", "问题", "建议"].map(function (x, i) {
    return '<th scope="col"' + (i === 2 ? ' class="hide-sm"' : i === 3 ? ' class="num"' : "") + ">" + x + "</th>"; })
    .join("") + "</tr></thead>";
  $("p-groups").innerHTML = '<p class="note">' + (D.group_mode === "custom" ? "按配置里的 groups 关键词归类，" :
    "按所在文件夹分组（在 atlas.config.json 里配置 groups 可以改成按产品线分），") +
    "每组列出全部条目，点名称展开看详情。</p>" + '<div class="bar"><button class="btn" data-open="1">全部展开</button>' +
    '<button class="btn" data-open="0">全部收起</button></div>' +
    names.map(function (n, i) {
      var rows = by[n].slice().sort(function (a, b) { return (b.last || 0) - (a.last || 0); });
      var types = {};
      rows.forEach(function (r) { types[r.type] = (types[r.type] || 0) + 1; });
      var live = rows.filter(function (r) { return r.status === "活跃"; }).length;
      var bad = rows.filter(function (r) { return r.issues.length; }).length;
      return '<details class="grp"' + (STANDALONE && i < 3 ? " open" : "") + "><summary>" +
        '<span class="gn">' + h(n) + '</span><span class="gs">' + rows.length + " 项 · " + size(sum(rows)) +
        " · 活跃 " + live + (bad ? ' · <span class="iss">有提示 ' + bad + "</span>" : "") + "</span>" +
        '<span class="gs">' + Object.keys(types).map(function (t) { return h(t) + " " + types[t]; }).join(" / ") +
        '</span><button class="btn" data-tab="t-list" data-group="' + h(n) + '">在清单中筛选</button></summary>' +
        '<div class="scroll"><table>' + head + "<tbody>" + rows.map(function (r) { return rowHtml(r, "g", true); })
        .join("") + "</tbody></table></div></details>";
    }).join("");
}
$("p-groups").addEventListener("click", function (ev) {
  var b = ev.target.closest("button[data-open]");
  if (b) $("p-groups").querySelectorAll("details.grp").forEach(function (d) { d.open = b.dataset.open === "1"; });
});

function renderPano() {
  var cmap = {};
  D.containers.forEach(function (c) { cmap[c.path.toLowerCase()] = c; });
  $("p-pano").innerHTML = '<p class="note">按位置列出每个根目录和分组目录下的每一个子目录各是什么：项目、分组、软件、跳过或其他（资料/媒体/程序数据）。' +
    "保证每个目录都有交代。点绿色或蓝色的名字可以跳到清单。</p>" + D.panorama.map(function (b, i) {
    var cnt = { 项目: 0, 分组: 0, 软件: 0, 跳过: 0, 其他: 0 };
    var items = b.rows.map(function (r) {
      var s = r.status, cls = "", label = s;
      if (s.indexOf("项目:") === 0) { cls = "p"; label = s.slice(3); cnt.项目++; }
      else if (s === "分组" || /^含/.test(s)) { cls = "g"; cnt.分组++; }
      else if (/^其他/.test(s)) { cls = "o"; cnt.其他++; }
      else if (/^跳过:/.test(s)) { label = s.slice(3); cnt.跳过++; }
      else if (/^(软件|Python)/.test(s)) { cnt.软件++; }
      else { cnt.项目++; }
      var full = b.parent.replace(/[\\\/]$/, "") + SEP + r.name;
      var nm = cls === "p" || cls === "g" ? '<button class="linkish n" data-tab="t-list" data-q="path:' + h(full) +
        '" title="' + h(full) + '">' + h(r.name) + "</button>" : '<span class="n" title="' + h(full) + '">' + h(r.name) + "</span>";
      return "<div>" + nm + '<span class="s ' + cls + '">' + h(label) + "</span></div>";
    }).join("");
    var c = cmap[b.parent.toLowerCase()];
    var gs = Object.keys(cnt).filter(function (k) { return cnt[k]; }).map(function (k) { return k + " " + cnt[k]; }).join(" · ") +
      (c && c.loose_code ? " · 另有散装脚本/代码 " + c.loose_code + " 个" : "");
    return '<details class="blk"' + (STANDALONE && i < 3 ? " open" : "") + '><summary><span class="gn mono">' + h(b.parent) +
      '</span><span class="gs">' + b.rows.length + " 个子目录 · " + h(gs) + '</span></summary><div class="inner"><div class="pano">' +
      items + "</div></div></details>";
  }).join("");
}

function renderIssues() {
  var out = [], byLast = function (a, b) { return (b.last || 0) - (a.last || 0); };
  var gitRow = function (r) {
    return td([pathCell(r), '<span class="iss">' + h(r.issues.filter(function (i) { return SERIOUS.test(i); }).join("；")) +
      "</span>", day(r.last), h(r.advice)]); };
  var own = D.rows.filter(ownRisk).sort(byLast), mod = D.rows.filter(thirdMod).sort(byLast);
  out.push("<h2>自己的 git 仓库有丢失风险（" + own.length + "）</h2><p class=\"note\">有未提交改动、没有远端，或者远端也在这台电脑上。" +
    "硬盘出问题时这些改动找不回来。</p>");
  out.push(table(["名称 / 路径", "问题", "最后活动", "建议"], own.map(gitRow)));
  out.push("<h2>别人仓库上的本地改动（" + mod.length + "）</h2><p class=\"note\">这些是克隆下来的别人的仓库，" +
    "你在上面改过或加过文件。git pull / 升级时可能冲突或被覆盖，升级前先备份这些改动。数量里包含新增的未跟踪文件。</p>");
  out.push(table(["名称 / 路径", "改动", "最后活动", "建议"], mod.map(gitRow)));
  var unk = D.rows.filter(unknownRisk).sort(byLast);
  if (unk.length) {
    out.push("<h2>有未保存改动的仓库（" + unk.length + "）</h2><p class=\"note\">这些仓库有远端，但分不清是不是你自己的。" +
      "在 atlas.config.json 的 github_users 里填上你的用户名，就能分到上面两类。</p>");
    out.push(table(["名称 / 路径", "改动", "最后活动", "建议"], unk.map(gitRow)));
  }
  out.push("<h2>失效的“最近打开”记录（" + D.stale.length + "）</h2><p class=\"note\">目录已经移走或删掉，但编辑器 / 编程代理" +
    "的“最近打开”还记着旧路径。“可能的新位置”是按目录名猜的，仅供参考。</p>");
  out.push(table(["记录来源", "旧路径", "可能的新位置", "最后使用"], [].concat(D.stale.map(function (s) {
    return td([h(Object.keys(s.sources).join("、")), mono(s.path), (s.guess || []).map(mono).join("<br>") ||
      '<span class="mut">没猜到</span>', day(s.last)]); }))));
  out.push("<h2>异常目录与散落文件</h2>");
  D.anomalies.forEach(function (a) {
    if (a.type === "散落文件") {
      if (!a.count) return;
      out.push("<h3>" + h(a.label) + "散落文件 " + a.count + " 个，共 " + size(a.size) + "（按大小排序）</h3>");
      out.push(table(["文件名", "大小", "修改时间"], a.files.map(function (f) { return td([mono(f.name), size(f.size), day(f.mtime)]); })));
      return;
    }
    out.push('<div class="card" style="margin:0 0 8px"><h3>' + h(a.type) + "：" + mono(a.path) + "</h3>" +
      (a.decoded ? "<p>本该在：" + mono(a.decoded) + (a.target_exists ? "（该目录存在）" : "（该目录不存在）") + "</p>" : "") +
      (a.note ? '<p class="note">' + h(a.note) + "</p>" : "") + "<p>" + (a.files != null ? a.files + " 个文件，" : "") +
      size(a.size) + (a.mtime ? "，最后修改 " + day(a.mtime) : "") + "</p>" + (a.children && a.children.length ?
      '<p class="mono mut">' + a.children.map(h).join("<br>") + "</p>" : "") +
      (a.package_json ? '<p class="mono mut">' + h(a.package_json) + "</p>" : "") + "</div>");
  });
  out.push("<h2>同名副本（" + D.dups.length + " 组）</h2><p class=\"note\">同一个名字出现在多个位置，多半是复制出来的旧版本或备份。" +
    "确认哪个是正在用的，其余的可以归档。</p>");
  out.push(table(["名称", "位置"], D.dups.map(function (d) { return td([h(d.name), d.paths.map(mono).join("<br>")]); })));
  var clean = D.rows.filter(cleanable).sort(function (a, b) { return (b.size || 0) - (a.size || 0); });
  out.push("<h2>可清理候选（" + clean.length + " 项，" + size(sum(clean)) + "）</h2><p class=\"note\">临时/测试目录、旧代理会话、" +
    "装完的安装包、休眠的第三方代码。都只是候选，删之前逐个确认；这个页面不会删除任何东西。</p>");
  out.push(table(["名称 / 路径", "类型", "大小", "最后活动", "建议"], clean.map(function (r) {
    return td([pathCell(r), h(r.type), size(r.size, r.capped), day(r.last) + " " + h(ago(r.last)), h(r.advice)]); })));
  var dep = D.rows.map(function (r) {
    var b = r.buckets || {};
    return { r: r, v: (b["依赖"] || 0) + (b["构建"] || 0) + (b["缓存"] || 0) };
  }).filter(function (x) { return x.v > 200 * 1048576; }).sort(function (a, b) { return b.v - a.v; });
  out.push("<h2>可重新生成的依赖 / 构建产物（" + size(dep.reduce(function (s, x) { return s + x.v; }, 0)) +
    "）</h2><p class=\"note\">node_modules、虚拟环境、dist/build、缓存这类目录删了能重新安装或构建，只对不再用的项目才值得清。只列超过 200 MB 的。</p>");
  out.push(table(["名称 / 路径", "依赖+构建+缓存", "状态"], dep.map(function (x) {
    return td([pathCell(x.r), size(x.v), '<span class="st st-' + h(x.r.status) + '">' + h(x.r.status) + "</span>"]); })));
  $("p-issues").innerHTML = out.join("");
}

function renderApps() {
  var apps = D.apps.slice().sort(function (a, b) { return a.path.localeCompare(b.path); });
  var out = ["<h2>识别为软件 / 运行环境的目录（" + apps.length + "）</h2><p class=\"note\">装好的程序、SDK 或 Python 环境，" +
    "不是项目，所以没有展开统计（只列到第 3 层）。</p>",
    table(["路径", "类型"], apps.map(function (a) { return td([mono(a.path), a.kind === "app" ? "软件/工具" : "Python 环境/库"]); })),
    "<h2>跳过的目录（" + D.skipped.length + "）</h2><p class=\"note\">系统目录、依赖缓存、云同步盘（不读取，避免触发下载）、" +
    "链接，以及工具配置目录（只列浅层）。</p>",
    table(["路径", "原因"], D.skipped.map(function (s) { return td([mono(s.path), h(s.why)]); }))];
  if (D.errors && D.errors.length) out.push("<h2>采集时的报错</h2><p class=\"mono\">" + D.errors.map(h).join("<br>") + "</p>");
  $("p-apps").innerHTML = out.join("");
}

(function init() {
  var s = D.scan || {}, t = new Date(D.generated * 1000);
  $("meta").textContent = "生成于 " + day(D.generated) + " " + t.toTimeString().slice(0, 5) + " · 扫描了 " +
    (s.dirs_visited || "?") + " 个目录：" + D.roots.join("、") + "\n只读扫描，没有修改、移动或删除任何文件 · " +
    "重新扫描：再运行一次 run.bat / run.sh · Project Atlas " + D.version;
  $("t-groups").textContent = "按" + GROUP_LABEL;
  renderStats(); renderAlerts(); renderGroups(); renderPano(); renderIssues(); renderApps();
  fillSelect("f-group", GROUP_LABEL, "group");
  fillSelect("f-type", "类型", "type");
  var ord = ["活跃", "近期", "休眠", "冷", "未知"];
  fillSelect("f-status", "状态", "status", function (a, b) { return ord.indexOf(a) - ord.indexOf(b); });
  fillSelect("f-drive", "根目录", "drive", function (a, b) { return a < b ? -1 : 1; });
  renderList();
  var tab = (location.hash || "").slice(1);  // 支持 项目总览.html#t-issues 直接打开某个视图
  if (tab && $(tab) && $(tab).getAttribute("role") === "tab") showTab(tab);
})();
