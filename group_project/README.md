# Bài Tập Nhóm — University Services RAG Chatbot

## Mục Tiêu

Sau khi hoàn thành bài cá nhân, nhóm ngồi lại để xây dựng **1 trong 2 sản phẩm**:

---

## Yêu cầu 1: Sản phẩm nhóm RAG Chatbot

Xây dựng chatbot trả lời câu hỏi về dịch vụ và chính sách đại học liên quan.

**Yêu cầu:**
- Giao diện chat (Streamlit / Gradio / Chainlit)
- Trả lời có citation (dựa trên Task 10)
- Hỗ trợ follow-up questions (conversation memory)
- Hiển thị source documents đã dùng

**Stack gợi ý:**
```
Chainlit/Streamlit → Retrieval (Task 9) → Generation (Task 10) → Display
```

---

## Yêu cầu 2: RAG Evaluation Pipeline

Sử dụng **1 trong 3 framework** sau để evaluate pipeline RAG của nhóm:

### Framework lựa chọn

| Framework | Cài đặt | Đặc điểm |
|-----------|---------|-----------|
| [DeepEval](https://github.com/confident-ai/deepeval) | `pip install deepeval` | Nhiều metric built-in, dễ integrate với pytest |
| [RAGAS](https://github.com/explodinggradients/ragas) | `pip install ragas` | Chuẩn industry cho RAG eval, 3 trục chính |
| [TruLens](https://github.com/truera/trulens) | `pip install trulens` | Dashboard UI, feedback functions mạnh |

### Yêu cầu Evaluation

1. **Tạo Golden Dataset** — tối thiểu 15 cặp Q&A (question, expected_answer, expected_context)
2. **Chạy evaluation** trên toàn bộ golden dataset với các metrics sau:
   - **Faithfulness** — câu trả lời có bám đúng context không?
   - **Answer Relevance** — câu trả lời có đúng câu hỏi không?
   - **Context Recall** — retriever có lấy đủ evidence không?
   - **Context Precision** — trong context lấy về, bao nhiêu % thực sự hữu ích?
3. **So sánh A/B** — chạy eval trên ít nhất 2 config khác nhau (ví dụ: có reranking vs không reranking, hoặc hybrid vs dense-only)
4. **Báo cáo** — bảng điểm + phân tích worst performers + đề xuất cải tiến

Xem code mẫu (DeepEval/RAGAS/TruLens) chi tiết trong `README.md` gốc mục "Yêu cầu 2".

### Deliverable Evaluation

- [ ] File `group_project/evaluation/golden_dataset.json` — 15+ cặp Q&A
- [ ] File `group_project/evaluation/eval_pipeline.py` — script chạy evaluation
- [ ] File `group_project/evaluation/results.md` — bảng điểm + phân tích
- [ ] So sánh A/B ít nhất 2 configs

---

## Yêu Cầu Chung

1. **Tích hợp pipeline** từ bài cá nhân của các thành viên
2. **Demo hoạt động được** trong buổi trình bày (chạy local hoặc deploy)
3. **Evaluation pipeline** chạy được và có báo cáo kết quả
4. **Code push lên repository** chung của nhóm
5. **README** mô tả kiến trúc và phân công (điền bên dưới)

---

## Kiến Trúc Hệ Thống

```
[Vẽ diagram kiến trúc ở đây]
```

---

## Phân Công Công Việc

| Thành viên | MSSV | Nhiệm vụ | Trạng thái |
|-----------|------|----------|------------|
| | | | |
| | | | |
| | | | |
| | | | |

---

## Hướng Dẫn Chạy

```bash
# Cài đặt dependencies
pip install -r requirements.txt

# Chạy app
streamlit run app.py
# hoặc
chainlit run app.py
```

## Member 3: PageIndex và Evaluation

Kiểm tra Golden Dataset 24 câu hỏi luật lao động:

```powershell
python -m group_project.evaluation.eval_pipeline
```

Chuẩn bị PageIndex:

1. Tạo API key tại `https://dash.pageindex.ai` và điền `PAGEINDEX_API_KEY` trong `.env`.
2. Đặt PDF gốc vào `data/landing/legal/`.
3. Chạy `python -m src.task8_pageindex_vectorless` để đồng bộ tài liệu remote và upload các PDF chưa có.
4. Script lưu `doc_id`, trạng thái, số trang và citation vào `data/pageindex/documents.json` ngay sau upload/đồng bộ.

Hiện tài khoản đã xử lý thành công `bo-luat-lao-dong-2019.pdf` (83 trang). Gói PageIndex hiện tại trả `LimitReached` khi upload tài liệu thứ hai. Fallback vì vậy truy vấn Bộ luật Lao động; sau khi tăng quota chỉ cần chạy lại uploader để thêm Nghị định 145. Legacy Retrieval API có thể trả rỗng nên module tự chuyển sang Chat API hiện hành và bật citation.

Evaluation cần callable từ Task 9/10 trả đúng contract:

`src.task10_generation.generate_with_citation` đã nhận tham số `use_reranking` và trả `answer` cùng `sources`, nên có thể dùng trực tiếp làm pipeline adapter.

Sau khi có callable:

```python
from group_project.evaluation.eval_pipeline import compare_configs, export_results, load_golden_dataset, run_ab_evaluation
from src.task10_generation import generate_with_citation

evaluations = run_ab_evaluation(generate_with_citation, load_golden_dataset())
comparison = compare_configs(evaluations)
export_results(comparison)
```

Hai cấu hình được đo là `dense_no_rerank` và `hybrid_with_rerank` (dense + sparse hợp nhất bằng RRF), nên A/B tạo ra hai đường retrieval thực sự khác nhau.

Raw answer/context được checkpoint sau từng câu tại `group_project/evaluation/artifacts/<config>_rows.json`. Nếu pipeline hoặc RAGAS bị timeout/rate-limit, chạy lại cùng lệnh sẽ bỏ qua câu đã thành công và chỉ thử lại câu lỗi/chưa chạy. Báo cáo hiển thị coverage và lý do lỗi theo từng cấu hình.

RAGAS gọi LLM nhiều lần cho mỗi câu. Nên thử subset 2–3 câu trước, sau đó mới chạy đủ 24 câu khi quota cho phép.

---

## Lưu ý

Hãy giữ lại repo này nếu như bạn học track 3 giai đoạn 2, chúng ta sẽ phát triển tiếp dự án lên knowledge graph để khắc phục các câu hỏi hóc búa khi có các câu hỏi khó.
