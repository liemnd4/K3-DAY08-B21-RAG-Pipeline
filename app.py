"""
RAG Chatbot — University Services (Starter Template)
Streamlit app kết nối RAG Retrieval (Task 9) và Generation (Task 10).

Chạy:
    streamlit run app.py
"""

import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# Thêm project root vào sys.path để import các task từ src/
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# =============================================================================
# PAGE CONFIG
# =============================================================================

st.set_page_config(
    page_title="Trợ Lý Hỏi Đáp Luật Lao Động Gen Z",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =============================================================================
# SESSION STATE
# =============================================================================

if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_query" not in st.session_state:
    st.session_state.pending_query = None

# =============================================================================
# SIDEBAR — INFO & SETTINGS & BONUS FEATURES
# =============================================================================

with st.sidebar:
    st.title("⚖️ Luật Lao Động Gen Z")
    st.caption("Trợ lý AI tra cứu & giải đáp pháp lý lao động cho người trẻ")

    st.divider()

    st.subheader("💡 Câu hỏi gợi ý")
    suggestions = [
        "Thời gian thử việc tối đa cho lập trình viên là bao lâu và lương tối thiểu bao nhiêu %?",
        "Nếu công ty chỉ trả 70% lương thử việc thì bị xử phạt như thế nào?",
        "Công ty sa thải tôi qua tin nhắn Zalo không báo trước 30 ngày đúng hay sai?",
        "Làm thêm giờ (OT) vào ngày lễ được tính lương như thế nào?",
        "Hợp đồng thử việc/thực tập có phải đóng BHXH không?",
    ]
    for s in suggestions:
        if st.button(s, use_container_width=True, key=f"sug_{s[:20]}"):
            st.session_state["pending_query"] = s

    st.divider()
    st.subheader("⚙️ Cấu hình & Chế độ")
    
    # 🌟 BONUS FEATURE: Chế độ So Sánh Trước & Sau Cải Tiến
    pipeline_mode = st.radio(
        "🎯 Chế độ Pipeline (Trước/Sau cải tiến):",
        options=["🟢 Advanced RAG (Sau cải tiến)", "🔴 Naive Baseline (Trước cải tiến)", "⚔️ So Sánh A/B (Cả hai)"],
        index=0,
        help="Advanced: Hybrid Search + RRF Rerank + Lost in Middle Reorder + Citation System Prompt\nNaive: Single Vector Search + No Rerank + Basic Prompt"
    )

    top_k = st.slider("Số chunks retrieval (top_k)", 3, 10, 5)

    st.divider()
    # 🌟 BONUS FEATURE: Conversation Memory Controls
    st.caption(f"💬 Lịch sử hội thoại: **{len(st.session_state.messages)} tin nhắn**")
    if st.button("🗑️ Xóa lịch sử chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.caption("**Kiến trúc hệ thống RAG:**")
    st.caption("Hybrid Retrieval (Semantic + BM25) → RRF Rerank → PageIndex Fallback → LLM Generation có Citation")

# =============================================================================
# MAIN CHAT AREA
# =============================================================================

st.title("⚖️ Trợ Lý Hỏi Đáp Luật Lao Động Gen Z")
st.caption("Hệ thống RAG tra cứu và giải đáp chính xác theo Bộ luật Lao động 2019 & Nghị định hướng dẫn")

# Hiển thị lịch sử chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            if "elapsed_sec" in msg:
                st.caption(f"⚡ Thời gian phản hồi: `{msg['elapsed_sec']}s` | Mode: `{msg.get('mode', 'advanced')}`")
            if "sources" in msg and msg["sources"]:
                with st.expander(f"📚 Nguồn tham khảo ({len(msg['sources'])} chunks)"):
                    for i, src in enumerate(msg["sources"], 1):
                        meta = src.get("metadata", {})
                        source_name = meta.get("source", "Unknown")
                        doc_type = meta.get("type", "unknown")
                        score = src.get("score", 0)
                        st.markdown(f"**[{i}] {source_name}** `{doc_type}` | score: `{score:.4f}`")
                        st.text(src.get("content", "")[:300] + "...")
                        st.divider()

# =============================================================================
# QUERY HANDLING
# =============================================================================

user_input = st.chat_input("Nhập câu hỏi của bạn về Luật Lao Động...")
query = user_input or st.session_state.pending_query

if query:
    st.session_state.pending_query = None

    # Hiển thị câu hỏi của user
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    import src.task10_generation as t10
    import importlib
    importlib.reload(t10)

    # 1. TRƯỜNG HỢP SO SÁNH A/B (DÙNG TAB SONG SONG)
    if "So Sánh A/B" in pipeline_mode:
        with st.chat_message("assistant"):
            st.markdown("### ⚔️ KẾT QUẢ SO SÁNH TRƯỚC & SAU CẢI TIẾN RAG")
            tab1, tab2 = st.tabs(["🟢 Advanced RAG (Sau cải tiến)", "🔴 Naive RAG (Trước cải tiến)"])

            with tab1:
                with st.spinner("Đang chạy Advanced RAG Pipeline (Hybrid + RRF)..."):
                    res_adv = t10.generate_with_citation(
                        query, top_k=top_k, chat_history=st.session_state.messages[:-1], mode="advanced"
                    )
                st.markdown(res_adv["answer"])
                st.caption(f"⚡ Thời gian: `{res_adv['elapsed_sec']}s` | Retrieval: Hybrid + RRF Rerank + Lost-in-Middle Reorder")
                if res_adv.get("sources"):
                    with st.expander(f"📚 Nguồn trích dẫn ({len(res_adv['sources'])} chunks)"):
                        for i, src in enumerate(res_adv["sources"], 1):
                            meta = src.get("metadata", {})
                            st.markdown(f"**[{i}] {meta.get('source', 'Unknown')}** | score: `{src.get('score', 0):.4f}`")
                            st.text(src.get("content", "")[:250] + "...")

            with tab2:
                with st.spinner("Đang chạy Naive RAG (Vector Search đơn thuần)..."):
                    res_naive = t10.generate_with_citation(
                        query, top_k=top_k, chat_history=st.session_state.messages[:-1], mode="naive"
                    )
                st.markdown(res_naive["answer"])
                st.caption(f"⚡ Thời gian: `{res_naive['elapsed_sec']}s` | Retrieval: Naive Vector Search")
                if res_naive.get("sources"):
                    with st.expander(f"📚 Nguồn trích dẫn ({len(res_naive['sources'])} chunks)"):
                        for i, src in enumerate(res_naive["sources"], 1):
                            meta = src.get("metadata", {})
                            st.markdown(f"**[{i}] {meta.get('source', 'Unknown')}** | score: `{src.get('score', 0):.4f}`")
                            st.text(src.get("content", "")[:250] + "...")

            sources = res_adv.get("sources", [])
            answer_text = f"**[Advanced Mode Answer]**\n\n{res_adv['answer']}"
            elapsed_sec = res_adv.get("elapsed_sec", 0)
            mode_tag = "A/B Comparison"

    # 2. TRƯỜNG HỢP CHẠY ĐƠN LẺ
    else:
        selected_mode = "naive" if "Naive" in pipeline_mode else "advanced"
        with st.chat_message("assistant"):
            with st.spinner("Đang tìm kiếm văn bản pháp luật và tổng hợp câu trả lời..."):
                try:
                    response = t10.generate_with_citation(
                        query, top_k=top_k, chat_history=st.session_state.messages[:-1], mode=selected_mode
                    )
                    answer_text = response.get("answer", "Chưa thể trả lời.")
                    sources = response.get("sources", [])
                    elapsed_sec = response.get("elapsed_sec", 0)
                    mode_tag = selected_mode
                except Exception as e:
                    answer_text = f"❌ **Lỗi khi chạy RAG Pipeline:** {e}"
                    sources = []
                    elapsed_sec = 0
                    mode_tag = selected_mode

            st.markdown(answer_text)
            st.caption(f"⚡ Thời gian phản hồi: `{elapsed_sec}s` | Pipeline: `{mode_tag}`")

            if sources:
                with st.expander(f"📚 Nguồn tham khảo trích dẫn ({len(sources)} chunks)"):
                    for i, src in enumerate(sources, 1):
                        meta = src.get("metadata", {})
                        source_name = meta.get("source", "Unknown")
                        doc_type = meta.get("type", "unknown")
                        score = src.get("score", 0)
                        st.markdown(f"**[{i}] {source_name}** `{doc_type}` | score: `{score:.4f}`")
                        st.text(src.get("content", "")[:300] + "...")
                        st.divider()

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer_text,
        "sources": sources,
        "elapsed_sec": elapsed_sec,
        "mode": mode_tag
    })
