"""
Phase 4 Step 4 Tests: Evaluation, Candidate Prefilter, and Fine-Tuning Verification
==================================================================================
Tests:
1. CandidateWindowPrefilter ranking and window subset selection.
2. Evaluator detection matrix accounting consistency.
3. Sliding-window target offset mapping for QA fine-tuning.
4. Pilot resource scaling and extrapolation logic.
5. Benchmark comparison and validation tuning artifact integrity.
"""

import os
import json
import pytest
import torch

from app.experiments.cuad.candidate_filter import CandidateWindowPrefilter
from app.experiments.cuad.evaluator import (
    compute_exact_match,
    compute_token_f1,
    normalize_answer,
    CUADEvaluator,
)
from app.experiments.cuad.fine_tuner import CUADFineTuner, CUADQADataset
from app.experiments.cuad.transformer_qa import CUADTransformerQA


def test_candidate_window_prefilter_selection():
    """Verify prefilter ranks windows with category trigger matches first."""
    prefilter = CandidateWindowPrefilter(top_k_windows=2)
    windows = [
        "The distributor shall make regular payments according to schedule A.",
        "This Agreement shall be governed by and construed in accordance with the laws of California.",
        "The company was incorporated in Delaware in 1999.",
        "General definitions and miscellaneous terms.",
    ]
    # Question on Governing Law
    question = "Which state/country's law governs the interpretation of the contract?"
    selected = prefilter.filter_windows(question, "Governing Law", windows)

    assert len(selected) <= 2
    # Window index 1 has "governed by and construed in accordance with the laws of California"
    assert 1 in selected


def test_evaluator_detection_confusion_matrix_consistency():
    """Verify detection TP + FN equals actual_present and TP + FP equals predicted_present."""
    examples = [
        {"id": "q1", "category": "Parties", "is_impossible": False, "gold_answers": ["Acme Corp"]},
        {"id": "q2", "category": "Parties", "is_impossible": False, "gold_answers": ["Beta LLC"]},
        {"id": "q3", "category": "Governing Law", "is_impossible": True, "gold_answers": []},
        {"id": "q4", "category": "Audit Rights", "is_impossible": True, "gold_answers": []},
    ]
    predictions = {
        "q1": "Acme Corp",       # TP (exact match)
        "q2": "Completely Wrong", # Missed true clause, produced wrong span -> FN=1, FP=1
        "q3": "Spurious Clause",  # FP (predicted on unanswerable)
        "q4": "",                 # TN (correct unanswerable)
    }

    metrics = CUADEvaluator.evaluate_predictions(examples, predictions, iou_threshold=0.5)
    det = metrics["detection"]

    # Total actual present = 2 (q1, q2)
    assert det["tp"] + det["fn"] == 2
    # Total predicted present = 3 (q1, q2, q3) -> tp(1) + fp(2) = 3
    assert det["tp"] + det["fp"] == 3
    # TN = 1 (q4)
    assert det["tn"] == 1
    assert metrics["exact_match"] == 50.0  # q1 and q4 are EM


def test_fine_tuner_feature_extraction_structure():
    """Verify that fine-tuning feature extraction maps answer spans correctly."""
    tuner = CUADFineTuner()
    dummy_contract = {
        "context": "This Agreement is made by and between ABC Corp and XYZ Inc on January 1, 2020.",
        "qas": [
            {
                "id": "q1",
                "question": "Highlight the Document Name",
                "category": "Document Name",
                "is_impossible": False,
                "answers": [{"text": "Agreement", "answer_start": 5}],
            },
            {
                "id": "q2",
                "question": "Highlight Expiration Date",
                "category": "Expiration Date",
                "is_impossible": True,
                "answers": [],
            }
        ]
    }
    features = tuner.prepare_training_features([dummy_contract], max_samples=2)
    assert len(features) == 2

    # Check answerable sample
    ans_feat = next(f for f in features if not f["is_impossible"])
    assert ans_feat["start_position"] > 0
    assert ans_feat["end_position"] >= ans_feat["start_position"]

    # Check unanswerable sample
    unans_feat = next(f for f in features if f["is_impossible"])
    assert unans_feat["start_position"] == 0
    assert unans_feat["end_position"] == 0


def test_transformer_qa_prefilter_integration():
    """Verify CUADTransformerQA predict_clause accepts prefilter parameters."""
    qa_model = CUADTransformerQA()
    context = "Section 1. Governing Law. This agreement is governed by New York law. Section 2. Miscellaneous."
    question = "Which law governs?"

    # Predict with prefilter enabled
    text, start, end, score = qa_model.predict_clause(
        context=context,
        question=question,
        category="Governing Law",
        use_prefilter=True,
        top_k_windows=2,
    )
    assert isinstance(text, str)
    assert isinstance(start, int)
    assert isinstance(end, int)
    assert isinstance(score, float)


def test_cuad_artifacts_presence_and_schema():
    """Verify all Step 4 results and model artifacts exist and adhere to schema."""
    cuad_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cuad")
    results_dir = os.path.join(cuad_dir, "results")
    models_dir = os.path.join(cuad_dir, "models")

    # 1. Pilot report
    pilot_path = os.path.join(results_dir, "cuad_finetuning_pilot.json")
    assert os.path.exists(pilot_path)
    with open(pilot_path, "r", encoding="utf-8") as f:
        pilot = json.load(f)
    assert "step_latency" in pilot
    assert "loss_trajectory" in pilot
    assert "full_cuad_cpu_extrapolation" in pilot

    # 2. Validation tuning report
    val_path = os.path.join(results_dir, "cuad_validation_tuning.json")
    assert os.path.exists(val_path)
    with open(val_path, "r", encoding="utf-8") as f:
        val = json.load(f)
    assert "prefilter_benchmark" in val
    assert "threshold_calibration" in val
    assert val["prefilter_benchmark"]["speedup_factor"] > 1.0

    # 3. Comparative benchmark report
    bench_path = os.path.join(results_dir, "cuad_benchmark_comparison.json")
    assert os.path.exists(bench_path)
    with open(bench_path, "r", encoding="utf-8") as f:
        bench = json.load(f)
    assert "evaluation_protocol" in bench
    assert "runtime_comparison" in bench
    assert "aggregate_metrics" in bench
    assert "error_analysis" in bench

    # 4. Fine-tuned model checkpoint
    ft_dir = os.path.join(models_dir, "distilbert_cuad_finetuned")
    assert os.path.exists(ft_dir)
    assert os.path.exists(os.path.join(ft_dir, "model.safetensors"))
    assert os.path.exists(os.path.join(ft_dir, "config.json"))
    assert os.path.exists(os.path.join(ft_dir, "training_meta.json"))


def test_partial_overlap_and_wrong_spans_detection_accounting():
    """
    Verify exact distinction between answer extraction quality and clause-presence detection:
    - Partial overlap (0 < F1 < 0.5): Fails extractive threshold (FN=1, FP=1), but succeeds binary presence (bin_tp=1).
    - Completely wrong span (F1 = 0): Fails extractive threshold (FN=1, FP=1), succeeds binary presence (bin_tp=1).
    """
    examples = [
        # Answerable example: gold is "New York State Court"
        {"id": "q1", "category": "Governing Law", "is_impossible": False, "gold_answers": ["New York State Court"]},
        # Answerable example: gold is "Delaware LLC"
        {"id": "q2", "category": "Parties", "is_impossible": False, "gold_answers": ["Delaware LLC"]},
    ]
    predictions = {
        # Partial overlap: "New York" has token overlap with "New York State Court"
        # precision=2/2=1.0, recall=2/4=0.5 -> F1 = (2*1.0*0.5)/1.5 = 0.667 >= 0.5 -> Extractive TP!
        "q1": "New York",
        # Partial overlap below threshold: "Only Court" (recall=1/4=0.25, prec=1/2=0.5 -> F1=0.333 < 0.5)
        # F1 < 0.5 -> Extractive Miss (FN=1, FP=1)
        "q2": "Only Court",
    }

    metrics = CUADEvaluator.evaluate_predictions(examples, predictions, iou_threshold=0.5)

    # Extractive detection (IoU >= 0.5): q1 is TP, q2 fails IoU so FN=1, FP=1
    det = metrics["detection"]
    assert det["tp"] == 1
    assert det["fp"] == 1
    assert det["fn"] == 1
    assert det["precision"] == 50.0  # 1 / (1 + 1)
    assert det["recall"] == 50.0     # 1 / (1 + 1)

    # Binary presence: both contracts actually have the clause, and both models predicted non-empty text
    bin_det = metrics["binary_presence"]
    assert bin_det["tp"] == 2
    assert bin_det["fp"] == 0
    assert bin_det["fn"] == 0
    assert bin_det["recall"] == 100.0
    assert bin_det["precision"] == 100.0

    # Extraction quality on answerable subset:
    assert metrics["answerable_metrics"]["exact_match"] == 0.0
    assert metrics["answerable_metrics"]["token_f1"] > 0.0


def test_empty_predictions_and_absent_clause_fp_tn():
    """
    Verify accounting for empty predictions and absent clauses:
    - Missed answerable clause (empty pred): FN=1 in both extractive and binary.
    - False positive on absent clause: FP=1 in both extractive and binary.
    - Correct abstention on absent clause: TN=1 in both extractive and binary.
    """
    examples = [
        {"id": "q1", "category": "Governing Law", "is_impossible": False, "gold_answers": ["California"]},
        {"id": "q2", "category": "Audit Rights", "is_impossible": True, "gold_answers": []},
        {"id": "q3", "category": "Non-Compete", "is_impossible": True, "gold_answers": []},
    ]
    predictions = {
        "q1": "",                   # Missed answerable -> FN=1
        "q2": "Spurious indemnity", # False positive on unanswerable -> FP=1
        "q3": "",                   # Correct abstention -> TN=1
    }

    metrics = CUADEvaluator.evaluate_predictions(examples, predictions, iou_threshold=0.5)

    det = metrics["detection"]
    assert det["tp"] == 0
    assert det["fn"] == 1
    assert det["fp"] == 1
    assert det["tn"] == 1

    bin_det = metrics["binary_presence"]
    assert bin_det["tp"] == 0
    assert bin_det["fn"] == 1
    assert bin_det["fp"] == 1
    assert bin_det["tn"] == 1

    # SQuAD evaluation:
    # q1: EM=0, F1=0
    # q2: EM=0, F1=0
    # q3: EM=1.0, F1=1.0
    # Aggregate EM: 1/3 = 33.33%, Token F1: 1/3 = 33.33%
    assert metrics["exact_match"] == 33.33
    assert metrics["token_f1"] == 33.33
    assert metrics["unanswerable_metrics"]["exact_match"] == 50.0  # 1 out of 2 unanswerables


def test_internal_consistency_identities():
    """
    Verify mathematical conservation laws across confusion matrices:
    1. bin_tp + bin_fn == count(actual present)
    2. bin_fp + bin_tn == count(actual absent)
    3. bin_tp + bin_fp == count(predicted present)
    4. bin_fn + bin_tn == count(predicted absent)
    5. bin_tp + bin_fp + bin_fn + bin_tn == total examples
    """
    examples = [
        {"id": "q1", "category": "C1", "is_impossible": False, "gold_answers": ["Span A"]},
        {"id": "q2", "category": "C2", "is_impossible": False, "gold_answers": ["Span B"]},
        {"id": "q3", "category": "C3", "is_impossible": True, "gold_answers": []},
        {"id": "q4", "category": "C4", "is_impossible": True, "gold_answers": []},
        {"id": "q5", "category": "C5", "is_impossible": True, "gold_answers": []},
    ]
    predictions = {
        "q1": "Span A",      # actual present, pred present (TP)
        "q2": "",            # actual present, pred absent (FN)
        "q3": "Hallucinated",# actual absent, pred present (FP)
        "q4": "",            # actual absent, pred absent (TN)
        "q5": "",            # actual absent, pred absent (TN)
    }

    metrics = CUADEvaluator.evaluate_predictions(examples, predictions)
    b = metrics["binary_presence"]

    num_actual_present = 2
    num_actual_absent = 3
    num_pred_present = 2
    num_pred_absent = 3
    total = 5

    assert b["tp"] + b["fn"] == num_actual_present
    assert b["fp"] + b["tn"] == num_actual_absent
    assert b["tp"] + b["fp"] == num_pred_present
    assert b["fn"] + b["tn"] == num_pred_absent
    assert b["tp"] + b["fp"] + b["fn"] + b["tn"] == total


def test_fine_tuning_leakage_audit_clean():
    """Verify the fine-tuning data leakage audit artifact proves zero leakage."""
    cuad_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cuad")
    audit_file = os.path.join(cuad_dir, "results", "cuad_finetuning_leakage_audit.json")

    assert os.path.exists(audit_file)
    with open(audit_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    summary = data["audit_summary"]
    assert summary["leakage_status"] == "CLEAN (Zero Leakage)"
    assert summary["any_sample_in_validation"] is False
    assert summary["any_sample_in_test"] is False
    assert summary["total_training_samples"] == 40
    assert summary["source_contracts_count"] == 3

    # Check that source contracts are disjoint from test contracts
    test_titles = [
        "ACCURAYINC_09_01_2010-EX-10.31-DISTRIBUTOR AGREEMENT",
        "AIRTECHINTERNATIONALGROUPINC_05_08_2000-EX-10.4-FRANCHISE AGREEMENT",
        "ALAMOGORDOFINANCIALCORP_12_16_1999-EX-1-AGENCY AGREEMENT",
    ]
    source_ids = [sc["contract_id"] for sc in data["source_contracts"]]
    for sc_id in source_ids:
        assert sc_id not in test_titles
