# BÀI TẬP NHÓM – Audit.py: Yêu cầu đề bài

**Môn:** Phân tích dữ liệu trong Kế toán – Kiểm toán
**Đề tài:** Audit.py – Hệ thống hỗ trợ đánh giá chấp nhận khách hàng kiểm toán

| Thông tin | Nội dung |
|---|---|
| Đối tượng | SV mã học phần: 261BAU402204, 261BAU402203, 261BAU402202, 261EAU402201 |
| Quy mô nhóm | 5 sinh viên |
| Thời gian hoàn thành | 2 tuần từ ngày nhận đề |
| Dữ liệu | Sổ nhật ký chung và số dư đầu kỳ |
| Công cụ | Python |
| Hình thức nộp | Mã nguồn + báo cáo đánh giá khách hàng |

## Tình huống

Công ty TNHH Kiểm toán UEL-Audit nhận thư mời kiểm toán BCTC năm của Công ty X. Trước khi ký hợp đồng, Ban Giám đốc yêu cầu nhóm kiểm toán viên (nhóm sinh viên) đánh giá chấp nhận khách hàng theo tinh thần **VSA 220** (kiểm soát chất lượng) và **VSA 210** (hợp đồng kiểm toán).

Công ty X gửi kèm Sổ Nhật ký chung cả năm. Nhóm viết chương trình Python để:

1. Đọc, làm sạch, kiểm tra toàn vẹn dữ liệu NKC.
2. Kiểm tra bút toán, phát hiện dấu hiệu gian lận và sai sót (VSA 240, VSA 315).
3. Tổng hợp NKC thành Bảng cân đối số phát sinh, Bảng cân đối kế toán, Báo cáo kết quả kinh doanh rút gọn.
4. Tính chỉ số sức khỏe tài chính, đánh giá hoạt động liên tục (VSA 570), thủ tục phân tích (VSA 520).
5. Xác định mức trọng yếu sơ bộ (VSA 320).
6. Trực quan hóa bằng biểu đồ.
7. Tổng hợp điểm rủi ro và kết luận: **Chấp nhận / Chấp nhận có điều kiện / Từ chối**.

## Lưu ý về chế độ kế toán

- Thông tư 99/2025/TT-BTC thay Thông tư 200/2014/TT-BTC, áp dụng cho năm tài chính bắt đầu từ 01/01/2026.
- Dữ liệu năm 2025 trở về trước dùng hệ thống tài khoản Thông tư 200.
- Chương trình phải cho phép cấu hình bảng ánh xạ tài khoản (JSON/CSV). **Không** viết cứng số hiệu tài khoản trong mã nguồn.

## Luồng xử lý (gợi ý)

```
NKC ─► M1 Toàn vẹn ─► M2 Test bút toán ─► M3 Sổ cái/TB/BCTC
                                              │
        M7 Kết luận ◄─ M6 Biểu đồ ◄─ M5 Trọng yếu ◄─ M4 Chỉ số
```

---

## Yêu cầu kỹ thuật bắt buộc

### Lập trình hướng đối tượng (OOP)

| STT | Kỹ thuật | Gợi ý vận dụng |
|---|---|---|
| 1 | Class, đối tượng, `__init__` | `GeneralLedger`, `TrialBalance`, `Client` |
| 2 | Đóng gói (`_protected`, `__private`, `@property`) | `TrialBalance.total_debit` chỉ đọc; không sửa trực tiếp dữ liệu gốc của NKC (giữ nguyên bằng chứng) |
| 3 | Kế thừa | `LineFormatLoader(BaseLoader)`, `PairFormatLoader(BaseLoader)` |
| 4 | Lớp trừu tượng (`abc.ABC`, `@abstractmethod`) | `BaseLoader`, `JournalEntryTest`, `FinancialStatement` |
| 5 | Đa hình | Engine gọi `test.run(df)` cho mọi thủ tục mà không cần biết loại cụ thể |
| 6 | `@dataclass` (ít nhất 1 lớp `frozen=True`) | `JournalLine`, `Finding`, `RatioResult` – bằng chứng kiểm toán không được thay đổi |
| 7 | Phương thức đặc biệt (dunder) | `__repr__`, `__len__`, `__iter__`, `__getitem__` cho `GeneralLedger`; `__add__` gộp hai `TrialBalance`; `__lt__` sắp xếp `Finding` theo rủi ro |
| 8 | `@classmethod`, `@staticmethod` | `Client.from_config(path)`, `Materiality.round_amount(x)` |
| 9 | Enum | `RiskLevel` (LOW, MEDIUM, HIGH), `Decision` (ACCEPT, CONDITIONAL, REJECT) |
| 10 | Composition | `AuditEngagement` chứa `Client`, `GeneralLedger`, danh sách `JournalEntryTest` |
| 11 | Ngoại lệ tự định nghĩa | `UnbalancedEntryError`, `SchemaError(Exception)` |
| 12 | Ít nhất 1 mẫu thiết kế | Strategy (các JE test), Factory (chọn Loader theo định dạng file), Registry (đăng ký chỉ số tài chính) |

### Lập trình hàm (FP)

| STT | Kỹ thuật | Gợi ý vận dụng |
|---|---|---|
| 1 | Hàm thuần, không thay đổi đầu vào | Mọi hàm tính chỉ số trong `m4_ratios.py` nhận số liệu, trả kết quả, không đọc biến toàn cục |
| 2 | `lambda` | Khóa sắp xếp, điều kiện lọc nhanh |
| 3 | `map`, `filter` | Chuẩn hóa mã tài khoản; lọc bút toán cuối kỳ |
| 4 | `functools.reduce` | Cộng dồn số dư TK theo từng bút toán; gộp nhiều bộ lọc thành một |
| 5 | Hàm bậc cao và closure | `make_threshold_test(nguong)` trả về hàm kiểm tra; `make_account_filter(prefix)` |
| 6 | Decorator tự viết | `@audit_log` (ghi tên thủ tục, thời gian chạy, số dòng vào/ra – audit trail); `@register_ratio` |
| 7 | `functools.partial` | `round_amount_test = partial(test_round_amount, base=1_000_000)` |
| 8 | Generator, `yield` | Đọc file lớn theo khối (`chunksize`), duyệt từng bút toán |
| 9 | `itertools` | `groupby` theo số chứng từ; `pairwise` kiểm tra khoảng trống số chứng từ; `accumulate` tính số dư lũy kế theo tháng |
| 10 | Function composition, pipeline | `compose(*fs)` hoặc `pipe(df, f1, f2, f3)`; `DataFrame.pipe()` cho bước làm sạch |
| 11 | Tính bất biến | `tuple`, `frozenset`, `MappingProxyType` cho cấu hình; `dataclass(frozen=True)` |
| 12 | Comprehension | list/dict/set comprehension cho tổng hợp kết quả |

---

## Yêu cầu chi tiết từng module

### Module 1 – Tiếp nhận và kiểm tra toàn vẹn dữ liệu

**Mục tiêu:** đảm bảo dữ liệu khách hàng đầy đủ và chính xác trước khi dùng làm bằng chứng.

- Đọc file bằng **Factory** chọn Loader phù hợp (CSV/Excel, dạng A/B); chuẩn hóa về một cấu trúc thống nhất.
- Chuẩn hóa: kiểu ngày, kiểu số, mã TK dạng chuỗi (giữ số 0 đầu, cắt khoảng trắng), xử lý giá trị thiếu.
- Lập **Bảng tóm tắt toàn vẹn dữ liệu**:
  - Số dòng, số chứng từ, khoảng thời gian (có đủ 12 tháng không).
  - Tổng phát sinh Nợ = tổng phát sinh Có (toàn sổ và từng chứng từ).
  - Tài khoản không có trong danh mục.
  - Dòng thiếu thông tin bắt buộc (ngày, TK, số tiền).
  - Số tiền âm, bằng 0.
  - Ngày ghi sổ ngoài kỳ kế toán; ngày ghi sổ khác ngày chứng từ quá X ngày.
  - Đối chiếu tổng phát sinh với Bảng cân đối số phát sinh của khách hàng.
- **Đầu ra:** `outputs/01_data_integrity.xlsx` và nhận xét về mức độ tin cậy của dữ liệu.

### Module 2 – Kiểm tra bút toán (Journal Entry Testing)

**Mục tiêu:** nhận diện rủi ro gian lận do Ban Giám đốc khống chế kiểm soát (VSA 240) và các bút toán bất thường.

Mỗi thủ tục là một lớp con của `JournalEntryTest`, trả về danh sách `Finding`. **Tối thiểu 10 thủ tục** trong 14 thủ tục sau:

| STT | Thủ tục | Ý nghĩa kiểm toán |
|---|---|---|
| 1 | Chứng từ không cân Nợ/Có | Sai sót hệ thống hoặc nhập liệu |
| 2 | Chứng từ trùng lặp (cùng số CT, ngày, số tiền, TK) | Ghi trùng chi phí/doanh thu |
| 3 | Khoảng trống/nhảy số chứng từ | Chứng từ bị hủy, bị xóa |
| 4 | Bút toán vào thứ Bảy, Chủ nhật, ngày lễ Việt Nam | Ngoài quy trình thông thường |
| 5 | Nhập liệu ngoài giờ làm việc (ví dụ sau 20h) | Ngoài quy trình thông thường |
| 6 | Số tiền tròn (chia hết cho 1 triệu, 10 triệu…) | Ước tính, bút toán điều chỉnh thủ công |
| 7 | Số tiền ngay dưới ngưỡng phê duyệt (95%–100% ngưỡng) | Né kiểm soát phê duyệt |
| 8 | Bút toán lớn sát ngày khóa sổ (±5 ngày quanh 31/12) | Rủi ro cut-off, thổi phồng doanh thu |
| 9 | Cặp TK đối ứng bất thường (Nợ 211/Có 511; Nợ 111/Có 511 giá trị lớn; Nợ 642/Có 111 giá trị lớn) | Hạch toán sai bản chất |
| 10 | Người lập lạ hoặc người lập có rất ít bút toán | Truy cập trái phép, phân quyền yếu |
| 11 | Diễn giải trống hoặc mơ hồ ("điều chỉnh", "khác", "xử lý") | Thiếu căn cứ |
| 12 | Khách hàng/đối tượng chỉ phát sinh 1 lần với giá trị lớn | Khách hàng ảo |
| 13 | Ngoại lệ thống kê (z-score hoặc IQR theo từng TK) | Giao dịch bất thường về quy mô |
| 14 | **Kiểm định Benford chữ số đầu (bắt buộc)** | Dấu hiệu dữ liệu bị "bịa" |

**Yêu cầu riêng cho Benford (thủ tục 14):**

- Tính tần suất thực tế chữ số đầu 1–9, so với kỳ vọng P(d) = log10(1 + 1/d).
- Tính thống kê Chi-bình phương và MAD. Ngưỡng MAD của Nigrini (chữ số đầu):

| MAD | Đánh giá |
|---|---|
| < 0,006 | Phù hợp chặt |
| 0,006 – 0,012 | Chấp nhận được |
| 0,012 – 0,015 | Phù hợp biên |
| > 0,015 | Không phù hợp |

- Thực hiện cho toàn bộ sổ và riêng cho nhóm TK doanh thu, nhóm TK chi phí.

**Mỗi `Finding` có tối thiểu:** mã thủ tục, số chứng từ, ngày, TK, số tiền, mô tả, mức độ rủi ro (`RiskLevel`). Kết quả xếp hạng theo rủi ro (dùng `__lt__`).

**Đầu ra:** `outputs/02_je_findings.xlsx` (mỗi thủ tục một sheet) và bảng tổng hợp số lượng, giá trị ngoại lệ theo thủ tục.

### Module 3 – Sổ cái, Bảng cân đối số phát sinh và BCTC rút gọn

- Lập `GeneralLedger` (sổ cái từng TK) và `TrialBalance` (số dư đầu kỳ, phát sinh Nợ, phát sinh Có, số dư cuối kỳ) bằng `reduce` hoặc `groupby`.
- **Loại trừ bút toán kết chuyển cuối kỳ** (sang TK 911, 421) khi tính doanh thu, chi phí; nếu không, TK loại 5–8 sẽ có số dư 0. Nhóm tự viết hàm nhận diện bút toán kết chuyển và giải thích logic.
- Ánh xạ TK sang chỉ tiêu BCTC qua `account_map.json` để lập:
  - **BCĐKT rút gọn:** Tiền, Phải thu, Hàng tồn kho, TSNH khác, TSCĐ (thuần), TSDH khác, Nợ ngắn hạn, Nợ dài hạn, Vốn chủ sở hữu.
  - **BCKQKD rút gọn:** Doanh thu thuần, Giá vốn, Lợi nhuận gộp, Chi phí bán hàng, Chi phí QLDN, Doanh thu/chi phí tài chính, Lợi nhuận khác, Lợi nhuận trước thuế, Thuế TNDN, Lợi nhuận sau thuế.
- Kiểm tra: Tổng tài sản = Tổng nguồn vốn (cho phép chênh lệch làm tròn).
- Lập số liệu theo tháng (doanh thu, giá vốn, chi phí, tiền) cho thủ tục phân tích xu hướng.
- TK lưỡng tính (131, 331, 138, 338…): phân tích theo đối tượng nếu có `ma_doi_tuong`; nếu không, nêu rõ giả định trình bày.

### Module 4 – Chỉ số sức khỏe tài chính và thủ tục phân tích

| Nhóm | Chỉ số | Công thức |
|---|---|---|
| Thanh khoản | Hệ số thanh toán hiện hành | TSNH / Nợ ngắn hạn |
| | Hệ số thanh toán nhanh | (TSNH − Hàng tồn kho) / Nợ ngắn hạn |
| | Hệ số thanh toán tiền mặt | Tiền và tương đương tiền / Nợ ngắn hạn |
| Cơ cấu vốn | Nợ phải trả / Tổng tài sản | |
| | Nợ phải trả / Vốn chủ sở hữu (D/E) | |
| | Khả năng trả lãi vay | EBIT / Chi phí lãi vay |
| Hiệu quả hoạt động | Vòng quay phải thu, DSO | Doanh thu thuần / Phải thu bình quân; 365 / vòng quay |
| | Vòng quay hàng tồn kho, DIO | Giá vốn / HTK bình quân; 365 / vòng quay |
| | Số ngày phải trả (DPO) | Phải trả người bán bình quân / Giá vốn × 365 |
| | Chu kỳ chuyển đổi tiền mặt (CCC) | DSO + DIO − DPO |
| | Vòng quay tổng tài sản | Doanh thu thuần / Tổng tài sản bình quân |
| Khả năng sinh lời | Biên lợi nhuận gộp, biên lợi nhuận ròng | |
| | ROA, ROE | LNST / Tài sản bình quân; LNST / VCSH bình quân |
| Cảnh báo | Altman Z'' | Z'' = 6,56·X1 + 3,26·X2 + 6,72·X3 + 1,05·X4 |
| | Tỷ lệ dồn tích (accruals ratio) | (LNST − Lưu chuyển tiền thuần từ HĐKD ước tính) / Tổng tài sản bình quân |

Trong đó: X1 = Vốn lưu động / Tổng tài sản; X2 = Lợi nhuận giữ lại / Tổng tài sản; X3 = EBIT / Tổng tài sản; X4 = Giá trị sổ sách VCSH / Tổng nợ phải trả.

Ngưỡng Altman Z'': > 2,6 vùng an toàn; 1,1 – 2,6 vùng xám; < 1,1 vùng nguy hiểm.

**Yêu cầu thêm:**

- Chia cho 0 phải an toàn: trả `None`/`NaN` kèm cảnh báo, không làm dừng chương trình.
- So sánh với ngưỡng tham chiếu (ví dụ trung bình ngành, nhóm tự tìm và **ghi nguồn**); gắn nhãn **Tốt / Cần chú ý / Rủi ro**.
- Thủ tục phân tích theo tháng: biến động doanh thu, biên lợi nhuận gộp từng tháng; tháng nào lệch quá ±2 độ lệch chuẩn phải được giải thích.
- Nếu có từ 2 năm dữ liệu (hoặc giảng viên cung cấp BCTC năm trước): phân tích xu hướng và tính thêm **Beneish M-score** (điểm cộng).

### Module 5 – Mức trọng yếu sơ bộ (VSA 320)

- Lớp `Materiality` tính mức trọng yếu tổng thể theo nhiều tiêu chí (ví dụ 5% lợi nhuận trước thuế, 0,5%–1% doanh thu, 1%–2% tổng tài sản). Cho phép chọn tiêu chí qua cấu hình và giải thích lý do chọn.
- Tính mức trọng yếu thực hiện (50%–75% mức tổng thể) và ngưỡng sai sót không đáng kể (khoảng 3%–5%).
- Dùng mức trọng yếu thực hiện làm ngưỡng lọc trong Module 2 (bút toán vượt ngưỡng → rủi ro cao).

### Module 6 – Trực quan hóa

**Tối thiểu 8 biểu đồ**, có tiêu đề, nhãn trục, đơn vị (triệu đồng/tỷ đồng), chú thích tiếng Việt, lưu vào `outputs/charts/`:

1. Doanh thu – giá vốn – lợi nhuận gộp theo tháng (đường/cột kết hợp).
2. Biên lợi nhuận gộp theo tháng, đánh dấu tháng bất thường.
3. Benford: tần suất thực tế so với kỳ vọng (cột + đường).
4. Heatmap số lượng bút toán theo ngày trong tuần × giờ nhập liệu.
5. Số lượng và giá trị bút toán theo người lập.
6. Phân phối số tiền giao dịch (histogram thang log) và boxplot theo nhóm TK.
7. Cơ cấu tài sản và nguồn vốn (cột chồng hoặc treemap).
8. Biểu đồ radar (hoặc bảng điều khiển) các nhóm chỉ số so với ngưỡng.
9. Biểu đồ đồng hồ/thanh thể hiện điểm rủi ro khách hàng và vùng quyết định.
10. *(Điểm cộng)* Dashboard tương tác bằng plotly hoặc Streamlit.

Các hàm vẽ nằm trong lớp `ChartBuilder`; dùng chung một hàm thiết lập định dạng (FP: hàm bậc cao bọc ngoài hàm vẽ).

### Module 7 – Đánh giá và kết luận chấp nhận khách hàng

Lớp `AcceptanceEngine` tổng hợp kết quả thành điểm rủi ro 0–100 theo trọng số trong `risk_weights.json`. Khung chấm gợi ý (nhóm được điều chỉnh nhưng phải lập luận):

| Nhóm yếu tố | Trọng số | Ví dụ tiêu chí |
|---|---|---|
| Chất lượng và toàn vẹn dữ liệu | 15% | Sổ không cân, thiếu tháng, TK lạ |
| Rủi ro gian lận từ kiểm tra bút toán | 30% | Số lượng/giá trị ngoại lệ so với mức trọng yếu; Benford không phù hợp |
| Sức khỏe tài chính và hoạt động liên tục | 30% | Altman Z'' vùng nguy hiểm, thanh khoản thấp, lỗ, D/E cao |
| Rủi ro báo cáo (cut-off, doanh thu, phải thu) | 15% | Doanh thu tăng đột biến cuối năm, DSO tăng mạnh |
| Yếu tố định tính (nhóm tự đánh giá) | 10% | Ngành nghề, quản trị, tính chính trực của Ban Giám đốc (nêu rõ giả định) |

**Quy tắc kết luận (ví dụ):**

| Điểm rủi ro | Kết luận | Hành động |
|---|---|---|
| 0–39 | Chấp nhận | Lập kế hoạch kiểm toán thông thường |
| 40–69 | Chấp nhận có điều kiện | Nêu rõ điều kiện: tăng cỡ mẫu, tham gia kiểm kê, xác nhận công nợ, bổ sung nhân sự có kinh nghiệm, phí kiểm toán phù hợp… |
| 70–100 | Từ chối | Nêu lý do chính dựa trên bằng chứng |

**Quy tắc chặn (knock-out rules):** một số phát hiện nghiêm trọng (ví dụ sổ không cân với giá trị trọng yếu, bút toán doanh thu khống vượt mức trọng yếu) tự động chuyển kết luận lên ít nhất "Chấp nhận có điều kiện", bất kể tổng điểm.

**Phân tích độ nhạy (bắt buộc):** thay đổi trọng số/ngưỡng ±20%, kết luận có thay đổi không?
