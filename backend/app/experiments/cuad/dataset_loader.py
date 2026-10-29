"""
CUAD Dataset Loader & Provenance Pipeline
=========================================
Handles download, integrity verification (SHA-256), schema validation,
answer-span verification against contract text, and leak-free contract-level
splitting for the Contract Understanding Atticus Dataset (CUAD v1).

License: CC BY 4.0 (The Atticus Project)
Official Website: https://www.atticusprojectai.org/cuad/
Hugging Face: https://huggingface.co/datasets/theatticusproject/cuad
"""

import os
import json
import csv
import hashlib
import datetime
import random
from typing import Dict, List, Any, Tuple, Optional
from huggingface_hub import hf_hub_download

CUAD_REPO_ID = "theatticusproject/cuad"
CUAD_JSON_FILENAME = "CUAD_v1/CUAD_v1.json"
CUAD_CSV_FILENAME = "CUAD_v1/master_clauses.csv"
CUAD_LICENSE = "Creative Commons Attribution 4.0 International (CC BY 4.0)"
CUAD_VERSION = "CUAD v1.0 (NeurIPS 2021)"
CUAD_CITATION = (
    "Hendrycks, D., Burns, C., Chen, A., Ball, S. (2021). "
    "CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review. "
    "Thirty-fifth Conference on Neural Information Processing Systems (NeurIPS 2021) "
    "Track on Datasets and Benchmarks."
)


def compute_sha256(filepath: str) -> str:
    """Compute the SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(65536), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


class CUADDatasetLoader:
    """
    Downloads, verifies, validates, and partitions the CUAD v1 dataset.
    """

    def __init__(self, target_dir: Optional[str] = None):
        self.target_dir = target_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
            "data",
            "cuad",
        )
        os.makedirs(self.target_dir, exist_ok=True)
        self.raw_json_path = os.path.join(self.target_dir, "CUAD_v1.json")
        self.raw_csv_path = os.path.join(self.target_dir, "master_clauses.csv")
        self.splits_path = os.path.join(self.target_dir, "cuad_splits.json")
        self.provenance_path = os.path.join(self.target_dir, "cuad_provenance.json")

    def download_and_verify(self) -> Dict[str, Any]:
        """
        Download CUAD_v1.json and master_clauses.csv from the official HF mirror.
        Verify file presence and compute SHA-256 checksums.
        """
        print(f"Downloading/Locating CUAD files from {CUAD_REPO_ID}...")
        download_timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Download json
        cached_json = hf_hub_download(
            repo_id=CUAD_REPO_ID,
            filename=CUAD_JSON_FILENAME,
            repo_type="dataset",
        )
        # Download csv
        cached_csv = hf_hub_download(
            repo_id=CUAD_REPO_ID,
            filename=CUAD_CSV_FILENAME,
            repo_type="dataset",
        )

        # Copy to local target dir if not already there
        if not os.path.exists(self.raw_json_path) or os.path.getsize(self.raw_json_path) != os.path.getsize(cached_json):
            import shutil
            shutil.copy2(cached_json, self.raw_json_path)

        if not os.path.exists(self.raw_csv_path) or os.path.getsize(self.raw_csv_path) != os.path.getsize(cached_csv):
            import shutil
            shutil.copy2(cached_csv, self.raw_csv_path)

        json_size = os.path.getsize(self.raw_json_path)
        json_sha256 = compute_sha256(self.raw_json_path)

        csv_size = os.path.getsize(self.raw_csv_path)
        csv_sha256 = compute_sha256(self.raw_csv_path)

        provenance = {
            "dataset_name": "Contract Understanding Atticus Dataset (CUAD v1)",
            "version": CUAD_VERSION,
            "license": CUAD_LICENSE,
            "citation": CUAD_CITATION,
            "source_repo": f"https://huggingface.co/datasets/{CUAD_REPO_ID}",
            "official_url": "https://www.atticusprojectai.org/cuad/",
            "download_timestamp_utc": download_timestamp,
            "files": {
                "CUAD_v1.json": {
                    "path": self.raw_json_path,
                    "size_bytes": json_size,
                    "size_mb": round(json_size / (1024 * 1024), 2),
                    "sha256": json_sha256,
                },
                "master_clauses.csv": {
                    "path": self.raw_csv_path,
                    "size_bytes": csv_size,
                    "size_mb": round(csv_size / (1024 * 1024), 2),
                    "sha256": csv_sha256,
                },
            },
        }

        with open(self.provenance_path, "w", encoding="utf-8") as f:
            json.dump(provenance, f, indent=2)

        return provenance

    def parse_and_validate(self) -> Dict[str, Any]:
        """
        Parse CUAD_v1.json, validate answer character spans against contract text,
        calculate statistics, and check for discrepancies.
        """
        if not os.path.exists(self.raw_json_path):
            self.download_and_verify()

        with open(self.raw_json_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        data = raw_data.get("data", [])
        version = raw_data.get("version", "unknown")

        total_contracts = len(data)
        contract_titles = []
        contract_title_counts = {}
        total_questions = 0
        answerable_questions = 0
        unanswerable_questions = 0
        total_answers = 0
        valid_answer_spans = 0
        span_discrepancies: List[Dict[str, Any]] = []
        categories_found = set()
        category_answerable_counts: Dict[str, int] = {}
        category_total_counts: Dict[str, int] = {}

        contracts_data = []

        for article_idx, article in enumerate(data):
            title = article.get("title", f"contract_{article_idx}")
            contract_titles.append(title)
            contract_title_counts[title] = contract_title_counts.get(title, 0) + 1

            paragraphs = article.get("paragraphs", [])
            for para_idx, para in enumerate(paragraphs):
                context = para.get("context", "")
                qas = para.get("qas", [])

                contract_info = {
                    "contract_id": title,
                    "article_index": article_idx,
                    "context": context,
                    "context_length": len(context),
                    "context_char_preview": context[:200],
                    "qas": [],
                }

                for qa in qas:
                    total_questions += 1
                    qid = qa.get("id", "")
                    question = qa.get("question", "")
                    is_impossible = qa.get("is_impossible", False)
                    answers = qa.get("answers", [])

                    # Extract clause category from question:
                    # e.g., 'Highlight the parts (if any) of this contract related to "Document Name" that should be reviewed...'
                    cat_name = "Unknown"
                    if '"' in question:
                        parts = question.split('"')
                        if len(parts) >= 2:
                            cat_name = parts[1].strip()

                    categories_found.add(cat_name)
                    category_total_counts[cat_name] = category_total_counts.get(cat_name, 0) + 1

                    if is_impossible or len(answers) == 0:
                        unanswerable_questions += 1
                    else:
                        answerable_questions += 1
                        category_answerable_counts[cat_name] = (
                            category_answerable_counts.get(cat_name, 0) + 1
                        )

                    # Validate each answer span
                    validated_answers = []
                    for ans in answers:
                        total_answers += 1
                        ans_text = ans.get("text", "")
                        ans_start = ans.get("answer_start", -1)

                        if ans_start >= 0 and ans_start + len(ans_text) <= len(context):
                            actual_substring = context[ans_start : ans_start + len(ans_text)]
                            if actual_substring == ans_text:
                                valid_answer_spans += 1
                                is_valid = True
                            else:
                                is_valid = False
                                span_discrepancies.append({
                                    "contract_title": title,
                                    "question_id": qid,
                                    "category": cat_name,
                                    "expected_text": ans_text,
                                    "actual_substring": actual_substring,
                                    "answer_start": ans_start,
                                    "length": len(ans_text),
                                })
                        else:
                            is_valid = False
                            span_discrepancies.append({
                                "contract_title": title,
                                "question_id": qid,
                                "category": cat_name,
                                "error": "IndexOutOfBounds",
                                "answer_start": ans_start,
                                "context_length": len(context),
                            })

                        validated_answers.append({
                            "text": ans_text,
                            "answer_start": ans_start,
                            "span_valid": is_valid,
                        })

                    contract_info["qas"].append({
                        "id": qid,
                        "category": cat_name,
                        "question": question,
                        "is_impossible": is_impossible,
                        "answers": validated_answers,
                    })

                contracts_data.append(contract_info)

        unique_titles = list(set(contract_titles))
        duplicate_titles = [t for t, count in contract_title_counts.items() if count > 1]

        validation_report = {
            "json_version": version,
            "total_contracts": total_contracts,
            "unique_contract_titles": len(unique_titles),
            "duplicate_titles_count": len(duplicate_titles),
            "duplicate_titles": duplicate_titles,
            "total_questions": total_questions,
            "answerable_questions": answerable_questions,
            "unanswerable_questions": unanswerable_questions,
            "total_answers": total_answers,
            "valid_answer_spans": valid_answer_spans,
            "span_discrepancies_count": len(span_discrepancies),
            "span_discrepancies_sample": span_discrepancies[:5],
            "total_categories": len(categories_found),
            "categories": sorted(list(categories_found)),
            "category_answerable_counts": dict(
                sorted(category_answerable_counts.items(), key=lambda x: x[1], reverse=True)
            ),
        }

        self._cached_contracts_data = contracts_data
        self._cached_validation_report = validation_report
        return validation_report

    def create_contract_level_splits(
        self,
        seed: int = 42,
        train_ratio: float = 0.78,
        val_ratio: float = 0.06,
        test_ratio: float = 0.16,
    ) -> Dict[str, Any]:
        """
        Partition contracts deterministically into train, validation, and test splits
        by contract title. Guarantees 0 data leakage between splits.
        """
        if not hasattr(self, "_cached_contracts_data"):
            self.parse_and_validate()

        contracts = self._cached_contracts_data
        unique_titles = sorted(list(set(c["contract_id"] for c in contracts)))
        n_contracts = len(unique_titles)

        # Deterministic shuffle
        rng = random.Random(seed)
        shuffled_titles = list(unique_titles)
        rng.shuffle(shuffled_titles)

        n_train = int(round(n_contracts * train_ratio))
        n_val = int(round(n_contracts * val_ratio))
        # Remainder goes to test
        n_test = n_contracts - n_train - n_val

        train_titles = set(shuffled_titles[:n_train])
        val_titles = set(shuffled_titles[n_train : n_train + n_val])
        test_titles = set(shuffled_titles[n_train + n_val :])

        # Strict leakage checks
        assert len(train_titles & val_titles) == 0, "Train-Val title leakage detected!"
        assert len(train_titles & test_titles) == 0, "Train-Test title leakage detected!"
        assert len(val_titles & test_titles) == 0, "Val-Test title leakage detected!"
        assert len(train_titles | val_titles | test_titles) == n_contracts, "Missing contracts in split!"

        # Count questions and categories per split
        def compute_split_stats(split_titles: set) -> Dict[str, Any]:
            split_contracts = [c for c in contracts if c["contract_id"] in split_titles]
            n_questions = sum(len(c["qas"]) for c in split_contracts)
            n_ans = sum(1 for c in split_contracts for q in c["qas"] if not q["is_impossible"] and len(q["answers"]) > 0)
            n_unans = n_questions - n_ans
            cat_counts = {}
            for c in split_contracts:
                for q in c["qas"]:
                    if not q["is_impossible"] and len(q["answers"]) > 0:
                        cat = q["category"]
                        cat_counts[cat] = cat_counts.get(cat, 0) + 1
            return {
                "num_contracts": len(split_titles),
                "num_questions": n_questions,
                "answerable_questions": n_ans,
                "unanswerable_questions": n_unans,
                "category_answerable_counts": cat_counts,
                "contract_titles": sorted(list(split_titles)),
            }

        train_stats = compute_split_stats(train_titles)
        val_stats = compute_split_stats(val_titles)
        test_stats = compute_split_stats(test_titles)

        # Check for categories absent from test split
        all_categories = set(self._cached_validation_report["categories"])
        test_active_categories = set(test_stats["category_answerable_counts"].keys())
        absent_from_test = sorted(list(all_categories - test_active_categories))

        split_payload = {
            "seed": seed,
            "train_ratio": train_ratio,
            "val_ratio": val_ratio,
            "test_ratio": test_ratio,
            "total_contracts": n_contracts,
            "train": train_stats,
            "val": val_stats,
            "test": test_stats,
            "categories_absent_from_test": absent_from_test,
        }

        with open(self.splits_path, "w", encoding="utf-8") as f:
            json.dump(split_payload, f, indent=2)

        return split_payload


if __name__ == "__main__":
    loader = CUADDatasetLoader()
    print("--- 1. Download & Provenance ---")
    prov = loader.download_and_verify()
    print(json.dumps(prov, indent=2))

    print("\n--- 2. Parse & Validate ---")
    val_rep = loader.parse_and_validate()
    print(json.dumps({k: v for k, v in val_rep.items() if k != "category_answerable_counts"}, indent=2))

    print("\n--- 3. Create Contract-Level Splits ---")
    splits = loader.create_contract_level_splits(seed=42)
    print(f"Train contracts: {splits['train']['num_contracts']}, Qs: {splits['train']['num_questions']}, Answerable: {splits['train']['answerable_questions']}")
    print(f"Val contracts:   {splits['val']['num_contracts']}, Qs: {splits['val']['num_questions']}, Answerable: {splits['val']['answerable_questions']}")
    print(f"Test contracts:  {splits['test']['num_contracts']}, Qs: {splits['test']['num_questions']}, Answerable: {splits['test']['answerable_questions']}")
    print(f"Categories absent from test: {splits['categories_absent_from_test']}")
