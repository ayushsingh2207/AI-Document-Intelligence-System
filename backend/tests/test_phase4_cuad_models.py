"""
Phase 4 Tests: Baseline Extractor, Transformer QA & Metric Evaluation
====================================================================
Tests that verify:
1. Exact Match and Token-level F1 calculations with multiple gold answers
2. Correct handling of unanswerable (no-answer) questions
3. Character span mapping from tokenizer offsets back to source contract context
4. Baseline extractor trigger detection and scoring
5. Transformer sliding-window output schema and boundary integrity
"""

import pytest
from app.experiments.cuad.evaluator import (
    compute_exact_match,
    compute_token_f1,
    CUADEvaluator,
)
from app.experiments.cuad.baseline_extractor import CUADBaselineExtractor
from app.experiments.cuad.transformer_qa import CUADTransformerQA


class TestCUADEvaluationMetrics:
    """Verifies standard academic extractive QA and detection metrics."""

    def test_exact_match_single_gold(self):
        assert compute_exact_match("State of New York", ["State of New York"]) == 1.0
        assert compute_exact_match("state of new york", ["State of New York"]) == 1.0
        assert compute_exact_match("New York", ["State of New York"]) == 0.0

    def test_exact_match_multiple_gold_answers(self):
        gold = ["New York", "State of New York", "Delaware"]
        assert compute_exact_match("State of New York", gold) == 1.0
        assert compute_exact_match("Delaware", gold) == 1.0
        assert compute_exact_match("California", gold) == 0.0

    def test_exact_match_unanswerable_handling(self):
        # Empty gold means clause is absent (unanswerable)
        assert compute_exact_match("", []) == 1.0
        assert compute_exact_match("some text", []) == 0.0

    def test_token_f1_calculation(self):
        gold = ["the laws of the State of New York"]
        # Partial overlap
        pred = "laws of New York"
        f1 = compute_token_f1(pred, gold)
        assert 0.0 < f1 < 1.0
        # Complete match
        assert compute_token_f1("the laws of the state of new york", gold) == 1.0
        # No overlap
        assert compute_token_f1("unrelated contract term", gold) == 0.0

    def test_token_f1_unanswerable_handling(self):
        assert compute_token_f1("", []) == 1.0
        assert compute_token_f1("extracted span", []) == 0.0

    def test_cuad_evaluator_aggregate_and_category_breakdown(self):
        examples = [
            {"id": "q1", "category": "Governing Law", "is_impossible": False, "gold_answers": ["New York"]},
            {"id": "q2", "category": "Governing Law", "is_impossible": True, "gold_answers": []},
            {"id": "q3", "category": "Non-Compete", "is_impossible": False, "gold_answers": ["12 months"]},
            {"id": "q4", "category": "Non-Compete", "is_impossible": True, "gold_answers": []},
        ]
        # Predict q1 correct, q2 correct no-answer, q3 false negative, q4 false positive
        predictions = {
            "q1": "New York",
            "q2": "",
            "q3": "",
            "q4": "some text",
        }
        report = CUADEvaluator.evaluate_predictions(examples, predictions)
        assert report["total_evaluated"] == 4
        # q1: EM=1.0, q2: EM=1.0, q3: EM=0.0, q4: EM=0.0 -> aggregate EM = 50.0%
        assert report["exact_match"] == 50.0
        assert "Governing Law" in report["by_category"]
        assert "Non-Compete" in report["by_category"]
        assert report["by_category"]["Governing Law"]["exact_match"] == 100.0
        assert report["by_category"]["Non-Compete"]["exact_match"] == 0.0


class TestBaselineExtractor:
    """Verifies the heuristic/BM25 baseline extractor."""

    @pytest.fixture
    def baseline(self):
        return CUADBaselineExtractor(confidence_threshold=1.5)

    def test_extract_governing_law(self, baseline):
        context = (
            "Section 12. Governing Law. This Agreement shall be governed by and "
            "construed in accordance with the laws of the State of Delaware."
        )
        text, start, end, score = baseline.extract_clause(
            context, "Governing Law", "What is the governing law?"
        )
        assert "Delaware" in text
        assert start >= 0
        assert end > start
        assert context[start:end] == text

    def test_unanswerable_returns_empty_when_below_threshold(self, baseline):
        context = "This agreement governs the delivery of widgets."
        text, start, end, score = baseline.extract_clause(
            context, "Covenant Not To Sue", "Highlight any Covenant Not To Sue."
        )
        assert text == ""
        assert start == -1
        assert end == -1


class TestTransformerQAEngine:
    """Verifies transformer extractive QA engine and character offset preservation."""

    @pytest.fixture(scope="class")
    def transformer_qa(self):
        return CUADTransformerQA(null_threshold=0.0)

    def test_model_metadata(self, transformer_qa):
        info = transformer_qa.get_model_info()
        assert info["model_name"] == "distilbert/distilbert-base-uncased-distilled-squad"
        assert info["license"] == "Apache-2.0"
        assert info["parameter_count"] > 60_000_000

    def test_extractive_span_character_offset_accuracy(self, transformer_qa):
        context = (
            "The Parties agree that this Agreement shall be governed by the laws of California. "
            "Neither party may assign this Agreement without prior written consent."
        )
        question = "What is the Governing Law?"
        pred_text, start_char, end_char, score = transformer_qa.predict_clause(context, question)

        assert pred_text != ""
        assert "California" in pred_text
        assert start_char >= 0
        assert end_char > start_char
        # Character slice must match predicted text exactly
        assert context[start_char:end_char] == pred_text

    def test_unanswerable_span_returns_empty(self, transformer_qa):
        # Empty context
        pred_text, start, end, score = transformer_qa.predict_clause("", "What is the Governing Law?")
        assert pred_text == ""
        assert start == -1
        assert end == -1
