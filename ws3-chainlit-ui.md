# WORKSTREAM 3: Chainlit Frontend & Agent UX

**Owner:** Person C
**Chainlit Version:** 2.9.6 (installed via `uv add chainlit`)
**Branch:** `ws3-ui`

---

## What You Deliver

1. `app.py` — the Chainlit application entry point (319 lines)
2. `.chainlit/config.toml` — Chainlit 2.x project configuration
3. `public/custom.css` — custom dark-theme stylesheet with welcome dashboard + card components (~389 lines)
4. `public/custom.js` — client-side interactivity (accordion, patient selector, assess chips, placeholder)
5. `chainlit_utils/__init__.py` — package re-exports
6. `chainlit_utils/formatters.py` — `format_agent_output()`, `format_welcome_card()`, `format_patient_load_card()` (512 lines)
7. `chainlit_utils/pipeline_adapter.py` — single import point, delegates mock/real via `USE_MOCK_PIPELINE` env var
8. `chainlit_utils/data_provider.py` — data loading abstraction (mock patients or MongoDB)
9. `chainlit_utils/mock_pipeline.py` — hardcoded `AgentOutput` with same interface as real pipeline (405 lines)
10. A working UI where a user sees a **branded HTML dashboard**, selects patients, watches the agent work step by step via `cl.Step`, and sees rich, card-based structured results

---

## Architecture: Pipeline Adapter Pattern

The frontend runs in two modes with **zero code changes** between them:

```
USE_MOCK_PIPELINE=true   (default) — No DB, no Redis, no LLM needed
USE_MOCK_PIPELINE=false  — Connects to MongoDB, Redis, Azure OpenAI
```

**Key design:**
- `app.py` imports ONLY from `chainlit_utils/` — never from `agent/` or `tools/` directly
- `pipeline_adapter.py` lazy-imports the real pipeline only when `USE_MOCK_PIPELINE=false`
- `data_provider.py` returns mock patients or real MongoDB data
- `mock_pipeline.py` fires the SAME `step_callback` protocol as the real pipeline
- The `chainlit_utils/` package is self-contained — no circular dependencies

```
app.py
  ├── chainlit_utils/pipeline_adapter.py  →  mock_pipeline.py  OR  agent.pipeline
  ├── chainlit_utils/data_provider.py     →  mock patients    OR  core.data_loader
  └── chainlit_utils/formatters.py        →  HTML card builders (shared)
```

---

## Design Language Reference

The entire UI follows a **dark clinical dashboard** aesthetic. Every colour, font, and spacing value below is intentional. Implement them precisely.

### Colour Tokens

| Token          | Value                         | Usage                                    |
| -------------- | ----------------------------- | ---------------------------------------- |
| `--bg`         | `#0e1117`                     | Page / body background                   |
| `--surface`    | `#161b27`                     | Card backgrounds                         |
| `--surface2`   | `#1c2333`                     | Hover / open-card background             |
| `--surface3`   | `#212840`                     | Tertiary surfaces                        |
| `--border`     | `#252e42`                     | Default card borders                     |
| `--border2`    | `#2e3a55`                     | Hover / active borders                   |
| `--text`       | `#dde4f0`                     | Primary text                             |
| `--text-dim`   | `#7a8ba8`                     | Secondary text, labels                   |
| `--text-muted` | `#3e4f6a`                     | Disabled / ultra-dim text                |
| `--teal`       | `#2dd4bf`                     | Primary accent, data completeness, links |
| `--green`      | `#34d399`                     | High confidence, matched phenotypes      |
| `--amber`      | `#fbbf24`                     | Moderate confidence, partial matches     |
| `--rose`       | `#fb7185`                     | Low confidence, red flags, missing data  |
| `--blue`       | `#60a5fa`                     | HPO chip accents, patient avatars        |

### Fonts

| Token           | Stack                          | Usage                             |
| --------------- | ------------------------------ | --------------------------------- |
| `--font-ui`     | `'Outfit', sans-serif`         | All UI text, labels, body copy    |
| `--font-mono`   | `'IBM Plex Mono', monospace`   | IDs, badges, metadata, chip text  |
| `--font-serif`  | `'Fraunces', serif`            | Large numbers, rank digits, gauge |

Load via Google Fonts CSS `@import` in the CSS file (not HTML link tag — Chainlit loads CSS via config):
```css
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500&family=Fraunces:ital,wght@0,300;0,600;1,300&display=swap');
```

### Spacing & Radii
- Default card border-radius: `10px`
- Chip border-radius: `5px`
- Badge border-radius: `20px`
- Default card padding: `14px 16px`

---

## Core UX Principles

1. **The agent's reasoning must be visible.** Judges want to watch the agent think — each tool call should appear as an expandable `cl.Step` in real time.
2. **The output must be scannable.** Differential diagnosis, next steps, and evidence must use **HTML cards with visual hierarchy** — colour-coded confidence bars, accordion expansions, gauge graphics — NOT plain markdown.
3. **Interaction, not just display.** Provide `cl.Action` buttons to load test patients and clickable "assess" chips that add phenotypes and re-run the pipeline.
4. **The welcome screen must be a branded dashboard.** NOT a plain markdown message — use `format_welcome_card()` to render an HTML dashboard with branded header, instruction tiles, and patient selector grid.
5. **Errors should be informative, not fatal.** If the LLM returns bad JSON or a tool fails, show what happened and what still worked.

---

## Chainlit 2.x API Reference

**Important:** This project uses Chainlit 2.9.6. The API differs from 1.x docs you may find online.

| API                                          | Notes                                                       |
| -------------------------------------------- | ----------------------------------------------------------- |
| `cl.Action(name, payload, label)`            | Dataclass. `payload` is a dict (not `value`). `label` replaces old `description`. |
| `cl.Step(name, type)`                        | Async context manager. Set `.output` before `__aexit__`.    |
| `cl.Message(content, actions).send()`        | `content` supports raw HTML when `unsafe_allow_html=true`.  |
| `cl.user_session.set(key, value)`            | Per-session key-value storage.                              |
| `@cl.on_chat_start`                          | Runs when a new session begins.                             |
| `@cl.on_message`                             | Receives `cl.Message` with `.content` string.               |
| `@cl.action_callback("name")`               | Receives `cl.Action` with `.payload` dict.                  |
| Config `cot = "full"`                        | Not `hide_cot = false` (that was 1.x). Options: `"hidden"`, `"tool_call"`, `"full"`. |
| Config `layout = "wide"`                     | Wide layout mode.                                           |
| Config `unsafe_allow_html = true`            | Required for HTML card rendering in messages.               |

---

## Phase 3A: Chainlit Setup & Custom Theme

### Task 1: Project Configuration — `.chainlit/config.toml`

Chainlit 2.x auto-generates this file on first run. Update these specific settings (leave other auto-generated defaults):

```toml
[features]
unsafe_allow_html = true

[UI]
name = "Diagnostic Copilot"
description = "AI-powered next-best-step diagnostic reasoning"
layout = "wide"
cot = "full"
default_collapse_content = true
custom_css = "/public/custom.css"
custom_js = "/public/custom.js"
confirm_new_chat = true
alert_style = "classic"
```

**Key settings explained:**
- `unsafe_allow_html = true` — Required. All card rendering is raw HTML inside `cl.Message(content=...)`.
- `cot = "full"` — Shows chain-of-thought steps expanded. Judges want to see the agent think.
- `layout = "wide"` — Uses full viewport width for the dashboard cards.
- `default_collapse_content = true` — Steps start collapsed; user can expand.

### Task 2: Custom CSS — `public/custom.css`

This file overrides Chainlit's default theme and provides all the card component styles. Create `public/custom.css` with the **complete** stylesheet below.

> **Important:** Chainlit renders message content as HTML when `unsafe_allow_html = true`. All card classes below will be used inside `cl.Message(content=html_string)`. The CSS must be loaded globally via the config.

```css
/* ── GOOGLE FONTS ───────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500&family=Fraunces:ital,wght@0,300;0,600;1,300&display=swap');

/* ── CSS VARIABLES ──────────────────────────────────── */
:root {
  --bg:        #0e1117;
  --surface:   #161b27;
  --surface2:  #1c2333;
  --surface3:  #212840;
  --border:    #252e42;
  --border2:   #2e3a55;
  --text:      #dde4f0;
  --text-dim:  #7a8ba8;
  --text-muted:#3e4f6a;
  --teal:      #2dd4bf;
  --teal-dim:  rgba(45,212,191,0.1);
  --teal-glow: rgba(45,212,191,0.18);
  --green:     #34d399;
  --green-dim: rgba(52,211,153,0.1);
  --amber:     #fbbf24;
  --amber-dim: rgba(251,191,36,0.1);
  --rose:      #fb7185;
  --rose-dim:  rgba(251,113,133,0.1);
  --blue:      #60a5fa;
  --blue-dim:  rgba(96,165,250,0.1);
  --font-ui:   'Outfit', sans-serif;
  --font-mono: 'IBM Plex Mono', monospace;
  --font-serif:'Fraunces', serif;
  --r:         10px;
}

/* ── CHAINLIT GLOBAL OVERRIDES ───────────────────────── */
body {
  background: var(--bg) !important;
  color: var(--text) !important;
  font-family: var(--font-ui) !important;
}

/* ── PATIENT HEADER CARD ─────────────────────────────── */
.card-patient {
  background: var(--surface); border: 1px solid var(--border2);
  border-radius: var(--r); padding: 14px 16px;
  display: flex; align-items: center; gap: 16px; margin-bottom: 0;
  animation: fadeUp 0.3s ease forwards;
}
.card-patient-avatar {
  width: 46px; height: 46px; border-radius: 10px;
  font-family: var(--font-mono); font-size: 14px; font-weight: 500;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.card-patient-avatar.m { background: rgba(96,165,250,0.15); color: var(--blue); }
.card-patient-avatar.f { background: rgba(45,212,191,0.12); color: var(--teal); }
.cp-name { font-size: 14px; font-weight: 600; color: var(--text); }
.cp-sub  { font-size: 12px; color: var(--text-dim); margin-top: 2px; }
.cp-chips { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 8px; }
.hpo-chip {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 3px 8px; border-radius: 5px;
  font-family: var(--font-mono); font-size: 11px;
  background: var(--blue-dim); color: var(--blue);
  border: 1px solid rgba(96,165,250,0.2);
}
.hpo-chip-label { color: var(--text-dim); font-size: 11px; }

/* ── STATS ROW (4-tile grid) ─────────────────────────── */
.card-stats {
  display: grid; grid-template-columns: repeat(4,1fr); gap: 8px;
  animation: fadeUp 0.3s 0.05s ease forwards; opacity: 0;
}
.stat-tile {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--r); padding: 12px 14px;
  position: relative; overflow: hidden;
}
.stat-tile::after {
  content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 2px;
}
.stat-tile.t { --c: var(--teal); }
.stat-tile.g { --c: var(--green); }
.stat-tile.a { --c: var(--amber); }
.stat-tile.r { --c: var(--rose); }
.stat-tile::after { background: var(--c); opacity: 0.5; }
.stat-num  { font-family: var(--font-serif); font-size: 26px; font-weight: 600; color: var(--c); line-height: 1; }
.stat-lbl  { font-size: 11px; color: var(--text-dim); margin-top: 4px; font-family: var(--font-mono); }

/* gauge (SVG-based circular progress) */
.stat-gauge { display: flex; align-items: center; gap: 10px; }
.gauge     { width: 46px; height: 46px; flex-shrink: 0; }
.gauge-bg  { fill: none; stroke: var(--border2); stroke-width: 5; }
.gauge-arc { fill: none; stroke: var(--teal); stroke-width: 5; stroke-linecap: round;
             stroke-dasharray: 113; stroke-dashoffset: 70;
             transform: rotate(-90deg); transform-origin: 50% 50%; transition: stroke-dashoffset 1.2s ease; }
.gauge-val { font-family: var(--font-mono); font-size: 9px; font-weight: 500; fill: var(--teal); }

/* ── SECTION HEADERS ─────────────────────────────────── */
.section-head {
  display: flex; align-items: center; gap: 8px; padding: 10px 0 8px;
  font-family: var(--font-mono); font-size: 10px; letter-spacing: 1.3px;
  text-transform: uppercase; color: var(--text-muted);
  border-bottom: 1px solid var(--border); margin-bottom: 8px;
}
.section-head span { font-size: 13px; }
.section-cnt {
  margin-left: auto; padding: 1px 8px; border-radius: 20px;
  background: var(--surface2); border: 1px solid var(--border);
  color: var(--text-dim); font-size: 10px;
}

/* ── DIFFERENTIAL DIAGNOSIS — ACCORDION CARDS ────────── */
.diff-cards { display: flex; flex-direction: column; gap: 5px; }

.diff-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--r); position: relative; overflow: hidden;
  transition: border-color 0.18s;
}
.diff-card.high { --cc: var(--green); }
.diff-card.mod  { --cc: var(--amber); }
.diff-card.low  { --cc: var(--rose);  }
.diff-card::before {
  content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 4px;
  border-radius: 0 2px 2px 0; background: var(--cc); z-index: 1;
}
.diff-card:hover { border-color: var(--border2); }
.diff-card.open  { border-color: var(--border2); background: var(--surface2); }

/* collapsed header row (always visible) */
.dc-header {
  display: grid;
  grid-template-columns: 32px 1fr auto auto 22px;
  align-items: center; gap: 12px;
  padding: 11px 14px 11px 20px;
  cursor: pointer; user-select: none;
}
.dc-num {
  font-family: var(--font-serif); font-size: 20px; font-weight: 600;
  color: var(--cc); line-height: 1; text-align: center;
}
.dc-name { font-size: 13px; font-weight: 600; color: var(--text); line-height: 1.2; }
.dc-id   { font-family: var(--font-mono); font-size: 10px; color: var(--text-muted); margin-top: 2px; }
.dc-score-col { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; min-width: 70px; }
.dc-pct  { font-family: var(--font-serif); font-size: 20px; font-weight: 600; color: var(--cc); line-height: 1; }
.dc-bar  { width: 64px; height: 3px; background: var(--border); border-radius: 2px; overflow: hidden; }
.dc-fill { height: 100%; border-radius: 2px; background: var(--cc); }
.dc-conf-badge {
  padding: 2px 9px; border-radius: 20px; font-size: 10px;
  font-family: var(--font-mono); font-weight: 500; white-space: nowrap;
  background: color-mix(in srgb, var(--cc) 12%, transparent);
  color: var(--cc); border: 1px solid color-mix(in srgb, var(--cc) 28%, transparent);
}
.dc-chevron {
  color: var(--text-muted); font-size: 12px; transition: transform 0.25s ease;
  display: flex; align-items: center; justify-content: center;
}
.diff-card.open .dc-chevron { transform: rotate(180deg); color: var(--teal); }

/* expandable body */
.dc-body {
  max-height: 0; overflow: hidden;
  transition: max-height 0.32s cubic-bezier(0.4,0,0.2,1), opacity 0.25s ease;
  opacity: 0;
}
.diff-card.open .dc-body { max-height: 600px; opacity: 1; }
.dc-body-inner {
  padding: 0 14px 14px 20px;
  border-top: 1px solid var(--border); padding-top: 12px;
}
.dc-reasoning {
  font-size: 12px; color: var(--text-dim); font-style: italic;
  line-height: 1.5; margin-bottom: 10px;
}
.dc-tags { display: flex; flex-wrap: wrap; gap: 4px; }
.tag { padding: 2px 7px; border-radius: 4px; font-size: 10px; font-family: var(--font-mono); font-weight: 500; }
.tag.s { background: var(--green-dim); color: var(--green); border: 1px solid rgba(52,211,153,0.2); }
.tag.m { background: var(--amber-dim); color: var(--amber); border: 1px solid rgba(251,191,36,0.2); }
.tag.x { background: var(--rose-dim); color: var(--rose); border: 1px solid rgba(251,113,133,0.2); }

/* ── ASSESS / REFINE CHIPS ───────────────────────────── */
.assess-row { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 10px; }
.assess-chip {
  padding: 4px 11px; border-radius: 6px; font-size: 11px;
  background: rgba(45,212,191,0.08); color: var(--teal);
  border: 1px solid rgba(45,212,191,0.22);
  cursor: pointer; font-family: var(--font-mono); transition: all 0.15s;
}
.assess-chip:hover {
  background: rgba(45,212,191,0.16); border-color: rgba(45,212,191,0.45);
  transform: translateY(-1px);
}

/* ── NEXT STEPS CARDS ────────────────────────────────── */
.steps-list-cards { display: flex; flex-direction: column; gap: 5px; }
.step-crd {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 9px; padding: 10px 12px 10px 16px;
  display: grid; grid-template-columns: 1fr auto; gap: 8px; align-items: center;
  position: relative; overflow: hidden; cursor: pointer; transition: all 0.15s;
}
.step-crd:hover { background: var(--surface2); }
.step-crd::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; }
.step-crd.urgent::before  { background: var(--rose); }
.step-crd.routine::before { background: var(--teal); }
.step-crd.low::before     { background: var(--text-muted); }
.sc-type  { font-size: 9px; font-family: var(--font-mono); letter-spacing: 1px; text-transform: uppercase; margin-bottom: 3px; }
.step-crd.urgent .sc-type  { color: var(--rose); }
.step-crd.routine .sc-type { color: var(--teal); }
.step-crd.low .sc-type     { color: var(--text-muted); }
.sc-action { font-size: 12px; font-weight: 500; color: var(--text); line-height: 1.35; }
.sc-disc   { font-size: 10px; color: var(--text-muted); font-family: var(--font-mono); margin-top: 3px; }
.sc-disc-vals { color: var(--text-dim); }
.sc-num    { font-family: var(--font-serif); font-size: 20px; font-weight: 300; color: var(--text-muted); }

/* ── TWO-COLUMN LAYOUT ───────────────────────────────── */
.two-col { display: grid; grid-template-columns: 1fr 300px; gap: 10px; align-items: start; }

/* ── UNCERTAINTY 3-COLUMN GRID ───────────────────────── */
.uncert-cols { display: grid; grid-template-columns: repeat(3,1fr); gap: 1px; background: var(--border); border-radius: var(--r); overflow: hidden; }
.uc { background: var(--surface); padding: 12px 12px; }
.uc-head { font-size: 9px; font-family: var(--font-mono); letter-spacing: 1.2px; text-transform: uppercase; margin-bottom: 8px; padding-bottom: 6px; border-bottom: 1px solid var(--border); }
.uc.known   .uc-head { color: var(--green); }
.uc.missing .uc-head { color: var(--rose); }
.uc.amb     .uc-head { color: var(--amber); }
.uc-item { font-size: 11px; color: var(--text-dim); padding: 4px 0; border-bottom: 1px solid var(--border); line-height: 1.4; }
.uc-item:last-child { border-bottom: none; padding-bottom: 0; }

/* ── WHAT WOULD CHANGE ───────────────────────────────── */
.wwc-list { display: flex; flex-direction: column; gap: 5px; }
.wwc-item { display: flex; gap: 10px; align-items: baseline; }
.wwc-bullet { color: var(--teal); font-size: 16px; line-height: 1; flex-shrink: 0; }
.wwc-text   { font-size: 12px; color: var(--text-dim); line-height: 1.45; }

/* ── RED FLAGS CARD ──────────────────────────────────── */
.red-flag-card {
  background: var(--rose-dim); border: 1px solid rgba(251,113,133,0.3);
  border-radius: var(--r); padding: 14px 16px;
  border-left: 4px solid var(--rose);
}
.rf-title { font-size: 13px; font-weight: 600; color: var(--rose); margin-bottom: 8px; }
.rf-item  { font-size: 12px; color: var(--text-dim); padding: 3px 0; }

/* ── STEP SUMMARY CARD ───────────────────────────────── */
.step-summary { display: flex; flex-direction: column; gap: 2px; margin-bottom: 10px; }
.step-summary-row {
  display: flex; align-items: center; gap: 10px; padding: 6px 8px; border-radius: 7px;
}
.step-summary-icon {
  width: 20px; height: 20px; border-radius: 50%;
  background: var(--green-dim); color: var(--green);
  border: 1px solid rgba(52,211,153,0.3);
  display: flex; align-items: center; justify-content: center; font-size: 9px;
}
.step-summary-name { font-size: 12px; color: var(--text-dim); }
.step-summary-dur { margin-left: auto; font-size: 10px; font-family: var(--font-mono); color: var(--text-muted); }

/* ── ANIMATIONS ─────────────────────────────────────── */
@keyframes fadeUp { from { opacity:0; transform:translateY(10px); } to { opacity:1; transform:translateY(0); } }
.diff-card:nth-child(1) { animation: fadeUp 0.35s 0.05s ease both; }
.diff-card:nth-child(2) { animation: fadeUp 0.35s 0.12s ease both; }
.diff-card:nth-child(3) { animation: fadeUp 0.35s 0.19s ease both; }
.diff-card:nth-child(4) { animation: fadeUp 0.35s 0.26s ease both; }
.diff-card:nth-child(5) { animation: fadeUp 0.35s 0.33s ease both; }
.step-crd:nth-child(1) { animation: fadeUp 0.3s 0.1s ease both; }
.step-crd:nth-child(2) { animation: fadeUp 0.3s 0.17s ease both; }
.step-crd:nth-child(3) { animation: fadeUp 0.3s 0.24s ease both; }
.step-crd:nth-child(4) { animation: fadeUp 0.3s 0.31s ease both; }
.card-patient { animation: fadeUp 0.3s ease both; }
.card-stats   { animation: fadeUp 0.3s 0.05s ease both; }

/* ── RESPONSIVE ──────────────────────────────────────── */
@media (max-width: 768px) {
  .card-stats { grid-template-columns: repeat(2,1fr); }
  .two-col { grid-template-columns: 1fr; }
  .uncert-cols { grid-template-columns: 1fr; }
  .patient-select-grid { grid-template-columns: 1fr; }
  .welcome-instructions { grid-template-columns: 1fr; }
}

/* ── HEADER BRANDING ─────────────────────────────────── */
[data-testid="app-header"] {
  font-family: var(--font-serif) !important;
}

/* ── WELCOME DASHBOARD CARD ──────────────────────────── */
.welcome-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--r); padding: 20px 22px 16px;
  animation: fadeUp 0.35s ease both;
}
.welcome-header {
  display: flex; align-items: center; gap: 14px;
  padding-bottom: 16px; border-bottom: 1px solid var(--border);
  margin-bottom: 14px;
}
.welcome-logo {
  width: 48px; height: 48px; border-radius: 12px;
  background: var(--teal-dim); border: 1px solid rgba(45,212,191,0.22);
  display: flex; align-items: center; justify-content: center;
  font-size: 22px; flex-shrink: 0;
}
.welcome-title {
  font-family: var(--font-serif); font-size: 22px; font-weight: 600;
  color: var(--text); line-height: 1.2;
}
.welcome-subtitle {
  font-size: 12px; color: var(--text-dim); margin-top: 2px;
  font-family: var(--font-mono);
}
.welcome-status {
  margin-left: auto; display: flex; align-items: center; gap: 6px;
  font-size: 10px; font-family: var(--font-mono); color: var(--text-dim);
  padding: 4px 10px; border-radius: 20px;
  background: var(--surface2); border: 1px solid var(--border);
  white-space: nowrap;
}
.welcome-status-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--green); display: inline-block;
  animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.4; } }

/* ── WELCOME INSTRUCTIONS ROW ────────────────────────── */
.welcome-instructions {
  display: grid; grid-template-columns: repeat(3,1fr); gap: 8px;
  margin-bottom: 14px;
}
.welcome-instr-item {
  display: flex; align-items: flex-start; gap: 10px;
  padding: 10px 12px; border-radius: 8px;
  background: var(--surface2); border: 1px solid var(--border);
}
.welcome-instr-icon { font-size: 16px; flex-shrink: 0; margin-top: 1px; }
.welcome-instr-label {
  font-size: 12px; font-weight: 600; color: var(--text); margin-bottom: 2px;
}
.welcome-instr-desc {
  font-size: 10px; color: var(--text-dim); line-height: 1.4;
  font-family: var(--font-mono);
}

/* ── PATIENT SELECTOR GRID ───────────────────────────── */
.patient-select-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 6px; margin-top: 8px;
}
.patient-select-card {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 12px; border-radius: 8px;
  background: var(--surface2); border: 1px solid var(--border);
  cursor: pointer; transition: all 0.15s;
}
.patient-select-card:hover {
  background: var(--surface3); border-color: var(--border2);
  transform: translateY(-1px);
}
.ps-info { overflow: hidden; }
.ps-name {
  font-size: 12px; font-weight: 600; color: var(--text);
  font-family: var(--font-mono);
}
.ps-detail {
  font-size: 11px; color: var(--text-dim); margin-top: 1px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.ps-hpo {
  font-size: 9px; font-family: var(--font-mono); color: var(--text-muted);
  margin-top: 2px;
}

/* ── WELCOME DISCLAIMER ──────────────────────────────── */
.welcome-disclaimer {
  margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--border);
  font-size: 10px; color: var(--text-muted); font-style: italic;
  text-align: center; font-family: var(--font-mono);
}

/* ── PATIENT LOAD ECHO CARD ──────────────────────────── */
.patient-load-card {
  background: var(--surface); border: 1px solid var(--border2);
  border-radius: var(--r); padding: 12px 16px;
  border-left: 3px solid var(--teal);
  animation: fadeUp 0.25s ease both;
}
.pl-top { display: flex; align-items: center; gap: 12px; }
.pl-action {
  font-size: 9px; font-family: var(--font-mono); letter-spacing: 1.2px;
  text-transform: uppercase; color: var(--teal); margin-bottom: 2px;
}
```

### Task 3: Client-Side JavaScript — `public/custom.js`

Create `public/custom.js` for accordion toggle, patient selector card clicks, assess chip interaction, and input placeholder override. Chainlit injects this script globally.

```js
/* ── Diagnostic Copilot — Custom JS ─────────────────── */

/* Accordion toggle for differential diagnosis cards */
function toggleCard(card) {
  card.classList.toggle('open');
}

/* MutationObserver: attach click handlers to dynamically injected elements */
var observer = new MutationObserver(function (mutations) {
  mutations.forEach(function (m) {
    m.addedNodes.forEach(function (node) {
      if (node.querySelectorAll) {
        /* Differential accordion headers */
        node.querySelectorAll('.dc-header').forEach(function (hdr) {
          if (!hdr.dataset.bound) {
            hdr.dataset.bound = '1';
            hdr.addEventListener('click', function () {
              toggleCard(hdr.closest('.diff-card'));
            });
          }
        });

        /* Assess chip click → inject HPO term into chat input */
        node.querySelectorAll('.assess-chip').forEach(function (chip) {
          if (!chip.dataset.bound) {
            chip.dataset.bound = '1';
            chip.addEventListener('click', function () {
              var term = chip.dataset.hpoId;
              var label = chip.dataset.hpoLabel;
              if (term) {
                var input = document.querySelector('textarea, input[type="text"]');
                if (input) {
                  var nativeSet = Object.getOwnPropertyDescriptor(
                    window.HTMLTextAreaElement.prototype, 'value'
                  );
                  if (!nativeSet) {
                    nativeSet = Object.getOwnPropertyDescriptor(
                      window.HTMLInputElement.prototype, 'value'
                    );
                  }
                  if (nativeSet && nativeSet.set) {
                    nativeSet.set.call(input, 'Assess for: ' + term + ' (' + label + ')');
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                  }
                }
              }
            });
          }
        });

        /* Patient selector card click → find and click corresponding action button */
        node.querySelectorAll('.patient-select-card').forEach(function (card) {
          if (!card.dataset.bound) {
            card.dataset.bound = '1';
            card.addEventListener('click', function () {
              var idx = parseInt(card.dataset.patientIndex, 10);
              /* Find the Chainlit action buttons and click the matching one */
              var buttons = document.querySelectorAll('button[id^="action"]');
              if (buttons[idx]) {
                buttons[idx].click();
              }
            });
          }
        });
      }
    });
  });
});
observer.observe(document.body, { childList: true, subtree: true });

/* Override input placeholder */
var placeholderInterval = setInterval(function () {
  var input = document.querySelector('textarea, input[type="text"]');
  if (input) {
    input.placeholder = 'Paste a clinical note, enter HP: terms, or select a patient\u2026';
    clearInterval(placeholderInterval);
  }
}, 500);
```

**Key JS behaviours:**
1. **Accordion toggle** — `.dc-header` click toggles `.open` class on parent `.diff-card`
2. **Assess chip click** — Uses native value setter to inject HPO term into chat textarea
3. **Patient selector card** — Click finds the corresponding `cl.Action` button by index and clicks it
4. **Placeholder override** — Polls for input element and sets custom placeholder text

---

## Phase 3B: Pipeline Adapter & Data Provider

### Task 4: `chainlit_utils/pipeline_adapter.py`

This is the **single import point** for the diagnostic pipeline. `app.py` imports ONLY `run_diagnostic_pipeline` from here — never from `agent/` or `chainlit_utils/mock_pipeline.py` directly.

```python
"""
chainlit_utils/pipeline_adapter.py — Single import point for the diagnostic pipeline.

Delegates to either mock or real pipeline based on USE_MOCK_PIPELINE env var.
app.py imports ONLY this function — never mock or real pipeline directly.

Switching from mock → real:
    Set USE_MOCK_PIPELINE=false in .env (or shell). No code changes needed.

Both mock and real pipelines share the EXACT same interface:
    async def run_diagnostic_pipeline(
        patient_input: PatientInput,
        data: dict | None,
        session_mgr: SessionManager | None,
        step_callback = None,
    ) -> AgentOutput
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Coroutine, Optional

from core.models import AgentOutput, PatientInput

logger = logging.getLogger(__name__)

# ── Type alias (matches real pipeline) ─────────────────────────────────
StepCallback = Optional[Callable[[str, Any], Coroutine[Any, Any, None] | None]]

_USE_MOCK = os.environ.get("USE_MOCK_PIPELINE", "true").lower() in ("true", "1", "yes")


async def run_diagnostic_pipeline(
    patient_input: PatientInput,
    data: dict | None = None,
    session_mgr: Any = None,
    step_callback: StepCallback = None,
) -> AgentOutput:
    """
    Run the diagnostic pipeline — delegates to mock or real.

    Parameters match agent.pipeline.run_pipeline exactly.
    """

    if _USE_MOCK:
        # Lazy import — so missing agent/tools deps don't crash mock mode
        from chainlit_utils.mock_pipeline import mock_run_pipeline

        logger.info("Running MOCK pipeline")
        return await mock_run_pipeline(
            patient_input=patient_input,
            data=data,
            session_mgr=session_mgr,
            step_callback=step_callback,
        )

    # ── Real pipeline ──────────────────────────────────────────────
    from agent.pipeline import run_pipeline

    logger.info("Running REAL pipeline")
    if data is None:
        raise RuntimeError(
            "Real pipeline requires data dict from load_all(). "
            "Set USE_MOCK_PIPELINE=true or ensure MongoDB is available."
        )
    return await run_pipeline(
        patient_input=patient_input,
        data=data,
        session_mgr=session_mgr,
        step_callback=step_callback,
    )
```

**Key design decisions:**
- `_USE_MOCK` is read once at module load from env var
- **Lazy imports** inside the function — if mock mode is active, `agent.pipeline` is never imported, so missing deps (Azure keys, MongoDB, etc.) won't crash the server
- The real pipeline function signature is `run_pipeline(patient_input, data, session_mgr, step_callback)` from `agent.pipeline`

### Task 5: `chainlit_utils/data_provider.py`

Isolates data loading from `app.py`. Handles both mock and real data sources.

```python
"""
chainlit_utils/data_provider.py — Isolates data loading from app.py.

When USE_MOCK_PIPELINE=true (default):
    - Returns mock patients from mock_pipeline.py
    - No MongoDB or Redis connection attempted
    - Works on any machine without infrastructure

When USE_MOCK_PIPELINE=false:
    - Connects to MongoDB, loads all reference data via core.data_loader
    - Initialises Redis SessionManager
    - Requires MONGODB_URI, REDIS_URL in .env
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# ── Module-level cache (populated on first call) ──────────────────────
_data_cache: dict | None = None
_session_mgr: object | None = None
_patients: list[dict] | None = None

_USE_MOCK = os.environ.get("USE_MOCK_PIPELINE", "true").lower() in ("true", "1", "yes")


async def load_data() -> tuple[Optional[dict], list[dict]]:
    """
    Load reference data and patient list.

    Returns
    -------
    (data_cache, patients_list)
        data_cache is None when mocked (pipeline doesn't need it).
        patients_list is always a list of patient dicts with
        keys: _id, age, sex, diagnosis_name, diagnosis_omim, hpo_terms.
    """
    global _data_cache, _session_mgr, _patients

    if _patients is not None:
        return _data_cache, _patients

    if _USE_MOCK:
        logger.info("USE_MOCK_PIPELINE=true — loading mock patients (no DB needed)")
        from chainlit_utils.mock_pipeline import get_mock_patients, get_mock_hpo_index

        _patients = get_mock_patients()
        # Store hpo_index in data_cache for the formatter
        _data_cache = {"hpo_index": get_mock_hpo_index()}
        return _data_cache, _patients

    # ── Real mode: connect to MongoDB + Redis ──────────────────────
    logger.info("USE_MOCK_PIPELINE=false — connecting to MongoDB and Redis")
    from core.database import get_db
    from core.data_loader import load_all
    from core.session_manager import SessionManager
    from core.config import REDIS_URL

    db = get_db()
    _data_cache = load_all(db)
    _patients = _data_cache.get("patients", [])
    _session_mgr = SessionManager(REDIS_URL)
    return _data_cache, _patients


def get_session_mgr():
    """Return the SessionManager instance (None when mocked)."""
    return _session_mgr


def get_hpo_index() -> dict:
    """Return the hpo_index dict from data_cache (works in both mock and real)."""
    if _data_cache and "hpo_index" in _data_cache:
        return _data_cache["hpo_index"]
    return {}


def is_mock_mode() -> bool:
    """Return True if running with mock pipeline."""
    return _USE_MOCK
```

**Key design decisions:**
- Module-level cache with `_data_cache`, `_session_mgr`, `_patients` — data loaded once per server lifecycle
- `load_data()` is async for consistency (real mode may need async DB connection in future)
- `get_hpo_index()` provides a convenience accessor used by both formatters and app.py
- `is_mock_mode()` for optional UI display

### Task 6: `chainlit_utils/mock_pipeline.py`

Returns hardcoded `AgentOutput` using the **same Pydantic models** as the real pipeline. Uses the **same `step_callback` protocol** as `agent.pipeline.run_pipeline`.

**Structure:**

1. **`MOCK_PATIENTS`** — 5 patient dicts matching the MongoDB document shape:
   ```python
   {"_id": "patient_01", "age": 3, "sex": "F",
    "diagnosis_name": "3-methylglutaconic aciduria type VIII",
    "diagnosis_omim": "OMIM:617248",
    "hpo_terms": ["HP:0001252", "HP:0001263", "HP:0000252", "HP:0001250", "HP:0000505"]}
   ```

2. **`MOCK_HPO_INDEX`** — 19 HPO ID → label mappings covering all mock patient terms plus common missing phenotypes used in the differential output.

3. **`get_mock_patients()`** and **`get_mock_hpo_index()`** — simple getters for `data_provider.py` to call.

4. **`_build_mock_output(patient_input)`** — Builds a realistic `AgentOutput` with:
   - `patient_hpo_observed`: `HPOMatch` for each input HPO term
   - `patient_hpo_excluded`: 1 excluded finding
   - `timing_profiles`: 1 timing profile
   - `data_completeness`: 0.42
   - `red_flags`: 1 red flag (WARNING — Infantile spasms)
   - `differential`: 5 entries with realistic reasoning, supporting/contradicting/missing phenotypes
   - `next_best_steps`: 4 steps with urgency levels and action types
   - `what_would_change`: 4 items
   - `uncertainty`: known/missing/ambiguous lists

5. **`mock_run_pipeline(patient_input, data, session_mgr, step_callback)`** — Main entry point:
   - **Same function signature** as `agent.pipeline.run_pipeline`
   - Fires `step_callback` with the same step names the real pipeline uses:
     1. `"Red Flag Check"` — sleeps 0.5s, returns `{"flags": 1, "detail": "WARNING — Infantile spasms"}`
     2. `"HPO Mapping"` — sleeps 0.7s, returns mapped terms summary
     3. `"Disease Matching"` — sleeps 0.8s, returns top 3 candidates
     4. `"Phenotype Extraction"` — sleeps 0.6s (only if `patient_input.free_text` is set)
     5. `"Disease Profile Fetch"` — sleeps 0.5s
     6. `"Complete"` — sleeps 0.8s, signals end
   - Returns `_build_mock_output(patient_input)`

**Step callback protocol (2 arguments):**
```python
async def step_callback(step_name: str, result: Any) -> None:
```
- `step_name`: One of the step names above. `"Complete"` signals pipeline is done.
- `result`: A dict with at least a `"detail"` key for display in the `cl.Step` output.

### Task 7: `chainlit_utils/__init__.py`

Re-exports the public API:

```python
"""
chainlit_utils — UI helpers for the Diagnostic Copilot Chainlit frontend.

Re-exports the public API:
    - format_agent_output   (HTML card builder)
    - run_diagnostic_pipeline  (adapter → mock or real pipeline)
    - load_data / get_session_mgr  (data provider)
"""

from chainlit_utils.formatters import format_agent_output
from chainlit_utils.pipeline_adapter import run_diagnostic_pipeline
from chainlit_utils.data_provider import load_data, get_session_mgr

__all__ = [
    "format_agent_output",
    "run_diagnostic_pipeline",
    "load_data",
    "get_session_mgr",
]
```

---

## Phase 3C: App Entry Point — `app.py`

This is the main Chainlit application file. It has **zero conditional branches** for mock vs real — all switching is handled inside `chainlit_utils/`.

### Task 8: Imports & Globals

```python
"""
app.py — Chainlit entry point for the Diagnostic Copilot UI.

Run with:  chainlit run app.py -w

Switching between mock and real pipeline:
    Mock (default, no DB needed):  USE_MOCK_PIPELINE=true
    Real (needs MongoDB/Redis/LLM): USE_MOCK_PIPELINE=false

This file has ZERO conditional branches for mock vs real.
All switching is handled inside chainlit_utils/.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from typing import Any

import chainlit as cl

from core.models import PatientInput
from chainlit_utils.formatters import format_agent_output, format_welcome_card, format_patient_load_card
from chainlit_utils.pipeline_adapter import run_diagnostic_pipeline
from chainlit_utils.data_provider import load_data, get_session_mgr, get_hpo_index

logger = logging.getLogger(__name__)

# ---------- Globals loaded once at startup ----------
DATA: dict | None = None
PATIENTS: list[dict] = []
```

**Key points:**
- Import from `chainlit_utils` only — never from `agent/` or `tools/`
- Import `PatientInput` from `core.models` (shared contract)
- `DATA` and `PATIENTS` are populated once per server lifecycle in `on_chat_start`

### Task 9: Startup Hook — `@cl.on_chat_start`

```python
@cl.on_chat_start
async def on_chat_start():
    """Initialise data and session on new conversation."""
    global DATA, PATIENTS

    # Load reference data & patients (mock or real, handled by data_provider)
    if DATA is None:
        DATA, PATIENTS = await load_data()

    # Generate session ID
    session_id = str(uuid.uuid4())
    cl.user_session.set("session_id", session_id)
    cl.user_session.set("current_hpo_terms", [])
    cl.user_session.set("current_patient", None)

    # Build patient selector action buttons (functional clicks)
    actions = []
    for i, patient in enumerate(PATIENTS[:15]):
        pid = patient.get("_id", f"patient_{i+1}")
        age = patient.get("age", "?")
        sex = patient.get("sex", "?")
        name = patient.get("diagnosis_name", "Unknown")
        hpo_count = len(patient.get("hpo_terms", []))
        label = f"{pid}: {age}yo {sex} — {name} ({hpo_count} HPO)"

        actions.append(
            cl.Action(
                name="load_patient",
                payload={"patient_index": i, "patient_id": pid},
                label=label,
            )
        )

    # Build styled HTML welcome dashboard
    hpo_index = get_hpo_index()
    welcome_html = format_welcome_card(PATIENTS, hpo_index)

    await cl.Message(
        content=welcome_html,
        actions=actions,
    ).send()
```

**Welcome message architecture:**
- The `cl.Action` buttons are attached to the message for functional interaction (Chainlit-native click handling)
- The `format_welcome_card()` HTML provides the visual dashboard (branded header, instruction tiles, patient grid)
- The patient grid cards in the HTML have `data-patient-index` attributes — the JS `MutationObserver` binds click handlers that find and click the corresponding `cl.Action` button

### Task 10: Patient Selector Callback

```python
@cl.action_callback("load_patient")
async def on_load_patient(action: cl.Action):
    """Handle patient button click — load patient and run analysis."""
    patient_index = action.payload.get("patient_index", 0)
    patient_id = action.payload.get("patient_id", "?")

    if patient_index >= len(PATIENTS):
        await cl.Message(content=f"❌ Patient index {patient_index} out of range.").send()
        return

    patient = PATIENTS[patient_index]
    hpo_terms = patient.get("hpo_terms", [])
    age = patient.get("age")
    sex = patient.get("sex")

    # Store in session
    cl.user_session.set("current_hpo_terms", hpo_terms)
    cl.user_session.set("current_patient", patient)

    # Send styled patient-load card (HTML, not plain text)
    hpo_index = get_hpo_index()
    load_html = format_patient_load_card(patient, hpo_index)
    await cl.Message(content=load_html).send()

    # Build input and run
    patient_input = PatientInput(
        hpo_terms=hpo_terms,
        age=age,
        sex=sex,
    )
    await run_analysis(patient_input, patient)
```

**Patient load echo:** Uses `format_patient_load_card()` which renders a teal-bordered card with the patient's avatar, name, age/sex, and HPO term chips — NOT a plain text echo.

### Task 11: Manual Input Handler

```python
@cl.on_message
async def on_message(message: cl.Message):
    """Handle incoming user message — parse and run pipeline."""
    text = message.content.strip()
    if not text:
        return

    # Check for HPO term pattern
    hpo_pattern = re.findall(r"HP:\d{7}", text)

    current_terms = cl.user_session.get("current_hpo_terms") or []
    patient_meta = cl.user_session.get("current_patient")

    if hpo_pattern:
        # HPO term input — merge with any existing session terms
        merged = list(set(current_terms + hpo_pattern))
        cl.user_session.set("current_hpo_terms", merged)

        patient_input = PatientInput(
            hpo_terms=merged,
            age=patient_meta.get("age") if patient_meta else None,
            sex=patient_meta.get("sex") if patient_meta else None,
        )
    else:
        # Treat as free text
        patient_input = PatientInput(
            free_text=text,
            hpo_terms=current_terms,
            age=patient_meta.get("age") if patient_meta else None,
            sex=patient_meta.get("sex") if patient_meta else None,
        )

    await run_analysis(patient_input, patient_meta)
```

**Input parsing:** Simple HPO regex pattern matching. If `HP:\d{7}` found → treat as HPO terms (merge with session). Otherwise → treat as free text. No complex clinical language detection needed.

### Task 12: Add HPO Term Callback

```python
@cl.action_callback("add_hpo_term")
async def on_add_hpo_term(action: cl.Action):
    """Handle assess chip click — add HPO term and re-run."""
    hpo_id = action.payload.get("hpo_id", "")
    label = action.payload.get("label", "")

    current_terms = cl.user_session.get("current_hpo_terms") or []
    patient_meta = cl.user_session.get("current_patient")

    if hpo_id and hpo_id not in current_terms:
        current_terms.append(hpo_id)
        cl.user_session.set("current_hpo_terms", current_terms)

    # Send a styled "phenotype added" card
    await cl.Message(
        content=(
            '<div class="patient-load-card" style="border-left-color:var(--green);">'
            '<div class="pl-top">'
            '<div style="width:32px;height:32px;border-radius:8px;background:var(--green-dim);'
            'color:var(--green);display:flex;align-items:center;justify-content:center;font-size:14px;">+</div>'
            '<div>'
            f'<div class="pl-action" style="color:var(--green);">Phenotype added — re-running analysis</div>'
            f'<div class="cp-name">{label}</div>'
            f'<div class="cp-sub" style="font-family:var(--font-mono);font-size:10px;">{hpo_id}</div>'
            '</div></div></div>'
        )
    ).send()

    patient_input = PatientInput(
        hpo_terms=current_terms,
        age=patient_meta.get("age") if patient_meta else None,
        sex=patient_meta.get("sex") if patient_meta else None,
    )

    await run_analysis(patient_input, patient_meta)
```

### Task 13: Core Analysis Runner — `run_analysis()`

This is the most important function. It runs the pipeline with step-by-step `cl.Step` visualization.

```python
STEP_EMOJIS = {
    "Red Flag Check": "🚨",
    "HPO Mapping": "🔍",
    "Disease Matching": "🧬",
    "Phenotype Extraction": "📝",
    "Disease Profile Fetch": "📋",
    "Complete": "🧠",
}


async def run_analysis(
    patient_input: PatientInput,
    patient_meta: dict | None = None,
) -> None:
    step_durations: list[dict] = []
    step_start_times: dict[str, float] = {}
    active_steps: dict[str, cl.Step] = {}

    async def step_callback(step_name: str, result: Any) -> None:
        """Chainlit step visualization callback — same protocol as real pipeline."""
        nonlocal step_durations

        # Close previous step if open
        for prev_name, prev_step in list(active_steps.items()):
            if prev_name in step_start_times:
                dur = time.monotonic() - step_start_times[prev_name]
                step_durations.append({"name": prev_name, "duration": round(dur, 1)})
                del step_start_times[prev_name]

        if step_name == "Complete":
            for name, start in list(step_start_times.items()):
                dur = time.monotonic() - start
                step_durations.append({"name": name, "duration": round(dur, 1)})
            step_start_times.clear()
            active_steps.clear()
            return

        # Create a new Chainlit step
        emoji = STEP_EMOJIS.get(step_name, "⚙️")
        step = cl.Step(name=f"{emoji} {step_name}", type="tool")
        step_start_times[step_name] = time.monotonic()
        active_steps[step_name] = step

        await step.__aenter__()

        # Format step output
        if isinstance(result, dict):
            detail = result.get("detail", "")
            step.output = detail or json.dumps(result, indent=2, default=str)
        else:
            step.output = str(result) if result else "Done"

        await step.__aexit__(None, None, None)

    try:
        # Run the pipeline
        output = await run_diagnostic_pipeline(
            patient_input=patient_input,
            data=DATA,
            session_mgr=get_session_mgr(),
            step_callback=step_callback,
        )

        # Build the complete HTML card output
        hpo_index = get_hpo_index()
        html_content = format_agent_output(
            output=output,
            patient_meta=patient_meta,
            hpo_index=hpo_index,
            step_durations=step_durations,
        )

        # Build action buttons for missing phenotypes (assess chips)
        assess_actions = []
        seen_labels: set[str] = set()
        for entry in output.differential[:3]:
            for label in entry.missing_key_phenotypes:
                if label.lower() not in seen_labels:
                    seen_labels.add(label.lower())
                    # Reverse-lookup HPO ID
                    hpo_id = ""
                    for hid, hlbl in hpo_index.items():
                        if hlbl.lower() == label.lower():
                            hpo_id = hid
                            break
                    assess_actions.append(
                        cl.Action(
                            name="add_hpo_term",
                            payload={"hpo_id": hpo_id, "label": label},
                            label=f"+ {label}",
                        )
                    )

        # Send the single output message with all HTML cards
        await cl.Message(
            content=html_content,
            actions=assess_actions[:8],  # Cap at 8 action buttons
        ).send()

    except Exception as e:
        logger.exception("Pipeline error")
        await cl.Message(
            content=(
                f"❌ **Analysis Error**\n\n"
                f"`{type(e).__name__}: {e}`\n\n"
                f"Try loading a test patient, or paste HPO terms in format `HP:XXXXXXX`.\n\n"
                f"_If the error persists, check the server logs for details._"
            )
        ).send()
```

**Key implementation details:**

1. **Step callback** receives `(step_name, result)` — 2 args, not 3
2. **Step tracking** — Uses `time.monotonic()` to measure wall-clock duration per step
3. **cl.Step context** — Uses `__aenter__`/`__aexit__` directly to control lifecycle
4. **Step output** — Extracts `result.get("detail")` for display in the step panel
5. **`"Complete"` step** signals pipeline end — records any remaining durations, clears state
6. **Assess actions** — `cl.Action` buttons with `name="add_hpo_term"` attached to the final message, capped at 8
7. **Error handling** — try/except wraps the entire analysis, sends formatted error message

---

## Phase 3D: HTML Card Formatter — `chainlit_utils/formatters.py`

This is the core rendering module. It takes an `AgentOutput` plus metadata and returns a **single HTML string** containing all card components. This HTML is passed to `cl.Message(content=html_string)`.

### Main Entry Point

```python
def format_agent_output(
    output: AgentOutput,
    patient_meta: dict | None = None,
    hpo_index: dict | None = None,
    step_durations: list[dict] | None = None,
) -> str:
```

**Note:** The `step_durations` parameter was added to support the step summary card at the top of the output. It's a list of `{"name": str, "duration": float}` dicts.

**The function assembles these HTML sections in order:**

1. `_build_step_summary(step_durations)` — Step timing summary
2. `_build_patient_header(output, patient_meta, hpo_index)` — Patient card
3. `_build_stats_row(output)` — 4-tile stats grid with gauge
4. `_build_red_flags(output)` — Red flags (conditional)
5. `_build_differential(output, hpo_index)` — Accordion cards
6. `_build_assess_chips(output, hpo_index)` — Refine chips
7. `_build_next_steps_and_uncertainty(output)` — Two-column layout

Each section returns an HTML string (or empty string if no data). They are joined with newlines.

### Section Builder Details

**Step Summary Card** (`_build_step_summary`):
Uses CSS classes `.step-summary`, `.step-summary-row`, `.step-summary-icon`, `.step-summary-name`, `.step-summary-dur`. Each row shows ✓ icon, step name, and duration in seconds.

**Patient Header** (`_build_patient_header`):
- Avatar: Uses last 2 chars of patient ID + sex initial (e.g. "01F"). CSS class `card-patient-avatar` plus sex class (`.m` or `.f`).
- Chips: Loops over `output.patient_hpo_observed`, resolves labels via `hpo_index` if `HPOMatch.label` is empty.

**Stats Row** (`_build_stats_row`):
- Data completeness gauge: `pct = int(output.data_completeness * 100)`, `offset = round(113 - (113 * output.data_completeness), 1)`
- Red flags tile: Uses `var(--rose)` if flags > 0, `var(--green)` if 0.

**Differential** (`_build_differential`):
- Confidence class: `{"high": "high", "moderate": "mod", "low": "low"}`
- First card starts open (CSS class `open`)
- Score percentage: Rank-based fallback `max(10, 100 - (i * 15))` when real coverage_pct unavailable
- Tags: Supporting → `.tag.s` with ✓, contradicting → `.tag.x` with ✗, missing → `.tag.m` with ⚠

**Assess Chips** (`_build_assess_chips`):
- Deduplicates `missing_key_phenotypes` across top 3 differential entries
- Each chip has `data-hpo-id` and `data-hpo-label` for JS handler
- Reverse-looks up HPO ID from `hpo_index`

**Two-Column Layout** (`_build_next_steps_and_uncertainty`):
- Left: Next steps cards with urgency classes and action type labels
- Right: Uncertainty 3-column grid + What Would Change list
- Wrapped in `.two-col` grid (responsive — collapses to single column on mobile)

### Additional Formatters

**`format_welcome_card(patients, hpo_index)`:**
Builds the welcome dashboard HTML:

```html
<div class="welcome-card">
  <!-- Hero header with DNA logo + title + status -->
  <div class="welcome-header">
    <div class="welcome-logo">🧬</div>
    <div>
      <div class="welcome-title">Diagnostic<span style="color:var(--teal)">Copilot</span></div>
      <div class="welcome-subtitle">AI-powered rare disease diagnostic reasoning</div>
    </div>
    <div class="welcome-status">
      <span class="welcome-status-dot"></span>
      {n} patients · {n} HPO terms loaded
    </div>
  </div>

  <!-- 3-column instruction tiles -->
  <div class="welcome-instructions">
    <div class="welcome-instr-item">📋 Clinical Note — Paste free-text symptoms</div>
    <div class="welcome-instr-item">🏷️ HPO Terms — Enter HP:XXXXXXX IDs</div>
    <div class="welcome-instr-item">👤 Test Patient — Select below</div>
  </div>

  <!-- Patient selector grid -->
  <div class="section-head">👤 Select a Patient <span class="section-cnt">{n} available</span></div>
  <div class="patient-select-grid">
    <!-- One card per patient with avatar, name, detail, HPO count -->
    <div class="patient-select-card" data-patient-index="{i}">...</div>
  </div>

  <!-- Disclaimer -->
  <div class="welcome-disclaimer">LLMs can make mistakes — verify clinical decisions independently</div>
</div>
```

Each `.patient-select-card` has `data-patient-index` attribute. The JS `MutationObserver` binds click handlers that find and click the matching `cl.Action` button from the message.

**`format_patient_load_card(patient, hpo_index)`:**
Builds a teal-bordered card echoing the loaded patient:

```html
<div class="patient-load-card">
  <div class="pl-top">
    <div class="card-patient-avatar {sex_class}">...</div>
    <div>
      <div class="pl-action">Loading patient for analysis</div>
      <div class="cp-name">Patient {id} — {age}yo {sex}</div>
      <div class="cp-sub">{name} · {count} HPO terms</div>
    </div>
  </div>
  <div class="cp-chips">{hpo_chips}</div>
</div>
```

### Helper Functions

- `_esc(text)` — `html.escape(str(text))` for safe HTML rendering
- `ACTION_TYPE_LABELS` — Maps `action_type` enum to display: `order_test` → "Order Test", etc.
- `CONF_CSS` — Maps confidence to CSS class: `high` → `"high"`, `moderate` → `"mod"`, `low` → `"low"`

---

## Phase 3E: Running & Testing

### Start the Server

```bash
# Mock mode (default — no DB needed)
chainlit run app.py -w

# Real mode (needs MongoDB, Redis, Azure OpenAI)
USE_MOCK_PIPELINE=false chainlit run app.py -w
```

Server starts on port 8000. The `-w` flag enables auto-reload on file changes.

### Verify

1. Open `http://localhost:8000` — should see the branded welcome dashboard
2. Click any patient card — should see patient-load echo card, then step indicators, then full diagnostic output
3. Check accordion expand/collapse on differential cards
4. Check assess chip buttons below the output
5. Paste `HP:0001250, HP:0001263` in chat — should trigger analysis
6. Click an assess chip — should show "Phenotype added" card and re-run

---

## File Checklist

| File | Purpose | Lines |
| ---- | ------- | ----- |
| `.chainlit/config.toml` | Chainlit 2.x configuration: HTML enabled, wide layout, CoT full, custom CSS/JS | ~175 |
| `public/custom.css` | Full dark-theme stylesheet: card components + welcome dashboard + patient load + step summary | ~389 |
| `public/custom.js` | Accordion toggle, assess-chip click, patient-card click, placeholder override | ~80 |
| `app.py` | Chainlit entry point: startup, message handling, action callbacks, `run_analysis()` | ~319 |
| `chainlit_utils/__init__.py` | Package init — re-exports public API | ~17 |
| `chainlit_utils/formatters.py` | `format_agent_output()`, `format_welcome_card()`, `format_patient_load_card()`, section builders | ~512 |
| `chainlit_utils/pipeline_adapter.py` | Single import point — delegates mock/real via `USE_MOCK_PIPELINE` env var | ~70 |
| `chainlit_utils/data_provider.py` | Data loading abstraction — mock patients or MongoDB/Redis | ~80 |
| `chainlit_utils/mock_pipeline.py` | Hardcoded `AgentOutput` + `step_callback` protocol matching real pipeline | ~405 |

---

## HTML Component Quick Reference

| Component | CSS Root Class | HTML Element | Data Source |
| --------- | -------------- | ------------ | ----------- |
| Welcome dashboard | `.welcome-card` | `<div>` | Patient list + HPO index count |
| Welcome instructions | `.welcome-instructions` | `<div>` grid | Static 3 tiles |
| Patient selector grid | `.patient-select-grid` | `<div>` grid | Patient list (capped at 15) |
| Patient load echo | `.patient-load-card` | `<div>` | Patient dict + HPO index |
| Step summary | `.step-summary` | `<div>` | Step durations from pipeline run |
| Patient header | `.card-patient` | `<div>` | Patient metadata + `patient_hpo_observed` |
| Stats row | `.card-stats` | `<div>` grid | `data_completeness`, HPO count, candidate count, red flag count |
| Completeness gauge | `.gauge` | `<svg>` | `data_completeness` float |
| Red flags alert | `.red-flag-card` | `<div>` | `red_flags` list |
| Differential card | `.diff-card` | `<div>` accordion | `differential` list |
| Confidence bar | `.dc-fill` | `<div>` | Rank-based percentage or `coverage_pct` |
| Confidence badge | `.dc-conf-badge` | `<span>` | `confidence` literal |
| Patient avatar (male) | `.card-patient-avatar.m` | `<div>` | Blue tint — `patient_meta["sex"]` |
| Patient avatar (female) | `.card-patient-avatar.f` | `<div>` | Teal tint — `patient_meta["sex"]` |
| Phenotype tag (matched) | `.tag.s` | `<span>` | `supporting_phenotypes` |
| Phenotype tag (contradicting) | `.tag.x` | `<span>` | `contradicting_phenotypes` |
| Phenotype tag (missing) | `.tag.m` | `<span>` | `missing_key_phenotypes` |
| Assess chip | `.assess-chip` | `<span>` | Deduplicated `missing_key_phenotypes` from top 3 |
| Next step card | `.step-crd` | `<div>` | `next_best_steps` list |
| Uncertainty grid | `.uncert-cols` | `<div>` 3-col grid | `uncertainty` (known/missing/ambiguous) |
| What Would Change | `.wwc-list` | `<div>` list | `what_would_change` strings |
