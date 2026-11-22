/* Сабактар: аталыштын астында кыска видео-нускама, тексти — «Текст менен окуу» ичинде жашырылат.
   HTML'де текст толук калат (издөө системалары жана JS иштебесе да окулат); бул скрипт аны гана түзөтөт.
   Видео: config.js → VIDEOS[ачкыч] (YouTube же assets/video/*.mp4). Бош болсо — «Видео жакында».
   Колдонуу: <li data-video="bingx-register">…</li>, бөлүм үчүн <section class="lesson" data-video="basics">. */
(function () {
  "use strict";

  function videos() { return (window.AITRADING_CONFIG || {}).VIDEOS || {}; }
  /* Тил боюнча видео: орусча — "ачкыч@ru", жок болсо кыргызчасы ("ачкыч") */
  function urlFor(key) {
    var v = videos(), ru = AT.lang() === "ru" ? String(v[key + "@ru"] || "").trim() : "";
    return ru || String(v[key] || "").trim();
  }
  function ytId(u) {
    var m = String(u).match(/(?:youtu\.be\/|youtube(?:-nocookie)?\.com\/(?:watch\?(?:.*&)?v=|embed\/|shorts\/|live\/))([A-Za-z0-9_-]{11})/);
    return m ? m[1] : null;
  }
  function isFile(u) { return /^(assets\/|\.\/|\/)?[^\s:]+\.(mp4|webm|mov)(\?.*)?$/i.test(u); }
  function vt(el, key) { el.setAttribute("data-vt", key); el.textContent = AT.t(key); return el; }

  function slot(key) {
    var url = urlFor(key);
    var box = document.createElement("div");
    box.className = "vslot";
    box.setAttribute("data-video-key", key);
    box.setAttribute("data-video-url", url);
    var id = url && ytId(url), file = url && !id && isFile(url);
    if (!id && !file) {
      box.classList.add("vsoon");
      box.innerHTML = '<span aria-hidden="true">🎬</span>';
      box.appendChild(vt(document.createElement("span"), "vid.soon"));
      return box;
    }
    var vertical = /\/shorts\//i.test(url) || /(^|[\/_-])(short|reel|vertical)/i.test(url);
    if (vertical) box.classList.add("vvert");
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "vplay";
    if (id) btn.style.backgroundImage = "url(https://i.ytimg.com/vi/" + id + "/hqdefault.jpg)";
    else btn.style.backgroundImage = "url(" + url.replace(/\.(mp4|webm|mov)(\?.*)?$/i, ".jpg") + ")";   // мукаба: видео менен бир аттуу .jpg
    btn.innerHTML = '<span class="vplay-ico" aria-hidden="true">▶</span>';
    btn.appendChild(vt(document.createElement("span"), "vid.play"));
    btn.addEventListener("click", function () {
      var el;
      if (id) {
        el = document.createElement("iframe");
        el.src = "https://www.youtube-nocookie.com/embed/" + id + "?autoplay=1&rel=0&playsinline=1&modestbranding=1";
        el.allow = "autoplay; encrypted-media; picture-in-picture; fullscreen";
        el.allowFullscreen = true;
        el.title = AT.t("vid.play");
      } else {
        el = document.createElement("video");
        el.src = url;
        el.controls = true;
        el.autoplay = true;
        el.playsInline = true;
        el.preload = "metadata";
      }
      el.className = "vmedia";
      box.replaceChild(el, btn);
      AT.track("video_play", { key: key });
    });
    box.appendChild(btn);
    return box;
  }

  function fold(nodes, key) {
    if (!nodes.length) return null;
    var det = document.createElement("details");
    det.className = "vtext";
    var sum = document.createElement("summary");
    sum.appendChild(vt(document.createElement("span"), key || "vid.text"));
    det.appendChild(sum);
    nodes.forEach(function (n) { det.appendChild(n); });
    det.addEventListener("toggle", function () { if (det.open) AT.track("lesson_text_open", { key: key || "" }); });
    return det;
  }

  function init() {
    if (!window.AT) return;
    // 1) Кадамдар: аталыш → видео → «Текст менен окуу» (баскычтар көрүнүп калат)
    document.querySelectorAll("li[data-video]").forEach(function (li) {
      var h = li.querySelector("h3");
      if (!h) return;
      var texts = Array.prototype.filter.call(li.children, function (c) { return c.tagName === "P"; });
      var s = slot(li.getAttribute("data-video"));
      h.insertAdjacentElement("afterend", s);
      var d = fold(texts);
      if (d) s.insertAdjacentElement("afterend", d);
    });
    // 2) Бөлүмдөр: аталыш → (видео) → киришүү тексти жашырылат; эскертүүлөр (callout) ачык калат
    document.querySelectorAll("section.lesson").forEach(function (sec) {
      var h = sec.querySelector(":scope > h2");
      if (!h) return;
      var anchor = h;
      if (sec.hasAttribute("data-video")) {
        anchor = slot(sec.getAttribute("data-video"));
        h.insertAdjacentElement("afterend", anchor);
      }
      var intro = Array.prototype.filter.call(sec.children, function (c) { return c.tagName === "P"; });
      var d = fold(intro, "vid.more");
      if (d) anchor.insertAdjacentElement("afterend", d);
    });
    // 3) Сөздүк: сөз гана көрүнөт, басканда түшүндүрмөсү ачылат
    document.querySelectorAll(".gloss").forEach(function (dl) {
      dl.classList.add("gloss-fold");
      dl.querySelectorAll(":scope > div").forEach(function (row) {
        var dt = row.querySelector("dt");
        if (!dt) return;
        dt.setAttribute("role", "button");
        dt.setAttribute("tabindex", "0");
        dt.setAttribute("aria-expanded", "false");
        function toggle() {
          var open = !row.classList.contains("open");
          row.classList.toggle("open", open);
          dt.setAttribute("aria-expanded", String(open));
        }
        dt.addEventListener("click", toggle);
        dt.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); } });
      });
    });
    AT.onLang(function () {
      document.querySelectorAll("[data-vt]").forEach(function (el) { el.textContent = AT.t(el.getAttribute("data-vt")); });
      // Тил алмашса жана башка тилдеги видео бар болсо — ойноткучту алмаштырабыз
      document.querySelectorAll(".vslot[data-video-key]").forEach(function (old) {
        var key = old.getAttribute("data-video-key");
        if (urlFor(key) !== old.getAttribute("data-video-url")) old.replaceWith(slot(key));
      });
    });
    devNote();
  }

  /* Локалдык текшерүүдө: канча видео коюлганын консолго жазат */
  function devNote() {
    if (!/^(localhost|127\.0\.0\.1)$/.test(location.hostname)) return;
    var v = videos(), keys = Object.keys(v), have = keys.filter(function (k) { return String(v[k] || "").trim(); });
    console.info("[AITRADING] Видео-нускамалар: " + have.length + " / " + keys.length + " коюлган (config.js → VIDEOS).");
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
