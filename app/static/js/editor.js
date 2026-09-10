(function () {
  const grid = document.getElementById("page-grid");
  if (!grid) return;

  // --- selection highlight ---
  grid.addEventListener("change", (e) => {
    if (e.target.classList.contains("page-check")) {
      e.target.closest(".page-thumb").classList.toggle("selected", e.target.checked);
    }
  });

  function selectedPages() {
    return Array.from(grid.querySelectorAll(".page-check:checked")).map((c) => c.value);
  }

  window.submitPages = function (path, extra) {
    const pages = selectedPages();
    if (pages.length === 0) {
      alert("Select at least one page first.");
      return;
    }
    const form = document.createElement("form");
    form.method = "post";
    form.action = path;
    const pagesInput = document.createElement("input");
    pagesInput.type = "hidden";
    pagesInput.name = "pages";
    pagesInput.value = pages.join(",");
    form.appendChild(pagesInput);
    for (const [key, value] of Object.entries(extra || {})) {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = key;
      input.value = value;
      form.appendChild(input);
    }
    document.body.appendChild(form);
    form.submit();
  };

  window.saveOrder = function () {
    const order = Array.from(grid.querySelectorAll(".page-thumb")).map((el) => el.dataset.index);
    const form = document.createElement("form");
    form.method = "post";
    form.action = "/pages/reorder";
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = "order";
    input.value = order.join(",");
    form.appendChild(input);
    document.body.appendChild(form);
    form.submit();
  };

  // --- native HTML5 drag & drop reordering ---
  let dragEl = null;

  grid.addEventListener("dragstart", (e) => {
    const thumb = e.target.closest(".page-thumb");
    if (!thumb) return;
    dragEl = thumb;
    e.dataTransfer.effectAllowed = "move";
  });

  grid.addEventListener("dragover", (e) => {
    e.preventDefault();
    const target = e.target.closest(".page-thumb");
    if (!target || target === dragEl) return;
    const rect = target.getBoundingClientRect();
    const before = (e.clientX - rect.left) / rect.width < 0.5;
    grid.insertBefore(dragEl, before ? target : target.nextSibling);
  });

  grid.addEventListener("drop", (e) => e.preventDefault());
})();
