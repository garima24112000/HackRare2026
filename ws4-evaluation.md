# WORKSTREAM 4: Evaluation Harness + Gold Cases

**Owner:** Person D
**Time:** ~18 hours (front-loaded with gold case work, back-loaded with scoring)
**Dependencies:** WS2's `pipeline.run_pipeline()` (needed by hour 18 for full eval run; can test scoring logic independently before that)
**Branch:** `ws4-eval`

**Additional role:** Person D also builds Comp B (Onset & Timing Extractor) during hours 1-5 in parallel with Person B building Comp A. See WS2 doc for Comp B specification — follow the exact same function signature and prompt file pattern.

---

## What You Deliver

1. `tools/timing_extract.py` — Onset & Timing Extractor (Component B), following the spec in WS2 doc
2. Gold standard test cases in MongoDB (`eval_gold_cases` collection)
3. 5 synthetic clinical notes (text files) that wrap the HPO-only patient data with negations and timing
4. `eval/gold_cases.py` — script to create and insert gold cases into MongoDB
5. `eval/score.py` — scoring script that runs the pipeline on all test patients and computes metrics
6. `eval/robustness.py` — HPO drop simulation script
7. Evaluation report with numbers ready for the presentation

---

## Phase 4A: Build Comp B (Hours 0–5)

Follow the specification in the WS2 document for `tools/timing_extract.py`. You own this component.

**File:** `tools/timing_extract.py`
**Function:** `run(note_text: str, hpo_labels: list[str]) → list[TimingProfile]`
**Prompt file:** `agent/prompts/timing.txt`

See WS2 doc "Phase 2C" for complete specification of the prompt, post-processing logic, and testing instructions.

**Push this to your branch by hour 5.** Person B will pull it into the pipeline.

---

## Phase 4B: Gold Case Curation (Hours 2–8)

This is the most time-consuming manual work. Do it carefully — the evaluation is only as good as the gold standard.

### Task 1: Assign Difficulty Levels

For each of the 15 patients in `Phenotypic-profiles-Rare-Disease-Hackathon2025.txt`, classify into Easy / Medium / Hard.

**Classification criteria:**

**Easy** (target: 5 patients) — Assign if:
- The disease has a well-known OMIM entry
- The HPO term count is either very low (clear, targeted) or well-matched to a specific disease
- The disease name is recognizable (e.g., craniosynostosis, spastic paraplegia)
- The patient's HPO term set has strong overlap with the disease's annotation in HPOA

Likely Easy candidates: Patient 4 (5 terms, ACCES syndrome), Patient 8 (16 terms, Craniosynostosis 4), Patient 9 (15 terms, Spastic paraplegia 79A), Patient 10 (5 terms, DEE2), Patient 12 (18 terms, Brown-Vialetto-Van Laere syndrome 1)

**Medium** (target: 5 patients) — Assign if:
- The disease is rarer but still has OMIM annotation
- The HPO term count is moderate (10-25)
- Some overlap with other diseases in the same family
- Moderate diagnostic complexity

Likely Medium candidates: Patient 3 (23 terms, Luo-Schoch-Yamamoto syndrome), Patient 5 (23 terms, ReNU syndrome), Patient 6 (22 terms, MEHMO syndrome), Patient 11 (54 terms, Cataracts+GH deficiency syndrome), Patient 13 (20 terms, Congenital disorder of deglycosylation 1)

**Hard** (target: 5 patients) — Assign if:
- The disease is ultra-rare or has no OMIM entry (e.g., "MRTFB-related condition")
- The phenotype profile overlaps with many other diseases
- The condition name is very new or not well-characterized
- Large HPO term sets with many non-specific features

Likely Hard candidates: Patient 1 (31 terms, 3-methylglutaconic aciduria VIII), Patient 2 (21 terms, MRTFB-related — no OMIM), Patient 7 (27 terms, RBBP5-related — no OMIM), Patient 14 (42 terms, Shashi-Pena syndrome), Patient 15 (14 terms, ATP1A1-related — no OMIM)

**Validate your assignments:** For each patient, manually check if the gold diagnosis appears in the HPOA annotation file. If the disease is not annotated at all (the "no OMIM" patients), it CANNOT appear in the disease match results — classify these as Hard and note that Recall@3 is expected to be 0 for these cases. This is important for interpreting results.

### Task 2: Define Gold Outputs

For each of the 15 patients, manually determine the gold standard fields. This requires clinical reasoning — use HPO, Orphanet, and OMIM websites to look up each disease.

**For each patient, define:**

`gold_diagnosis`: The OMIM ID or disease name as given in the patient data.

`gold_diagnosis_in_hpoa`: Boolean — is this disease annotated in the HPOA file? If False, disease_match cannot find it, and that's expected behavior, not a failure.

`gold_next_step_type`: What would a clinician recommend as the most useful next step? Choose one of: "order_test", "refine_phenotype", "genetic_testing", "refer_specialist". Base this on the disease profile. For example:
- If the disease has a characteristic biochemical marker → "order_test"
- If the patient's HPO terms are sparse relative to the disease profile → "refine_phenotype"
- If the disease is associated with a known gene → "genetic_testing"

`gold_next_step_action`: Specific action string. For example: "Urine organic acids for 3-MGA", "Targeted CLPB sequencing", "Echocardiogram", "EEG".

**You don't need gold values for EVERY field.** Focus on:
- Diagnosis (Recall@3 metric)
- Next step type (action type accuracy)
- Difficulty level (for stratified reporting)

### Task 3: Write 5 Synthetic Clinical Notes

For 5 representative patients (pick 2 Easy, 2 Medium, 1 Hard that has an OMIM entry), write short clinical note paragraphs that:
- Describe the patient's HPO terms in natural clinical language
- Include at least 2-3 explicit negation phrases (for testing Comp A)
- Include at least 2-3 temporal phrases (for testing Comp B)
- Are 100-200 words each (not long — just enough to test extraction)

**Negation phrases to include (examples):**
- "No seizures have been reported."
- "Hearing was tested and found to be normal."
- "There is no evidence of cardiac involvement."
- "Deep tendon reflexes were absent." (this is tricky — "absent reflexes" is a PRESENT finding of an abnormality, not a negation of a finding. Include this as a trick case.)
- "Family history is negative for developmental delay." (this is a family negation, should NOT be extracted as patient exclusion)

**Temporal phrases to include (examples):**
- "Hypotonia was noted at birth."
- "Seizures first appeared at approximately 4 months of age."
- "Developmental milestones were normal until age 2, when regression was first observed."
- "Gait difficulties have been progressively worsening over the past 3 years."
- "Speech delay was identified at the 18-month well-child visit."

For each synthetic note, also create the gold extraction output:
- `gold_excluded_phenotypes`: list of {hpo_id, text, exclusion_type}
- `gold_onset_profiles`: list of {hpo_id, onset_stage, onset_normalized}

**File format:** Store each synthetic note as a plain text file in `eval/notes/patient_XX_note.txt`. Store the gold extraction data as part of the gold case JSON.

### Task 4: Insert Gold Cases into MongoDB

**File:** `eval/gold_cases.py`

**Purpose:** Script that inserts all gold case documents into the `eval_gold_cases` collection in MongoDB.

Each document should have:
- `_id`: patient ID string (e.g., "patient_01")
- `difficulty`: "easy", "medium", or "hard"
- `gold_diagnosis`: OMIM ID or disease name
- `gold_diagnosis_in_hpoa`: boolean
- `gold_next_step_type`: string
- `gold_next_step_action`: string
- `gold_excluded_phenotypes`: list (only for patients with synthetic notes)
- `gold_onset_profiles`: list (only for patients with synthetic notes)
- `synthetic_note`: string (the full text of the synthetic note, or null if no note written)
- `hpo_terms`: list of HPO IDs (copied from patient data — so the scoring script has easy access)

Drop and re-insert the collection each time the script runs (idempotent).

---

## Phase 4C: Scoring Script (Hours 8–16)

### File: `eval/score.py`

**Purpose:** Run the diagnostic pipeline on all test patients, compare outputs to gold standards, compute metrics, and store results.

### Execution Flow:

1. Connect to MongoDB. Load all gold cases from `eval_gold_cases` collection.
2. Load the data cache using `load_all()` (same as app startup).
3. Initialize a SessionManager for Redis.
4. For each gold case:
   a. Build a `PatientInput` from the gold case data:
      - If the gold case has a `synthetic_note`, use it as `free_text` AND provide `hpo_terms`
      - If no synthetic note, use only `hpo_terms`
   b. Run `pipeline.run_pipeline(patient_input, data, session_mgr)`
   c. Compare the pipeline output to the gold standard
   d. Compute per-case metrics
   e. Add a 1-second sleep between cases (rate limit protection)

5. Aggregate metrics by difficulty level.
6. Print the formatted report.
7. Store results in MongoDB `eval_results` collection.

### Metrics to Compute:

**Metric 1: Recall@K (K=3, 5, 10)**

For each patient: check if `gold_diagnosis` appears in the pipeline's `differential` list.
- Compare by disease_id (OMIM ID match)
- If `gold_diagnosis_in_hpoa` is False, skip this patient in the Recall calculation (the system cannot possibly find a disease not in its database — this is not a failure)
- Recall@3 = 1 if gold diagnosis is in top 3 of differential, 0 otherwise
- Compute average Recall@3, Recall@5, Recall@10 across all evaluable patients

**Metric 2: Next-Step Type Accuracy**

For each patient: compare `pipeline_output.next_best_steps[0].action_type` to `gold_next_step_type`.
- Exact match = 1, no match = 0
- Average across all patients

**Metric 3: Exclusion Precision and Recall (only for patients with synthetic notes)**

For patients with `gold_excluded_phenotypes`:
- Precision = |correctly extracted exclusions| / |total extracted exclusions|
- Recall = |correctly extracted exclusions| / |total gold exclusions|
- Match by HPO ID if both are mapped, or by fuzzy text match if HPO mapping differs
- Average P and R across patients with notes

**Metric 4: Onset Stage Error (only for patients with synthetic notes)**

For patients with `gold_onset_profiles`:
- For each phenotype with both gold and predicted timing:
  - Map both onset_stages to numeric order: Neonatal=0, Infantile=1, Childhood=2, Juvenile=3, Adult=4
  - Error = |predicted_order - gold_order|
  - Full credit (error=0) if same stage, partial (error=1) if off by one, worse otherwise
- Average error across all phenotypes across all patients

### Report Format:

Print to console AND store in MongoDB:

```
═══════════════════════════════════════════════════
  DIAGNOSTIC COPILOT — EVALUATION REPORT
  Date: {timestamp}
  Model: Claude Sonnet 4
  Patients evaluated: {n} ({n_evaluable} with HPOA annotations)
═══════════════════════════════════════════════════

  DISEASE MATCHING (Recall @ K, n={n_evaluable})
  ─────────────────────────────────────────────────
  Overall:    Recall@3: {x.xx}  Recall@5: {x.xx}  Recall@10: {x.xx}

  By Difficulty:
    Easy   (n={x}):  Recall@3: {x.xx}  Recall@5: {x.xx}
    Medium (n={x}):  Recall@3: {x.xx}  Recall@5: {x.xx}
    Hard   (n={x}):  Recall@3: {x.xx}  Recall@5: {x.xx}

  NEXT-STEP RECOMMENDATION
  ─────────────────────────────────────────────────
  Action Type Accuracy: {x.xx}

  PHENOTYPE EXTRACTION (n={x} patients with notes)
  ─────────────────────────────────────────────────
  Exclusion Precision: {x.xx}
  Exclusion Recall:    {x.xx}
  Onset Stage Error:   {x.x} stages (lower is better)

  NOTES
  ─────────────────────────────────────────────────
  {x} patients have diagnoses not in HPOA — excluded from Recall
  These are ultra-rare/novel conditions the system cannot match.
═══════════════════════════════════════════════════
```

### MongoDB Storage:

Store each eval run as a document in `eval_results`:
- `_id`: "run_{timestamp}"
- `timestamp`: ISO datetime string
- `config`: dict with model name, number of patients, etc.
- `results_overall`: dict with overall metrics
- `results_by_difficulty`: dict with per-difficulty metrics
- `per_patient_results`: list of per-patient metric dicts (for detailed analysis)

---

## Phase 4D: Robustness Testing (Hours 16–20)

### File: `eval/robustness.py`

**Purpose:** Test how the system degrades when patient data is incomplete. This directly addresses the equity question — patients with sparse records should receive appropriate "gather more data" guidance, not confident wrong answers.

### Logic:

1. Select the patients classified as Easy and Medium that have `gold_diagnosis_in_hpoa=True` (Hard patients with no HPOA entry are not useful for robustness testing since they always fail Recall).

2. For each selected patient, run three conditions:
   - **Full**: all HPO terms
   - **30% drop**: randomly remove 30% of HPO terms (round up)
   - **60% drop**: randomly remove 60% of HPO terms

3. For each condition, run the pipeline and record:
   - Recall@3 (is gold diagnosis still in top 3?)
   - Top next-step action_type (did it shift toward "refine_phenotype"?)
   - Data completeness score

4. Run each drop condition 3 times with different random seeds and average the results (to smooth out randomness in which terms get dropped).

5. Compute aggregate statistics:

**Recall degradation:**
- Average Recall@3 at full, 30%, 60%
- Expected: Recall drops as data gets sparser — this is acceptable and expected

**Behavioral shift:**
- Percentage of cases where top action_type = "refine_phenotype" at full, 30%, 60%
- Expected: this percentage should INCREASE as data gets sparser
- This is the KEY metric: a well-designed system asks for more data when uncertain, rather than guessing

**Completeness tracking:**
- Average data_completeness score at full, 30%, 60%

### Report Format:

```
  ROBUSTNESS UNDER DATA MISSINGNESS
  ─────────────────────────────────────────────────
  Patients tested: {n} (Easy + Medium with HPOA)
  Drop conditions: Full | 30% removed | 60% removed
  Iterations per condition: 3

  Recall@3:
    Full:     {x.xx}
    30% drop: {x.xx} ({change}% change)
    60% drop: {x.xx} ({change}% change)

  Behavioral Appropriateness:
    "refine_phenotype" as top action:
      Full:     {x}%
      30% drop: {x}% 
      60% drop: {x}%
    ✓ System correctly shifts toward data gathering under uncertainty

  Data Completeness Score:
    Full:     {x.xx}
    30% drop: {x.xx}
    60% drop: {x.xx}
```

### Add to MongoDB:

Store robustness results as a sub-document in the same eval_results entry, or as a separate document with `_id: "robustness_{timestamp}"`.

---

## Phase 4E: Final Report & Demo Numbers (Hours 20–24)

### Task: Prepare Numbers for Presentation

Run the full evaluation suite:

```bash
python -m eval.score        # Full evaluation
python -m eval.robustness   # Robustness testing
```

Collect the key numbers that Person C needs for the demo:
- Recall@3 overall and by difficulty
- The behavioral shift statistic (refine_phenotype increase under missingness)
- Exclusion precision/recall (if synthetic notes were tested)
- Any interesting per-patient observations (e.g., "Patient 10 was correctly identified in top 1 every time")

Write a brief summary (5-10 bullet points) that can be shown during the presentation.

If any metrics look bad, investigate:
- Low Recall@3 for Easy patients? Check if the disease is actually in HPOA.
- Exclusion precision low? Check if the prompt is extracting false positives. Suggest prompt edits to WS2.
- Behavioral shift not happening? Check if the data_completeness formula in the pipeline is working correctly.

---

## Handoff Points

**Hour 5:** Push `tools/timing_extract.py` and the timing prompt file. WS2 integrates it into the pipeline.

**Hour 8:** Push gold case data (eval/gold_cases.py script + gold case documents). WS2 can use these for their own testing.

**Hour 12:** Push synthetic clinical notes. WS2 can test extraction quality against them.

**Hour 18:** Push eval/score.py with all metric computation logic. Can test with mock pipeline output before WS2's pipeline is fully ready.

**Hour 22:** Run full evaluation and robustness tests. Push results.

**Hour 24:** Final numbers prepared for presentation.

---

## Development Strategy: Work While Waiting

You depend on WS2's pipeline for the actual eval run, but you can build everything else independently:

**Hours 0-5:** Build Comp B (timing_extract). This is real code that ships.

**Hours 2-8:** Curate gold cases. This is manual research work — look up each disease on OMIM/Orphanet, determine appropriate next steps, write synthetic notes. No code dependency.

**Hours 8-16:** Build the scoring script. Test it with MOCK pipeline output — create a function that returns a hardcoded AgentOutput for Patient 10, and verify your metrics compute correctly against a hand-crafted gold case. This way your scoring logic is debugged before the real pipeline is ready.

**Hours 16-22:** Plug in the real pipeline and run actual evaluation. Debug any integration issues.

**Hours 22-24:** Generate final report and prepare numbers.
