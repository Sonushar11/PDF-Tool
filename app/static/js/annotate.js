(function () {
  const img = document.getElementById("preview-img");
  const marker = document.getElementById("marker");
  const posLabel = document.getElementById("pos-label");
  let xPct = null;
  let yPct = null;

  if (img) {
    img.addEventListener("click", (e) => {
      const rect = img.getBoundingClientRect();
      xPct = ((e.clientX - rect.left) / rect.width) * 100;
      yPct = ((e.clientY - rect.top) / rect.height) * 100;
      marker.style.left = e.clientX - rect.left + "px";
      marker.style.top = e.clientY - rect.top + "px";
      marker.style.display = "block";
      posLabel.textContent = `x: ${xPct.toFixed(1)}%, y: ${yPct.toFixed(1)}%`;
      document.querySelectorAll(".place-form .x-pct").forEach((el) => (el.value = xPct));
      document.querySelectorAll(".place-form .y-pct").forEach((el) => (el.value = yPct));
    });
  }

  document.querySelectorAll(".place-form").forEach((form) => {
    form.addEventListener("submit", (e) => {
      if (xPct === null || yPct === null) {
        e.preventDefault();
        alert("Click on the page preview first to choose a position.");
      }
    });
  });

  // --- signature pad ---
  const canvas = document.getElementById("sig-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  ctx.lineWidth = 2;
  ctx.lineCap = "round";
  ctx.strokeStyle = "#111";
  let drawing = false;

  function pos(e) {
    const rect = canvas.getBoundingClientRect();
    const point = e.touches ? e.touches[0] : e;
    return { x: point.clientX - rect.left, y: point.clientY - rect.top };
  }

  function start(e) {
    drawing = true;
    const p = pos(e);
    ctx.beginPath();
    ctx.moveTo(p.x, p.y);
    e.preventDefault();
  }

  function move(e) {
    if (!drawing) return;
    const p = pos(e);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
    e.preventDefault();
  }

  function end() {
    drawing = false;
  }

  canvas.addEventListener("mousedown", start);
  canvas.addEventListener("mousemove", move);
  window.addEventListener("mouseup", end);
  canvas.addEventListener("touchstart", start, { passive: false });
  canvas.addEventListener("touchmove", move, { passive: false });
  canvas.addEventListener("touchend", end);

  window.clearSig = function () {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  };

  const sigForm = document.getElementById("sig-form");
  if (sigForm) {
    sigForm.addEventListener("submit", (e) => {
      document.getElementById("signature_data").value = canvas.toDataURL("image/png");
    });
  }
})();
