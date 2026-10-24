// Small touches on the landing page: magnetic buttons, and the hero mascot's eyes follow the pointer (it hops when the
// pointer reaches an app button). The button shine and press are CSS only (touches.css). Nothing here with reduced motion.
// All inside one function, so no name here can clash with the page's own script.
(() => {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  // buttons lean a quarter of the way toward the pointer, at most 10 px, and spring back on leave (the CSS `translate`
  // property with a transition in touches.css, so the hover lift keeps its `transform`). Mouse and trackpad only.
  if (matchMedia("(hover: hover) and (pointer: fine)").matches) {
    const pull = v => Math.max(-10, Math.min(10, v * .25)).toFixed(1);
    document.querySelectorAll(".btn").forEach(b => {
      let r;   // measured on enter: measuring while it moves would include its own pull
      b.addEventListener("pointerenter", () => { r = b.getBoundingClientRect(); });
      b.addEventListener("pointermove", e => {
        r ??= b.getBoundingClientRect();
        b.style.translate = `${pull(e.clientX - r.left - r.width / 2)}px ${pull(e.clientY - r.top - r.height / 2)}px`;
      });
      b.addEventListener("pointerleave", () => { b.style.translate = ""; r = null; });
    });
    // a clicked button never gets its leave, so it would come back shifted from the back/forward cache
    addEventListener("pagehide", () => document.querySelectorAll(".btn").forEach(b => b.style.translate = ""));
  }

  // the hero mascot looks at the pointer: its eyes move up to 4 units (of 140) toward it
  const m = document.getElementById("heroMascot"), eyes = m?.querySelector(".m-eyes");
  if (!eyes || !window.gsap?.quickTo || typeof window.hop !== "function") return;
  const ex = gsap.quickTo(eyes, "x", { duration: .35, ease: "power3" }), ey = gsap.quickTo(eyes, "y", { duration: .35, ease: "power3" });
  addEventListener("pointermove", e => {
    if (m.closest(".off")) return;                                    // the hero is off screen
    const r = m.getBoundingClientRect();
    const dx = e.clientX - (r.left + r.width * 71 / 140), dy = e.clientY - (r.top + r.height * 56 / 180);
    const d = Math.hypot(dx, dy) || 1, k = 4 * Math.min(1, d / 250) / d;   // closer than 250 px, the eyes move less
    ex(dx * k); ey(dy * k);
  }, { passive: true });
  // and hops when the pointer reaches one of the app buttons, at most once every 1.5 s
  let last = 0;
  document.querySelectorAll(".hero .btns .btn, .final2 .btns .btn:not(.ghost2)").forEach(b => b.addEventListener("pointerenter", () => {
    if (Date.now() - last < 1500) return;
    last = Date.now(); hop(m);
  }));
})();
