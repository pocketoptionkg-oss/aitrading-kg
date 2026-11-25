/* ИИ-боттун үнү.
   1-артыкчылык: assets/audio/<lang>/<key>.mp3 (мисалы, ElevenLabs'те автордун үнү менен жазылган) — тизмеси assets/audio/voice.json.
   2-артыкчылык: браузердин үнү (Web Speech API): ky → kk (казакча, жакын айтылыш) → ru.
   Браузерлер үндү колдонуучу баскычты баскандан кийин гана уруксат кылат — ошондуктан 🔊 баскычы. */
(function () {
  "use strict";
  if (!window.AT) return;
  var KEY = "aitrading-voice";
  var synth = window.speechSynthesis || null;
  var voices = [];
  var manifest = { ky: [], ru: [] };
  var audio = null;
  var warned = false;
  var enabled = false;
  try { enabled = localStorage.getItem(KEY) === "1"; } catch (e) { /* */ }
  var unlocked = false;   // колдонуучу баскычты баскандан кийин гана үн чыгат

  function loadVoices() { if (synth) voices = synth.getVoices() || []; }
  if (synth) { loadVoices(); synth.onvoiceschanged = loadVoices; }
  fetch("assets/audio/voice.json", { cache: "no-cache" }).then(function (r) { return r.ok ? r.json() : null; }).then(function (j) { if (j) manifest = j; }).catch(function () {});

  /* «Технологиялык» үн: эркек/диктор үндөрү жана Neural/Google биринчи */
  var PREFER = /(dmitry|pavel|yuri|maxim|daulet|neural|natural|google)/i;
  function pick(prefix) {
    var list = voices.filter(function (v) { return v.lang && v.lang.toLowerCase().indexOf(prefix) === 0; });
    if (!list.length) return null;
    list.sort(function (a, b) { return (PREFER.test(b.name) ? 1 : 0) - (PREFER.test(a.name) ? 1 : 0); });
    return list[0];
  }

  /* Кайсы тилде, кайсы үн менен сүйлөйт */
  function plan(lang) {
    if (lang === "ky") {
      var ky = pick("ky") || pick("kk");
      if (ky) return { voice: ky, textLang: "ky" };
      var ru = pick("ru");
      if (ru && !warned) { warned = true; AT.toast(AT.t("aiv.no_ky")); }
      return { voice: ru, textLang: "ru" };
    }
    return { voice: pick("ru"), textLang: "ru" };
  }

  function phrase(key, lang) {
    var d = (window.AITRADING_I18N || {})[lang] || {};
    return d["aiv." + key] || ((window.AITRADING_I18N || {}).ky || {})["aiv." + key] || "";
  }

  function stop() {
    if (synth) synth.cancel();
    if (audio) { audio.pause(); audio = null; }
  }

  /* Автордун үнү (ElevenLabs, functions/api/tts.js). Туташпаса — браузердин үнү. */
  var cloud = false, cloudFails = 0, blobs = {};
  fetch("api/tts", { cache: "no-store" }).then(function (r) { return r.ok ? r.json() : null; })
    .then(function (j) { cloud = !!(j && j.ok); }).catch(function () {});

  function playUrl(url, finish) {
    audio = new Audio(url);
    audio.playbackRate = 1;
    audio.onended = finish;
    audio.onerror = finish;
    sfx("pre");
    audio.play().catch(finish);
  }
  function webSay(text, lang, finish) {
    if (!synth) return finish();
    var p = plan(lang);
    if (!p.voice) return finish();
    var u = new SpeechSynthesisUtterance(text);
    u.voice = p.voice; u.lang = p.voice.lang; u.rate = 1.15; u.pitch = 1;
    u.onend = finish; u.onerror = finish;
    sfx("pre");
    synth.speak(u);
  }
  /* Каалаган текстти окуу (сигнал, ассистенттин жообу). Promise — бүткөндө. */
  function say(text, maxMs, force) {
    text = String(text || "").replace(/[*_#`>]/g, "").replace(/https?:\/\/\S+/g, "").replace(/\s+/g, " ").trim().slice(0, 600);
    if (!text || (!force && !enabled) || !unlocked) return Promise.resolve();
    var lang = AT.lang() === "ru" ? "ru" : "ky";
    stop();
    return new Promise(function (resolve) {
      var done = false;
      var finish = function () { if (!done) { done = true; resolve(); } };
      setTimeout(finish, maxMs || 45000);
      var k = lang + "|" + text;
      if (blobs[k]) return playUrl(blobs[k], finish);
      if (!cloud || cloudFails >= 3) return webSay(text, lang, finish);
      fetch("api/tts", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ text: text, lang: lang }) })
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.blob(); })
        .then(function (b) { if (done) return; blobs[k] = URL.createObjectURL(b); playUrl(blobs[k], finish); })
        .catch(function () { cloudFails++; if (!done) webSay(text, lang, finish); });
    });
  }

  /* Эки стиль (A — сабырдуу, B — шайыр): ар бир фраза аралаш алмашат — A,A,B,A,B,B,A,A,A,B…
     ошондо бир эле сөз улам кайталанбайт. Эсептегич localStorage'да (жок болсо — эс тутумда). */
  var MIX = [0, 0, 1, 0, 1, 1, 0, 0, 0, 1, 1, 0, 1];
  var mixN = {};
  try { mixN = JSON.parse(localStorage.getItem("aitrading-voice-mix") || "{}") || {}; } catch (e) { mixN = {}; }
  function variant(key, lang) {
    if ((manifest[lang] || []).indexOf(key + "_b") < 0) return key;
    var i = mixN[key] || 0;
    mixN[key] = i + 1;
    try { localStorage.setItem("aitrading-voice-mix", JSON.stringify(mixN)); } catch (e) { /* */ }
    return MIX[i % MIX.length] ? key + "_b" : key;
  }

  /* key → Promise (сүйлөп бүткөндө же max мс өткөндө чечилет) */
  function speak(key, maxMs) {
    if (!enabled || !unlocked) return Promise.resolve();
    var lang = AT.lang() === "ru" ? "ru" : "ky";
    maxMs = maxMs || 2600;
    if ((manifest[lang] || []).indexOf(key) < 0 && cloud && cloudFails < 3) return say(phrase(key, lang), maxMs + 1500);
    stop();
    return new Promise(function (resolve) {
      var done = false;
      var finish = function () { if (!done) { done = true; resolve(); } };
      setTimeout(finish, maxMs);
      if ((manifest[lang] || []).indexOf(key) >= 0) {
        audio = new Audio("assets/audio/" + lang + "/" + variant(key, lang) + ".mp3");
        audio.playbackRate = 1.05;
        audio.preservesPitch = true;
        sfx("pre");
        audio.onended = finish;
        audio.onerror = finish;
        audio.play().catch(finish);
        return;
      }
      if (!synth) return finish();
      var p = plan(lang);
      var text = phrase(key, p.textLang);
      if (!text || !p.voice) return finish();
      var u = new SpeechSynthesisUtterance(text);
      u.voice = p.voice;
      u.lang = p.voice.lang;
      u.rate = 1.32;      // тездетилген
      u.pitch = 0.92;     // бир аз төмөн — «машиналык» тон
      sfx("pre");
      u.onend = finish;
      u.onerror = finish;
      synth.speak(u);
    });
  }

  /* ---------- Санарип үндөр (WebAudio, файлсыз) ---------- */
  var ac = null, lastPip = 0;
  function ctx() {
    if (!ac) { var C = window.AudioContext || window.webkitAudioContext; if (!C) return null; ac = new C(); }
    if (ac.state === "suspended") ac.resume();
    return ac;
  }
  function tone(f1, f2, dur, type, vol, delay) {
    var c = ctx(); if (!c) return;
    var t = c.currentTime + (delay || 0), o = c.createOscillator(), g = c.createGain();
    o.type = type || "sine";
    o.frequency.setValueAtTime(f1, t);
    if (f2) o.frequency.exponentialRampToValueAtTime(f2, t + dur);
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(vol || 0.05, t + 0.012);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(g); g.connect(c.destination);
    o.start(t); o.stop(t + dur + 0.02);
  }
  function sfx(name) {
    if (!enabled || !unlocked) return;
    try {
      if (name === "pre") { tone(1400, 2100, 0.06, "square", 0.018); tone(2100, 2100, 0.05, "square", 0.014, 0.07); }
      else if (name === "pip") { var n = performance.now(); if (n - lastPip < 70) return; lastPip = n; tone(2400 + Math.random() * 900, 0, 0.045, "sine", 0.02); }
      else if (name === "blip") tone(880, 1320, 0.09, "triangle", 0.035);
      else if (name === "sweep") tone(300, 2400, 0.45, "sawtooth", 0.012);
      else if (name === "done") { tone(660, 0, 0.12, "triangle", 0.04); tone(880, 0, 0.12, "triangle", 0.04, 0.1); tone(1320, 0, 0.22, "triangle", 0.045, 0.2); }
    } catch (e) { /* үн болбосо сайт иштей берет */ }
  }

  function setEnabled(v) {
    enabled = !!v;
    if (enabled) unlocked = true;
    try { localStorage.setItem(KEY, enabled ? "1" : "0"); } catch (e) { /* */ }
    if (!enabled) stop();
  }

  /* Каалаган баскычты басуу «кулпуну ачат» (браузердин эрежеси) */
  ["pointerdown", "keydown"].forEach(function (ev) {
    document.addEventListener(ev, function () { unlocked = true; }, { capture: true, passive: true });
  });

  window.AIVOICE = {
    speak: speak,
    say: say,
    hasAuthor: function () { return cloud && cloudFails < 3; },
    sfx: sfx,
    stop: stop,
    setEnabled: setEnabled,
    isOn: function () { return enabled; },
    canSpeak: function () { return cloud || !!synth || (manifest.ky || []).length > 0 || (manifest.ru || []).length > 0; }
  };
})();
