/* «Коопсуздук» бети: 12 суроолуу текшерүү (ушул түзмөктө сакталат) жана муздак капчык өндүрүүчүлөрү.
   Өндүрүүчүнүн баскычы: config.js → WALLET_REF_URLS[ачкыч] коюлса — партнёрдук шилтеме (белгиленет), болбосо расмий сайт. */
(function () {
  "use strict";
  if (!window.AT) return;
  var T = AT.t;
  var KEY = "aitrading-sec-check";

  var WALLETS = [
    { id: "tangem", name: "Tangem", type: "sc.wt1_h", url: "https://tangem.com/" },
    { id: "ledger", name: "Ledger", type: "sc.wt2_h", url: "https://www.ledger.com/" },
    { id: "trezor", name: "Trezor", type: "sc.wt2_h", url: "https://trezor.io/" },
    { id: "keystone", name: "Keystone", type: "sc.wt3_h", url: "https://keyst.one/" }
  ];

  function load() { try { return JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { return {}; } }
  function save(v) { try { localStorage.setItem(KEY, JSON.stringify(v)); } catch (e) { /* купуя режим */ } }

  /* ---------- Текшерүү ---------- */
  function initCheck() {
    var box = document.querySelector(".sc-check");
    if (!box) return;
    var boxes = box.querySelectorAll("[data-chk]"), state = load();
    var ring = box.querySelector("[data-score-ring]"), num = box.querySelector("[data-score-num]"), lvl = box.querySelector("[data-score-level]");
    var C = 2 * Math.PI * 19;
    function render() {
      var n = 0, tot = boxes.length;
      boxes.forEach(function (b) { if (b.checked) n++; b.closest("label").classList.toggle("on", b.checked); });
      num.textContent = n + "/" + tot;
      ring.style.strokeDasharray = C;
      ring.style.strokeDashoffset = C * (1 - n / tot);
      var k = n >= 10 ? "good" : n >= 6 ? "mid" : "bad";
      box.setAttribute("data-level", k);
      lvl.textContent = T("sc.lvl_" + k);
    }
    boxes.forEach(function (b) {
      b.checked = !!state[b.getAttribute("data-chk")];
      b.addEventListener("change", function () {
        state[b.getAttribute("data-chk")] = b.checked ? 1 : 0;
        save(state);
        render();
        AT.track("sec_check", { item: b.getAttribute("data-chk"), on: b.checked });
      });
    });
    box.querySelector("[data-chk-reset]").addEventListener("click", function () {
      state = {};
      save(state);
      boxes.forEach(function (b) { b.checked = false; });
      render();
    });
    AT.onLang(render);
    render();
  }

  /* ---------- Муздак капчыктар ---------- */
  function initWallets() {
    var host = document.querySelector("[data-wallets]");
    if (!host) return;
    var refs = (window.AITRADING_CONFIG || {}).WALLET_REF_URLS || {};
    function render() {
      host.innerHTML = WALLETS.map(function (w) {
        var ref = String(refs[w.id] || "").trim(), partner = /^https:\/\/\S+$/i.test(ref);
        return '<a class="sc-brand" href="' + (partner ? ref : w.url) + '" target="_blank" rel="' + (partner ? "sponsored noopener" : "noopener") + '" data-wallet="' + w.id + '">' +
          "<b>" + w.name + "</b><span>" + T(w.type) + "</span>" +
          '<em>' + T(partner ? "sc.buy_partner" : "sc.buy_official") + ' ↗</em></a>';
      }).join("");
    }
    host.addEventListener("click", function (e) {
      var a = e.target.closest("[data-wallet]");
      if (a) AT.track("wallet_click", { brand: a.getAttribute("data-wallet") });
    });
    AT.onLang(render);
    render();
  }

  function init() { initCheck(); initWallets(); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
