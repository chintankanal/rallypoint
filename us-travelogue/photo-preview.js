(() => {
 const imgs=[...document.querySelectorAll('.story .photo img')].filter(i=>/(?:^|\/)D7P1[45]\.jpg(?:\?|$)/i.test(i.getAttribute('src')||''));
 if(!imgs.length)return;
 const hover=matchMedia('(hover: hover) and (pointer: fine)').matches;
 const preview=document.createElement('div');preview.className='photo-hover-preview';preview.setAttribute('aria-hidden','true');preview.innerHTML='<div class="photo-hover-preview__content"><img alt=""><p></p></div>';document.body.append(preview);
 const pi=preview.querySelector('img'),pc=preview.querySelector('p');
 const dialog=document.createElement('dialog');dialog.className='photo-lightbox';dialog.innerHTML='<button class="photo-lightbox__close" type="button" aria-label="Close image">×</button><figure><img alt=""><figcaption></figcaption></figure>';document.body.append(dialog);
 const li=dialog.querySelector('img'),lc=dialog.querySelector('figcaption');
 const src=i=>i.currentSrc||i.src,cap=i=>i.closest('figure')?.querySelector('figcaption')?.textContent?.trim()||i.alt||'';
 const show=i=>{pi.src=src(i);pi.alt=i.alt||'';pc.textContent=cap(i);preview.classList.add('is-visible');preview.setAttribute('aria-hidden','false')};
 const hide=()=>{preview.classList.remove('is-visible');preview.setAttribute('aria-hidden','true')};
 const open=i=>{hide();li.src=src(i);li.alt=i.alt||'';lc.textContent=cap(i);if(!dialog.open)dialog.showModal()};
 imgs.forEach(i=>{i.classList.add('photo-preview-enabled');i.tabIndex=0;i.setAttribute('role','button');i.setAttribute('aria-label','Preview full-size image: '+(i.alt||'travel photograph'));if(hover){i.addEventListener('mouseenter',()=>show(i));i.addEventListener('mouseleave',hide);i.addEventListener('focus',()=>show(i));i.addEventListener('blur',hide)}i.addEventListener('click',()=>open(i));i.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();open(i)}})});
 dialog.querySelector('.photo-lightbox__close').addEventListener('click',()=>dialog.close());dialog.addEventListener('click',e=>{if(e.target===dialog)dialog.close()});dialog.addEventListener('close',()=>li.removeAttribute('src'));
})();