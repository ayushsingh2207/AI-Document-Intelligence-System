"""
Tests restart behavior and disk persistence for FAISS index and metadata store.
"""
import os
import tempfile
import shutil
from app.schemas.document import DocumentPage
from app.services.vector_store import VectorStore

def test_vector_store_restart_persistence():
    temp_dir = tempfile.mkdtemp(prefix="vector_test_persistence_")
    try:
        # 1. Instantiate store in temp dir and index a document
        store1 = VectorStore(data_dir=temp_dir)
        doc_page = DocumentPage(
            page_number=1,
            text="Autonomous agents utilize planning loops and semantic memories to persist state across interruptions.",
            char_count=107,
            word_count=13,
            is_approximate=False,
            boundary_type="physical"
        )
        store1.index_document(
            doc_id="persist_doc_01",
            filename="persistence_sample.txt",
            file_type="TXT",
            file_size_bytes=107,
            pages=[doc_page]
        )
        
        # Verify initial state
        assert store1.get_stats().total_documents == 1
        assert store1.get_stats().total_vectors >= 1
        initial_search = store1.search("planning loops and memory", top_k=1)
        assert len(initial_search.results) == 1
        initial_score = initial_search.results[0].score

        # Ensure index and metadata files exist on disk
        index_file = os.path.join(temp_dir, "vector_index.faiss")
        meta_file = os.path.join(temp_dir, "metadata_store.json")
        assert os.path.exists(index_file)
        assert os.path.exists(meta_file)

        # 2. Simulate complete application restart by instantiating a new VectorStore instance
        del store1
        store2 = VectorStore(data_dir=temp_dir)

        # 3. Verify that restored instance has identical document and vector counts
        stats2 = store2.get_stats()
        assert stats2.total_documents == 1
        assert stats2.total_vectors >= 1
        assert "persist_doc_01" in [d.doc_id for d in store2.list_documents()]


        # 4. Verify search on restored instance produces exact same score and result
        res_after = store2.search("planning loops and memory", top_k=1)
        assert len(res_after.results) == 1
        assert res_after.results[0].doc_id == "persist_doc_01"
        assert abs(res_after.results[0].score - initial_score) < 1e-4

        # 5. Verify document deletion purges the disk files on save
        deleted = store2.delete_document("persist_doc_01")
        assert deleted is True
        assert store2.get_stats().total_documents == 0
        assert store2.get_stats().total_vectors == 0

        # Restart again and confirm empty state persisted cleanly
        del store2
        store3 = VectorStore(data_dir=temp_dir)
        assert store3.get_stats().total_documents == 0
        assert store3.get_stats().total_vectors == 0
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
