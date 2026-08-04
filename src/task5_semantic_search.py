import chromadb
from pathlib import Path
from sentence_transformers import SentenceTransformer

CHROMA_DIR = Path(__file__).parent.parent / "chroma_db"
COLLECTION_NAME = "university_services_docs"
EMBEDDING_MODEL_NAME = "BAAI/bge-m3"

_model = None


def get_embedding_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _model


def semantic_search(query: str, top_k: int = 10) -> list[dict]:
    """
    Tìm kiếm ngữ nghĩa sử dụng vector similarity.

    Args:
        query: Câu truy vấn
        top_k: Số lượng kết quả tối đa

    Returns:
        List of {
            'content': str,      # Nội dung chunk
            'score': float,      # Cosine similarity score
            'metadata': dict     # source, doc_type, chunk_index
        }
        Sorted by score descending.
    """
    if not CHROMA_DIR.exists():
        return []

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        collection = client.get_collection(name=COLLECTION_NAME)
    except Exception:
        return []

    model = get_embedding_model()
    query_vector = model.encode(query).tolist()

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    if not results or not results.get("documents") or not results["documents"][0]:
        return []

    output = []
    for doc, meta, dist in zip(
        results["documents"][0], results["metadatas"][0], results["distances"][0]
    ):
        score = max(0.0, 1.0 - dist)
        output.append({"content": doc, "score": round(score, 4), "metadata": meta or {}})

    output.sort(key=lambda x: x["score"], reverse=True)
    return output[:top_k]


if __name__ == "__main__":
    results = semantic_search("thời gian thử việc vị trí lập trình viên", top_k=5)
    for r in results:
        print(f"[{r['score']:.3f}] {r['content'][:100]}...")

