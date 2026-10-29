"""
CUAD Evaluation Metrics
=======================
Standard academic evaluation functions for extractive QA on legal contracts.
Supports:
- Exact Match (EM)
- Token-level F1 (SQuAD 2.0 specification)
- Clause-level Classification Metrics (Precision, Recall, F1 for detection)
- Macro and per-category breakdown across all 41 categories
- Correct handling of unanswerable (no-answer) questions
"""

import re
import string
from collections import Counter
from typing import List, Dict, Any, Tuple, Optional


def normalize_answer(s: str) -> str:
    """
    Lower text and remove punctuation, articles, and extra whitespace.
    Standard SQuAD / CUAD text normalization.
    """
    def remove_articles(text: str) -> str:
        return re.sub(r"\b(a|an|the)\b", " ", text)

    def white_space_fix(text: str) -> str:
        return " ".join(text.split())

    def remove_punc(text: str) -> str:
        exclude = set(string.punctuation)
        return "".join(ch for ch in text if ch not in exclude)

    def lower(text: str) -> str:
        return text.lower()

    if not s:
        return ""
    return white_space_fix(remove_articles(remove_punc(lower(s))))


def compute_exact_match(prediction: str, gold_answers: List[str]) -> float:
    """
    Computes Exact Match (EM) score.
    If gold_answers is empty (unanswerable):
      EM = 1.0 if prediction is empty, 0.0 otherwise.
    If gold_answers is not empty:
      EM = 1.0 if normalized prediction matches ANY normalized gold answer, 0.0 otherwise.
    """
    norm_pred = normalize_answer(prediction)
    if not gold_answers:
        return 1.0 if not norm_pred else 0.0

    for gold in gold_answers:
        if norm_pred == normalize_answer(gold):
            return 1.0
    return 0.0


def compute_token_f1(prediction: str, gold_answers: List[str]) -> float:
    """
    Computes token-level F1 score.
    If gold_answers is empty:
      F1 = 1.0 if prediction is empty, 0.0 otherwise.
    If gold_answers is not empty:
      F1 = max(f1(prediction, gold) for gold in gold_answers).
    """
    norm_pred = normalize_answer(prediction)
    if not gold_answers:
        return 1.0 if not norm_pred else 0.0

    pred_tokens = norm_pred.split()
    if not pred_tokens:
        return 0.0

    best_f1 = 0.0
    for gold in gold_answers:
        gold_tokens = normalize_answer(gold).split()
        if not gold_tokens:
            continue

        common = Counter(pred_tokens) & Counter(gold_tokens)
        num_same = sum(common.values())
        if num_same == 0:
            continue

        precision = 1.0 * num_same / len(pred_tokens)
        recall = 1.0 * num_same / len(gold_tokens)
        f1 = (2 * precision * recall) / (precision + recall)
        if f1 > best_f1:
            best_f1 = f1

    return best_f1


class CUADEvaluator:
    """
    Evaluates extraction predictions across multiple contracts and categories.
    """

    @staticmethod
    def evaluate_predictions(
        examples: List[Dict[str, Any]],
        predictions: Dict[str, str],
        iou_threshold: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Evaluate predictions against gold examples.

        Args:
            examples: List of dicts, each with:
                - 'id': question ID
                - 'category': clause category name
                - 'contract_id': contract identifier
                - 'is_impossible': bool
                - 'gold_answers': List[str]
            predictions: Dict mapping question ID -> predicted text string (or "" for no-answer)
            iou_threshold: token overlap threshold for detection TP

        Returns:
            Dict containing:
                - 'exact_match': aggregate EM %
                - 'token_f1': aggregate token F1 %
                - 'detection': precision, recall, f1 for clause presence
                - 'answerable_metrics': EM and F1 on answerable questions only
                - 'unanswerable_metrics': EM on unanswerable questions only
                - 'by_category': per-category metrics breakdown
                - 'total_evaluated': count of questions evaluated
        """
        total = len(examples)
        if total == 0:
            return {"error": "No examples provided for evaluation"}

        em_scores = []
        f1_scores = []

        ans_em_scores = []
        ans_f1_scores = []
        unans_em_scores = []

        # Extractive Detection classification (IoU thresholded)
        tp = 0
        fp = 0
        fn = 0
        tn = 0

        # Binary Clause-Presence Classification (Presence vs Absence)
        bin_tp = 0
        bin_fp = 0
        bin_fn = 0
        bin_tn = 0

        # Category breakdowns
        cat_data: Dict[str, Dict[str, Any]] = {}

        for ex in examples:
            qid = ex["id"]
            cat = ex.get("category", "General")
            gold_answers = ex.get("gold_answers", [])
            is_unanswerable = ex.get("is_impossible", len(gold_answers) == 0)

            pred_text = predictions.get(qid, "").strip()

            em = compute_exact_match(pred_text, gold_answers)
            f1 = compute_token_f1(pred_text, gold_answers)

            em_scores.append(em)
            f1_scores.append(f1)

            # Detection classification
            predicted_present = bool(pred_text)
            actual_present = not is_unanswerable

            # 1. Binary presence classification
            if actual_present and predicted_present:
                bin_tp += 1
            elif not actual_present and predicted_present:
                bin_fp += 1
            elif actual_present and not predicted_present:
                bin_fn += 1
            else:
                bin_tn += 1

            # 2. Extractive span detection (IoU thresholded)
            if actual_present and predicted_present:
                if f1 >= iou_threshold:
                    tp += 1
                else:
                    # Predicted text failed overlap threshold: missed the true clause and produced an incorrect span
                    fp += 1
                    fn += 1
            elif actual_present and not predicted_present:
                fn += 1
            elif not actual_present and predicted_present:
                fp += 1
            else:  # not actual_present and not predicted_present
                tn += 1

            if actual_present:
                ans_em_scores.append(em)
                ans_f1_scores.append(f1)
            else:
                unans_em_scores.append(em)

            # Category tracking
            if cat not in cat_data:
                cat_data[cat] = {
                    "total": 0,
                    "answerable": 0,
                    "unanswerable": 0,
                    "em_list": [],
                    "f1_list": [],
                    "tp": 0,
                    "fp": 0,
                    "fn": 0,
                    "tn": 0,
                    "bin_tp": 0,
                    "bin_fp": 0,
                    "bin_fn": 0,
                    "bin_tn": 0,
                }

            cat_data[cat]["total"] += 1
            cat_data[cat]["em_list"].append(em)
            cat_data[cat]["f1_list"].append(f1)
            if actual_present:
                cat_data[cat]["answerable"] += 1
            else:
                cat_data[cat]["unanswerable"] += 1

            if actual_present and predicted_present:
                bin_tp_cat = 1
                bin_fp_cat = 0
                bin_fn_cat = 0
                bin_tn_cat = 0
                if f1 >= iou_threshold:
                    cat_data[cat]["tp"] += 1
                else:
                    cat_data[cat]["fp"] += 1
                    cat_data[cat]["fn"] += 1
            elif actual_present and not predicted_present:
                bin_tp_cat = 0
                bin_fp_cat = 0
                bin_fn_cat = 1
                bin_tn_cat = 0
                cat_data[cat]["fn"] += 1
            elif not actual_present and predicted_present:
                bin_tp_cat = 0
                bin_fp_cat = 1
                bin_fn_cat = 0
                bin_tn_cat = 0
                cat_data[cat]["fp"] += 1
            else:
                bin_tp_cat = 0
                bin_fp_cat = 0
                bin_fn_cat = 0
                bin_tn_cat = 1
                cat_data[cat]["tn"] += 1

            cat_data[cat]["bin_tp"] += bin_tp_cat
            cat_data[cat]["bin_fp"] += bin_fp_cat
            cat_data[cat]["bin_fn"] += bin_fn_cat
            cat_data[cat]["bin_tn"] += bin_tn_cat

        # Aggregate Extractive Detection Metrics
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        det_f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

        # Aggregate Binary Presence Metrics
        b_prec = bin_tp / (bin_tp + bin_fp) if (bin_tp + bin_fp) > 0 else 0.0
        b_rec = bin_tp / (bin_tp + bin_fn) if (bin_tp + bin_fn) > 0 else 0.0
        b_det_f1 = (2 * b_prec * b_rec) / (b_prec + b_rec) if (b_prec + b_rec) > 0 else 0.0

        # Category Aggregation
        by_category = {}
        for cat, cvals in cat_data.items():
            c_tp = cvals["tp"]
            c_fp = cvals["fp"]
            c_fn = cvals["fn"]
            c_prec = c_tp / (c_tp + c_fp) if (c_tp + c_fp) > 0 else 0.0
            c_rec = c_tp / (c_tp + c_fn) if (c_tp + c_fn) > 0 else 0.0
            c_det_f1 = (2 * c_prec * c_rec) / (c_prec + c_rec) if (c_prec + c_rec) > 0 else 0.0

            cb_tp = cvals["bin_tp"]
            cb_fp = cvals["bin_fp"]
            cb_fn = cvals["bin_fn"]
            cb_prec = cb_tp / (cb_tp + cb_fp) if (cb_tp + cb_fp) > 0 else 0.0
            cb_rec = cb_tp / (cb_tp + cb_fn) if (cb_tp + cb_fn) > 0 else 0.0
            cb_det_f1 = (2 * cb_prec * cb_rec) / (cb_prec + cb_rec) if (cb_prec + cb_rec) > 0 else 0.0

            by_category[cat] = {
                "total_questions": cvals["total"],
                "answerable": cvals["answerable"],
                "unanswerable": cvals["unanswerable"],
                "exact_match": round(100.0 * sum(cvals["em_list"]) / len(cvals["em_list"]), 2),
                "token_f1": round(100.0 * sum(cvals["f1_list"]) / len(cvals["f1_list"]), 2),
                "detection_precision": round(100.0 * c_prec, 2),
                "detection_recall": round(100.0 * c_rec, 2),
                "detection_f1": round(100.0 * c_det_f1, 2),
                "binary_presence_precision": round(100.0 * cb_prec, 2),
                "binary_presence_recall": round(100.0 * cb_rec, 2),
                "binary_presence_f1": round(100.0 * cb_det_f1, 2),
            }

        return {
            "total_evaluated": total,
            "overall_squad_metrics": {
                "exact_match": round(100.0 * sum(em_scores) / total, 2),
                "token_f1": round(100.0 * sum(f1_scores) / total, 2),
            },
            "exact_match": round(100.0 * sum(em_scores) / total, 2),
            "token_f1": round(100.0 * sum(f1_scores) / total, 2),
            "extractive_detection_iou_0_5": {
                "precision": round(100.0 * prec, 2),
                "recall": round(100.0 * rec, 2),
                "f1": round(100.0 * det_f1, 2),
                "correct_extractions": tp,
                "invalid_extractions": fp,
                "missed_extractions": fn,
                "correct_abstentions": tn,
                "accounting_note": (
                    "Not a conventional binary confusion matrix: an incorrect or sub-threshold span prediction "
                    "on an answerable clause is penalized as both a missed valid extraction (missed_extractions / FN) "
                    "and an invalid extraction (invalid_extractions / FP). Therefore, the sum of counts exceeds total questions."
                ),
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "tn": tn,
                "iou_threshold": iou_threshold,
            },
            "detection": {
                "precision": round(100.0 * prec, 2),
                "recall": round(100.0 * rec, 2),
                "f1": round(100.0 * det_f1, 2),
                "correct_extractions": tp,
                "invalid_extractions": fp,
                "missed_extractions": fn,
                "correct_abstentions": tn,
                "accounting_note": (
                    "Not a conventional binary confusion matrix: an incorrect or sub-threshold span prediction "
                    "on an answerable clause is penalized as both a missed valid extraction (missed_extractions / FN) "
                    "and an invalid extraction (invalid_extractions / FP)."
                ),
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "tn": tn,
                "iou_threshold": iou_threshold,
            },
            "binary_presence": {
                "positive_prediction_definition": "Any non-empty predicted span string, regardless of span correctness",
                "precision": round(100.0 * b_prec, 2),
                "recall": round(100.0 * b_rec, 2),
                "f1": round(100.0 * b_det_f1, 2),
                "tp_present_detected": bin_tp,
                "fp_absent_hallucinated": bin_fp,
                "fn_present_missed": bin_fn,
                "tn_absent_abstained": bin_tn,
                "tp": bin_tp,
                "fp": bin_fp,
                "fn": bin_fn,
                "tn": bin_tn,
            },
            "answerable_only_metrics": {
                "count": len(ans_em_scores),
                "exact_match": round(100.0 * sum(ans_em_scores) / len(ans_em_scores), 2) if ans_em_scores else 0.0,
                "token_f1": round(100.0 * sum(ans_f1_scores) / len(ans_f1_scores), 2) if ans_f1_scores else 0.0,
            },
            "unanswerable_only_metrics": {
                "count": len(unans_em_scores),
                "exact_match": round(100.0 * sum(unans_em_scores) / len(unans_em_scores), 2) if unans_em_scores else 0.0,
                "abstention_accuracy": round(100.0 * sum(unans_em_scores) / len(unans_em_scores), 2) if unans_em_scores else 0.0,
            },
            "answerable_metrics": {
                "count": len(ans_em_scores),
                "exact_match": round(100.0 * sum(ans_em_scores) / len(ans_em_scores), 2) if ans_em_scores else 0.0,
                "token_f1": round(100.0 * sum(ans_f1_scores) / len(ans_f1_scores), 2) if ans_f1_scores else 0.0,
            },
            "unanswerable_metrics": {
                "count": len(unans_em_scores),
                "exact_match": round(100.0 * sum(unans_em_scores) / len(unans_em_scores), 2) if unans_em_scores else 0.0,
            },
            "by_category": by_category,
        }
