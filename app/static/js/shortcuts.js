/* Global keyboard shortcuts.

   Undo/redo post to the server, which holds the document history - there is no
   client-side copy of the PDF to roll back. Pages with their own pending state
   (the annotate canvas) can claim Ctrl+Z first by setting window.LOCAL_UNDO to
   a function returning true when it handled the keypress. */
(function () {
  const undoForm = document.getElementById("undo-form");
  const redoForm = document.getElementById("redo-form");
  const help = document.getElementById("shortcut-help");
  const isMac = /Mac|iPhone|iPad/.test(navigator.platform);

  function inTextField() {
    const el = document.activeElement;
    if (!el) return false;
    return /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName) || el.isContentEditable;
  }

  function flashToast(message) {
    let toast = document.getElementById("kb-toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "kb-toast";
      toast.className = "kb-toast";
      document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.classList.add("visible");
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => toast.classList.remove("visible"), 1600);
  }

  function submitHistory(form, what) {
    if (!form) {
      flashToast("Load a PDF first.");
      return;
    }
    if (form.dataset.available === "false") {
      flashToast("Nothing to " + what + ".");
      return;
    }
    form.submit();
  }

  function toggleHelp(force) {
    if (!help) return;
    const show = force === undefined ? !help.classList.contains("visible") : force;
    help.classList.toggle("visible", show);
  }

  document.addEventListener("keydown", (e) => {
    const mod = isMac ? e.metaKey : e.ctrlKey;

    // Escape closes the help panel wherever focus is.
    if (e.key === "Escape") {
      if (help && help.classList.contains("visible")) {
        e.preventDefault();
        toggleHelp(false);
      }
      return;
    }

    // Inside a text field the browser's own undo must win, so only non-editing
    // shortcuts are handled there.
    if (inTextField() && mod && /^(z|y)$/i.test(e.key)) return;

    if (mod && e.key.toLowerCase() === "z" && !e.shiftKey) {
      e.preventDefault();
      if (typeof window.LOCAL_UNDO === "function" && window.LOCAL_UNDO()) return;
      submitHistory(undoForm, "undo");
      return;
    }

    if (mod && (e.key.toLowerCase() === "y" || (e.key.toLowerCase() === "z" && e.shiftKey))) {
      e.preventDefault();
      submitHistory(redoForm, "redo");
      return;
    }

    if (mod && e.key.toLowerCase() === "s") {
      const dl = document.getElementById("download-link");
      if (dl) {
        e.preventDefault();
        window.location.href = dl.href;
      }
      return;
    }

    if (inTextField()) return;

    if (e.key === "?" || (e.key === "/" && e.shiftKey)) {
      e.preventDefault();
      toggleHelp();
    }
  });

  document.querySelectorAll("[data-toggle-help]").forEach((btn) =>
    btn.addEventListener("click", (e) => { e.preventDefault(); toggleHelp(); })
  );

  if (help) {
    help.addEventListener("click", (e) => {
      if (e.target === help || e.target.closest("[data-close-help]")) toggleHelp(false);
    });
  }

  // Show the platform's real modifier key in the help panel.
  if (isMac) {
    document.querySelectorAll(".kbd-mod").forEach((el) => (el.textContent = "⌘"));
  }
})();
