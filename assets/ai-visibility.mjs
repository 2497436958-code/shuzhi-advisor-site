/* Optional summary helpers for the AI construction fields in a report result. */

function asObject(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : null;
}

function formatScore(value) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(2) : "—";
}

export function summarizeAiResult(result) {
  const data = asObject(result) || {};
  const priority = asObject(data.robust_priority);
  const graph = asObject(data.evidence_graph);
  const deliberation = asObject(data.deliberation);
  if (!priority && !graph && !deliberation) return { visible: false };

  const scenarios = asObject(priority?.scenarios);
  const base = Array.isArray(scenarios?.base) ? scenarios.base : [];
  const first = base[0] || {};
  const stability = asObject(priority?.stability);
  const decision = asObject(deliberation?.final_decision) || asObject(deliberation?.consensus) || {};
  const reasons = Array.isArray(deliberation?.trigger_reasons)
    ? deliberation.trigger_reasons.filter(Boolean).join("、")
    : "";
  const nodeCount = Array.isArray(graph?.nodes) ? graph.nodes.length : 0;
  const edgeCount = Array.isArray(graph?.edges) ? graph.edges.length : 0;

  return {
    visible: true,
    priority: {
      score: formatScore(first.score),
      rank: first.id ? String(first.id) : "—",
      stability: stability?.stable === false ? "存在排序变化" : "排序稳定",
      explanation: stability?.explanation || "",
    },
    graph: `${nodeCount} 个节点 · ${edgeCount} 条边`,
    deliberation: {
      status: decision.status || (deliberation?.requires_deliberation ? "需要复核" : "已裁决"),
      reasons: reasons || "未触发额外复核",
      recommendation: decision.recommendation || decision.proposed_recommendation || "—",
    },
  };
}

if (typeof window !== "undefined") {
  window.AdvisorAIVisibility = { summarizeAiResult };
}
