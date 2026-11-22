(() => {
  function isTarget(img) {
    if (!img || img.tagName !== 'IMG') return false;
    const source = (img.getAttribute('src') || '').toLowerCase();
    return source.includes('d2p1.jpg') ||
      source.includes('d7p14.jpg') ||
      source.includes('d7p15.jpg') ||
      source.includes('d8p22.jpg') ||
      source.includes('d8p23.jpg') ||
      source.includes('beale street - filmstrip.png');
  }

  const preview = document.createElement('div');
  preview.id = 'selected-photo-preview';
  preview.className = 'photo-hover-preview';
  preview.setAttribute('aria-hidden', 'true');
  preview.innerHTML = '<figure><img alt=""><figcaption></figcaption></figure>';
  document.body.appendChild(preview);

  const previewImage = preview.querySelector('img');
  const previewCaption = preview.querySelector('figcaption');
  let activeImage = null;
  let zoomLevel = 1;
  const minZoom = 1;
  const maxZoom = 3;
  const zoomStep = 0.2;

  function applyZoom() {
    previewImage.style.transform = `scale(${zoomLevel})`;
    previewImage.style.transformOrigin = 'center center';
  }

  function show(img) {
    if (!isTarget(img)) return;
    activeImage = img;
    zoomLevel = 1;
    applyZoom();
    previewImage.src = img.currentSrc || img.src;
    previewImage.alt = img.alt || '';
    previewCaption.textContent =
      img.closest('figure')?.querySelector('figcaption')?.textContent?.trim() || img.alt || '';
    preview.classList.add('is-visible');
    preview.setAttribute('aria-hidden', 'false');
  }

  function hide() {
    activeImage = null;
    zoomLevel = 1;
    previewImage.style.transform = 'scale(1)';
    preview.classList.remove('is-visible');
    preview.setAttribute('aria-hidden', 'true');
    previewImage.removeAttribute('src');
  }

  // Keep the proven D7P14/D7P15 mouse-hover behaviour unchanged.
  document.addEventListener('mouseover', (event) => {
    const img = event.target.closest?.('.story .photo img');
    if (isTarget(img) && img !== activeImage) show(img);
  });
  document.addEventListener('mouseout', (event) => {
    const img = event.target.closest?.('.story .photo img');
    if (isTarget(img) && !img.contains(event.relatedTarget)) hide();
  });

  document.addEventListener('focusin', (event) => {
    const img = event.target.closest?.('.story .photo img');
    if (isTarget(img)) show(img);
  });
  document.addEventListener('focusout', (event) => {
    const img = event.target.closest?.('.story .photo img');
    if (isTarget(img)) hide();
  });

  // Resolve the hovered source image at wheel time. The preview overlay can
  // change mouseover/mouseout targets, so do not rely only on activeImage.
  document.addEventListener('wheel', (event) => {
    const underPointer = document.elementFromPoint(event.clientX, event.clientY);
    const hoveredImage = underPointer?.closest?.('.story .photo img');
    const targetImage = isTarget(hoveredImage) ? hoveredImage : activeImage;
    if (!targetImage || !isTarget(targetImage)) return;

    if (activeImage !== targetImage || !preview.classList.contains('is-visible')) {
      show(targetImage);
    }

    event.preventDefault();
    if (event.deltaY < 0) zoomLevel = Math.min(maxZoom, zoomLevel + zoomStep);
    else if (event.deltaY > 0) zoomLevel = Math.max(minZoom, zoomLevel - zoomStep);
    applyZoom();
  }, { capture: true, passive: false });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') hide();
  });

  document.querySelectorAll('.story .photo img').forEach((img) => {
    if (isTarget(img)) {
      img.classList.add('photo-preview-enabled');
      img.tabIndex = 0;
      img.setAttribute('aria-label', 'Hover to view the complete photograph');
    }
  });
})();


