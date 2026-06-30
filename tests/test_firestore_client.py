from src.clients.firestore_client import FirestoreClient


def test_firestore_mock_can_persist_and_reload(tmp_path):
    storage_path = tmp_path / "firestore.json"
    first = FirestoreClient(dry_run=True, storage_path=str(storage_path))
    first.add_document("product_candidates", {"title": "test", "status": "fetched"}, doc_id="p1")

    second = FirestoreClient(dry_run=True, storage_path=str(storage_path))
    docs = second.get_documents_by_status("product_candidates", "fetched")

    assert docs[0]["id"] == "p1"
    assert docs[0]["title"] == "test"
