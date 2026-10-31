"""Write Excel files, charts and the Vietnamese acceptance report."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .charts import ChartBuilder
from .engagement import Result
from .fp import TRAIL
from .je_tests import entries
from .models import Finding

VI = {"ma_thu_tuc": "Mã thủ tục", "so_ct": "Số CT", "ngay": "Ngày", "tk": "TK", "so_tien": "Số tiền",
      "mo_ta": "Mô tả", "muc_do": "Mức độ rủi ro", "chi_tieu": "Chỉ tiêu", "gia_tri": "Giá trị",
      "danh_gia": "Đánh giá", "thu_tuc": "Thủ tục", "so_luong": "Số lượng", "so_rui_ro_cao": "Số rủi ro cao",
      "ghi_chu": "Ghi chú", "kich_ban": "Kịch bản", "diem": "Điểm", "ket_luan": "Kết luận",
      "doi_ket_luan": "Đổi kết luận?",
      "ket_luan_theo_diem": "Kết luận theo điểm", "doi_theo_diem": "Đổi (theo điểm)?"}


def write_excel(path: Path, sheets: dict[str, pd.DataFrame]) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        for name, df in sheets.items():
            df.rename(columns=VI).to_excel(xw, sheet_name=name[:31], index=False)


def benford_frames(res: Result) -> tuple[pd.DataFrame, pd.DataFrame]:
    summ = pd.DataFrame([{"nhom": k, "n": v["n"], "mad": v["mad"], "chi2": v["chi2"], "muc_phu_hop": v["level"]}
                         for k, v in res.benford.items()])
    freq = pd.concat({k: v["table"] for k, v in res.benford.items()}, names=["nhom"]).reset_index() if res.benford else summ
    return summ, freq


def md_table(df: pd.DataFrame) -> str:
    head = "| " + " | ".join(map(str, df.columns)) + " |\n|" + "---|" * len(df.columns)
    rows = ["| " + " | ".join((f"{v:,.4f}" if 0 < abs(v) < 1 else f"{v:,.2f}") if isinstance(v, float) else str(v) for v in r) + " |"
            for r in df.itertuples(index=False)]
    return "\n".join([head, *rows])


def _ratio_frame(res: Result) -> pd.DataFrame:
    return pd.DataFrame([{"nhom": r.group, "chi_so": r.name, "gia_tri": r.value, "danh_gia": r.label, "ghi_chu": r.note}
                         for r in res.ratios])


def group_scores(res: Result) -> dict[str, float]:
    score = {"Tốt": 100, "Cần chú ý": 50, "Rủi ro": 0}
    df = _ratio_frame(res).assign(diem=lambda d: d["danh_gia"].map(score)).dropna(subset=["diem"])
    return df.groupby("nhom")["diem"].mean().to_dict()


def write_charts(res: Result, lines: pd.DataFrame, out: Path) -> list[Path]:
    cb, st = ChartBuilder(out / "charts"), res.statements
    ents = entries(lines)
    paths = [cb.revenue_cogs_profit(st.monthly), cb.gross_margin(res.month_flags)]
    if "Toàn sổ" in res.benford:
        paths.append(cb.benford(res.benford["Toàn sổ"]))
    paths += [cb.heatmap(ents), cb.by_user(ents), cb.distribution(lines), cb.structure(st.bs),
              cb.radar(group_scores(res)), cb.gauge(res.assessment.total, res.cutoffs)]
    return paths


def write_report(res: Result, out: Path) -> Path:
    a, m, st = res.assessment, res.materiality, res.statements
    top = pd.DataFrame([f.row() for f in res.findings[:10]])
    factors = pd.DataFrame([{"nhom": k, "diem": v, "trong_so": a.weights[k]} for k, v in a.scores.items()])
    d = res.integrity.details
    tb_diff = d.get("lech_so_voi_khach_hang")
    recon = ("Đối chiếu với bảng CĐSPS của khách hàng: không có tài khoản lệch." if tb_diff is None or tb_diff.empty else
             "Tài khoản lệch so với bảng CĐSPS của khách hàng (đã đối chiếu với chứng từ không cân ở mục JE01):\n\n"
             + md_table(tb_diff))
    opening = d.get("chung_tu_so_du_dau_ky")
    open_note = (f"{len(opening)} chứng từ số dư đầu kỳ (ghi ngày đầu kỳ, lệch một vế do nhập số dư) được báo cáo riêng, "
                 f"không tính vào quy tắc chặn \"sổ không cân\"." if opening is not None and len(opening) else "")
    text = f"""# Báo cáo đánh giá chấp nhận khách hàng kiểm toán

**Khách hàng:** {res.client.name} | **Ngành:** {res.client.industry} | **Kỳ:** {res.client.period_start} đến {res.client.period_end}

## 1. Kết luận
- Điểm rủi ro: **{a.total:.1f}/100**
- Kết luận: **{a.decision.vi}**
- Quy tắc chặn: {'; '.join(a.knocked) or 'không kích hoạt'}

Lý do chính:
{chr(10).join('- ' + r for r in res.reasons)}

Điều kiện / hành động đề xuất:
{chr(10).join('- ' + c for c in res.conditions) or '- Lập kế hoạch kiểm toán thông thường'}

## 2. Điểm theo nhóm
{md_table(factors)}

## 3. Toàn vẹn dữ liệu
{res.integrity.comment}
{res.balance_note}

{open_note}

{md_table(res.integrity.summary)}

{recon}

## 4. Mức trọng yếu
{md_table(m.to_frame())}

Lý do chọn tiêu chí `{m.benchmark}`: {m.reason}

## 5. Kiểm tra bút toán
{md_table(res.je_summary)}

10 phát hiện rủi ro cao nhất:
{md_table(top) if len(top) else 'Không có.'}

Kiểm định Benford (MAD Nigrini: <0.006 chặt, <0.012 chấp nhận, <0.015 biên, còn lại không phù hợp; chi2 tới hạn 15.507):
{md_table(benford_frames(res)[0])}

## 6. Chỉ số tài chính
{md_table(_ratio_frame(res))}

Lưu ý: tài khoản lưỡng tính (131, 331...) được trình bày theo số dư thuần theo tài khoản. Chênh lệch BCĐKT: {st.bs['difference']:,.0f}.

## 7. Phân tích độ nhạy (±20%)
{md_table(res.sensitivity)}

Kết luận cuối có đổi trong {int(res.sensitivity['doi_ket_luan'].sum())}/{len(res.sensitivity)} kịch bản.
Kết luận chỉ theo điểm (bỏ quy tắc chặn) có đổi trong {int(res.sensitivity['doi_theo_diem'].sum())}/{len(res.sensitivity)} kịch bản.
Quy tắc chặn giữ kết luận cuối ở mức tối thiểu "Chấp nhận có điều kiện" nên cột "theo điểm" mới cho thấy độ nhạy thật của điểm số.

## 8. Giả định
- Yếu tố định tính do nhóm tự đánh giá: {dict(res.client.qualitative)} (0 = rủi ro thấp, 100 = cao).
- Ngưỡng chỉ số trong `config/benchmarks.json` là ngưỡng kinh nghiệm, cần thay bằng số liệu ngành có nguồn.
- Danh sách ngày lễ trong `config/params.json` cần được kiểm tra lại.
- Chứng từ số dư đầu kỳ nhận diện theo tiền tố trong `opening_prefixes` và ngày ghi sổ = ngày đầu kỳ.
- Tài khoản 131/331 trình bày theo số dư thuần; bút toán kết chuyển cuối kỳ bị loại khỏi doanh thu/chi phí bằng `flag_closing`.

## 9. Hạn chế dữ liệu
| Hạn chế | Ảnh hưởng |
|---|---|
| Sổ không có giờ nhập và người lập | JE05, JE10 bỏ qua; biểu đồ 04, 05 dùng thay thế (thứ trong tuần x tháng; tiền tố số chứng từ) |
| Cột TK đối ứng gần như trống | JE09 yếu |
| Chỉ có dữ liệu 1 năm | Không phân tích xu hướng, không tính Beneish M-score; số dư đầu kỳ lấy từ sổ và bảng CĐSPS |
| Số chứng từ có nhiều định dạng | JE03 chỉ kiểm tra định dạng "chuỗi + YYMM + số thứ tự"; dòng thiếu số chứng từ gộp chung |
| Tên và ngành khách hàng chưa có | Dùng tên giả định; benchmark ngành chưa có nguồn |
"""
    path = out / "report.md"
    path.write_text(text, encoding="utf-8")
    return path


def export_all(res: Result, lines: pd.DataFrame, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    integ = res.integrity
    write_excel(out / "01_data_integrity.xlsx",
                {"tom_tat": integ.summary, **{k: v for k, v in integ.details.items() if len(v)},
                 "nhan_xet": pd.DataFrame({"nhan_xet": [integ.comment, res.balance_note]})})
    by_code: dict[str, list[Finding]] = {t.code: [] for t in res.tests}
    for f in res.findings:
        by_code[f.ma_thu_tuc].append(f)
    write_excel(out / "02_je_findings.xlsx",
                {"tong_hop": res.je_summary, "benford": benford_frames(res)[0], "benford_tan_suat": benford_frames(res)[1],
                 **{c: pd.DataFrame([f.row() for f in fs]) for c, fs in by_code.items() if fs}})
    st = res.statements
    tb = res.tb.table.reset_index(names="tk")
    write_excel(out / "03_statements.xlsx",
                {"CDSPS": tb, "BCDKT": st.bs.to_frame(), "KQKD": st.income.to_frame(),
                 "theo_thang": st.monthly.reset_index(names="thang"), "phan_tich_thang": res.month_flags.reset_index(names="thang")})
    write_excel(out / "04_ratios_materiality.xlsx",
                {"chi_so": _ratio_frame(res), "trong_yeu": res.materiality.to_frame()})
    a = res.assessment
    write_excel(out / "05_acceptance.xlsx",
                {"diem": pd.DataFrame({"nhom": list(a.scores), "diem": list(a.scores.values()),
                                       "trong_so": [a.weights[k] for k in a.scores]}),
                 "ket_luan": pd.DataFrame({"ket_luan": [a.decision.vi, f"{a.total:.1f}"] + list(a.knocked)}),
                 "do_nhay": res.sensitivity, "audit_trail": pd.DataFrame(TRAIL)})
    write_charts(res, lines, out)
    write_report(res, out)
