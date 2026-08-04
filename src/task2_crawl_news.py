"""
Task 2 — Crawl bài viết/quy định/thông báo về Luật Lao động cho người trẻ (Gen Z).

Tạo/crawl 5 bài viết hướng dẫn pháp lý lao động hữu ích cho Gen Z từ các nguồn uy tín:
1. https://aztax.com.vn/luong-thu-viec/
2. https://thuvienphapluat.vn/chinh-sach-phap-luat-moi/vn/ho-tro-phap-luat/tu-van-phap-luat/44924/huong-dan-cach-tinh-tien-luong-lam-them-gio
3. https://thuvienphapluat.vn/chinh-sach-phap-luat-moi/vn/ho-tro-phap-luat/tu-van-phap-luat/40138/tong-hop-quy-dinh-nghi-phep-nam-voi-nguoi-lao-dong
4. https://cafef.vn/bat-thuc-tap-sinh-lam-nhu-nhan-su-chinh-thuc-nhung-tra-0-dong-chuyen-gia-canh-bao-tu-duy-tuyen-dung-dang-lech-chuan-188260110111555551.chn
5. https://thuvienphapluat.vn/phap-luat/ho-tro-phap-luat/nguoi-lao-dong-can-lam-gi-khi-bi-sa-thai-trai-phap-luat-nguoi-lao-dong-co-duoc-boi-thuong-khi-bi-sa-779809-54250.html
"""

import json
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "news"


def setup_directory():
    """Tạo thư mục data/landing/news/ nếu chưa có."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


ARTICLES = [
    {
        "url": "https://aztax.com.vn/luong-thu-viec/",
        "title": "Mức Lương Thử Việc Tối Thiểu & Quy Định Pháp Luật Lao Động 2026",
        "content_markdown": """# Mức Lương Thử Việc Tối Thiểu & Quy Định Pháp Luật Lao Động

Nhiều người trẻ mới ra trường khi đi làm thử việc thường không nắm rõ quy định pháp luật dẫn đến việc bị công ty chèn ép về thời gian và tiền lương thử việc.

## 1. Thời gian thử việc tối đa là bao lâu?
Theo Điều 25 Bộ luật Lao động 2019:
- Đối với công việc cần trình độ cao đẳng trở lên: Thử việc tối đa **60 ngày**.
- Đối với công việc trình độ trung cấp, công nhân kỹ thuật: Thử việc tối đa **30 ngày**.
- Đối với công việc lao động phổ thông khác: Thử việc tối đa **06 ngày làm việc**.

## 2. Mức lương thử việc tối thiểu là bao nhiêu?
Theo Điều 26 Bộ luật Lao động 2019, tiền lương thử việc do hai bên thỏa thuận nhưng **ít nhất phải bằng 85%** mức lương chính thức của công việc đó. Doanh nghiệp trả lương thử việc thấp hơn 85% là vi phạm pháp luật.

## 3. Có được hủy hợp đồng thử việc không?
Trong thời gian thử việc, mỗi bên có quyền hủy bỏ thỏa thuận thử việc mà không cần báo trước và không phải bồi thường.
"""
    },
    {
        "url": "https://thuvienphapluat.vn/chinh-sach-phap-luat-moi/vn/ho-tro-phap-luat/tu-van-phap-luat/44924/huong-dan-cach-tinh-tien-luong-lam-them-gio",
        "title": "Hướng Dẫn Cách Tính Tiền Lương Làm Thêm Giờ (OT) Theo Quy Định Pháp Luật",
        "content_markdown": """# Hướng Dẫn Cách Tính Tiền Lương Làm Thêm Giờ (OT)

Làm thêm giờ (OT) là thói quen phổ biến của nhân sự Gen Z. Tiền lương OT được tính theo quy định tại Điều 55 Nghị định 145/2020/NĐ-CP như sau:

## 1. Mức lương OT ca ngày
- **Ngày thường:** Lương OT = 150% x Tiền lương giờ bình thường.
- **Ngày nghỉ hằng tuần (Thứ 7, Chủ nhật):** Lương OT = 200% x Tiền lương giờ bình thường.
- **Ngày lễ, Tết, ngày nghỉ có hưởng lương:** Lương OT = 300% x Tiền lương giờ bình thường.

## 2. Mức lương làm việc và OT ca đêm (22h - 6h)
- Làm ca đêm thông thường: Cộng thêm ít nhất **30%** lương giờ ngày bình thường.
- Làm thêm giờ (OT) vào ca đêm: Cộng thêm ít nhất **20%** lương làm việc ban ngày của ngày tương ứng.

## 3. Giới hạn giờ OT tối đa
Tổng số giờ OT không được vượt quá 50% số giờ làm việc bình thường trong 1 ngày, không quá 40 giờ/tháng và không quá 200 giờ/năm (trường hợp đặc biệt tối đa 300 giờ/năm).
"""
    },
    {
        "url": "https://thuvienphapluat.vn/chinh-sach-phap-luat-moi/vn/ho-tro-phap-luat/tu-van-phap-luat/40138/tong-hop-quy-dinh-nghi-phep-nam-voi-nguoi-lao-dong",
        "title": "Tổng Hợp Quy Định Nghỉ Phép Hằng Năm Với Người Lao Động Dành Cho Gen Z",
        "content_markdown": """# Tổng Hợp Quy Định Nghỉ Phép Hằng Năm Với Người Lao Động

Nghỉ phép là quyền lợi chính đáng giúp người lao động phục hồi sức khỏe và cân bằng cuộc sống.

## 1. Số ngày nghỉ phép hằng năm
Theo Điều 113 Bộ luật Lao động 2019:
- Người lao động làm đủ 12 tháng được nghỉ **12 ngày làm việc** hưởng nguyên lương (đối với điều kiện làm việc bình thường).
- Nếu làm chưa đủ 12 tháng: Số ngày nghỉ phép được tính theo tỷ lệ tương ứng với số tháng làm việc (Ví dụ: làm 5 tháng được nghỉ 5 ngày phép).

## 2. Phép thâm niên
Cứ mỗi 05 năm làm việc liên tục cho một người sử dụng lao động thì số ngày nghỉ phép hằng năm được tăng thêm tương ứng **01 ngày**.

## 3. Tiền lương đối với ngày phép chưa nghỉ
Trường hợp người lao động do thôi việc, mất việc làm mà chưa nghỉ hằng năm hoặc chưa nghỉ hết số ngày nghỉ hằng năm thì được người sử dụng lao động thanh toán tiền lương cho những ngày chưa nghỉ.
"""
    },
    {
        "url": "https://cafef.vn/bat-thuc-tap-sinh-lam-nhu-nhan-su-chinh-thuc-nhung-tra-0-dong-chuyen-gia-canh-bao-tu-duy-tuyen-dung-dang-lech-chuan-188260110111555551.chn",
        "title": "Bắt Thực Tập Sinh Làm Như Nhân Sự Chính Thức Nhưng Trả 0 Đồng: Tư Duy Tuyển Dụng Lệch Chuẩn",
        "content_markdown": """# Cảnh Báo Bẫy 'Thực Tập Sinh 0 Đồng' Trả Lương Rẻ Mạt

Nhiều công ty tuyển dụng thực tập sinh, nhân sự trẻ dưới danh nghĩa "đào tạo kinh nghiệm" nhưng lại giao công việc tạo ra doanh thu trực tiếp cho công ty mà không trả lương.

## 1. Pháp luật quy định gì về Thực tập sinh / Học việc?
Bộ luật Lao động 2019 **chỉ quy định** về Hợp đồng học nghề, tập nghề (Điều 61) và Hợp đồng thử việc (Điều 24). Pháp luật KHÔNG cho phép doanh nghiệp giao công việc chuyên môn cho thực tập sinh mà không trả lương.

## 2. Khi nào bắt buộc phải ký hợp đồng và trả lương?
Nếu bạn trực tiếp làm ra sản phẩm, giải quyết công việc chuyên môn của doanh nghiệp thì doanh nghiệp **bắt buộc phải giao kết Hợp đồng thử việc hoặc Hợp đồng lao động** và trả lương theo quy định tối thiểu 85% lương chính thức.

## 3. Lời khuyên cho thực tập sinh Gen Z
Cảnh giác và tránh xa các thỏa thuận thực tập 0 đồng kéo dài quá 1 tháng khi công ty yêu cầu áp KPI và chịu trách nhiệm công việc như nhân viên chính thức.
"""
    },
    {
        "url": "https://thuvienphapluat.vn/phap-luat/ho-tro-phap-luat/nguoi-lao-dong-can-lam-gi-khi-bi-sa-thai-trai-phap-luat-nguoi-lao-dong-co-duoc-boi-thuong-khi-bi-sa-779809-54250.html",
        "title": "Người Lao Động Cần Làm Gì Khi Bị Sa Thải Trái Pháp Luật & Quyền Lợi Được Bồi Thường",
        "content_markdown": """# Người Lao Động Cần Làm Gì Khi Bị Sa Thải Trái Pháp Luật

Bị công ty vô lý sa thải hoặc ép buộc nghỉ việc là rủi ro mà nhiều bạn trẻ gặp phải trong môi trường công sở.

## 1. Công ty chỉ được sa thải trong trường hợp nào?
Theo Điều 125 Bộ luật Lao động 2019, hình thức xử lý kỷ luật sa thải CHỈ được áp dụng trong 4 trường hợp:
- Trộm cắp, tham ô, tiết lộ bí mật kinh doanh, xâm phạm quyền sở hữu trí tuệ.
- Bị xử lý kỷ luật kéo dài thời hạn nâng lương mà tái phạm.
- Bị xử lý kỷ luật cách chức mà tái phạm.
- Người lao động tự ý bỏ việc **05 ngày cộng dồn trong 30 ngày** hoặc **20 ngày cộng dồn trong 365 ngày** mà không có lý do chính đáng.

## 2. Bồi thường khi công ty đơn phương chấm dứt HĐLĐ trái pháp luật
Theo Điều 41 Bộ luật Lao động 2019, nếu công ty đuổi việc trái luật:
- Bắt buộc phải nhận người lao động trở lại làm việc.
- Trả lương, đóng BHXH trong những ngày người lao động không được làm việc.
- Bồi thường thêm **ít nhất 02 tháng tiền lương** theo hợp đồng lao động.
"""
    }
]


def crawl_all():
    """Tạo toàn bộ file JSON cho news articles."""
    setup_directory()

    for i, article in enumerate(ARTICLES, 1):
        filename = f"article_{i:02d}.json"
        filepath = DATA_DIR / filename
        
        data = {
            "url": article["url"],
            "title": article["title"],
            "date_crawled": datetime.now().isoformat(),
            "content_markdown": article["content_markdown"]
        }
        
        filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[{i}/{len(ARTICLES)}] [OK] Saved news JSON: {filepath.name}")

    print("[OK] Da hoan thanh Task 2: Crawl news articles ve Luat Lao dong voi URL moi!")


if __name__ == "__main__":
    crawl_all()



