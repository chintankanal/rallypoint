(() => {
  function targetImage(node) {
    const img = node?.closest?.('img');
    if (!img) return null;
    const source = (img.getAttribute('src') || '').toLowerCase();
    return source.includes('d7p14.jpg') ||
      source.includes('d7p15.jpg') ||
      source.includes('beale street - filmstrip.png') ? img : null;
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
    if (!img || activeImage === img) return;
    activeImage = img;
    previewImage.src = img.currentSrc || img.src;
    previewImage.alt = img.alt || '';
    previewCaption.textContent =
      img.closest('figure')?.querySelector('figcaption')?.textContent?.trim() || img.alt || '';
    preview.classList.add('is-visible');
    preview.setAttribute('aria-hidden', 'false');
  }

  function hide() {
    if (!activeImage) return;
    activeImage = null;
    preview.classList.remove('is-visible');
    preview.setAttribute('aria-hidden', 'true');
    previewImage.removeAttribute('src');
  }

  // Listen at document level so the behaviour also works for images added later.
  document.addEventListener('pointerover', (event) => {
    const img = targetImage(event.target);
    if (img && !img.contains(event.relatedTarget)) show(img);
  });
  document.addEventListener('pointerout', (event) => {
    const img = targetImage(event.target);
    if (img && !img.contains(event.relatedTarget)) hide();
  });

  document.addEventListener('focusin', (event) => show(targetImage(event.target)));
  document.addEventListener('focusout', (event) => {
    if (targetImage(event.target)) hide();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') hide();
  });

  document.querySelectorAll('img').forEach((img) => {
    if (targetImage(img)) {
      img.classList.add('photo-preview-enabled');
      img.tabIndex = 0;
      img.setAttribute('aria-label', 'Hover to view the complete photograph');
    }
  });
})();