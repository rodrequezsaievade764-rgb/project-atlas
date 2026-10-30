"use strict";
/* 项目总览 · 页面逻辑（一）：数据、格式化、行渲染、全部清单表格、事件 */
var D;
try { D = JSON.parse(document.getElementById("data").textContent); }
catch (e) { showErr("数据解析失败：" + e.message); throw e; }
function showErr(msg) { var el = document.getElementById("err"); el.hidden = false; el.textContent = msg; }
window.addEventListener("error", function (ev) { showErr("页面脚本出错：" + ev.message); });

var $ = function (id) { return document.getElementById(id); };
var ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
function h(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return ESC[c]; }); }
function size(b, capped) {
  if (b == null) return "—";
  var u = ["B", "KB", "MB", "GB", "TB"], i = 0;
  while (b >= 1024 && i < u.length - 1) { b /= 1024; i++; }
  return (capped ? "≥" : "") + (i ? b.toFixed(b < 10 ? 1 : 0) : b) + " " + u[i];
}
function day(t) {
  if (!t) return "—";
  var d = new Date(t * 1000), p = function (n) { return (n < 10 ? "0" : "") + n; };
  return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate());
}
function ago(t) {
  if (!t) return "";
  var s = D.generated - t;
  if (s < 3600) return "1 小时内";
  if (s < 86400) return Math.floor(s / 3600) + " 小时前";
  if (s < 86400 * 60) return Math.floor(s / 86400) + " 天前";
  return Math.floor(s / 86400 / 30) + " 个月前";
}
var SERIOUS = /^(未提交|未推送|git 无远端|远端在本机|本地改动|git 状态|git 不信任)/;
function serious(r) { return r.issues.some(function (i) { return SERIOUS.test(i); }); }
/* 风险由生成器判定：own = 自己的改动没有异地备份；mod = 别人仓库上的本地改动；unknown = 分不清归属但有未保存改动 */
function ownRisk(r) { return r.risk === "own"; }
function thirdMod(r) { return r.risk === "mod"; }
function unknownRisk(r) { return r.risk === "unknown"; }
var SEP = D.sep || "\\";
var GROUP_LABEL = D.group_mode === "custom" ? "分组" : "位置";
function cleanable(r) { return /可清理|可删|装好后/.test(r.advice); }
D.rows.forEach(function (r, i) {
  r.id = i;
  r.hay = [r.name, r.path, r.desc, r.group, r.type, r.origin, r.langs.join(" "), r.issues.join(" ")].join(" ").toLowerCase();
});

function rowHtml(r, pre, compact) {
  var did = pre + "-d" + r.id;
  var name = '<button class="tog" aria-expanded="false" aria-controls="' + did + '" data-id="' + r.id + '">' +
    h(r.name) + '</button><span class="path mono">' + h(r.path) + "</span>";
  var issues = r.issues.length ? '<span class="iss">' + h(r.issues.join("；")) + "</span>" : '<span class="mut">—</span>';
  var cells = ["<td>" + name + "</td>"];
  if (!compact) cells.push("<td>" + h(r.group) + "</td>");
  cells.push('<td><span class="tag">' + h(r.type) + "</span></td>");
  cells.push('<td class="hide-sm">' + h(r.origin) + (r.langs.length ? "<br><span class=\"mut\">" +
    h(r.langs.join(" / ")) + "</span>" : "") + "</td>");
  cells.push('<td class="num">' + size(r.size, r.capped) + "</td>");
  cells.push('<td><span class="st st-' + h(r.status) + '">' + h(r.status) + '</span><br><span class="mut">' +
    day(r.last) + "</span></td>");
  cells.push("<td>" + issues + "</td>");
  cells.push("<td>" + h(r.advice) + "</td>");
  return '<tr class="row" data-pre="' + pre + '">' + cells.join("") + "</tr>";
}

function detailHtml(r, pre, span) {
  var out = [], g = r.git;
  out.push('<div><b>完整路径</b><span class="mono">' + h(r.path) + '</span> <button class="btn" data-copy="' +
    h(r.path) + '">复制路径</button></div>');
  if (r.desc) out.push("<div><b>说明</b>" + h(r.desc) + "</div>");
  out.push("<div><b>来源</b>" + h(r.origin) + "　<b>标记</b>" + h(r.markers.join("、") || "—") +
    (r.files != null ? "　<b>文件数</b>" + r.files : "") + "</div>");
  if (g) {
    out.push("<div><b>Git</b>分支 " + h(g.branch || "—") + "，共 " + h(g.commits || "?") + " 次提交" +
      (g.last_commit ? "，最后提交 " + day(g.last_commit) + "「" + h(g.subject || "") + "」" : "") + "</div>");
    out.push('<div><b>远端</b><span class="mono">' + h(g.remote || "无") + "</span>" +
      (g.worktree_of ? '　<b>工作树来自</b><span class="mono">' + h(g.worktree_of) + "</span>" : "") + "</div>");
  }
  var bk = Object.keys(r.buckets || {}).filter(function (k) { return r.buckets[k] > 1048576; });
  if (bk.length) {
    out.push("<div><b>大小构成</b>" + bk.map(function (k) { return k + " " + size(r.buckets[k]); }).join("，") +
      "，其余 " + size(r.size - bk.reduce(function (s, k) { return s + r.buckets[k]; }, 0)) + "</div>");
  }
  if (r.recent) {
    out.push("<div><b>最近打开</b>" + Object.keys(r.recent.sources).map(function (s) {
      return s + " ×" + r.recent.sources[s]; }).join("，") + (r.recent.last ? "，最后 " + day(r.recent.last) : "") + "</div>");
  }
  if (r.parent) out.push('<div><b>上级项目</b><span class="mono">' + h(r.parent) + "</span></div>");
  if (r.child_count) {
    out.push("<div><b>包含 " + r.child_count + " 个子目录</b>" + (r.child_count > r.children.length ?
      "（只列前 " + r.children.length + " 个）" : "") + '<div class="kids mono">' +
      r.children.map(function (c) { return "<span>" + h(c) + "</span>"; }).join("") + "</div></div>");
  }
  if (r.nested_git && r.nested_git.length) {
    out.push('<div><b>里面还有 git 仓库</b><span class="mono">' + h(r.nested_git.join("、")) + "</span></div>");
  }
  return '<tr class="det" id="' + pre + "-d" + r.id + '"><td colspan="' + span + '">' +
    out.map(function (x) { return x; }).join("") + "</td></tr>";
}

var COLS = [["name", "名称 / 路径"], ["group", GROUP_LABEL], ["type", "类型"], ["origin", "来源 / 技术栈"],
  ["size", "大小"], ["last", "最后活动"], ["issues", "问题"], ["advice", "建议"]];
var sortKey = "last", sortDir = -1;
function cmp(a, b) {
  var x, y;
  if (sortKey === "size" || sortKey === "last") { x = a[sortKey] || 0; y = b[sortKey] || 0; }
  else if (sortKey === "issues") { x = (serious(a) ? 100 : 0) + a.issues.length; y = (serious(b) ? 100 : 0) + b.issues.length; }
  else { return sortDir * String(a[sortKey]).localeCompare(String(b[sortKey]), "zh-CN"); }
  return sortDir * (x - y);
}

function filtered() {
  var raw = $("q").value.trim(), words = [], pathPre = null;
  raw.split(/\s+/).forEach(function (w) {
    if (!w) return;
    if (w.toLowerCase().indexOf("path:") === 0) pathPre = w.slice(5).toLowerCase(); else words.push(w.toLowerCase());
  });
  var fg = $("f-group").value, ft = $("f-type").value, fs = $("f-status").value, fd = $("f-drive").value;
  var fi = $("f-iss").checked;
  return D.rows.filter(function (r) {
    if (fg && r.group !== fg) return false;
    if (ft && r.type !== ft) return false;
    if (fs && r.status !== fs) return false;
    if (fd && r.drive !== fd) return false;
    if (fi && !r.issues.length) return false;
    if (pathPre && r.path.toLowerCase().indexOf(pathPre) !== 0) return false;
    return words.every(function (w) { return r.hay.indexOf(w) >= 0; });
  });
}

function renderList() {
  var rows = filtered().sort(cmp);
  $("tbl").tHead.innerHTML = "<tr>" + COLS.map(function (c) {
    var s = c[0] === sortKey ? (sortDir > 0 ? "ascending" : "descending") : "none";
    var cls = (c[0] === "size" ? "num" : "") + (c[0] === "origin" ? " hide-sm" : "");
    return '<th scope="col" class="' + cls + '" aria-sort="' + s + '"><button data-sort="' + c[0] + '">' + c[1] + "</button></th>";
  }).join("") + "</tr>";
  $("tbl").tBodies[0].innerHTML = rows.map(function (r) { return rowHtml(r, "l", false); }).join("") ||
    '<tr><td colspan="8" class="mut">没有符合条件的条目</td></tr>';
  var total = rows.reduce(function (s, r) { return s + (r.size || 0); }, 0);
  $("count").textContent = "显示 " + rows.length + " / " + D.rows.length + " 项，共 " + size(total);
}

function fillSelect(id, label, key, order) {
  var cnt = {};
  D.rows.forEach(function (r) { cnt[r[key]] = (cnt[r[key]] || 0) + 1; });
  var keys = Object.keys(cnt).sort(order || function (a, b) { return cnt[b] - cnt[a]; });
  $(id).innerHTML = '<option value="">' + label + "：全部</option>" + keys.map(function (k) {
    return '<option value="' + h(k) + '">' + h(k) + "（" + cnt[k] + "）</option>"; }).join("");
}

function showTab(id) {
  document.querySelectorAll('[role="tab"]').forEach(function (t) {
    var on = t.id === id;
    t.setAttribute("aria-selected", on ? "true" : "false");
    t.tabIndex = on ? 0 : -1;
    $(t.getAttribute("aria-controls")).hidden = !on;
  });
}

function copyText(text, btn) {
  var done = function () { btn.textContent = "已复制"; setTimeout(function () { btn.textContent = "复制路径"; }, 1500); };
  if (navigator.clipboard && window.isSecureContext) { navigator.clipboard.writeText(text).then(done, fallback); }
  else fallback();
  function fallback() {
    var ta = document.createElement("textarea");
    ta.value = text; document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); done(); } catch (e) { btn.textContent = "复制失败"; }
    document.body.removeChild(ta);
  }
}

$("po").addEventListener("click", function (ev) {
  var t = ev.target.closest("button");
  if (!t) return;
  if (t.classList.contains("tog")) {
    var tr = t.closest("tr"), r = D.rows[+t.dataset.id], pre = tr.dataset.pre, next = tr.nextElementSibling;
    if (next && next.classList.contains("det")) { next.remove(); t.setAttribute("aria-expanded", "false"); return; }
    var span = t.closest("table").tHead.rows[0].cells.length;
    tr.insertAdjacentHTML("afterend", detailHtml(r, pre, span));
    t.setAttribute("aria-expanded", "true");
  } else if (t.dataset.copy) {
    copyText(t.dataset.copy, t);
  } else if (t.dataset.sort) {
    var k = t.dataset.sort;
    sortDir = k === sortKey ? -sortDir : (k === "size" || k === "last" || k === "issues" ? -1 : 1);
    sortKey = k; renderList();
  } else if (t.dataset.tab) {
    ev.preventDefault(); ev.stopPropagation();
    if (t.dataset.group != null || t.dataset.q != null) {
      ["q", "f-group", "f-type", "f-status", "f-drive"].forEach(function (id) { $(id).value = ""; });
      $("f-iss").checked = false;
    }
    if (t.dataset.group != null) { $("f-group").value = t.dataset.group; }
    if (t.dataset.q != null) { $("q").value = t.dataset.q; }
    if (t.dataset.iss) { $("f-iss").checked = true; }
    if (t.dataset.tab === "t-list") renderList();
    showTab(t.dataset.tab); $(t.dataset.tab).focus();
  } else if (t.getAttribute("role") === "tab") {
    showTab(t.id);
  }
});
document.querySelector('[role="tablist"]').addEventListener("keydown", function (ev) {
  if (ev.key !== "ArrowRight" && ev.key !== "ArrowLeft") return;
  var tabs = Array.prototype.slice.call(document.querySelectorAll('[role="tab"]'));
  var i = tabs.indexOf(document.activeElement);
  if (i < 0) return;
  var n = tabs[(i + (ev.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length];
  showTab(n.id); n.focus(); ev.preventDefault();
});
["q", "f-group", "f-type", "f-status", "f-drive", "f-iss"].forEach(function (id) {
  $(id).addEventListener(id === "q" ? "input" : "change", renderList);
});
