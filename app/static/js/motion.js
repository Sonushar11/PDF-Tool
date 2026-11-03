/* Motion layer: GSAP intro, scroll reveals, view transitions, work overlay.
   Degrades to a plain static page if GSAP is unavailable or motion is reduced. */
(function () {
  const root = document.documentElement;
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // If GSAP never arrived, drop the pre-hidden state so nothing stays invisible.
  if (!window.gsap || reduced) {
    root.classList.remove("motion");
    initDropzones();
    initWorkOverlay();
    return;
  }

  const { gsap } = window;
  if (window.ScrollTrigger) gsap.registerPlugin(window.ScrollTrigger);

  /* ---------- intro timeline ---------- */
  const tl = gsap.timeline({ defaults: { ease: "power3.out" } });

  tl.from(".topnav", { y: -18, opacity: 0, duration: 0.45 })
    .from(".topnav .brand", { x: -10, opacity: 0, duration: 0.4 }, "-=0.25")
    .from(".topnav a:not(.brand)", {
      y: -6, opacity: 0, duration: 0.3, stagger: 0.035,
    }, "-=0.3");

  /* ---------- scroll reveals ----------
     Elements already in view fire immediately, so this covers the first paint
     and anything further down the page with one code path. */
  const revealables = gsap.utils.toArray(".reveal");

  if (window.ScrollTrigger && revealables.length) {
    window.ScrollTrigger.batch(revealables, {
      start: "top 92%",
      once: true,
      onEnter: (batch) =>
        gsap.to(batch, {
          opacity: 1, y: 0, duration: 0.55, stagger: 0.08,
          ease: "power3.out", overwrite: true,
        }),
    });
    gsap.set(revealables, { y: 22 });
  } else {
    gsap.to(revealables, { opacity: 1, y: 0, duration: 0.5, stagger: 0.07 });
  }

  /* ---------- page thumbnail stagger ----------
     Skipped on large documents - a few hundred staggered tweens costs more
     than the effect is worth. */
  const thumbs = gsap.utils.toArray("#page-grid .page-thumb");
  if (thumbs.length && thumbs.length <= 60) {
    gsap.from(thumbs, {
      opacity: 0, y: 18, scale: 0.96, duration: 0.45,
      stagger: { each: 0.03, from: "start" },
      ease: "power2.out", delay: 0.15, clearProps: "all",
    });
  }

  /* ---------- drag reorder feedback ---------- */
  const grid = document.getElementById("page-grid");
  if (grid) {
    grid.addEventListener("dragstart", (e) => {
      const t = e.target.closest(".page-thumb");
      if (t) t.classList.add("dragging");
    });
    grid.addEventListener("dragend", (e) => {
      const t = e.target.closest(".page-thumb");
      if (t) t.classList.remove("dragging");
    });
  }

  /* ---------- Barba-style view transition ----------
     Only nav + backlinks, so file downloads and form posts are never faded. */
  const main = document.querySelector("main");
  document.querySelectorAll(".topnav a, .backlink").forEach((link) => {
    link.addEventListener("click", (e) => {
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
      if (link.hasAttribute("download") || link.target === "_blank") return;
      const href = link.getAttribute("href");
      if (!href || href.startsWith("#")) return;

      e.preventDefault();
      gsap.to(main, {
        opacity: 0, y: -10, duration: 0.2, ease: "power2.in",
        onComplete: () => { window.location.href = href; },
      });
      // Restore if the navigation stalls or the user comes back via bfcache.
      setTimeout(() => gsap.to(main, { opacity: 1, y: 0, duration: 0.25 }), 1800);
    });
  });

  window.addEventListener("pageshow", (e) => {
    if (e.persisted) gsap.set(main, { opacity: 1, y: 0 });
  });

  initDropzones();
  initWorkOverlay();

  /* ====================================================================== */

  function initDropzones() {
    document.querySelectorAll(".dropzone").forEach((zone) => {
      const input = zone.querySelector("input[type=file]");
      const label = zone.querySelector(".dz-file");
      if (!input) return;

      ["dragenter", "dragover"].forEach((ev) =>
        zone.addEventListener(ev, (e) => {
          e.preventDefault();
          zone.classList.add("dragover");
        })
      );
      ["dragleave", "drop"].forEach((ev) =>
        zone.addEventListener(ev, (e) => {
          e.preventDefault();
          zone.classList.remove("dragover");
        })
      );
      zone.addEventListener("drop", (e) => {
        if (e.dataTransfer && e.dataTransfer.files.length) {
          input.files = e.dataTransfer.files;
          input.dispatchEvent(new Event("change", { bubbles: true }));
        }
      });

      input.addEventListener("change", () => {
        if (!label) return;
        const n = input.files.length;
        if (!n) { label.textContent = ""; return; }
        label.textContent = n === 1 ? input.files[0].name : n + " files selected";
        if (window.gsap && !reduced) {
          gsap.fromTo(label, { opacity: 0, y: 6 }, { opacity: 1, y: 0, duration: 0.3 });
        }
      });
    });
  }

  function initWorkOverlay() {
    const overlay = document.getElementById("work-overlay");
    if (!overlay) return;
    const titleEl = overlay.querySelector(".work-title");
    const bar = overlay.querySelector(".work-bar");
    let barTween = null;

    document.querySelectorAll("form[data-slow]").forEach((form) => {
      form.addEventListener("submit", (e) => {
        // Let a confirm()/validation cancel win before showing the overlay.
        if (e.defaultPrevented) return;
        titleEl.textContent = form.dataset.slow || "Working...";
        overlay.classList.add("visible");

        if (window.gsap && !reduced) {
          gsap.fromTo(overlay, { opacity: 0 }, { opacity: 1, duration: 0.2 });
          barTween = gsap.fromTo(bar,
            { xPercent: -110 },
            { xPercent: 440, duration: 1.3, ease: "power1.inOut", repeat: -1 }
          );
        }
      });
    });

    // Coming back via the back button must not leave the overlay stuck on.
    window.addEventListener("pageshow", () => {
      overlay.classList.remove("visible");
      if (barTween) barTween.kill();
    });
  }
})();
