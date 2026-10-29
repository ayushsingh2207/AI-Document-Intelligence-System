"""
CUAD Experiment Package
=======================
Dedicated experimental pipeline for Contract Understanding Atticus Dataset (CUAD v1).
Kept strictly modular and isolated from the general document intelligence production pipeline.
"""

from .dataset_loader import CUADDatasetLoader, compute_sha256
from .baseline_extractor import CUADBaselineExtractor
from .transformer_qa import CUADTransformerQA
from .evaluator import CUADEvaluator, compute_exact_match, compute_token_f1
from .pipeline import CUADExperimentPipeline

__all__ = [
    "CUADDatasetLoader",
    "compute_sha256",
    "CUADBaselineExtractor",
    "CUADTransformerQA",
    "CUADEvaluator",
    "compute_exact_match",
    "compute_token_f1",
    "CUADExperimentPipeline",
]
