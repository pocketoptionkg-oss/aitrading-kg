/* AITRADING.KG — service worker: телефонго орнотуу (PWA), офлайн кабык жана билдирмелер.
   Маалымат (assets/data/*, биржа API) — ар дайым тармактан; калган файлдар — кэштен тез. */
var VERSION = "aitrading-v5";
var SHELL = [
  "./", "index.html", "forecast.html", "trends.html", "news.html", "learn.html", "marketing.html", "analyzer.html", "register.html", "tools.html", "security.html", "traders.html",
  "assets/js/register.js", "assets/js/i18n-more.js", "assets/js/tools.js", "assets/js/security.js", "assets/js/traders.js", "assets/css/pages.css", "assets/js/lessons.js",
  "assets/css/style.css", "assets/js/config.js", "assets/js/i18n.js", "assets/js/main.js", "assets/js/ai-engine.js",
  "assets/js/ai-voice.js", "assets/js/ai-spider.js", "assets/js/ai-analyst.js", "assets/js/ai-page.js", "assets/js/trends.js",
  "assets/js/posts.js", "assets/js/home.js", "assets/js/news.js", "assets/js/analyzer.js", "assets/vendor/lightweight-charts-4.2.0.js",
  "assets/img/favicon.svg", "assets/img/icon-192.png", "assets/img/icon-512.png", "assets/img/author.webp", "assets/img/binodex-logo.png",
  "manifest.webmanifest"
];

self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(VERSION).then(function (c) { return c.addAll(SHELL).catch(function () {}); }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== VERSION; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener("fetch", function (e) {
  var url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;          // биржалар, TradingView — түз
  if (url.pathname.indexOf("/assets/data/") >= 0) return;                                // маалымат — дайыма жаңы
  if (/\.(mp4|webm|mov)$/i.test(url.pathname)) return;                                   // видео — бөлүктөп жүктөлөт, кэшке салынбайт
  // Тармак биринчи (жаңы версия тез жетсин), болбосо кэш
  e.respondWith(fetch(e.request).then(function (r) {
    var copy = r.clone();
    caches.open(VERSION).then(function (c) { c.put(e.request, copy); });
    return r;
  }).catch(function () { return caches.match(e.request).then(function (m) { return m || caches.match("index.html"); }); }));
});

/* Билдирмени басканда — сайтты ачуу */
self.addEventListener("notificationclick", function (e) {
  e.notification.close();
  var target = (e.notification.data && e.notification.data.url) || "forecast.html";
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (list) {
    for (var i = 0; i < list.length; i++) {
      if ("focus" in list[i]) { list[i].navigate(target).catch(function () {}); return list[i].focus(); }
    }
    return self.clients.openWindow(target);
  }));
});

/* Келечекте: сервердик Web Push (жабык тиркемеге билдирме) ушул жерден көрсөтүлөт */
self.addEventListener("push", function (e) {
  var d = {};
  try { d = e.data ? e.data.json() : {}; } catch (err) { d = { title: "AITRADING.KG", body: e.data ? e.data.text() : "" }; }
  e.waitUntil(self.registration.showNotification(d.title || "AITRADING.KG", {
    body: d.body || "", icon: "assets/img/icon-192.png", badge: "assets/img/icon-192.png", tag: d.tag || "aitrading", data: { url: d.url || "forecast.html" }
  }));
});
