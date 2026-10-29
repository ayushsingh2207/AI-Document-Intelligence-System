"""
Phase 4 Tests: CUAD Dataset Integrity, Provenance & Leakage Prevention
=====================================================================
Tests that verify:
1. Provenance and SHA-256 checksum tracking
2. SQuAD 2.0 schema parsing and contract counts
3. Exact answer-span validity against source contract text
4. Strict contract-level partitioning with 0 cross-split leakage
5. Proper representation of all 41 clause categories
6. Unanswerable question (no-answer) classification
"""

import os
import json
import pytest
from app.experiments.cuad.dataset_loader import (
    CUADDatasetLoader,
    compute_sha256,
    CUAD_VERSION,
    CUAD_LICENSE,
)


@pytest.fixture(scope="module")
def cuad_loader():
    """Initializes and parses the CUAD dataset once for the test module."""
    loader = CUADDatasetLoader()
    if not os.path.exists(loader.raw_json_path):
        loader.download_and_verify()
    loader.parse_and_validate()
    return loader


class TestCUADDatasetIntegrity:
    """Verifies file integrity, schema structure, and span validity."""

    def test_provenance_file_created(self, cuad_loader):
        assert os.path.exists(cuad_loader.provenance_path), "Provenance JSON must exist"
        with open(cuad_loader.provenance_path, "r", encoding="utf-8") as f:
            prov = json.load(f)

        assert prov["version"] == CUAD_VERSION
        assert prov["license"] == CUAD_LICENSE
        assert "CUAD_v1.json" in prov["files"]
        assert "master_clauses.csv" in prov["files"]
        assert prov["files"]["CUAD_v1.json"]["size_mb"] > 35.0
        assert len(prov["files"]["CUAD_v1.json"]["sha256"]) == 64

    def test_sha256_checksum_reproducibility(self, cuad_loader):
        computed_hash = compute_sha256(cuad_loader.raw_json_path)
        with open(cuad_loader.provenance_path, "r", encoding="utf-8") as f:
            prov = json.load(f)
        assert computed_hash == prov["files"]["CUAD_v1.json"]["sha256"]

    def test_total_contract_and_question_counts(self, cuad_loader):
        rep = cuad_loader._cached_validation_report
        # CUAD v1 has exactly 510 contracts and 41 categories
        assert rep["total_contracts"] == 510
        assert rep["unique_contract_titles"] == 510
        assert rep["duplicate_titles_count"] == 0
        assert rep["total_questions"] == 510 * 41
        assert rep["total_questions"] == 20910

    def test_answerable_and_unanswerable_proportions(self, cuad_loader):
        rep = cuad_loader._cached_validation_report
        # In real-world legal contracts, most clauses are absent in any given contract
        assert rep["answerable_questions"] == 6702
        assert rep["unanswerable_questions"] == 14208
        assert rep["answerable_questions"] + rep["unanswerable_questions"] == rep["total_questions"]

    def test_answer_span_validity(self, cuad_loader):
        rep = cuad_loader._cached_validation_report
        # All answer spans must match context exactly
        assert rep["span_discrepancies_count"] == 0
        assert rep["valid_answer_spans"] == rep["total_answers"]
        assert rep["valid_answer_spans"] == 13823

    def test_all_41_clause_categories_present(self, cuad_loader):
        rep = cuad_loader._cached_validation_report
        assert rep["total_categories"] == 41
        categories = rep["categories"]
        expected_sample_cats = [
            "Document Name",
            "Parties",
            "Agreement Date",
            "Effective Date",
            "Governing Law",
            "Termination For Convenience",
            "Non-Compete",
            "Cap On Liability",
            "Ip Ownership Assignment",
        ]
        for cat in expected_sample_cats:
            assert cat in categories


class TestCUADContractLevelSplitting:
    """Verifies deterministic contract-level splitting and zero data leakage."""

    def test_deterministic_split_reproducibility(self, cuad_loader):
        split1 = cuad_loader.create_contract_level_splits(seed=42)
        split2 = cuad_loader.create_contract_level_splits(seed=42)
        assert split1["train"]["contract_titles"] == split2["train"]["contract_titles"]
        assert split1["val"]["contract_titles"] == split2["val"]["contract_titles"]
        assert split1["test"]["contract_titles"] == split2["test"]["contract_titles"]

    def test_zero_leakage_between_splits(self, cuad_loader):
        splits = cuad_loader.create_contract_level_splits(seed=42)
        train_set = set(splits["train"]["contract_titles"])
        val_set = set(splits["val"]["contract_titles"])
        test_set = set(splits["test"]["contract_titles"])

        # No overlap between any pair of splits
        assert len(train_set & val_set) == 0, "Leakage between train and val"
        assert len(train_set & test_set) == 0, "Leakage between train and test"
        assert len(val_set & test_set) == 0, "Leakage between val and test"

        # Complete coverage
        assert len(train_set | val_set | test_set) == 510

    def test_split_sizes(self, cuad_loader):
        splits = cuad_loader.create_contract_level_splits(seed=42)
        assert splits["train"]["num_contracts"] == 398
        assert splits["val"]["num_contracts"] == 31
        assert splits["test"]["num_contracts"] == 81

    def test_all_categories_represented_in_test(self, cuad_loader):
        splits = cuad_loader.create_contract_level_splits(seed=42)
        assert splits["categories_absent_from_test"] == []
        assert len(splits["test"]["category_answerable_counts"]) == 41
