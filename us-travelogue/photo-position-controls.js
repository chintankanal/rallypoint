(() => {
  "use strict";
  const targets = new Set(["D7P5.JPG", "D6P15.JPG", "D6P11.JPG"]);
  const savedPositions = {
    "D7P5.JPG": { h: 50, v: 20 },
    "D6P15.JPG": { h: 50, v: 19 },
    "D6P11.JPG": { h: 50, v: 37 }
  };

  function addSlider(figure, image, axis, initialValue) {
    const row = document.createElement("div");
    row.className = "photo-adjust-row";

    const label = document.createElement("label");
    const id = "crop-" + image.getAttribute("src").split("/").pop().replace(/[^a-z0-9]/gi, "-") + "-" + axis;
    label.htmlFor = id;
    label.textContent = axis === "h" ? "Horizontal" : "Vertical";

    const slider = document.createElement("input");
    slider.type = "range";
    slider.id = id;
    slider.min = "0";
    slider.max = "100";
    slider.step = "1";
    slider.value = String(initialValue);
    slider.setAttribute("aria-label", label.textContent + " image crop position");

    const value = document.createElement("output");
    value.className = "photo-adjust-value";
    value.htmlFor = id;
    value.textContent = initialValue + "%";

    slider.addEventListener("input", () => {
      const h = figure.querySelector('[data-crop-axis="h"]')?.value ?? "50";
      const v = figure.querySelector('[data-crop-axis="v"]')?.value ?? "50";
      slider.dataset.cropAxis = axis;
      image.style.objectPosition = h + "% " + v + "%";
      value.textContent = slider.value + "%";
    });
    slider.dataset.cropAxis = axis;
    row.append(label, slider, value);
    return row;
  }

  function addControls(image, filename) {
    const figure = image.closest("figure.photo");
    if (!figure || figure.querySelector(".photo-adjust-controls")) return;

    // Keep the original image and its fixed CSS crop frame. Only change
    // object-position, exactly as with the previously approved D7P21 framing.
    image.style.objectFit = "cover";
    const controls = document.createElement("div");
    controls.className = "photo-adjust-controls";
    controls.setAttribute("role", "group");
    controls.setAttribute("aria-label", "Adjust photo crop");

    const hint = document.createElement("p");
    hint.className = "photo-adjust-hint";
    hint.textContent = "Move the crop window across the original photo. H50 V50 is centred.";
    controls.append(
      hint,
      addSlider(figure, image, "h", 50),
      addSlider(figure, image, "v", 50)
    );
    figure.appendChild(controls);
    image.style.objectPosition = savedPositions[filename].h + "% " + savedPositions[filename].v + "%";
  }

  function initialise() {
    document.querySelectorAll("figure.photo img").forEach((image) => {
      const filename = decodeURIComponent(image.getAttribute("src").split("/").pop()).toUpperCase();
      if (targets.has(filename)) addControls(image, filename);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialise);
  } else {
    initialise();
  }
})();
