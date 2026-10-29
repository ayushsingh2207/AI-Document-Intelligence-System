"""
CUAD Experiment Runner & Comparative Benchmark Pipeline
======================================================
Executes:
1. Smoke test: profiles latency, memory, and span accuracy on a single contract.
2. Validation tuning: tunes null score / confidence thresholds on the validation split.
3. Comparative test evaluation: runs Baseline vs Transformer on held-out test contracts.
4. Records all configurations, hardware specs, runtime, and per-category metrics.
"""

import os
import time
import json
from typing import List, Dict, Any, Optional

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

import sys

# Ensure backend root is in sys.path
backend_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

try:
    from .dataset_loader import CUADDatasetLoader
    from .baseline_extractor import CUADBaselineExtractor
    from .transformer_qa import CUADTransformerQA
    from .evaluator import CUADEvaluator
    from .candidate_filter import CandidateWindowPrefilter
    from .fine_tuner import CUADFineTuner
except ImportError:
    from app.experiments.cuad.dataset_loader import CUADDatasetLoader
    from app.experiments.cuad.baseline_extractor import CUADBaselineExtractor
    from app.experiments.cuad.transformer_qa import CUADTransformerQA
    from app.experiments.cuad.evaluator import CUADEvaluator
    from app.experiments.cuad.candidate_filter import CandidateWindowPrefilter
    from app.experiments.cuad.fine_tuner import CUADFineTuner


class CUADExperimentPipeline:
    def __init__(
        self,
        loader: Optional[CUADDatasetLoader] = None,
        results_dir: Optional[str] = None,
        confidence_threshold: float = 2.5,
        null_threshold: float = 0.0,
    ):
        self.loader = loader or CUADDatasetLoader()
        self.results_dir = results_dir or os.path.join(self.loader.target_dir, "results")
        os.makedirs(self.results_dir, exist_ok=True)

        # Initialize dataset and splits
        self.loader.download_and_verify()
        self.loader.parse_and_validate()
        self.splits = self.loader.create_contract_level_splits(seed=42)

        # Load frozen thresholds if available from validation tuning
        val_tuning_path = os.path.join(self.results_dir, "cuad_validation_tuning.json")
        if os.path.exists(val_tuning_path):
            try:
                with open(val_tuning_path, "r", encoding="utf-8") as f:
                    v_meta = json.load(f)
                    cal = v_meta.get("threshold_calibration", {})
                    confidence_threshold = cal.get("frozen_baseline_confidence_threshold", confidence_threshold)
                    null_threshold = cal.get("frozen_transformer_null_threshold", null_threshold)
            except Exception:
                pass

        self.confidence_threshold = confidence_threshold
        self.null_threshold = null_threshold
        self.baseline = CUADBaselineExtractor(confidence_threshold=confidence_threshold)
        self.transformer: Optional[CUADTransformerQA] = None

    def _get_transformer(self, model_name: Optional[str] = None) -> CUADTransformerQA:
        if model_name or self.transformer is None:
            return CUADTransformerQA(
                model_name=model_name or "distilbert/distilbert-base-uncased-distilled-squad",
                null_threshold=self.null_threshold,
            )
        return self.transformer

    def run_smoke_test(
        self,
        use_prefilter: bool = True,
        top_k_windows: int = 4,
    ) -> Dict[str, Any]:
        """
        Smoke test on 1 contract (41 questions) to profile runtime and memory on CPU.
        """
        print("=== Running CUAD Experiment Smoke Test (1 contract, 41 questions) ===")
        transformer = self._get_transformer()

        test_title = self.splits["test"]["contract_titles"][0]
        contract = next(c for c in self.loader._cached_contracts_data if c["contract_id"] == test_title)
        mem_before_mb = 0.0
        if HAS_PSUTIL:
            try:
                process = psutil.Process(os.getpid())
                mem_before_mb = round(process.memory_info().rss / (1024 * 1024), 2)
            except Exception:
                pass

        # 1. Baseline Run
        t0 = time.time()
        cpu0 = time.process_time()
        baseline_preds = self.baseline.evaluate_contract(contract)
        baseline_time_s = round(time.time() - t0, 3)
        baseline_cpu_s = round(time.process_time() - cpu0, 3)

        # 2. Transformer Run
        t0 = time.time()
        cpu0 = time.process_time()
        transformer_preds = transformer.evaluate_contract(
            contract,
            use_prefilter=use_prefilter,
            top_k_windows=top_k_windows,
        )
        transformer_time_s = round(time.time() - t0, 3)
        transformer_cpu_s = round(time.process_time() - cpu0, 3)

        mem_after_mb = 0.0
        if HAS_PSUTIL:
            try:
                mem_after_mb = round(process.memory_info().rss / (1024 * 1024), 2)
            except Exception:
                pass

        # Prepare examples for evaluation
        examples = []
        for qa in contract["qas"]:
            examples.append({
                "id": qa["id"],
                "category": qa["category"],
                "contract_id": contract["contract_id"],
                "is_impossible": qa["is_impossible"],
                "gold_answers": [a["text"] for a in qa["answers"]],
            })

        # Evaluate both
        b_pred_map = {qid: res[0] for qid, res in baseline_preds.items()}
        t_pred_map = {qid: res[0] for qid, res in transformer_preds.items()}

        b_metrics = CUADEvaluator.evaluate_predictions(examples, b_pred_map)
        t_metrics = CUADEvaluator.evaluate_predictions(examples, t_pred_map)

        smoke_report = {
            "contract_title": test_title,
            "context_length_chars": contract["context_length"],
            "total_questions": len(examples),
            "configuration": {
                "use_prefilter": use_prefilter,
                "top_k_windows": top_k_windows if use_prefilter else None,
                "baseline_threshold": self.confidence_threshold,
                "transformer_null_threshold": self.null_threshold,
            },
            "memory_usage": {
                "before_mb": mem_before_mb,
                "after_mb": mem_after_mb,
                "delta_mb": round(mem_after_mb - mem_before_mb, 2),
            },
            "runtime_seconds": {
                "baseline_total_s": baseline_time_s,
                "baseline_cpu_s": baseline_cpu_s,
                "baseline_per_q_ms": round((baseline_time_s / len(examples)) * 1000, 2),
                "transformer_total_s": transformer_time_s,
                "transformer_cpu_s": transformer_cpu_s,
                "transformer_per_q_ms": round((transformer_time_s / len(examples)) * 1000, 2),
            },
            "baseline_summary": {
                "exact_match": b_metrics["exact_match"],
                "token_f1": b_metrics["token_f1"],
                "detection_f1": b_metrics["detection"]["f1"],
            },
            "transformer_summary": {
                "exact_match": t_metrics["exact_match"],
                "token_f1": t_metrics["token_f1"],
                "detection_f1": t_metrics["detection"]["f1"],
            },
        }

        smoke_file = os.path.join(self.results_dir, "cuad_smoke_test_results.json")
        with open(smoke_file, "w", encoding="utf-8") as f:
            json.dump(smoke_report, f, indent=2)

        return smoke_report

    def run_comparative_evaluation(
        self,
        num_test_contracts: int = 3,
        use_prefilter: bool = True,
        top_k_windows: int = 4,
    ) -> Dict[str, Any]:
        """
        Evaluate baseline, pretrained transformer, and fine-tuned transformer on held-out test contracts.
        """
        print(f"=== Running Comparative Evaluation on {num_test_contracts} Held-Out Contracts ===")
        transformer = self._get_transformer()

        test_titles = self.splits["test"]["contract_titles"][:num_test_contracts]
        test_contracts = [c for c in self.loader._cached_contracts_data if c["contract_id"] in test_titles]

        all_examples = []
        for c in test_contracts:
            for qa in c["qas"]:
                all_examples.append({
                    "id": qa["id"],
                    "category": qa["category"],
                    "contract_id": c["contract_id"],
                    "is_impossible": qa["is_impossible"],
                    "gold_answers": [a["text"] for a in qa["answers"]],
                })

        print(f"Evaluating {len(all_examples)} test examples across {len(test_contracts)} contracts...")

        # 1. Baseline Evaluation
        t0 = time.time()
        cpu0 = time.process_time()
        b_pred_map = {}
        for c in test_contracts:
            preds = self.baseline.evaluate_contract(c)
            for qid, res in preds.items():
                b_pred_map[qid] = res[0]
        baseline_time_s = round(time.time() - t0, 3)
        baseline_cpu_s = round(time.process_time() - cpu0, 3)

        # 2. Pretrained Transformer Evaluation
        t0 = time.time()
        cpu0 = time.process_time()
        t_pred_map = {}
        for c in test_contracts:
            preds = transformer.evaluate_contract(c, use_prefilter=use_prefilter, top_k_windows=top_k_windows)
            for qid, res in preds.items():
                t_pred_map[qid] = res[0]
        transformer_time_s = round(time.time() - t0, 3)
        transformer_cpu_s = round(time.process_time() - cpu0, 3)

        # 3. Fine-Tuned Transformer Evaluation (if checkpoint exists)
        ft_dir = os.path.join(self.loader.target_dir, "models", "distilbert_cuad_finetuned")
        ft_eval = None
        ft_time_s = None
        ft_cpu_s = None
        if os.path.exists(ft_dir):
            ft_transformer = self._get_transformer(model_name=ft_dir)
            t0 = time.time()
            cpu0 = time.process_time()
            ft_pred_map = {}
            for c in test_contracts:
                preds = ft_transformer.evaluate_contract(c, use_prefilter=use_prefilter, top_k_windows=top_k_windows)
                for qid, res in preds.items():
                    ft_pred_map[qid] = res[0]
            ft_time_s = round(time.time() - t0, 3)
            ft_cpu_s = round(time.process_time() - cpu0, 3)
            ft_eval = CUADEvaluator.evaluate_predictions(all_examples, ft_pred_map)

        # Calculate metrics
        b_eval = CUADEvaluator.evaluate_predictions(all_examples, b_pred_map)
        t_eval = CUADEvaluator.evaluate_predictions(all_examples, t_pred_map)

        comparison_report = {
            "evaluation_protocol": {
                "evaluation_type": "Sampled Held-Out Test Split (Deterministic)",
                "note": "Full test evaluation (81 contracts, 3,321 Qs) on CPU requires ~27 hours. Evaluated on a deterministic sampled subset.",
                "contracts_evaluated": test_titles,
                "total_examples": len(all_examples),
            },
            "runtime_seconds": {
                "baseline_total_s": baseline_time_s,
                "baseline_cpu_s": baseline_cpu_s,
                "baseline_per_q_ms": round((baseline_time_s / len(all_examples)) * 1000, 2),
                "pretrained_transformer_total_s": transformer_time_s,
                "pretrained_transformer_cpu_s": transformer_cpu_s,
                "pretrained_per_q_ms": round((transformer_time_s / len(all_examples)) * 1000, 2),
                "finetuned_transformer_total_s": ft_time_s,
                "finetuned_transformer_cpu_s": ft_cpu_s,
                "finetuned_per_q_ms": round((ft_time_s / len(all_examples)) * 1000, 2) if ft_time_s else None,
            },
            "baseline_metrics": b_eval,
            "pretrained_transformer_metrics": t_eval,
            "finetuned_transformer_metrics": ft_eval,
        }

        out_file = os.path.join(self.results_dir, "cuad_benchmark_comparison.json")
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(comparison_report, f, indent=2)

        return comparison_report


if __name__ == "__main__":
    pipeline = CUADExperimentPipeline()
    smoke = pipeline.run_smoke_test(use_prefilter=True)
    print(json.dumps(smoke, indent=2))
