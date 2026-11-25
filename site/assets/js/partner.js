/* AITRADING.KG — «Маркетинг»: өнөктөштүн башкаруу панели / панель управления партнёра.
   Кирүү Telegram-бот аркылуу: бот кол коюлган шилтеме берет marketing.html#p=<tg36>.<exp36>.<sig> (30 күн).
   Токен ушул браузерде сакталат (localStorage), даректен өчүрүлөт. Маалымат: GET /api/partner?t=<токен>
   (functions/api/partner.js). Чакырылгандардын аты, номери көрсөтүлбөйт — эсептер гана. */
(function () {
  "use strict";
  var KEY = "aitrading-ptn";

  var TXT = {
    ky: {
      login: "Башкаруу панелине кирүү",
      bot_soon: "Telegram-бот жакында ачылат",
      loading: "Панель жүктөлүүдө…",
      bad: "Кирүү шилтемеси жараксыз же мөөнөтү бүттү. Ботто «🤝 Өнөктөштүк» → «📊 Башкаруу панели» баскычын кайра басыңыз.",
      net: "Сервер жооп берген жок. Интернетти текшерип, кайра жаңыртыңыз.",
      pending: "Панель даярдалууда: бот маалыматты бир нече мүнөттө жөнөтөт. Бир аздан кийин бетти жаңыртыңыз.",
      retry: "Жаңыртуу",
      title: "Башкаруу панели",
      code: "Код",
      logout: "Чыгуу",
      main: "Жеке шилтемеңиз",
      main_note: "Шилтеме ботко алып барат: ал жерде адам катталып, ID жөнөткөндө жана толуктаганда сиздин статистикаңызга кошулат.",
      main_note_bd: "Шилтеме сизге берилген BinoDex шилтемесине алып барат. Ботко келгендер да эсептелет.",
      copy: "Көчүрүү", copied: "Көчүрүлдү ✓", share: "Бөлүшүү",
      more: "Башка шилтемелер",
      l_bot: "Telegram-бот аркылуу", l_bd: "Түз BinoDex", l_bx: "Түз BingX",
      more_note: "Түз брокерге кеткен адам ботко келбесе, анын катталуусу бул панелде көрүнбөйт (өтүү гана эсептелет).",
      k_clicks: "Шилтемеге өтүү", k_clicks_s: "30 күндө {d30} · 7 күндө {d7}",
      k_inv: "Ботко келди", k_reg: "Брокерде катталды", k_fund: "Эсебин толуктады", k_fund_s: "азыр доступу ачык: {a}",
      conv: "{p}% мурунку кадамдан",
      money: "Акча", m_earned: "Эсептелди", m_paid: "Төлөндү", m_due: "Төлөнө элек",
      m_note: "{pct}% — сиз чакырган трейдерлер үчүн брокер авторго төлөгөн кирешеден. Кирешени автор айына бир жолу брокердин кабинетинен киргизет; төлөм кол менен. Брокер төлөбөсө — 0.",
      months: "Айлар", th_m: "Ай", th_inc: "Авторго киреше", th_pay: "Сизге ({pct}%)", th_st: "Абалы",
      st_paid: "✅ төлөндү", st_wait: "⏳ төлөнө элек", no_months: "Азырынча эсептелген ай жок.",
      days: "Акыркы күндөр", th_d: "Күн", th_inv: "Келди", th_reg: "Катталды", th_fund: "Толуктады", no_days: "Азырынча эч ким келе элек — шилтемеңизди бөлүшүңүз.",
      pay_warn: "Төлөм реквизиттери коюла элек: ботто «🤝 Өнөктөштүк» → «💳 Төлөм реквизиттери».",
      off: "Өнөктөштүгүңүз азыр өчүрүлгөн. Суроо болсо — ботто «💬 Колдоо».",
      updated: "Маалымат жаңыртылды: {t}. Бот аны 10 мүнөт сайын жөнөтөт.",
      share_text: "AITRADING.KG — ИИ сигналдары жана сабактар (BinoDex, BingX). 18+, соода тобокелдиктүү."
    },
    ru: {
      login: "Войти в панель управления",
      bot_soon: "Telegram-бот скоро откроется",
      loading: "Загружаем панель…",
      bad: "Ссылка для входа недействительна или устарела. В боте нажмите «🤝 Партнёрка» → «📊 Панель управления» ещё раз.",
      net: "Сервер не ответил. Проверьте интернет и обновите страницу.",
      pending: "Панель готовится: бот пришлёт данные в течение нескольких минут. Обновите страницу чуть позже.",
      retry: "Обновить",
      title: "Панель управления",
      code: "Код",
      logout: "Выйти",
      main: "Ваша личная ссылка",
      main_note: "Ссылка ведёт в бота: когда человек там регистрируется, отправляет ID и пополняет счёт, это попадает в вашу статистику.",
      main_note_bd: "Ссылка ведёт на выданную вам ссылку BinoDex. Те, кто пришёл в бот, тоже учитываются.",
      copy: "Копировать", copied: "Скопировано ✓", share: "Поделиться",
      more: "Другие ссылки",
      l_bot: "Через Telegram-бота", l_bd: "Напрямую BinoDex", l_bx: "Напрямую BingX",
      more_note: "Если человек ушёл прямо к брокеру и не пришёл в бот, его регистрация в этой панели не видна (считается только переход).",
      k_clicks: "Переходов по ссылке", k_clicks_s: "за 30 дней {d30} · за 7 дней {d7}",
      k_inv: "Пришли в бот", k_reg: "Зарегистрировались", k_fund: "Пополнили счёт", k_fund_s: "сейчас с доступом: {a}",
      conv: "{p}% от предыдущего шага",
      money: "Деньги", m_earned: "Начислено", m_paid: "Выплачено", m_due: "К выплате",
      m_note: "{pct}% — от дохода, который брокер платит автору за приглашённых вами трейдеров. Доход автор вносит раз в месяц из кабинета брокера; выплата вручную. Если брокер ничего не заплатил — 0.",
      months: "По месяцам", th_m: "Месяц", th_inc: "Доход автора", th_pay: "Вам ({pct}%)", th_st: "Статус",
      st_paid: "✅ выплачено", st_wait: "⏳ к выплате", no_months: "Начислений пока нет.",
      days: "Последние дни", th_d: "День", th_inv: "Пришли", th_reg: "Зарегистр.", th_fund: "Пополнили", no_days: "Пока никто не пришёл — поделитесь ссылкой.",
      pay_warn: "Реквизиты для выплаты не указаны: в боте «🤝 Партнёрка» → «💳 Реквизиты для выплаты».",
      off: "Ваше партнёрство сейчас отключено. Вопросы — в боте «💬 Поддержка».",
      updated: "Данные обновлены: {t}. Бот присылает их каждые 10 минут.",
      share_text: "AITRADING.KG — ИИ-сигналы и обучение (BinoDex, BingX). 18+, торговля рискованна."
    }
  };

  var state = { data: null, err: null, loading: false };

  function L() { return window.AT && AT.lang() === "ru" ? "ru" : "ky"; }
  function tx(k, o) {
    var s = TXT[L()][k] !== undefined ? TXT[L()][k] : TXT.ky[k];
    return String(s).replace(/\{(\w+)\}/g, function (_, x) { return o && o[x] !== undefined ? o[x] : ""; });
  }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function money(v) { v = +v || 0; return "$" + (Math.round(v * 100) / 100).toLocaleString("en-US", { maximumFractionDigits: 2 }); }
  function num(v) { return (+v || 0).toLocaleString("ru-RU"); }
  function getTok() { try { return localStorage.getItem(KEY) || ""; } catch (e) { return ""; } }
  function setTok(v) { try { if (v) localStorage.setItem(KEY, v); else localStorage.removeItem(KEY); } catch (e) { /* жеке режим */ } }
  function conv(a, b) { return b > 0 ? tx("conv", { p: Math.round((a / b) * 100) }) : ""; }

  /* #p=<токен> → сактоо, даректен өчүрүү (бөлүшүлгөн скриншотто/шилтемеде токен калбасын) */
  function takeHash() {
    var m = /[#&]p=([0-9a-z]{1,13}\.[0-9a-z]{1,10}\.[A-Za-z0-9_-]{22})/.exec(location.hash || "");
    if (!m) return;
    setTok(m[1]);
    try { history.replaceState(null, "", location.pathname + location.search + "#panel"); } catch (e) { location.hash = "panel"; }
  }

  function copy(text, btn) {
    function ok() {
      if (btn) { var o = btn.textContent; btn.textContent = tx("copied"); setTimeout(function () { btn.textContent = o; }, 1600); }
    }
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(ok, fallback);
    else fallback();
    function fallback() {
      var ta = document.createElement("textarea");
      ta.value = text; ta.setAttribute("readonly", ""); ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta); ta.select();
      try { document.execCommand("copy"); ok(); } catch (e) { /* көчүрүлгөн жок */ }
      document.body.removeChild(ta);
    }
  }

  function linkRow(label, url, cls) {
    return '<div class="pp-link ' + (cls || "") + '"><div class="pp-link-l"><span>' + esc(label) + '</span><code>' + esc(url) + "</code></div>" +
      '<button type="button" class="btn btn-ghost btn-sm" data-pp-copy="' + esc(url) + '">' + esc(tx("copy")) + "</button></div>";
  }

  function kpi(label, val, sub, tone) {
    return '<div class="pp-kpi' + (tone ? " pp-" + tone : "") + '"><span class="pp-kpi-l">' + esc(label) + '</span><b>' + esc(val) + "</b>" +
      (sub ? '<small>' + esc(sub) + "</small>" : "") + "</div>";
  }

  function render() {
    var box = document.getElementById("pp");
    if (!box) return;
    var tok = getTok();
    box.hidden = !tok;
    document.querySelectorAll("[data-pp-hide]").forEach(function (el) { el.hidden = !!tok; });
    if (!tok) { box.innerHTML = ""; return; }
    if (state.loading && !state.data) { box.innerHTML = '<div class="pp-card pp-msg">' + esc(tx("loading")) + "</div>"; return; }
    if (state.err) {
      box.innerHTML = '<div class="pp-card pp-msg"><p>' + esc(tx(state.err)) + '</p><div class="pp-row">' +
        (state.err === "bad" ? loginBtn("btn-mint") : '<button type="button" class="btn btn-mint" data-pp-retry>' + esc(tx("retry")) + "</button>") +
        '<button type="button" class="btn btn-ghost" data-pp-logout>' + esc(tx("logout")) + "</button></div></div>";
      return;
    }
    var d = state.data;
    if (!d) return;
    if (d.pending) {
      box.innerHTML = '<div class="pp-card pp-msg"><p>' + esc(tx("pending")) + '</p><div class="pp-row"><button type="button" class="btn btn-mint" data-pp-retry>' +
        esc(tx("retry")) + '</button><button type="button" class="btn btn-ghost" data-pp-logout>' + esc(tx("logout")) + "</button></div></div>";
      return;
    }
    var s = d.snap, c = s.counts || {}, ck = d.clicks || {}, t = s.totals || {}, pct = Math.round((s.share || 0.6) * 100);
    var lk = s.links || {};
    var share = "https://t.me/share/url?url=" + encodeURIComponent(lk.main || "") + "&text=" + encodeURIComponent(tx("share_text"));
    var h = "";
    h += '<div class="pp-head"><div><span class="eyebrow">' + esc(tx("title")) + '</span><h2>' + esc(s.name || "") + ' <span class="pp-code">' +
      esc(tx("code")) + " <code>" + esc(s.code) + '</code></span></h2></div><button type="button" class="btn btn-ghost btn-sm" data-pp-logout>' + esc(tx("logout")) + "</button></div>";
    if (!s.on) h += '<div class="callout"><svg aria-hidden="true"><use href="#i-warn"/></svg><p>' + esc(tx("off")) + "</p></div>";
    if (s.on && !s.pay_set) h += '<div class="callout"><svg aria-hidden="true"><use href="#i-warn"/></svg><p>' + esc(tx("pay_warn")) + "</p></div>";

    h += '<div class="pp-card pp-main"><h3>' + esc(tx("main")) + "</h3>" +
      '<div class="pp-big"><code>' + esc(lk.main) + '</code><div class="pp-row"><button type="button" class="btn btn-mint" data-pp-copy="' + esc(lk.main) + '">' +
      esc(tx("copy")) + '</button><a class="btn btn-ghost" target="_blank" rel="noopener" href="' + esc(share) + '">' + esc(tx("share")) + "</a></div></div>" +
      '<p class="muted">' + esc(tx(s.own_bd ? "main_note_bd" : "main_note")) + "</p>" +
      '<details class="pp-more"><summary>' + esc(tx("more")) + "</summary>" +
      linkRow(tx("l_bot"), lk.bot) + linkRow(tx("l_bd"), lk.binodex) + linkRow(tx("l_bx"), lk.bingx) +
      '<p class="muted">' + esc(tx("more_note")) + "</p></details></div>";

    h += '<div class="pp-kpis">' +
      kpi(tx("k_clicks"), num(ck.n), tx("k_clicks_s", { d30: num(ck.d30), d7: num(ck.d7) })) +
      kpi(tx("k_inv"), num(c.inv), conv(c.inv, ck.n)) +
      kpi(tx("k_reg"), num(c.reg), conv(c.reg, c.inv)) +
      kpi(tx("k_fund"), num(c.fund), tx("k_fund_s", { a: num(c.act) }), "mint") + "</div>";

    h += '<div class="pp-card"><h3>' + esc(tx("money")) + '</h3><div class="pp-kpis pp-kpis-3">' +
      kpi(tx("m_earned"), money(t.earned)) + kpi(tx("m_paid"), money(t.paid)) + kpi(tx("m_due"), money(t.due), "", "yellow") + "</div>" +
      '<p class="muted pp-note">' + esc(tx("m_note", { pct: pct })) + "</p>";
    var ms = s.months || [];
    h += "<h4>" + esc(tx("months")) + "</h4>";
    h += ms.length ? '<div class="pp-tw"><table class="pp-t"><thead><tr><th>' + esc(tx("th_m")) + "</th><th>" + esc(tx("th_inc")) + "</th><th>" +
      esc(tx("th_pay", { pct: pct })) + "</th><th>" + esc(tx("th_st")) + "</th></tr></thead><tbody>" +
      ms.map(function (m) {
        return "<tr><td>" + esc(m.m) + "</td><td>" + money(m.income) + "</td><td><b>" + money(m.payout) + "</b></td><td>" + esc(tx(m.paid ? "st_paid" : "st_wait")) + "</td></tr>";
      }).join("") + "</tbody></table></div>" : '<p class="muted">' + esc(tx("no_months")) + "</p>";
    h += "</div>";

    var rd = (s.recent || []).slice().reverse();
    h += '<div class="pp-card"><h3>' + esc(tx("days")) + "</h3>" + (rd.length ? '<div class="pp-tw"><table class="pp-t"><thead><tr><th>' + esc(tx("th_d")) + "</th><th>" +
      esc(tx("th_inv")) + "</th><th>" + esc(tx("th_reg")) + "</th><th>" + esc(tx("th_fund")) + "</th></tr></thead><tbody>" +
      rd.map(function (r) { return "<tr><td>" + esc(r.d) + "</td><td>" + num(r.inv) + "</td><td>" + num(r.reg) + "</td><td>" + num(r.fund) + "</td></tr>"; }).join("") +
      "</tbody></table></div>" : '<p class="muted">' + esc(tx("no_days")) + "</p>") + "</div>";

    if (s.updated) {
      var dt = new Date(s.updated);
      h += '<p class="muted pp-upd">' + esc(tx("updated", { t: dt.toLocaleString(L() === "ru" ? "ru-RU" : "ky-KG", { dateStyle: "short", timeStyle: "short" }) })) + "</p>";
    }
    box.innerHTML = h;
  }

  function loginBtn(cls) {
    var u = window.AT && AT.botUrl ? AT.botUrl("partner") : null;
    return u ? '<a class="btn ' + cls + '" href="' + esc(u) + '" target="_blank" rel="noopener">' + esc(tx("login")) + "</a>"
             : '<span class="btn btn-ghost" aria-disabled="true">' + esc(tx("bot_soon")) + "</span>";
  }

  function load() {
    var tok = getTok();
    if (!tok) return render();
    state.loading = true; state.err = null;
    render();
    fetch("/api/partner?t=" + encodeURIComponent(tok), { cache: "no-store" })
      .then(function (r) { return r.json().catch(function () { return { ok: false, net: true }; }); })
      .then(function (j) {
        state.loading = false;
        if (j && j.ok) { state.data = j; state.err = null; }
        else { state.data = null; state.err = j && (j.error === "config" || j.net) ? "net" : "bad"; }
        render();
      })
      .catch(function () { state.loading = false; state.err = "net"; render(); });
  }

  function bindLogin() {
    document.querySelectorAll("[data-pp-login]").forEach(function (a) {
      var u = window.AT && AT.botUrl ? AT.botUrl("partner") : null;
      if (u) { a.href = u; a.target = "_blank"; a.rel = "noopener"; a.removeAttribute("aria-disabled"); }
      else {
        a.removeAttribute("href");
        a.setAttribute("aria-disabled", "true");
        a.onclick = function (e) { e.preventDefault(); if (window.AT && AT.toast) AT.toast(tx("bot_soon")); };
      }
    });
  }

  function init() {
    takeHash();
    bindLogin();
    document.addEventListener("click", function (e) {
      var b = e.target.closest("[data-pp-copy]");
      if (b) { e.preventDefault(); copy(b.getAttribute("data-pp-copy"), b); return; }
      if (e.target.closest("[data-pp-logout]")) { setTok(""); state = { data: null, err: null, loading: false }; render(); return; }
      if (e.target.closest("[data-pp-retry]")) load();
    });
    window.addEventListener("hashchange", function () { if (/[#&]p=/.test(location.hash)) { takeHash(); load(); } });
    if (window.AT && AT.onLang) AT.onLang(function () { bindLogin(); render(); });
    load();
    if (getTok() && location.hash === "#panel") { var el = document.getElementById("pp"); if (el) setTimeout(function () { el.scrollIntoView(); }, 60); }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function () { setTimeout(init, 0); });
  else setTimeout(init, 0);
})();
