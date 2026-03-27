---
title: Failure Mode Analysis
---

# Failure Mode Analysis

## Summary by Failure Type

```sql failure_type_summary
SELECT
    failure_type,
    COUNT(*) AS total_failures,
    SUM(CASE WHEN risk_level = 'high' THEN 1 ELSE 0 END) AS high_risk,
    SUM(CASE WHEN risk_level = 'medium' THEN 1 ELSE 0 END) AS medium_risk,
    SUM(CASE WHEN risk_level = 'low' THEN 1 ELSE 0 END) AS low_risk
FROM audit_results.failure_matrix
GROUP BY failure_type
ORDER BY high_risk DESC, total_failures DESC
```

<DataTable data={failure_type_summary} />

---

## Failures by Type (Chart)

```sql failures_by_type_chart
SELECT
    failure_type,
    COUNT(*) AS total_failures
FROM audit_results.failure_matrix
GROUP BY failure_type
ORDER BY total_failures DESC
```

<BarChart
    data={failures_by_type_chart}
    x="failure_type"
    y="total_failures"
    title="Failure Count by Type"
    xAxisTitle="Failure Type"
    yAxisTitle="Count"
/>

---

## Full Failure Matrix

```sql full_failure_matrix
SELECT
    step_id,
    step_name,
    failure_type,
    risk_level,
    rationale,
    mitigation
FROM audit_results.failure_matrix
ORDER BY
    CASE risk_level
        WHEN 'high' THEN 1
        WHEN 'medium' THEN 2
        WHEN 'low' THEN 3
        ELSE 4
    END,
    step_name
```

<DataTable data={full_failure_matrix} />

---

## Navigation

- [Executive Summary](/)
- [Workflow Map](/workflow-map)
- [Failure Modes](/failures)
- [Checkpoints](/human-checkpoints)
- [Cost Analysis](/cost-analysis)
- [Recommendations](/recommendations)
