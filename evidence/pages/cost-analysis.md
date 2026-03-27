---
title: Cost Analysis
---

# Cost Analysis

## Cost Summary

```sql cost_summary
SELECT
    monthly_cost,
    annual_cost,
    cost_per_request
FROM audit_results.executive_summary
LIMIT 1
```

<BigValue data={cost_summary} value="monthly_cost" title="Monthly Cost" fmt="usd" />
<BigValue data={cost_summary} value="annual_cost" title="Annual Cost" fmt="usd" />
<BigValue data={cost_summary} value="cost_per_request" title="Cost per Request" fmt="usd4" />

---

## Monthly Cost by Step

```sql cost_by_step
SELECT
    step_name,
    monthly_cost
FROM audit_results.cost_breakdown
ORDER BY monthly_cost DESC
```

<BarChart
    data={cost_by_step}
    x="step_name"
    y="monthly_cost"
    title="Monthly Cost by Step"
    xAxisTitle="Step"
    yAxisTitle="Monthly Cost (USD)"
/>

---

## Cost Growth Projections

```sql growth_projections
SELECT
    month,
    daily_volume,
    token_monthly_cost,
    infra_monthly_cost,
    total_monthly_cost
FROM audit_results.growth_projections
ORDER BY month
```

<LineChart
    data={growth_projections}
    x="month"
    y="total_monthly_cost"
    title="Projected Total Monthly Cost"
    xAxisTitle="Month"
    yAxisTitle="Total Monthly Cost (USD)"
/>

---

## Cost Breakdown Detail

```sql cost_breakdown
SELECT
    step_id,
    step_name,
    model,
    tokens_in_per_request,
    tokens_out_per_request,
    cost_per_request,
    daily_cost,
    monthly_cost,
    annual_cost
FROM audit_results.cost_breakdown
ORDER BY monthly_cost DESC
```

<DataTable data={cost_breakdown} />

---

## Cost Optimization Opportunities

```sql cost_optimizations
SELECT
    step_id,
    step_name,
    suggestion,
    estimated_monthly_savings,
    category
FROM audit_results.cost_optimizations
ORDER BY estimated_monthly_savings DESC
```

<DataTable data={cost_optimizations} />

---

## Navigation

- [Executive Summary](/)
- [Workflow Map](/workflow-map)
- [Failure Modes](/failures)
- [Checkpoints](/human-checkpoints)
- [Cost Analysis](/cost-analysis)
- [Recommendations](/recommendations)
