"""
CUAD Sliding-Window Transformer QA Extractor
============================================
Extractive question-answering on legal contracts using a pre-trained
transformer (DistilBERT-SQuAD, Apache-2.0 License).

Mechanisms:
1. Sliding window chunking (max_length=512, stride=128) with offset mapping.
2. Character-level offset preservation from token spans back to the contract text.
3. Overlapping window aggregation via maximum span confidence over null score.
4. Robust unanswerable / absent clause classification.
"""

import os
import torch
from typing import List, Dict, Any, Tuple, Optional
from transformers import AutoTokenizer, AutoModelForQuestionAnswering

MODEL_NAME = "distilbert/distilbert-base-uncased-distilled-squad"
MODEL_REVISION = "dfb8fa0e03905f0b6ea92133e56b6fef138015f2"
MODEL_LICENSE = "Apache-2.0"


try:
    from .candidate_filter import CandidateWindowPrefilter
except ImportError:
    from app.experiments.cuad.candidate_filter import CandidateWindowPrefilter


class CUADTransformerQA:
    """
    Sliding-window transformer extractive QA engine for long legal contracts.
    """

    def __init__(
        self,
        model_name: str = MODEL_NAME,
        device: Optional[str] = None,
        max_seq_length: int = 512,
        doc_stride: int = 128,
        max_answer_length: int = 60,
        null_threshold: float = 0.0,
    ):
        self.model_name = model_name
        self.max_seq_length = max_seq_length
        self.doc_stride = doc_stride
        self.max_answer_length = max_answer_length
        self.null_threshold = null_threshold

        # Device selection: use CPU or CUDA if explicitly requested/available
        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)

        print(f"Loading transformer QA model: {model_name} on {self.device}...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForQuestionAnswering.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.eval()

    def get_model_info(self) -> Dict[str, Any]:
        """Return model metadata, license, and parameter count."""
        param_count = sum(p.numel() for p in self.model.parameters())
        return {
            "model_name": self.model_name,
            "revision": MODEL_REVISION,
            "license": MODEL_LICENSE,
            "device": str(self.device),
            "parameter_count": param_count,
            "max_seq_length": self.max_seq_length,
            "doc_stride": self.doc_stride,
            "max_answer_length": self.max_answer_length,
            "null_threshold": self.null_threshold,
        }

    def predict_clause(
        self,
        context: str,
        question: str,
        category: Optional[str] = None,
        use_prefilter: bool = False,
        top_k_windows: int = 4,
    ) -> Tuple[str, int, int, float]:
        """
        Extract the best answer span from a long contract using sliding windows.

        Args:
            context: Full contract text.
            question: Category extraction question prompt.
            category: Optional clause category name for prefilter scoring.
            use_prefilter: If True, uses CandidateWindowPrefilter to select top-K windows.
            top_k_windows: Number of candidate windows to evaluate if filtered.

        Returns:
            Tuple of (predicted_text, start_char, end_char, score).
            If unanswerable or score < null_threshold, returns ("", -1, -1, 0.0).
        """
        if not context or not context.strip():
            return "", -1, -1, 0.0

        # Encode context with sliding window
        inputs = self.tokenizer(
            question,
            context,
            max_length=self.max_seq_length,
            truncation="only_second",
            stride=self.doc_stride,
            return_overflowing_tokens=True,
            return_offsets_mapping=True,
            padding="max_length",
            return_tensors="pt",
        )

        offset_mapping = inputs.pop("offset_mapping")
        num_windows = inputs["input_ids"].shape[0]

        # Determine which windows to evaluate
        if use_prefilter and num_windows > top_k_windows:
            window_texts = []
            for w_idx in range(num_windows):
                seq_ids = inputs.sequence_ids(w_idx)
                ctx_indices = [i for i, sid in enumerate(seq_ids) if sid == 1]
                if ctx_indices:
                    c_start = offset_mapping[w_idx][ctx_indices[0]][0].item()
                    c_end = offset_mapping[w_idx][ctx_indices[-1]][1].item()
                    window_texts.append(context[c_start:c_end])
                else:
                    window_texts.append("")

            prefilter = CandidateWindowPrefilter(top_k_windows=top_k_windows)
            active_windows = prefilter.filter_windows(
                question=question,
                category=category or "",
                window_texts=window_texts,
            )
        else:
            active_windows = list(range(num_windows))

        # Run model inference on active windows in mini-batches
        batch_size = 8
        all_start_logits = []
        all_end_logits = []

        sub_input_ids = inputs["input_ids"][active_windows]
        sub_attention_mask = inputs["attention_mask"][active_windows]
        num_active = len(active_windows)

        with torch.no_grad():
            for b_start in range(0, num_active, batch_size):
                b_end = min(b_start + batch_size, num_active)
                b_input_ids = sub_input_ids[b_start:b_end].to(self.device)
                b_attention_mask = sub_attention_mask[b_start:b_end].to(self.device)
                outputs = self.model(input_ids=b_input_ids, attention_mask=b_attention_mask)
                all_start_logits.append(outputs.start_logits.cpu())
                all_end_logits.append(outputs.end_logits.cpu())

        start_logits = torch.cat(all_start_logits, dim=0)
        end_logits = torch.cat(all_end_logits, dim=0)

        best_overall_score = -float("inf")
        best_span_text = ""
        best_start_char = -1
        best_end_char = -1

        for local_idx, orig_w_idx in enumerate(active_windows):
            w_offsets = offset_mapping[orig_w_idx]
            seq_ids = inputs.sequence_ids(orig_w_idx)

            # Null score = start + end logits at [CLS] (index 0)
            null_score = (start_logits[local_idx, 0] + end_logits[local_idx, 0]).item()

            context_indices = [
                i for i, sid in enumerate(seq_ids) if sid == 1
            ]
            if not context_indices:
                continue

            ctx_start = context_indices[0]
            ctx_end = context_indices[-1]

            w_start_logits = start_logits[local_idx, ctx_start : ctx_end + 1]
            w_end_logits = end_logits[local_idx, ctx_start : ctx_end + 1]

            # Top candidates within window
            top_start_indices = torch.topk(w_start_logits, min(10, len(w_start_logits))).indices + ctx_start
            top_end_indices = torch.topk(w_end_logits, min(10, len(w_end_logits))).indices + ctx_start

            for s_idx in top_start_indices.tolist():
                for e_idx in top_end_indices.tolist():
                    if s_idx > e_idx:
                        continue
                    if (e_idx - s_idx + 1) > self.max_answer_length:
                        continue

                    start_char = w_offsets[s_idx][0].item()
                    end_char = w_offsets[e_idx][1].item()

                    if start_char >= end_char or start_char < 0 or end_char > len(context):
                        continue

                    span_score = (start_logits[local_idx, s_idx] + end_logits[local_idx, e_idx]).item()
                    score_over_null = span_score - null_score

                    if score_over_null > best_overall_score:
                        best_overall_score = score_over_null
                        best_start_char = start_char
                        best_end_char = end_char
                        best_span_text = context[start_char:end_char].strip()

        # If score over null exceeds threshold, return the span
        if best_overall_score > self.null_threshold and best_span_text:
            return best_span_text, best_start_char, best_end_char, round(best_overall_score, 3)

        return "", -1, -1, 0.0

    def evaluate_contract(
        self,
        contract: Dict[str, Any],
        use_prefilter: bool = False,
        top_k_windows: int = 4,
    ) -> Dict[str, Tuple[str, int, int, float]]:
        """
        Run extractive QA on all QAs in a contract.
        Returns dict mapping question ID -> (pred_text, start_char, end_char, score).
        """
        context = contract.get("context", "")
        if not context and "paragraphs" in contract:
            context = contract["paragraphs"][0].get("context", "")

        results = {}
        for qa in contract.get("qas", []):
            qid = qa["id"]
            q_text = qa.get("question", "")
            cat = qa.get("category", "")
            results[qid] = self.predict_clause(
                context=context,
                question=q_text,
                category=cat,
                use_prefilter=use_prefilter,
                top_k_windows=top_k_windows,
            )
        return results
