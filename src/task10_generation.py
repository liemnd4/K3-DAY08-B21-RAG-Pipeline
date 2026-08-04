import os
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# CONFIGURATION — Giải thích lựa chọn
# =============================================================================

TOP_K = 5
TOP_P = 0.9
TEMPERATURE = 0.3
LLM_MODEL = "gpt-4o-mini"

# =============================================================================
# SYSTEM PROMPT (Dành cho Trợ Lý Luật Lao Động Gen Z)
# =============================================================================

SYSTEM_PROMPT = """Bạn là Trợ lý AI tra cứu và giải đáp các vấn đề pháp lý lao động cho người trẻ / Gen Z
(thử việc, OT, nghỉ phép, hợp đồng, sa thải, bảo hiểm, lương thưởng).

Quy tắc trả lời:
1. Ưu tiên tối đa các thông tin và căn cứ pháp lý từ context được cung cấp.
2. Mỗi khẳng định dựa trên tài liệu cần có trích dẫn nguồn ngay sau đó, ví dụ: [Bộ luật Lao động, 2019] hoặc [Nghị định 145/2020/NĐ-CP].
3. Trả lời bằng tiếng Việt chuyên nghiệp, rõ ràng, dễ hiểu cho người trẻ, giải thích ngắn gọn bản chất vấn đề.
4. Nếu context chưa chứa đầy đủ chi tiết, hãy tổng hợp thông tin liên quan có trong context để giải đáp một cách chính xác nhất."""


# =============================================================================
# DOCUMENT REORDERING (tránh lost in the middle)
# =============================================================================

def reorder_for_llm(chunks: list[dict]) -> list[dict]:
    """
    Sắp xếp chunks để tránh "lost in the middle" effect.

    LLM nhớ tốt thông tin ở ĐẦU và CUỐI prompt, quên thông tin ở GIỮA.
    Strategy: đặt chunks quan trọng nhất ở đầu và cuối, kém quan trọng ở giữa.

    Input order (by score):  [1, 2, 3, 4, 5]
    Output order:            [1, 3, 5, 4, 2]
    """
    if len(chunks) <= 2:
        return chunks

    front = chunks[::2]   # index 0, 2, 4
    back = chunks[1::2]   # index 1, 3
    return front + back[::-1]


# =============================================================================
# CONTEXT FORMATTING
# =============================================================================

def format_context(chunks: list[dict]) -> str:
    """
    Format chunks thành context string cho prompt.
    Mỗi chunk có label source để LLM có thể cite.
    """
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        source = chunk.get("metadata", {}).get("source", f"Source {i}")
        doc_type = chunk.get("metadata", {}).get("type", "legal")
        context_parts.append(
            f"[Document {i} | Source: {source} | Type: {doc_type}]\n"
            f"{chunk['content']}\n"
        )
    return "\n---\n".join(context_parts)


# =============================================================================
# GENERATION
# =============================================================================

# =============================================================================
# GENERATION (Hỗ trợ Multi-turn Memory & Comparison Mode)
# =============================================================================

BASIC_PROMPT = """Bạn là trợ lý AI trả lời câu hỏi dựa trên văn bản được cung cấp."""

def generate_with_citation(
    query: str,
    top_k: int = TOP_K,
    chat_history: list = None,
    mode: str = "advanced",
    use_reranking: bool = True,
) -> dict:
    """
    End-to-end RAG generation có citation và hỗ trợ multi-turn conversation memory.
    
    Args:
        query: Câu hỏi hiện tại
        top_k: Số lượng chunks retrieval
        chat_history: Lịch sử hội thoại dạng list [{'role': 'user'|'assistant', 'content': str}]
        mode: 'advanced' (Hybrid + RRF + Reorder + Citation) hoặc 'naive' (Naive Vector + No RRF)
        use_reranking: Dùng hybrid RRF khi True, dense-only baseline khi False.
    """
    import time
    start_time = time.time()

    if mode == "naive":
        try:
            from .task5_semantic_search import semantic_search
            chunks = semantic_search(query, top_k=top_k)
        except Exception:
            chunks = []
        reordered = chunks
        prompt_template = BASIC_PROMPT
    else:
        try:
            from .task9_retrieval_pipeline import retrieve
            chunks = retrieve(
                query, top_k=top_k, use_reranking=use_reranking
            )
        except Exception:
            chunks = []
        reordered = reorder_for_llm(chunks)
        prompt_template = SYSTEM_PROMPT

    context = format_context(reordered) if reordered else "Không có context."
    user_message = f"Context:\n{context}\n\n---\n\nQuestion: {query}"

    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        elapsed = round(time.time() - start_time, 3)
        return {
            "answer": "Tôi không thể xác minh thông tin này từ nguồn hiện có (Thiếu API Key).",
            "sources": chunks,
            "retrieval_source": chunks[0].get("source", "none") if chunks else "none",
            "mode": mode,
            "elapsed_sec": elapsed
        }

    from openai import OpenAI
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    if os.getenv("OPENROUTER_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        base_url = "https://openrouter.ai/api/v1"

    client = OpenAI(api_key=api_key, base_url=base_url)

    # Xây dựng danh sách messages hỗ trợ Multi-turn Conversation Memory
    messages = [{"role": "system", "content": prompt_template}]
    if chat_history:
        # Lấy tối đa 4 tin nhắn gần nhất (2 lượt hội thoại)
        for msg in chat_history[-4:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
    
    messages.append({"role": "user", "content": user_message})

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        temperature=TEMPERATURE,
        top_p=TOP_P,
    )

    answer = response.choices[0].message.content
    elapsed = round(time.time() - start_time, 3)

    return {
        "answer": answer,
        "sources": chunks,
        "retrieval_source": chunks[0].get("source", "hybrid") if chunks else "none",
        "mode": mode,
        "elapsed_sec": elapsed
    }


if __name__ == "__main__":
    test_queries = [
        "Thời gian thử việc tối đa cho vị trí lập trình viên là bao lâu?",
        "Công ty sa thải tôi qua tin nhắn Zalo không báo trước 30 ngày đúng hay sai?",
    ]

    for q in test_queries:
        print(f"\n{'='*70}")
        print(f"Q: {q}")
        print("=" * 70)
        result = generate_with_citation(q)
        print(f"\nA: {result['answer']}")
        print(f"\n[Sources: {len(result['sources'])} chunks | via {result['retrieval_source']}]")

