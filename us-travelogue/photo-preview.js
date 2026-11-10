(() => {
  const targets = [...document.querySelectorAll('.story .photo img')].filter((img) =>
    /D7P1[45]\.jpg(?:[?#].*)?$/i.test(img.getAttribute('src') || '')
  );
  if (!targets.length) return;

  const preview = document.createElement('div');
  preview.className = 'photo-hover-preview';
  preview.setAttribute('aria-hidden', 'true');
  preview.innerHTML = '<figure><img alt=""><figcaption></figcaption></figure>';
  document.body.appendChild(preview);

  const previewImage = preview.querySelector('img');
  const previewCaption = preview.querySelector('figcaption');

  function show(img) {
    previewImage.src = img.currentSrc || img.src;
    previewImage.alt = img.alt || '';
    previewCaption.textContent =
      img.closest('figure')?.querySelector('figcaption')?.textContent?.trim() || img.alt || '';
    preview.classList.add('is-visible');
    preview.setAttribute('aria-hidden', 'false');
  }

  function hide() {
    preview.classList.remove('is-visible');
    preview.setAttribute('aria-hidden', 'true');
    previewImage.removeAttribute('src');
  }

  targets.forEach((img) => {
    img.classList.add('photo-preview-enabled');
    img.addEventListener('pointerenter', (event) => {
      if (event.pointerType === 'mouse' || event.pointerType === 'pen') show(img);
    });
    img.addEventListener('pointerleave', hide);
    img.addEventListener('focus', () => show(img));
    img.addEventListener('blur', hide);
  });
})();