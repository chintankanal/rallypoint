(() => {
  "use strict";
  const targets = new Set(["D7P5.JPG", "D6P15.JPG", "D6P11.JPG"]);
  const positions = new Map();

  function applyPosition(image, wrapper, position) {
    // A small, fixed zoom creates real horizontal and vertical travel while
    // preserving the image frame and the surrounding page layout.
    const zoom = 112;
    const travel = 100 - zoom;
    image.style.left = (travel * position.h / 100) + "%";
    image.style.top = (travel * position.v / 100) + "%";
    const readout = wrapper.querySelector(".photo-position-readout");
    if (readout) readout.textContent = "H" + position.h + " V" + position.v;
  }

  function addControls(image, filename) {
    const figure = image.closest("figure.photo");
    if (!figure || image.parentElement.classList.contains("photo-adjust-wrap")) return;

    const isPair = figure.classList.contains("photo-pair");
    const wrapper = document.createElement("div");
    wrapper.className = "photo-adjust-wrap" + (isPair ? " photo-adjust-pair" : " photo-adjust-feature");
    if (!isPair) {
      const setAspect = () => {
        if (image.naturalWidth && image.naturalHeight) {
          wrapper.style.aspectRatio = image.naturalWidth + " / " + image.naturalHeight;
        }
      };
      setAspect();
      if (!image.complete) image.addEventListener("load", setAspect, { once: true });
    }

    image.parentNode.insertBefore(wrapper, image);
    wrapper.appendChild(image);
    image.classList.add("photo-adjust-image");

    const position = { h: 50, v: 50 };
    positions.set(filename, position);

    const controls = document.createElement("div");
    controls.className = "photo-position-controls";
    controls.setAttribute("role", "group");
    controls.setAttribute("aria-label", "Adjust " + filename + " photo position");

    const makeButton = (direction, symbol, label) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "photo-position-arrow arrow-" + direction;
      button.textContent = symbol;
      button.setAttribute("aria-label", label);
      button.addEventListener("click", () => {
        // The arrows move the visible picture, not the crop anchor.
        if (direction === "left") position.h = Math.min(100, position.h + 1);
        if (direction === "right") position.h = Math.max(0, position.h - 1);
        if (direction === "up") position.v = Math.min(100, position.v + 1);
        if (direction === "down") position.v = Math.max(0, position.v - 1);
        applyPosition(image, wrapper, position);
      });
      return button;
    };

    controls.appendChild(makeButton("up", "↑", "Move photo up"));
    controls.appendChild(makeButton("left", "←", "Move photo left"));
    const readout = document.createElement("span");
    readout.className = "photo-position-readout";
    readout.textContent = "H50 V50";
    controls.appendChild(readout);
    controls.appendChild(makeButton("right", "→", "Move photo right"));
    controls.appendChild(makeButton("down", "↓", "Move photo down"));
    wrapper.appendChild(controls);
    applyPosition(image, wrapper, position);
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