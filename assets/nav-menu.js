(() => {
  const nav = document.querySelector('.topnav');
  const bar = document.querySelector('.topbar-inner');
  if (!nav || !bar) return;
  const button = document.createElement('button');
  button.className = 'nav-toggle'; button.type = 'button'; button.setAttribute('aria-label','打开导航菜单'); button.setAttribute('aria-expanded','false');
  button.innerHTML = '<span></span><span></span><span></span>'; bar.appendChild(button);
  const lines = [...button.children];
  const setOpen = (open) => {
    nav.classList.toggle('is-open', open); button.setAttribute('aria-expanded', String(open)); button.setAttribute('aria-label', open ? '关闭导航菜单' : '打开导航菜单');
    if (window.gsap && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      window.gsap.to(lines[0], {rotation: open ? 45 : 0, y: open ? 6.5 : 0, duration:.22, ease:'power2.out'});
      window.gsap.to(lines[1], {autoAlpha: open ? 0 : 1, duration:.16});
      window.gsap.to(lines[2], {rotation: open ? -45 : 0, y: open ? -6.5 : 0, duration:.22, ease:'power2.out'});
      window.gsap.fromTo(nav, {y:-8, autoAlpha:0}, {y:0, autoAlpha:1, duration:.25, ease:'power2.out', overwrite:'auto'});
    }
  };
  button.addEventListener('click', () => setOpen(!nav.classList.contains('is-open')));
  nav.addEventListener('click', (e) => { if (e.target.closest('a')) setOpen(false); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') setOpen(false); });
})();
