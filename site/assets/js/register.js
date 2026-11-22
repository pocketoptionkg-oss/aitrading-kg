/* «Катталуу» барагы: брокер тандоо (#bingx / #binodex), кадамдарды «Бүттү» деп белгилөө, прогресс.
   Белгилер ушул түзмөктө гана сакталат (localStorage). */
(function () {
  "use strict";
  var KEY_B = "aitrading-reg-broker", KEY_D = "aitrading-reg-done";

  function load(k, def) { try { return JSON.parse(localStorage.getItem(k)) || def; } catch (e) { return def; } }
  function save(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* жеке режим */ } }

  function init() {
    if (!window.AT) return;
    var done = load(KEY_D, {});
    var picks = document.querySelectorAll("[data-broker]");

    function progress() {
      document.querySelectorAll("[data-box]").forEach(function (box) {
        var steps = box.querySelectorAll("[data-step]"), n = 0;
        steps.forEach(function (li) {
          var on = !!done[li.getAttribute("data-step")];
          if (on) n++;
          li.classList.toggle("done", on);
          var b = li.querySelector("[data-done]");
          if (b) b.setAttribute("aria-pressed", String(on));
        });
        box.querySelector("[data-prog-txt]").textContent = AT.t("rg.prog").replace("{n}", n).replace("{m}", steps.length);
        box.querySelector("[data-prog-bar]").style.width = (steps.length ? n / steps.length * 100 : 0) + "%";
      });
    }

    function pick(b, scroll) {
      if (b !== "bingx" && b !== "binodex") return;
      picks.forEach(function (p) { p.setAttribute("aria-pressed", String(p.getAttribute("data-broker") === b)); });
      document.querySelectorAll("[data-box]").forEach(function (box) { box.hidden = box.getAttribute("data-box") !== b; });
      try { localStorage.setItem(KEY_B, b); } catch (e) { /* */ }
      if (scroll) {
        var box = document.querySelector('[data-box="' + b + '"]');
        if (box) box.scrollIntoView({ behavior: "smooth", block: "start" });
        history.replaceState(null, "", "#" + b);
      }
      AT.track("register_pick", { broker: b });
    }

    picks.forEach(function (p) { p.addEventListener("click", function () { pick(p.getAttribute("data-broker"), true); }); });
    document.addEventListener("click", function (e) {
      var b = e.target.closest("[data-done]");
      if (!b) return;
      var id = b.closest("[data-step]").getAttribute("data-step");
      done[id] = !done[id];
      if (!done[id]) delete done[id];
      save(KEY_D, done);
      progress();
    });

    var h = (location.hash || "").replace("#", "");
    var saved = null;
    try { saved = localStorage.getItem(KEY_B); } catch (e) { /* */ }
    pick(h === "bingx" || h === "binodex" ? h : saved, false);
    progress();
    AT.onLang(progress);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
