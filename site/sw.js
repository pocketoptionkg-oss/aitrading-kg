/* AITRADING.KG — service worker: телефонго орнотуу (PWA), офлайн кабык жана билдирмелер.
   Маалымат (assets/data/*, биржа API) — ар дайым тармактан; калган файлдар — кэштен тез. */
var VERSION = "aitrading-v7";
var PREFS = "aitrading-prefs";   // колдонуучунун тили (билдирменин тили үчүн) — жаңыртууда өчүрүлбөйт
var SHELL = [
  "./", "index.html", "forecast.html", "trends.html", "news.html", "learn.html", "marketing.html", "analyzer.html", "register.html", "tools.html", "security.html", "traders.html",
  "assets/js/register.js", "assets/js/i18n-more.js", "assets/js/tools.js", "assets/js/security.js", "assets/js/traders.js", "assets/css/pages.css", "assets/js/lessons.js", "assets/js/chartbox.js", "assets/css/chartbox.css",
  "assets/css/style.css", "assets/js/config.js", "assets/js/i18n.js", "assets/js/main.js", "assets/js/ai-engine.js",
  "assets/js/ai-voice.js", "assets/js/ai-spider.js", "assets/js/ai-analyst.js", "assets/js/ai-page.js", "assets/js/trends.js",
  "assets/js/posts.js", "assets/js/home.js", "assets/js/news.js", "assets/js/analyzer.js", "assets/vendor/lightweight-charts-4.2.0.js",
  "assets/js/alerts.js", "assets/js/i18n-news.js", "assets/img/author-avatar.webp",
  "assets/img/favicon.svg", "assets/img/icon-192.png", "assets/img/icon-512.png", "assets/img/author.webp", "assets/img/binodex-logo.png",
  "manifest.webmanifest"
];

self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(VERSION).then(function (c) { return c.addAll(SHELL).catch(function () {}); }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== VERSION && k !== PREFS; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener("fetch", function (e) {
  var url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;          // биржалар, TradingView — түз
  if (url.pathname.indexOf("/assets/data/") >= 0) return;                                // маалымат — дайыма жаңы
  if (url.pathname.indexOf("/api/") === 0) return;                                       // ИИ-жардамчы ж.б. — сервер, кэш жок
  if (url.pathname.indexOf("/r/") === 0) return;                                         // өнөктөштүн шилтемеси — сервер эсептейт жана багыттайт
  if (/\.(mp4|webm|mov)$/i.test(url.pathname)) return;                                   // видео — бөлүктөп жүктөлөт, кэшке салынбайт
  // Тармак биринчи (жаңы версия тез жетсин), болбосо кэш
  e.respondWith(fetch(e.request).then(function (r) {
    var copy = r.clone();
    caches.open(VERSION).then(function (c) { c.put(e.request, copy); });
    return r;
  }).catch(function () { return caches.match(e.request).then(function (m) { return m || caches.match("index.html"); }); }));
});

/* Билдирмени басканда — сайтты ачуу (тышкы шилтеме болсо — жаңы терезеде) */
self.addEventListener("notificationclick", function (e) {
  e.notification.close();
  var target = (e.notification.data && e.notification.data.url) || "forecast.html";
  var external = /^https?:/i.test(target) && new URL(target).origin !== location.origin;
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (list) {
    if (!external) {
      for (var i = 0; i < list.length; i++) {
        if ("focus" in list[i]) { list[i].navigate(target).catch(function () {}); return list[i].focus(); }
      }
    }
    return self.clients.openWindow(target);
  }));
});

/* Сервердик Web Push (тиркеме/сайт жабык болсо да). Сервер (functions/api/live.js) push'ту бош жөнөтөт —
   бул жерде /api/live'дан эң акыркы шашылыш жаңылыкты окуп, колдонуучунун тилинде көрсөтөбүз. */
function prefLang() {
  return caches.open(PREFS).then(function (c) { return c.match("lang"); }).then(function (r) { return r ? r.text() : "ky"; }).catch(function () { return "ky"; });
}
function latestFromLive(j, lang) {
  var l = lang === "ru" ? "ru" : "ky", T = { ky: "⚠️ Шашылыш · AITRADING.KG", ru: "⚠️ Срочно · AITRADING.KG" };
  var cand = [];
  (j.urgent || []).forEach(function (u) { cand.push({ t: u.t, body: u[l] || u.ky || u.ru, url: u.url || "news.html#pulse", tag: "aitrading-" + u.id }); });
  if (j.alert) cand.push({ t: j.alert.t, body: j.alert[l] || j.alert.ky, url: "news.html#pulse", tag: "aitrading-market" });
  (j.tweets || []).slice(0, 1).forEach(function (w) {
    cand.push({ t: w.t, title: (w.name || "@" + w.handle) + " · X", body: w[l] || w.text, url: "news.html#tweets", tag: "aitrading-" + w.id });
  });
  cand.sort(function (a, b) { return b.t - a.t; });
  var c = cand[0] || { body: l === "ru" ? "Откройте новости на сайте." : "Сайттан жаңылыктарды ачыңыз.", url: "news.html" };
  return { title: c.title || T[l], body: c.body, url: c.url, tag: c.tag || "aitrading-urgent" };
}
self.addEventListener("push", function (e) {
  var d = null;
  try { d = e.data ? e.data.json() : null; } catch (err) { d = e.data ? { title: "AITRADING.KG", body: e.data.text() } : null; }
  var job = d ? Promise.resolve(d) : prefLang().then(function (lang) {
    return fetch("/api/live?sw=" + Date.now(), { cache: "no-store" }).then(function (r) { return r.json(); }).then(function (j) { return latestFromLive(j, lang); })
      .catch(function () { return latestFromLive({}, lang); });
  });
  e.waitUntil(job.then(function (n) {
    return self.registration.showNotification(n.title || "AITRADING.KG", {
      body: n.body || "", icon: "assets/img/icon-192.png", badge: "assets/img/icon-192.png", tag: n.tag || "aitrading", renotify: true,
      vibrate: [90, 50, 90], data: { url: n.url || "news.html" }
    });
  }));
});
