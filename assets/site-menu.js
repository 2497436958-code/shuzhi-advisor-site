(() => {
  const nav = document.querySelector('.topnav');
  const shell = document.querySelector('.topbar-inner');
  if (!nav || !shell) return;
  const toggle = document.createElement('button');
  toggle.type = 'button';
  toggle.className = 'site-menu-toggle';
  toggle.setAttribute('aria-expanded', 'false');
  toggle.setAttribute('aria-controls', 'site-navigation');
  toggle.innerHTML = '<span>目录</span><i aria-hidden="true"></i>';
  nav.id = 'site-navigation';
  shell.appendChild(toggle);
  const close = () => { nav.classList.remove('is-open'); toggle.setAttribute('aria-expanded','false'); };
  toggle.addEventListener('click', () => {
    const open = !nav.classList.contains('is-open');
    nav.classList.toggle('is-open', open);
    toggle.setAttribute('aria-expanded', String(open));
  });
  nav.addEventListener('click', event => { if (event.target.closest('a')) close(); });
  document.addEventListener('keydown', event => { if (event.key === 'Escape') close(); });
  document.addEventListener('click', event => { if (!shell.contains(event.target)) close(); });
  window.addEventListener('resize', () => { if (window.innerWidth > 900) close(); });
})();
