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
(thử việc, OT, nghỉ phép, hợp đồng học việc, sa thải, bảo hiểm, lương thưởng).

Quy tắc bắt buộc:
1. Chỉ sử dụng thông tin từ context được cung cấp — KHÔNG bịa đặt thông tin.
2. Mỗi khẳng định phải có trích dẫn nguồn ngay sau đó, ví dụ: [Bộ luật Lao động, 2019] hoặc [Hợp đồng lao động mẫu, 2023].
3. Nếu context không đủ thông tin để trả lời câu hỏi → trả lời chính xác câu: "Tôi không thể xác minh thông tin này từ nguồn hiện có"
4. Trả lời bằng tiếng Việt, rõ ràng, mạch lạc, dễ hiểu cho người trẻ.
5. Không suy luận hay mở rộng ngoài những gì được nêu trong context."""


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

def generate_with_citation(query: str, top_k: int = TOP_K) -> dict:
    """
    End-to-end RAG generation có citation.
    """
    try:
        from .task9_retrieval_pipeline import retrieve
        chunks = retrieve(query, top_k=top_k)
    except Exception:
        chunks = []

    reordered = reorder_for_llm(chunks)
    context = format_context(reordered) if reordered else "Không có context."

    user_message = f"Context:\n{context}\n\n---\n\nQuestion: {query}"

    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return {
            "answer": "Tôi không thể xác minh thông tin này từ nguồn hiện có (Thiếu API Key).",
            "sources": chunks,
            "retrieval_source": chunks[0].get("source", "none") if chunks else "none"
        }

    from openai import OpenAI
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    if os.getenv("OPENROUTER_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        base_url = "https://openrouter.ai/api/v1"

    client = OpenAI(api_key=api_key, base_url=base_url)

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ],
        temperature=TEMPERATURE,
        top_p=TOP_P,
    )

    answer = response.choices[0].message.content

    return {
        "answer": answer,
        "sources": chunks,
        "retrieval_source": chunks[0].get("source", "hybrid") if chunks else "none"
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

