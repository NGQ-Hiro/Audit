"""Module 1 (phần kiểm tra): bảng tóm tắt toàn vẹn dữ liệu.

Câu hỏi của kiểm toán viên: "Dữ liệu khách hàng gửi có đủ tin cậy để làm bằng chứng không?"
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import pandas as pd


@dataclass(frozen=True)
class IntegrityReport:
    """Kết quả kiểm tra toàn vẹn."""
    summary: pd.DataFrame               # bảng tóm tắt: chỉ tiêu, giá trị, đánh giá (Đạt / Cần chú ý)
    details: Mapping[str, pd.DataFrame]  # chi tiết từng lỗi (mỗi lỗi một bảng, thành một sheet Excel)
    metrics: Mapping[str, float]         # số liệu để module 7 chấm điểm
    comment: str                         # nhận xét một câu về độ tin cậy


def check_integrity(df: pd.DataFrame, client, catalog: set[str], params: Mapping,
                    client_tb: pd.DataFrame | None) -> IntegrityReport:
    """df là bảng đã làm sạch nhưng CHƯA bỏ dòng lỗi (để còn đếm được lỗi).
    catalog: danh mục tài khoản hợp lệ. client_tb: bảng CĐPS của khách hàng (có thể None)."""
    n = len(df)
    no, co = df["no"].fillna(0), df["co"].fillna(0)
    start, end = pd.Timestamp(client.period_start), pd.Timestamp(client.period_end)
    tol = params["balance_tolerance"]  # sai số làm tròn cho phép khi so Nợ với Có

    # 1) Chứng từ không cân: tổng Nợ - tổng Có của từng chứng từ phải bằng 0
    voucher_diff = (no - co).groupby(df["so_ct"]).sum()
    all_unbalanced = voucher_diff[voucher_diff.abs() > tol]
    # Chứng từ số dư đầu kỳ (OD, NKO...) ghi ngày đầu kỳ và lệch một vế theo thiết kế: báo cáo riêng
    first_day = df.groupby("so_ct")["ngay_ghi_so"].min() == start
    is_open = all_unbalanced.index.to_series().str.match("^(?:" + "|".join(params.get("opening_prefixes", ["^$"])) + r")\d") \
        & first_day.reindex(all_unbalanced.index).fillna(False)
    opening_unbal, unbalanced = all_unbalanced[is_open], all_unbalanced[~is_open]

    # 2) Các lỗi theo dòng
    unknown = df[(df["tk"] != "") & ~df["tk"].str[:3].isin(catalog)]  # tài khoản ngoài danh mục (so 3 số đầu)
    missing = df[df["ngay_ghi_so"].isna() | (df["tk"] == "") | (df["no"].isna() & df["co"].isna())]  # thiếu ngày/TK/số tiền
    negative = df[(df["no"] < 0) | (df["co"] < 0)]  # số tiền âm
    zero = df[(df["no"] == 0) & (df["co"] == 0)]    # số tiền bằng 0
    outside = df[df["ngay_ghi_so"].notna() & ((df["ngay_ghi_so"] < start) | (df["ngay_ghi_so"] > end))]  # ngoài kỳ
    lag = (df["ngay_ghi_so"] - df["ngay_ct"]).abs().dt.days  # số ngày lệch giữa ngày ghi sổ và ngày chứng từ
    late = df[lag > params["max_post_lag_days"]]

    # 3) Tháng nào trong kỳ không có dòng dữ liệu nào?
    expected = pd.period_range(start, end, freq="M")
    present = df["ngay_ghi_so"].dropna().dt.to_period("M").unique()
    missing_months = [str(m) for m in expected if m not in present]

    details = {"chung_tu_khong_can": unbalanced.rename("chenh_lech").reset_index(),
               "chung_tu_so_du_dau_ky": opening_unbal.rename("chenh_lech").reset_index(),
               "tk_ngoai_danh_muc": unknown.groupby("tk").size().rename("so_dong").reset_index(),
               "dong_thieu_thong_tin": missing, "so_tien_am": negative, "so_tien_bang_0": zero,
               "ngoai_ky": outside, "lech_ngay_ct": late}

    # 4) Đối chiếu tổng phát sinh từng tài khoản với bảng CĐPS của khách hàng
    tb_diff = 0.0
    if client_tb is not None:
        mine = df.assign(no=no, co=co).groupby("tk")[["no", "co"]].sum()       # số của mình (từ sổ)
        theirs = client_tb.set_index("tk")[["ps_no", "ps_co"]]                 # số của khách hàng
        diff = mine.join(theirs, how="outer").fillna(0)
        diff["lech_no"], diff["lech_co"] = diff["no"] - diff["ps_no"], diff["co"] - diff["ps_co"]
        bad = diff[(diff["lech_no"].abs() > params["tb_tolerance"]) | (diff["lech_co"].abs() > params["tb_tolerance"])]
        details["lech_so_voi_khach_hang"] = bad.reset_index()
        tb_diff = float(bad[["lech_no", "lech_co"]].abs().max(axis=1).sum())

    # Số liệu cho module 7 (AcceptanceEngine) chấm điểm
    metrics = {"unbalanced_docs": len(unbalanced), "unbalanced_amount": float(unbalanced.abs().sum()),
               "opening_unbalanced_docs": len(opening_unbal), "opening_unbalanced_amount": float(opening_unbal.abs().sum()),
               "missing_months": len(missing_months), "unknown_ratio": len(unknown) / max(n, 1),
               "missing_ratio": len(missing) / max(n, 1), "out_period_ratio": len(outside) / max(n, 1),
               "tb_mismatch_amount": tb_diff}

    # Bảng tóm tắt: mỗi dòng là (chỉ tiêu, giá trị, có vấn đề không). True = Cần chú ý.
    rows = [("Số dòng", n, False), ("Số chứng từ", df["so_ct"].nunique(), False),
            ("Từ ngày", str(df["ngay_ghi_so"].min().date()), False),
            ("Đến ngày", str(df["ngay_ghi_so"].max().date()), False),
            ("Số tháng thiếu dữ liệu", len(missing_months), bool(missing_months)),
            ("Tổng phát sinh Nợ", float(no.sum()), False), ("Tổng phát sinh Có", float(co.sum()), False),
            ("Chênh lệch Nợ - Có toàn sổ", float(no.sum() - co.sum()), abs(no.sum() - co.sum()) > tol),
            ("Chứng từ không cân (không tính bút toán số dư đầu kỳ)", len(unbalanced), len(unbalanced) > 0),
            ("Chứng từ số dư đầu kỳ lệch một vế (OD, NKO, OI, OV; ghi ngày đầu kỳ)", len(opening_unbal), False),
            ("Dòng có TK ngoài danh mục", len(unknown), len(unknown) > 0),
            ("Dòng thiếu ngày/TK/số tiền", len(missing), len(missing) > 0),
            ("Dòng thiếu số chứng từ", int((df["so_ct"] == "").sum()), bool((df["so_ct"] == "").any())),
            ("Dòng số tiền âm", len(negative), len(negative) > 0),
            ("Dòng số tiền bằng 0", len(zero), len(zero) > 0),
            ("Dòng ghi sổ ngoài kỳ kế toán", len(outside), len(outside) > 0),
            (f"Dòng ngày ghi sổ lệch ngày CT > {params['max_post_lag_days']} ngày", len(late), len(late) > 0),
            ("Tài khoản lệch so với bảng CĐSPS của khách hàng",
             len(details.get("lech_so_voi_khach_hang", [])), tb_diff > 0)]
    summary = pd.DataFrame([(a, b, "Cần chú ý" if bad else "Đạt") for a, b, bad in rows],
                           columns=["chi_tieu", "gia_tri", "danh_gia"])
    # Độ tin cậy: càng nhiều chỉ tiêu "Cần chú ý" thì càng thấp (<=1 cao, <=4 trung bình, còn lại thấp)
    failed = int((summary["danh_gia"] == "Cần chú ý").sum())
    level = "cao" if failed <= 1 else "trung bình" if failed <= 4 else "thấp"
    comment = (f"Có {failed}/{len(summary)} chỉ tiêu cần chú ý"
               + (f"; thiếu tháng: {', '.join(missing_months)}" if missing_months else "")
               + f". Mức độ tin cậy của dữ liệu: {level}.")
    return IntegrityReport(summary, details, metrics, comment)
