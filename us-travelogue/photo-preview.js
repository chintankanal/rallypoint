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


/* Temporary D8P9 framing tool; open the page with ?tune=D8P9. */
(() => {
  const params = new URLSearchParams(window.location.search);
  if (params.get('tune') !== 'D8P9') return;
  const figure = document.querySelector('#d8p9-photo');
  const img = figure?.querySelector('.d8p9-frame img');
  if (!figure || !img) return;

  const panel = document.createElement('div');
  panel.className = 'd8p9-tuning-panel';
  panel.innerHTML = '<div class="tuning-heading">Adjust D8P9 image position</div>' +
    '<label class="tuning-control"><span>Horizontal</span><input type="range" min="0" max="100" value="50" data-axis="x"><output>50%</output></label>' +
    '<label class="tuning-control"><span>Vertical</span><input type="range" min="0" max="100" value="50" data-axis="y"><output>50%</output></label>';
  figure.insertAdjacentElement('afterend', panel);

  const values = { x: 50, y: 50 };
  panel.querySelectorAll('input[type="range"]').forEach((slider) => {
    slider.addEventListener('input', () => {
      const axis = slider.dataset.axis;
      values[axis] = Number(slider.value);
      slider.nextElementSibling.value = slider.value + '%';
      img.style.objectPosition = values.x + '% ' + values.y + '%';
    });
  });
})();
