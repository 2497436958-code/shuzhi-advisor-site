(() => {
  const nav = document.querySelector('.topnav');
  const bar = document.querySelector('.topbar-inner');
  if (!nav || !bar) return;
  nav.classList.add('staggered-menu-panel');
  nav.setAttribute('id', 'staggered-menu-panel');
  nav.setAttribute('aria-hidden', 'true');
  const pre = document.createElement('div'); pre.className = 'sm-prelayers'; pre.setAttribute('aria-hidden','true');
  ['#B497CF','#5227FF'].forEach(color => { const layer=document.createElement('div'); layer.className='sm-prelayer'; layer.style.background=color; pre.appendChild(layer); });
  bar.appendChild(pre);
  [...nav.querySelectorAll('a')].forEach((a, i) => { a.classList.add('sm-panel-item'); a.dataset.index=String(i+1); });
  const button = document.createElement('button');
  button.className = 'nav-toggle'; button.type = 'button'; button.setAttribute('aria-label','打开导航菜单'); button.setAttribute('aria-expanded','false');
  button.textContent = 'menu+'; bar.appendChild(button);
  const setOpen = (open) => {
    nav.classList.toggle('is-open', open); nav.setAttribute('aria-hidden', String(!open)); button.setAttribute('aria-expanded', String(open)); button.setAttribute('aria-label', open ? '关闭导航菜单' : '打开导航菜单'); button.textContent = open ? 'close×' : 'menu+';
    if (window.gsap && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      const tl = window.gsap.timeline({defaults:{ease:'power4.out'}});
      tl.fromTo(nav, {xPercent:8, autoAlpha:0}, {xPercent:0, autoAlpha:1, duration:.55})
        .fromTo([...nav.querySelectorAll('a')], {yPercent:140, rotation:8, autoAlpha:0}, {yPercent:0, rotation:0, autoAlpha:1, duration:.7, stagger:.07}, '-=.25');
    }
  };
  button.addEventListener('click', () => setOpen(!nav.classList.contains('is-open')));
  nav.addEventListener('click', (e) => { if (e.target.closest('a')) setOpen(false); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') setOpen(false); });
})();
