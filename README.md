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

## Hạn chế dữ liệu

- File sổ chi tiết không có giờ nhập và người lập: JE05, JE10 bị bỏ qua; biểu đồ 04, 05 dùng số liệu thay thế.
- Cột TK đối ứng gần như trống: JE09 yếu.
- Chỉ có dữ liệu một năm: không phân tích xu hướng, không tính Beneish M-score.
- JE03 chỉ kiểm tra số chứng từ có dạng "chuỗi + YYMM + số thứ tự".

## Chưa làm / cần kiểm tra

- Chưa làm: Beneish M-score, dashboard tương tác (điểm cộng).
- `config/account_map_tt99.json` chỉ là **bản sao tạm** của TT200. Cần điền trước khi dùng dữ liệu năm 2026.
- Ngưỡng trong `config/benchmarks.json` là ngưỡng kinh nghiệm. Cần thêm số liệu ngành có nguồn.
- Ngày lễ trong `config/params.json` cần đối chiếu với thông báo chính thức.
- Điểm định tính, ngưỡng phê duyệt (JE07) và tên công ty là giả định của nhóm, cần thay bằng số liệu thật.
