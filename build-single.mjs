// 把 static_site/ 打包成一个可双击打开的单文件 HTML（离线兜底用）。
// 用法：node static_site/build-single.mjs
// 产物：static_site/单文件版/数改指导智能体-演示.html
//
// 做法：按 index.html 里真实的加载顺序，把 9 个 CSS、6 个 JS 全部内联，
// 图片与字体转 base64，数据用 window.__DATASETS 注入。
// 动态拼路径的图片（16 场景、首屏车间图）走 window.__ASSETS 查表。
import { readFileSync, writeFileSync, readdirSync, mkdirSync, statSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const SITE = dirname(fileURLToPath(import.meta.url));
const read = (p) => readFileSync(join(SITE, p), 'utf8');
const buf = (p) => readFileSync(join(SITE, p));
const posixDir = (p) => (p.includes('/') ? p.slice(0, p.lastIndexOf('/')) : '');
const posixJoin = (dir, rel) => (dir ? `${dir}/${rel}` : rel).replace(/\/\.\//g, '/');

const MIME = {
  '.webp': 'image/webp', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
  '.png': 'image/png', '.svg': 'image/svg+xml', '.woff2': 'font/woff2',
};

function dataURI(path) {
  const dot = path.lastIndexOf('.');
  if (dot < 0) return null;
  const mime = MIME[path.slice(dot).toLowerCase()];
  if (!mime) return null;
  return `data:${mime};base64,${buf(path).toString('base64')}`;
}

/* ------------------------------------------------------------ 1. 数据 */
const datasets = {};
for (const p of ['data/criteria.json', 'data/fixtures.json', 'data/policy-notes.json']) {
  datasets[p] = JSON.parse(read(p));
}
for (const f of readdirSync(join(SITE, 'data', 'samples'))) {
  if (!f.endsWith('.json')) continue;
  const body = JSON.parse(read(`data/samples/${f}`));
  datasets[`data/samples/${f}`] = body;
  datasets[`data/samples/${encodeURIComponent(f)}`] = body;
}

/* ------------------------------------------------------------ 2. 资源清单（按 index.html 顺序） */
let html = read('index.html').replace(/\r\n/g, '\n');
// 资源带 ?v=... 缓存版本号时，先归一化，后续标签匹配与内联都按无参路径处理
html = html.replace(/((?:href|src)="assets\/[^"?]+)\?v=[^"]*"/g, '$1"');
// 单文件离线版不携带子页，避免生成无法打开的相对链接。
html = html
  .replace(/href="highlights\.html"/g, 'href="#advisor"')
  .replace(/href="policy\.html"/g, 'href="#advisor"')
  .replace(/href="report\.html(?:\?[^"]*)?"/g, 'href="#advisor"')
  .replace(/href="ask\.html"/g, 'href="#advisor"');

const cssHrefs = [...html.matchAll(/<link rel="stylesheet" href="([^"]+)">/g)].map((m) => m[1]);
const jsSrcs = [...html.matchAll(/<script src="([^"]+)"><\/script>/g)].map((m) => m[1]);
if (!cssHrefs.length || !jsSrcs.includes('assets/engine.js') || !jsSrcs.includes('assets/app.js')) {
  console.error('index.html 的资源标签对不上（期望 <link rel="stylesheet"> 与 engine.js / app.js 的 script 标签）');
  process.exit(1);
}

/* ------------------------------------------------------------ 3. CSS 内联，字体与背景图转 base64 */
let cssBundle = '';
for (const href of cssHrefs) {
  let css = read(href).replace(/\r\n/g, '\n');
  css = css.replace(/url\((["']?)([^"')]+)\1\)/g, (whole, quote, ref) => {
    if (/^(data:|https?:|#)/.test(ref)) return whole;
    let uri = null;
    try { uri = dataURI(posixJoin(posixDir(href), ref)); } catch { return whole; }
    return uri ? `url("${uri}")` : whole;
  });
  cssBundle += `\n/* ===== ${href} ===== */\n${css}\n`;
}

/* ------------------------------------------------------------ 4. 图片表（JS 动态拼路径时查表） */
const assetMap = {};
const addAsset = (p) => {
  if (p in assetMap) return;
  try {
    const uri = dataURI(p);
    if (uri) assetMap[p] = uri;
  } catch { /* 缺图时保留原路径 */ }
};
for (const f of readdirSync(join(SITE, 'assets', 'img', 'scenes'))) addAsset(`assets/img/scenes/${f}`);
[
  'assets/img/hero-golden.jpg',
  'assets/img/method-aisle.webp',
  'assets/img/report-workbench.webp',
  'assets/img/scenario-cell.webp',
].forEach(addAsset);

/* ------------------------------------------------------------ 5. JS 内联 */
function patch(name, from, to, code) {
  if (!code.includes(from)) {
    console.error(`${name} 未匹配到预期代码，检查是否被改过：\n${from}`);
    process.exit(1);
  }
  return code.split(from).join(to);
}

function loadScript(src) {
  let code = read(src).replace(/\r\n/g, '\n');
  if (src === 'assets/app.js') {
    // 优先读内联数据，避开 file:// 下的 fetch 限制
    code = patch('assets/app.js', `  async function fetchJSON(url) {
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(\`\${url} → HTTP \${response.status}\`);
    return response.json();
  }`, `  async function fetchJSON(url) {
    if (window.__DATASETS && Object.prototype.hasOwnProperty.call(window.__DATASETS, url)) {
      return JSON.parse(JSON.stringify(window.__DATASETS[url]));
    }
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(\`\${url} → HTTP \${response.status}\`);
    return response.json();
  }`, code);
  }
  if (src === 'assets/scenario-atlas.js') {
    code = patch('assets/scenario-atlas.js',
      'const imagePath = (id) => `assets/img/scenes/${id.toLowerCase()}.webp`;',
      'const imagePath = (id) => { const key = `assets/img/scenes/${id.toLowerCase()}.webp`; return (window.__ASSETS && window.__ASSETS[key]) || key; };',
      code);
    // 单文件版没有 data/ 目录，判据直接读内联表
    code = patch('assets/scenario-atlas.js', `      const res = await fetch("data/criteria.json");
      if (!res.ok) throw new Error("criteria");
      const data = await res.json();`, `      const inline = window.__DATASETS && window.__DATASETS["data/criteria.json"];
      const res = inline ? { ok: true, json: async () => JSON.parse(JSON.stringify(inline)) } : await fetch("data/criteria.json");
      if (!res.ok) throw new Error("criteria");
      const data = await res.json();`, code);
  }
  if (src === 'assets/cinematic-scene.js') {
    code = patch('assets/cinematic-scene.js',
      'image.src = "assets/img/hero-golden.jpg";',
      'image.src = (window.__ASSETS && window.__ASSETS["assets/img/hero-golden.jpg"]) || "assets/img/hero-golden.jpg";',
      code);
  }
  return code;
}

/* ------------------------------------------------------------ 6. 组装 HTML */
const firstLink = `<link rel="stylesheet" href="${cssHrefs[0]}">`;
html = html.replace(firstLink, () => `<style>\n${cssBundle}\n</style>`);
for (const href of cssHrefs.slice(1)) {
  html = html.split(`<link rel="stylesheet" href="${href}">`).join('');
}

// 标签里写死的图片直接换 data URI
html = html.replace(/(data-image|src)="(assets\/img\/[^"]+)"/g, (whole, attr, ref) => {
  let uri = null;
  try { uri = dataURI(ref); } catch { return whole; }
  return uri ? `${attr}="${uri}"` : whole;
});

// 脚本逐个就地替换，顺序不变；第一段前面注入数据表与图片表
let injected = false;
for (const src of jsSrcs) {
  const tag = `<script src="${src}"></script>`;
  if (src.startsWith('http://') || src.startsWith('https://')) {
    html = html.split(tag).join('');
    continue;
  }
  const head = injected ? '' : `<script>window.__ASSETS = ${JSON.stringify(assetMap)};</script>\n<script>window.__DATASETS = ${JSON.stringify(datasets)};</script>\n`;
  html = html.split(tag).join(`${head}<script>\n${loadScript(src)}\n</script>`);
  injected = true;
}
if (html.includes('<script src="assets/')) {
  console.error('仍有脚本没内联，检查 index.html 的 script 标签是否被改写');
  process.exit(1);
}

/* ------------------------------------------------------------ 7. 输出 */
const outDir = join(SITE, '单文件版');
mkdirSync(outDir, { recursive: true });
const out = join(outDir, '数改指导智能体-演示.html');
writeFileSync(out, html, 'utf8');
console.log('输出', out, Math.round(statSync(out).size / 1024 / 1024 * 10) / 10 + 'MB');
