# fds-ai-workflow-audit — Implementation Spec

## Overview

A config-driven AI workflow risk and quality assessment tool that takes a description of an AI-powered workflow (customer support agent, content generation pipeline, data enrichment system, etc.) and produces an opinionated assessment showing:

1. **Where humans should stay in the loop** — based on blast radius, reversibility, and frequency
2. **Where evaluation checkpoints should sit** — based on failure modes and quality requirements
3. **What the failure modes are** — mapped to Nate B. Jones' six failure types
4. **What it costs to run at scale** — token economics + infrastructure costs (including Snowflake credits if applicable)

This is Tool A + Tool B combined: the risk assessment and the cost calculator in one framework.

**Design philosophy:** Same pattern as fds-snowflake-cost-audit — config-driven, opinionated output, Evidence BI report. Input a workflow, get back an assessment a CTO can act on.

**Immediate deployment targets:**
- [Client A] — building a new AI product, needs to understand guardrails, human checkpoints, and cost profile. The assessment could reactivate the deal and expand scope.
- [Client B] — evaluating AI/data infrastructure. A workflow assessment demonstrates FDS value beyond Snowflake.
- Blog content — "How to Audit Your AI Workflow Before It Hits Production" as a companion to the Snowflake cost audit content.

**Positioning:** The Snowflake cost audit answers "is your data infrastructure cost-effective?" This tool answers "is your AI workflow production-ready and cost-effective?" Together, FDS evaluates both the data layer and the AI layer.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  workflow.yml                                                │
│  - workflow description (steps, agents, tools)               │
│  - volume profile (requests/day, tokens/request)             │
│  - risk profile (blast radius, reversibility, sensitivity)   │
│  - model selection (providers, models, pricing)              │
│  - infrastructure (Snowflake, DuckDB, APIs, etc.)           │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│  Assessment Engine (Python)                                  │
│  - Parses workflow into step graph                          │
│  - Scores each step on risk dimensions                      │
│  - Maps failure modes per step                              │
│  - Identifies human checkpoint recommendations              │
│  - Calculates cost model                                    │
│  - Writes results to local JSON + CSVs                      │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│  Evidence BI Report                                          │
│  - Executive summary with risk score                        │
│  - Workflow diagram with checkpoint annotations             │
│  - Failure mode analysis per step                           │
│  - Human-in-the-loop recommendations                        │
│  - Cost breakdown at scale                                  │
│  - Recommendations prioritized by impact                    │
└─────────────────────────────────────────────────────────────┘
```

Optional: Claude API integration for automated workflow analysis. If configured, the tool can send the workflow description to Claude for enriched failure mode analysis and recommendation generation. Works without it — the rule-based engine handles the core assessment.

---

## 1. Repository Structure

```
fds-ai-workflow-audit/
├── LICENSE                      # Apache 2.0
├── README.md
├── workflow.example.yml         # Example workflow config
├── run_audit.py                 # Main entrypoint
├── requirements.txt
│
├── examples/                    # Pre-built example workflows
│   ├── customer_support_agent.yml
│   ├── content_generation_pipeline.yml
│   ├── data_enrichment_system.yml
│   ├── sales_outreach_agent.yml
│   └── internal_knowledge_qa.yml
│
├── engine/                      # Assessment engine
│   ├── __init__.py
│   ├── parser.py                # Workflow YAML → step graph
│   ├── risk_scorer.py           # Risk dimension scoring
│   ├── failure_mapper.py        # Failure mode analysis
│   ├── checkpoint_recommender.py # Human-in-the-loop placement
│   ├── cost_calculator.py       # Token + infrastructure economics
│   └── claude_enricher.py       # Optional Claude API enhancement
│
├── models/                      # Pricing data
│   ├── model_pricing.yml        # Token prices by provider/model
│   └── infra_pricing.yml        # Snowflake credits, cloud compute, etc.
│
├── evidence/                    # Evidence BI report
│   ├── pages/
│   │   ├── index.md             # Executive summary + risk score
│   │   ├── workflow-map.md      # Visual workflow with annotations
│   │   ├── failure-modes.md     # Failure analysis per step
│   │   ├── checkpoints.md       # Human-in-the-loop recommendations
│   │   ├── cost-analysis.md     # Token + infra cost breakdown
│   │   └── recommendations.md   # Prioritized action items
│   └── sources/
│       └── audit_results/
│
└── docs/
    ├── METHODOLOGY.md
    ├── FAILURE_TAXONOMY.md      # The six failure types explained
    └── RISK_DIMENSIONS.md       # How risk scoring works
```

---

## 2. Workflow Configuration

### `workflow.example.yml`

```yaml
# Workflow metadata
workflow:
  name: "Tier 1 Customer Support Agent"
  description: "AI agent handling password resets, order status, and return initiations with human escalation on negative sentiment"
  owner: "Customer Experience Team"
  environment: "production"

# Workflow steps — the core of the assessment
steps:
  - id: intake
    name: "Receive customer message"
    type: input                     # input | ai_generation | ai_classification | ai_action | human_review | data_lookup | external_api
    description: "Customer submits a support request via chat widget"
    data_sensitivity: low           # low | medium | high | critical
    
  - id: classify
    name: "Classify intent"
    type: ai_classification
    description: "Determine if request is password reset, order status, return, or other"
    model: "claude-haiku-4-5"
    estimated_tokens_in: 500
    estimated_tokens_out: 50
    error_consequence: "Misrouted ticket, delayed resolution"
    reversible: true

  - id: sentiment
    name: "Score customer sentiment"
    type: ai_classification
    description: "Determine if customer is frustrated, neutral, or positive"
    model: "claude-haiku-4-5"
    estimated_tokens_in: 800
    estimated_tokens_out: 100
    error_consequence: "Missed escalation of angry customer"
    reversible: true
    
  - id: escalation_check
    name: "Escalation decision"
    type: ai_classification
    description: "If sentiment is negative and confidence > 0.8, escalate to human"
    depends_on: [classify, sentiment]
    model: "claude-haiku-4-5"
    estimated_tokens_in: 300
    estimated_tokens_out: 50
    error_consequence: "False negative: angry customer gets bot response. False positive: unnecessary human escalation"
    reversible: true
    branches:
      escalate: human_handoff
      continue: resolve

  - id: resolve
    name: "Execute resolution"
    type: ai_action
    description: "Handle the classified request: reset password via API, look up order status, or initiate return"
    depends_on: [escalation_check]
    model: "claude-sonnet-4-20250514"
    estimated_tokens_in: 1500
    estimated_tokens_out: 500
    tools:
      - "password_reset_api"
      - "order_status_api"
      - "return_initiation_api"
    error_consequence: "Wrong action taken on customer account"
    reversible: false              # Password reset is irreversible
    data_sensitivity: high         # Touches customer account

  - id: respond
    name: "Generate customer response"
    type: ai_generation
    description: "Draft and send response to customer"
    depends_on: [resolve]
    model: "claude-haiku-4-5"
    estimated_tokens_in: 800
    estimated_tokens_out: 300
    error_consequence: "Incorrect or inappropriate response to customer"
    reversible: false              # Once sent, can't unsend
    customer_facing: true

  - id: log
    name: "Log interaction"
    type: ai_action
    description: "Log ticket, resolution, and escalation reason code to CRM"
    depends_on: [respond]
    model: "claude-haiku-4-5"
    estimated_tokens_in: 500
    estimated_tokens_out: 200
    error_consequence: "Missing or incorrect CRM record"
    reversible: true

  - id: human_handoff
    name: "Escalate to human agent"
    type: human_review
    description: "Transfer to human with full context summary"
    depends_on: [escalation_check]

# Volume profile
volume:
  requests_per_day: 5000
  peak_multiplier: 3               # Peak is 3x average
  growth_rate_monthly_pct: 10      # Expected monthly growth

# Risk profile
risk:
  regulatory_environment: "standard"  # standard | regulated (healthcare, finance) | critical (safety)
  customer_facing: true
  financial_impact_per_error: 50     # Average cost of a single error (refund, churn, etc.)
  brand_risk: "medium"               # low | medium | high
  data_classification: "PII"         # public | internal | PII | PHI | financial

# Model pricing (override defaults from models/model_pricing.yml)
pricing_overrides:
  # Optional — use if client has negotiated rates
  # claude-sonnet-4-20250514:
  #   input_per_1m: 3.00
  #   output_per_1m: 15.00

# Infrastructure costs (optional — for total cost picture)
infrastructure:
  snowflake:
    enabled: true
    credit_price: 3.00              # Per credit
    estimated_credits_per_day: 5    # For data lookups supporting the workflow
  other_services:
    - name: "CRM API (Salesforce)"
      monthly_cost: 0               # Included in existing license
    - name: "Resend (email notifications)"
      monthly_cost: 20
```

---

## 3. Risk Dimensions

Each workflow step is scored on five dimensions (adapted from Nate's trust and security design framework):

### 3.1 Blast Radius
- **Score 1-5:** How bad is it if this step fails?
- 1 = Internal log error, no customer impact
- 2 = Minor inconvenience, easily correctable
- 3 = Customer-visible error, requires human follow-up
- 4 = Financial impact, account-level consequences
- 5 = Regulatory violation, safety risk, irreversible harm

**Scoring inputs:** `error_consequence`, `customer_facing`, `data_sensitivity`, `risk.regulatory_environment`

### 3.2 Reversibility
- **Score 1-5:** Can you undo the damage?
- 1 = Fully reversible (draft review before send)
- 2 = Mostly reversible (can correct within minutes)
- 3 = Partially reversible (requires manual intervention)
- 4 = Difficult to reverse (customer already impacted)
- 5 = Irreversible (financial transaction, data deletion, sent communication)

**Scoring inputs:** `reversible` flag, `type` (ai_action with tools = higher risk)

### 3.3 Frequency
- **Score 1-5:** How often does this step execute?
- 1 = < 10/day
- 2 = 10-100/day
- 3 = 100-1,000/day
- 4 = 1,000-10,000/day
- 5 = > 10,000/day

**Scoring inputs:** `volume.requests_per_day`, step position in workflow (every request hits intake, fewer hit escalation)

### 3.4 Verifiability
- **Score 1-5:** How hard is it to verify correctness?
- 1 = Trivially verifiable (binary pass/fail)
- 2 = Straightforward check (lookup against known data)
- 3 = Requires domain knowledge to verify
- 4 = Requires contextual judgment (sentiment, tone)
- 5 = Unverifiable without end-user feedback

**Scoring inputs:** `type` (classification = more verifiable, generation = less), `customer_facing`

### 3.5 Cascading Risk
- **Score 1-5:** If this step fails, how many downstream steps are affected?
- Based on dependency graph: count downstream dependents

**Scoring inputs:** `depends_on` relationships, step graph topology

### Composite Risk Score

Each step gets a composite score: `(blast_radius × 2 + reversibility × 2 + frequency + verifiability + cascading_risk) / 8`

Weighted toward blast radius and reversibility because those are the dimensions that matter most for production deployment decisions.

Steps scoring > 3.5 get flagged as **"human checkpoint recommended"**
Steps scoring > 4.0 get flagged as **"human checkpoint required"**

---

## 4. Failure Mode Mapping

Each workflow step is analyzed for susceptibility to Nate's six failure types:

### 4.1 Failure Taxonomy

| Failure Type | Description | Susceptible Step Types | Detection Method |
|---|---|---|---|
| Context Degradation | Quality drops as context window fills | Multi-turn conversations, long sessions | Monitor output quality over session length |
| Specification Drift | Agent forgets the original spec over time | Long-running agents, multi-step workflows | Periodic spec re-injection, output comparison |
| Sycophantic Confirmation | Agent confirms incorrect data and builds on it | Data lookup + generation chains | Cross-reference outputs against source data |
| Tool Selection Error | Agent picks wrong tool or uses tool incorrectly | Steps with multiple tools available | Tool call logging, expected-tool assertions |
| Cascading Failure | One step's error propagates through chain | Any step with downstream dependents | Per-step validation gates |
| Silent Failure | Output looks correct but isn't functionally correct | Customer-facing generation, action steps | Functional correctness evals (not just semantic) |

### 4.2 Per-Step Failure Mapping

For each step, `failure_mapper.py` identifies which failure types are applicable based on:
- Step `type` (ai_generation is susceptible to context degradation and silent failure)
- Step `tools` (multiple tools = tool selection error risk)
- Step `depends_on` (downstream dependents = cascading failure risk)
- Step `customer_facing` (true = silent failure risk elevated)
- Workflow length (more steps = specification drift risk)

Output: a matrix of steps × failure types with risk levels (low/medium/high) and recommended mitigations.

---

## 5. Human Checkpoint Recommendations

`checkpoint_recommender.py` uses the risk scores and failure mappings to recommend where humans should be in the loop:

### Recommendation Types

| Type | When | Example |
|---|---|---|
| **Pre-flight review** | Before an irreversible action | Human reviews password reset before execution |
| **Sampling audit** | High-volume, lower-risk steps | Review 5% of AI-generated responses daily |
| **Escalation trigger** | Confidence below threshold | Route to human if sentiment score < 0.7 |
| **Post-action verification** | After customer-facing output | Review flagged interactions within 1 hour |
| **Periodic calibration** | Evaluation drift over time | Weekly eval review, monthly spec refresh |

### Recommendation Logic

```
IF blast_radius >= 4 AND reversible == false:
    → "Pre-flight review REQUIRED"
    
IF customer_facing == true AND verifiability >= 4:
    → "Sampling audit recommended (suggest 5-10% sample rate)"
    
IF step has branches AND error_consequence mentions "false negative":
    → "Escalation trigger: add confidence threshold gate"
    
IF composite_risk > 3.5:
    → "Human checkpoint recommended — review step design"
    
IF workflow length > 5 steps:
    → "Periodic calibration: spec re-injection every N steps"
```

---

## 6. Cost Calculator

`cost_calculator.py` computes the total cost of running the workflow at scale.

### Token Cost Model

For each step with a model:
```
step_cost = (estimated_tokens_in × input_price_per_token) + (estimated_tokens_out × output_price_per_token)
daily_cost = step_cost × daily_volume_for_step
monthly_cost = daily_cost × 30
annual_cost = daily_cost × 365
```

With growth projection:
```
month_N_daily_volume = base_volume × (1 + growth_rate)^N
```

### Model Pricing Database

**File: `models/model_pricing.yml`** (updated regularly)

```yaml
# Prices per 1M tokens as of March 2026
anthropic:
  claude-opus-4-6:
    input: 15.00
    output: 75.00
  claude-sonnet-4-20250514:
    input: 3.00
    output: 15.00
  claude-haiku-4-5:
    input: 0.80
    output: 4.00

openai:
  gpt-4o:
    input: 2.50
    output: 10.00
  gpt-4o-mini:
    input: 0.15
    output: 0.60

# Add more as needed
```

### Infrastructure Cost Model

Snowflake costs (if applicable):
```
snowflake_daily = estimated_credits_per_day × credit_price
snowflake_monthly = snowflake_daily × 30
```

Other services:
```
other_monthly = sum(service.monthly_cost for service in other_services)
```

### Total Cost Output

```
total_monthly = token_monthly + snowflake_monthly + other_monthly
cost_per_request = total_monthly / (requests_per_day × 30)
```

### Cost Optimization Recommendations

The calculator should also suggest:
- Steps where a cheaper model could work (e.g. "classify intent uses Sonnet but Haiku would suffice based on task complexity")
- Steps where caching could reduce token consumption (e.g. "order status lookup returns same data for same order — cache for 5 minutes")
- Snowflake credit optimization tie-in (e.g. "data lookups supporting this workflow could run on DuckDB instead of Snowflake — saving N credits/day")

---

## 7. Claude API Enrichment (Optional)

If an Anthropic API key is configured, `claude_enricher.py` sends the workflow description to Claude for enhanced analysis:

**Prompt:**
```
You are an AI systems architect reviewing a production AI workflow for risk and quality.

WORKFLOW:
{workflow_yaml}

RULE-BASED ASSESSMENT:
{engine_output}

Enhance this assessment:
1. Identify failure modes the rule-based engine may have missed
2. Suggest specific eval criteria for each step (what does "correct" look like?)
3. Recommend specific guardrail implementations (not just "add a guardrail")
4. Identify any steps where the model choice seems mismatched to task complexity
5. Flag any implicit assumptions in the workflow that could cause silent failures

Output as structured JSON matching the assessment schema.
```

This enrichment is additive — the core assessment works without it. But it turns a rule-based report into a judgment-enriched report, which is the difference between "here's what the tool found" and "here's what an expert would say."

---

## 8. Evidence BI Report

### Executive Summary (`evidence/pages/index.md`)

Top-level findings:
- Workflow risk score (composite across all steps)
- Number of steps requiring human checkpoints
- Number of high-risk failure modes identified
- Estimated monthly cost at current volume
- Estimated monthly cost at 12-month projected volume
- Top 3 recommendations by impact

### Workflow Map (`evidence/pages/workflow-map.md`)

- Visual step-by-step diagram (Mermaid or Evidence chart)
- Each step annotated with: risk score, recommended checkpoint type, primary failure mode
- Color coding: green (low risk), yellow (medium), red (high), purple (human checkpoint)

### Failure Modes (`evidence/pages/failure-modes.md`)

- Matrix: steps × failure types with risk levels
- For each high-risk combination: specific mitigation recommendation
- Examples of what the failure would look like in this workflow

### Checkpoints (`evidence/pages/checkpoints.md`)

- Table of recommended human checkpoints with justification
- Estimated volume of human reviews per day (so client can staff appropriately)
- Sampling rate recommendations for audit-based checkpoints

### Cost Analysis (`evidence/pages/cost-analysis.md`)

- Token cost breakdown by step and model
- Infrastructure cost breakdown
- Total monthly cost with growth projection chart (12 months)
- Cost per request
- Model optimization suggestions
- Snowflake ↔ DuckDB savings opportunity (if Snowflake is in the stack)

### Recommendations (`evidence/pages/recommendations.md`)

- Prioritized list of recommendations (high/medium/low impact)
- Each recommendation includes: what to change, why, estimated effort, estimated cost impact
- Grouped by category: guardrails, evals, cost optimization, architecture

---

## 9. Pre-Built Examples

### `examples/customer_support_agent.yml`
Nate's exact example from the video: tier 1 tickets, password resets, order status, returns, sentiment-based escalation. The reference workflow for demos and blog content.

### `examples/content_generation_pipeline.yml`
Marketing team using AI to draft blog posts, social media, email campaigns. Lower blast radius but high volume, brand risk concerns.

### `examples/data_enrichment_system.yml`
Sales team enriching CRM records with AI-generated firmographic data. Connects to the Salesforce/HubSpot world.

### `examples/sales_outreach_agent.yml`
AI drafting personalized sales emails based on prospect research. Connects to the GTM engine work. Tool selection risk is high (which CRM field to update, which email to send).

### `examples/internal_knowledge_qa.yml`
RAG-based internal Q&A system. Context architecture risk is dominant. Silent failure (plausible but wrong answer) is the primary concern. Directly relevant to internal knowledge base systems.

---

## 10. Build Order

### Session 1: Config Parser + Risk Engine
1. Scaffold repo structure
2. Implement `workflow.example.yml` schema and parser
3. Implement `risk_scorer.py` — five dimension scoring
4. Implement `failure_mapper.py` — six failure type mapping
5. Test against `customer_support_agent.yml` example

### Session 2: Checkpoints + Cost Calculator
1. Implement `checkpoint_recommender.py` — recommendation logic
2. Implement `cost_calculator.py` — token + infrastructure costs
3. Build `model_pricing.yml` with current prices
4. Test full pipeline: config → risk → failures → checkpoints → costs
5. Output to JSON + CSVs

### Session 3: Evidence Report
1. Scaffold Evidence project
2. Build each report page
3. Wire up data sources
4. Test with all five example workflows
5. Style to match FDS brand

### Session 4: Claude Enrichment + Polish
1. Implement `claude_enricher.py` (optional enhancement)
2. Write README, METHODOLOGY.md, FAILURE_TAXONOMY.md
3. Polish examples
4. Security audit
5. Make repo public






---

## 11. Relationship to Nate's Seven Skills

This tool is a **demonstrable artifact for skills 2, 4, 5, and 7:**

| Nate's Skill | How This Tool Demonstrates It |
|---|---|
| Evaluation & Quality Judgment | The tool IS an eval framework for AI workflows |
| Failure Pattern Recognition | The failure taxonomy is the core analytical engine |
| Trust & Security Design | Checkpoint recommendations are trust boundary design |
| Cost & Token Economics | The cost calculator with Snowflake integration |

Building this tool in public (Apache 2.0) is the social proof that you have these skills. The blog post about it is the content that gets you found by hiring managers and prospects who are looking for exactly these capabilities.

---

## 13. Dependencies

```
# requirements.txt
pyyaml>=6.0
pydantic>=2.0          # Config validation
networkx>=3.0          # Step graph / dependency analysis
anthropic>=0.40.0      # Optional: Claude enrichment
```

Evidence BI has its own npm dependencies.
