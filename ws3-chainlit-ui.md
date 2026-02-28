# WORKSTREAM 3: Chainlit Frontend & Agent UX

**Owner:** Person C
**Time:** ~20 hours
**Dependencies:** WS1's `load_all()` (hour 3), WS2's `pipeline.run_pipeline()` (hour 10 for partial, hour 15 for full)
**Branch:** `ws3-ui`

---

## What You Deliver

1. `app.py` — the Chainlit application entry point
2. `.chainlit/config.toml` — Chainlit project configuration
3. `chainlit_utils/formatters.py` — output formatting helpers
4. A working UI where a user pastes input, watches the agent work step by step, and sees structured results

---

## Core UX Principles

1. **The agent's reasoning must be visible.** Judges want to watch the agent think — each tool call should appear as an expandable step in real time.
2. **The output must be scannable.** Differential diagnosis, next steps, and evidence should use clear visual hierarchy with markdown formatting and emoji indicators.
3. **Interaction, not just display.** Provide action buttons to load test patients and ideally to add an HPO term and re-run the pipeline.
4. **Errors should be informative, not fatal.** If the LLM returns bad JSON or a tool fails, show what happened and what still worked.

---

## Phase 3A: Chainlit Setup (Hours 0–2)

### Task 1: Project Configuration

Create `.chainlit/config.toml` with these settings:
- Project name: "Diagnostic Copilot"
- Enable telemetry: false
- UI name: "Rare Disease Diagnostic Copilot"
- Description: "AI-powered next-best-step diagnostic reasoning"
- `default_collapse_content`: true (steps start collapsed, user can expand)
- `hide_cot`: false (we WANT to show the chain of thought)

### Task 2: `app.py` Skeleton

This is the main file. Chainlit runs it directly with `chainlit run app.py`.

**On module load (top of file):**
- Import everything from core (config, database, data_loader, session_manager)
- Import the pipeline function from agent/pipeline
- Import models from core/models
- Do NOT load data at module level — do it in the startup hook

**Global variables:**
- `data_cache`: dict or None — will hold the result of `load_all()`. Set to None initially.
- `session_mgr`: SessionManager instance or None.

### Task 3: Chainlit Startup Hook

Use `@cl.on_chat_start` — this runs when a new user session begins.

**Logic:**

1. If `data_cache` is None (first session after server start):
   - Show a message: "Loading diagnostic knowledge base... (this takes ~20 seconds on first run)"
   - Get the MongoDB database object using `Database.get_db()`
   - Call `load_all(db)` and store the result in the global `data_cache`
   - Initialize `session_mgr` with the Redis URL from config
   - Show a message: "Knowledge base loaded. {len} diseases, {len} HPO terms ready."

2. Generate a session UUID and store it in `cl.user_session.set("session_id", session_id)`

3. Build patient selector action buttons:
   - Loop through `data_cache["patients"]`
   - For each patient, create a `cl.Action` with:
     - `name`: "load_patient"
     - `payload`: dict with patient_id and all patient data
     - `label`: formatted string like "Patient 1: 17yo F — 3-methylglutaconic aciduria VIII"
   - Cap at 15 buttons (all test patients)

4. Send a welcome message with the action buttons:
   - Title: "Rare Disease Diagnostic Copilot"
   - Body text explaining what the user can do:
     - Paste a clinical note (free text with symptoms)
     - Enter HPO term IDs (comma-separated)
     - Or select a test patient below
   - Attach the action buttons list

---

## Phase 3B: Patient Loading Actions (Hours 2–4)

### Task 4: Action Callback for Patient Loading

Register an `@cl.action_callback("load_patient")` handler.

**When a patient button is clicked:**

1. Extract the patient data from `action.payload`
2. Store the patient's HPO terms in `cl.user_session.set("current_hpo_terms", hpo_terms)`
3. Send a message showing the loaded patient details:
   - Format as: "**Loaded Patient {id}**\nAge: {age} | Sex: {sex}\nDiagnosis: {name}\nHPO Terms: {count} terms loaded"
   - List the HPO terms with their labels (look up labels from `data_cache["hpo_index"]`)
4. Trigger the analysis pipeline (call the same function that `on_message` would call — extract this into a shared helper function to avoid duplication)

### Task 5: Manual Input Handling

Register `@cl.on_message` handler.

**When the user sends a message:**

1. Parse the message content to determine input type:
   - If the message contains strings matching the pattern `HP:\d{7}`, extract them as HPO term IDs. Treat the message as HPO input.
   - If the message is longer than 50 characters and contains clinical-sounding language, treat the entire message as `free_text`.
   - If unclear, treat as free_text (the pipeline handles both).
   
2. Build a `PatientInput` object:
   - `hpo_terms`: extracted HP IDs (if any)
   - `free_text`: the full message text (if treating as free text)
   - `age`, `sex`, `prior_tests`, `family_history`: None for manual input (could be extracted from free text by the pipeline)

3. Trigger the analysis pipeline.

---

## Phase 3C: Pipeline Execution with Step Visualization (Hours 4–12)

This is the most important part of the UI. Build a helper function that runs the pipeline and renders each step in real time.

### Task 6: Step-by-Step Pipeline Runner

Create an async function (e.g., `run_analysis`) that is called by both the action callback and the on_message handler.

**The idea:** Instead of calling `pipeline.run_pipeline()` as a black box, call each pipeline step individually and wrap each one in a Chainlit `cl.Step` context. This gives judges the real-time "watch the agent think" experience.

**However**, this means the pipeline needs to expose individual steps OR accept a callback. There are two approaches — choose based on how WS2 structures the pipeline:

**Approach A (Preferred — callback-based):**
WS2's `run_pipeline` accepts an optional `step_callback` parameter. After each tool call, it invokes `step_callback(step_name, step_input_summary, step_output_summary)`. In Chainlit, you implement this callback to create `cl.Step` objects.

**Approach B (If WS2 doesn't support callbacks):**
Import WS1's tools directly and call them yourself in sequence, wrapping each in `cl.Step`. Then call WS2's final reasoning function separately. This duplicates some pipeline logic but gives you full control over the UX.

**Recommended: Start with Approach B for guaranteed UX control**, then switch to Approach A if WS2 adds callback support.

### Approach B Implementation (step by step):

**Step 1 display: Red Flag Check**
- Show a `cl.Step` with name "🚨 Red Flag Check" and type "tool"
- Call `red_flag.run(patient_hpo_ids, data_cache["ontology"])`
- Set step output: if flags found, format them with severity and action. If none, "No urgent flags detected ✓"
- If URGENT flag found, send a prominent message with red emoji and recommended action. Stop here.

**Step 2 display: HPO Term Mapping**
- Show a `cl.Step` with name "🔍 HPO Term Mapping" and type "tool"
- Call `hpo_lookup.run(input_texts, data_cache)`
- Set step output: table-like format showing each input → matched HPO term → IC score → confidence
- Example output format:
  ```
  "seizures" → HP:0001250 (Seizures) | IC: 3.82 | ✓ high
  "small head" → HP:0000252 (Microcephaly) | IC: 5.41 | ✓ high
  ```

**Step 3 display: Disease Matching**
- Show a `cl.Step` with name "🧬 Disease Matching" and type "tool"
- Call `disease_match.run(hpo_ids, excluded_ids, data_cache)`
- Set step output: top 5 diseases with scores
  ```
  #1 Dev. & epileptic encephalopathy 2 (score: 47.3, coverage: 68%)
  #2 Dravet syndrome (score: 41.1, coverage: 55%)
  ...
  ```

**Step 4 display: Phenotype Extraction (only if free text present)**
- Show a `cl.Step` with name "📝 Phenotype Extraction" and type "tool"
- Call both `excluded_extract.run()` and `timing_extract.run()`
- Set step output: list excluded findings and timing profiles
  ```
  Excluded: "no seizures" → HP:0001250 (explicit, high confidence)
  Timing: Hypotonia — onset: birth (Neonatal), ongoing, stable
  ```

**Step 5 display: Disease Profile Fetch**
- Show a `cl.Step` with name "📋 Disease Profile Fetch" and type "tool"
- Call `orphanet_fetch.run(top_5_disease_ids, data_cache)`
- Set step output: brief summary of each fetched profile (inheritance, key genes, test count)

**Step 6 display: Clinical Reasoning**
- Show a `cl.Step` with name "🧠 Clinical Reasoning" and type "llm"
- This is where you either call the final reasoning function from WS2's pipeline, or assemble the context packet yourself and call the Anthropic API
- Set step output: "Analysis complete"

**After all steps:** Send the final formatted output message (Task 7).

### Task 7: Format and Send Final Output

Create a helper in `chainlit_utils/formatters.py` that takes an `AgentOutput` and returns a well-formatted markdown string.

**Section order and formatting:**

**Data Completeness Bar:**
- Compute a visual bar: filled blocks (█) and empty blocks (░) proportional to the score, out of 10 characters
- Format: `**Data Completeness:** [bar] XX%`

**Red Flags Section (only if flags present):**
- Header: `## 🚨 Red Flags`
- Each flag: severity emoji + label + recommended action
- Use ⛔ for URGENT, ⚠️ for WARNING, 👁️ for WATCH

**Differential Diagnosis Section:**
- Header: `## 🔍 Differential Diagnosis`
- Top 5 entries, each with:
  - Confidence indicator: 🟢 high, 🟡 moderate, 🔴 low
  - Disease name and ID in bold
  - Confidence reasoning as a sub-line
  - Supporting phenotypes listed
  - Missing key phenotypes listed with ⚠️ prefix
- Separate entries with blank lines for readability

**Next Best Steps Section:**
- Header: `## 🎯 Recommended Next Steps`
- Numbered list, each entry with:
  - Action type in brackets and uppercase: `[ORDER TEST]`, `[REFINE PHENOTYPE]`, etc.
  - Action description in bold
  - Rationale as a sub-line
  - "Discriminates between: X vs Y" as a sub-line
  - Urgency tag if not "routine"
  - Evidence source reference

**What Would Change This Section:**
- Header: `## 🔄 What Would Change This`
- Bulleted list of the what_would_change strings

**Uncertainty Summary Section:**
- Header: `## ❓ Uncertainty Summary`
- Three sub-sections: Known (with ✅), Missing (with ❓), Ambiguous (with ⚡)

**Send this as a `cl.Message` with the formatted markdown as content.**

---

## Phase 3D: Polish & Interactive Features (Hours 12–20)

### Task 8: Add HPO Term Action

After displaying the final output, also display a set of "suggested next phenotype" action buttons based on the `missing_key_phenotypes` from the top differential entries.

For each unique missing phenotype across the top 3 diseases:
- Create a `cl.Action` with name "add_hpo_term", payload containing the HPO term ID and label
- Label: "+ Assess for {label}"

Register an `@cl.action_callback("add_hpo_term")` handler that:
1. Gets current HPO terms from `cl.user_session`
2. Appends the new term
3. Sends a message: "➕ Added **{label}** to patient profile. Re-running analysis..."
4. Re-runs the full analysis with the updated term list
5. This creates the "interactive update" demo moment

### Task 9: Error Handling

Wrap the entire analysis flow in try/except. On any exception:
- Send a `cl.Message` with the error details formatted nicely
- Include a suggestion: "Try loading a test patient, or paste HPO terms in format HP:XXXXXXX"
- Log the full traceback for debugging

Handle specific failure modes:
- If WS2's pipeline isn't available yet (import error), display: "Pipeline not yet connected. Loading test patient data only."
- If MongoDB connection fails, display: "Database connection failed. Check .env configuration."
- If Anthropic API fails, display: "LLM service unavailable. Showing tool outputs without final reasoning."

### Task 10: Chainlit Custom Styling (OPTIONAL — only if ahead of schedule)

Chainlit supports custom CSS. If time permits:
- Add a custom header/logo
- Adjust color scheme to feel clinical/professional (blue/white/gray tones)
- Add a favicon

---

## Phase 3E: Demo Readiness (Hours 20–24)

### Task 11: Demo Script Preparation

Pre-test these three demo scenarios and make sure they work smoothly:

**Demo 1: Clean HPO Input (30 seconds)**
- Click "Load Patient 10"
- Watch 5 steps complete in sequence
- Point out: correct diagnosis in differential, sensible next steps
- Time it — should complete in under 30 seconds

**Demo 2: Complex Patient (45 seconds)**
- Click "Load Patient 1" (31 HPO terms)
- Watch the agent process a larger phenotype set
- Point out: more disease candidates, more nuanced next steps
- Show the data completeness score difference

**Demo 3: Interactive Update (45 seconds)**
- Click "Load Patient 4" (5 HPO terms)
- Show initial results with moderate confidence
- Click one of the "Assess for..." buttons
- Watch the differential shift
- Narrate: "Adding one phenotype changed the top recommendation from 'gather more data' to 'order specific test'"

**Pre-check before demo:**
- Server starts without errors
- MongoDB and Redis connections work
- All 15 patients load in the selector
- At least Patients 1, 4, and 10 produce reasonable output

---

## Development Strategy: Stub-First

You will be blocked on WS2's pipeline for the first ~10 hours. Here's how to stay productive:

**Hours 0-6: Build the full UI with a stub pipeline.**

Create a mock `run_pipeline` function in your own code that:
- Takes a PatientInput
- Returns a hardcoded AgentOutput with realistic-looking data for Patient 10
- Sleeps 1 second between "steps" to simulate agent processing time
- This lets you build and polish ALL the Chainlit rendering code without waiting for WS2

**Hours 6-10: Build the step-by-step visualization with direct tool calls.**

As WS1 pushes tools (hour 6), start calling them directly:
- Import hpo_lookup, disease_match, red_flag from tools/
- Call them directly in your step-by-step runner
- This gives you a working demo of steps 1-3 even without WS2's pipeline

**Hours 10-15: Integrate WS2's pipeline.**

When WS2 pushes the pipeline function, switch from your direct tool calls to calling their pipeline. Adjust the step rendering as needed.

**Hours 15+: Polish, error handling, demo prep.**

---

## Chainlit Commands Reference (for Copilot)

These are the key Chainlit APIs you'll use:

- `@cl.on_chat_start` — async function, runs when session starts
- `@cl.on_message` — async function, receives `cl.Message` object with `.content` string
- `@cl.action_callback("name")` — async function, receives `cl.Action` object with `.payload` dict
- `cl.Message(content="markdown string", actions=[...]).send()` — send a message to the user
- `cl.Step(name="step name", type="tool"|"llm")` — async context manager, creates an expandable step in the UI. Set `.output` before the context exits.
- `cl.Action(name="callback_name", payload={...}, label="Button Text")` — clickable button
- `cl.user_session.set(key, value)` / `cl.user_session.get(key)` — per-session storage
- `chainlit run app.py` — start the server (default port 8000)
- `chainlit run app.py -w` — start with auto-reload on file changes (useful during development)
