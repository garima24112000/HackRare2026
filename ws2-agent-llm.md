# WORKSTREAM 2: Agent Pipeline + LLM Extraction Tools

**Owner:** Person B (can pair with Person D on extraction components)
**Time:** ~22 hours (most complex workstream — start immediately)
**Dependencies:** WS1's `load_all()` and tool functions (available by hour 6)
**Branch:** `ws2-agent`

---

## What You Deliver

1. `tools/excluded_extract.py` — LLM-powered negated phenotype extraction (Comp A)
2. `tools/timing_extract.py` — LLM-powered onset/timing extraction (Comp B)
3. `agent/prompts/` — All prompt files (excluded, timing, final reasoning)
4. `agent/pipeline.py` — The main orchestrator function that calls all tools in order and produces `AgentOutput`
5. Optionally: `tools/reanalysis.py` — Reanalysis trigger scoring

---

## Core Design Principle

**The LLM never generates medical facts.** It does two things only:
1. **Extract** structured information from unstructured clinical text (Comp A, Comp B)
2. **Synthesize** a recommendation by reasoning over structured facts already retrieved by programmatic tools (Final Reasoning Call)

Every LLM call uses a focused, single-purpose prompt stored in a separate `.txt` file. Prompts are swappable without touching any Python code.

---

## Phase 2A: LLM Client Setup (Hours 0–1)

### Anthropic Client

Create a simple helper that all LLM-powered tools use. Put this at the top of each tool file or in a shared utility.

Use the `anthropic` Python SDK directly (not through LangChain). This is simpler and gives you more control over the prompt.

- Import `anthropic.Anthropic`
- Initialize with `api_key` from `core/config.py`
- Every LLM call uses model `"claude-sonnet-4-20250514"`
- Every LLM call sets `max_tokens=2000`
- Every LLM call includes a system message and a user message
- Every LLM call expects JSON output — include "Return ONLY valid JSON. No markdown, no preamble." in the prompt

**Error handling pattern for all LLM calls:**
- Wrap in try/except
- If the response isn't valid JSON, try to extract JSON from the response by finding the first `[` or `{` and the last `]` or `}`
- If that still fails, return an empty list (for extraction tools) or a minimal default output (for final reasoning)
- Always log the raw response on failure for debugging

---

## Phase 2B: Excluded Phenotype Extractor — Component A (Hours 1–5)

### File: `tools/excluded_extract.py`

**Function:** `run(note_text: str, synonym_index: dict) → list[ExcludedFinding]`

### Prompt: `agent/prompts/excluded.txt`

Write this prompt with the following instructions to the LLM:

**Role:** You are a clinical NLP specialist focused on identifying negated medical findings.

**Task:** Given a clinical note, find ALL explicitly negated or ruled-out clinical findings.

**What counts as negation:**
- Direct negation: "no seizures", "denies hearing loss", "without ataxia"
- Ruled out: "seizures ruled out", "cardiac defect excluded"
- Normal findings: "reflexes normal", "hearing intact", "MRI showed no abnormalities"
- Absent features: "absent deep tendon reflexes", "no evidence of regression"

**What does NOT count:**
- Missing information (symptom simply not mentioned ≠ negated)
- Family history negations: "no family history of seizures" — this is about the family, not the patient. SKIP these.
- Resolved symptoms that were once present: "seizures resolved after treatment" — this was present, now resolved. This is a TIMING issue, not an exclusion. SKIP these.

**Output format:** JSON array of objects, each with:
- `raw_text`: the exact phrase from the note containing the negation
- `finding`: the clinical finding being negated, using medical terminology as close to HPO naming as possible (e.g., "Seizures" not "fits", "Hearing impairment" not "deaf")
- `exclusion_type`: "explicit" if clearly negated, "soft" if uncertain
- `confidence`: "high" if clear negation, "medium" if somewhat ambiguous

**If no negations found:** Return an empty JSON array `[]`.

**Strict instruction:** Return ONLY the JSON array. No explanation, no markdown fences, no preamble.

### Post-processing logic in the Python function:

1. Read the prompt from `agent/prompts/excluded.txt`.
2. Call the Anthropic API with system=prompt_text and user=note_text.
3. Parse the response as JSON. Handle parse failures gracefully (see error pattern above).
4. For each item in the parsed list:
   a. Take the `finding` string, lowercase it
   b. Look it up in `synonym_index` (exact match first)
   c. If no exact match, use `rapidfuzz.process.extractOne()` with `score_cutoff=80`
   d. If match found, set `mapped_hpo_term` and `mapped_hpo_label`
   e. If no match, leave them as None — the finding is noted but unmapped
5. Build and return a list of `ExcludedFinding` objects.

### Testing:

Create a test clinical note string that contains at least 3 negations:
- "Patient is a 5-year-old male. No seizures have ever been reported. Hearing was tested and confirmed normal. Deep tendon reflexes are absent. No family history of cardiac disease. Developmental milestones were appropriate until age 2."

Expected output: 3 ExcludedFinding objects (seizures, hearing impairment, deep tendon reflexes). The family history line should NOT produce an exclusion. The developmental milestone line is not a negation.

---

## Phase 2C: Onset & Timing Extractor — Component B (Hours 1–5)

### File: `tools/timing_extract.py`

**NOTE:** Person D can build this in parallel with you building Comp A. They use the same LLM client pattern, just a different prompt.

**Function:** `run(note_text: str, hpo_labels: list[str]) → list[TimingProfile]`

The `hpo_labels` parameter is a list of HPO term labels (strings like "Seizures", "Hypotonia") that have already been identified for this patient. The extractor should try to link temporal expressions to these specific phenotypes.

### Prompt: `agent/prompts/timing.txt`

**Role:** You are a clinical temporal reasoning specialist.

**Task:** Given a clinical note and a list of known patient phenotypes, extract timing information for each phenotype where timing is mentioned or inferable.

**What to extract for each phenotype:**
- `phenotype_ref`: which phenotype from the provided list this timing applies to
- `onset`: the age or period description as stated in the note (e.g., "at birth", "age 4 months", "around age 2")
- `onset_normalized`: convert to decimal years (birth=0.0, 6 months=0.5, 18 months=1.5, 3 years=3.0, etc.)
- `resolution`: if the symptom resolved, when (null if ongoing)
- `is_ongoing`: true if the symptom is currently present, false if resolved
- `progression`: one of "stable", "progressive", "improving", "episodic"
- `raw_evidence`: the exact sentence or phrase from the note you're basing this on

**Handling relative time references:**
- "since birth" / "congenital" / "neonatal" → onset_normalized = 0.0
- "in infancy" / "as an infant" → onset_normalized = 0.5
- "as a toddler" → onset_normalized = 2.0
- "since starting school" / "preschool" → onset_normalized = 5.0
- "in childhood" → onset_normalized = 6.0
- "as a teenager" / "adolescence" → onset_normalized = 13.0
- "in adulthood" → onset_normalized = 20.0

**Only extract timing for phenotypes in the provided list.** If the note mentions a symptom not in the list, skip it. If a phenotype in the list has no timing information in the note, skip it.

**Output:** JSON array. Return ONLY JSON, no preamble.

### Post-processing logic:

1. Read prompt from file. Format it by appending the list of known phenotype labels.
2. Call Anthropic API with system=prompt_text and user=note_text.
3. Parse JSON response.
4. For each item, apply onset_stage normalization:
   - onset_normalized 0.0 → onset_stage "Congenital/Neonatal"
   - 0.0 to 1.0 → "Infantile"
   - 1.0 to 5.0 → "Childhood"
   - 5.0 to 15.0 → "Juvenile"
   - over 15.0 → "Adult"
5. Build and return list of `TimingProfile` objects.

### Testing:

Test note: "Hypotonia was noted since birth. Seizures began at 4 months of age. Speech delay was identified at the 18-month checkup. Walking was achieved at 28 months but gait has progressively worsened over the past 2 years."

With hpo_labels: ["Hypotonia", "Seizures", "Speech delay", "Gait disturbance"]

Expected: 4 TimingProfile objects with onset_normalized values approximately 0.0, 0.33, 1.5, and 2.33 (walking at 28 months). Gait should have progression="progressive".

---

## Phase 2D: The Main Pipeline — `agent/pipeline.py` (Hours 5–15)

### Function: `async run_pipeline(patient_input: PatientInput, data: dict, session_mgr: SessionManager) → AgentOutput`

This is the single most important function in the entire project. Everything converges here.

### Design Decision: Simple Async Function Chain (NOT LangGraph)

For hackathon reliability, implement this as a straightforward async function — NOT a LangGraph state machine. Here's why:
- LangGraph adds complexity without adding value for a demo with a fixed tool order
- A simple function is easier to debug at 3am during a hackathon
- Chainlit integration is simpler (WS3 just awaits this function)
- The "agentic" story is preserved — the pipeline still calls tools autonomously, reasons over context, and adapts based on what it finds

If there's time after the core pipeline works, refactoring to LangGraph is a clean upgrade path because the tool contracts don't change.

### Pipeline Step Sequence:

**Step 0: Initialize**
- Generate a session_id (uuid4 string)
- Call `session_mgr.create_session(session_id, patient_input.model_dump())`
- Initialize an empty tool_call_log list
- Initialize a `step_callback` parameter (optional) — WS3 will pass a callback function that gets called after each step so Chainlit can display progress. If no callback, steps just run silently.

**Step 1: Red Flag Check (ALWAYS FIRST)**
- Call `red_flag.run(patient_input.hpo_terms, data["ontology"])`
- Log the tool call to session_mgr and to tool_call_log
- If any flag has severity "URGENT": build a minimal AgentOutput with only red_flags populated and return immediately. Do not proceed with further analysis.
- If callback provided, call it with step name "Red Flag Check" and the result.

**Step 2: HPO Mapping**
- Determine what needs mapping:
  - If `patient_input.hpo_terms` is non-empty, run those through hpo_lookup to get enriched HPOMatch objects (these are already HPO IDs so they'll hit the direct ID path)
  - If `patient_input.free_text` is non-empty, extract symptom phrases and run them through hpo_lookup too
  - For free text extraction: split on common delimiters (commas, semicolons, periods, "and") and pass each chunk. This is a rough heuristic — good enough for hackathon.
- Merge results into one list of HPOMatch objects. Deduplicate by hpo_id.
- Log tool call.
- If callback provided, call it.

**Step 3: Disease Matching**
- Collect all valid hpo_ids from the HPOMatch list (where hpo_id is not empty)
- Collect excluded HPO IDs — initially empty (will be populated in step 4, but for this first pass, use empty)
- Call `disease_match.run(hpo_ids, [], data)`
- Log tool call.
- If callback provided, call it.

**Step 4: Phenotype Extraction (Comp A + Comp B) — ONLY if free_text is present**
- If `patient_input.free_text` is None or empty, skip this step. Set excluded=[] and timing=[].
- Otherwise, run both extractors:
  - `excluded_extract.run(patient_input.free_text, data["synonym_index"])`
  - `timing_extract.run(patient_input.free_text, [h.label for h in hpo_matches])`
  - Run these concurrently using `asyncio.gather()` if both tools are async, or sequentially if sync. Either is fine for hackathon.
- Log both tool calls.
- If callback provided, call it.

**Step 4b: Re-run Disease Match with exclusions (OPTIONAL — do if time)**
- If excluded findings were found in step 4, re-run disease_match with the excluded HPO IDs
- This refines the ranking by penalizing diseases whose cardinal features are explicitly absent
- If no time for this, just use the original ranking from step 3

**Step 5: Disease Profile Fetch**
- Take the top 5 disease_ids from the disease match results
- Call `orphanet_fetch.run(top_5_ids, data)`
- Log tool call.
- If callback provided, call it.

**Step 6: Compute Data Completeness**
- Compute a float between 0.0 and 1.0:
  - `hpo_weight = 0.30`: 1.0 if >= 3 HPO terms, 0.5 if 1-2, 0.0 if none
  - `timing_weight = 0.20`: fraction of HPO terms that have timing info
  - `exclusion_weight = 0.15`: 1.0 if any exclusions found, 0.0 if none
  - `test_weight = 0.20`: 1.0 if prior_tests provided, 0.0 if not
  - `family_weight = 0.15`: 1.0 if family_history provided, 0.0 if not
  - completeness = sum of (weight × value) for each component

**Step 7: Final Reasoning Call (LLM)**
- Assemble a context packet (plain dict) containing:
  - patient_hpo_matches (list of dicts from HPOMatch objects)
  - excluded_findings (list of dicts)
  - timing_profiles (list of dicts)
  - disease_candidates top 10 (list of dicts)
  - disease_profiles (list of dicts, from Orphanet fetch)
  - data_completeness score
  - red_flags (list, may be empty)
  - prior_tests from patient_input (if any)
  - family_history from patient_input (if any)
  - patient age and sex

- Store the context packet in Redis: `session_mgr.set_context(session_id, context_packet)`

- Read the final reasoning prompt from `agent/prompts/final_reasoning.txt`

- Call the Anthropic API with:
  - system: the final reasoning prompt
  - user: the context packet serialized as a formatted JSON string
  - Ask the LLM to return a JSON object matching the AgentOutput schema

- Parse the response into an `AgentOutput` Pydantic model
- If parsing fails, build a fallback AgentOutput from the raw tool outputs (at minimum, populate differential from disease_match results, and next_best_steps with a generic "refine_phenotype" recommendation)

- Store the final output in Redis: `session_mgr.set_output(session_id, output.model_dump())`

- Return the AgentOutput

### Prompt: `agent/prompts/final_reasoning.txt`

**Role:** You are a rare disease diagnostic consultant. You are NOT a diagnostician — your job is to recommend the next best diagnostic action, not make a final diagnosis.

**Context:** You will receive a JSON context packet containing all data gathered by the diagnostic pipeline's tools. This data comes from verified medical databases (HPO, OMIM, Orphanet). You must reason ONLY over this data — do not introduce disease facts not present in the context.

**Task:** Produce a JSON object with these fields:

`differential` — array of top 5 disease entries. For each:
- `disease`: name, `disease_id`: ID
- `confidence`: "high" if 4+ supporting features and no contradictions, "moderate" if 2-3 supporting features, "low" if weak evidence
- `confidence_reasoning`: one sentence explaining why this confidence level
- `supporting_phenotypes`: which patient HPO terms support this disease (use labels)
- `contradicting_phenotypes`: which excluded findings contradict this disease
- `missing_key_phenotypes`: which high-frequency disease features the patient hasn't been assessed for

`next_best_steps` — array of 3-5 ranked recommendations. For each:
- `rank`: 1 to 5
- `action_type`: one of "order_test", "refine_phenotype", "genetic_testing", "reanalysis", "refer_specialist", "urgent_escalation"
- `action`: specific action description (e.g., "Order echocardiogram", "Assess for intellectual disability")
- `rationale`: why this is recommended, referencing specific diseases it would discriminate between
- `discriminates_between`: list of disease names this step helps distinguish
- `urgency`: "urgent" or "routine" or "low"
- `evidence_source`: which tool provided the evidence for this recommendation

**CRITICAL RULES:**
1. If `data_completeness` is below 0.4, the TOP recommendation MUST be action_type "refine_phenotype" — the system needs more data before recommending tests.
2. Next-best-steps should DISCRIMINATE between top candidates, not just confirm the leading one.
3. If excluded phenotypes contradict the top candidate, mention this explicitly in confidence_reasoning.

`what_would_change` — array of 3-5 strings describing specific findings that would shift the recommendation. Each should be concrete: "If echocardiogram shows pulmonary stenosis, Noonan syndrome moves to high confidence." Not vague: "More data would help."

`uncertainty` — object with:
- `known`: list of things confidently established (e.g., "Seizures explicitly excluded")
- `missing`: list of things not yet assessed (e.g., "Cardiac imaging not done")
- `ambiguous`: list of things unclear (e.g., "Family history of 'heart problems' — insufficient to classify")

**Output:** Return ONLY the JSON object. No markdown, no explanation, no code fences.

---

## Phase 2E: Reanalysis Trigger (Hours 18–22, OPTIONAL)

### File: `tools/reanalysis.py`

**Function:** `run(prior_test: dict, candidate_genes: list[str], patient_hpo_ids: list[str]) → ReanalysisResult`

**Only build this if the core pipeline (steps 1-7) is fully working and tested.**

**Simplified approach for hackathon:**
- Don't download full ClinVar (2GB). Instead, implement a rule-based scorer.
- Score components (additive, cap at 1.0):
  - +0.35 if the test is more than 3 years old (gene-disease knowledge doubles roughly every 3 years)
  - +0.25 if the test type is "gene_panel" (panels miss many genes vs exome/genome)
  - +0.20 if the patient has 5+ HPO terms added since the test date (new phenotypes = new filtering criteria)
  - +0.20 if any candidate diseases from the differential are associated with genes not typically on older panels
- Generate a recommendation string and reasons list based on which score components contributed.
- Optionally, use a brief LLM call to write a one-paragraph clinician-readable summary of the reasons.

---

## Integration Testing (Hours 15–18)

Test the full pipeline end-to-end before WS3 integration:

1. **HPO-only test:** Create a PatientInput with just `hpo_terms` from Patient 10: `["HP:0002360", "HP:0100704", "HP:0001250", "HP:0001252", "HP:0001332"]`. Run the pipeline. Verify: AgentOutput has a non-empty differential with OMIM:300672 in top 10. next_best_steps has at least one entry. data_completeness is between 0.2-0.5 (no free text, no timing, no exclusions).

2. **Free text test:** Create a PatientInput with `free_text` containing a synthetic clinical note with negations and timing information. Verify: excluded findings are populated, timing profiles are populated, differential accounts for exclusions.

3. **Red flag test:** Create a PatientInput with hpo_terms including "HP:0002133" (status epilepticus). Verify: pipeline returns early with URGENT red flag, no disease matching performed.

4. **Sparse input test:** Create a PatientInput with just 1 HPO term. Verify: data_completeness is low, top recommendation is "refine_phenotype".

---

## Handoff Points

**Hour 5:** Push `tools/excluded_extract.py`, `tools/timing_extract.py`, and all prompts. WS4 can start testing extraction quality.

**Hour 10:** Push `agent/pipeline.py` with at least steps 1-3 working (red flag, HPO mapping, disease match). WS3 can start wiring into Chainlit.

**Hour 15:** Push complete pipeline with final reasoning. WS3 integrates the full output rendering. WS4 can start running evaluation.

---

## Critical Gotchas

1. **JSON parsing from LLM:** Claude sometimes wraps JSON in markdown code fences. Always strip ```json and ``` from the response before parsing.

2. **Empty free_text:** If patient_input.free_text is None, do NOT pass None to the extraction tools. Skip steps 4 entirely.

3. **HPO ID validation:** Some HPO IDs in the patient data may not exist in the ontology. Always check before calling `get_ancestors_up_to_root`.

4. **Prompt file loading:** Read prompt files with `open(..., "r", encoding="utf-8").read()`. Cache the loaded text — don't re-read the file on every pipeline run.

5. **Anthropic rate limits:** If running evaluation (15 patients × multiple LLM calls each), you may hit rate limits. Add a 1-second sleep between pipeline runs in batch mode.
