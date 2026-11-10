(() => {
  function isTarget(img) {
    if (!img || img.tagName !== 'IMG') return false;
    const source = (img.getAttribute('src') || '').toLowerCase();
    return source.includes('d7p14.jpg') || source.includes('d7p15.jpg');
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

  function show(img) {
    if (!isTarget(img)) return;
    activeImage = img;
    previewImage.src = img.currentSrc || img.src;
    previewImage.alt = img.alt || '';
    previewCaption.textContent =
      img.closest('figure')?.querySelector('figcaption')?.textContent?.trim() || img.alt || '';
    preview.classList.add('is-visible');
    preview.setAttribute('aria-hidden', 'false');
  }

  function hide() {
    activeImage = null;
    preview.classList.remove('is-visible');
    preview.setAttribute('aria-hidden', 'true');
    previewImage.removeAttribute('src');
  }

  // Delegated mouse events avoid relying on individual image listeners.
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