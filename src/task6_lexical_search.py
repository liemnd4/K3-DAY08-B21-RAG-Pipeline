import numpy as np
from pathlib import Path
from rank_bm25 import BM25Okapi

STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"
CHROMA_DIR = Path(__file__).parent.parent / "chroma_db"

CORPUS: list[dict] = []
_bm25_index = None


def tokenize(text: str) -> list[str]:
    """Tokenize text using underthesea if available, otherwise whitespace split."""
    text_lower = text.lower()
    try:
        from underthesea import word_tokenize
        tokens = word_tokenize(text_lower)
    except ImportError:
        tokens = text_lower.split()
    return tokens


def load_corpus() -> list[dict]:
    """
    Tải corpus từ ChromaDB (nếu có) hoặc từ file markdown trong data/standardized/.
    """
    global CORPUS
    if CORPUS:
        return CORPUS

    # Thử load từ ChromaDB trước để lấy đúng chunks
    if CHROMA_DIR.exists():
        try:
            import chromadb
            client = chromadb.PersistentClient(path=str(CHROMA_DIR))
            collection = client.get_collection(name="university_services_docs")
            all_docs = collection.get(include=["documents", "metadatas"])
            if all_docs and all_docs.get("documents"):
                for doc, meta in zip(all_docs["documents"], all_docs["metadatas"]):
                    CORPUS.append({"content": doc, "metadata": meta or {}})
                if CORPUS:
                    return CORPUS
        except Exception:
            pass

    # Fallback: đọc trực tiếp file markdown từ data/standardized/
    if STANDARDIZED_DIR.exists():
        for md_file in STANDARDIZED_DIR.rglob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8").strip()
                if content:
                    doc_type = "legal" if "legal" in str(md_file) else "news"
                    CORPUS.append({
                        "content": content,
                        "metadata": {"source": md_file.name, "type": doc_type}
                    })
            except Exception:
                pass

    return CORPUS


def build_bm25_index(corpus: list[dict]):
    """
    Xây dựng BM25 index từ corpus.
    """
    if not corpus:
        return None
    tokenized_corpus = [tokenize(doc["content"]) for doc in corpus]
    bm25 = BM25Okapi(tokenized_corpus)
    return bm25


def get_bm25():
    global _bm25_index, CORPUS
    if _bm25_index is None:
        corpus = load_corpus()
        if corpus:
            _bm25_index = build_bm25_index(corpus)
    return _bm25_index


def lexical_search(query: str, top_k: int = 10) -> list[dict]:
    """
    Tìm kiếm từ khóa sử dụng BM25.

    Args:
        query: Câu truy vấn
        top_k: Số lượng kết quả tối đa

    Returns:
        List of {
            'content': str,
            'score': float,      # BM25 score
            'metadata': dict
        }
        Sorted by score descending.
    """
    bm25 = get_bm25()
    corpus = load_corpus()

    if not bm25 or not corpus:
        return []

    tokenized_query = tokenize(query)
    scores = bm25.get_scores(tokenized_query)

    top_indices = np.argsort(scores)[::-1][:top_k]

    results = []
    for idx in top_indices:
        score_val = float(scores[idx])
        if score_val > 0:
            results.append({
                "content": corpus[idx]["content"],
                "score": round(score_val, 4),
                "metadata": corpus[idx]["metadata"]
            })
    return results



if __name__ == "__main__":
    results = lexical_search("thời gian thử việc lập trình viên", top_k=5)
    for r in results:
        print(f"[{r['score']:.3f}] {r['content'][:100]}...")

