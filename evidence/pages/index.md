---
title: Executive Summary
---

# AI Workflow Audit — Executive Summary

```sql exec_summary
SELECT
    workflow_name,
    total_steps,
    high_risk_steps,
    checkpoints_required,
    checkpoints_recommended,
    failure_modes_high,
    monthly_cost,
    annual_cost,
    cost_per_request
FROM audit_results.executive_summary
LIMIT 1
```

<BigValue data={exec_summary} value="workflow_name" title="Workflow" />
<BigValue data={exec_summary} value="total_steps" title="Total Steps" fmt="num0" />
<BigValue data={exec_summary} value="high_risk_steps" title="High-Risk Steps" fmt="num0" />
<BigValue data={exec_summary} value="monthly_cost" title="Monthly Cost" fmt="usd" />
<BigValue data={exec_summary} value="annual_cost" title="Annual Cost" fmt="usd" />
<BigValue data={exec_summary} value="cost_per_request" title="Cost per Request" fmt="usd4" />

---

## Composite Risk by Step

```sql risk_by_step
SELECT step_name, composite
FROM audit_results.risk_scores
ORDER BY composite DESC
```

<BarChart
    data={risk_by_step}
    x="step_name"
    y="composite"
    title="Composite Risk Score by Step"
    xAxisTitle="Step"
    yAxisTitle="Composite Risk Score"
/>

---

## Failure Mode Summary

```sql failure_summary
SELECT
    failure_type,
    COUNT(*) AS total_failures,
    SUM(CASE WHEN risk_level = 'high' THEN 1 ELSE 0 END) AS high_risk,
    SUM(CASE WHEN risk_level = 'medium' THEN 1 ELSE 0 END) AS medium_risk,
    SUM(CASE WHEN risk_level = 'low' THEN 1 ELSE 0 END) AS low_risk
FROM audit_results.failure_matrix
GROUP BY failure_type
ORDER BY high_risk DESC
```

<DataTable data={failure_summary} />

---

## Navigation

- [Executive Summary](/)
- [Workflow Map](/workflow-map)
- [Failure Modes](/failures)
- [Checkpoints](/human-checkpoints)
- [Cost Analysis](/cost-analysis)
- [Recommendations](/recommendations)
