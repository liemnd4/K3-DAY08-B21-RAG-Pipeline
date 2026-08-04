import chromadb
from pathlib import Path
from sentence_transformers import SentenceTransformer

CHROMA_DIR = Path(__file__).parent.parent / "chroma_db"
COLLECTION_NAME = "labor_law_genz_docs"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

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


# =============================================================================
# BONUS TASK 5 — HyDE (Hypothetical Document Embeddings) (+5 ĐIỂM BONUS)
# =============================================================================

def generate_hypothetical_document(query: str) -> str:
    """
    HyDE Step 1: Dùng LLM sinh một câu trả lời giả định dựa trên câu hỏi của user
    trước khi chuyển thành vector embedding.
    """
    try:
        import os
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            return query

        base_url = "https://api.openai.com/v1"
        model_name = "gpt-4o-mini"
        if os.getenv("OPENROUTER_API_KEY") and not os.getenv("OPENAI_API_KEY"):
            base_url = "https://openrouter.ai/api/v1"
            model_name = "meta-llama/llama-3.3-70b-instruct:free"

        client = OpenAI(api_key=api_key, base_url=base_url)
        prompt = f"Hãy viết một đoạn văn ngắn giả định trả lời cho câu hỏi pháp lý sau: {query}"

        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.5,
            timeout=10.0
        )
        hypo_doc = response.choices[0].message.content
        return hypo_doc
    except Exception as e:
        print(f"  [HyDE Fallback to original query due to API error: {e}]")
        return query


def semantic_search_hyde(query: str, top_k: int = 10) -> list[dict]:
    """
    Hàm tìm kiếm ngữ nghĩa nâng cao kết hợp kỹ thuật HyDE (+5 điểm Bonus).

    Args:
        query: Câu hỏi của người dùng
        top_k: Số lượng kết quả tìm kiếm

    Returns:
        List of chunks sorted by similarity score descending.
    """
    # 1. Sinh câu trả lời giả định từ LLM
    hypo_doc = generate_hypothetical_document(query)

    # 2. Embed và truy vấn bằng câu trả lời giả định thay vì câu hỏi gốc
    return semantic_search(query=hypo_doc, top_k=top_k)


if __name__ == "__main__":
    print("--- Test Standard Semantic Search ---")
    results = semantic_search("thời gian thử việc vị trí lập trình viên", top_k=3)
    for r in results:
        print(f"[{r['score']:.3f}] {r['content'][:100]}...")

    print("\n--- Test HyDE Semantic Search (+5 Bonus) ---")
    hyde_results = semantic_search_hyde("thời gian thử việc vị trí lập trình viên", top_k=3)
    for r in hyde_results:
        print(f"[{r['score']:.3f}] {r['content'][:100]}...")


