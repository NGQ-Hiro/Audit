"""Monthly analytical procedures (VSA 520)."""
from __future__ import annotations

import pandas as pd


def zscore(s: pd.Series) -> pd.Series:
    std = s.std(ddof=0)
    return (s - s.mean()) / std if std else s * float("nan")


def flag_months(monthly: pd.DataFrame, k: float = 2.0) -> pd.DataFrame:
    """Flag months whose revenue or gross margin is beyond +-k standard deviations."""
    out = pd.DataFrame({"doanh_thu": monthly["revenue"], "bien_loi_nhuan_gop": monthly["gross_margin"],
                        "bien_dong_doanh_thu": monthly["revenue"].pct_change(),
                        "z_doanh_thu": zscore(monthly["revenue"]),
                        "z_bien_gop": zscore(monthly["gross_margin"])})
    out["bat_thuong"] = (out["z_doanh_thu"].abs() > k) | (out["z_bien_gop"].abs() > k)
    out["goi_y"] = [("Cần giải thích: " + ", ".join(
        f"{n} lệch {z:+.1f} độ lệch chuẩn" for n, z in (("doanh thu", r.z_doanh_thu), ("biên gộp", r.z_bien_gop))
        if abs(z) > k)) if r.bat_thuong else "" for r in out.itertuples()]
    out["giai_thich_cua_nhom"] = ""  # the team writes the explanation here
    return out
