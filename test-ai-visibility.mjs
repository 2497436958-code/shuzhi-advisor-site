import assert from 'node:assert/strict';
import { summarizeAiResult } from './assets/ai-visibility.mjs';

const summary = summarizeAiResult({
  robust_priority: {
    scenarios: {
      base: [
        { id: 'P-PLAN', score: 0.82, rank: 1 },
        { id: 'P-DATA', score: 0.61, rank: 2 },
      ],
    },
    stability: { stable: false, agreement: 0.75, explanation: '情景间存在排序变化，应补充证据或开展人工审查' },
  },
  evidence_graph: {
    nodes: [{ id: 'symptom:P-PLAN' }, { id: 'action:P-PLAN:1' }],
    edges: [{ source: 'symptom:P-PLAN', target: 'action:P-PLAN:1', relation: 'addressed_by' }],
  },
  deliberation: {
    requires_deliberation: true,
    round_count: 1,
    trigger_reasons: ['证据不足', '排序不稳定'],
    final_decision: { status: '需要补证据', recommendation: '暂缓裁决' },
  },
});

assert.equal(summary.visible, true);
assert.equal(summary.priority.score, '0.82');
assert.equal(summary.priority.rank, 'P-PLAN');
assert.equal(summary.priority.stability, '存在排序变化');
assert.equal(summary.graph, '2 个节点 · 1 条边');
assert.equal(summary.deliberation.status, '需要补证据');
assert.equal(summary.deliberation.reasons, '证据不足、排序不稳定');

assert.deepEqual(summarizeAiResult({}), { visible: false });

console.log('✓ AI visibility summary');
