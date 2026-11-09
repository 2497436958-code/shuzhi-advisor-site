import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const source = readFileSync(new URL('assets/environment.js', import.meta.url), 'utf8');
function boot(width, { touch = false, reduced = false, saveData = false } = {}) {
  const listeners = {};
  const root = { dataset: {}, style: { setProperty() {} } };
  const media = new Map();
  const window = { innerWidth: width, innerHeight: 800,
    matchMedia(query) {
      if (!media.has(query)) media.set(query, { matches: query.includes('reduced-motion') ? reduced : touch, addEventListener(type, fn) { listeners[query] = fn; } });
      return media.get(query);
    },
    addEventListener(type, fn) { listeners[type] = fn; },
    dispatchEvent() {},
  };
  const navigator = { connection: { saveData, addEventListener(type, fn) { listeners.connection = fn; } } };
  vm.runInNewContext(source, { window, navigator, document: { documentElement: root }, CustomEvent: class {} });
  return { root, window, navigator, listeners, media };
}
const phone = boot(390, { touch: true });
assert.equal(phone.root.dataset.viewport, 'compact');
assert.equal(phone.root.dataset.input, 'touch');
assert.equal(phone.root.dataset.effects, 'full');
const desktop = boot(1440);
assert.equal(desktop.root.dataset.viewport, 'wide');
assert.equal(desktop.root.dataset.input, 'pointer');
desktop.window.innerWidth = 820; desktop.listeners.resize();
assert.equal(desktop.root.dataset.viewport, 'medium');
assert.equal(boot(390, { reduced: true }).root.dataset.effects, 'reduced');
assert.equal(boot(1440, { saveData: true }).root.dataset.effects, 'reduced');
desktop.navigator.connection.saveData = true; desktop.listeners.connection();
assert.equal(desktop.root.dataset.effects, 'reduced');
desktop.navigator.connection.saveData = false; desktop.listeners.connection();
assert.equal(desktop.root.dataset.effects, 'full');
for (const page of ['index', 'report', 'highlights', 'ask']) {
  const html = readFileSync(new URL(`${page}.html`, import.meta.url), 'utf8');
  assert.ok(html.includes('assets/environment.js'), `${page}: missing detector`);
  assert.ok(html.includes('assets/environment.css'), `${page}: missing styles`);
}
console.log('Environment adaptation: 4 pages, viewport changes, touch, reduced motion and data saving passed.');
