/* Annotate & edit toolbar.
   One preview image, several tools. Every coordinate the server sees is a
   percentage of the page, so the preview can be any size on screen. */
(function () {
  const wrap = document.getElementById("preview-wrap");
  const img = document.getElementById("preview-img");
  if (!wrap || !img) return;

  const overlay = document.getElementById("overlay");
  const ctx = overlay.getContext("2d");
  const marker = document.getElementById("marker");
  const spanLayer = document.getElementById("span-layer");
  const posLabel = document.getElementById("pos-label");
  const hint = document.getElementById("tool-hint");

  // point  - a single click position (text, stamp, signature)
  // rect   - a dragged box or line (highlight, shape, whiteout)
  // ink    - accumulated freehand strokes (pen)
  // spans  - clickable overlay of existing text runs (edit text)
  const TOOLS = {
    select:    { mode: "point", hint: "Click the page to set a position." },
    text:      { mode: "point", hint: "Click where the note should start." },
    highlight: { mode: "sweep", hint: "Hold and slide across the text, like a marker." },
    pen:       { mode: "ink",   hint: "Draw freehand, then press Apply." },
    shape:     { mode: "rect",  hint: "Drag to draw the shape." },
    whiteout:  { mode: "rect",  hint: "Drag over the content to remove." },
    edittext:  { mode: "spans", hint: "Click a highlighted run of text." },
    stamp:     { mode: "point", hint: "Click where the image should sit." },
    signature: { mode: "point", hint: "Click where the signature should sit." },
  };

  let tool = "select";
  let point = null;              // {x, y} in page %
  let rect = null;               // {x0, y0, x1, y1} in page %
  let strokes = [];              // array of arrays of [x%, y%]
  let drawing = null;            // in-progress gesture
  let spansLoaded = false;
  let words = null;              // word boxes for snap-to-text highlighting
  let wordsLoading = null;
  let sweepHits = [];            // words under the current stroke
  let sweepBand = null;          // fallback band when a page has no text

  /* ---------------- canvas sizing ---------------- */

  function sizeCanvas() {
    const w = img.clientWidth;
    const h = img.clientHeight;
    if (!w || !h) return;
    const dpr = window.devicePixelRatio || 1;
    overlay.width = Math.round(w * dpr);
    overlay.height = Math.round(h * dpr);
    overlay.style.width = w + "px";
    overlay.style.height = h + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    redraw();
    positionMarker();
    layoutSpans();
  }

  if (img.complete) sizeCanvas();
  img.addEventListener("load", sizeCanvas);
  window.addEventListener("resize", sizeCanvas);

  /* ---------------- coordinate helpers ---------------- */

  function pctFromEvent(e) {
    const r = img.getBoundingClientRect();
    return {
      x: clamp(((e.clientX - r.left) / r.width) * 100),
      y: clamp(((e.clientY - r.top) / r.height) * 100),
    };
  }
  const clamp = (v) => Math.max(0, Math.min(100, v));
  const toPx = (xPct, yPct) => [
    (xPct / 100) * img.clientWidth,
    (yPct / 100) * img.clientHeight,
  ];

  /* ---------------- drawing ---------------- */

  function redraw() {
    ctx.clearRect(0, 0, overlay.width, overlay.height);
    drawStrokes();
    drawPending();
    drawSweep();
  }

  function drawStrokes() {
    if (!strokes.length) return;
    ctx.save();
    ctx.strokeStyle = valueOf("ink_color", "#e02424");
    ctx.lineWidth = parseFloat(valueOf("ink_width", "2")) || 2;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    for (const stroke of strokes) {
      if (stroke.length < 2) continue;
      ctx.beginPath();
      const [sx, sy] = toPx(stroke[0][0], stroke[0][1]);
      ctx.moveTo(sx, sy);
      for (let i = 1; i < stroke.length; i++) {
        const [px, py] = toPx(stroke[i][0], stroke[i][1]);
        ctx.lineTo(px, py);
      }
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawPending() {
    if (!rect) return;
    const [x0, y0] = toPx(rect.x0, rect.y0);
    const [x1, y1] = toPx(rect.x1, rect.y1);
    const kind = tool === "shape" ? valueOf("shape_kind", "rect") : "rect";

    ctx.save();
    if (tool === "whiteout") {
      ctx.fillStyle = "rgba(255,255,255,0.75)";
      ctx.strokeStyle = "#ff5f5f";
    } else if (tool === "highlight") {
      ctx.fillStyle = hexToRgba(valueOf("hl_color", "#ffeb3b"), 0.4);
      ctx.strokeStyle = valueOf("hl_color", "#ffeb3b");
    } else {
      ctx.fillStyle = document.getElementById("shape_filled") &&
        document.getElementById("shape_filled").checked
        ? hexToRgba(valueOf("shape_fill", "#ffe066"), 0.5)
        : "transparent";
      ctx.strokeStyle = valueOf("shape_color", "#e02424");
    }
    ctx.lineWidth = 2;
    ctx.setLineDash([6, 4]);

    if (kind === "line" || kind === "arrow") {
      ctx.beginPath();
      ctx.moveTo(x0, y0);
      ctx.lineTo(x1, y1);
      ctx.stroke();
      if (kind === "arrow") drawArrowHead(x0, y0, x1, y1);
    } else if (kind === "ellipse") {
      ctx.beginPath();
      ctx.ellipse((x0 + x1) / 2, (y0 + y1) / 2,
        Math.abs(x1 - x0) / 2, Math.abs(y1 - y0) / 2, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    } else {
      const rx = Math.min(x0, x1), ry = Math.min(y0, y1);
      const rw = Math.abs(x1 - x0), rh = Math.abs(y1 - y0);
      ctx.fillRect(rx, ry, rw, rh);
      ctx.strokeRect(rx, ry, rw, rh);
    }
    ctx.restore();
  }

  function drawArrowHead(x0, y0, x1, y1) {
    const angle = Math.atan2(y1 - y0, x1 - x0);
    const size = 12;
    ctx.setLineDash([]);
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x1 - size * Math.cos(angle - Math.PI / 6), y1 - size * Math.sin(angle - Math.PI / 6));
    ctx.moveTo(x1, y1);
    ctx.lineTo(x1 - size * Math.cos(angle + Math.PI / 6), y1 - size * Math.sin(angle + Math.PI / 6));
    ctx.stroke();
  }

  function hexToRgba(hex, alpha) {
    const v = (hex || "").replace("#", "");
    if (v.length !== 6) return "rgba(255,235,59," + alpha + ")";
    const n = parseInt(v, 16);
    return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
  }

  function valueOf(id, fallback) {
    const el = document.getElementById(id);
    return el && el.value ? el.value : fallback;
  }

  /* ---------------- marker ---------------- */

  function positionMarker() {
    if (!point) { marker.style.display = "none"; return; }
    const [px, py] = toPx(point.x, point.y);
    marker.style.left = px + "px";
    marker.style.top = py + "px";
    marker.style.display = "block";
  }

  function setPoint(p) {
    point = p;
    positionMarker();
    posLabel.textContent = `Position: ${p.x.toFixed(1)}% across, ${p.y.toFixed(1)}% down.`;
    document.querySelectorAll(".place-form .x-pct").forEach((el) => (el.value = p.x));
    document.querySelectorAll(".place-form .y-pct").forEach((el) => (el.value = p.y));
  }

  /* ---------------- pointer gestures ---------------- */

  wrap.addEventListener("pointerdown", (e) => {
    const cfg = TOOLS[tool];
    if (!cfg || cfg.mode === "spans") return;
    if (e.button !== 0) return;
    e.preventDefault();
    wrap.setPointerCapture(e.pointerId);
    const p = pctFromEvent(e);

    if (cfg.mode === "point") {
      setPoint(p);
    } else if (cfg.mode === "rect") {
      drawing = { kind: "rect", x0: p.x, y0: p.y };
      rect = { x0: p.x, y0: p.y, x1: p.x, y1: p.y };
      redraw();
    } else if (cfg.mode === "ink") {
      drawing = { kind: "ink", points: [[p.x, p.y]] };
      strokes.push(drawing.points);
    } else if (cfg.mode === "sweep") {
      drawing = { kind: "sweep", last: p };
      sweepHits = [];
      sweepBand = { x0: p.x, y0: p.y, x1: p.x, y1: p.y };
      collectSweep(p, p);
      redraw();
    }
  });

  wrap.addEventListener("pointermove", (e) => {
    if (!drawing) return;
    const p = pctFromEvent(e);
    if (drawing.kind === "rect") {
      rect = { x0: drawing.x0, y0: drawing.y0, x1: p.x, y1: p.y };
    } else if (drawing.kind === "ink") {
      drawing.points.push([p.x, p.y]);
    } else if (drawing.kind === "sweep") {
      collectSweep(drawing.last, p);
      drawing.last = p;
      sweepBand.x1 = p.x;
      sweepBand.y1 = p.y;
    }
    redraw();
  });

  wrap.addEventListener("pointerup", (e) => {
    if (!drawing) return;
    if (drawing.kind === "rect") {
      const p = pctFromEvent(e);
      rect = { x0: drawing.x0, y0: drawing.y0, x1: p.x, y1: p.y };
      // A click with no drag is almost always a misfire, not a zero-size shape.
      if (Math.abs(rect.x1 - rect.x0) < 0.4 && Math.abs(rect.y1 - rect.y0) < 0.4) {
        rect = null;
      }
    } else if (drawing.kind === "ink" && drawing.points.length < 2) {
      strokes.pop();
    } else if (drawing.kind === "sweep") {
      drawing = null;
      applySweep();
      return;
    }
    drawing = null;
    redraw();
    syncRectInputs();
    syncInk();
  });

  wrap.addEventListener("pointercancel", () => { drawing = null; redraw(); });

  /* ---------------- rect -> form fields ---------------- */

  function syncRectInputs() {
    const panel = activePanel();
    if (!panel) return;
    const form = panel.querySelector(".rect-form");
    if (!form) return;

    const readout = form.querySelector(".rect-readout");
    const btn = form.querySelector(".needs-rect");

    if (!rect) {
      if (btn) btn.disabled = true;
      if (readout) readout.textContent = "Drag on the page to choose an area.";
      refreshRailUndo();
      return;
    }

    // Corner form (shape, whiteout) keeps direction; box form (highlight)
    // needs a normalised origin plus width/height.
    setIf(form, ".r-x0", rect.x0);
    setIf(form, ".r-y0", rect.y0);
    setIf(form, ".r-x1", rect.x1);
    setIf(form, ".r-y1", rect.y1);

    const x = Math.min(rect.x0, rect.x1);
    const y = Math.min(rect.y0, rect.y1);
    const w = Math.abs(rect.x1 - rect.x0);
    const h = Math.abs(rect.y1 - rect.y0);
    setIf(form, ".r-x", x);
    setIf(form, ".r-y", y);
    setIf(form, ".r-w", w);
    setIf(form, ".r-h", h);

    if (btn) btn.disabled = false;
    if (readout) {
      readout.textContent =
        `Area: ${w.toFixed(1)}% x ${h.toFixed(1)}%, from ${x.toFixed(1)}% across, ${y.toFixed(1)}% down.`;
    }
    refreshRailUndo();
  }

  function setIf(form, selector, value) {
    const el = form.querySelector(selector);
    if (el) el.value = value;
  }

  /* ---------------- ink -> form fields ---------------- */

  function syncInk() {
    const field = document.getElementById("ink-strokes");
    const apply = document.getElementById("ink-apply");
    const readout = document.getElementById("ink-readout");
    if (!field) return;
    const usable = strokes.filter((s) => s.length >= 2);
    field.value = JSON.stringify(usable);
    if (apply) apply.disabled = usable.length === 0;
    if (readout) {
      readout.textContent = usable.length
        ? `${usable.length} stroke${usable.length === 1 ? "" : "s"} ready to apply.`
        : "No strokes yet.";
    }
    refreshRailUndo();
  }

  const inkClear = document.getElementById("ink-clear");
  if (inkClear) {
    inkClear.addEventListener("click", () => {
      strokes = [];
      redraw();
      syncInk();
    });
  }

  /* ---------------- highlighter pen ----------------
     A real marker: hold and slide across the text. The stroke is matched
     against the page's word boxes so the highlight lands on the words rather
     than wherever the hand wobbled, and it applies on release - no separate
     Apply step. Pages with no text layer (scans) paint the swept band. */

  function loadWords() {
    if (words || wordsLoading) return wordsLoading;
    wordsLoading = fetch(window.WORDS_URL, { headers: { Accept: "application/json" } })
      .then((r) => r.json())
      .then((data) => {
        words = data.words || [];
        setHighlightStatus(words.length
          ? "Hold and slide across the text."
          : "No text layer on this page - sweeps will highlight freehand. OCR it first to snap to words.");
        return words;
      })
      .catch(() => {
        words = [];
        setHighlightStatus("Could not read this page's text - sweeps will highlight freehand.");
        return words;
      });
    return wordsLoading;
  }

  // Sampled along the segment so a fast flick cannot skip over words.
  function collectSweep(from, to) {
    if (!words || !words.length) return;
    const steps = Math.max(2, Math.ceil(Math.hypot(to.x - from.x, to.y - from.y) / 0.4));
    for (let i = 0; i <= steps; i++) {
      const t = i / steps;
      const px = from.x + (to.x - from.x) * t;
      const py = from.y + (to.y - from.y) * t;
      for (const w of words) {
        if (px >= w.x_pct && px <= w.x_pct + w.w_pct &&
            py >= w.y_pct && py <= w.y_pct + w.h_pct &&
            !sweepHits.includes(w)) {
          sweepHits.push(w);
        }
      }
    }
  }

  function drawSweep() {
    if (tool !== "highlight") return;
    const colour = valueOf("hl_color", "#ffeb3b");
    ctx.save();
    ctx.fillStyle = hexToRgba(colour, 0.45);

    if (sweepHits.length) {
      for (const w of sweepHits) {
        const [x, y] = toPx(w.x_pct, w.y_pct);
        const [x2, y2] = toPx(w.x_pct + w.w_pct, w.y_pct + w.h_pct);
        ctx.fillRect(x, y, x2 - x, y2 - y);
      }
    } else if (sweepBand && drawing) {
      const [x, y] = toPx(Math.min(sweepBand.x0, sweepBand.x1), Math.min(sweepBand.y0, sweepBand.y1));
      const [x2, y2] = toPx(Math.max(sweepBand.x0, sweepBand.x1), Math.max(sweepBand.y0, sweepBand.y1));
      ctx.fillRect(x, y - 7, Math.max(x2 - x, 2), Math.max(y2 - y, 0) + 14);
    }
    ctx.restore();
  }

  async function applySweep() {
    let boxes = sweepHits.map((w) => ({
      x_pct: w.x_pct, y_pct: w.y_pct, w_pct: w.w_pct, h_pct: w.h_pct,
    }));

    if (!boxes.length && sweepBand) {
      const x = Math.min(sweepBand.x0, sweepBand.x1);
      const y = Math.min(sweepBand.y0, sweepBand.y1);
      const w = Math.abs(sweepBand.x1 - sweepBand.x0);
      const h = Math.abs(sweepBand.y1 - sweepBand.y0);
      if (w < 0.6 && h < 0.6) { resetSweep(); return; }   // a stray click, not a sweep
      boxes = [{
        x_pct: x, y_pct: Math.max(0, y - 0.5),
        w_pct: Math.max(w, 1), h_pct: Math.max(h, 1.8),
      }];
    }
    if (!boxes.length) { resetSweep(); return; }

    setHighlightStatus("Applying...");
    try {
      const res = await fetch(window.SWEEP_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          page: window.ANNOTATE_PAGE,
          color: valueOf("hl_color", "#ffeb3b"),
          boxes: boxes,
        }),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "Could not highlight.");
      await refreshPreview();
      setHighlightStatus(
        `Highlighted ${boxes.length} ${sweepHits.length ? "word" : "area"}${boxes.length === 1 ? "" : "s"}. Keep sweeping.`);
      markEdited();
    } catch (err) {
      setHighlightStatus("Could not apply that highlight.");
    }
    resetSweep();
  }

  function resetSweep() {
    sweepHits = [];
    sweepBand = null;
    redraw();
  }

  function setHighlightStatus(text) {
    const el = document.getElementById("hl-status");
    if (el) el.textContent = text;
  }

  // The highlight is baked into the PDF now, so re-render the page image.
  // Word boxes are unaffected by a highlight, so they are not refetched.
  function refreshPreview() {
    return new Promise((resolve) => {
      const base = img.src.split("?")[0];
      const next = new Image();
      next.onload = next.onerror = () => { img.src = next.src; resolve(); };
      next.src = base + "?t=" + Date.now();
    });
  }

  // Applying a sweep without a page reload means the undo/redo affordances
  // have to be brought up to date by hand.
  function markEdited() {
    const u = document.getElementById("rail-undo");
    const r = document.getElementById("rail-redo");
    if (u) u.disabled = false;
    if (r) r.disabled = true;
    const uf = document.getElementById("undo-form");
    if (uf) uf.dataset.available = "true";
    const rf = document.getElementById("redo-form");
    if (rf) rf.dataset.available = "false";
  }

  /* ---------------- local undo ----------------
     Ctrl+Z should take back the stroke or selection you just made before it
     reaches the server and rolls back the whole document. shortcuts.js calls
     this first and only posts the undo form when it returns false. */
  window.LOCAL_UNDO = function () {
    if (strokes.length) {
      strokes.pop();
      redraw();
      syncInk();
      return true;
    }
    if (rect) {
      rect = null;
      redraw();
      syncRectInputs();
      return true;
    }
    return false;
  };

  const railUndo = document.getElementById("rail-undo");
  const railRedo = document.getElementById("rail-redo");
  // Server history decides the button's resting state, but unapplied local
  // work must be undoable even on a document with no saved history yet.
  const serverCanUndo = railUndo ? !railUndo.disabled : false;

  function refreshRailUndo() {
    if (!railUndo) return;
    const hasLocal = strokes.some((s) => s.length >= 2) || Boolean(rect);
    railUndo.disabled = !(hasLocal || serverCanUndo);
  }
  if (railUndo) {
    railUndo.addEventListener("click", () => {
      if (window.LOCAL_UNDO()) return;
      const form = document.getElementById("undo-form");
      if (form) form.submit();
    });
  }
  if (railRedo) {
    railRedo.addEventListener("click", () => {
      const form = document.getElementById("redo-form");
      if (form) form.submit();
    });
  }

  ["ink_color", "ink_width", "hl_color", "shape_color", "shape_fill", "shape_kind", "shape_filled"]
    .forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.addEventListener("input", redraw);
    });

  /* ---------------- text spans (click to edit) ---------------- */

  async function loadSpans() {
    if (spansLoaded) return;
    spansLoaded = true;
    const status = document.getElementById("et-status");
    try {
      const res = await fetch(window.SPANS_URL, { headers: { Accept: "application/json" } });
      const data = await res.json();
      const spans = data.spans || [];
      spanLayer.innerHTML = "";
      spans.forEach((s) => {
        const box = document.createElement("div");
        box.className = "span-box";
        box.dataset.text = s.text;
        box.dataset.size = s.size;
        box.dataset.x = s.x_pct;
        box.dataset.y = s.y_pct;
        box.dataset.w = s.w_pct;
        box.dataset.h = s.h_pct;
        box.title = s.text;
        spanLayer.appendChild(box);
      });
      layoutSpans();
      if (status) {
        status.textContent = spans.length
          ? `${spans.length} editable text run${spans.length === 1 ? "" : "s"} found - click one on the page.`
          : "No editable text found on this page. Scanned pages need OCR first.";
      }
    } catch (err) {
      spansLoaded = false;
      if (status) status.textContent = "Could not load the text on this page.";
    }
  }

  function layoutSpans() {
    const w = img.clientWidth;
    const h = img.clientHeight;
    spanLayer.querySelectorAll(".span-box").forEach((box) => {
      box.style.left = (parseFloat(box.dataset.x) / 100) * w + "px";
      box.style.top = (parseFloat(box.dataset.y) / 100) * h + "px";
      box.style.width = (parseFloat(box.dataset.w) / 100) * w + "px";
      box.style.height = (parseFloat(box.dataset.h) / 100) * h + "px";
    });
  }

  spanLayer.addEventListener("click", (e) => {
    const box = e.target.closest(".span-box");
    if (!box) return;
    spanLayer.querySelectorAll(".span-box.active").forEach((b) => b.classList.remove("active"));
    box.classList.add("active");

    document.getElementById("et-x").value = box.dataset.x;
    document.getElementById("et-y").value = box.dataset.y;
    document.getElementById("et-w").value = box.dataset.w;
    document.getElementById("et-h").value = box.dataset.h;

    const textInput = document.getElementById("et-text");
    const sizeInput = document.getElementById("et-size");
    const apply = document.getElementById("et-apply");
    const status = document.getElementById("et-status");

    textInput.disabled = false;
    sizeInput.disabled = false;
    apply.disabled = false;
    textInput.value = box.dataset.text;
    sizeInput.value = "";
    sizeInput.placeholder = `original ~${parseFloat(box.dataset.size).toFixed(1)}pt`;
    if (status) status.textContent = "Editing: " + box.dataset.text;
    textInput.focus();
    textInput.select();
  });

  /* ---------------- tool switching ---------------- */

  function activePanel() {
    return document.querySelector(`.tool-panel[data-panel="${tool}"]`);
  }

  function setTool(next) {
    if (!TOOLS[next]) return;
    tool = next;

    document.querySelectorAll(".tool-btn").forEach((b) =>
      b.classList.toggle("active", b.dataset.tool === next));
    document.querySelectorAll(".tool-panel").forEach((p) =>
      (p.hidden = p.dataset.panel !== next));

    const cfg = TOOLS[next];
    if (hint) hint.textContent = cfg.hint;
    wrap.dataset.mode = cfg.mode;

    // Pending work for one tool shouldn't carry over to another.
    rect = null;
    sweepHits = [];
    sweepBand = null;
    redraw();
    syncRectInputs();

    spanLayer.classList.toggle("visible", cfg.mode === "spans");
    if (cfg.mode === "spans") loadSpans();
    if (cfg.mode === "sweep") loadWords();
  }

  document.querySelectorAll(".tool-btn").forEach((btn) => {
    btn.addEventListener("click", () => setTool(btn.dataset.tool));
  });

  const KEYS = { v: "select", t: "text", h: "highlight", p: "pen",
                 s: "shape", w: "whiteout", e: "edittext", i: "stamp", g: "signature" };
  document.addEventListener("keydown", (e) => {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    const el = document.activeElement;
    if (el && /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)) return;
    const next = KEYS[e.key.toLowerCase()];
    if (next) { e.preventDefault(); setTool(next); }
  });

  /* ---------------- colour swatches ---------------- */

  document.querySelectorAll(".swatch-row").forEach((row) => {
    const target = document.getElementById(row.dataset.target);
    row.querySelectorAll(".swatch").forEach((sw) => {
      sw.addEventListener("click", () => {
        if (target) { target.value = sw.dataset.color; }
        row.querySelectorAll(".swatch").forEach((s) => s.classList.remove("active"));
        sw.classList.add("active");
        redraw();
      });
    });
  });

  /* ---------------- submit guards ---------------- */

  document.querySelectorAll(".place-form").forEach((form) => {
    form.addEventListener("submit", (e) => {
      if (!point) {
        e.preventDefault();
        dismissOverlay();
        alert("Click the page first to choose where this goes.");
      }
    });
  });

  // The work overlay listener runs before this one, so if a guard cancels the
  // submit the overlay has to be taken back down by hand.
  function dismissOverlay() {
    const ov = document.getElementById("work-overlay");
    if (ov) ov.classList.remove("visible");
  }

  /* ---------------- signature pad ---------------- */

  const canvas = document.getElementById("sig-canvas");
  if (canvas) {
    const sctx = canvas.getContext("2d");
    sctx.lineWidth = 2;
    sctx.lineCap = "round";
    sctx.strokeStyle = "#111";
    let signing = false;

    const sigPos = (e) => {
      const r = canvas.getBoundingClientRect();
      const pt = e.touches ? e.touches[0] : e;
      return { x: pt.clientX - r.left, y: pt.clientY - r.top };
    };

    const sigStart = (e) => {
      signing = true;
      const p = sigPos(e);
      sctx.beginPath();
      sctx.moveTo(p.x, p.y);
      e.preventDefault();
    };
    const sigMove = (e) => {
      if (!signing) return;
      const p = sigPos(e);
      sctx.lineTo(p.x, p.y);
      sctx.stroke();
      e.preventDefault();
    };
    const sigEnd = () => { signing = false; };

    canvas.addEventListener("mousedown", sigStart);
    canvas.addEventListener("mousemove", sigMove);
    window.addEventListener("mouseup", sigEnd);
    canvas.addEventListener("touchstart", sigStart, { passive: false });
    canvas.addEventListener("touchmove", sigMove, { passive: false });
    canvas.addEventListener("touchend", sigEnd);

    window.clearSig = () => sctx.clearRect(0, 0, canvas.width, canvas.height);

    const sigForm = document.getElementById("sig-form");
    if (sigForm) {
      sigForm.addEventListener("submit", () => {
        document.getElementById("signature_data").value = canvas.toDataURL("image/png");
      });
    }
  }

  setTool("select");
})();
