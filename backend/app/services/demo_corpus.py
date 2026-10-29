import logging
from typing import Dict, Any, List, Set
from app.schemas.document import DocumentPage

logger = logging.getLogger(__name__)

# Reviewed, non-sensitive educational sample documents for public demonstration
DEMO_DOC_TRANSFORMER_ID = "doc_demo_transformer"
DEMO_DOC_CONTRACT_ID = "doc_demo_contract"

APPROVED_DEMO_DOC_IDS: Set[str] = {DEMO_DOC_TRANSFORMER_ID, DEMO_DOC_CONTRACT_ID}

DEMO_DOCUMENTS: List[Dict[str, Any]] = [
    {
        "doc_id": DEMO_DOC_TRANSFORMER_ID,
        "filename": "transformer_attention_overview.txt",
        "file_type": "txt",
        "metadata": {
            "title": "Attention Is All You Need — Academic Overview",
            "author": "Vaswani et al. (2017) Educational Summary",
            "subject": "Deep Learning / Natural Language Processing",
            "is_sample": True
        },
        "pages": [
            DocumentPage(
                page_number=1,
                text=(
                    "Attention Is All You Need — Architecture Overview\n\n"
                    "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks "
                    "in an encoder-decoder configuration. The Transformer model architecture eschews recurrence and instead relies "
                    "entirely on an attention mechanism to draw global dependencies between input and output representations. "
                    "The Transformer allows for significantly more parallelization and can reach a new state of the art in translation quality "
                    "after being trained for as little as twelve hours on eight P100 GPUs.\n\n"
                    "Model Architecture: Most competitive neural sequence models have an encoder-decoder structure. "
                    "The encoder maps an input sequence of symbol representations (x_1, ..., x_n) to a sequence of continuous representations z = (z_1, ..., z_n). "
                    "Given z, the decoder then generates an output sequence (y_1, ..., y_m) of symbols one element at a time. "
                    "At each step the model is auto-regressive, consuming the previously generated symbols as additional input when generating the next."
                ),
                char_count=1080,
                word_count=154,
                is_approximate=False,
                boundary_type="physical"
            ),
            DocumentPage(
                page_number=2,
                text=(
                    "Scaled Dot-Product and Multi-Head Attention Mechanisms\n\n"
                    "An attention function can be described as mapping a query and a set of key-value pairs to an output, "
                    "where the query, keys, values, and output are all vectors. The output is computed as a weighted sum of the values, "
                    "where the weight assigned to each value is computed by a compatibility function of the query with the corresponding key.\n\n"
                    "Scaled Dot-Product Attention: We compute the dot products of the query with all keys, divide each by sqrt(d_k), "
                    "and apply a softmax function to obtain the weights on the values. In practice, we compute the attention function on a set of queries simultaneously, "
                    "packed together into a matrix Q. The keys and values are also packed into matrices K and V. "
                    "The formula is: Attention(Q, K, V) = softmax(Q * K^T / sqrt(d_k)) * V.\n\n"
                    "Multi-Head Attention: Instead of performing a single attention function with d_model-dimensional keys, values, and queries, "
                    "we found it beneficial to linearly project the queries, keys, and values h times with different, learned linear projections "
                    "to d_k, d_k, and d_v dimensions respectively."
                ),
                char_count=1214,
                word_count=176,
                is_approximate=False,
                boundary_type="physical"
            ),
            DocumentPage(
                page_number=3,
                text=(
                    "Positional Encodings and Empirical Results\n\n"
                    "Since our model contains no recurrence and no convolution, in order for the model to make use of the order of the sequence, "
                    "we must inject some information about the relative or absolute position of the tokens in the sequence. "
                    "To this end, we add positional encodings to the input embeddings at the bottoms of the encoder and decoder stacks. "
                    "The positional encodings have the same dimension d_model as the embeddings, so that the two can be summed.\n\n"
                    "Empirical Evaluation on Translation Tasks:\n"
                    "On the WMT 2014 English-to-German translation task, the big transformer model achieves a state-of-the-art BLEU score of 28.4, "
                    "outperforming the existing best models by more than 2.0 BLEU. On the WMT 2014 English-to-French translation task, "
                    "our big model achieves a BLEU score of 41.8, outperforming all of the previously published single models, at less than 1/4 the training cost."
                ),
                char_count=1012,
                word_count=146,
                is_approximate=False,
                boundary_type="physical"
            )
        ]
    },
    {
        "doc_id": DEMO_DOC_CONTRACT_ID,
        "filename": "sample_mutual_nda_delaware.txt",
        "file_type": "txt",
        "metadata": {
            "title": "Mutual Non-Disclosure Agreement (Standard Delaware Model)",
            "author": "Academic Educational Contract Model",
            "subject": "Commercial Contracting / Confidentiality",
            "is_sample": True
        },
        "pages": [
            DocumentPage(
                page_number=1,
                text=(
                    "MUTUAL NON-DISCLOSURE AGREEMENT\n\n"
                    "This Mutual Non-Disclosure Agreement ('Agreement') is entered into as of January 15, 2026 ('Effective Date'), "
                    "by and between Alpha Intelligence Labs, Inc., a Delaware corporation ('Disclosing Party'), and Beta Enterprise Solutions, LLC, "
                    "a Delaware limited liability company ('Receiving Party').\n\n"
                    "1. Purpose and Confidential Information\n"
                    "The parties wish to explore a potential strategic commercial partnership regarding document intelligence technologies ('Purpose'). "
                    "'Confidential Information' means all non-public information disclosed by one party ('Discloser') to the other party ('Recipient'), "
                    "whether orally or in writing, that is designated as confidential or that reasonably should be understood to be confidential "
                    "given the nature of the information and the circumstances of disclosure, including software code, technical specifications, "
                    "research benchmarks, business roadmaps, and customer data."
                ),
                char_count=1035,
                word_count=138,
                is_approximate=False,
                boundary_type="physical"
            ),
            DocumentPage(
                page_number=2,
                text=(
                    "2. Exclusions from Confidential Information\n"
                    "Confidential Information does not include information that: (a) is or becomes generally known to the public without breach of this Agreement; "
                    "(b) was known to the Recipient prior to its disclosure by the Discloser without breach of any confidentiality obligation; "
                    "(c) is independently developed by the Recipient without reference to or reliance upon Discloser's Confidential Information; or "
                    "(d) is rightfully received from a third party without duty of confidentiality.\n\n"
                    "3. Non-Disclosure and Use Obligations\n"
                    "Recipient agrees: (i) to hold Discloser's Confidential Information in strict confidence using at least the degree of care it uses "
                    "for its own confidential information of like nature, but not less than reasonable care; (ii) not to use Confidential Information "
                    "for any purpose outside the scope of the Purpose; and (iii) not to disclose Confidential Information to any third party except "
                    "to its employees, contractors, and advisors who need to know such information and are bound by confidentiality obligations at least as restrictive as this Agreement."
                ),
                char_count=1176,
                word_count=165,
                is_approximate=False,
                boundary_type="physical"
            ),
            DocumentPage(
                page_number=3,
                text=(
                    "4. Term and Termination\n"
                    "This Agreement shall remain in effect for a term of two (2) years from the Effective Date, after which either party may terminate "
                    "this Agreement upon thirty (30) days prior written notice. The obligations of confidentiality shall survive termination for a period of "
                    "three (3) years from the date of disclosure.\n\n"
                    "5. Governing Law and Jurisdiction\n"
                    "This Agreement, and all disputes arising out of or related to this Agreement, shall be governed by, and construed in accordance with, "
                    "the laws of the State of Delaware, without giving effect to any principles of conflicts of law. Each party irrevocably consents "
                    "to the exclusive personal jurisdiction and venue of the state and federal courts located in Wilmington, Delaware.\n\n"
                    "6. Entire Agreement\n"
                    "This Agreement constitutes the entire agreement between the parties concerning its subject matter and supersedes all prior agreements."
                ),
                char_count=1072,
                word_count=154,
                is_approximate=False,
                boundary_type="physical"
            )
        ]
    }
]

def ensure_demo_corpus_indexed(vector_store_instance) -> None:
    """
    Ensure the approved non-sensitive academic demo corpus is indexed in the demo store.
    Only indexes documents if the store is currently uninitialized or missing the demo docs.
    """
    existing_docs = {d.doc_id for d in vector_store_instance.list_documents()}
    for doc_data in DEMO_DOCUMENTS:
        doc_id = doc_data["doc_id"]
        if doc_id not in existing_docs:
            logger.info("Indexing approved demo document '%s' (%s)...", doc_id, doc_data["filename"])
            total_chars = sum(p.char_count for p in doc_data["pages"])
            vector_store_instance.index_document(
                doc_id=doc_id,
                filename=doc_data["filename"],
                file_type=doc_data["file_type"],
                file_size_bytes=total_chars,
                pages=doc_data["pages"],
                metadata=doc_data["metadata"],
                is_sample=True,
                chunk_size=500,
                chunk_overlap=80
            )

def is_approved_demo_doc_id(doc_id: str) -> bool:
    """Check if doc_id belongs to the approved demo corpus."""
    return doc_id in APPROVED_DEMO_DOC_IDS
