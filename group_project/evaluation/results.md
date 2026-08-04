# RAG Evaluation Results

## Trạng thái

Đã chạy RAGAS thật trên 24 câu hỏi cho cả hai cấu hình bằng OpenAI `gpt-4o-mini`. Cả 48 lượt pipeline đều thành công; raw answer/context được lưu trong `group_project/evaluation/artifacts/`.

## Cấu hình A/B

- `dense_no_rerank`: Dense-only retrieval, không RRF reranking.
- `hybrid_with_rerank`: Dense + sparse retrieval, hợp nhất bằng RRF.

## Overall Scores

| Metric | dense_no_rerank | hybrid_with_rerank | Δ |
|---|---:|---:|---:|
| faithfulness | 0.3366 | 0.6801 | +0.3435 |
| answer_relevancy | 0.7072 | 0.7411 | +0.0338 |
| context_recall | 0.6042 | 0.7986 | +0.1944 |
| context_precision | 0.8374 | 0.8802 | +0.0427 |

## Coverage và lỗi thu thập

| Config | Thành công | Lỗi | Tổng |
|---|---:|---:|---:|
| dense_no_rerank | 24/24 | 0 | 24 |
| hybrid_with_rerank | 24/24 | 0 | 24 |

## Worst Performers

| ID | Question | Average |
|---|---|---:|
| labor_009 | Công ty có được cho nhân viên nghỉ việc chỉ bằng một tin nhắn Zalo không? | 0.1987 |
| labor_007 | Người lao động ký hợp đồng không xác định thời hạn muốn nghỉ việc thông thường phải báo trước bao lâu? | 0.3150 |
| labor_014 | Thời giờ làm việc bình thường tối đa là bao nhiêu giờ? | 0.5636 |

## Phân tích worst performers

### `labor_009` — Cho nghỉ việc qua tin nhắn Zalo

Đây là lỗi retrieval kết hợp generation. Cả hai cấu hình không lấy được các Điều 35–36, 41, 122 và 125 cần thiết; context chủ yếu nói về thời giờ làm việc, thông tin doanh nghiệp và thử việc. Generation sau đó tự khẳng định phải thông báo bằng văn bản và viện dẫn sai Điều 38. Golden answer yêu cầu phân biệt đơn phương chấm dứt với xử lý kỷ luật sa thải, nên câu trả lời vừa thiếu căn cứ vừa quá tuyệt đối.

### `labor_007` — Báo trước khi nghỉ hợp đồng không xác định thời hạn

Retriever không lấy được điểm a khoản 1 Điều 35. Context lại chứa quy định về người sử dụng lao động và thủ tục kỷ luật. Cả hai cấu hình vì vậy trả sai `30 ngày` và viện dẫn Điều 36/37, trong khi đáp án đúng là ít nhất `45 ngày` theo Điều 35. Đây là trường hợp retrieval miss dẫn đến generation hallucination.

### `labor_014` — Thời giờ làm việc bình thường

Context không chứa trực tiếp Điều 105; phần lớn là Điều 107, 109, 116 hoặc nội dung OT. Generation vẫn trả đúng giới hạn 8 giờ/ngày và 48 giờ/tuần nhưng viện dẫn sai Điều 104, đồng thời thêm diễn giải 40 giờ/tuần không có trong context. Điểm thấp phản ánh faithfulness và context recall yếu dù đáp án bề mặt gần đúng.

## Kết luận A/B

`hybrid_with_rerank` thắng với điểm trung bình `0.7750`, cao hơn `dense_no_rerank` (`0.6214`) khoảng `0.1536`. Cải thiện lớn nhất nằm ở Faithfulness (`+0.3435`) và Context Recall (`+0.1944`), cho thấy BM25 + RRF giúp lấy đúng căn cứ pháp lý hơn dense-only trên corpus tiếng Việt. Context Precision chỉ tăng `+0.0427`, nghĩa là cả hai cấu hình vẫn đưa khá nhiều đoạn không cần thiết vào top 5.

## Khuyến nghị

1. Chunk theo Điều/Khoản thay vì chỉ cắt 500 ký tự để tiêu đề điều luật và nội dung không bị tách rời.
2. Lưu `article_number` trong metadata và tăng trọng số lexical khi câu hỏi chứa loại hợp đồng, thời hạn hoặc thuật ngữ pháp lý cụ thể.
3. Dùng embedding đa ngôn ngữ phù hợp tiếng Việt như `BAAI/bge-m3` thay cho `all-MiniLM-L6-v2`.
4. Siết system prompt: nếu context không chứa điều luật cần thiết thì phải từ chối xác minh, không tự suy đoán số điều hoặc hình thức thông báo.
5. Bổ sung truy vấn mở rộng cho các cặp khái niệm dễ nhầm: đơn phương chấm dứt/sa thải, Điều 35/36 và thời giờ bình thường/làm thêm giờ.
