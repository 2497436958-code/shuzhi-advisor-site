/* Browser capability adaptation; no fingerprint collection or requests. */
(() => {
  const root = document.documentElement;
  const touch = window.matchMedia('(pointer: coarse)');
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const connection = navigator.connection;
  function update() {
    const width = window.innerWidth;
    root.dataset.viewport = width <= 720 ? 'compact' : width <= 1080 ? 'medium' : 'wide';
    root.dataset.input = touch.matches ? 'touch' : 'pointer';
    root.dataset.effects = motion.matches || connection?.saveData ? 'reduced' : 'full';
    root.style.setProperty('--app-height', `${window.visualViewport?.height || window.innerHeight}px`);
    window.dispatchEvent(new CustomEvent('advisor:environmentchange'));
  }
  for (const query of [touch, motion]) {
    if (query.addEventListener) query.addEventListener('change', update);
    else if (query.addListener) query.addListener(update);
  }
  window.addEventListener('resize', update, { passive: true });
  window.visualViewport?.addEventListener('resize', update, { passive: true });
  connection?.addEventListener?.('change', update);
  update();
})();
