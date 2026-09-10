(function () {
  const img = document.getElementById("preview-img");
  const box = document.getElementById("sel-box");
  const boxData = document.getElementById("box-data");
  const areaForm = document.getElementById("area-form");
  if (!img) return;

  let startX = null;
  let startY = null;
  let dragging = false;
  let selection = null;

  function pctFromEvent(e) {
    const rect = img.getBoundingClientRect();
    return {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
      rectW: rect.width,
      rectH: rect.height,
    };
  }

  img.addEventListener("mousedown", (e) => {
    const p = pctFromEvent(e);
    startX = p.x;
    startY = p.y;
    dragging = true;
    box.style.left = startX + "px";
    box.style.top = startY + "px";
    box.style.width = "0px";
    box.style.height = "0px";
    box.style.display = "block";
  });

  window.addEventListener("mousemove", (e) => {
    if (!dragging) return;
    const p = pctFromEvent(e);
    const x = Math.min(startX, p.x);
    const y = Math.min(startY, p.y);
    const w = Math.abs(p.x - startX);
    const h = Math.abs(p.y - startY);
    box.style.left = x + "px";
    box.style.top = y + "px";
    box.style.width = w + "px";
    box.style.height = h + "px";
    selection = { x, y, w, h, rectW: p.rectW, rectH: p.rectH };
  });

  window.addEventListener("mouseup", () => {
    if (!dragging) return;
    dragging = false;
    if (selection && selection.w > 3 && selection.h > 3) {
      boxData.value = JSON.stringify({
        x_pct: (selection.x / selection.rectW) * 100,
        y_pct: (selection.y / selection.rectH) * 100,
        width_pct: (selection.w / selection.rectW) * 100,
        height_pct: (selection.h / selection.rectH) * 100,
      });
    }
  });

  areaForm.addEventListener("submit", (e) => {
    if (!boxData.value) {
      e.preventDefault();
      alert("Drag a rectangle on the preview first.");
    }
  });
})();
