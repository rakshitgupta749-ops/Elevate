# Elevate: Structured Persona & World Model Architecture (Phase 2)

## 1. Overview & Rationale

Prior to Phase 2, Elevate represented simulated conversational counterparts through unstructured Markdown files (`CTO.md`, `CEO.md`, etc.). While functional for basic role-play prompts, static text files presented severe architectural limitations for enterprise simulation:
1. **No Programmatic Querying**: Behavioral rules, state engines, and rubric evaluators cannot inspect or adjust unstructured text.
2. **Omniscient LLM Hallucinations**: Without explicit epistemic boundaries, personas frequently answer out-of-role questions or expose unrealistic technical or commercial knowledge.
3. **Fragile Prompt String Interpolation**: Prompts mixed the stakeholder's identity with their company environment and scenario constraints into a single uncontrolled block.

Phase 2 replaces the legacy pattern:
```text
role_id → raw Markdown (.md) → unstructured system prompt
```
with a strongly typed data foundation:
```text
role_id → EnterprisePersona + CompanyContext (World Model) → structured system prompt
```

---

## 2. Separation: Persona vs. World Model

A fundamental architectural principle of Elevate is the separation of **WHO** from **WHERE**:

* **Persona (`PersonaProfile`, `ValueOrientation`, `StakeholderGoal`, `Incentive`, `KnowledgeBoundary`)**:
  Represents the internal identity, values, goals, personal incentives, and epistemic boundaries of the simulated human stakeholder. A persona can be transplanted across different companies or interview scenarios while maintaining behavioral integrity.
* **World Model (`CompanyContext`)**:
  Represents the operating environment: company scale, existing technology stack, incumbent software vendors, commercial constraints, budget limits, pain points, and current strategic initiatives.

---

## 3. Core Model Concepts

### 3.1 Values (`ValueOrientation`)
Values define what the stakeholder prioritizes when evaluating proposals, candidates, or products (e.g., `reliability`, `security`, `cost`, `scalability`, `culture fit`).
> [!IMPORTANT]
> **Simulation Parameters, Not Psychometrics**  
> Numerical weights (`0.0 <= weight <= 1.0`) in `ValueOrientation` and `Incentive` are **simulation configuration weights**. They govern how strongly the LLM emphasizes specific criteria during questioning. They are **NOT** psychometric test scores or psychological diagnostic measures.

### 3.2 Goals (`StakeholderGoal`)
Structured evaluation objectives held by the stakeholder (e.g., `verify_architectural_fit`, `validate_financial_payback`). Each goal contains:
* `id`: Unique programmatic identifier.
* `priority`: Relative importance in the conversation.
* `type`: Categorical domain (`technical`, `business`, `financial`, `risk`, `personal`, `procurement`).
* `success_condition`: Explicit condition required for the stakeholder to consider the goal satisfied.
* `dealbreaker`: Boolean indicating if failure on this goal terminates the deal/interview.

### 3.3 Incentives (`Incentive`)
Incentives capture the pressures and motivations driving stakeholder reactions:
* **Organizational**: e.g., protecting system uptime, meeting quarterly revenue targets.
* **Personal / Professional**: e.g., minimizing developer on-call burnout, career reputation.
* **Political**: e.g., defending technology standards, navigating inter-departmental friction.

### 3.4 Knowledge Boundaries (`KnowledgeBoundary`)
Explicit epistemic barriers that prevent unrealistic omniscient LLM behavior:
* `expert_topics`: Domains where the persona speaks with authoritative depth.
* `known_topics`: Domains the persona understands at a competent operational level.
* `limited_topics`: Topics the persona has only secondhand awareness of.
* `unknown_topics`: Topics explicitly out-of-bounds for the role.
* `confidential_topics`: Sensitive internal information the persona will not disclose.
* `disclosure_rules`: Rules governing when confidential details may be shared.

---

## 4. How to Add a New Persona

To add a new enterprise persona (e.g., `CIO`, `CFO`, `PROCUREMENT_HEAD`):

1. Open [`backend/app/roles/registry.py`](file:///home/labuser/Desktop/Project/Elevate/backend/app/roles/registry.py).
2. Define a builder function returning an `EnterprisePersona` instance:
   ```python
   def _build_cfo_persona() -> EnterprisePersona:
       return EnterprisePersona(
           profile=PersonaProfile(
               role="CFO",
               title="Chief Financial Officer",
               department="Finance",
               seniority="Executive (C-Suite)",
               years_of_experience=20,
               industry_expertise=["SaaS Finance", "Unit Economics"],
               technical_depth="Financial / Non-Technical",
               communication_style="Direct, skeptical, ROI-focused",
               personality_characteristics=["Analytical", "Meticulous"],
               risk_profile="Fiduciary Conservative",
           ),
           values=[
               ValueOrientation(name="cost", weight=0.95, description="Minimizes software OpEx", priority=1),
               ValueOrientation(name="margin", weight=0.90, description="Protects EBITDA margin", priority=2),
           ],
           goals=[
               StakeholderGoal(
                   id="verify_roi",
                   description="Confirm payback period under 12 months",
                   priority=0.95,
                   type="financial",
                   success_condition="Vendor presents audited ROI model",
                   dealbreaker=True,
               )
           ],
           incentives=[
               Incentive(id="protect_free_cash_flow", description="Hit quarterly EBITDA", importance=0.95, category="organizational")
           ],
           knowledge_boundary=KnowledgeBoundary(
               expert_topics=["Corporate finance", "Unit economics", "Tax compliance"],
               unknown_topics=["Low-level code implementation"],
               confidential_topics=["Unallocated cash reserves"],
           ),
           world_model=CompanyContext(
               industry="Enterprise SaaS",
               company_size="3,000 employees",
           )
       )
   ```
3. Register the persona in the `_PERSONA_REGISTRY` dictionary:
   ```python
   _PERSONA_REGISTRY["CFO"] = _build_cfo_persona()
   ```
4. The persona is now immediately accessible to `RoleAgent`, `POST /api/session`, and the test suite without any additional glue code.

---

## 5. Scope Boundaries: What is NOT in Phase 2

To maintain clean architectural boundaries, Phase 2 is strictly a **data modeling phase**.

The following capabilities are intentionally **NOT IMPLEMENTED YET**:
* **NO Dynamic Psychological State**: Trust, skepticism, and patience meters are not yet updated per-turn.
* **NO Behavioral Policy Selection**: The system does not yet dynamically choose actions (e.g. `ChallengeMetric`, `Interrupt`, `Concede`).
* **NO Adaptive Interviewing / Difficulty Escalation**: Difficulty does not yet automatically ramp up or down based on candidate answers.
* **NO Real-Time Candidate Analysis**: Responses are not yet classified for evasiveness or evidence citation.
* **NO Independent Evaluator Refactoring**: Post-interview judging remains in its current location until Phase 10.

These systems will be introduced cleanly in subsequent phases, utilizing the structured data foundation established here.
