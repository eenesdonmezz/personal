/* Arka plan: süzülen mavi ve sarı noktalar.
   Mavi = sosyal hizmet, sarı = En2Studios. Birbirine yakın noktalar ince
   çizgilerle bağlanır; fare (ya da parmak) yaklaşınca noktalar ona bağlanır.
   "Hareketi azalt" ayarı açıksa noktalar durağan çizilir. */
(function () {
  var canvas = document.querySelector(".bg-field");
  if (!canvas || !canvas.getContext) return;
  var ctx = canvas.getContext("2d");
  var root = document.documentElement;
  var still = window.matchMedia("(prefers-reduced-motion: reduce)");

  var W = 0, H = 0, dpr = 1, dots = [], colors = {}, running = false, raf = 0;
  var pointer = { x: -9999, y: -9999 };
  var LINK = 140;          // bu mesafeden yakın noktalar bağlanır (px)
  var POINTER_LINK = 190;  // fareye bağlanma mesafesi

  function readColors() {
    var cs = getComputedStyle(root);
    colors.blue = cs.getPropertyValue("--blue").trim() || "#2f4bdb";
    colors.yellow = cs.getPropertyValue("--yellow").trim() || "#f2b705";
    colors.line = cs.getPropertyValue("--muted").trim() || "#56627a";
  }

  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = window.innerWidth;
    H = window.innerHeight;
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    var target = Math.min(70, Math.round((W * H) / 19000));
    while (dots.length < target) dots.push(makeDot());
    dots.length = target;
  }

  function makeDot() {
    var speed = 0.12 + Math.random() * 0.25;
    var angle = Math.random() * Math.PI * 2;
    return {
      x: Math.random() * W,
      y: Math.random() * H,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed,
      r: 1.6 + Math.random() * 2.6,
      yellow: Math.random() < 0.45,
      phase: Math.random() * Math.PI * 2
    };
  }

  function draw(t) {
    ctx.clearRect(0, 0, W, H);
    var i, j, a, b, dx, dy, d;

    // bağlantı çizgileri
    ctx.lineWidth = 1;
    ctx.strokeStyle = colors.line;
    for (i = 0; i < dots.length; i++) {
      a = dots[i];
      for (j = i + 1; j < dots.length; j++) {
        b = dots[j];
        dx = a.x - b.x; dy = a.y - b.y;
        d = dx * dx + dy * dy;
        if (d < LINK * LINK) {
          ctx.globalAlpha = (1 - Math.sqrt(d) / LINK) * 0.22;
          ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
        }
      }
      dx = a.x - pointer.x; dy = a.y - pointer.y;
      d = Math.sqrt(dx * dx + dy * dy);
      if (d < POINTER_LINK) {
        ctx.globalAlpha = (1 - d / POINTER_LINK) * 0.45;
        ctx.strokeStyle = a.yellow ? colors.yellow : colors.blue;
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(pointer.x, pointer.y); ctx.stroke();
        ctx.strokeStyle = colors.line;
      }
    }

    // noktalar: hafifçe "nefes alır"
    for (i = 0; i < dots.length; i++) {
      a = dots[i];
      var pulse = 1 + Math.sin(t / 1400 + a.phase) * 0.18;
      ctx.globalAlpha = 0.55;
      ctx.fillStyle = a.yellow ? colors.yellow : colors.blue;
      ctx.beginPath(); ctx.arc(a.x, a.y, a.r * pulse, 0, Math.PI * 2); ctx.fill();
    }
    ctx.globalAlpha = 1;
  }

  function step(t) {
    for (var i = 0; i < dots.length; i++) {
      var p = dots[i];
      // fareye çok yaklaşan nokta biraz uzaklaşır
      var dx = p.x - pointer.x, dy = p.y - pointer.y, d2 = dx * dx + dy * dy;
      if (d2 < 6400 && d2 > 0.01) {
        var push = (6400 - d2) / 6400 * 0.6, d = Math.sqrt(d2);
        p.x += dx / d * push; p.y += dy / d * push;
      }
      p.x += p.vx; p.y += p.vy;
      if (p.x < -10) p.x = W + 10; else if (p.x > W + 10) p.x = -10;
      if (p.y < -10) p.y = H + 10; else if (p.y > H + 10) p.y = -10;
    }
    draw(t);
    raf = requestAnimationFrame(step);
  }

  function start() {
    cancelAnimationFrame(raf);
    running = !still.matches && !document.hidden;
    if (running) raf = requestAnimationFrame(step);
    else draw(0);
  }

  window.addEventListener("resize", function () { resize(); if (!running) draw(0); });
  window.addEventListener("pointermove", function (e) { pointer.x = e.clientX; pointer.y = e.clientY; }, { passive: true });
  window.addEventListener("pointerleave", function () { pointer.x = pointer.y = -9999; });
  document.addEventListener("visibilitychange", start);
  if (still.addEventListener) still.addEventListener("change", start);

  // tema değişince renkleri yeniden oku
  new MutationObserver(function () { readColors(); if (!running) draw(0); })
    .observe(root, { attributes: true, attributeFilter: ["data-theme"] });
  var darkMq = window.matchMedia("(prefers-color-scheme: dark)");
  if (darkMq.addEventListener) darkMq.addEventListener("change", function () { readColors(); });

  readColors();
  resize();
  start();
})();
