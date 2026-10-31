# audit_py – Hệ thống hỗ trợ đánh giá chấp nhận khách hàng kiểm toán

Đọc sổ (dùng làm Sổ Nhật ký chung) → kiểm tra dữ liệu → kiểm tra bút toán → lập báo cáo tài chính và chỉ số → chấm điểm rủi ro → đưa ra kết luận.

```
data/*.xlsx|csv ─► loaders ─► ledger ─► statements ─► ratios ─┐
                     │          └─► je_tests (14) ─────────────┼─► acceptance ─► báo cáo + Excel + biểu đồ
                     └─► integrity ─────────────────────────┘
```

## Cài đặt uv (một lần)

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
# hoặc: brew install uv

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

uv --version    # kiểm tra
```

Mở lại terminal sau khi cài. `uv` sẽ tự tải Python phù hợp theo `pyproject.toml`.

## Cách chạy

```bash
uv sync                                                   # một lần: tạo venv + cài thư viện
uv run python main.py                                     # dữ liệu thật (config/client_2024.json) -> outputs/
uv run python scripts/make_sample_data.py                 # tạo dữ liệu mẫu (có lỗi cài sẵn)
uv run python main.py config/client.json outputs_sample   # chạy dữ liệu mẫu
uv run pytest -q
```

Kết quả nằm trong `outputs/`: 5 file Excel, `charts/` (9 ảnh PNG), `report.md` (tiếng Việt).

Dữ liệu thật nằm trong `data/real/`: sổ chi tiết 2024 và bảng cân đối phát sinh tài khoản của khách hàng.

## Các module

| # | Module | File |
|---|---|---|
| 1 | Toàn vẹn dữ liệu | `audit/integrity.py`, `audit/loaders.py` |
| 2 | Kiểm tra bút toán JE01–JE14 (JE14 = Benford) | `audit/je_tests.py` |
| 3 | Sổ cái, bảng cân đối phát sinh, BCĐKT / KQKD | `audit/ledger.py`, `audit/statements.py` |
| 4 | Chỉ số tài chính, Altman Z'', dồn tích, ±2σ theo tháng | `audit/ratios.py`, `audit/analytics.py` |
| 5 | Mức trọng yếu (VSA 320) | `audit/materiality.py` |
| 6 | Biểu đồ | `audit/charts.py` |
| 7 | Đánh giá chấp nhận khách hàng | `audit/acceptance.py` |

Mọi con số có thể thay đổi nằm trong `config/` (tài khoản, ngưỡng, trọng số, benchmark). Không có mã tài khoản nào được viết cứng trong Python.

## Kỹ thuật được dùng ở đâu

| Kỹ thuật | Vị trí |
|---|---|
| Class, đóng gói | `GeneralLedger` (thuộc tính private `__df`, `.data` trả về bản sao) |
| Kế thừa + ABC | `BaseLoader`, `JournalEntryTest`, `FinancialStatement` |
| Đa hình | `AuditEngagement.run` gọi `t.run(df)` cho mọi thủ tục |
| Dataclass frozen | `Finding`, `RatioResult`, `Result`, `Assessment` (`models.py`, `engagement.py`) |
| Phương thức đặc biệt | `Finding.__lt__`, `GeneralLedger.__len__/__iter__/__getitem__/__repr__`, `TrialBalance.__add__` |
| classmethod / staticmethod | `Client.from_config`, `TrialBalance.from_ledger`, `Materiality.round_amount`, `AcceptanceEngine.assess` |
| Enum | `RiskLevel`, `Decision` |
| Composition | `AuditEngagement` chứa client, ledger, tb, statements, tests |
| Ngoại lệ tự định nghĩa | `AuditError`, `SchemaError`, `UnbalancedEntryError` |
| Factory | `loaders.make_loader` |
| Registry | `@register_test` (je_tests), `@register_ratio` (ratios) |
| Strategy | mỗi thủ tục JE là một lớp; `SCORERS` trong acceptance |
| Hàm thuần, pipe/compose | `fp.py`; `loaders.clean` gọi `pipe(df, parse_dates, ...)` |
| Lambda, map, filter, reduce | `reduce` trong `TrialBalance.from_ledger`; `filter`+`map` trong `GapTest`; lambda trong `KNOCKOUTS` |
| Closure / hàm bậc cao | `make_threshold_test` (JE07), `make_account_filter` (JE14), `@chart` |
| Decorator | `@audit_log`, `@register_ratio`, `@register_test`, `@chart` |
| partial | `RoundAmountTest` |
| Generator, itertools | `BaseLoader.chunks`, `GeneralLedger.entries` (`groupby`), `GapTest` (`pairwise`), `monthly_table` (`accumulate`) |
| Bất biến, comprehension | dataclass frozen, `assign` (không sửa tại chỗ) |

## Giả định

- Bút toán kết chuyển: chứng từ bị loại khỏi KQKD nếu có dòng nào ghi vào TK 911.
- Số dư KQKD chưa kết chuyển được cộng vào vốn chủ sở hữu trong BCĐKT.
- Dồn tích dùng CFO **ước tính**: LNST + khấu hao − ΔPhải thu − ΔHàng tồn kho + ΔPhải trả.
- Tài khoản như 131 / 331 trình bày theo số dư thuần (không tách theo bên Nợ/Có).
- Điểm định tính (ngành, quản trị, tính chính trực) trong `config/client_2024.json` do nhóm tự đánh giá.
- Số dư đầu kỳ lấy từ các dòng "Số dư đầu kỳ" của sổ; tài khoản không phát sinh trong năm lấy từ bảng cân đối của khách hàng.
- Chứng từ số dư đầu kỳ (tiền tố `OD`, `NKO`, `OI`, `OV`, ghi ngày đầu kỳ) được báo cáo riêng và không tính vào quy tắc chặn "sổ không cân". Danh sách tiền tố nằm trong `config/params.json`.
- Ngày tháng: `yyyy-mm-dd` trước, sau đó `dd/mm/yyyy`.

## Hạn chế dữ liệu (số liệu từ lần chạy dữ liệu thật 2024)

| Hạn chế | Số liệu cụ thể | Ảnh hưởng | Cách khắc phục |
|---|---|---|---|
| Không có giờ nhập (`gio`) | 0% dòng có dữ liệu | JE05 bị bỏ qua; biểu đồ 04 vẽ thứ trong tuần × tháng ghi sổ thay cho thứ × giờ | Xin khách hàng file có giờ nhập |
| Không có người lập (`nguoi_lap`) | 0% dòng có dữ liệu | JE10 bị bỏ qua; biểu đồ 05 nhóm theo tiền tố số chứng từ (top 15) | Xin file có user ID |
| Chỉ có 1 năm (2024) | 12 tháng, không có 2023 | Không có phân tích xu hướng, không tính Beneish M-score; chỉ số "bình quân" dùng số đầu kỳ và cuối kỳ của năm 2024 | Xin BCTC 2023 |
| TK 131/331 chưa tách theo đối tượng | `ma_doi_tuong` có ở 79% dòng, nhưng BCĐKT vẫn trình bày theo số dư thuần từng tài khoản | Công nợ phải thu/phải trả có thể bị bù trừ giữa các khách hàng | Tách theo `ma_doi_tuong` trong `statements.py` |
| JE03 chỉ đọc số chứng từ dạng "chuỗi + YYMM + số thứ tự" | 454 khoảng trống, tổng 624 số bị thiếu, dài nhất 19 số liên tiếp; 129 dòng không có số chứng từ | Có thể là sổ xuất thiếu, không chắc là chứng từ bị xóa | Hỏi khách hàng về chứng từ bị hủy / bộ lọc khi xuất sổ |
| Số dư đầu kỳ không có file riêng | Lấy từ dòng "Số dư đầu kỳ" của sổ; TK không phát sinh lấy từ bảng CĐPS của khách hàng | Nếu bảng CĐPS sai thì số dư đầu kỳ sai | Xin file số dư đầu kỳ riêng |
| Sổ lệch bảng CĐPS của khách hàng | 1 tài khoản: 6418, lệch 812,142 đồng (chứng từ `INO2402001`, các dòng lương/BHTN chỉ có bên Nợ) | Chứng từ không cân duy nhất ngoài nhóm đầu kỳ | Hỏi khách hàng về chứng từ này |
| Chứng từ số dư đầu kỳ lệch một vế | 34 chứng từ (`OD`, `NKO`, `OI`, `OV`, ghi ngày 01/01) | Được báo cáo riêng, không kích hoạt quy tắc chặn; JE01 vẫn đếm đủ 35 chứng từ | Kiểm toán viên xác nhận cách xử lý này |
| Chất lượng dòng | 1,579 dòng số tiền 0; 5,156 dòng số tiền âm; 376 dòng ngày ghi sổ cách ngày chứng từ hơn 30 ngày | Chỉ báo cáo, không loại khỏi phân tích | Xem sheet tương ứng trong `01_data_integrity.xlsx` |
| Tên và ngành khách hàng | Dùng tên giả định "Công ty X (dữ liệu thật 2024)" | Không chọn được benchmark ngành | Điền vào `config/client_2024.json` |

JE09 (cặp tài khoản bất thường) chạy được vì so sánh các tài khoản trong cùng một chứng từ, không cần cột TK đối ứng. Kết quả lần chạy này: 0 phát hiện.

## Chưa làm / cần nhóm bổ sung

| Việc | Hiện tại | Cần làm |
|---|---|---|
| Beneish M-score, dashboard (điểm cộng) | Chưa làm | Cần BCTC 2023 cho Beneish; dashboard dùng plotly hoặc Streamlit |
| `config/account_map_tt99.json` | Bản sao tạm của TT200 | Điền đúng hệ thống TK của TT99 trước khi dùng dữ liệu năm 2026 |
| `config/benchmarks.json` | Ngưỡng kinh nghiệm, không có nguồn | Thay bằng trung bình ngành có ghi nguồn |
| Ngày lễ 2024 trong `config/params.json` | Nhập từ trí nhớ (01/01, 08–14/02, 18/04, 30/04, 01/05, 02–03/09) | Đối chiếu thông báo chính thức |
| Ngưỡng phê duyệt JE07 | 500 triệu và 200 triệu đồng (giả định) | Dùng ngưỡng thật của công ty |
| Điểm định tính (ngành, quản trị, chính trực) | 40 / 50 / 40 (giả định) | Ghi lý do chấm trong báo cáo |
| Độ nhạy ±20% | Chỉ trọng số, tín hiệu, cutoff; chưa có mức trọng yếu | Thêm mức trọng yếu nếu giảng viên yêu cầu |
