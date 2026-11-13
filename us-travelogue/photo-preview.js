(() => {
  function isTarget(img) {
    if (!img || img.tagName !== 'IMG') return false;
    const source = (img.getAttribute('src') || '').toLowerCase();
    return source.includes('d7p14.jpg') ||
      source.includes('d7p15.jpg') ||
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

/* Temporary D8P5 framing tool. Controls appear only on the private tuning URL. */
(() => {
  const params = new URLSearchParams(window.location.search);
  if (params.get('tune') !== 'D8P5') return;
  const figure = document.getElementById('d8p5-photo');
  if (!figure) return;
  const frame = figure.querySelector('.d8p5-frame img');
  const panel = figure.querySelector('.d8p5-position-controls');
  if (!frame || !panel) return;
  panel.hidden = false;
  const sliders = panel.querySelectorAll('input[type="range"]');
  const values = { x: 50, y: 50 };
  const apply = () => {
    frame.style.objectPosition = '50% ' + values.y + '%';
    frame.style.transform = 'translateX(' + ((50 - values.x) * 0.15) + '%) scale(1.15)';
    sliders.forEach((slider) => {
      const output = slider.parentElement.querySelector('output');
      output.textContent = values[slider.dataset.axis] + '%';
    });
  };
  sliders.forEach((slider) => {
    slider.addEventListener('input', () => {
      values[slider.dataset.axis] = Number(slider.value);
      apply();
    });
  });
  apply();
})();
