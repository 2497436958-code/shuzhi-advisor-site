// 浏览器内引擎（assets/engine.js）与后端预计算结果逐项比对。
// 用法：node site/test-regression.mjs
// 依赖：零第三方依赖；数据来自 site/data（由 tools/sync_site_data.py 导出）。
import { readFileSync, readdirSync } from 'fs';
import { createRequire } from 'module';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const HERE = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const engine = require(join(HERE, 'assets', 'engine.js'));

const criteria = JSON.parse(readFileSync(join(HERE, 'data', 'criteria.json'), 'utf8'));
const dir = join(HERE, 'data', 'samples');
const files = readdirSync(dir).filter((f) => f.endsWith('.json'));

let pass = 0, fail = 0;
for (const file of files) {
  const sample = JSON.parse(readFileSync(join(dir, file), 'utf8'));
  const got = engine.evaluate(criteria, sample.profile);
  const want = sample.result.evaluation;
  const errs = [];

  const g = got.evaluation;
  if (Math.abs(g.total_score - want.total_score) > 1e-9) errs.push(`总分 ${g.total_score} != ${want.total_score}`);
  if (g.level !== want.level) errs.push(`等级 ${g.level} != ${want.level}`);
  if (g.level_name !== want.level_name) errs.push(`等级名 ${g.level_name} != ${want.level_name}`);
  for (const k of Object.keys(want.dimension_scores)) {
    const d = Math.abs((g.dimension_scores[k] ?? 0) - want.dimension_scores[k]);
    if (d > 1e-9) errs.push(`维度 ${k} ${g.dimension_scores[k]} != ${want.dimension_scores[k]}`);
  }
  for (const k of ['1', '2', '3', '4']) {
    if (g.scenario_count_by_level[k] !== want.scenario_count_by_level[k]) errs.push(`场景${k}级 ${g.scenario_count_by_level[k]} != ${want.scenario_count_by_level[k]}`);
    if (g.constraint_count_by_level[k] !== want.constraint_count_by_level[k]) errs.push(`约束${k}级 ${g.constraint_count_by_level[k]} != ${want.constraint_count_by_level[k]}`);
  }
  // 逐项得分
  const itemMap = new Map(want && sample.result.item_results ? sample.result.item_results.map((i) => [i.id, i]) : []);
  for (const item of got.item_results) {
    const w = itemMap.get(item.id);
    if (!w) continue;
    if (Math.abs(item.points - w.points) > 1e-9) errs.push(`采集项${item.id} points ${item.points} != ${w.points}`);
  }

  if (errs.length) { fail++; console.log(`✗ ${file}`); errs.forEach((e) => console.log('   ' + e)); }
  else { pass++; console.log(`✓ ${file}  ${g.total_score} 分 · ${g.level_name}`); }
}
console.log(`\n结果：${pass} 通过 / ${fail} 失败 / 共 ${files.length}`);

// 二级校验：等级判定措辞与未达标说明
let p2 = 0, f2 = 0;
for (const file of files) {
  const sample = JSON.parse(readFileSync(join(dir, file), 'utf8'));
  const got = engine.evaluate(criteria, sample.profile);
  const want = sample.result;
  const errs = [];
  got.level_judgement.forEach((j, i) => {
    const w = want.level_judgement[i];
    if (!w) return;
    if (j.satisfied !== w.satisfied) errs.push(`L${j.level} satisfied`);
    if (j.note !== w.note) errs.push(`L${j.level} note\n     got: ${j.note}\n     want:${w.note}`);
  });
  const gu = JSON.stringify(got.evaluation.unmet), wu = JSON.stringify(want.evaluation.unmet);
  if (gu !== wu) errs.push(`unmet\n     got: ${gu}\n     want:${wu}`);
  if (got.evaluation.scenario_levels_source !== want.evaluation.scenario_levels_source) errs.push('source');
  if (errs.length) { f2++; console.log(`✗ ${file}`); errs.forEach((e) => console.log('   ' + e)); }
  else p2++;
}
console.log(`\n二级校验：${p2} 通过 / ${f2} 失败`);
process.exit(fail || f2 ? 1 : 0);
