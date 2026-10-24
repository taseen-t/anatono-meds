// Page changes between the landing page and the app (cross-document view transitions: Chrome, Edge, Safari 18.2+;
// other browsers just change page). The page you leave writes down what you clicked; both pages then give the
// transition a type, and vt.css picks the animation from it:
//   grow   a coral button grows into the app        sheet  a text link slides the app up over the landing page
//   back   the app slides down to the landing page   (none) the browser's plain cross-fade
// The logo glides between the two headers every time (it's a named part in vt.css). Reduced motion: plain fade only.
// Loaded in <head> so the pageswap / pagereveal listeners are there before the first paint.
(() => {
  const KEY = "anatono.vt", still = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const where = u => /\/app\.html$/.test(new URL(u, location.href).pathname) ? "app" : "home";

  // a click on a link to the other page: remember how we're leaving (downloads, new tabs and other sites don't count)
  addEventListener("click", e => {
    const a = e.target.closest?.("a[href]");
    if (!a || e.defaultPrevented || a.hasAttribute("download") || a.target === "_blank" || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    const u = new URL(a.href, location.href);
    if (u.origin !== location.origin || u.pathname === location.pathname) return;
    const type = where(u) === "app" ? (a.classList.contains("btn") ? "grow" : "sheet") : "back";
    sessionStorage.setItem(KEY, JSON.stringify({ type, at: Date.now() }));
    if (type === "grow" && !still) a.style.viewTransitionName = "cta";
  });

  // browser back / forward have no click, so the direction decides; a fresh note from a click wins otherwise
  function typeOf(act) {
    if (still || !act) return null;
    const from = act.from?.url && where(act.from.url), to = act.entry?.url && where(act.entry.url);
    if (from && to && from === to) return null;
    if (act.navigationType === "traverse") return to === "home" ? "back" : "sheet";
    try { const n = JSON.parse(sessionStorage.getItem(KEY)); if (n && Date.now() - n.at < 8000) return n.type; } catch {}
    return to === "home" ? "back" : to === "app" ? "sheet" : null;
  }
  const clean = () => {
    document.querySelectorAll("[style*='view-transition-name']").forEach(el => el.style.viewTransitionName = "");
    document.documentElement.classList.remove("vt-grow");
  };

  addEventListener("pageswap", e => {
    if (!e.viewTransition) return;
    const t = typeOf(e.activation);
    if (t !== "grow") clean();
    // the logo glides only from where it's visible (the menu bar can be hidden while scrolling)
    const logo = document.querySelector(".vt-logo"), r = logo?.getBoundingClientRect();
    if (logo && (r.bottom < 0 || r.top > innerHeight)) logo.style.viewTransitionName = "none";
    if (t) e.viewTransition.types.add(t);
  });
  addEventListener("pagereveal", e => {
    clean();                                                  // a page back from the cache can still carry old names
    const t = typeOf(window.navigation?.activation);
    sessionStorage.removeItem(KEY);
    if (!e.viewTransition || !t) return;
    e.viewTransition.types.add(t);
    if (t === "grow") document.documentElement.classList.add("vt-grow");   // the app takes the button's place (vt.css)
  });
})();
