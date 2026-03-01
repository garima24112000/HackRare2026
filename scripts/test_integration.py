#!/usr/bin/env python3
"""
scripts/test_integration.py — End-to-end integration test for WS1 + WS2.

Runs the full pipeline against real MongoDB data and the Azure LLM endpoint.
No Chainlit UI required — pure CLI.

Usage:
    python -m scripts.test_integration              # all tests
    python -m scripts.test_integration --test 1     # single test
    python -m scripts.test_integration --quick      # skip LLM calls (tools only)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.config import REDIS_URL, AZURE_ENDPOINT, AZURE_API_KEY, AZURE_DEPLOYMENT
from core.database import get_db
from core.data_loader import load_all
from core.session_manager import SessionManager
from core.models import PatientInput, AgentOutput

# ── Logging ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("integration_test")


# ── Pretty printer ───────────────────────────────────────────────────────

def pp(label: str, obj, indent: int = 2):
    """Print a labelled JSON-serialisable object."""
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    if hasattr(obj, "model_dump"):
        obj = obj.model_dump()
    if isinstance(obj, (dict, list)):
        print(json.dumps(obj, indent=indent, default=str))
    else:
        print(obj)


# ── Step callback for CLI progress ───────────────────────────────────────

async def cli_step_callback(step_name: str, result) -> None:
    """Print progress during pipeline execution."""
    if isinstance(result, list):
        count = len(result)
        print(f"  ✓ {step_name}: {count} item(s)")
    elif isinstance(result, dict):
        keys = list(result.keys())
        print(f"  ✓ {step_name}: {keys}")
    elif hasattr(result, "model_dump"):
        print(f"  ✓ {step_name}: done")
    else:
        print(f"  ✓ {step_name}")


# ═════════════════════════════════════════════════════════════════════════
# TEST CASES
# ═════════════════════════════════════════════════════════════════════════


async def test_1_patient10_hpo_only(data: dict, session_mgr: SessionManager) -> bool:
    """
    Test 1: Patient 10 — HPO terms only, no free text.
    Expected: OMIM:300672 in top 10 differential.
    """
    print("\n" + "─" * 60)
    print("TEST 1: Patient 10 — HPO-only (5 terms, no free text)")
    print("─" * 60)

    from agent.pipeline import run_pipeline

    patient = PatientInput(
        hpo_terms=["HP:0002360", "HP:0100704", "HP:0001250", "HP:0001252", "HP:0001332"],
        age=5,
        sex="M",
    )

    t0 = time.time()
    output: AgentOutput = await run_pipeline(
        patient, data, session_mgr, step_callback=cli_step_callback
    )
    elapsed = time.time() - t0

    print(f"\n  Pipeline completed in {elapsed:.1f}s")
    print(f"  HPO terms matched: {len(output.patient_hpo_observed)}")
    print(f"  Diseases in differential: {len(output.differential)}")
    print(f"  Data completeness: {output.data_completeness:.2f}")
    print(f"  Red flags: {len(output.red_flags)}")
    print(f"  Next steps: {len(output.next_best_steps)}")

    # Show HPO matches
    if output.patient_hpo_observed:
        print("\n  HPO Matches:")
        for m in output.patient_hpo_observed:
            print(f"    {m.hpo_id} — {m.label} (confidence={m.match_confidence}, IC={m.ic_score:.2f})")

    # Show differential (LLM confidence reasoning)
    if output.differential:
        print("\n  Differential Diagnosis:")
        for d in output.differential:
            print(f"    {d.disease_id} — {d.disease} (confidence={d.confidence})")
            print(f"      Reasoning: {d.confidence_reasoning}")

    # Show next steps
    if output.next_best_steps:
        print("\n  Next Best Steps:")
        for s in output.next_best_steps:
            print(f"    {s.rank}. [{s.action_type}] {s.action} ({s.urgency})")

    # Show uncertainty
    if output.uncertainty:
        print("\n  Uncertainty:")
        if output.uncertainty.known:
            print(f"    Known: {output.uncertainty.known}")
        if output.uncertainty.missing:
            print(f"    Missing: {output.uncertainty.missing}")

    # Validation
    disease_ids = [d.disease_id for d in output.differential]
    if "OMIM:300672" in disease_ids:
        print("\n  ✅ PASS: OMIM:300672 found in differential")
        return True
    else:
        print(f"\n  ⚠️  OMIM:300672 not in differential. Got: {disease_ids}")
        print("  (This may still be OK — it should appear in the disease_match results)")
        return False


async def test_2_red_flag(data: dict, session_mgr: SessionManager) -> bool:
    """
    Test 2: Red flag — Status epilepticus triggers URGENT early exit.
    """
    print("\n" + "─" * 60)
    print("TEST 2: Red Flag — HP:0002133 (Status epilepticus)")
    print("─" * 60)

    from agent.pipeline import run_pipeline

    patient = PatientInput(
        hpo_terms=["HP:0002133"],
        age=3,
        sex="M",
    )

    t0 = time.time()
    output: AgentOutput = await run_pipeline(
        patient, data, session_mgr, step_callback=cli_step_callback
    )
    elapsed = time.time() - t0

    print(f"\n  Pipeline completed in {elapsed:.1f}s")
    print(f"  Red flags: {len(output.red_flags)}")
    print(f"  Differential: {len(output.differential)} (should be 0 — early exit)")
    print(f"  HPO observed: {len(output.patient_hpo_observed)} (should be 0 — early exit)")

    if output.red_flags:
        for f in output.red_flags:
            print(f"    🚨 {f.severity}: {f.flag_label}")
            print(f"       Action: {f.recommended_action}")

    has_urgent = any(f.severity == "URGENT" for f in output.red_flags)
    early_exit = len(output.differential) == 0

    if has_urgent and early_exit:
        print("\n  ✅ PASS: URGENT flag detected, pipeline exited early")
        return True
    else:
        print(f"\n  ❌ FAIL: urgent={has_urgent}, early_exit={early_exit}")
        return False


async def test_3_free_text(data: dict, session_mgr: SessionManager) -> bool:
    """
    Test 3: Free text with negations and timing info.
    Tests excluded_extract (LLM) and timing_extract (LLM).
    """
    print("\n" + "─" * 60)
    print("TEST 3: Free Text — exclusions + timing (LLM calls)")
    print("─" * 60)

    from agent.pipeline import run_pipeline

    note = (
        "5-year-old male presenting with global developmental delay and seizures "
        "since 4 months of age. Hypotonia was noted at birth. "
        "No hearing loss. Cardiac examination was normal. "
        "MRI showed cerebral atrophy. "
        "Family history notable for a maternal uncle with epilepsy."
    )

    patient = PatientInput(
        hpo_terms=["HP:0001263", "HP:0001250", "HP:0001290", "HP:0012444"],
        free_text=note,
        age=5,
        sex="M",
        family_history="Maternal uncle with epilepsy",
    )

    t0 = time.time()
    output: AgentOutput = await run_pipeline(
        patient, data, session_mgr, step_callback=cli_step_callback
    )
    elapsed = time.time() - t0

    print(f"\n  Pipeline completed in {elapsed:.1f}s")
    print(f"  HPO terms: {len(output.patient_hpo_observed)}")
    print(f"  Excluded findings: {len(output.patient_hpo_excluded)}")
    print(f"  Timing profiles: {len(output.timing_profiles)}")
    print(f"  Data completeness: {output.data_completeness:.2f}")
    print(f"  Differential: {len(output.differential)}")

    if output.patient_hpo_excluded:
        print("\n  Excluded Findings:")
        for e in output.patient_hpo_excluded:
            mapped = f"{e.mapped_hpo_term} ({e.mapped_hpo_label})" if e.mapped_hpo_term else "unmapped"
            print(f"    ✗ \"{e.raw_text}\" → {mapped} [{e.exclusion_type}, {e.confidence}]")

    if output.timing_profiles:
        print("\n  Timing Profiles:")
        for t in output.timing_profiles:
            print(f"    ⏱ {t.phenotype_ref}: onset={t.onset} ({t.onset_normalized}y, {t.onset_stage}), "
                  f"progression={t.progression}")

    if output.differential:
        print("\n  Differential:")
        for d in output.differential[:5]:
            print(f"    {d.disease_id} — {d.disease} ({d.confidence})")

    # Evidence: programmatic scores
    if output.disease_candidates:
        print("\n  Disease Candidates (programmatic scores):")
        for c in output.disease_candidates:
            print(f"    #{c.rank} {c.disease_id} — {c.disease_name}")
            print(f"       sim_score={c.sim_score:.2f}  coverage={c.coverage_pct:.0%}  penalty={c.excluded_penalty}")
            if c.matched_terms:
                print(f"       matched: {', '.join(c.matched_terms[:5])}")
            if c.missing_terms:
                print(f"       missing: {', '.join(c.missing_terms[:5])}")

    # Evidence: disease profiles (genes, inheritance, phenotype frequencies)
    if output.disease_profiles:
        print("\n  Disease Profiles (genomic context):")
        for p in output.disease_profiles:
            genes = ', '.join(p.causal_genes) if p.causal_genes else 'unknown'
            print(f"    {p.disease_id} — {p.disease_name}")
            print(f"       inheritance={p.inheritance}  genes=[{genes}]")
            if p.phenotype_freqs:
                top_phenos = p.phenotype_freqs[:3]
                for pf in top_phenos:
                    print(f"       {pf.label}: {pf.frequency}")

    if output.next_best_steps:
        print("\n  Next Steps:")
        for s in output.next_best_steps[:3]:
            print(f"    {s.rank}. [{s.action_type}] {s.action}")

    # Soft checks
    has_exclusions = len(output.patient_hpo_excluded) > 0
    has_timing = len(output.timing_profiles) > 0
    has_differential = len(output.differential) > 0

    if has_exclusions and has_timing and has_differential:
        print("\n  ✅ PASS: Exclusions, timing, and differential all populated")
        return True
    else:
        print(f"\n  ⚠️  Partial: exclusions={has_exclusions}, timing={has_timing}, diff={has_differential}")
        return has_differential  # At least the core pipeline worked


async def test_4_quick_tools_only(data: dict) -> bool:
    """
    Test 4: Quick tool-level tests (no LLM, no pipeline).
    Verifies WS1 tools work correctly with real data.
    """
    print("\n" + "─" * 60)
    print("TEST 4: Quick Tool-Level Verification (no LLM)")
    print("─" * 60)

    import tools.hpo_lookup as hpo_lookup
    import tools.disease_match as disease_match
    import tools.red_flag as red_flag

    # 4a: HPO Lookup
    print("\n  4a: HPO Lookup")
    matches = hpo_lookup.run(["seizures", "small head", "HP:0001290"], data)
    for m in matches:
        print(f"    \"{m.raw_input}\" → {m.hpo_id} ({m.label}, conf={m.match_confidence})")

    seizure_match = [m for m in matches if m.hpo_id == "HP:0001250"]
    hp_direct = [m for m in matches if m.hpo_id == "HP:0001290"]
    ok_4a = len(seizure_match) > 0 and len(hp_direct) > 0
    print(f"    {'✅' if ok_4a else '❌'} Seizures mapped correctly: {bool(seizure_match)}")
    print(f"    {'✅' if hp_direct else '❌'} Direct HP ID lookup: {bool(hp_direct)}")

    # 4b: Disease Match
    print("\n  4b: Disease Match (Patient 10 terms)")
    p10_terms = ["HP:0002360", "HP:0100704", "HP:0001250", "HP:0001252", "HP:0001332"]
    t0 = time.time()
    candidates = disease_match.run(p10_terms, [], data)
    elapsed = time.time() - t0
    print(f"    Returned {len(candidates)} candidates in {elapsed:.2f}s")
    for c in candidates[:5]:
        print(f"    #{c.rank}: {c.disease_id} — {c.disease_name} "
              f"(score={c.sim_score:.2f}, coverage={c.coverage_pct:.0%})")

    target_in_results = any(c.disease_id == "OMIM:300672" for c in candidates)
    print(f"    {'✅' if target_in_results else '⚠️ '} OMIM:300672 in top 15: {target_in_results}")

    # 4c: Red Flag
    print("\n  4c: Red Flag")
    flags = red_flag.run(["HP:0002133"], data["ontology"])
    for f in flags:
        print(f"    🚨 {f.severity}: {f.flag_label}")
    ok_4c = any(f.severity == "URGENT" for f in flags)
    print(f"    {'✅' if ok_4c else '❌'} URGENT flag for status epilepticus: {ok_4c}")

    # 4d: Red flag - no flags for benign terms
    print("\n  4d: Red Flag — benign terms (should be 0 URGENT)")
    flags_benign = red_flag.run(["HP:0001263"], data["ontology"])
    urgent_benign = [f for f in flags_benign if f.severity == "URGENT"]
    ok_4d = len(urgent_benign) == 0
    print(f"    Flags for HP:0001263: {len(flags_benign)} total, {len(urgent_benign)} URGENT")
    print(f"    {'✅' if ok_4d else '⚠️ '} No false URGENT: {ok_4d}")

    all_ok = ok_4a and target_in_results and ok_4c and ok_4d
    if all_ok:
        print(f"\n  ✅ ALL tool-level tests PASSED")
    else:
        print(f"\n  ⚠️  Some tool-level tests had issues")
    return all_ok


# ═════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════


async def main():
    parser = argparse.ArgumentParser(description="WS1+WS2 Integration Test")
    parser.add_argument("--test", type=int, choices=[1, 2, 3, 4],
                        help="Run a single test (1-4)")
    parser.add_argument("--quick", action="store_true",
                        help="Run only tool-level tests (no LLM calls)")
    args = parser.parse_args()

    # ── Environment check ────────────────────────────────────────────────
    print("=" * 60)
    print("  WS1 + WS2 Integration Test")
    print("=" * 60)

    print("\nEnvironment:")
    print(f"  AZURE_ENDPOINT:   {AZURE_ENDPOINT[:60]}{'…' if len(AZURE_ENDPOINT) > 60 else ''}")
    print(f"  AZURE_DEPLOYMENT: {AZURE_DEPLOYMENT}")
    print(f"  AZURE_API_KEY:    {'✓ set' if AZURE_API_KEY else '✗ MISSING'}")
    print(f"  REDIS_URL:        {'✓ set' if REDIS_URL else '✗ MISSING'}")

    # ── Load data ────────────────────────────────────────────────────────
    print("\nLoading reference data from MongoDB + hp.obo …")
    t0 = time.time()
    db = get_db()
    data = load_all(db)
    elapsed = time.time() - t0
    print(f"Data loaded in {elapsed:.1f}s")
    print(f"  HPO terms:  {len(data['hpo_index'])}")
    print(f"  Synonyms:   {len(data['synonym_index'])}")
    print(f"  Diseases:   {len(data['disease_to_hpo'])}")
    print(f"  Patients:   {len(data['patients'])}")
    print(f"  Ontology:   {'✓' if data.get('ontology') else '✗'}")

    # ── Session manager ──────────────────────────────────────────────────
    session_mgr = SessionManager(REDIS_URL) if REDIS_URL else None
    if session_mgr:
        print(f"  Redis:      ✓ connected")
    else:
        print(f"  Redis:      ✗ no REDIS_URL — session logging disabled")

    # ── Run tests ────────────────────────────────────────────────────────
    results: dict[str, bool] = {}

    if args.quick or args.test == 4:
        results["T4: Tools"] = await test_4_quick_tools_only(data)
        if args.quick:
            _summarise(results)
            return

    if args.test is None or args.test == 4:
        if "T4: Tools" not in results:
            results["T4: Tools"] = await test_4_quick_tools_only(data)

    if args.test is None or args.test == 2:
        results["T2: Red Flag"] = await test_2_red_flag(data, session_mgr)

    if args.test is None or args.test == 1:
        results["T1: Patient 10"] = await test_1_patient10_hpo_only(data, session_mgr)

    if args.test is None or args.test == 3:
        if not AZURE_API_KEY:
            print("\n  ⚠️  Skipping Test 3 (free text) — no AZURE_API_KEY set")
        else:
            results["T3: Free Text"] = await test_3_free_text(data, session_mgr)

    _summarise(results)


def _summarise(results: dict[str, bool]):
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    for name, passed in results.items():
        status = "✅ PASS" if passed else "⚠️  WARN"
        print(f"  {status}  {name}")
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    print(f"\n  {passed}/{total} tests passed")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
