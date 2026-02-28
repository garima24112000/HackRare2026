# WORKSTREAM 1: Data Pipeline + Programmatic Tools

**Owner:** Person A
**Time:** ~18 hours (includes buffer to help others)
**Dependencies:** None — you are the foundation. Everyone else waits on your `load_all()`.
**Branch:** `ws1-data`

---

## What You Deliver

1. MongoDB populated with all data (3 collections)
2. `core/database.py` — MongoDB connection singleton
3. `core/data_loader.py` — startup hydration function
4. `core/session_manager.py` — Redis session operations
5. `tools/hpo_lookup.py` — free-text to HPO term mapping
6. `tools/disease_match.py` — patient vs disease IC-weighted similarity
7. `tools/red_flag.py` — urgent phenotype detection
8. `tools/orphanet_fetch.py` — disease profile retrieval
9. Three ingestion scripts in `scripts/`

---

## Phase 1A: Infrastructure (Hours 0–2)

### Task 1: `core/database.py`

Create a singleton class `Database` with a class method `get_db()` that:
- Connects to MongoDB Atlas using `MONGODB_URI` from `core/config.py`
- Uses `pymongo.MongoClient`
- Returns the database object for `DB_NAME` ("diagnostic_copilot")
- Caches the client so it's only created once (class-level variable)
- Has a `close()` classmethod that closes the connection

This is 15 lines of code. Keep it minimal.

### Task 2: `core/session_manager.py`

Create a class `SessionManager` that wraps Redis operations.

**Constructor:** Takes `redis_url` string. Creates a `redis.from_url()` connection. Store a TTL constant of 3600 seconds (1 hour).

**Methods:**

`create_session(session_id, raw_input)` — Store the raw input as a JSON string under key `session:{session_id}:input` with TTL.

`log_tool_call(session_id, tool_name, input_data, output_data)` — Append a JSON record to a Redis list at key `session:{session_id}:tools`. The record should contain tool_name, input_data, output_data, and current UTC timestamp as ISO string. Set TTL on the list key after each append.

`get_tool_log(session_id)` — Read the full Redis list at `session:{session_id}:tools`, parse each entry from JSON, return as a Python list of dicts.

`set_context(session_id, context)` — Store the assembled context packet as JSON string at `session:{session_id}:context` with TTL.

`get_context(session_id)` — Read and parse JSON from `session:{session_id}:context`. Return None if key doesn't exist.

`set_output(session_id, output)` — Store final output JSON at `session:{session_id}:output` with TTL.

All methods should handle connection errors gracefully — wrap in try/except, log the error, but don't crash the pipeline. Redis failure should never block the diagnostic analysis.

---

## Phase 1B: Data Ingestion Scripts (Hours 1–4)

### IMPORTANT: Run these scripts BEFORE the hackathon starts (night before) if possible.

### Task 3: `scripts/ingest_hpo.py`

**Purpose:** Parse `hp.obo` and `phenotype.hpoa`, insert into MongoDB collections `hpo_terms` and `disease_profiles`.

**Step-by-step logic:**

1. Load ontology from `data/raw/hp.obo` using `pronto.Ontology()`. Ignore the UnicodeWarning.

2. Iterate all terms in the ontology. For each term whose ID starts with "HP:":
   - Extract: `id`, `name`, list of synonym description strings, list of parent IDs (superclasses at distance=1 excluding self), definition as string (or None)
   - Build a document dict with keys: `_id` (the HP ID), `label`, `definition`, `synonyms`, `parents`, `ic_score` (set to None for now — computed in step 4)

3. Drop the `hpo_terms` collection, then bulk insert all term documents.

4. Load disease annotations from `data/raw/phenotype.hpoa` using `hpo_functions.read_disease_annotations()`. This gives you `disease_to_hpo` (disease_id → set of HPO IDs) and `disease_to_name` (disease_id → name string).

5. Compute IC scores using `hpo_functions.hpo_term_probability(disease_to_hpo)`. This returns a dict of `hpo_id → probability`. For each entry, compute IC = -log2(probability). Update each document in the `hpo_terms` collection with its IC score using `update_one`.

6. For each disease in `disease_to_hpo`:
   - Compute the ancestor set: for each HPO term in the disease's term set, call `hpo_functions.get_ancestors_up_to_root(ontology, term_id)` and union all results together
   - Build a document: `_id` = disease_id, `name` = disease_to_name[disease_id], `hpo_terms` = list of HPO IDs, `ancestor_terms` = list of ancestor IDs, `orphanet` = None (populated later if Orphanet data is parsed)
   - NOTE: The ancestor computation for 12,630 diseases will take several minutes. Print progress every 1000 diseases.

7. Drop the `disease_profiles` collection, then bulk insert all disease documents.

8. Create indexes: text index on `hpo_terms.label` and `hpo_terms.synonyms` for search capability.

9. Print summary stats: number of HPO terms inserted, number of diseases inserted, average HPO terms per disease.

**Error handling:** Wrap the entire ingestion in try/except. If `get_ancestors_up_to_root` fails for a specific term (some terms may not be under HP:0000118), skip that term and continue. Log skipped terms.

### Task 4: `scripts/ingest_patients.py`

**Purpose:** Parse the provided `Phenotypic-profiles-Rare-Disease-Hackathon2025.txt` file and insert into MongoDB `patients` collection.

**Parsing logic:** The file has a repeating pattern:
- Line starting with "Patient N" → new patient record
- Next line: "X-year-old male/female diagnosed with [DISEASE NAME] (OMIM: XXXXXX)"
- Next line: comma-separated HPO term IDs

For each patient, extract:
- `_id`: "patient_01" through "patient_15" (zero-padded)
- `age`: integer parsed from the description line
- `sex`: "M" or "F" parsed from "male"/"female"
- `diagnosis_name`: disease name string
- `diagnosis_omim`: "OMIM:XXXXXX" parsed from the parenthetical (handle cases where OMIM isn't present — some patients have non-OMIM diagnoses like "MRTFB-related condition")
- `hpo_terms`: list of HPO ID strings, stripped of whitespace

Drop and re-insert the `patients` collection.

### Task 5: `scripts/ingest_diseases.py` (Orphanet enrichment — OPTIONAL, do if time)

**Purpose:** Parse `data/raw/en_product4.xml` (Orphanet disease profiles XML) and update existing disease documents in MongoDB with phenotype frequencies, inheritance, genes, and recommended tests.

**Logic:** Use `xml.etree.ElementTree` to parse the XML. For each `<Disorder>` element:
- Extract Orphanet number, disease name
- Extract `<HPODisorderAssociation>` elements which contain HPO ID and frequency
- Extract inheritance pattern, associated genes
- Try to match the Orphanet entry to an existing disease in `disease_profiles` by name similarity or cross-reference ID
- Update the matched MongoDB document's `orphanet` field with the extracted data

**If this proves too complex or the XML structure is difficult:** Skip it. The pipeline works without Orphanet enrichment — disease matching uses IC overlap which only needs HPOA data. Orphanet enrichment adds phenotype frequencies and recommended tests, which improve the "next step" recommendations but aren't required for core functionality.

---

## Phase 1C: Data Loader (Hours 3–5)

### Task 6: `core/data_loader.py`

**Purpose:** Single function `load_all(db)` that reads from MongoDB and builds all in-memory data structures the tools need.

**Input:** `db` — the MongoDB database object from `Database.get_db()`

**Output:** A plain Python dict with these exact keys:

`"hpo_index"` — dict mapping `hpo_id (str) → full document dict` from the `hpo_terms` collection. Read all documents, key by `_id`.

`"synonym_index"` — dict mapping `lowercase_string → hpo_id`. For every document in `hpo_terms`, add entries for: the label (lowercased) → _id, and every synonym (lowercased) → _id. This is the fuzzy matching lookup table.

`"ic_scores"` — dict mapping `hpo_id → float IC score`. Extract from hpo_terms documents.

`"disease_to_hpo"` — dict mapping `disease_id → set of HPO ID strings`. Read from `disease_profiles` collection.

`"disease_ancestors"` — dict mapping `disease_id → set of ancestor HPO ID strings`. Read from `disease_profiles` collection.

`"disease_to_name"` — dict mapping `disease_id → disease name string`.

`"orphanet_profiles"` — dict mapping `disease_id → orphanet sub-document (dict or None)`. Only populated if Orphanet ingestion was done.

`"patients"` — list of all patient documents from the `patients` collection.

`"ontology"` — load the pronto Ontology object from `data/raw/hp.obo`. This is needed by red_flag tool and for ancestor traversal at runtime.

**Performance notes:**
- This function runs once at startup. Total time target: under 30 seconds.
- Reading 18,354 HPO terms and 12,630 disease profiles from MongoDB Atlas over network: ~10-15 seconds.
- Loading pronto ontology: ~5 seconds.
- Building synonym_index from 18K terms with ~50K synonyms: ~2 seconds.
- Print progress messages so the team knows startup is working: "Loading HPO terms...", "Loading diseases...", etc.

---

## Phase 1D: Programmatic Tools (Hours 4–10)

### Task 7: `tools/hpo_lookup.py`

**Function:** `run(raw_texts: list[str], data: dict) → list[HPOMatch]`

**Purpose:** Take a list of free-text symptom descriptions and map each to the best-matching HPO term.

**Logic for each text string in the input list:**

1. Normalize the input: lowercase, strip whitespace.

2. **Exact match attempt:** Look up the normalized string in `data["synonym_index"]`. If found, this is a direct match → confidence "high".

3. **Fuzzy match attempt:** If no exact match, use `rapidfuzz.process.extractOne()` to find the closest match in the synonym_index keys. Use `score_cutoff=75`. If a match is found:
   - Score >= 85 → confidence "high"
   - Score 75-84 → confidence "medium"
   - Below 75 → confidence "low"

4. **HPO ID direct input:** If the input string matches the pattern `HP:\d{7}`, treat it as a direct HPO ID. Look it up in `data["hpo_index"]`. If found → confidence "high". If not found → skip it.

5. For each matched term, build an `HPOMatch` object using data from `data["hpo_index"][matched_id]`: label, definition, IC score, parents.

6. If no match at all for a text string, still return an HPOMatch with `hpo_id=""`, `match_confidence="low"`, and `raw_input` set to the original text. Don't silently drop inputs.

**IMPORTANT: No LLM calls in this tool.** The original design had an LLM fallback for ambiguous text, but for hackathon simplicity, fuzzy string matching with rapidfuzz is sufficient. If WS2 wants to add an LLM pre-processing step in the pipeline before calling this tool, they can — but this tool itself is pure programmatic.

### Task 8: `tools/disease_match.py`

**Function:** `run(patient_hpo_ids: list[str], excluded_hpo_ids: list[str], data: dict) → list[DiseaseCandidate]`

**Purpose:** Rank all diseases by phenotypic similarity to the patient. This is the core differential diagnosis engine.

**Logic:**

1. Build the patient's ancestral set: for each HPO ID in `patient_hpo_ids`, get its ancestors using `hpo_functions.get_ancestors_up_to_root(data["ontology"], hpo_id)`. Union all ancestors together into one set called `patient_ancestors`.

2. For each disease in `data["disease_to_hpo"]`:
   - Get the disease's pre-cached ancestor set from `data["disease_ancestors"][disease_id]`
   - Compute overlap: `patient_ancestors ∩ disease_ancestors`
   - Compute similarity score: sum of `data["ic_scores"][term]` for each term in the overlap set. Use 0.0 for terms not found in ic_scores.
   - Compute `matched_terms`: `patient_hpo_ids ∩ disease_hpo_terms` (direct term overlap, not ancestor overlap — this is for display)
   - Compute `missing_terms`: `disease_hpo_terms - set(patient_hpo_ids)` (features in the disease profile that the patient hasn't been assessed for)
   - Compute `extra_terms`: `set(patient_hpo_ids) - disease_hpo_terms` (patient features not in this disease profile)
   - Compute `coverage_pct`: `len(matched_terms) / len(disease_hpo_terms)` if disease has terms, else 0

3. **Exclusion penalty:** For each disease, check if any term in `excluded_hpo_ids` appears in the disease's HPO term set. If so, set `excluded_penalty=True` and multiply the score by 0.5. (This penalizes diseases that require a feature the patient explicitly lacks.)

4. Sort all diseases by penalized score descending. Return the top 15 as `DiseaseCandidate` objects with rank 1–15.

**Performance target:** Under 5 seconds for all 12,630 diseases. The bottleneck is computing the patient's ancestral set (step 1). Disease ancestor sets are pre-cached, so the per-disease loop is just set intersection + IC summation — fast.

**Edge cases:**
- If `patient_hpo_ids` is empty, return an empty list.
- If a patient HPO ID is not found in the ontology (bad ID), skip it with a warning print.
- If `excluded_hpo_ids` is empty, skip the penalty step entirely.

### Task 9: `tools/red_flag.py`

**Function:** `run(patient_hpo_ids: list[str], ontology) → list[RedFlag]`

**Purpose:** Check if any patient phenotype falls under a life-threatening HPO subtree. This is a safety gate — must be fast and deterministic.

**Urgent subtree roots (hardcode these):**
- `HP:0001695` — Cardiac arrest
- `HP:0002098` — Respiratory distress
- `HP:0002133` — Status epilepticus
- `HP:0001259` — Coma
- `HP:0001279` — Syncope
- `HP:0006579` — Neonatal onset (context-dependent, flag as WARNING not URGENT)
- `HP:0003812` — Clinical deterioration

**Combination rules (hardcode these):**
- If patient has BOTH any term under "Abnormality of the cardiovascular system" (HP:0001626) AND any term under "Abnormality of the musculature" (HP:0003011) → flag as WARNING: "Consider metabolic cardiomyopathy workup"
- If patient has BOTH any term under "Seizures" (HP:0001250) AND any term under "Neurodevelopmental abnormality" (HP:0012759) AND any term under "Abnormality of metabolism" (HP:0001939) → flag as WARNING: "Consider urgent metabolic screening"

**Logic for each patient HPO ID:**

1. Use `ontology[hpo_id].superclasses()` to get all ancestors.
2. Check if any ancestor ID is in the urgent subtree roots set.
3. If match found:
   - If the root is HP:0001695, HP:0002098, HP:0002133, HP:0001259 → severity "URGENT"
   - If the root is HP:0001279, HP:0006579, HP:0003812 → severity "WARNING"
4. Build a `RedFlag` object with the appropriate label, severity, triggering terms list, and a hardcoded recommended action string for each flag type.

Then check combination rules by building sets of which high-level categories the patient's terms fall under, and checking if the rule conditions are met.

**Performance:** Must complete in under 200ms. No database calls, no LLM calls. Pure ontology traversal.

**CRITICAL DESIGN RULE:** This tool must NEVER use an LLM. Medical urgency detection must be deterministic, auditable, and reproducible. The curated rule set is small, defensible, and explainable.

### Task 10: `tools/orphanet_fetch.py`

**Function:** `run(disease_ids: list[str], data: dict) → list[DiseaseProfile]`

**Purpose:** For a list of disease IDs (typically the top 3-5 from disease_match), retrieve their full clinical profiles from the pre-loaded Orphanet data.

**Logic:**

1. For each disease_id in the input list:
   - Look up `data["orphanet_profiles"].get(disease_id)`
   - If found, build a `DiseaseProfile` from the stored data
   - If not found (Orphanet data not available for this disease), build a minimal `DiseaseProfile` with just disease_id and disease_name from `data["disease_to_name"]`, and empty lists for everything else

2. Return the list of DiseaseProfile objects.

**This tool is simple by design.** All the heavy work was done in the ingestion script. This is just a dict lookup. If Orphanet ingestion wasn't done, this tool returns minimal profiles — the pipeline still works, just with less detail in the "recommended tests" output.

---

## Phase 1E: Integration Testing (Hours 10–12)

Before merging to main, verify:

1. **Database test:** Run `Database.get_db()`, query `hpo_terms.count_documents({})` — should return ~18,354. Query `disease_profiles.count_documents({})` — should return ~12,630. Query `patients.count_documents({})` — should return 15.

2. **Loader test:** Run `load_all(db)`, verify all dict keys present, verify `len(data["synonym_index"])` is > 40,000 (terms + synonyms), verify IC scores are populated.

3. **HPO Lookup test:** Call `hpo_lookup.run(["seizures", "small head", "HP:0001290"], data)`. Expect 3 HPOMatch objects. "seizures" should map to HP:0001250 with high confidence. "HP:0001290" should return directly.

4. **Disease Match test:** Use Patient 10's HPO terms `["HP:0002360", "HP:0100704", "HP:0001250", "HP:0001252", "HP:0001332"]`. Call `disease_match.run(terms, [], data)`. Verify "OMIM:300672" (Dev and epileptic encephalopathy 2) appears in top 10.

5. **Red Flag test:** Call with `["HP:0002133"]` (Status epilepticus). Verify an URGENT flag is returned.

6. **Redis test:** Create a session, log a tool call, retrieve the log. Verify data round-trips correctly.

Print all test results. Fix any failures before merging.

---

## Handoff Points

**Hour 3:** Push `core/database.py`, `core/session_manager.py`, and `core/data_loader.py` to branch. WS2 and WS3 can start using `load_all()` with a stub if your branch isn't merged yet.

**Hour 6:** Push `tools/hpo_lookup.py` and `tools/disease_match.py`. WS2 needs these to wire the pipeline.

**Hour 8:** Push `tools/red_flag.py`. WS2 needs this for the pipeline's first step.

**Hour 12:** Merge `ws1-data` to `main`. Everything is tested, all tools work independently.

**Hour 15-18:** Implement `tools/orphanet_fetch.py` (if Orphanet data was ingested) and help WS4 with eval data or help WS2 debug integration.
