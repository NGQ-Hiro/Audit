"""Module 4 (phần chỉ số): chỉ số tài chính.
Mỗi chỉ số là một hàm thuần: nhận dict số liệu f, trả về số (hoặc None nếu không tính được).
Gắn @register_ratio để tự đăng ký vào RATIOS (mẫu Registry). Thêm chỉ số mới = thêm một hàm.
"""
from __future__ import annotations

import logging
from typing import Callable, Mapping

from .models import RatioResult

log = logging.getLogger("audit")
RATIOS: dict[str, tuple[Callable, str, str]] = {}  # mã chỉ số -> (hàm tính, tên, nhóm)


def register_ratio(key: str, name: str, group: str):
    """Decorator: đăng ký hàm tính chỉ số vào RATIOS."""
    def deco(fn):
        RATIOS[key] = (fn, name, group)
        return fn
    return deco


def safe_div(a, b):
    """Chia an toàn: trả None nếu thiếu số hoặc mẫu bằng 0 (không làm chương trình dừng)."""
    return None if a is None or b is None or b == 0 else a / b


def avg(f: Mapping, key: str) -> float:
    """Số bình quân = (cuối kỳ + đầu kỳ) / 2. Số đầu kỳ nằm ở khóa 'tên_open'."""
    return (f[key] + f[f"{key}_open"]) / 2


def figures(st, days: int) -> dict[str, float]:
    """Gom số liệu cuối kỳ, đầu kỳ (hậu tố _open) và kết quả kinh doanh vào một dict phẳng cho các chỉ số."""
    keys = ("cash", "receivables", "inventory", "payables", "current_assets", "current_liabilities",
            "total_assets", "liabilities", "equity", "retained_total")
    inc = ("net_revenue", "cogs", "gross_profit", "net_profit", "ebit", "interest", "depreciation")
    return {"days": days, **{k: st.bs[k] for k in keys}, **{f"{k}_open": st.bs_open[k] for k in keys},
            **{k: st.income[k] for k in inc}}


# ---- Thanh khoản
@register_ratio("current_ratio", "Hệ số thanh toán hiện hành", "Thanh khoản")
def current_ratio(f): return safe_div(f["current_assets"], f["current_liabilities"])  # TSNH / Nợ ngắn hạn


@register_ratio("quick_ratio", "Hệ số thanh toán nhanh", "Thanh khoản")
def quick_ratio(f): return safe_div(f["current_assets"] - f["inventory"], f["current_liabilities"])  # (TSNH - HTK) / Nợ NH


@register_ratio("cash_ratio", "Hệ số thanh toán tiền mặt", "Thanh khoản")
def cash_ratio(f): return safe_div(f["cash"], f["current_liabilities"])  # Tiền / Nợ ngắn hạn


# ---- Cơ cấu vốn
@register_ratio("debt_to_assets", "Nợ phải trả / Tổng tài sản", "Cơ cấu vốn")
def debt_to_assets(f): return safe_div(f["liabilities"], f["total_assets"])


@register_ratio("debt_to_equity", "Nợ phải trả / Vốn chủ sở hữu (D/E)", "Cơ cấu vốn")
def debt_to_equity(f): return safe_div(f["liabilities"], f["equity"])


@register_ratio("interest_coverage", "Khả năng trả lãi vay (EBIT / lãi vay)", "Cơ cấu vốn")
def interest_coverage(f): return safe_div(f["ebit"], f["interest"])


# ---- Hiệu quả hoạt động
@register_ratio("dso", "Số ngày thu tiền (DSO)", "Hiệu quả hoạt động")
def dso(f):
    """DSO = số ngày / vòng quay phải thu; vòng quay = doanh thu thuần / phải thu bình quân."""
    turnover = safe_div(f["net_revenue"], avg(f, "receivables"))
    return safe_div(f["days"], turnover)


@register_ratio("dio", "Số ngày tồn kho (DIO)", "Hiệu quả hoạt động")
def dio(f):
    """DIO = số ngày / vòng quay hàng tồn kho; vòng quay = giá vốn / HTK bình quân."""
    turnover = safe_div(f["cogs"], avg(f, "inventory"))
    return safe_div(f["days"], turnover)


@register_ratio("dpo", "Số ngày phải trả (DPO)", "Hiệu quả hoạt động")
def dpo(f):
    """DPO = phải trả người bán bình quân / giá vốn x số ngày."""
    ratio = safe_div(avg(f, "payables"), f["cogs"])
    return None if ratio is None else ratio * f["days"]


@register_ratio("ccc", "Chu kỳ chuyển đổi tiền mặt (CCC)", "Hiệu quả hoạt động")
def ccc(f):
    """CCC = DSO + DIO - DPO. Thiếu một thành phần thì không tính (None)."""
    parts = (dso(f), dio(f), dpo(f))
    return None if None in parts else parts[0] + parts[1] - parts[2]


@register_ratio("asset_turnover", "Vòng quay tổng tài sản", "Hiệu quả hoạt động")
def asset_turnover(f): return safe_div(f["net_revenue"], avg(f, "total_assets"))


# ---- Khả năng sinh lời
@register_ratio("gross_margin", "Biên lợi nhuận gộp", "Khả năng sinh lời")
def gross_margin(f): return safe_div(f["gross_profit"], f["net_revenue"])


@register_ratio("net_margin", "Biên lợi nhuận ròng", "Khả năng sinh lời")
def net_margin(f): return safe_div(f["net_profit"], f["net_revenue"])


@register_ratio("roa", "ROA", "Khả năng sinh lời")
def roa(f): return safe_div(f["net_profit"], avg(f, "total_assets"))  # LNST / tài sản bình quân


@register_ratio("roe", "ROE", "Khả năng sinh lời")
def roe(f): return safe_div(f["net_profit"], avg(f, "equity"))  # LNST / vốn chủ sở hữu bình quân


# ---- Chỉ số cảnh báo
@register_ratio("altman_z", "Altman Z'' (không có hằng số)", "Cảnh báo")
def altman_z(f):
    """Z'' = 6.56*X1 + 3.26*X2 + 6.72*X3 + 1.05*X4. Trên 2.6 an toàn, 1.1–2.6 vùng xám, dưới 1.1 nguy hiểm.
    X1 = vốn lưu động / TTS; X2 = lợi nhuận giữ lại / TTS; X3 = EBIT / TTS; X4 = vốn chủ sở hữu / nợ phải trả."""
    ta = f["total_assets"]
    x = (safe_div(f["current_assets"] - f["current_liabilities"], ta), safe_div(f["retained_total"], ta),
         safe_div(f["ebit"], ta), safe_div(f["equity"], f["liabilities"]))
    return None if None in x else 6.56 * x[0] + 3.26 * x[1] + 6.72 * x[2] + 1.05 * x[3]


@register_ratio("accruals", "Tỷ lệ dồn tích (accruals)", "Cảnh báo")
def accruals(f):
    """Dồn tích = (LNST - CFO) / tài sản bình quân. Dòng tiền CFO là số ƯỚC TÍNH (phương pháp gián tiếp):
    CFO = LNST + khấu hao - tăng phải thu - tăng hàng tồn kho + tăng phải trả."""
    cfo = (f["net_profit"] + f["depreciation"] - (f["receivables"] - f["receivables_open"])
           - (f["inventory"] - f["inventory_open"]) + (f["payables"] - f["payables_open"]))
    return safe_div(f["net_profit"] - cfo, avg(f, "total_assets"))


def label(value, bench: Mapping | None) -> str:
    """Gắn nhãn Tốt / Cần chú ý / Rủi ro bằng cách so với ngưỡng trong config/benchmarks.json.
    higher_is_better = True: số càng cao càng tốt (ví dụ thanh khoản); False: số càng thấp càng tốt (ví dụ nợ / TTS)."""
    if value is None:
        return "Không tính được"
    if not bench:
        return "Tham khảo"  # không có ngưỡng để so
    good, risk = bench["good"], bench["risk"]
    if bench["higher_is_better"]:
        return "Tốt" if value >= good else "Rủi ro" if value < risk else "Cần chú ý"
    return "Tốt" if value <= good else "Rủi ro" if value > risk else "Cần chú ý"


def compute_ratios(f: Mapping, benchmarks: Mapping) -> list[RatioResult]:
    """Tính mọi chỉ số đã đăng ký. Chỉ số không tính được thì ghi chú và cảnh báo, không dừng chương trình."""
    out = []
    for key, (fn, name, group) in RATIOS.items():
        value = fn(f)
        note = ""
        if value is None:
            note = "Chia cho 0 hoặc thiếu dữ liệu"
            log.warning("Ratio %s not computable: %s", key, note)
        out.append(RatioResult(key, name, group, value, label(value, benchmarks.get(key)), note))
    return out
