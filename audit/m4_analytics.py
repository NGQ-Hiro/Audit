"""Module 4 (phần phân tích theo tháng): thủ tục phân tích VSA 520."""
from __future__ import annotations

import pandas as pd


def zscore(s: pd.Series) -> pd.Series:
    """Z-score: mỗi giá trị cách trung bình bao nhiêu độ lệch chuẩn. z = (x - trung bình) / độ lệch chuẩn.
    Nếu mọi giá trị bằng nhau (độ lệch chuẩn = 0) thì trả về NaN, không chia cho 0."""
    std = s.std(ddof=0)
    return (s - s.mean()) / std if std else s * float("nan")


def flag_months(monthly: pd.DataFrame, k: float = 2.0) -> pd.DataFrame:
    """Đánh dấu tháng có doanh thu hoặc biên lợi nhuận gộp lệch quá ±k độ lệch chuẩn (mặc định k = 2).
    Tháng bị đánh dấu thì nhóm phải giải thích (cột giai_thich_cua_nhom)."""
    out = pd.DataFrame({"doanh_thu": monthly["revenue"], "bien_loi_nhuan_gop": monthly["gross_margin"],
                        "bien_dong_doanh_thu": monthly["revenue"].pct_change(),  # % thay đổi so với tháng trước
                        "z_doanh_thu": zscore(monthly["revenue"]),
                        "z_bien_gop": zscore(monthly["gross_margin"])})
    out["bat_thuong"] = (out["z_doanh_thu"].abs() > k) | (out["z_bien_gop"].abs() > k)
    # Gợi ý: nói rõ chỉ tiêu nào lệch và lệch bao nhiêu độ lệch chuẩn
    out["goi_y"] = [("Cần giải thích: " + ", ".join(
        f"{n} lệch {z:+.1f} độ lệch chuẩn" for n, z in (("doanh thu", r.z_doanh_thu), ("biên gộp", r.z_bien_gop))
        if abs(z) > k)) if r.bat_thuong else "" for r in out.itertuples()]
    out["giai_thich_cua_nhom"] = ""  # nhóm tự viết lời giải thích ở đây
    return out
