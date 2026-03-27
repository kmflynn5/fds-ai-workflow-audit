# Risk Dimensions

The composite risk score is built from 5 dimensions. Each is scored 1–5. Two dimensions (blast radius, reversibility) carry double weight in the composite formula:

```
composite = (blast_radius × 2 + reversibility × 2 + frequency + verifiability + cascading_risk) / 8
```

---

## 1. Blast Radius (weight: 2x)

**What it measures:** How bad is the damage if this step fails?

**Weighting rationale:** This is the primary driver of whether a failure matters at all. A step that fails silently and affects only an internal log is categorically different from one that triggers a regulatory violation or corrupts customer data at scale. Double weight ensures high-blast-radius steps dominate the composite even if other dimensions are moderate.

**Inputs used:** `error_consequence`, `customer_facing`, `data_sensitivity`, `regulatory_environment`

### Scale

| Score | Level | Description | Example |
|-------|-------|-------------|---------|
| 1 | Minimal | Internal log error, no user impact | A metadata tagging step fails; records are untagged |
| 2 | Low | Degraded experience for a single user | Personalization step fails; user gets generic content |
| 3 | Moderate | Feature outage or batch data quality issue | Enrichment step fails; CRM records are stale for a period |
| 4 | High | Customer-visible data error, trust damage, or financial impact | Email sends with wrong pricing; customer escalation |
| 5 | Critical | Regulatory violation, PII exposure, or irreversible brand damage | Compliance check bypassed; GDPR breach; discriminatory content published |

---

## 2. Reversibility (weight: 2x)

**What it measures:** Can you undo the damage after a failure?

**Weighting rationale:** Reversibility determines the cost of being wrong. A fully reversible failure means you fix it and move on. An irreversible failure means you live with it. Double weight reflects that "can we recover" is as important as "how bad is it."

**Inputs used:** `reversible` flag on the step config, `step_type`, presence of `tools` (tool-calling steps are generally less reversible than pure generation steps)

### Scale

| Score | Level | Description | Example |
|-------|-------|-------------|---------|
| 1 | Fully reversible | No side effects; retry is safe and complete | LLM classification step with no downstream write |
| 2 | Mostly reversible | Side effects exist but are easily corrected | Draft created in CMS; can be deleted before publish |
| 3 | Partially reversible | Recovery is possible but requires manual effort | CRM field overwritten; can be restored from audit log |
| 4 | Difficult to reverse | Some damage is permanent or requires significant remediation | Email sent to a segment; can apologize but not unsend |
| 5 | Irreversible | Cannot be undone; permanent external effect | Public post published and indexed; regulatory filing submitted |

---

## 3. Frequency (weight: 1x)

**What it measures:** How often does this step execute?

**Weighting rationale:** Frequency converts a per-occurrence risk score into a portfolio risk. A low-severity step that runs 10,000 times a day has a higher expected daily damage than a high-severity step that runs once. Single weight because frequency amplifies risk rather than defining it — the blast radius and reversibility set the ceiling.

**Inputs used:** `daily_volume` from the workflow header, step position in the workflow graph (steps earlier in the graph may execute at full volume; steps gated by conditions execute less frequently)

### Scale

| Score | Level | Volume | Example |
|-------|-------|--------|---------|
| 1 | Rare | < 10 executions/day | Internal analyst tool used ad hoc |
| 2 | Low | 10–100/day | Daily batch enrichment job |
| 3 | Moderate | 100–1,000/day | Mid-size SaaS product feature |
| 4 | High | 1,000–10,000/day | High-traffic customer support flow |
| 5 | Very high | > 10,000/day | Core transactional flow at scale |

---

## 4. Verifiability (weight: 1x)

**What it measures:** How hard is it to verify that this step's output is correct?

**Weighting rationale:** Verifiability determines how quickly you catch failures. A step whose output can be checked mechanically (schema validation, exact match) has a much shorter mean time to detection than one whose output requires a domain expert to evaluate. Single weight because verifiability affects detection speed, not damage magnitude.

**Inputs used:** `step_type` — classification and extraction steps are more verifiable than open-ended generation; action steps are often verifiable only by checking downstream effects

### Scale

| Score | Level | Description | Example |
|-------|-------|-------------|---------|
| 1 | Trivially verifiable | Deterministic or schema-checkable output | JSON extraction with a known schema |
| 2 | Easily verifiable | Automated eval against a defined rubric | Sentiment classification checked against labeled test set |
| 3 | Moderately verifiable | Requires sampling + human review to validate at acceptable confidence | Email subject line quality |
| 4 | Hard to verify | Correctness depends on domain knowledge or downstream outcome | Strategic recommendation; prospect prioritization |
| 5 | Unverifiable without end-user feedback | Functional correctness only knowable after the customer acts | Whether a support response actually resolved the customer's issue |

---

## 5. Cascading Risk (weight: 1x)

**What it measures:** If this step fails, how many downstream steps are affected?

**Weighting rationale:** Cascading risk quantifies the blast radius expansion effect — a failure here doesn't just damage this step, it propagates. Single weight because cascading risk is a structural property of the workflow graph, and it interacts multiplicatively with blast radius (which already captures the per-step damage).

**Inputs used:** DAG descendant count — computed by `engine/parser.py` from the `depends_on` fields across all steps

### Scale

| Score | Level | Downstream Dependents | Example |
|-------|-------|-----------------------|---------|
| 1 | Terminal | 0 dependents | Final send/publish step |
| 2 | Low propagation | 1–2 dependents | Formatting step before output |
| 3 | Moderate propagation | 3–4 dependents | Data enrichment mid-pipeline |
| 4 | High propagation | 5–6 dependents | Customer identity resolution step |
| 5 | Full cascade | 6+ dependents | Initial data retrieval step that all subsequent steps depend on |

---

## Composite Score Interpretation

| Range | Meaning | Default Action |
|-------|---------|----------------|
| 1.0 – 2.5 | Low risk | Automated handling; log for monitoring |
| 2.5 – 3.5 | Moderate risk | Monitor closely; consider spot-checks |
| 3.5 – 4.0 | High risk | Human checkpoint recommended |
| 4.0 – 5.0 | Critical risk | Human checkpoint required before execution |
