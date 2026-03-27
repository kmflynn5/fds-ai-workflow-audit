# Assessment Methodology

## Overview

fds-ai-workflow-audit takes a YAML description of an AI-powered workflow and produces a structured assessment a CTO or engineering lead can act on. The pipeline is:

```
workflow.yml → Assessment Engine (Python) → JSON + CSVs → Evidence BI Report
```

No black boxes. Every score is traceable back to a specific input field in the workflow config.

---

## Three Pillars

### 1. Risk Scoring

Every step in the workflow receives a composite risk score across 5 dimensions. The composite formula is:

```
composite = (blast_radius × 2 + reversibility × 2 + frequency + verifiability + cascading_risk) / 8
```

Blast radius and reversibility are double-weighted because production deployment decisions hinge on "how bad can this get" and "can we undo it." The other three dimensions (frequency, verifiability, cascading risk) are equal-weighted as modifying factors.

All dimensions are scored 1–5. The composite therefore ranges from 1.0 to 5.0.

**Checkpoint thresholds:**

| Composite Score | Recommendation |
|----------------|----------------|
| > 4.0 | Human checkpoint required |
| 3.5 – 4.0 | Human checkpoint recommended |
| < 3.5 | Automated handling acceptable |

### 2. Failure Mode Mapping

Each step is analyzed against 6 failure types drawn from Nate B. Jones' framework for LLM failure modes. The engine maps step attributes (type, position, tools, customer-facing flag, etc.) to susceptible failure types and produces a prioritized list per step. See [FAILURE_TAXONOMY.md](FAILURE_TAXONOMY.md) for full definitions.

### 3. Cost Analysis

The engine models token economics per step using:
- Estimated input tokens (from step complexity, context, and tool count)
- Estimated output tokens (from step type and response requirements)
- Model pricing at current API rates
- Infrastructure overhead (orchestration, storage, monitoring)

Costs are projected over 12 months using the workflow's declared volume and a configurable growth rate.

---

## Config-Driven Assessment

### Workflow YAML

Workflows are described in YAML. Each workflow has a header (metadata, volume, growth) and a list of steps. Each step declares:

- `type` — e.g., `data_lookup`, `llm_generation`, `action`, `validation`
- `model` — which LLM (if any)
- `tools` — list of tools available to the step
- `reversible` — whether the action can be undone
- `customer_facing` — whether output reaches a customer
- `depends_on` — upstream steps (builds the DAG)
- `error_consequence` — plain-text description of what breaks on failure

See `examples/` for fully worked workflow configs.

### Assessment Engine

The engine is a set of Python modules in `engine/`:

| Module | Role |
|--------|------|
| `parser.py` | YAML → Pydantic models → networkx DAG |
| `risk_scorer.py` | 5-dimension scoring, composite formula |
| `failure_mapper.py` | 6 failure type susceptibility per step |
| `checkpoint_recommender.py` | Where to place human-in-the-loop gates |
| `cost_calculator.py` | Token economics, infrastructure, projections |
| `claude_enricher.py` | Optional: Claude API for narrative enrichment |

### Evidence Report

Output CSVs are loaded into an Evidence BI project. The report surfaces:

- Per-step risk scores with composite ranking
- Failure mode heatmap by step
- Checkpoint placement map
- Cost breakdown (per step, per day, 12-month projection)
- Executive summary with prioritized recommendations

---

## How to Interpret Results

**A high composite score (> 4.0)** means the step can cause significant, hard-to-reverse damage at volume. It needs a human checkpoint before it executes.

**A high blast radius score** means failures here have wide organizational impact — regulatory exposure, customer trust damage, or data integrity issues. Prioritize these regardless of frequency.

**A high reversibility score** means the damage is hard or impossible to undo. Sent emails, published content, and irreversible API calls all score high here.

**A high cascading risk score** means a failure here will propagate to multiple downstream steps. These are often early-pipeline steps that set context or retrieve data.

**The failure mode mapping** tells you what kind of failure is most likely, not just how bad it could be. A step with high tool selection error susceptibility needs different mitigation (tool restriction, call logging) than one with high silent failure susceptibility (sampling audits, functional evals).

---

## Cost Model

### Token Economics

Each step's token cost is estimated from:
- Base input tokens: prompt template size + context injection
- Tool definitions: ~200–800 tokens per tool depending on schema complexity
- History: accumulated conversation context for multi-turn steps
- Output tokens: expected response length by step type

Costs use current model pricing and are summed per workflow execution, then multiplied by daily volume.

### Infrastructure Costs

Beyond API tokens, the model accounts for:
- Orchestration compute (Lambda/Cloud Run)
- Vector store queries (if RAG steps present)
- Monitoring and observability tooling
- Human review time at recommended checkpoints (at a configurable hourly rate)

### Growth Projections

The 12-month projection uses compound growth on the declared `daily_volume` and `monthly_growth_rate` from the workflow header. It produces a table of monthly costs and a breakeven analysis for additional tooling investment.
