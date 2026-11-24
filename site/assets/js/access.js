/* AITRADING.KG — 1) WhatsApp номери брокерде катталуудан МУРУН (почта/сырсөз жок);
                  2) сигналдарга доступ: 2 акысыз сигнал → андан ары катталуу + толуктоо + бот.
   Сервер: /api/lead (KV, бот алып админге жиберет), /api/access (боттун колу менен доступ).
   Сайт статикалык, ошондуктан лимит браузерде — бул ыңгайлуулук үчүн, толук коргоо эмес. */
(function () {
  "use strict";
  if (window.ATGate || !window.AT) return;

  var LEAD = "aitrading-lead", FREE = "aitrading-free", ACC = "aitrading-acc", FREE_N = 2;

  var TXT = {
    ky: {
      l_title: "Катталуудан мурун — WhatsApp номериңиз",
      l_sub: "Номериңизди калтырыңыз: команда сизге катталуу жана толуктоо боюнча WhatsApp'тан жардам берет. Почта жана сырсөз керек эмес.",
      l_wa: "WhatsApp номери", l_name: "Атыңыз (милдеттүү эмес)",
      l_consent: "Номеримди AITRADING.KG командасына байланыш үчүн берүүгө макулмун. Мен 18 жаштан өйдөмүн.",
      l_go: "Улантуу →", l_wait: "Жөнөтүлүүдө…",
      l_e_phone: "Номерди толук жазыңыз, мисалы +996 700 123 456.",
      l_e_consent: "Улантуу үчүн макулдукту белгилеңиз.",
      l_e_limit: "Өтө көп аракет. Бир аздан кийин кайталаңыз.",
      l_e_server: "Жөнөтүлгөн жок. Интернетти текшерип, кайра басыңыз.",
      l_ok: "✓ Рахмат! Эми брокерде катталыңыз:",
      l_ok_next: "Катталып, эсепти толуктагандан кийин ID'ңизди ботко жибериңиз — сигналдар ачылат.",
      l_done_inline: "✓ WhatsApp номериңиз алынды. Төмөндө брокерди тандап катталыңыз.",
      bot: "Ботко кирүү",
      g_free: "🎁 Акысыз сигнал {n}/{m}",
      g_title: "🔒 Акысыз сигналдар бүттү ({m}/{m})",
      g_steps: ["Биздин шилтеме менен брокерде катталыңыз", "Эсепти толуктаңыз", "ID'ни Telegram-ботко жибериңиз — текшерилгенден кийин сигналдар ушул жерде жана Telegram'да ачылат"],
      g_note: "Сигналдар толукталган эсеби бар команда мүчөлөрүнө гана ачык. Соода тобокелдиктүү, 18+.",
      g_have: "Доступ ботто ачылдыбы? Боттогу «🌐 Сайтта ачуу» баскычын басыңыз.",
      g_best: "🔒 Багыт жабык",
      g_open: "✓ Сайттагы сигналдарга доступ ачылды"
    },
    ru: {
      l_title: "Перед регистрацией — ваш номер WhatsApp",
      l_sub: "Оставьте номер: команда поможет с регистрацией и пополнением в WhatsApp. Почта и пароль не нужны.",
      l_wa: "Номер WhatsApp", l_name: "Имя (необязательно)",
      l_consent: "Согласен(на) передать номер команде AITRADING.KG для связи. Мне есть 18 лет.",
      l_go: "Продолжить →", l_wait: "Отправка…",
      l_e_phone: "Введите номер полностью, например +996 700 123 456.",
      l_e_consent: "Чтобы продолжить, отметьте согласие.",
      l_e_limit: "Слишком много попыток. Повторите чуть позже.",
      l_e_server: "Не отправилось. Проверьте интернет и нажмите ещё раз.",
      l_ok: "✓ Спасибо! Теперь зарегистрируйтесь у брокера:",
      l_ok_next: "После регистрации и пополнения отправьте ID в бот — сигналы откроются.",
      l_done_inline: "✓ Номер WhatsApp получен. Выберите брокера ниже и зарегистрируйтесь.",
      bot: "Открыть бота",
      g_free: "🎁 Бесплатный сигнал {n}/{m}",
      g_title: "🔒 Бесплатные сигналы закончились ({m}/{m})",
      g_steps: ["Зарегистрируйтесь у брокера по нашей ссылке", "Пополните счёт", "Отправьте ID в Telegram-бот — после проверки сигналы откроются здесь и в Telegram"],
      g_note: "Сигналы открыты только участникам команды с пополненным счётом. Торговля рискованна, 18+.",
      g_have: "Доступ в боте уже открыт? Нажмите в боте кнопку «🌐 Открыть на сайте».",
      g_best: "🔒 Направление скрыто",
      g_open: "✓ Доступ к сигналам на сайте открыт"
    }
  };
  function L() { return AT.lang() === "ru" ? "ru" : "ky"; }
  function tx(k) { var d = TXT[L()]; return d[k] !== undefined ? d[k] : TXT.ky[k]; }
  function fmt(s, o) { return String(s).replace(/\{(\w+)\}/g, function (_, k) { return o[k] !== undefined ? o[k] : ""; }); }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function get(k, d) { try { var v = JSON.parse(localStorage.getItem(k)); return v == null ? d : v; } catch (e) { return d; } }
  function put(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* жеке режим */ } }

  (function css() {
    var l = document.createElement("link");
    l.rel = "stylesheet"; l.href = "assets/css/access.css";
    document.head.appendChild(l);
  })();

  /* =================== 1. WhatsApp заявка =================== */
  function lead() { return get(LEAD, null); }
  function brokerName(b) { return b === "binodex" ? "BinoDex" : "BingX"; }

  function formHtml(broker) {
    return '<form class="ld-form" novalidate data-broker="' + esc(broker || "") + '">' +
      '<label class="ld-f"><span>' + esc(tx("l_wa")) + ' *</span><input type="tel" name="wa" inputmode="tel" autocomplete="tel" placeholder="+996 700 123 456" required></label>' +
      '<label class="ld-f"><span>' + esc(tx("l_name")) + '</span><input type="text" name="name" autocomplete="given-name" maxlength="60"></label>' +
      '<label class="ld-c"><input type="checkbox" name="consent"><span>' + esc(tx("l_consent")) + "</span></label>" +
      '<p class="ld-err" role="alert" hidden></p>' +
      '<button type="submit" class="btn btn-mint">' + esc(tx("l_go")) + "</button></form>";
  }

  function okHtml(broker, id) {
    var bs = broker ? [broker] : ["bingx", "binodex"];
    return '<p class="ld-ok">' + esc(tx("l_ok")) + "</p>" +
      '<div class="actions ld-act">' + bs.map(function (b) {
        return '<a class="btn ' + (b === "binodex" ? "btn-mint" : "btn-blue") + '" data-ref="' + b + '" href="#">' + esc(AT.t("cta.reg_" + b)) + "</a>";
      }).join("") + "</div>" +
      '<p class="ld-next">' + esc(tx("l_ok_next")) + "</p>" +
      (AT.botUrl("ld_" + id) ? '<a class="btn btn-ghost btn-sm" data-bot="ld_' + esc(id) + '" href="#">' + esc(tx("bot")) + " →</a>" : "");
  }

  function bindForm(root, done) {
    var f = root.querySelector(".ld-form"), err = f.querySelector(".ld-err"), btn = f.querySelector("button[type=submit]");
    function show(k) { err.textContent = tx(k); err.hidden = false; }
    f.addEventListener("submit", function (e) {
      e.preventDefault();
      err.hidden = true;
      var wa = f.wa.value.trim(), digits = wa.replace(/\D/g, "");
      if (digits.length < 9 || digits.length > 15) { show("l_e_phone"); f.wa.focus(); return; }
      if (!f.consent.checked) { show("l_e_consent"); return; }
      btn.disabled = true; btn.textContent = tx("l_wait");
      fetch("api/lead", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ wa: wa, name: f.name.value, broker: f.getAttribute("data-broker"), lang: L(), page: (document.body && document.body.getAttribute("data-page")) || "", consent: true })
      }).then(function (r) { return r.json().catch(function () { return { error: "server" }; }); }).then(function (j) {
        if (j && j.ok) {
          put(LEAD, { id: j.id, t: Date.now() });
          AT.track("lead", { broker: f.getAttribute("data-broker") || "", page: (document.body && document.body.getAttribute("data-page")) || "" });
          done(j.id);
          return;
        }
        show(j && j.error === "phone" ? "l_e_phone" : j && j.error === "limit" ? "l_e_limit" : "l_e_server");
        btn.disabled = false; btn.textContent = tx("l_go");
      }).catch(function () {
        show("l_e_server");
        btn.disabled = false; btn.textContent = tx("l_go");
      });
    });
  }

  var modal = null;
  function openLead(broker) {
    if (!modal) {
      modal = document.createElement("div");
      modal.className = "ld-modal";
      modal.setAttribute("role", "dialog");
      modal.setAttribute("aria-modal", "true");
      modal.innerHTML = '<div class="ld-back" data-ld-x></div><div class="ld-win"><button type="button" class="ld-x" data-ld-x aria-label="×">×</button><div class="ld-body"></div></div>';
      document.body.appendChild(modal);
      modal.addEventListener("click", function (e) { if (e.target.closest("[data-ld-x]")) closeLead(); });
      document.addEventListener("keydown", function (e) { if (e.key === "Escape" && modal && !modal.hidden) closeLead(); });
    }
    var body = modal.querySelector(".ld-body");
    body.innerHTML = '<h2 class="ld-h">' + esc(tx("l_title")) + '</h2><p class="ld-sub">' + esc(tx("l_sub")) + "</p>" + formHtml(broker);
    bindForm(body, function (id) { body.innerHTML = okHtml(broker, id); AT.applyRefLinks(); });
    modal.hidden = false;
    document.documentElement.classList.add("no-scroll");
    AT.track("lead_open", { broker: broker || "" });
    setTimeout(function () { var i = body.querySelector("input[name=wa]"); if (i) i.focus(); }, 50);
  }
  function closeLead() {
    if (!modal) return;
    modal.hidden = true;
    document.documentElement.classList.remove("no-scroll");
  }

  // Брокердин катталуу шилтемесин басканда — номер жок болсо, алгач форма
  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest("a[data-ref]");
    if (!a || lead()) return;
    e.preventDefault();
    e.stopPropagation();
    openLead(a.getAttribute("data-ref"));
  }, true);

  // register.html: беттин ичиндеги форма
  function inline() {
    document.querySelectorAll("[data-lead-inline]").forEach(function (box) {
      if (lead()) { box.innerHTML = '<p class="ld-done">' + esc(tx("l_done_inline")) + "</p>"; return; }
      box.innerHTML = '<div class="ld-card"><h2 class="ld-h">' + esc(tx("l_title")) + '</h2><p class="ld-sub">' + esc(tx("l_sub")) + "</p>" + formHtml("") + "</div>";
      bindForm(box, function (id) { box.innerHTML = '<div class="ld-card">' + okHtml("", id) + "</div>"; AT.applyRefLinks(); });
    });
  }

  /* =================== 2. Сигналдарга доступ =================== */
  var listeners = [];
  function acc() { var a = get(ACC, null); return a && a.exp > Date.now() ? a : null; }
  function used() { var u = get(FREE, []); return Array.isArray(u) ? u : []; }
  function state() { return acc() ? "open" : used().length < FREE_N ? "free" : "locked"; }
  function changed() {
    listeners.forEach(function (fn) { try { fn(state()); } catch (e) { /* */ } });
    try { window.dispatchEvent(new Event("atgate")); } catch (e) { /* */ }
  }

  /* Багыты бар жаңы сигнал көрсөтүлөөрдө: true — көрсөтүүгө болот (акысыз болсо — эсептелет) */
  function consume(id) {
    if (acc()) return true;
    var u = used();
    if (u.indexOf(id) >= 0) return true;
    if (u.length >= FREE_N) return false;
    u.push(id);
    put(FREE, u);
    AT.track("free_signal", { n: u.length });
    if (u.length >= FREE_N) setTimeout(changed, 0);
    return true;
  }
  function freeChip(id) {
    if (acc()) return "";
    var k = used().indexOf(id);
    return k < 0 ? "" : '<span class="gt-chip">' + esc(fmt(tx("g_free"), { n: k + 1, m: FREE_N })) + "</span>";
  }
  function lockHtml(fx) {
    var bs = fx === true ? ["binodex"] : fx === false ? ["bingx"] : ["bingx", "binodex"];
    return '<div class="gt-lock"><h3>' + esc(fmt(tx("g_title"), { m: FREE_N })) + "</h3><ol>" +
      tx("g_steps").map(function (s) { return "<li>" + esc(s) + "</li>"; }).join("") + "</ol>" +
      '<div class="actions gt-act">' + bs.map(function (b) {
        return '<a class="btn ' + (b === "binodex" ? "btn-mint" : "btn-blue") + ' btn-sm" data-ref="' + b + '" href="#">' + esc(AT.t("cta.reg_" + b)) + "</a>";
      }).join("") + (AT.botUrl("paywall") ? '<a class="btn btn-ghost btn-sm" data-bot="paywall" href="#">' + esc(tx("bot")) + " →</a>" : "") + "</div>" +
      '<p class="gt-have">' + esc(tx("g_have")) + '</p><p class="gt-note">' + esc(tx("g_note")) + "</p></div>";
  }

  // Боттон келген шилтеме: …#acc=<token>
  function verify(t, quiet) {
    return fetch("api/access?t=" + encodeURIComponent(t), { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (j && j.ok) {
          put(ACC, { t: t, exp: j.exp, chk: Date.now() });
          if (!quiet) { AT.toast(tx("g_open")); AT.track("site_access", {}); }
          changed();
        } else if (j && j.ok === false && !j.error) {
          try { localStorage.removeItem(ACC); } catch (e) { /* */ }
          changed();
        }
      }).catch(function () { /* тармак жок — кийин кайра текшерилет */ });
  }
  function initAccess() {
    var m = /[#&]acc=([0-9a-z]+\.[0-9a-z]+\.[A-Za-z0-9_-]{22})/.exec(location.hash);
    if (m) {
      try { history.replaceState(null, "", location.pathname + location.search); } catch (e) { /* */ }
      verify(m[1], false);
      return;
    }
    var a = acc();
    if (a && Date.now() - (a.chk || 0) > 86400000) verify(a.t, true);
  }

  window.ATGate = {
    state: state, consume: consume, freeChip: freeChip, lockHtml: lockHtml,
    bestLock: function () { return tx("g_best"); },
    onChange: function (fn) { listeners.push(fn); },
    openLead: openLead, hasLead: function () { return !!lead(); }
  };

  initAccess();
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", inline); else inline();
  AT.onLang(function () { inline(); });
})();
