# WORKSTREAM 0: Shared Contracts & Integration Points

**Purpose:** This document defines every shared interface, data model, file path, and function signature that all 4 workstreams depend on. Build the shared files FIRST. One person creates them, pushes to `main`, everyone pulls before starting their workstream.

**Time:** 30–45 minutes to create all shared files.

---

## Folder Structure (Final)

```
diagnostic-copilot/
├── .env
├── pyproject.toml
├── app.py                          # WS3 — Chainlit entry point
├── hpo_functions.py                # PROVIDED — copy into root
│
├── core/
│   ├── __init__.py
│   ├── config.py                   # Env vars loader
│   ├── models.py                   # ALL Pydantic models (this doc)
│   ├── database.py                 # WS1 — MongoDB singleton
│   ├── data_loader.py              # WS1 — startup hydration
│   └── session_manager.py          # WS1 — Redis session ops
│
├── tools/
│   ├── __init__.py
│   ├── hpo_lookup.py               # WS1
│   ├── disease_match.py            # WS1
│   ├── red_flag.py                 # WS1
│   ├── excluded_extract.py         # WS2
│   ├── timing_extract.py           # WS2
│   ├── orphanet_fetch.py           # WS1
│   └── reanalysis.py              # WS2 (optional)
│
├── agent/
│   ├── __init__.py
│   ├── pipeline.py                 # WS2 — main orchestrator
│   └── prompts/
│       ├── excluded.txt            # WS2
│       ├── timing.txt              # WS2
│       └── final_reasoning.txt     # WS2
│
├── scripts/
│   ├── ingest_hpo.py               # WS1
│   ├── ingest_diseases.py          # WS1
│   └── ingest_patients.py          # WS1
│
├── eval/
│   ├── gold_cases.py               # WS4
│   ├── score.py                    # WS4
│   └── robustness.py              # WS4
│
└── data/raw/
    ├── hp.obo
    ├── phenotype.hpoa
    └── en_product4.xml
```

---

## File: `core/config.py`

Single responsibility: load environment variables from `.env` and expose them as module-level constants.

**Constants to expose:**
- `MONGODB_URI` — connection string for MongoDB Atlas
- `REDIS_URL` — connection string for Redis Cloud
- `ANTHROPIC_API_KEY` — Claude API key
- `OMIM_API_KEY` — optional, empty string default
- `DB_NAME` — hardcoded to `"diagnostic_copilot"`

Use `python-dotenv` `load_dotenv()` at module import time.

---

## File: `core/models.py`

This is the single source of truth for ALL data models across the project. Every workstream imports from here. No workstream defines its own models.

### Models to define (all Pydantic BaseModel):

**`HPOMatch`** — Output of HPO Lookup Tool
- `hpo_id`: str (e.g., "HP:0001250")
- `label`: str (e.g., "Seizures")
- `definition`: str or None
- `ic_score`: float, default 0.0
- `parents`: list of str, default empty
- `match_confidence`: Literal "high" | "medium" | "low", default "medium"
- `raw_input`: str, default empty

**`DiseaseCandidate`** — Output of Disease Match Tool
- `rank`: int
- `disease_id`: str
- `disease_name`: str
- `sim_score`: float
- `matched_terms`: list of str, default empty
- `missing_terms`: list of str, default empty (terms in disease but not patient)
- `extra_terms`: list of str, default empty (terms in patient but not disease)
- `coverage_pct`: float, default 0.0
- `excluded_penalty`: bool, default False

**`RedFlag`** — Output of Red Flag Detector
- `flag_label`: str
- `severity`: Literal "URGENT" | "WARNING" | "WATCH"
- `triggering_terms`: list of str
- `recommended_action`: str

**`ExcludedFinding`** — Output of Excluded Phenotype Extractor
- `raw_text`: str (the negation phrase from the note)
- `mapped_hpo_term`: str or None
- `mapped_hpo_label`: str or None
- `exclusion_type`: Literal "explicit" | "soft"
- `confidence`: Literal "high" | "medium" | "low"

**`TimingProfile`** — Output of Onset & Timing Extractor
- `phenotype_ref`: str
- `phenotype_label`: str or None
- `onset`: str (e.g., "at birth", "age 4 months")
- `onset_normalized`: float (age in years, 0.0 = birth)
- `onset_stage`: str (e.g., "Neonatal", "Infantile", "Childhood", "Juvenile", "Adult")
- `resolution`: str or None
- `is_ongoing`: bool, default True
- `progression`: Literal "stable" | "progressive" | "improving" | "episodic"
- `raw_evidence`: str
- `confidence`: Literal "high" | "medium" | "low"

**`PhenotypeFrequency`** — Sub-model for disease profiles
- `hpo_id`: str
- `label`: str
- `frequency`: str (e.g., "95-100%")

**`DiseaseProfile`** — Output of Orphanet/OMIM Fetch
- `disease_id`: str
- `disease_name`: str
- `inheritance`: str or None
- `causal_genes`: list of str
- `phenotype_freqs`: list of PhenotypeFrequency
- `recommended_tests`: list of str

**`ReanalysisReason`** — Sub-model
- `reason_type`: str
- `detail`: str
- `source`: str

**`ReanalysisResult`** — Output of Reanalysis Trigger
- `score`: float (0 to 1)
- `recommendation`: str
- `reasons`: list of ReanalysisReason

**`ToolCallRecord`** — For logging
- `tool_name`: str
- `input_data`: dict
- `output_data`: dict
- `timestamp`: str
- `duration_ms`: int

**`PatientInput`** — Input to the pipeline
- `free_text`: str or None
- `hpo_terms`: list of str, default empty
- `prior_tests`: list of dict or None
- `family_history`: str or None
- `age`: int or None
- `sex`: str or None

**`NextStep`** — Part of final output
- `rank`: int
- `action_type`: Literal "order_test" | "refine_phenotype" | "genetic_testing" | "reanalysis" | "refer_specialist" | "urgent_escalation"
- `action`: str
- `rationale`: str
- `discriminates_between`: list of str
- `urgency`: Literal "urgent" | "routine" | "low"
- `evidence_source`: str

**`DifferentialEntry`** — Part of final output
- `disease`: str
- `disease_id`: str
- `confidence`: Literal "high" | "moderate" | "low"
- `confidence_reasoning`: str
- `supporting_phenotypes`: list of str
- `contradicting_phenotypes`: list of str
- `missing_key_phenotypes`: list of str

**`UncertaintySummary`** — Part of final output
- `known`: list of str
- `missing`: list of str
- `ambiguous`: list of str

**`AgentOutput`** — The complete pipeline output
- `patient_hpo_observed`: list of HPOMatch
- `patient_hpo_excluded`: list of ExcludedFinding
- `timing_profiles`: list of TimingProfile
- `data_completeness`: float
- `red_flags`: list of RedFlag
- `differential`: list of DifferentialEntry
- `next_best_steps`: list of NextStep
- `reanalysis`: ReanalysisResult or None
- `what_would_change`: list of str
- `uncertainty`: UncertaintySummary

---

## Integration Function Signatures (Cross-Workstream Contract)

These are the exact function signatures each workstream must expose. Workstreams can have any internal structure they want, but the entry-point functions must match these signatures exactly.

### WS1 Exposes → WS2, WS3, WS4 Consume

```
core/data_loader.py:
  load_all(db) → dict
    Keys: "hpo_index", "synonym_index", "ic_scores",
          "disease_to_hpo", "disease_ancestors", "disease_to_name",
          "orphanet_profiles", "patients", "ontology"

core/session_manager.py:
  class SessionManager:
    __init__(redis_url: str)
    create_session(session_id: str, raw_input: dict) → None
    log_tool_call(session_id: str, tool_name: str, input_data: dict, output_data: dict) → None
    get_tool_log(session_id: str) → list[dict]
    set_context(session_id: str, context: dict) → None
    get_context(session_id: str) → dict or None
    set_output(session_id: str, output: dict) → None

tools/hpo_lookup.py:
  run(raw_texts: list[str], data: dict) → list[HPOMatch]
    data is the dict from load_all()

tools/disease_match.py:
  run(patient_hpo_ids: list[str], excluded_hpo_ids: list[str], data: dict) → list[DiseaseCandidate]
    Returns top 15, sorted by sim_score descending

tools/red_flag.py:
  run(patient_hpo_ids: list[str], ontology) → list[RedFlag]
    ontology is the pronto Ontology object from data["ontology"]

tools/orphanet_fetch.py:
  run(disease_ids: list[str], data: dict) → list[DiseaseProfile]
```

### WS2 Exposes → WS3, WS4 Consume

```
tools/excluded_extract.py:
  run(note_text: str, synonym_index: dict) → list[ExcludedFinding]

tools/timing_extract.py:
  run(note_text: str, hpo_labels: list[str]) → list[TimingProfile]

agent/pipeline.py:
  async run_pipeline(patient_input: PatientInput, data: dict, session_mgr: SessionManager)
    → AgentOutput
    This is THE main function. Chainlit calls it, eval calls it.
    It calls all tools in order, assembles context, calls final LLM reasoning.
```

### WS3 Consumes (does not expose functions to other workstreams)

```
Calls: pipeline.run_pipeline() on user message
Calls: data_loader.load_all() once at startup
Calls: SessionManager methods for session tracking
Reads: data["patients"] for patient selector buttons
```

### WS4 Consumes

```
Calls: pipeline.run_pipeline() in batch for each test patient
Reads: MongoDB eval_gold_cases collection
Writes: MongoDB eval_results collection
```

---

## Dependency Installation

Everyone runs the same install command at project start. Use either:
- `pip install -e .` (if using pyproject.toml)
- or `pip install langgraph langchain-anthropic anthropic chainlit pronto pandas pymongo redis pydantic python-dotenv rapidfuzz`

---

## Git Workflow

- `main` branch: shared contracts only (models.py, config.py, .env template, pyproject.toml)
- Each person works on their own branch: `ws1-data`, `ws2-agent`, `ws3-ui`, `ws4-eval`
- Merge into `main` at each phase milestone
- Integration testing happens after merges
