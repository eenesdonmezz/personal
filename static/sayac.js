/* Öne çıkan videolar: izlenme sayıları görünür olunca 0'dan sayarak yükselir.
   Ekran okuyucular hep son değeri duyar (gizli metin); hareketli sayı onlardan
   saklanır. "Hareketi azalt" açıksa ya da JavaScript yoksa sayılar olduğu gibi kalır. */
(function () {
  if (!("IntersectionObserver" in window)) return;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  var els = document.querySelectorAll(".video-views strong");
  if (!els.length) return;
  var DURATION = 1600;

  function ease(t) { return 1 - Math.pow(1 - t, 3); }

  function setup(el) {
    var text = el.textContent;
    var m = text.match(/^(\D*)(\d+)(.*)$/);
    if (!m) return null;
    var real = document.createElement("span");
    real.className = "sr-only";
    real.textContent = text;
    var shown = document.createElement("span");
    shown.setAttribute("aria-hidden", "true");
    shown.textContent = m[1] + "0" + m[3];
    el.textContent = "";
    el.appendChild(real);
    el.appendChild(shown);
    return { node: shown, before: m[1], target: parseInt(m[2], 10), after: m[3] };
  }

  function run(c) {
    var start = null;
    function step(t) {
      if (start === null) start = t;
      var p = Math.min((t - start) / DURATION, 1);
      c.node.textContent = c.before + Math.round(c.target * ease(p)) + c.after;
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (!e.isIntersecting) return;
      io.unobserve(e.target);
      run(e.target._sayac);
    });
  }, { threshold: 0.5 });

  Array.prototype.forEach.call(els, function (el) {
    var c = setup(el);
    if (!c) return;
    el._sayac = c;
    io.observe(el);
  });
})();
