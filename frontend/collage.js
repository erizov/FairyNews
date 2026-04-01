/**
 * Коллаж: GET /api/ui/collage. При сбое API или картинок — CSS-плейсхолдеры.
 */
(function () {
  var DEFAULT_MOTIFS = [
    "news",
    "neutral",
    "news",
    "folktale",
    "folktale",
    "folktale",
    "neutral",
    "neutral",
  ];

  function appendPlaceholder(cell, motif, alt) {
    var ph = document.createElement("div");
    var m = motif || "neutral";
    ph.className = "collage-placeholder collage-placeholder--" + m;
    ph.setAttribute("role", "img");
    ph.setAttribute("aria-label", alt || "");
    cell.appendChild(ph);
  }

  function renderPlaceholderGrid(container) {
    if (!container) {
      return;
    }
    container.textContent = "";
    container.className = "collage-grid";
    DEFAULT_MOTIFS.forEach(function (motif) {
      var cell = document.createElement("div");
      cell.className = "collage-cell";
      appendPlaceholder(cell, motif, "");
      container.appendChild(cell);
    });
  }

  function wireImage(img, tile, cell) {
    var fb = (tile.fallback_src || "").trim();
    img.addEventListener("error", function () {
      if (fb && img.src !== fb) {
        img.src = fb;
        return;
      }
      if (cell.contains(img)) {
        var ph = document.createElement("div");
        var motif = tile.motif || "neutral";
        ph.className =
          "collage-placeholder collage-placeholder--" + motif;
        ph.setAttribute("role", "img");
        ph.setAttribute("aria-label", tile.alt || "");
        cell.replaceChild(ph, img);
      }
    });
  }

  function mountCollage(containerId) {
    var container = document.getElementById(containerId);
    if (!container) {
      return;
    }
    fetch("/api/ui/collage")
      .then(function (r) {
        if (!r.ok) {
          throw new Error("collage");
        }
        return r.json();
      })
      .then(function (data) {
        var items = data.items || [];
        if (!items.length) {
          renderPlaceholderGrid(container);
          return;
        }
        container.textContent = "";
        container.className = "collage-grid";
        items.forEach(function (tile) {
          var cell = document.createElement("div");
          cell.className = "collage-cell";
          var usePh = !(tile.placeholder === false && tile.src);
          if (usePh) {
            appendPlaceholder(
              cell,
              tile.motif || "neutral",
              tile.alt || "",
            );
          } else {
            var img = document.createElement("img");
            img.src = tile.src;
            img.alt = tile.alt || "";
            img.loading = "lazy";
            img.decoding = "async";
            img.referrerPolicy = "no-referrer";
            img.width = 200;
            img.height = 200;
            wireImage(img, tile, cell);
            cell.appendChild(img);
          }
          container.appendChild(cell);
        });
      })
      .catch(function () {
        renderPlaceholderGrid(container);
      });
  }

  window.fairyNewsMountCollage = mountCollage;
})();
