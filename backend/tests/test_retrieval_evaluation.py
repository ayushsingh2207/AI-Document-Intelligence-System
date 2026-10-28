"""
Quantitative Retrieval Evaluation Benchmark for Phase 2 AI Document Intelligence.
Measures Recall@5 and Mean Reciprocal Rank (MRR) using a labeled evaluation corpus.
"""
import pytest
from typing import List, Dict, Any
from app.schemas.document import DocumentPage
from app.services.vector_store import VectorStore

EVAL_DOCUMENTS = [
    {
        "doc_id": "eval_doc_01_nlp",
        "filename": "eval_transformer_nlp.txt",
        "pages": [
            DocumentPage(
                page_number=1,
                text="The transformer architecture relies on multi-head self-attention mechanisms to compute contextual representations of tokens without recurrence. Scaled dot-product attention computes compatibility between queries and keys to weight value representations.",
                char_count=255,
                word_count=30,
                is_approximate=False,
                boundary_type="physical"
            )
        ]
    },
    {
        "doc_id": "eval_doc_02_legal",
        "filename": "eval_commercial_lease.txt",
        "pages": [
            DocumentPage(
                page_number=1,
                text="The tenant shall indemnify, defend, and hold harmless the landlord from all liabilities and claims. The aggregate liability of either party under this lease shall not exceed the total base rent paid during the preceding twelve months.",
                char_count=235,
                word_count=35,
                is_approximate=False,
                boundary_type="physical"
            )
        ]
    },
    {
        "doc_id": "eval_doc_03_finance",
        "filename": "eval_financial_q2.txt",
        "pages": [
            DocumentPage(
                page_number=1,
                text="In the second fiscal quarter, consolidated total revenue grew twenty-four percent year-over-year to four hundred million dollars. Adjusted EBITDA margin expanded by two hundred basis points driven by enterprise software subscription expansion.",
                char_count=248,
                word_count=31,
                is_approximate=False,
                boundary_type="physical"
            )
        ]
    },
    {
        "doc_id": "eval_doc_04_security",
        "filename": "eval_zero_trust_security.txt",
        "pages": [
            DocumentPage(
                page_number=1,
                text="Zero-trust architecture enforces continuous verification of identity and device posture. Network microsegmentation restricts lateral movement by establishing granular access boundaries around sensitive production databases and workload clusters.",
                char_count=254,
                word_count=28,
                is_approximate=False,
                boundary_type="physical"
            )
        ]
    },
    {
        "doc_id": "eval_doc_05_healthcare",
        "filename": "eval_healthcare_hipaa.txt",
        "pages": [
            DocumentPage(
                page_number=1,
                text="Protected health information (PHI) must be encrypted both in transit and at rest. Covered entities are strictly prohibited from disclosing confidential patient clinical records without an explicit signed HIPAA authorization from the individual.",
                char_count=248,
                word_count=32,
                is_approximate=False,
                boundary_type="physical"
            )
        ]
    },
    {
        "doc_id": "eval_doc_06_logistics",
        "filename": "eval_supply_chain.txt",
        "pages": [
            DocumentPage(
                page_number=1,
                text="Global container shipping bottlenecks require multi-modal logistics routing. Automated inventory replenishment and real-time freight tracking reduce warehouse fulfillment transit times and prevent inventory stockouts across regional fulfillment centers.",
                char_count=264,
                word_count=30,
                is_approximate=False,
                boundary_type="physical"
            )
        ]
    },
    {
        "doc_id": "eval_doc_07_employment",
        "filename": "eval_employment_agreement.txt",
        "pages": [
            DocumentPage(
                page_number=1,
                text="For a duration of twelve months following the separation date, the employee agrees not to engage in competing business activities or solicit active clients within a fifty-mile geographical radius under this restrictive covenant clause.",
                char_count=241,
                word_count=34,
                is_approximate=False,
                boundary_type="physical"
            )
        ]
    },
    {
        "doc_id": "eval_doc_08_distributed",
        "filename": "eval_distributed_consensus.txt",
        "pages": [
            DocumentPage(
                page_number=1,
                text="The Raft consensus algorithm decomposes state machine replication into leader election, log replication, and safety guarantees. Quorum majorities ensure that committed log entries survive subsequent leader failures across distributed nodes.",
                char_count=248,
                word_count=31,
                is_approximate=False,
                boundary_type="physical"
            )
        ]
    }
]

EVAL_QUERIES = [
    {
        "query": "How do attention mechanisms weight token representations?",
        "expected_doc_id": "eval_doc_01_nlp",
        "domain": "Natural Language Processing"
    },
    {
        "query": "What is the maximum tenant liability cap and indemnification clause?",
        "expected_doc_id": "eval_doc_02_legal",
        "domain": "Commercial Contracts"
    },
    {
        "query": "What were the quarterly revenue growth and EBITDA figures?",
        "expected_doc_id": "eval_doc_03_finance",
        "domain": "Financial Performance"
    },
    {
        "query": "How does identity verification prevent lateral movement in zero trust?",
        "expected_doc_id": "eval_doc_04_security",
        "domain": "Cybersecurity"
    },
    {
        "query": "What are the restrictions on disclosing protected patient health records?",
        "expected_doc_id": "eval_doc_05_healthcare",
        "domain": "Healthcare Regulatory"
    },
    {
        "query": "How are freight shipping transit delays mitigated in warehouses?",
        "expected_doc_id": "eval_doc_06_logistics",
        "domain": "Supply Chain Logistics"
    },
    {
        "query": "What is the duration of the employee non-compete restrictive covenant?",
        "expected_doc_id": "eval_doc_07_employment",
        "domain": "Employment Law"
    },
    {
        "query": "How does leader election maintain quorum safety in state machines?",
        "expected_doc_id": "eval_doc_08_distributed",
        "domain": "Distributed Systems"
    }
]

def run_retrieval_benchmark(store: VectorStore) -> Dict[str, Any]:
    """Indexes the evaluation corpus and evaluates Recall@5 and MRR."""
    # Index all evaluation documents
    for doc in EVAL_DOCUMENTS:
        store.index_document(
            doc_id=doc["doc_id"],
            filename=doc["filename"],
            file_type="TXT",
            file_size_bytes=sum(p.char_count for p in doc["pages"]),
            pages=doc["pages"]
        )

    recalls_at_5: List[float] = []
    reciprocal_ranks: List[float] = []
    query_details: List[Dict[str, Any]] = []

    for item in EVAL_QUERIES:
        query = item["query"]
        expected_id = item["expected_doc_id"]
        response = store.search(query=query, top_k=5)

        retrieved_doc_ids = [r.doc_id for r in response.results]
        
        # Check Recall@5 (1.0 if target doc in top 5, else 0.0)
        found_in_top5 = expected_id in retrieved_doc_ids
        recalls_at_5.append(1.0 if found_in_top5 else 0.0)

        # Compute Reciprocal Rank (1/rank if found, else 0.0)
        if found_in_top5:
            rank = retrieved_doc_ids.index(expected_id) + 1
            rr = 1.0 / rank
        else:
            rank = None
            rr = 0.0
        reciprocal_ranks.append(rr)

        top_score = response.results[0].score if response.results else 0.0
        query_details.append({
            "query": query,
            "domain": item["domain"],
            "expected": expected_id,
            "rank": rank,
            "reciprocal_rank": rr,
            "top_score": top_score
        })

    mrr = sum(reciprocal_ranks) / len(reciprocal_ranks)
    mean_recall_at_5 = sum(recalls_at_5) / len(recalls_at_5)

    return {
        "num_queries": len(EVAL_QUERIES),
        "mean_recall_at_5": mean_recall_at_5,
        "mrr": mrr,
        "details": query_details
    }

def test_retrieval_evaluation_benchmark():
    """Pytest test asserting high retrieval quality on the labeled benchmark."""
    eval_store = VectorStore(data_dir=None)  # In-memory store
    eval_store.clear_all()

    metrics = run_retrieval_benchmark(eval_store)
    
    print("\n--- RETRIEVAL EVALUATION RESULTS ---")
    print(f"Total Evaluated Queries: {metrics['num_queries']}")
    print(f"Recall@5: {metrics['mean_recall_at_5'] * 100:.1f}%")
    print(f"Mean Reciprocal Rank (MRR): {metrics['mrr']:.4f}")
    for d in metrics["details"]:
        print(f"  [{d['domain']}] Rank #{d['rank']} (Score: {d['top_score']:.4f}) - '{d['query']}'")

    # Rigorous assertions for semantic search quality
    assert metrics["mean_recall_at_5"] >= 0.85, f"Recall@5 ({metrics['mean_recall_at_5']}) fell below 85%"
    assert metrics["mrr"] >= 0.75, f"MRR ({metrics['mrr']}) fell below 0.75"

if __name__ == "__main__":
    test_store = VectorStore(data_dir=None)
    res = run_retrieval_benchmark(test_store)
    print(f"Recall@5: {res['mean_recall_at_5'] * 100:.2f}% | MRR: {res['mrr']:.4f}")
