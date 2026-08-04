import json
import logging

import pytest

from src import task8_pageindex_vectorless as pageindex


def test_normalize_retrieved_nodes_preserves_legal_citation_metadata():
    document = {
        "doc_id": "pi-law",
        "title": "Bo luat Lao dong 2019",
        "filename": "bo_luat_lao_dong_2019.pdf",
        "source_url": "https://vanban.chinhphu.vn/example",
    }
    nodes = [
        {
            "title": "Dieu 26. Tien luong thu viec",
            "node_id": "0026",
            "relevant_contents": [
                {
                    "page_index": 18,
                    "relevant_content": "Tiền lương thử việc ít nhất bằng 85%.",
                }
            ],
        }
    ]

    results = pageindex.normalize_retrieved_nodes(nodes, document)

    assert results == [
        {
            "content": "Tiền lương thử việc ít nhất bằng 85%.",
            "score": 1.0,
            "metadata": {
                "doc_id": "pi-law",
                "title": "Bo luat Lao dong 2019",
                "filename": "bo_luat_lao_dong_2019.pdf",
                "source_url": "https://vanban.chinhphu.vn/example",
                "section": "Dieu 26. Tien luong thu viec",
                "node_id": "0026",
                "page": 18,
            },
            "source": "pageindex",
        }
    ]


def test_normalize_retrieved_nodes_skips_empty_content_and_scores_by_rank():
    nodes = [
        {
            "title": "A",
            "relevant_contents": [
                {"relevant_content": ""},
                {"relevant_content": "Nội dung một"},
                {"relevant_content": "Nội dung hai"},
            ],
        }
    ]

    results = pageindex.normalize_retrieved_nodes(nodes, {"doc_id": "pi-1"})

    assert [item["score"] for item in results] == [1.0, 0.5]


def test_pageindex_search_queries_manifest_documents_and_applies_top_k(tmp_path, monkeypatch):
    manifest = tmp_path / "documents.json"
    manifest.write_text(
        json.dumps(
            [
                {"doc_id": "pi-1", "title": "Law 1"},
                {"doc_id": "pi-2", "title": "Law 2"},
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(pageindex, "MANIFEST_PATH", manifest)
    monkeypatch.setattr(pageindex, "PAGEINDEX_API_KEY", "pix-test")

    def fake_retrieve(doc_id, query, **kwargs):
        return [
            {
                "title": doc_id,
                "relevant_contents": [
                    {"page_index": 1, "relevant_content": f"{query} in {doc_id}"}
                ],
            }
        ]

    monkeypatch.setattr(pageindex, "retrieve_document", fake_retrieve)

    results = pageindex.pageindex_search("thử việc", top_k=1)

    assert len(results) == 1
    assert results[0]["content"] == "thử việc in pi-1"
    assert results[0]["source"] == "pageindex"


def test_pageindex_search_uses_chat_api_when_legacy_retrieval_is_empty(
    tmp_path, monkeypatch
):
    manifest = tmp_path / "documents.json"
    manifest.write_text(
        json.dumps(
            [
                {
                    "doc_id": "pi-1",
                    "title": "Bộ luật Lao động 2019",
                    "filename": "bo-luat-lao-dong-2019.pdf",
                    "source_url": "https://vanban.chinhphu.vn/law",
                    "status": "completed",
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(pageindex, "MANIFEST_PATH", manifest)
    monkeypatch.setattr(pageindex, "PAGEINDEX_API_KEY", "pix-test")
    monkeypatch.setattr(pageindex, "retrieve_document", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        pageindex,
        "chat_document",
        lambda *_args, **_kwargs: "Thời gian thử việc tối đa 60 ngày. <doc=law.pdf;page=18>",
    )

    results = pageindex.pageindex_search("thử việc", top_k=3)

    assert len(results) == 1
    assert results[0]["content"].startswith("Thời gian thử việc tối đa 60 ngày")
    assert results[0]["metadata"]["retrieval_mode"] == "chat_api"
    assert results[0]["source"] == "pageindex"


def test_pageindex_search_requires_api_key(tmp_path, monkeypatch):
    manifest = tmp_path / "documents.json"
    manifest.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(pageindex, "MANIFEST_PATH", manifest)
    monkeypatch.setattr(pageindex, "PAGEINDEX_API_KEY", "")

    with pytest.raises(RuntimeError, match="PAGEINDEX_API_KEY"):
        pageindex.pageindex_search("query")


def test_upload_documents_recovers_completed_remote_document(tmp_path, monkeypatch):
    legal_dir = tmp_path / "legal"
    legal_dir.mkdir()
    (legal_dir / "bo-luat-lao-dong-2019.pdf").write_bytes(b"%PDF-test%%EOF")
    manifest = tmp_path / "documents.json"
    monkeypatch.setattr(pageindex, "LEGAL_DIR", legal_dir)
    monkeypatch.setattr(pageindex, "MANIFEST_PATH", manifest)
    monkeypatch.setattr(pageindex, "PAGEINDEX_API_KEY", "pix-test")
    monkeypatch.setattr(
        pageindex,
        "list_remote_documents",
        lambda: [
            {
                "id": "pi-existing",
                "name": "bo-luat-lao-dong-2019.pdf",
                "status": "completed",
                "pageNum": 83,
            }
        ],
    )

    def fail_if_uploaded(_):
        raise AssertionError("A completed remote document must not be uploaded again")

    monkeypatch.setattr(pageindex, "upload_document", fail_if_uploaded)

    documents = pageindex.upload_documents()

    assert documents[0]["doc_id"] == "pi-existing"
    assert documents[0]["status"] == "completed"
    assert documents[0]["source_url"].startswith("https://vanban.chinhphu.vn/")
    assert json.loads(manifest.read_text(encoding="utf-8")) == documents


def test_upload_documents_persists_recovered_entry_before_next_upload_fails(
    tmp_path, monkeypatch
):
    legal_dir = tmp_path / "legal"
    legal_dir.mkdir()
    for name in ("bo-luat-lao-dong-2019.pdf", "nghi-dinh-145-2020-nd-cp.pdf"):
        (legal_dir / name).write_bytes(b"%PDF-test%%EOF")
    manifest = tmp_path / "documents.json"
    monkeypatch.setattr(pageindex, "LEGAL_DIR", legal_dir)
    monkeypatch.setattr(pageindex, "MANIFEST_PATH", manifest)
    monkeypatch.setattr(pageindex, "PAGEINDEX_API_KEY", "pix-test")
    monkeypatch.setattr(
        pageindex,
        "list_remote_documents",
        lambda: [
            {
                "id": "pi-existing",
                "name": "bo-luat-lao-dong-2019.pdf",
                "status": "completed",
                "pageNum": 83,
            }
        ],
    )
    monkeypatch.setattr(
        pageindex,
        "upload_document",
        lambda _: (_ for _ in ()).throw(RuntimeError("LimitReached")),
    )

    with pytest.raises(RuntimeError, match="LimitReached"):
        pageindex.upload_documents()

    persisted = json.loads(manifest.read_text(encoding="utf-8"))
    assert persisted[0]["doc_id"] == "pi-existing"
    assert persisted[0]["status"] == "completed"


def test_pageindex_search_refreshes_processing_status_before_skipping(
    tmp_path, monkeypatch
):
    manifest = tmp_path / "documents.json"
    manifest.write_text(
        json.dumps(
            [
                {
                    "doc_id": "pi-processing",
                    "filename": "bo-luat-lao-dong-2019.pdf",
                    "status": "processing",
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(pageindex, "MANIFEST_PATH", manifest)
    monkeypatch.setattr(pageindex, "PAGEINDEX_API_KEY", "pix-test")
    monkeypatch.setattr(
        pageindex,
        "list_remote_documents",
        lambda: [
            {
                "id": "pi-processing",
                "name": "bo-luat-lao-dong-2019.pdf",
                "status": "completed",
                "pageNum": 83,
            }
        ],
    )
    monkeypatch.setattr(
        pageindex,
        "retrieve_document",
        lambda *_args, **_kwargs: [
            {
                "title": "Điều 25",
                "relevant_contents": [{"relevant_content": "Tối đa 60 ngày"}],
            }
        ],
    )

    results = pageindex.pageindex_search("thử việc", top_k=1)

    assert results[0]["content"] == "Tối đa 60 ngày"
    persisted = json.loads(manifest.read_text(encoding="utf-8"))
    assert persisted[0]["status"] == "completed"


def test_pageindex_search_warns_when_document_is_still_processing(
    tmp_path, monkeypatch, caplog
):
    manifest = tmp_path / "documents.json"
    manifest.write_text(
        json.dumps(
            [
                {
                    "doc_id": "pi-processing",
                    "filename": "law.pdf",
                    "status": "processing",
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(pageindex, "MANIFEST_PATH", manifest)
    monkeypatch.setattr(pageindex, "PAGEINDEX_API_KEY", "pix-test")
    monkeypatch.setattr(
        pageindex,
        "list_remote_documents",
        lambda: [
            {
                "id": "pi-processing",
                "name": "law.pdf",
                "status": "processing",
            }
        ],
    )

    with caplog.at_level(logging.WARNING):
        results = pageindex.pageindex_search("query")

    assert results == []
    assert "law.pdf" in caplog.text
    assert "processing" in caplog.text
