/* ИИ-паук: процедуралык жөргөмүш (8 бут, чыныгы басуу) + «жиптер» жана түйүндөр.
   Canvas компоненттин үстүндө турат (pointer-events: none). Өз дизайн — AITRADING.KG стили. */
(function () {
  "use strict";

  var TAU = Math.PI * 2;
  var COLORS = { mint: "92,232,170", yellow: "255,204,21", blue: "110,160,255", pink: "255,92,170", red: "255,107,107", white: "235,242,250" };

  function lerp(a, b, t) { return a + (b - a) * t; }
  function dist(a, b) { return Math.hypot(a.x - b.x, a.y - b.y); }

  function Spider(host, opts) {
    opts = opts || {};
    var self = this;
    this.host = host;
    this.s = opts.scale || 1;
    this.cv = document.createElement("canvas");
    this.cv.className = "aia-fx";
    host.appendChild(this.cv);
    this.ctx = this.cv.getContext("2d");
    this.dpr = Math.min(2, window.devicePixelRatio || 1);
    this.w = 0; this.h = 0;
    this.pos = { x: 60, y: -60 };
    this.target = { x: 60, y: -60 };
    this.dir = Math.PI / 2;
    this.speed = 430;
    this.talking = false;
    this.threads = [];
    this.anchor = null;          // түшүү жиби (жогорудан)
    this.onFrame = null;
    this.waiters = [];
    var L = 22 * this.s;
    this.L1 = L; this.L2 = L * 1.15;
    var angs = [40, 75, 110, 145];
    this.legs = [];
    [-1, 1].forEach(function (side) {
      angs.forEach(function (a, i) {
        self.legs.push({ a: side * a * Math.PI / 180, side: side, group: (i + (side > 0 ? 1 : 0)) % 2, foot: { x: self.pos.x, y: self.pos.y }, from: null, to: null, t: 1 });
      });
    });
    this.resize();
    if ("ResizeObserver" in window) new ResizeObserver(function () { self.resize(); }).observe(host);
    this.last = performance.now();
    this.visible = true;
    if ("IntersectionObserver" in window) new IntersectionObserver(function (e) { self.visible = e[0].isIntersecting; }).observe(host);
    this.lastFrame = 0;
    requestAnimationFrame(function f(now) { self.lastFrame = performance.now(); self.frame(now); requestAnimationFrame(f); });
    // запас: rAF токтоп калса (фондогу вкладка, кадрлар сейрек) — логика баары бир алга жылат
    setInterval(function () { if (performance.now() - self.lastFrame > 120) self.frame(performance.now()); }, 60);
  }

  Spider.prototype.resize = function () {
    var w = this.host.clientWidth, h = this.host.clientHeight;
    if (w === this.w && h === this.h) return;
    this.w = w; this.h = h;
    this.cv.width = Math.round(w * this.dpr);
    this.cv.height = Math.round(h * this.dpr);
    this.cv.style.width = w + "px";
    this.cv.style.height = h + "px";
  };

  Spider.prototype.ideal = function (leg) {
    var a = this.dir + leg.a, r = (this.L1 + this.L2) * 0.78;
    return { x: this.pos.x + Math.cos(a) * r, y: this.pos.y + Math.sin(a) * r };
  };

  /* Жылуу: максаттуу чекитке жеткенде Promise чечилет */
  Spider.prototype.moveTo = function (x, y, speedMul) {
    var self = this;
    x = Math.max(16, Math.min(this.w - 16, x));
    y = Math.max(16, Math.min(this.h - 16, y));
    this.target = { x: x, y: y };
    this.curSpeed = this.speed * (speedMul || 1);
    return new Promise(function (res) { self.waiters.push(res); });
  };
  Spider.prototype.place = function (x, y) {
    var self = this;
    this.pos = { x: x, y: y }; this.target = { x: x, y: y };
    this.legs.forEach(function (l) { l.foot = self.ideal(l); l.t = 1; });
  };
  Spider.prototype.dropTo = function (x, y) {
    this.place(x, -30);
    this.anchor = { x: x, y: 0 };
    var self = this;
    return this.moveTo(x, y, 0.8).then(function () { setTimeout(function () { self.anchor = null; }, 500); });
  };

  /* Жиптер */
  Spider.prototype.thread = function (x, y, opt) {
    opt = opt || {};
    this.threads.push({ follow: opt.from ? null : true, ax: opt.from ? opt.from.x : null, ay: opt.from ? opt.from.y : null, bx: x, by: y,
      col: COLORS[opt.color || "white"], label: opt.label || "", t0: performance.now(), life: opt.life || 2600, grow: 260 });
  };
  Spider.prototype.burst = function (n, rad, color) {
    for (var i = 0; i < n; i++) {
      var a = Math.random() * TAU, r = rad * (0.45 + Math.random() * 0.55);
      this.thread(this.pos.x + Math.cos(a) * r, this.pos.y + Math.sin(a) * r, { color: color || (i % 3 ? "mint" : "yellow"), life: 1400 + Math.random() * 600 });
    }
  };
  Spider.prototype.clear = function () { this.threads = []; };

  /* ---------- Кадр ---------- */
  Spider.prototype.frame = function (now) {
    var dt = Math.max(0, Math.min(0.05, (now - this.last) / 1000));
    this.last = Math.max(this.last, now);
    if (!this.visible) return;
    this.update(dt, now);
    this.draw(now);
    if (this.onFrame) this.onFrame(this.pos.x, this.pos.y);
  };

  Spider.prototype.update = function (dt, now) {
    var self = this;
    var dx = this.target.x - this.pos.x, dy = this.target.y - this.pos.y, d = Math.hypot(dx, dy);
    var moving = d > 1.5;
    if (moving) {
      var sp = Math.min(this.curSpeed || this.speed, d * 7 + 40);
      var k = Math.min(1, sp * dt / d);
      this.pos.x += dx * k; this.pos.y += dy * k;
      var want = Math.atan2(dy, dx), da = ((want - this.dir + Math.PI * 3) % TAU) - Math.PI;
      this.dir += da * Math.min(1, dt * 10);
    } else if (this.waiters.length) {
      var w = this.waiters; this.waiters = [];
      w.forEach(function (r) { r(); });
    }
    if (!moving) this.dir += Math.sin(now / 900) * 0.002;     // тынч дем алуу
    // Бут басуу: эки топ алмак-салмак
    var stepping = [0, 0], reach = this.L1 + this.L2;
    var stepDur = moving ? Math.max(0.055, Math.min(0.11, 0.11 * 300 / ((this.curSpeed || this.speed)))) : 0.11;
    this.legs.forEach(function (l) { if (l.t < 1) stepping[l.group]++; });
    this.legs.forEach(function (l) {
      if (l.t < 1) {
        l.t = Math.min(1, l.t + dt / stepDur);
        var e = l.t * l.t * (3 - 2 * l.t);
        l.foot = { x: lerp(l.from.x, l.to.x, e), y: lerp(l.from.y, l.to.y, e) };
        l.lift = Math.sin(l.t * Math.PI);
        return;
      }
      var ideal = self.ideal(l);
      var far = dist(l.foot, ideal);
      if (far > reach * 1.6 || (far > self.L1 * 0.85 && !stepping[1 - l.group])) {
        l.from = { x: l.foot.x, y: l.foot.y };
        l.to = { x: ideal.x + dx * 0.08, y: ideal.y + dy * 0.08 };
        l.t = 0;
        stepping[l.group]++;
      }
    });
  };

  Spider.prototype.draw = function (now) {
    var c = this.ctx, s = this.s, self = this;
    c.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    c.clearRect(0, 0, this.w, this.h);

    // жиптер
    this.threads = this.threads.filter(function (t) { return now - t.t0 < t.life; });
    this.threads.forEach(function (t) {
      var age = now - t.t0, g = Math.min(1, age / t.grow), fade = 1 - Math.max(0, (age - t.life * 0.65) / (t.life * 0.35));
      var ax = t.follow ? self.pos.x : t.ax, ay = t.follow ? self.pos.y : t.ay;
      var ex = lerp(ax, t.bx, g), ey = lerp(ay, t.by, g);
      c.strokeStyle = "rgba(" + t.col + "," + (0.75 * fade).toFixed(3) + ")";
      c.lineWidth = 1.1;
      c.beginPath(); c.moveTo(ax, ay); c.lineTo(ex, ey); c.stroke();
      if (g >= 1) {
        c.fillStyle = "rgba(" + t.col + "," + fade.toFixed(3) + ")";
        c.beginPath(); c.arc(t.bx, t.by, 2.6, 0, TAU); c.fill();
        c.strokeStyle = "rgba(" + t.col + "," + (0.5 * fade).toFixed(3) + ")";
        c.beginPath(); c.arc(t.bx, t.by, 5 + 3 * Math.sin(age / 120), 0, TAU); c.stroke();
        if (t.label) {
          c.font = "700 10px Inter, Segoe UI, sans-serif";
          var tw = c.measureText(t.label).width, lx = Math.min(self.w - tw - 10, t.bx + 8), ly = t.by - 9;
          c.fillStyle = "rgba(7,11,18," + (0.85 * fade).toFixed(3) + ")";
          c.fillRect(lx - 4, ly - 10, tw + 8, 14);
          c.fillStyle = "rgba(" + t.col + "," + fade.toFixed(3) + ")";
          c.fillText(t.label, lx, ly + 1);
        }
      }
    });

    // түшүү жиби
    if (this.anchor) {
      c.strokeStyle = "rgba(235,242,250,0.55)"; c.lineWidth = 1;
      c.beginPath(); c.moveTo(this.anchor.x, 0); c.lineTo(this.pos.x, this.pos.y); c.stroke();
    }

    // буттар (эки муун, «тизе» сыртка)
    this.legs.forEach(function (l) {
      var ha = self.dir + l.a, hip = { x: self.pos.x + Math.cos(ha) * 6 * s, y: self.pos.y + Math.sin(ha) * 6 * s };
      var reach = self.L1 + self.L2, f = l.foot, d0 = Math.max(1, dist(hip, f));
      if (d0 > reach * 1.15) f = { x: hip.x + (f.x - hip.x) / d0 * reach * 1.15, y: hip.y + (f.y - hip.y) / d0 * reach * 1.15 };
      var d = Math.max(1, dist(hip, f)), mx = (hip.x + f.x) / 2, my = (hip.y + f.y) / 2;
      var h = Math.sqrt(Math.max(0, (reach / 2) * (reach / 2) - (d / 2) * (d / 2))) * 0.9 + (l.lift || 0) * 6;
      var nx = -(f.y - hip.y) / d * l.side, ny = (f.x - hip.x) / d * l.side;
      var knee = { x: mx + nx * h, y: my + ny * h };
      c.strokeStyle = "rgba(92,232,170,0.95)"; c.lineWidth = 1.8 * s; c.lineCap = "round";
      c.beginPath(); c.moveTo(hip.x, hip.y); c.lineTo(knee.x, knee.y); c.lineTo(f.x, f.y); c.stroke();
      c.fillStyle = "#ffcc15";
      c.beginPath(); c.arc(knee.x, knee.y, 1.6 * s, 0, TAU); c.fill();
    });

    // дене
    var pulse = this.talking ? 1 + 0.18 * Math.sin(now / 70) : 1 + 0.05 * Math.sin(now / 400);
    var R = 9 * s * pulse;
    var gl = c.createRadialGradient(this.pos.x, this.pos.y, 0, this.pos.x, this.pos.y, R * 3.2);
    gl.addColorStop(0, "rgba(92,232,170,0.55)"); gl.addColorStop(1, "rgba(92,232,170,0)");
    c.fillStyle = gl; c.beginPath(); c.arc(this.pos.x, this.pos.y, R * 3.2, 0, TAU); c.fill();
    var bx = this.pos.x - Math.cos(this.dir) * R * 0.9, by = this.pos.y - Math.sin(this.dir) * R * 0.9;
    c.fillStyle = "#1b8f63"; c.beginPath(); c.arc(bx, by, R * 0.95, 0, TAU); c.fill();          // курсак
    var bg = c.createRadialGradient(this.pos.x - 2, this.pos.y - 2, 1, this.pos.x, this.pos.y, R);
    bg.addColorStop(0, "#b8ffe1"); bg.addColorStop(1, "#2fbf86");
    c.fillStyle = bg; c.beginPath(); c.arc(this.pos.x, this.pos.y, R * 0.8, 0, TAU); c.fill();   // баш
    c.strokeStyle = "rgba(255,204,21,0.9)"; c.lineWidth = 1.4;
    c.beginPath(); c.arc(this.pos.x, this.pos.y, R * 0.8 + 2.5, now / 300, now / 300 + 4.2); c.stroke();
    var ex = Math.cos(this.dir), ey = Math.sin(this.dir), px = -ey, py = ex;
    c.fillStyle = "#0a1220";
    [-1, 1].forEach(function (k) { c.beginPath(); c.arc(self.pos.x + ex * R * 0.35 + px * k * R * 0.28, self.pos.y + ey * R * 0.35 + py * k * R * 0.28, 1.7 * s, 0, TAU); c.fill(); });
  };

  window.AISpider = Spider;
})();
