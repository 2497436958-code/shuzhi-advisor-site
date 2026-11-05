/* 前端页面冒烟测试（零依赖，Node 内置能力即可）。
 *
 * 为什么需要它：知识库页面与评测报告页面都是纯前端渲染，CI 里没有浏览器，
 * 只靠 `node --check app.js` 只能查语法，查不出运行时报错与字段错位。
 * 这里用最小 DOM 桩 + fetch 桩把 app.js 的启动流程真跑一遍，检查：
 *   1. app.js 请求的所有元素 id 都能在 index.html 里找到；
 *   2. 知识库区块能渲染出四库统计、四个库块、条目与原文链接；
 *   3. 检索与筛选会发出正确请求，并把结果回填到页面；
 *   4. 评测报告区块能渲染出样本层分列、七行指标表、四组对照与四组消融，
 *      且"真实层 0 家"如实出现在页面上。
 *
 * 用法：node scripts/check_frontend_pages.mjs
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const read = (p) => readFileSync(join(ROOT, p), "utf8");

/* ------------------------------------------------------------ 最小 DOM 桩 */

class TextNode {
  constructor(text) { this.nodeType = 3; this._text = String(text); }
  get textContent() { return this._text; }
  set textContent(v) { this._text = String(v); }
}

class El {
  constructor(tag) {
    this.nodeType = 1;
    this.tagName = String(tag).toUpperCase();
    this.children = [];
    this.attributes = {};
    this.style = { setProperty() {} };
    const attributes = this.attributes;
    const self = this;
    this._reflecting = false;
    this.dataset = new Proxy({}, {
      set(target, prop, value) {
        target[prop] = value;
        if (!self._reflecting) {
          self._reflecting = true;
          self.setAttribute("data-" + String(prop).replace(/[A-Z]/g, (c) => "-" + c.toLowerCase()), value);
          self._reflecting = false;
        }
        return true;
      },
      get(target, prop) { return target[prop]; },
    });
    this.className = "";
    this.value = "";
    this.checked = false;
    this.hidden = false;
    this.disabled = false;
    this.id = "";
    this.offsetHeight = 40;
    this.innerWidth = 1280;
    this.listeners = new Map();
    this.parentNode = null;
    this._ownText = "";
  }
  get textContent() {
    if (!this.children.length) return this._ownText;
    return this.children.map((child) => child.textContent).join("");
  }
  set textContent(value) {
    this.children = [];
    this._ownText = value === null || value === undefined ? "" : String(value);
  }
  appendChild(child) {
    this.children.push(child);
    child.parentNode = this;
    return child;
  }
  insertBefore(child, reference) {
    const index = this.children.indexOf(reference);
    this.children.splice(index < 0 ? this.children.length : index, 0, child);
    child.parentNode = this;
    return child;
  }
  removeChild(child) {
    this.children = this.children.filter((item) => item !== child);
    return child;
  }
  remove() {
    if (this.parentNode) this.parentNode.removeChild(this);
  }
  setAttribute(name, value) {
    this.attributes[name] = String(value);
    if (name === "id") this.id = String(value);
    if (name.startsWith("data-") && !this._reflecting) {
      this._reflecting = true;
      this.dataset[name.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = String(value);
      this._reflecting = false;
    }
  }
  getAttribute(name) { return name in this.attributes ? this.attributes[name] : null; }
  hasAttribute(name) { return name in this.attributes; }
  addEventListener(type, handler) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    this.listeners.get(type).push(handler);
  }
  removeEventListener(type, handler) {
    const list = this.listeners.get(type) || [];
    this.listeners.set(type, list.filter((item) => item !== handler));
  }
  dispatch(type, event = {}) {
    const payload = { type, target: this, preventDefault() {}, ...event };
    for (const handler of this.listeners.get(type) || []) handler(payload);
  }
  scrollIntoView() {}
  focus() {}
  matchesSimple(simple) {
    let tag = null, id = null, checked = false;
    const classes = [];
    const attrs = [];
    const pattern = /(^[a-zA-Z][\w-]*)|#([\w-]+)|\.([\w-]+)|\[([\w-]+)(?:=["']?([^"'\]]*)["']?)?\]|:checked/g;
    let match;
    while ((match = pattern.exec(simple)) !== null) {
      if (match[1]) tag = match[1].toUpperCase();
      else if (match[2]) id = match[2];
      else if (match[3]) classes.push(match[3]);
      else if (match[4]) attrs.push([match[4], match[5]]);
      else if (match[0] === ":checked") checked = true;
    }
    if (tag && this.tagName !== tag) return false;
    if (id && this.id !== id) return false;
    for (const cls of classes) {
      if (!String(this.className).split(/\s+/).includes(cls)) return false;
    }
    for (const [name, value] of attrs) {
      const actual = this.getAttribute(name);
      if (actual === null) return false;
      if (value !== undefined && actual !== value) return false;
    }
    if (checked && !this.checked) return false;
    return true;
  }
  walk(visit) {
    for (const child of this.children) {
      if (child.nodeType !== 1) continue;
      visit(child);
      child.walk(visit);
    }
  }
  querySelectorAll(selector) {
    const parts = selector.trim().split(/\s+/);
    const last = parts[parts.length - 1];
    const ancestors = parts.slice(0, -1).reverse();
    const found = [];
    this.walk((node) => {
      if (!node.matchesSimple(last)) return;
      if (!ancestors.length) { found.push(node); return; }
      let cursor = node.parentNode;
      let index = 0;
      while (cursor && cursor.nodeType === 1 && index < ancestors.length) {
        if (cursor.matchesSimple(ancestors[index])) index += 1;
        cursor = cursor.parentNode;
      }
      if (index === ancestors.length) found.push(node);
    });
    return found;
  }
  querySelector(selector) {
    const found = this.querySelectorAll(selector)[0];
    if (found) return found;
    // 桩里没有真实子节点时，按选择器补一个占位元素，
    // 让"取子节点再设属性"这类写法能跑完（真实 DOM 里这些都是存在的）。
    const simple = selector.trim().split(/\s+/).pop();
    const tagMatch = /^[a-zA-Z][\w-]*/.exec(simple);
    const stub = new El(tagMatch ? tagMatch[0] : "div");
    const idMatch = /#([\w-]+)/.exec(simple);
    if (idMatch) stub.setAttribute("id", idMatch[1]);
    this.appendChild(stub);
    return stub;
  }
}

const html = read("index.html");
const ids = [...html.matchAll(/id="([^"]+)"/g)].map((m) => m[1]);
const root = new El("html");
const body = new El("body");
root.appendChild(body);
const registry = new Map();
for (const id of ids) {
  const node = new El("div");
  node.setAttribute("id", id);
  registry.set(id, node);
  body.appendChild(node);
}
const missingIds = new Set();

const document = {
  documentElement: root,
  body,
  listeners: new Map(),
  createElement: (tag) => new El(tag),
  createTextNode: (text) => new TextNode(text),
  addEventListener(type, handler) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    this.listeners.get(type).push(handler);
  },
  querySelector(selector) {
    const trimmed = selector.trim();
    if (trimmed.startsWith("#") && !/[ >]/.test(trimmed)) {
      const id = trimmed.slice(1);
      const node = registry.get(id);
      if (node) return node;
      missingIds.add(id);
      const stub = new El("div");
      stub.setAttribute("id", id);
      registry.set(id, stub);
      body.appendChild(stub);
      return stub;
    }
    return root.querySelector(selector);
  },
  querySelectorAll(selector) {
    return root.querySelectorAll(selector);
  },
};

/* ------------------------------------------------------------ fetch 桩 */

const fixture = JSON.parse(read("scripts/fixtures/knowledge_api.json"));
const criteria = JSON.parse(read("precomputed/criteria.json"));
const fixtures = JSON.parse(read("precomputed/fixtures.json"));
const evaluation = JSON.parse(read("data/evaluation/report.json"));
const calls = [];

function respond(body) {
  return { ok: true, status: 200, json: async () => body };
}

const fetchStub = async (url) => {
  calls.push(url);
  const path = url.split("?")[0];
  const query = url.includes("?") ? url.slice(url.indexOf("?") + 1) : "";
  if (path.endsWith("api/health")) return respond({ status: "ok", mode: "online" });
  if (path.endsWith("api/criteria")) return respond(criteria);
  if (path.endsWith("api/fixtures")) return respond(fixtures);
  if (path.endsWith("api/scenario_evidence")) return respond({ available: true, judgments: {} });
  if (path.endsWith("api/knowledge/stats")) return respond(fixture.stats);
  if (path.endsWith("api/evaluation/report")) return respond(evaluation);
  if (path.endsWith("data/evaluation/report.json")) return respond(evaluation);
  for (const key of ["policy", "cases", "papers", "patents"]) {
    if (path.endsWith("api/knowledge/" + key)) return respond(fixture[key]);
  }
  throw new Error("未预期的请求：" + url + (query ? " ?" + query : ""));
};

/* ------------------------------------------------------------ 跑 app.js */

const sandbox = {
  document,
  window: { innerWidth: 1280, addEventListener() {} },
  fetch: fetchStub,
  console,
  URLSearchParams,
  setTimeout,
  clearTimeout,
  Promise,
  Math,
  Date,
  JSON,
  Object,
  Array,
  String,
  Number,
  Boolean,
  Error,
};
sandbox.window.document = document;
sandbox.globalThis = sandbox;

vm.createContext(sandbox);
vm.runInContext(read("app.js"), sandbox, { filename: "app.js" });

const bootPromise = (document.listeners.get("DOMContentLoaded") || []).map((fn) => fn());

async function waitFor(predicate, label) {
  for (let i = 0; i < 200; i += 1) {
    if (predicate()) return true;
    await new Promise((resolve) => setTimeout(resolve, 1));
  }
  throw new Error("等待超时：" + label);
}

await waitFor(
  () => registry.get("knowledge-body") && registry.get("knowledge-body").children.length > 1,
  "知识库区块渲染"
);

await Promise.all(bootPromise);

/* ------------------------------------------------------------ 断言 */

const failures = [];
const check = (condition, message) => {
  if (!condition) failures.push(message);
};

const knowledgeBody = registry.get("knowledge-body");
const statCards = knowledgeBody.querySelectorAll(".kb-stat");
const libBlocks = knowledgeBody.querySelectorAll(".kb-lib");

check(statCards.length === 4, `四库统计卡片应为 4 个，实际 ${statCards.length}`);
check(libBlocks.length === 4, `知识库区块应为 4 个，实际 ${libBlocks.length}`);

for (const key of ["policy", "cases", "papers", "patents"]) {
  const block = knowledgeBody.querySelector('[data-kb="' + key + '"]');
  check(Boolean(block), `缺少 ${key} 库区块`);
  if (!block) continue;
  const count = block.querySelector(".kb-count");
  check(Boolean(count) && count.textContent.length > 0, `${key} 缺少命中计数`);
  const items = block.querySelectorAll(".kb-list .kb-item");
  check(items.length > 0, `${key} 没有渲染出条目`);
  const links = block.querySelectorAll("a");
  check(links.length > 0, `${key} 没有渲染出原文链接`);
}

const patentBlock = knowledgeBody.querySelector('[data-kb="patents"]');
if (patentBlock) {
  const entry = patentBlock.querySelector(".kb-entry");
  check(Boolean(entry) && entry.textContent.includes("检索入口"), "专利库缺少官方检索入口");
}

const papersBlock = knowledgeBody.querySelector('[data-kb="papers"]');
if (papersBlock) {
  const select = papersBlock.querySelector(".kb-select");
  const options = select ? select.querySelectorAll("option") : [];
  check(options.length > 1, "论文库的类型筛选下拉没有选项（分面维度可能写错）");
}

// 检索：改关键词 → 应发出带 q 的请求并回填计数
const before = calls.length;
const policyBlock = knowledgeBody.querySelector('[data-kb="policy"]');
const search = policyBlock.querySelector(".kb-search");
search.value = "奖补";
search.dispatch("change");
await waitFor(() => calls.length > before, "检索请求发出");
await waitFor(
  () => {
    const count = policyBlock.querySelector(".kb-count");
    return count && (count.textContent.includes("命中") || count.textContent.includes("共"));
  },
  "检索结果回填"
);
check(
  calls.slice(before).some((url) => url.includes("api/knowledge/policy") && url.includes("q=%E5%A5%96%E8%A1%A5")),
  "检索请求缺少 q 参数：" + calls.slice(before).join(" | ")
);

// 筛选：选一个角色 → 应发出带 role 的请求
const roleSelect = policyBlock.querySelector(".kb-select");
const roleValue = roleSelect.querySelectorAll("option")[1]?.getAttribute("value");
if (roleValue) {
  const beforeFilter = calls.length;
  roleSelect.value = roleValue;
  roleSelect.dispatch("change");
  await waitFor(() => calls.length > beforeFilter, "筛选请求发出");
  check(
    calls.slice(beforeFilter).some((url) => url.includes("role=")),
    "筛选请求缺少 role 参数"
  );
}

/* ---- 评测报告页面 ---- */

const evalBody = registry.get("evaluation-body");
check(Boolean(evalBody) && evalBody.children.length > 1, "评测报告区块没有渲染出来");

const evalTables = evalBody ? evalBody.querySelectorAll("table") : [];
check(evalTables.length === 3, `评测报告应有 3 张表（指标 / 对照 / 消融），实际 ${evalTables.length}`);

const metricRows = evalTables[0] ? evalTables[0].querySelectorAll("tbody tr") : [];
check(metricRows.length === 7, `指标表应有 7 行，实际 ${metricRows.length}`);

const statusTags = evalBody ? evalBody.querySelectorAll("table tbody tr td .tag") : [];
const statuses = statusTags.map((tag) => tag.textContent);
check(
  statuses.includes("达标") || statuses.includes("未达标") || statuses.includes("不可测"),
  "指标表没有渲染出结论标签",
);

const controlRows = evalTables[1] ? evalTables[1].querySelectorAll("tbody tr") : [];
check(controlRows.length === 4, `对照表应有 4 行，实际 ${controlRows.length}`);

const ablationRows = evalTables[2] ? evalTables[2].querySelectorAll("tbody tr") : [];
check(ablationRows.length === 4, `消融表应有 4 行，实际 ${ablationRows.length}`);

const evalText = evalBody ? evalBody.textContent : "";
check(evalText.includes("真实层"), "评测报告没有显示样本层分列");
check(
  evalText.includes(String(evaluation.layers.real.count)),
  "评测报告没有如实显示真实层的家数",
);
check(
  evalText.includes(evaluation.verdicts.T043_ranking_top3.status),
  "评测报告没有如实显示 T043 的结论状态",
);

/* ---- 方法页：静态内容守卫（口径、公式与合规声明不能被悄悄删掉） ---- */

const indexHtml = read("index.html");
const methodStart = indexHtml.indexOf('id="method-panel"');
check(methodStart >= 0, "index.html 里没有方法页区块");
if (methodStart >= 0) {
  const methodHtml = indexHtml.slice(methodStart, indexHtml.indexOf("</main>", methodStart));
  const required = [
    ["官方判据出处", "工信厅企业〔2024〕56 号"],
    ["权重链乘口径", "一级指标权重 × 二级指标权重 × 采集项权重"],
    ["多选计分公式", "选中数 × 100 ÷ (总选项数 − 1)"],
    ["官方口径缺口披露", "官方评分逻辑未覆盖，按等距线性兜底并显式披露"],
    ["约束性场景数", "10 个是官方标注的约束性场景"],
    ["AP1 判据", "采集项 2 设备数字化率 ≥(40%,60%]"],
    ["AP2 判据", "采集项 5 覆盖绝大部分业务环节或全覆盖"],
    ["AP3 判据", "采集项 4 自动采集覆盖环节数 ≥6"],
    ["AP4 判据", "采集项 11 数字化投入占营业额 ≥(20%,40%]"],
    ["ROI 公式", "ROI = 预期可量化成效收益 ÷ 投入成本"],
    ["优先级公式", "P = (等级跃迁分 + 关联成效改善) ÷ 投入成本"],
    ["排序取下界", "排序取<strong>下界</strong>"],
    ["补贴不入分子", "补贴不进分子"],
    ["ROI 同系数折算", "分子分母必须同系数"],
    ["弹性未公开案例支撑", "未被公开案例支撑</strong>，只用于排序"],
    ["真实层合成层不混写", "真实层与合成层不混写"],
    ["不承诺补贴获批", "不承诺补贴获批"],
    ["不承接申报代理", "不承接申报代理"],
    ["不把论文结论当定论", "不把论文的单一结论写成定论"],
    ["不把合成样本写成真实企业", "不把合成样本写成真实企业"],
    ["真实层家数如实写", "真实层目前 <strong>0 家</strong>"],
    ["路径表覆盖范围", "路径表目前只覆盖 9 个场景"],
    ["可复算入口", "scripts/compare_precomputed.py"],
  ];
  for (const [label, snippet] of required) {
    check(methodHtml.includes(snippet), `方法页缺少「${label}」：${snippet}`);
  }
  const sectionCount = (methodHtml.match(/class="kb-lib"/g) || []).length;
  check(sectionCount === 9, `方法页应有 9 个小节，实际 ${sectionCount}`);
}

if (missingIds.size) {
  failures.push("app.js 请求了 index.html 里不存在的 id：" + [...missingIds].join("、"));
}

if (failures.length) {
  console.error("知识库页面冒烟测试未通过：");
  for (const failure of failures) console.error("  ✗ " + failure);
  process.exit(1);
}

console.log("前端页面冒烟测试通过");
console.log(`  统计卡片 ${statCards.length} 个，库块 ${libBlocks.length} 个`);
console.log(`  渲染条目 ${knowledgeBody.querySelectorAll(".kb-item").length} 条`);
console.log(`  评测报告：指标表 ${metricRows.length} 行、对照 ${controlRows.length} 组、消融 ${ablationRows.length} 组`);
console.log(`  方法页：内容守卫 23 条口径与合规声明齐全`);
console.log(`  fetch 调用 ${calls.length} 次，缺失 id ${missingIds.size} 个`);
