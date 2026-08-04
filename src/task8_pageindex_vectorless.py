"""PageIndex vectorless retrieval adapter used as Task 9 fallback.

Upload is a one-time operation. Document IDs and citation metadata are kept in
``data/pageindex/documents.json``; queries reuse that manifest.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

API_URL = "https://api.pageindex.ai"
PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY", "")
LEGAL_DIR = Path(__file__).parent.parent / "data" / "landing" / "legal"
MANIFEST_PATH = Path(__file__).parent.parent / "data" / "pageindex" / "documents.json"
OFFICIAL_SOURCES = {
    "bo-luat-lao-dong-2019.pdf": {
        "title": "Bộ luật Lao động 2019",
        "source_url": "https://vanban.chinhphu.vn/?classid=1&docid=198540&pageid=27160",
    },
    "nghi-dinh-145-2020-nd-cp.pdf": {
        "title": "Nghị định 145/2020/NĐ-CP",
        "source_url": "https://vanban.chinhphu.vn/?docid=201967&pageid=27160",
    },
}
LOGGER = logging.getLogger(__name__)


def _headers() -> dict[str, str]:
    if not PAGEINDEX_API_KEY:
        raise RuntimeError("Thiếu PAGEINDEX_API_KEY trong file .env")
    return {"api_key": PAGEINDEX_API_KEY}


def load_manifest() -> list[dict]:
    if not MANIFEST_PATH.exists():
        return []
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Manifest phải là JSON array: {MANIFEST_PATH}")
    return data


def save_manifest(documents: list[dict]) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(documents, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def list_remote_documents() -> list[dict]:
    """List documents already present in the PageIndex account."""
    response = requests.get(
        f"{API_URL}/docs",
        headers=_headers(),
        params={"limit": 100, "offset": 0},
        timeout=60,
    )
    response.raise_for_status()
    return response.json().get("documents", [])


def _manifest_entry(filename: str, doc_id: str, **remote: Any) -> dict:
    citation = OFFICIAL_SOURCES.get(filename, {})
    return {
        "doc_id": doc_id,
        "filename": filename,
        "title": citation.get("title", Path(filename).stem.replace("_", " ")),
        "source_url": citation.get("source_url", ""),
        "status": remote.get("status", "processing"),
        "page_count": remote.get("pageNum"),
    }


def refresh_manifest_statuses(documents: list[dict]) -> list[dict]:
    """Refresh non-terminal manifest entries from PageIndex's document list."""
    if not any(item.get("status") not in (None, "completed") for item in documents):
        return documents
    remote_documents = list_remote_documents()
    remote_by_id = {item.get("id"): item for item in remote_documents}
    remote_by_name = {item.get("name"): item for item in remote_documents}
    refreshed = []
    for document in documents:
        if document.get("status") in (None, "completed"):
            refreshed.append(document)
            continue
        remote = remote_by_id.get(document.get("doc_id")) or remote_by_name.get(
            document.get("filename")
        )
        if remote:
            refreshed.append(
                _manifest_entry(document["filename"], remote["id"], **remote)
            )
        else:
            refreshed.append(document)
    save_manifest(refreshed)
    return refreshed


def wait_for_document(
    doc_id: str, timeout: float = 900, poll_interval: float = 5
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = requests.get(
            f"{API_URL}/doc/{doc_id}/",
            headers=_headers(),
            params={"type": "tree"},
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") == "completed" and payload.get("retrieval_ready"):
            return payload
        if payload.get("status") == "failed":
            raise RuntimeError(f"PageIndex xử lý thất bại cho {doc_id}: {payload}")
        time.sleep(poll_interval)
    raise TimeoutError(f"PageIndex chưa xử lý xong {doc_id} sau {timeout:g} giây")


def upload_document(pdf_path: Path) -> dict:
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"PageIndex document endpoint chỉ nhận PDF: {pdf_path}")
    with pdf_path.open("rb") as file_handle:
        response = requests.post(
            f"{API_URL}/doc/",
            headers=_headers(),
            files={"file": (pdf_path.name, file_handle, "application/pdf")},
            timeout=120,
        )
    if not response.ok:
        raise RuntimeError(
            f"PageIndex upload lỗi HTTP {response.status_code} cho {pdf_path.name}: "
            f"{response.text[:500]}"
        )
    doc_id = response.json().get("doc_id")
    if not doc_id:
        raise RuntimeError(f"PageIndex không trả doc_id cho {pdf_path.name}")
    return _manifest_entry(pdf_path.name, doc_id, status="processing")


def upload_documents() -> list[dict]:
    """Reconcile remote documents, then upload missing legal PDFs.

    PageIndex can take more than 15 minutes for long legal documents, so every
    ``doc_id`` is persisted immediately. A later run refreshes processing
    status from the remote document list and never uploads a duplicate name.
    """
    existing = load_manifest()
    by_filename = {item.get("filename"): item for item in existing}
    remote_by_filename = {
        item.get("name"): item for item in list_remote_documents() if item.get("name")
    }
    for pdf_path in sorted(LEGAL_DIR.glob("*.pdf")):
        remote = remote_by_filename.get(pdf_path.name)
        if remote:
            document = _manifest_entry(pdf_path.name, remote["id"], **remote)
            if pdf_path.name in by_filename:
                existing[existing.index(by_filename[pdf_path.name])] = document
            else:
                existing.append(document)
            by_filename[pdf_path.name] = document
            save_manifest(existing)
        elif pdf_path.name not in by_filename:
            document = upload_document(pdf_path)
            existing.append(document)
            by_filename[pdf_path.name] = document
            save_manifest(existing)
    save_manifest(existing)
    return existing


def retrieve_document(
    doc_id: str,
    query: str,
    timeout: float = 180,
    poll_interval: float = 2,
) -> list[dict]:
    response = requests.post(
        f"{API_URL}/retrieval/",
        headers=_headers(),
        json={"doc_id": doc_id, "query": query, "thinking": True},
        timeout=60,
    )
    response.raise_for_status()
    retrieval_id = response.json().get("retrieval_id")
    if not retrieval_id:
        raise RuntimeError(f"PageIndex không trả retrieval_id cho {doc_id}")

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = requests.get(
            f"{API_URL}/retrieval/{retrieval_id}/",
            headers=_headers(),
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") == "completed":
            return payload.get("retrieved_nodes", [])
        if payload.get("status") == "failed":
            raise RuntimeError(f"PageIndex retrieval thất bại: {payload}")
        time.sleep(poll_interval)
    raise TimeoutError(f"PageIndex retrieval quá {timeout:g} giây")


def chat_document(doc_id: str, query: str) -> str:
    """Use the current PageIndex Chat API when legacy retrieval returns no nodes."""
    response = requests.post(
        f"{API_URL}/chat/completions",
        headers={**_headers(), "Content-Type": "application/json"},
        json={
            "doc_id": doc_id,
            "messages": [{"role": "user", "content": query}],
            "stream": False,
            "enable_citations": True,
            "temperature": 0.0,
        },
        timeout=180,
    )
    response.raise_for_status()
    choices = response.json().get("choices", [])
    if not choices:
        return ""
    return str(choices[0].get("message", {}).get("content", "")).strip()


def normalize_retrieved_nodes(nodes: list[dict], document: dict) -> list[dict]:
    """Convert the current PageIndex legacy retrieval schema to Task 9 results."""
    results: list[dict] = []
    for node in nodes:
        relevant_contents = node.get("relevant_contents") or []
        # Compatibility with an older response shape that wrapped content in groups.
        if relevant_contents and isinstance(relevant_contents[0], list):
            relevant_contents = [item for group in relevant_contents for item in group]
        for item in relevant_contents:
            content = str(item.get("relevant_content", "")).strip()
            if not content:
                continue
            rank = len(results) + 1
            results.append(
                {
                    "content": content,
                    "score": 1.0 / rank,
                    "metadata": {
                        "doc_id": document.get("doc_id"),
                        "title": document.get("title"),
                        "filename": document.get("filename"),
                        "source_url": document.get("source_url"),
                        "section": node.get("title") or item.get("section_title"),
                        "node_id": node.get("node_id"),
                        "page": item.get("page_index"),
                    },
                    "source": "pageindex",
                }
            )
    return results


def pageindex_search(query: str, top_k: int = 5) -> list[dict]:
    """Query every manifested document and return normalized fallback contexts."""
    _headers()
    if not query.strip() or top_k <= 0:
        return []
    results: list[dict] = []
    documents = load_manifest()
    try:
        documents = refresh_manifest_statuses(documents)
    except Exception as error:
        LOGGER.warning("Could not refresh PageIndex document statuses: %s", error)
    for document in documents:
        if document.get("status") not in (None, "completed"):
            LOGGER.warning(
                "Skipping PageIndex document %s because status is %s",
                document.get("filename", document.get("doc_id", "unknown")),
                document.get("status", "unknown"),
            )
            continue
        doc_id = document.get("doc_id")
        if not doc_id:
            continue
        nodes = retrieve_document(doc_id, query)
        document_results = normalize_retrieved_nodes(nodes, document)
        if document_results:
            results.extend(document_results)
            continue
        chat_content = chat_document(doc_id, query)
        if chat_content:
            results.append(
                {
                    "content": chat_content,
                    "score": 1.0,
                    "metadata": {
                        "doc_id": doc_id,
                        "title": document.get("title"),
                        "filename": document.get("filename"),
                        "source_url": document.get("source_url"),
                        "retrieval_mode": "chat_api",
                    },
                    "source": "pageindex",
                }
            )
    # PageIndex exposes ranks rather than comparable cross-document scores.
    for rank, result in enumerate(results, 1):
        result["score"] = 1.0 / rank
    return results[:top_k]


if __name__ == "__main__":
    if not PAGEINDEX_API_KEY:
        raise SystemExit("Missing PAGEINDEX_API_KEY in .env")
    documents = upload_documents()
    print(f"PageIndex manifest has {len(documents)} documents: {MANIFEST_PATH}")
    for document in documents:
        print(f"- {document['filename']}: {document.get('status', 'unknown')}")
