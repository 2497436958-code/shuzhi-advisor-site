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
      const tl = window.gsap.timeline({defaults:{ease:'power4.out'}});
      tl.fromTo(nav, {xPercent:8, autoAlpha:0}, {xPercent:0, autoAlpha:1, duration:.55})
        .fromTo([...nav.querySelectorAll('a')], {yPercent:140, rotation:8, autoAlpha:0}, {yPercent:0, rotation:0, autoAlpha:1, duration:.7, stagger:.07}, '-=.25');
      window.gsap.to(lines[0], {rotation: open ? 45 : 0, y: open ? 6.5 : 0, duration:.22, ease:'power2.out'});
      window.gsap.to(lines[1], {autoAlpha: open ? 0 : 1, duration:.16});
      window.gsap.to(lines[2], {rotation: open ? -45 : 0, y: open ? -6.5 : 0, duration:.22, ease:'power2.out'});
    }
  };
  button.addEventListener('click', () => setOpen(!nav.classList.contains('is-open')));
  nav.addEventListener('click', (e) => { if (e.target.closest('a')) setOpen(false); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') setOpen(false); });
})();
