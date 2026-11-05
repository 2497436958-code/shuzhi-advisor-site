/* 数改指导智能体 · 演示站前端
 *
 * 无构建步骤：原生 ES2018 + DOM API，不引入任何第三方库。
 *
 * 三件事：
 * 1. 从 /api/criteria 拿 15 个采集项与 16 个场景的**官方原文**，据此渲染表单；
 * 2. 把表单提交给 /api/evaluate，拿回符合 result.schema.json 的四段式结果并渲染；
 * 3. /api/health 失败时切离线模式：读 precomputed/*.json，明示"预计算结果（非实时计算）"。
 */
(() => {
  "use strict";

  const $ = (sel) => document.querySelector(sel);

  const state = {
    mode: "checking",        // online | offline
    criteria: null,
    fixtures: [],
    result: null,
    profile: null,
    evidenceAvailable: false,   // 模型判定的官方原文引文是否已接入
  };

  /* ------------------------------------------------------------ DOM 辅助 */

  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    if (attrs) {
      for (const [key, value] of Object.entries(attrs)) {
        if (value === null || value === undefined || value === false) continue;
        if (key === "class") node.className = value;
        else if (key === "text") node.textContent = value;
        else if (key === "html") node.innerHTML = value;
        else if (key.startsWith("on") && typeof value === "function") {
          node.addEventListener(key.slice(2), value);
        } else if (value === true) node.setAttribute(key, "");
        else node.setAttribute(key, value);
      }
    }
    for (const child of [].concat(children || [])) {
      if (child === null || child === undefined || child === false) continue;
      node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
    }
    return node;
  }

  const num = (value, digits) =>
    typeof value === "number" && isFinite(value) ? value.toFixed(digits) : "—";

  /* 一组"标签 + 取值"，标签在上、取值在下，避免网格把两者拆散 */
  function pair(label, value) {
    return el("div", { class: "pair" }, [
      el("span", { class: "pair-label", text: label }),
      el("span", { class: "pair-value", text: value }),
    ]);
  }

  async function fetchJSON(url) {
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`${url} → HTTP ${response.status}`);
    return response.json();
  }

  /* ------------------------------------------------------------ 模式检测 */

  function setModeChip() {
    const chip = $("#mode-chip");
    if (state.mode === "online") {
      chip.dataset.state = "online";
      chip.textContent = "实时计算（后端在线）";
    } else if (state.mode === "offline") {
      chip.dataset.state = "offline";
      chip.textContent = "预计算结果（非实时计算）";
    } else {
      chip.dataset.state = "checking";
      chip.textContent = "正在检测服务…";
    }
  }

  async function boot() {
    setModeChip();
    try {
      await fetchJSON("api/health");
      state.mode = "online";
    } catch (err) {
      state.mode = "offline";
    }
    setModeChip();

    try {
      if (state.mode === "online") {
        state.criteria = await fetchJSON("api/criteria");
        const listing = await fetchJSON("api/fixtures");
        state.fixtures = listing.fixtures || [];
      } else {
        state.criteria = await fetchJSON("precomputed/criteria.json");
        const listing = await fetchJSON("precomputed/fixtures.json");
        state.fixtures = listing.fixtures || [];
      }
    } catch (err) {
      $("#form-status").textContent = "加载判据失败：" + err.message;
      return;
    }

    try {
      const evidence = state.mode === "online"
        ? await fetchJSON("api/scenario_evidence")
        : await fetchJSON("precomputed/scenario_judgments.json");
      state.evidenceAvailable = state.mode === "online"
        ? Boolean(evidence.available)
        : Boolean(evidence && Object.keys(evidence).length);
    } catch (err) {
      state.evidenceAvailable = false;
    }

    renderForm();
    renderFixturePicker();
    bindActions();
    loadKnowledge();
  }

  /* ------------------------------------------------------------ 表单渲染 */

  function renderForm() {
    const indicatorsHost = $("#indicator-groups");
    indicatorsHost.textContent = "";
    const byPrimary = new Map();
    for (const indicator of state.criteria.indicators) {
      if (!byPrimary.has(indicator.primary)) byPrimary.set(indicator.primary, []);
      byPrimary.get(indicator.primary).push(indicator);
    }

    let index = 0;
    for (const [primary, items] of byPrimary) {
      const weight = items[0].primary_weight;
      const group = el("details", { class: "group", open: index === 0 });
      group.appendChild(el("summary", {}, [
        `${primary}`,
        el("span", { class: "count", text: `${items.length} 个采集项 · 一级指标权重 ${(weight * 100).toFixed(0)}%` }),
      ]));
      const body = el("div", { class: "group-body" });
      for (const indicator of items) body.appendChild(renderIndicator(indicator));
      group.appendChild(body);
      indicatorsHost.appendChild(group);
      index += 1;
    }

    const scenariosHost = $("#scenario-groups");
    scenariosHost.textContent = "";
    const scenarioPrimary = new Map();
    for (const scenario of state.criteria.scenarios) {
      if (!scenarioPrimary.has(scenario.primary)) scenarioPrimary.set(scenario.primary, []);
      scenarioPrimary.get(scenario.primary).push(scenario);
    }
    index = 0;
    for (const [primary, scenarios] of scenarioPrimary) {
      const group = el("details", { class: "group", open: index === 0 });
      const constraintCount = scenarios.filter((s) => s.constraint).length;
      group.appendChild(el("summary", {}, [
        primary,
        el("span", {
          class: "count",
          text: `${scenarios.length} 个场景 · 约束性 ${constraintCount} 个 · ` +
            (state.evidenceAvailable ? "官方原文引文已接入" : "引文待接入"),
        }),
      ]));
      const body = el("div", { class: "group-body" });
      for (const scenario of scenarios) body.appendChild(renderScenario(scenario));
      group.appendChild(body);
      scenariosHost.appendChild(group);
      index += 1;
    }
  }

  function renderIndicator(indicator) {
    const wrap = el("div", { class: "item", "data-indicator": indicator.id });
    wrap.appendChild(el("div", { class: "item-head" }, [
      el("span", { class: "item-no", text: String(indicator.id) }),
      el("span", { class: "item-title", text: indicator.title }),
      el("span", {
        class: "item-meta",
        text: `${indicator.option_type} · 权重链 ${(indicator.chain_weight * 100).toFixed(1)}%` +
          (indicator.official_rule_gap ? " · 官方评分规则未覆盖（等距线性兜底）" : ""),
      }),
    ]));

    const body = el("div", { class: "item-body" });
    if (indicator.option_type === "单选") {
      const select = el("select", {
        "data-role": "single",
        "data-indicator": indicator.id,
        id: `indicator-${indicator.id}`,
      });
      select.appendChild(el("option", { value: "", text: "— 请选择 —" }));
      for (const option of indicator.options) {
        select.appendChild(el("option", { value: option, text: option }));
      }
      body.appendChild(select);
    } else {
      const list = el("div", { class: "opts" });
      for (const option of indicator.options) {
        const input = el("input", {
          type: "checkbox",
          value: option,
          "data-role": "multi",
          "data-indicator": indicator.id,
          id: `indicator-${indicator.id}-${indicator.options.indexOf(option)}`,
        });
        input.addEventListener("change", () => onMultiChange(input));
        list.appendChild(el("label", { class: "opt", for: `indicator-${indicator.id}-${indicator.options.indexOf(option)}` }, [
          input,
          el("span", { text: option }),
        ]));
      }
      body.appendChild(list);
    }
    wrap.appendChild(body);
    return wrap;
  }

  function onMultiChange(input) {
    const indicator = state.criteria.indicators.find((i) => i.id === Number(input.dataset.indicator));
    if (!indicator) return;
    const boxes = () => Array.from(
      document.querySelectorAll(`input[data-role="multi"][data-indicator="${indicator.id}"]`)
    );
    if (input.value === "无") {
      // 官方规则：选"无"得 0 分，且不能与其他选项并存
      if (input.checked) boxes().forEach((box) => { if (box !== input) box.checked = false; });
    } else if (input.checked) {
      boxes().forEach((box) => { if (box.value === "无") box.checked = false; });
    }
  }

  const scenarioEmptyHint = "尚未选择等级。官方要求：应在完全满足低级场景的所有基本要求之后，方可进阶至更高一级场景的判定。";

  function updateScenarioHint(scenarioId, level) {
    const scenario = (state.criteria?.scenarios || []).find((item) => item.id === scenarioId);
    const desc = document.querySelector(`.level-desc[data-scenario="${scenarioId}"]`);
    if (!scenario || !desc) return;
    if (level) {
      desc.className = "level-desc";
      desc.textContent = `${level} 级：${scenario.levels[String(level)]}`;
    } else {
      desc.className = "level-desc none";
      desc.textContent = scenarioEmptyHint;
    }
  }

  function renderScenario(scenario) {
    const wrap = el("div", { class: "item", "data-scenario": scenario.id });
    wrap.appendChild(el("div", { class: "item-head" }, [
      el("span", { class: "item-no", text: scenario.id }),
      el("span", { class: "item-title", text: scenario.name }),
      el("span", {
        class: "item-meta",
        text: `${scenario.primary} · ${scenario.constraint ? "约束性场景（官方标 *）" : "指导性场景"}`,
      }),
    ]));

    const desc = el("p", { class: "level-desc none", "data-scenario": scenario.id, text: scenarioEmptyHint });
    const radios = el("div", { class: "level-radios" });
    for (const level of [1, 2, 3, 4]) {
      const input = el("input", {
        type: "radio",
        name: `scenario-${scenario.id}`,
        value: String(level),
        id: `scenario-${scenario.id}-${level}`,
        "data-role": "scenario",
        "data-scenario": scenario.id,
      });
      input.addEventListener("change", () => {
        updateScenarioHint(scenario.id, level);
      });
      radios.appendChild(el("label", { class: "level-radio", for: `scenario-${scenario.id}-${level}` }, [
        input,
        el("span", { text: `${level} 级` }),
      ]));
    }

    const official = el("details", { class: "official-levels" });
    official.appendChild(el("summary", { text: "查看官方四级判定要求（逐字原文）" }));
    const dl = el("dl");
    for (const level of [1, 2, 3, 4]) {
      dl.appendChild(el("dt", { text: `${level} 级` }));
      dl.appendChild(el("dd", { text: scenario.levels[String(level)] }));
    }
    official.appendChild(dl);

    wrap.appendChild(el("div", { class: "item-body levels-row" }, [radios]));
    wrap.appendChild(desc);
    wrap.appendChild(official);
    return wrap;
  }

  function renderFixturePicker() {
    const host = $("#fixture-picker-host");
    if (!host) return;
    host.textContent = "";
    const select = el("select", { id: "fixture-select" });
    for (const fixture of state.fixtures) {
      select.appendChild(el("option", {
        value: fixture.name,
        text: `${fixture.label}（${fixture.total_score} 分 · ${fixture.level_name}）`,
      }));
    }
    select.addEventListener("change", () => { state.selectedFixture = select.value; });
    state.selectedFixture = state.fixtures.length ? state.fixtures[0].name : null;
    host.appendChild(select);
    host.appendChild(el("button", {
      type: "button",
      class: "btn",
      text: "载入并评测",
      onclick: () => { if (state.selectedFixture) loadFixture(state.selectedFixture); },
    }));
  }

  /* ------------------------------------------------------------ 表单读写 */

  function applyProfile(profile) {
    state.profile = profile;
    $("#f-name").value = profile.name || "";
    $("#f-revenue").value = profile.revenue_wan ?? "";
    $("#f-spend").value = profile.digital_spend_wan ?? "";
    $("#f-energy").value = profile.energy_wan ?? "";
    $("#f-headcount").value = profile.headcount ?? "";
    $("#f-cost").value = profile.cost_wan ?? "";
    $("#f-province").value = profile.province ?? "";

    for (const indicator of state.criteria.indicators) {
      const selected = profile.answers[String(indicator.id)] || [];
      if (indicator.option_type === "单选") {
        const select = document.querySelector(`select[data-role="single"][data-indicator="${indicator.id}"]`);
        if (select) select.value = selected[0] || "";
      } else {
        document.querySelectorAll(`input[data-role="multi"][data-indicator="${indicator.id}"]`)
          .forEach((box) => { box.checked = selected.includes(box.value); });
      }
    }
    for (const scenario of state.criteria.scenarios) {
      document.querySelectorAll(
        `input[data-role="scenario"][data-scenario="${scenario.id}"]`
      ).forEach((radio) => { radio.checked = false; });
      const level = profile.scenario_levels[scenario.id] || 0;
      const input = document.querySelector(
        `input[data-role="scenario"][data-scenario="${scenario.id}"][value="${level}"]`
      );
      if (input) input.checked = true;
      updateScenarioHint(scenario.id, level);
    }
  }

  function collectProfile() {
    const answers = {};
    for (const indicator of state.criteria.indicators) {
      if (indicator.option_type === "单选") {
        const select = document.querySelector(`select[data-role="single"][data-indicator="${indicator.id}"]`);
        const value = select ? select.value : "";
        if (value) answers[String(indicator.id)] = [value];
      } else {
        const picked = Array.from(
          document.querySelectorAll(`input[data-role="multi"][data-indicator="${indicator.id}"]:checked`)
        ).map((box) => box.value);
        if (picked.length) answers[String(indicator.id)] = picked;
      }
    }
    const scenarioLevels = {};
    for (const scenario of state.criteria.scenarios) {
      const checked = document.querySelector(`input[data-role="scenario"][data-scenario="${scenario.id}"]:checked`);
      if (checked) scenarioLevels[scenario.id] = Number(checked.value);
    }
    const number = (id) => {
      const raw = $(id).value.trim();
      if (raw === "") return null;
      const value = Number(raw);
      return isFinite(value) ? value : null;
    };
    return {
      name: $("#f-name").value.trim() || "未命名企业",
      provenance: "用户现场填写",
      answers,
      scenario_levels: scenarioLevels,
      revenue_wan: number("#f-revenue"),
      digital_spend_wan: number("#f-spend"),
      energy_wan: number("#f-energy"),
      headcount: number("#f-headcount"),
      cost_wan: number("#f-cost"),
      province: $("#f-province").value.trim(),
    };
  }

  /* ------------------------------------------------------------ 评测 */

  async function runEvaluation() {
    const status = $("#form-status");
    const button = $("#btn-evaluate");
    const missingIndicators = [];
    for (const indicator of state.criteria.indicators) {
      const answered = indicator.option_type === "单选"
        ? Boolean(document.querySelector(`select[data-role="single"][data-indicator="${indicator.id}"]`).value)
        : Boolean(document.querySelector(`input[data-role="multi"][data-indicator="${indicator.id}"]:checked`));
      if (!answered) missingIndicators.push(indicator.id);
    }
    const missingScenarios = state.criteria.scenarios
      .filter((scenario) => !document.querySelector(`input[data-role="scenario"][data-scenario="${scenario.id}"]:checked`))
      .map((scenario) => scenario.id);
    if (missingIndicators.length || missingScenarios.length) {
      const parts = [];
      if (missingIndicators.length) parts.push(`采集项 ${missingIndicators.join("、")}`);
      if (missingScenarios.length) parts.push(`场景 ${missingScenarios.join("、")}`);
      status.className = "form-status error";
      status.textContent = `还有 ${missingIndicators.length + missingScenarios.length} 个必填项未作答（${parts.join("；")}）。官方要求 15 个采集项与 16 个场景等级全部作答才能定级。`;
      return;
    }
    if (state.mode !== "online") {
      status.className = "form-status error";
      status.textContent = "离线模式：后端不可用，无法实时评测。请在上方选择示例企业查看预计算结果。";
      return;
    }

    status.className = "form-status";
    status.textContent = "正在计算…";
    button.disabled = true;
    try {
      const response = await fetch("api/evaluate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(collectProfile()),
      });
      const payload = await response.json();
      if (!response.ok) {
        status.className = "form-status error";
        status.textContent = typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail);
        return;
      }
      status.textContent = "";
      renderResult(payload, { precomputed: false });
    } catch (err) {
      status.className = "form-status error";
      status.textContent = "评测请求失败：" + err.message;
    } finally {
      button.disabled = false;
    }
  }

  async function loadFixture(name) {
    const status = $("#form-status");
    status.className = "form-status";
    status.textContent = "正在载入…";
    try {
      if (state.mode === "online") {
        const data = await fetchJSON(`api/fixtures/${encodeURIComponent(name)}`);
        applyProfile(data.profile);
        await runEvaluation();
      } else {
        const data = await fetchJSON(`precomputed/${encodeURIComponent(name)}`);
        applyProfile(data.profile);
        status.textContent = "";
        renderResult(data.result, { precomputed: true });
      }
    } catch (err) {
      status.className = "form-status error";
      status.textContent = "载入失败：" + err.message;
    }
  }

  /* ------------------------------------------------------------ 结果渲染 */

  function renderResult(result, options) {
    state.result = result;
    $("#output-panel").hidden = false;
    $("#summary-empty").hidden = true;
    $("#summary-body").hidden = false;

    const evaluation = result.evaluation || {};
    $("#score-value").textContent = num(evaluation.total_score, 1);
    $("#level-value").textContent = evaluation.level_name || "无等级";

    const chips = $("#level-chips");
    chips.textContent = "";
    for (const judgement of result.level_judgement || []) {
      chips.appendChild(el("span", {
        class: "level-chip " + (judgement.satisfied ? "ok" : "miss"),
        title: judgement.note,
      }, [
        el("span", { class: "lv", text: judgement.level + " 级" }),
        el("span", { text: judgement.name }),
        el("span", { class: "mk", text: judgement.satisfied ? "达标" : "未达标" }),
      ]));
    }

    const gaps = evaluation.rule_gaps || [];
    const gapBlock = $("#gap-block");
    if (gaps.length) {
      gapBlock.hidden = false;
      $("#gap-toggle").textContent = `${gaps.length} 项待披露 · 点击查看`;
      const list = $("#gap-list");
      list.textContent = "";
      for (const gap of gaps) list.appendChild(el("li", { text: gap }));
    } else {
      gapBlock.hidden = true;
    }

    const host = $("#output-panel");
    const oldNotice = host.querySelector(".notice");
    if (oldNotice) oldNotice.remove();
    if (options.precomputed) {
      const notice = el("div", { class: "notice" }, [
        el("b", { text: "当前为预计算结果（非实时计算）。" }),
        " 后端不可用，以下结论来自构建时预先生成的预计算文件（precomputed/" +
        "），不是本次现场计算的结果。",
      ]);
      host.insertBefore(notice, host.firstChild.nextSibling);
    }

    renderDiagnosis(result);
    renderPathway(result);
    renderRanking(result);
    renderPolicy(result);
    renderAssumptions(result);
  }

  function renderDiagnosis(result) {
    const host = $("#out-diagnosis");
    host.textContent = "";
    const entries = result.diagnosis || [];
    if (!entries.length) {
      host.appendChild(el("div", { class: "placeholder" }, [
        el("b", { text: "未发现结构性瓶颈" }),
        "按官方采集项与场景等级，未命中四类投入无效模式，也未发现约束性场景断层。",
      ]));
      return;
    }
    for (const entry of entries) {
      const card = el("article", { class: "card" });
      card.appendChild(el("div", { class: "card-head" }, [
        el("span", { class: "tag tag-accent", text: entry.bottleneck_type || "瓶颈" }),
        el("h4", { text: entry.bottleneck }),
      ]));
      const body = el("div", { class: "card-body" });
      body.appendChild(el("p", { class: "card-quote", text: entry.evidence }));
      const meta = el("ul", { class: "meta-list" });
      meta.appendChild(el("li", {}, ["命中采集项：", el("b", { text: (entry.hit_items || []).join("、") || "—（场景层不直接计分）" })]));
      meta.appendChild(el("li", {}, ["命中场景：", el("b", { text: (entry.hit_scenarios || []).join("、") || "—" })]));
      if (typeof entry.max_score_gain === "number") {
        meta.appendChild(el("li", {}, ["相关采集项可提升分数上限：", el("b", { text: num(entry.max_score_gain, 2) + " 分" })]));
      }
      if (entry.case_ref) meta.appendChild(el("li", {}, ["案例编号：", el("b", { text: entry.case_ref })]));
      meta.appendChild(el("li", {}, ["判据性质：", el("b", { text: entry.basis_kind || "官方口径" })]));
      body.appendChild(meta);
      body.appendChild(evidenceDetails(entry.evidence_refs));
      card.appendChild(body);
      host.appendChild(card);
    }
    host.appendChild(renderScenarioEvidence(result));
  }

  /* 场景等级判定的官方原文引文 */
  function renderScenarioEvidence(result) {
    const scenarios = result.scenario_results || [];
    const withQuote = scenarios.filter((s) => s.judgment && s.judgment.quote);
    const block = el("details", { class: "evidence-block" });
    block.appendChild(el("summary", {
      text: `场景等级判定依据（官方原文引文 · ${withQuote.length}/${scenarios.length} 个场景）`,
    }));
    const cards = el("div", { class: "ev-cards" });
    if (!withQuote.length) {
      cards.appendChild(el("div", { class: "placeholder" }, [
        el("b", { text: "引文待接入" }),
        "模型判定的官方原文引文尚未离线跑好（预期文件：src/advisor/web/precomputed/scenario_judgments.json）。" +
        "当前展示的仍是确定性规则基线判定，模型不会被调用。",
      ]));
    }
    for (const scenario of withQuote) {
      const judgment = scenario.judgment;
      const card = el("div", { class: "ev-card", "data-kind": "场景" });
      card.appendChild(el("div", { class: "ev-head" }, [
        el("span", { class: "ev-ref", text: scenario.id }),
        el("span", { class: "ev-title", text: `${scenario.name} · ${judgment.level} 级` }),
        el("span", {
          class: "tag " + (judgment.source === "rule_baseline" ? "tag-warn" : "tag-accent"),
          text: judgment.source === "rule_baseline"
            ? "规则基线"
            : judgment.source === "submitted" ? "用户自评" : "模型判定",
        }),
        judgment.citation_ok ? el("span", { class: "tag tag-good", text: "引文已校验" }) : null,
      ]));
      card.appendChild(el("p", { class: "ev-quote", text: judgment.quote }));
      if (judgment.note) card.appendChild(el("p", { class: "ev-note", text: judgment.note }));
      card.appendChild(el("p", { class: "ev-src" }, [
        el("span", { text: "工信厅企业〔2024〕56 号 附件（二）数字化经营应用场景等级判定表" }),
      ]));
      cards.appendChild(card);
    }
    block.appendChild(cards);
    return block;
  }

  function evidenceDetails(refs) {
    const details = el("details", { class: "evidence" });
    const list = refs || [];
    details.appendChild(el("summary", {
      text: list.length ? `看依据（${list.length} 条 · 官方原文与出处）` : "看依据",
    }));
    const cards = el("div", { class: "ev-cards" });
    for (const ref of list) {
      const card = el("div", { class: "ev-card", "data-kind": ref.kind });
      card.appendChild(el("div", { class: "ev-head" }, [
        el("span", { class: "ev-ref", text: ref.ref }),
        el("span", { class: "ev-title", text: ref.title }),
      ]));
      card.appendChild(el("p", { class: "ev-quote", text: ref.quote }));
      if (ref.note) card.appendChild(el("p", { class: "ev-note", text: ref.note }));
      const source = el("p", { class: "ev-src" });
      source.appendChild(el("span", { text: ref.doc || "—" }));
      if (ref.url) {
        source.appendChild(document.createTextNode(" "));
        source.appendChild(el("a", {
          href: ref.url,
          target: "_blank",
          rel: "noopener",
          text: "打开原文 ↗",
        }));
      }
      card.appendChild(source);
      cards.appendChild(card);
    }
    details.appendChild(cards);
    return details;
  }

  function renderPathway(result) {
    const host = $("#out-pathway");
    host.textContent = "";
    const steps = result.pathway || [];
    if (!steps.length) {
      host.appendChild(el("div", { class: "placeholder" }, [
        el("b", { text: "本次没有需要推进的改造步骤" }),
        "在当前起点上，官方口径下没有必须先做的动作。",
      ]));
      return;
    }
    const list = el("div", { class: "steps" });
    for (const step of steps) {
      const box = el("article", { class: "step" });
      box.appendChild(el("div", { class: "step-head" }, [
        el("span", { class: "step-no", text: "第 " + step.step + " 步" }),
        el("span", { class: "step-action", text: step.action }),
      ]));
      const grid = el("div", { class: "step-grid" });
      grid.appendChild(pair("目标场景", `${step.target_scenario}${step.target_items && step.target_items.length
        ? `（关联采集项 ${step.target_items.join("、")}）` : ""}`));
      grid.appendChild(pair("投入区间", `${num(step.cost_range[0], 1)} — ${num(step.cost_range[1], 1)} 万元/年（估算）`));
      grid.appendChild(pair("前置依赖", step.depends_on && step.depends_on.length
        ? `第 ${step.depends_on.join("、第 ")} 步` : "无"));
      box.appendChild(grid);

      if (step.expected && step.expected.length) {
        const expected = el("div", { class: "step-grid step-grid-expected" });
        for (const metric of step.expected) {
          expected.appendChild(pair(`预期成效 · 采集项 ${metric.indicator}`, `${metric.metric}：${metric.expect}`));
        }
        box.appendChild(expected);
      }

      if (step.path_ref) {
        box.appendChild(el("div", { class: "step-cause" }, [
          el("b", { text: `归因 ${step.path_ref}${step.confidence ? "（置信度 " + step.confidence + "，待人工审校）" : ""}` }),
          step.symptom ? el("span", { text: "症状：" + step.symptom }) : null,
          step.root_cause ? el("span", { text: "根因：" + step.root_cause }) : null,
          step.basis ? el("span", { class: "ev-note", text: "依据：" + step.basis }) : null,
        ]));
      }

      box.appendChild(el("div", { class: "step-accept" }, [
        el("b", { text: "验收口径" }),
        step.acceptance,
      ]));
      box.appendChild(evidenceDetails(step.evidence_refs));
      list.appendChild(box);
    }
    host.appendChild(list);
  }

  function renderRanking(result) {
    const host = $("#out-ranking");
    host.textContent = "";

    const ranking = result.ranking || [];
    const assumptions = result.roi_assumptions || {};
    if (ranking.length) {
      const wrap = el("div", { class: "table-wrap" });
      const table = el("table");
      table.appendChild(el("caption", {
        text: `${assumptions.formula || "ROI = 预期成效收益 ÷ 投入成本"}；${assumptions.conservatism || "排序取下界"}。` +
          "投入区间为估算，成效弹性未被公开案例支撑，只用于排序，不作为结论数。",
      }));
      const thead = el("thead");
      thead.appendChild(el("tr", {}, [
        el("th", { text: "排名" }),
        el("th", { text: "改造动作" }),
        el("th", { text: "目标场景" }),
        el("th", { text: "投入（万元/年）" }),
        el("th", { text: "预期年化收益（万元）" }),
        el("th", { text: "ROI 区间" }),
        el("th", { text: "受阻" }),
        el("th", { text: "依据" }),
      ]));
      table.appendChild(thead);

      const tbody = el("tbody");
      for (const row of ranking) {
        const tr = el("tr");
        tr.appendChild(el("td", { class: "num" }, [el("span", { class: "rank-no", text: "#" + row.rank })]));
        tr.appendChild(el("td", { text: row.name || row.action_id }));
        tr.appendChild(el("td", { text: row.target_scenario || "—" }));
        tr.appendChild(el("td", { class: "num", text: `${num(row.cost_range[0], 1)} — ${num(row.cost_range[1], 1)}` }));
        tr.appendChild(el("td", { class: "num", text: `${num(row.benefit_range[0], 1)} — ${num(row.benefit_range[1], 1)}` }));
        tr.appendChild(el("td", { class: "num", text: `${num(row.roi_low, 3)} — ${num(row.roi_high, 3)}` }));
        tr.appendChild(el("td", { text: row.blocked_by && row.blocked_by.length ? row.blocked_by.join("、") : "—" }));
        const last = el("td");
        last.appendChild(evidenceDetails(row.evidence_refs));
        tr.appendChild(last);
        tbody.appendChild(tr);
      }
      table.appendChild(tbody);
      wrap.appendChild(table);
      host.appendChild(wrap);

      host.appendChild(el("p", { class: "hint" , text:
        `路径段按前置依赖排序（先底座后场景），排序段按 ROI 下界排序，两者口径不同。` +
        `逐项扰动 40% 时整体排序翻转率 ${assumptions.flip_rate ?? "—"}。` }));
    } else {
      host.appendChild(el("div", { class: "placeholder" }, [
        el("b", { text: "没有可量化的投入产出排序" }),
        "本次动作均无可直接量化的成效收益（或尚未形成动作），建议直接看路径段与「不建议做」清单。",
      ]));
    }

    const doNot = result.do_not || [];
    const box = el("div", { class: "donot" });
    box.appendChild(el("h4", { text: "不建议做清单（命中投入无效模式）" }));
    if (!doNot.length) {
      box.appendChild(el("p", { text: "未命中四类典型投入无效模式。" }));
    } else {
      const list = el("ul");
      for (const item of doNot) {
        const li = el("li");
        li.appendChild(el("div", { class: "card-head" }, [
          el("span", { class: "tag tag-bad", text: item.pattern_id }),
          el("strong", { text: item.name }),
        ]));
        li.appendChild(el("p", { text: item.evidence }));
        li.appendChild(el("p", { class: "hint", text: "判据：" + item.basis }));
        li.appendChild(el("p", { class: "hint", text: item.basis_kind || "" }));
        li.appendChild(evidenceDetails(item.evidence_refs));
        list.appendChild(li);
      }
      box.appendChild(list);
    }
    host.appendChild(box);
  }

  function renderPolicy(result) {
    const host = $("#out-policy");
    host.textContent = "";
    const status = result.policy_notes_status || {};
    const notes = result.policy_notes || [];
    if (notes.length) {
      for (const note of notes) {
        const card = el("div", { class: "card" });
        card.appendChild(el("div", { class: "card-head" }, [
          el("span", { class: "tag tag-accent", text: note.role || "政策" }),
          el("h4", { text: note.doc }),
        ]));
        const meta = el("ul", { class: "meta-list" });
        if (note.window) meta.appendChild(el("li", {}, ["窗口期：", el("b", { text: note.window })]));
        if (note.issuer) meta.appendChild(el("li", {}, ["发文：", el("b", { text: note.issuer })]));
        if (note.covers_step) {
          meta.appendChild(el("li", {}, ["对应路径第 ", el("b", { text: String(note.covers_step) }), " 步"]));
        }
        if (note.used_where) meta.appendChild(el("li", {}, ["用在哪里：", el("b", { text: note.used_where })]));
        card.appendChild(meta);
        if (note.url) {
          card.appendChild(el("p", { class: "card-body" }, [
            el("a", { href: note.url, target: "_blank", rel: "noopener", text: "打开原文 ↗" }),
          ]));
        }
        if (note.key_provisions && note.key_provisions.length) {
          const quotes = el("div", { class: "ev-cards" });
          for (const provision of note.key_provisions) {
            quotes.appendChild(el("div", { class: "ev-card", "data-kind": "政策" }, [
              el("p", { class: "ev-quote", text: provision }),
            ]));
          }
          card.appendChild(quotes);
        }
        host.appendChild(card);
      }
    } else {
      host.appendChild(el("div", { class: "placeholder" }, [
        el("b", { text: "政策注记段：待接入" }),
        status.reason || "政策库尚未就绪，本段留空位。",
        status.planned ? `计划接入：${status.planned}。` : "",
      ]));
    }
  }

  function renderAssumptions(result) {
    const host = $("#out-assumptions");
    host.textContent = "";
    const assumptions = result.roi_assumptions || {};
    const meta = result.meta || {};
    const dl = el("dl");
    const add = (label, value) => {
      dl.appendChild(el("dt", { text: label }));
      dl.appendChild(el("dd", { text: value === undefined || value === null || value === "" ? "—" : String(value) }));
    };
    add("ROI 口径", assumptions.formula);
    add("排序口径", assumptions.conservatism);
    add("成效弹性", assumptions.elasticity);
    add("收益基数（万元/年）", JSON.stringify(assumptions.benefit_bases || {}));
    add("规模折算系数", assumptions.scale_factor);
    add("场景等级来源", (result.evaluation || {}).scenario_levels_source === "submitted"
      ? "提交值（用户自评或上游判定）"
      : (result.evaluation || {}).scenario_levels_source === "rule_baseline"
        ? "确定性规则基线 advisor.agent.scenario_judge.rule_scenario_levels（未调用模型）"
        : "未提供");
    add("判据来源", meta.criteria_source);
    add("场景来源", meta.scenario_source);
    add("官方文件", meta.document);
    add("生成时间", meta.generated_at);
    add("计算方式", meta.mode === "precomputed" ? "预计算（构建时生成）" : "实时计算");
    host.appendChild(dl);
  }

  /* ------------------------------------------------------------ 知识库 */

  const KB_LIBRARIES = {
    policy: {
      title: "政策库",
      desc: "定判据、门槛、验收口径与资金通道。每条带文号、发布方、发布日期与原文链接。",
      filters: [{ key: "role", label: "用途" }],
      render: renderKbPolicyItem,
    },
    cases: {
      title: "案例库",
      desc: "提供症状 → 根因 → 改造项的证据。条目均为公开案例，逐条可回查原文。",
      filters: [
        { key: "source_type", label: "来源类型" },
        { key: "industry", label: "行业" },
      ],
      render: renderKbCaseItem,
    },
    papers: {
      title: "论文库",
      desc: "提供成效弹性区间与评价方法。文献与检索入口分开计数，单一结论不写成定论。",
      filters: [{ key: "kind", facet: "type", label: "类型" }],
      render: renderKbPaperItem,
    },
    patents: {
      title: "专利库",
      desc: "判断某类改造在本地有没有成熟供给。只用官方大类口径，不做专利质量评价。",
      filters: [],
      render: renderKbPatentItem,
    },
  };

  const kbState = {
    stats: null,
    libraries: {},
  };

  function kbInitial() {
    const libraries = {};
    for (const [key, meta] of Object.entries(KB_LIBRARIES)) {
      libraries[key] = { q: "", filters: {}, items: [], total: 0, facets: {} };
    }
    return libraries;
  }

  function kbOptions(facets, key, facet) {
    const counts = (facets && facets[facet || key]) || {};
    return Object.entries(counts).map(([name, count]) => ({ name, count }));
  }

  function renderKbPolicyItem(item) {
    return el("li", { class: "kb-item" }, [
      el("div", { class: "kb-item-head" }, [
        el("a", {
          class: "kb-item-title",
          href: item.url || "#",
          target: "_blank",
          rel: "noopener",
          text: item.title || item.doc_no,
        }),
        el("span", { class: "tag", text: item.doc_no || "" }),
      ]),
      el("p", { class: "kb-item-meta", text: `${item.issuer || "发布方未登记"} · ${item.publish_date || "日期未登记"}` }),
      item.used_where ? el("p", { class: "kb-item-meta", text: "用在：" + item.used_where }) : null,
    ]);
  }

  function renderKbCaseItem(item) {
    const evidence = item.evidence || {};
    const scenarios = [];
    for (const action of item.actions || []) {
      if (action.target_scenario && !scenarios.includes(action.target_scenario)) {
        scenarios.push(action.target_scenario);
      }
    }
    return el("li", { class: "kb-item" }, [
      el("div", { class: "kb-item-head" }, [
        el("a", {
          class: "kb-item-title",
          href: evidence.url || "#",
          target: "_blank",
          rel: "noopener",
          text: item.title || item.id,
        }),
        el("span", { class: "tag", text: item.source_type || "案例" }),
        item.industry ? el("span", { class: "tag tag-accent", text: item.industry }) : null,
      ]),
      item.symptom ? el("p", { class: "kb-item-quote", text: item.symptom }) : null,
      el("p", { class: "kb-item-meta", text: `${item.id} · 目标场景 ${scenarios.join("、") || "未登记"} · ${item.collection || ""}` }),
    ]);
  }

  function renderKbPaperItem(item) {
    return el("li", { class: "kb-item" }, [
      el("div", { class: "kb-item-head" }, [
        el("a", {
          class: "kb-item-title",
          href: item.url || "#",
          target: "_blank",
          rel: "noopener",
          text: item.title || item.id,
        }),
        el("span", { class: "tag", text: item.type || "论文" }),
        item.tier ? el("span", { class: "tag tag-accent", text: item.tier }) : null,
      ]),
      item.claim ? el("p", { class: "kb-item-quote", text: item.claim }) : null,
      el("p", { class: "kb-item-meta", text: `${item.id} · ${item.journal || "来源未登记"}${item.year ? " · " + item.year : ""}${item.doi ? " · DOI " + item.doi : ""}` }),
      item.used_where ? el("p", { class: "kb-item-meta", text: "用在：" + item.used_where }) : null,
    ]);
  }

  function renderKbPatentItem(item) {
    const aggregate = item.official_aggregate || {};
    const numbers = aggregate.applications_cn
      ? `${aggregate.ipc_class || ""} ${aggregate.year || ""} 年大类申请 ${aggregate.applications_cn} 件 / 授权 ${aggregate.grants_cn} 件`
      : "小类数量待人工检索";
    return el("li", { class: "kb-item" }, [
      el("div", { class: "kb-item-head" }, [
        el("span", { class: "kb-item-title", text: item.category || item.id }),
        el("span", { class: "tag", text: item.status || "口径" }),
        aggregate.ipc_class ? el("span", { class: "tag tag-accent", text: "IPC " + aggregate.ipc_class }) : null,
      ]),
      el("p", { class: "kb-item-meta", text: "关键词：" + ((item.keywords || []).join("、") || "未登记") }),
      el("p", { class: "kb-item-meta", text: "对应场景：" + ((item.maps_to_scenarios || []).join("、") || "未映射") }),
      el("p", { class: "kb-item-meta", text: numbers + "（官方大类口径）" }),
    ]);
  }

  function renderKbOverview(stats) {
    const status = stats.status || {};
    const cards = [
      { label: "政策", value: status.policy, unit: "份", note: "含文号、发布方、日期与原文链接" },
      { label: "案例", value: status.cases, unit: "条", note: "公开案例，真实层与合成层分开统计" },
      { label: "论文", value: status.papers, unit: "篇", note: "另有 " + (status.paper_entries - status.papers) + " 条检索入口，不计入文献" },
      { label: "专利", value: status.patent_categories, unit: "个大类", note: "官方 IPC 大类口径，非小类数量" },
    ];
    return el("div", { class: "kb-overview" }, cards.map((card) =>
      el("div", { class: "kb-stat" }, [
        el("span", { class: "kb-stat-label", text: card.label }),
        el("span", { class: "kb-stat-value" }, [
          el("strong", { text: card.value === undefined ? "—" : String(card.value) }),
          el("em", { text: card.unit }),
        ]),
        el("span", { class: "kb-stat-note", text: card.note }),
      ])
    ));
  }

  function renderKbControls(key, meta, library) {
    const online = state.mode === "online";
    const input = el("input", {
      type: "search",
      class: "kb-search",
      placeholder: online ? "检索标题、文号、原文…" : "离线模式不提供检索",
      "aria-label": meta.title + "检索",
      disabled: !online,
    });
    const status = el("span", { class: "kb-status", role: "status" });

    const controls = el("div", { class: "kb-controls" }, [input]);
    for (const filter of meta.filters) {
      const select = el("select", { class: "kb-select", "aria-label": filter.label, disabled: !online });
      select.appendChild(el("option", { value: "", text: "全部" + filter.label }));
      for (const option of kbOptions(library.facets, filter.key, filter.facet)) {
        select.appendChild(el("option", {
          value: option.name,
          text: option.name + "（" + option.count + "）",
          selected: library.filters[filter.key] === option.name,
        }));
      }
      select.addEventListener("change", () => {
        library.filters[filter.key] = select.value;
        refreshKbLibrary(key);
      });
      controls.appendChild(select);
    }
    controls.appendChild(status);
    if (!online) {
      controls.appendChild(el("span", { class: "tag tag-warn", text: "离线仅浏览" }));
    }

    input.addEventListener("change", () => {
      library.q = input.value.trim();
      refreshKbLibrary(key);
    });

    const block = el("section", { class: "kb-lib" }, [
      el("div", { class: "kb-lib-head" }, [
        el("h3", { class: "kb-lib-title", text: meta.title }),
        el("span", { class: "kb-count", text: "" }),
      ]),
      el("p", { class: "kb-lib-desc", text: meta.desc }),
      controls,
      el("p", { class: "kb-entry kb-item-meta" }),
      el("ul", { class: "kb-list" }),
    ]);
    return block;
  }

  function kbStatusText(library) {
    const shown = library.items.length;
    if (!library.total) return "没有命中条目";
    if (shown >= library.total) return "共 " + library.total + " 条";
    return "命中 " + library.total + " 条，显示前 " + shown + " 条";
  }

  function paintKbLibrary(key) {
    const meta = KB_LIBRARIES[key];
    const library = kbState.libraries[key];
    const block = document.querySelector('[data-kb="' + key + '"]');
    if (!block) return;
    const count = block.querySelector(".kb-count");
    if (count) count.textContent = kbStatusText(library);
    const status = block.querySelector(".kb-status");
    if (status) status.textContent = "";
    const list = block.querySelector(".kb-list");
    list.textContent = "";
    if (!library.items.length) {
      list.appendChild(el("li", { class: "placeholder", text: "没有命中条目，换个关键词或把筛选放宽。" }));
      return;
    }
    for (const item of library.items) {
      list.appendChild(meta.render(item));
    }
    const entry = block.querySelector(".kb-entry");
    const searchEntry = library.meta && library.meta.search_entry;
    if (entry && searchEntry) {
      entry.textContent = "";
      entry.appendChild(el("span", { text: "官方检索入口：" }));
      entry.appendChild(el("a", {
        href: searchEntry,
        target: "_blank",
        rel: "noopener",
        text: "国家知识产权局专利检索系统 ↗",
      }));
      if (library.meta.counting_rule) {
        entry.appendChild(el("span", { text: "计数规则：" + library.meta.counting_rule }));
      }
    }
  }

  async function refreshKbLibrary(key) {
    const library = kbState.libraries[key];
    const meta = KB_LIBRARIES[key];
    const params = new URLSearchParams();
    if (library.q) params.set("q", library.q);
    for (const [name, value] of Object.entries(library.filters)) {
      if (value) params.set(name, value);
    }
    params.set("limit", "20");
    try {
      const response = await fetchJSON("api/knowledge/" + key + "?" + params.toString());
      library.items = response.items || [];
      library.total = response.total || 0;
      library.facets = response.facets || {};
      if (response.meta) library.meta = response.meta;
    } catch (err) {
      const status = document.querySelector('[data-kb="' + key + '"] .kb-status');
      if (status) status.textContent = "检索失败：" + err.message;
      return;
    }
    // 筛选下拉的可选项跟着命中结果走
    for (const filter of meta.filters) {
      const select = document.querySelector('[data-kb="' + key + '"] .kb-select[aria-label="' + filter.label + '"]');
      if (!select) continue;
      const current = library.filters[filter.key] || "";
      select.textContent = "";
      select.appendChild(el("option", { value: "", text: "全部" + filter.label }));
      const options = kbOptions(library.facets, filter.key, filter.facet);
      if (current && !options.some((option) => option.name === current)) {
        options.push({ name: current, count: 0 });
      }
      for (const option of options) {
        select.appendChild(el("option", {
          value: option.name,
          text: option.name + "（" + option.count + "）",
          selected: current === option.name,
        }));
      }
    }
    paintKbLibrary(key);
  }

  async function loadKnowledge() {
    const host = $("#knowledge-body");
    if (!host) return;
    kbState.libraries = kbInitial();
    host.textContent = "";
    host.appendChild(el("p", { class: "placeholder", text: "正在加载知识库…" }));

    const online = state.mode === "online";
    let stats = null;
    try {
      stats = online
        ? await fetchJSON("api/knowledge/stats")
        : await kbOfflineStats();
    } catch (err) {
      host.textContent = "";
      host.appendChild(el("p", { class: "placeholder", text: "知识库加载失败：" + err.message }));
      return;
    }
    kbState.stats = stats;
    host.textContent = "";
    host.appendChild(renderKbOverview(stats));

    for (const [key, meta] of Object.entries(KB_LIBRARIES)) {
      const block = renderKbControls(key, meta, kbState.libraries[key]);
      block.setAttribute("data-kb", key);
      host.appendChild(block);
    }

    if (online) {
      for (const key of Object.keys(KB_LIBRARIES)) {
        await refreshKbLibrary(key);
      }
    } else {
      await kbOfflineBrowse();
    }
  }

  async function kbOfflineStats() {
    const [policy, cases, papers, patents] = await Promise.all([
      fetchJSON("data/knowledge/policy.json"),
      fetchJSON("data/knowledge/cases.json"),
      fetchJSON("data/knowledge/papers.json"),
      fetchJSON("data/knowledge/patents.json"),
    ]);
    const literature = papers.filter((paper) => paper.type !== "检索入口");
    return {
      status: {
        policy: policy.length,
        cases: cases.length,
        papers: literature.length,
        paper_entries: papers.length,
        patent_categories: (patents.categories || []).length,
      },
    };
  }

  async function kbOfflineBrowse() {
    const files = {
      policy: "data/knowledge/policy.json",
      cases: "data/knowledge/cases.json",
      papers: "data/knowledge/papers.json",
      patents: "data/knowledge/patents.json",
    };
    for (const [key, file] of Object.entries(files)) {
      const library = kbState.libraries[key];
      try {
        const payload = await fetchJSON(file);
        const items = key === "patents" ? payload.categories || [] : payload;
        library.items = items.slice(0, 20);
        library.total = items.length;
      } catch (err) {
        library.items = [];
        library.total = 0;
      }
      paintKbLibrary(key);
    }
  }

  /* ------------------------------------------------------------ 交互 */

  /* 顶栏高度会随屏幕宽度变化（手机上换行），固定条要跟着它走 */
  function syncTopbarHeight() {
    const topbar = document.querySelector(".topbar");
    if (!topbar) return;
    document.documentElement.style.setProperty("--topbar-h", `${topbar.offsetHeight}px`);
  }

  /* 手机上"四个等级判定"默认折叠，免得固定条吃掉半屏 */
  function syncLevelDetails() {
    const details = $("#level-details");
    if (!details) return;
    const summary = details.querySelector("summary");
    const wide = window.innerWidth > 720;
    if (wide) {
      details.open = true;
      summary.style.display = "none";
    } else {
      summary.style.display = "";
      details.open = false;
    }
  }

  function bindActions() {
    syncTopbarHeight();
    syncLevelDetails();
    window.addEventListener("resize", () => {
      syncTopbarHeight();
      syncLevelDetails();
    });

    $("#btn-demo").addEventListener("click", async () => {
      $("#input-panel").hidden = false;
      // 默认拿反模式样例 AP1：四段式内容最完整（诊断 + 路径 + 排序 + 不建议做）
      const preferred = state.fixtures.find((f) => f.name.startsWith("ap1")) || state.fixtures[0];
      if (!preferred) return;
      const picker = $("#fixture-select");
      if (picker) picker.value = preferred.name;
      state.selectedFixture = preferred.name;
      await loadFixture(preferred.name);
      $("#output-panel").scrollIntoView({ behavior: "smooth", block: "start" });
    });

    $("#btn-fill").addEventListener("click", () => {
      $("#input-panel").hidden = false;
      $("#input-panel").scrollIntoView({ behavior: "smooth", block: "start" });
    });

    $("#profile-form").addEventListener("submit", (event) => {
      event.preventDefault();
      runEvaluation();
    });

    $("#btn-reset").addEventListener("click", () => {
      $("#profile-form").reset();
      $("#form-status").textContent = "";
    });

    $("#gap-toggle").addEventListener("click", () => {
      const list = $("#gap-list");
      const open = list.hasAttribute("hidden");
      if (open) list.removeAttribute("hidden"); else list.setAttribute("hidden", "");
      $("#gap-toggle").setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  document.addEventListener("DOMContentLoaded", boot);
})();
