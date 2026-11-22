/* ИИ-посттор: assets/data/posts.json (tools/ai_posts.py күн сайын жазат) */
(function () {
  "use strict";
  if (!window.AT) return;
  var IS_LOCAL = /^(localhost|127\.0\.0\.1|\[::1\]|)$/.test(location.hostname) && !/[?&]nodev\b/.test(location.search);
  var data = null;

  function L() { return AT.lang() === "ru" ? "ru" : "ky"; }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function paras(t) { return String(t || "").split(/\n{1,}/).filter(Boolean).map(function (p) { return "<p>" + esc(p) + "</p>"; }).join(""); }
  function dateTxt(s) { var p = String(s || "").split("-"); return p.length === 3 ? p[2] + "." + p[1] + "." + p[0] : s; }

  function empty(box) {
    if (!IS_LOCAL) { box.hidden = true; return; }
    box.innerHTML = '<div class="callout"><svg aria-hidden="true"><use href="#i-info"/></svg><p>' + esc(AT.t("ai.empty")) + "</p></div>";
  }

  function renderFull(box) {
    var p = data.posts[0], l = L();
    var hl = (p.highlights || []).map(function (h) {
      return '<li><b>' + esc(h.asset) + "</b> — " + esc(h["note_" + l]) + "</li>";
    }).join("");
    var arch = data.posts.slice(1, 8).map(function (q, i) {
      return '<details class="ai-old"><summary>' + esc(dateTxt(q.date)) + " · " + esc(q["title_" + l]) + "</summary>" + paras(q["body_" + l]) + "</details>";
    }).join("");
    box.innerHTML =
      '<article class="ai-post">' +
      '<div class="ai-meta"><span class="badge badge-mint">' + esc(AT.t("ai.badge")) + '</span><span class="muted">' + esc(dateTxt(p.date)) + "</span></div>" +
      "<h2>" + esc(p["title_" + l]) + "</h2>" +
      '<div class="ai-body">' + paras(p["body_" + l]) + "</div>" +
      (hl ? '<h3 class="dr-h">' + esc(AT.t("ai.hl")) + '</h3><ul class="ai-hl">' + hl + "</ul>" : "") +
      '<p class="ai-cta">' + esc(p["cta_" + l]) + "</p>" +
      '<div class="cta-row" style="margin:14px 0 6px">' +
      '<a class="btn btn-yellow" href="trends.html">' + esc(AT.t("hs.more_t")) + "</a>" +
      '<button type="button" class="btn btn-ghost" data-copy-tg>' + esc(AT.t("ai.copy")) + "</button></div>" +
      '<p class="cta-note">' + esc(AT.t("ai.note")) + "</p>" +
      (arch ? '<h3 class="dr-h" style="margin-top:18px">' + esc(AT.t("ai.archive")) + "</h3>" + arch : "") +
      "</article>";
    box.querySelector("[data-copy-tg]").addEventListener("click", function () {
      var txt = p["telegram_" + l] || p["body_" + l];
      (navigator.clipboard ? navigator.clipboard.writeText(txt) : Promise.reject()).then(function () {
        AT.toast(AT.t("ai.copied"));
      }).catch(function () { window.prompt("Telegram:", txt); });
    });
  }

  function renderTeaser(box) {
    var p = data.posts[0], l = L();
    var first = String(p["body_" + l] || "").split(/\n+/)[0];
    box.innerHTML =
      '<a class="ai-teaser" href="news.html#ai-post">' +
      '<span class="badge badge-mint">' + esc(AT.t("ai.badge")) + " · " + esc(dateTxt(p.date)) + "</span>" +
      "<h3>" + esc(p["title_" + l]) + "</h3><p>" + esc(first) + "</p>" +
      '<span class="ai-more">' + esc(AT.t("ai.read")) + " →</span></a>";
  }

  function render() {
    document.querySelectorAll("[data-ai-post]").forEach(function (box) {
      if (!data || !data.posts || !data.posts.length) return empty(box);
      box.hidden = false;
      if (box.getAttribute("data-ai-post") === "teaser") renderTeaser(box); else renderFull(box);
    });
  }

  fetch("assets/data/posts.json", { cache: "no-cache" }).then(function (r) {
    if (!r.ok) throw new Error(r.status);
    return r.json();
  }).then(function (j) { data = j; }).catch(function () { data = null; }).then(render);

  AT.onLang(render);
})();
