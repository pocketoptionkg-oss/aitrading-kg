/* «Трейдерлердин пикири» бети.
   1) Пикирлер: assets/data/opinions.json → { "items": [ { "nick", "date", "broker", "text", "img", "link" } ] }.
      Ник сайтта ар дайым кыскартылат (Tr***G). Пикирлер ойлоп табылбайт — админ чыныгы постторду макулдук менен гана кошот.
   2) Рамка: скриншот + ник + пикир → AITRADING бренддик сүрөтү (canvas, 1080×1080 же 1080×1920).
      Сүрөт түзмөктөн чыкпайт. Купуя жерлерди тик бурчтук тартып бүдөмүктөөгө болот. */
(function () {
  "use strict";
  if (!window.AT) return;
  var T = AT.t;
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function mask(n) {
    n = String(n || "").trim().replace(/^@/, "");
    if (!n) return "Trader";
    var a = Array.from(n);
    if (a.length <= 3) return a[0] + "**";
    return a.slice(0, 2).join("") + "***" + a[a.length - 1];
  }
  /* Браузерлерде кыргызча ай аттары көбүнчө жок — өзүбүз: «2026-жылдын 22-ноябры» ордуна кыскасы «22-ноябрь, 2026» */
  var KY_M = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"];
  function dstr(d, short) {
    if (AT.lang() === "ru") return d.toLocaleDateString("ru-RU", { day: "numeric", month: short ? "short" : "long", year: "numeric" });
    return d.getDate() + "-" + KY_M[d.getMonth()] + ", " + d.getFullYear();
  }
  function today() { return dstr(new Date()); }

  /* ================= 1. Пикирлер ================= */
  var items = [], flt = "all";
  function renderFeed() {
    var box = document.querySelector("[data-feed]");
    if (!box) return;
    var list = items.filter(function (x) { return flt === "all" || String(x.broker || "").toLowerCase() === flt; });
    if (!list.length) {
      box.innerHTML = '<div class="tr-empty"><span aria-hidden="true">💬</span><b>' + esc(T(items.length ? "tr.empty_f" : "tr.empty")) + "</b><p>" + esc(T("tr.empty_p")) + '</p><a class="btn btn-mint btn-sm" href="#frame">' + esc(T("tr.go_frame")) + "</a></div>";
      return;
    }
    box.innerHTML = list.map(function (x) {
      var nick = mask(x.nick), d = x.date ? new Date(x.date) : null;
      var date = d && !isNaN(d) ? dstr(d, true) : "";
      var img = /^(assets\/|https:\/\/)/.test(String(x.img || "")) ? '<a class="tr-img" href="' + esc(x.img) + '" target="_blank" rel="noopener"><img src="' + esc(x.img) + '" alt="" loading="lazy"></a>' : "";
      var link = /^https:\/\//.test(String(x.link || "")) ? '<a class="tr-src" href="' + esc(x.link) + '" target="_blank" rel="noopener nofollow ugc">' + esc(T("tr.source")) + " ↗</a>" : "";
      return '<article class="tr-card">' +
        '<header><span class="tr-ava" aria-hidden="true">' + esc(Array.from(nick)[0].toUpperCase()) + "</span><div><b>" + esc(nick) + "</b><small>" + esc(date) + "</small></div>" +
        (x.broker ? '<span class="badge ' + (/binodex/i.test(x.broker) ? "badge-mint" : "badge-blue") + '">' + esc(x.broker) + "</span>" : "") + "</header>" +
        (x.text ? "<p>" + esc(x.text) + "</p>" : "") + img +
        '<footer><span>' + esc(T("tr.personal")) + "</span>" + link + "</footer></article>";
    }).join("");
  }
  function initFeed() {
    if (!document.querySelector("[data-feed]")) return;
    fetch("assets/data/opinions.json", { cache: "no-cache" }).then(function (r) { return r.ok ? r.json() : { items: [] }; }).catch(function () { return { items: [] }; }).then(function (j) {
      items = (j.items || []).filter(function (x) { return x && (x.text || x.img); });
      renderFeed();
    });
    document.querySelectorAll("[data-flt]").forEach(function (b) {
      b.addEventListener("click", function () {
        flt = b.getAttribute("data-flt");
        document.querySelectorAll("[data-flt]").forEach(function (x) { x.setAttribute("aria-pressed", String(x === b)); });
        renderFeed();
      });
    });
    AT.onLang(renderFeed);
  }

  /* ================= 2. Рамка ================= */
  var S = { img: null, fname: "", nick: "", mask: true, text: "", broker: "", fmt: "sq", blurs: [], map: null, drag: null };
  var cv, ctx;

  function rr(c, x, y, w, h, r) {
    c.beginPath();
    c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r); c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r);
    c.closePath();
  }
  function wrap(c, text, maxW, maxLines) {
    var words = String(text).split(/\s+/).filter(Boolean), lines = [], cur = "";
    words.forEach(function (w) {
      var t = cur ? cur + " " + w : w;
      if (c.measureText(t).width > maxW && cur) { lines.push(cur); cur = w; } else cur = t;
    });
    if (cur) lines.push(cur);
    if (lines.length > maxLines) { lines = lines.slice(0, maxLines); lines[maxLines - 1] = lines[maxLines - 1].replace(/\s*\S*$/, "") + "…"; }
    return lines;
  }
  /* Бүдөмүктөө: аймакты кичирейтип, кайра чоңойтуп — пикселдер (бардык браузерлерде иштейт) */
  function pixelate(img, r, dx, dy, k) {
    var tmp = document.createElement("canvas"), cw = Math.max(1, Math.round(r.w / 14)), ch = Math.max(1, Math.round(r.h / 14));
    tmp.width = cw; tmp.height = ch;
    tmp.getContext("2d").drawImage(img, r.x, r.y, r.w, r.h, 0, 0, cw, ch);
    ctx.save();
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(tmp, 0, 0, cw, ch, dx + r.x * k, dy + r.y * k, r.w * k, r.h * k);
    ctx.restore();
  }

  function draw() {
    if (!cv) return;
    var W = 1080, H = S.fmt === "st" ? 1920 : 1080;
    if (cv.height !== H) cv.height = H;
    var g = ctx.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, "#0d1626"); g.addColorStop(1, "#070b12");
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    var glow = ctx.createRadialGradient(140, 120, 10, 140, 120, 520);
    glow.addColorStop(0, "rgba(92,232,170,0.16)"); glow.addColorStop(1, "rgba(92,232,170,0)");
    ctx.fillStyle = glow; ctx.fillRect(0, 0, W, H);
    var glow2 = ctx.createRadialGradient(W - 120, H - 160, 10, W - 120, H - 160, 560);
    glow2.addColorStop(0, "rgba(255,204,21,0.12)"); glow2.addColorStop(1, "rgba(255,204,21,0)");
    ctx.fillStyle = glow2; ctx.fillRect(0, 0, W, H);

    var head = "Montserrat, 'Segoe UI', sans-serif", body = "Inter, 'Segoe UI', sans-serif";
    var top = S.fmt === "st" ? 120 : 48;
    // Бренд
    rr(ctx, 60, top, 92, 64, 16); ctx.fillStyle = "#5ce8aa"; ctx.fill();
    ctx.fillStyle = "#04170f"; ctx.font = "800 38px " + head; ctx.textBaseline = "middle"; ctx.textAlign = "center";
    ctx.fillText("AI", 106, top + 34);
    ctx.textAlign = "left"; ctx.font = "800 40px " + head; ctx.fillStyle = "#e9eef6";
    ctx.fillText("TRADING", 170, top + 34);
    var tw = ctx.measureText("TRADING").width;
    ctx.fillStyle = "#ffcc15"; ctx.fillText(".KG", 170 + tw, top + 34);
    ctx.font = "600 24px " + body; ctx.fillStyle = "#9aa6b8"; ctx.textAlign = "right";
    ctx.fillText(T("tr.cv_tag"), W - 60, top + 34);
    ctx.textAlign = "left";

    // Төмөнкү тилке жана пикир — ордун эсептейбиз
    var footH = 150, nickH = 96;
    ctx.font = "600 " + (S.img ? 38 : 54) + "px " + body;
    var lines = S.text ? wrap(ctx, "«" + S.text + "»", W - 160, S.img ? 3 : 6) : [];
    var lh = S.img ? 50 : 70, textH = lines.length ? lines.length * lh + 24 : 0;
    var imgTop = top + 100, imgBot = H - footH - nickH - textH - 24;

    // Скриншот
    S.map = null;
    if (S.img && imgBot - imgTop > 120) {
      var bw = W - 120, bh = imgBot - imgTop, iw = S.img.naturalWidth, ih = S.img.naturalHeight;
      var k = Math.min(bw / iw, bh / ih), dw = iw * k, dh = ih * k, dx = 60 + (bw - dw) / 2, dy = imgTop + (bh - dh) / 2;
      ctx.save(); rr(ctx, dx, dy, dw, dh, 22); ctx.clip();
      ctx.drawImage(S.img, dx, dy, dw, dh);
      S.blurs.forEach(function (r) { pixelate(S.img, r, dx, dy, k); });
      ctx.restore();
      rr(ctx, dx, dy, dw, dh, 22); ctx.strokeStyle = "rgba(255,255,255,0.14)"; ctx.lineWidth = 3; ctx.stroke();
      S.map = { dx: dx, dy: dy, dw: dw, dh: dh, k: k };
    } else if (!S.img) {
      // Скриншотсуз — чоң тырмакча белгиси
      ctx.font = "800 220px " + head; ctx.fillStyle = "rgba(92,232,170,0.18)"; ctx.fillText("“", 50, imgTop + 140);
    }
    // Тартылып жаткан тик бурчтук
    if (S.drag && S.drag.w) {
      ctx.save(); ctx.setLineDash([12, 8]); ctx.strokeStyle = "#ffcc15"; ctx.lineWidth = 4;
      ctx.strokeRect(S.drag.x, S.drag.y, S.drag.w, S.drag.h); ctx.restore();
    }

    // Пикир
    var y = H - footH - nickH - textH + 8;
    if (!S.img) y = Math.max(imgTop + 120, (H - footH - nickH) / 2 - textH / 2);
    ctx.fillStyle = "#e9eef6"; ctx.font = "600 " + (S.img ? 38 : 54) + "px " + body; ctx.textBaseline = "top";
    lines.forEach(function (l, i) { ctx.fillText(l, 80, y + i * lh); });

    // Ник, дата, платформа
    var ny = H - footH - nickH + 8, nick = S.mask ? mask(S.nick) : (S.nick || "Trader");
    ctx.beginPath(); ctx.arc(104, ny + 36, 34, 0, Math.PI * 2); ctx.fillStyle = "#131d2e"; ctx.fill();
    ctx.strokeStyle = "rgba(92,232,170,0.6)"; ctx.lineWidth = 3; ctx.stroke();
    ctx.fillStyle = "#5ce8aa"; ctx.font = "800 32px " + head; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText(Array.from(nick)[0].toUpperCase(), 104, ny + 37);
    ctx.textAlign = "left"; ctx.fillStyle = "#e9eef6"; ctx.font = "800 34px " + head; ctx.fillText(nick, 156, ny + 22);
    ctx.fillStyle = "#9aa6b8"; ctx.font = "500 24px " + body; ctx.fillText(today(), 156, ny + 58);
    if (S.broker) {
      ctx.font = "700 26px " + head;
      var pw = ctx.measureText(S.broker).width + 40, px = W - 60 - pw;
      rr(ctx, px, ny + 14, pw, 46, 23); ctx.fillStyle = /bino/i.test(S.broker) ? "rgba(92,232,170,0.16)" : "rgba(59,123,255,0.2)"; ctx.fill();
      ctx.fillStyle = /bino/i.test(S.broker) ? "#5ce8aa" : "#8fb2ff"; ctx.textAlign = "center"; ctx.fillText(S.broker, px + pw / 2, ny + 38); ctx.textAlign = "left";
    }

    // Төмөнкү тилке
    var fy = H - footH;
    ctx.fillStyle = "rgba(255,255,255,0.05)"; ctx.fillRect(0, fy, W, footH);
    ctx.fillStyle = "#ffcc15"; ctx.fillRect(0, fy, W, 4);
    ctx.textBaseline = "middle";
    ctx.fillStyle = "#5ce8aa"; ctx.font = "800 40px " + head; ctx.fillText("aitrading.kg", 60, fy + 52);
    ctx.fillStyle = "#c9d2df"; ctx.font = "600 24px " + body; ctx.textAlign = "right";
    ctx.fillText(T("tr.cv_slogan"), W - 60, fy + 52); ctx.textAlign = "left";
    ctx.fillStyle = "#6d7a8f"; ctx.font = "500 21px " + body;
    ctx.fillText(T("tr.cv_disc"), 60, fy + 108);

    var has = !!(S.img || S.text);
    cv.classList.toggle("has-img", !!S.map);   // сүрөт бар болсо — манжа менен тартканда барак жылбайт
    document.querySelector("[data-fr-dl]").disabled = !has;
    var hint = document.querySelector("[data-fr-hint]");
    if (hint) hint.hidden = has;
  }

  /* Сүрөттүн үстүнөн тик бурчтук тартуу → бүдөмүк */
  function toCanvas(e) {
    var r = cv.getBoundingClientRect();
    return { x: (e.clientX - r.left) * cv.width / r.width, y: (e.clientY - r.top) * cv.height / r.height };
  }
  function initDrag() {
    cv.addEventListener("pointerdown", function (e) {
      if (!S.map) return;
      var p = toCanvas(e);
      S.drag = { x0: p.x, y0: p.y, x: p.x, y: p.y, w: 0, h: 0 };
      try { cv.setPointerCapture(e.pointerId); } catch (err) { /* эски браузер */ }
      e.preventDefault();
    });
    cv.addEventListener("pointermove", function (e) {
      if (!S.drag) return;
      var p = toCanvas(e), d = S.drag;
      d.x = Math.min(d.x0, p.x); d.y = Math.min(d.y0, p.y); d.w = Math.abs(p.x - d.x0); d.h = Math.abs(p.y - d.y0);
      draw();
    });
    function end() {
      var d = S.drag, m = S.map;
      S.drag = null;
      if (d && m && d.w > 12 && d.h > 12) {
        // canvas → сүрөттүн өз координаттары (сүрөттүн чегинде гана)
        var x1 = Math.max(m.dx, d.x), y1 = Math.max(m.dy, d.y), x2 = Math.min(m.dx + m.dw, d.x + d.w), y2 = Math.min(m.dy + m.dh, d.y + d.h);
        if (x2 > x1 && y2 > y1) S.blurs.push({ x: (x1 - m.dx) / m.k, y: (y1 - m.dy) / m.k, w: (x2 - x1) / m.k, h: (y2 - y1) / m.k });
        AT.track("frame_blur", {});
      }
      draw();
    }
    cv.addEventListener("pointerup", end);
    cv.addEventListener("pointercancel", end);
  }

  function initFrame() {
    cv = document.querySelector("[data-fr-canvas]");
    if (!cv) return;
    ctx = cv.getContext("2d");
    var q = function (s) { return document.querySelector(s); };
    q("[data-fr-file]").addEventListener("change", function () {
      var f = this.files && this.files[0];
      if (!f || !/^image\//.test(f.type)) return;
      var url = URL.createObjectURL(f), im = new Image();
      im.onload = function () { S.img = im; S.blurs = []; draw(); AT.track("frame_image", {}); };
      im.src = url;
      S.fname = f.name;
      q("[data-fr-fname]").textContent = f.name;
      q("[data-fr-fname]").removeAttribute("data-i18n");
    });
    q("[data-fr-nick]").addEventListener("input", function () { S.nick = this.value; draw(); });
    q("[data-fr-mask]").addEventListener("change", function () { S.mask = this.checked; draw(); });
    q("[data-fr-text]").addEventListener("input", function () { S.text = this.value.trim(); q("[data-fr-count]").textContent = this.value.length + "/140"; draw(); });
    q("[data-fr-broker]").addEventListener("change", function () { S.broker = this.value; draw(); });
    document.querySelectorAll("[data-fr-fmt]").forEach(function (b) {
      b.addEventListener("click", function () {
        S.fmt = b.getAttribute("data-fr-fmt");
        document.querySelectorAll("[data-fr-fmt]").forEach(function (x) { x.setAttribute("aria-pressed", String(x === b)); });
        cv.classList.toggle("st", S.fmt === "st");
        draw();
      });
    });
    q("[data-fr-unblur]").addEventListener("click", function () { S.blurs = []; draw(); });
    function blob() { return new Promise(function (res) { cv.toBlob(res, "image/png"); }); }
    function fname() { return "aitrading-" + new Date().toISOString().slice(0, 10) + (S.fmt === "st" ? "-story" : "") + ".png"; }
    q("[data-fr-dl]").addEventListener("click", function () {
      blob().then(function (b) {
        var a = document.createElement("a");
        a.href = URL.createObjectURL(b);
        a.download = fname();
        document.body.appendChild(a); a.click(); a.remove();
        setTimeout(function () { URL.revokeObjectURL(a.href); }, 4000);
        AT.track("frame_download", { fmt: S.fmt });
      });
    });
    var share = q("[data-fr-share]");
    try {
      var probe = new File([new Blob(["x"], { type: "image/png" })], "x.png", { type: "image/png" });
      if (navigator.canShare && navigator.canShare({ files: [probe] })) share.hidden = false;
    } catch (e) { /* бөлүшүү жок */ }
    share.addEventListener("click", function () {
      blob().then(function (b) {
        var file = new File([b], fname(), { type: "image/png" });
        return navigator.share({ files: [file], text: "aitrading.kg" });
      }).then(function () { AT.track("frame_share", { fmt: S.fmt }); }).catch(function () { /* колдонуучу жапты */ });
    });
    initDrag();
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(draw);
    AT.onLang(draw);
    draw();
  }

  function init() { initFeed(); initFrame(); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
