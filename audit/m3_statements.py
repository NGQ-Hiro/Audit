"""Module 3 (phần 2): lập BCĐKT và BCKQKD rút gọn từ Bảng cân đối số phát sinh.
Không có số hiệu tài khoản nào viết cứng: tất cả nằm trong file ánh xạ (config/account_map_*.json).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from itertools import accumulate
from types import MappingProxyType
from typing import Mapping, Sequence

import pandas as pd

from .m3_ledger import GeneralLedger, TrialBalance


def tag(tks: Sequence[str], items: Mapping[str, Sequence[str]]) -> list:
    """Gán mỗi tài khoản vào một chỉ tiêu BCTC. Nếu nhiều tiền tố cùng khớp thì chọn tiền tố DÀI NHẤT
    (ví dụ TK 1112 khớp "111" và "1112" -> chọn "1112"). Không khớp thì trả về None."""
    rules = sorted(((p, k) for k, ps in items.items() for p in ps), key=lambda r: -len(r[0]))  # tiền tố dài trước
    return [next((k for p, k in rules if t.startswith(p)), None) for t in tks]


def sum_items(values: pd.Series, items: Mapping[str, Sequence[str]]) -> dict[str, float]:
    """Cộng số dư của các tài khoản theo chỉ tiêu. Chỉ tiêu không có tài khoản nào thì bằng 0."""
    sums = values.groupby(tag(list(values.index), items)).sum()
    return {k: float(sums.get(k, 0.0)) for k in items}


class FinancialStatement(ABC):
    """Báo cáo tài chính: một dict chỉ đọc (chỉ tiêu -> số tiền) cộng với bố cục để hiển thị."""
    layout: tuple[tuple[str, str], ...]  # (khóa, nhãn tiếng Việt) theo thứ tự hiển thị

    def __init__(self, cfg: Mapping, source):
        self._cfg = cfg
        self.values: Mapping[str, float] = MappingProxyType(self.build(source))  # chỉ đọc

    @abstractmethod
    def build(self, source) -> dict[str, float]: ...

    def __getitem__(self, key: str) -> float:
        """statement["cash"] -> số tiền của chỉ tiêu."""
        return self.values[key]

    def to_frame(self) -> pd.DataFrame:
        """Bảng hai cột (chỉ tiêu, số tiền) để ghi ra Excel."""
        return pd.DataFrame([(label, self.values[k]) for k, label in self.layout], columns=["chi_tieu", "so_tien"])


class BalanceSheet(FinancialStatement):
    """Bảng cân đối kế toán rút gọn. Đầu vào: số dư Nợ ròng theo tài khoản (Series)."""
    layout = (("cash", "Tiền và tương đương tiền"), ("receivables", "Phải thu"), ("inventory", "Hàng tồn kho"),
              ("other_current_assets", "TSNH khác"), ("current_assets", "Tổng tài sản ngắn hạn"),
              ("fixed_assets", "TSCĐ (thuần)"), ("other_noncurrent_assets", "TSDH khác"),
              ("total_assets", "TỔNG TÀI SẢN"), ("current_liabilities", "Nợ ngắn hạn"),
              ("long_term_debt", "Nợ dài hạn"), ("equity", "Vốn chủ sở hữu"),
              ("total_funding", "TỔNG NGUỒN VỐN"), ("difference", "Chênh lệch (TS - NV)"))

    def build(self, nd: pd.Series) -> dict[str, float]:
        c = self._cfg
        cls = nd.index.str[:1]  # loại tài khoản = chữ số đầu
        # Tài sản: số dư Nợ ròng của TK loại tài sản. Nguồn vốn: đổi dấu (số dư Có thành số dương)
        assets = sum_items(nd[cls.isin(c["asset_classes"])], c["balance_sheet"]["assets"])
        funding = sum_items(-nd[cls.isin(c["funding_classes"])], c["balance_sheet"]["funding"])
        unclosed = float(-nd[cls.isin(c["pl_classes"])].sum())  # lãi lỗ chưa kết chuyển sang 421
        v = {**assets, **funding, "unclosed_profit": unclosed}
        v["current_assets"] = sum(v[k] for k in ("cash", "receivables", "inventory", "other_current_assets"))
        v["total_assets"] = v["current_assets"] + v["fixed_assets"] + v["other_noncurrent_assets"]
        v["current_liabilities"] = v["payables"] + v["short_term_other"]
        v["retained_total"] = v["retained"] + unclosed  # lợi nhuận giữ lại + lãi lỗ chưa kết chuyển
        v["equity"] = v["retained_total"] + v["equity_other"]
        v["liabilities"] = v["current_liabilities"] + v["long_term_debt"]
        v["total_funding"] = v["liabilities"] + v["equity"]
        v["difference"] = v["total_assets"] - v["total_funding"]  # phải bằng 0 (hoặc rất nhỏ do làm tròn)
        return v


class IncomeStatement(FinancialStatement):
    """Báo cáo kết quả kinh doanh rút gọn. Đầu vào: các dòng sổ (đã loại chứng từ kết chuyển)."""
    layout = (("net_revenue", "Doanh thu thuần"), ("cogs", "Giá vốn hàng bán"), ("gross_profit", "Lợi nhuận gộp"),
              ("selling", "Chi phí bán hàng"), ("admin", "Chi phí QLDN"), ("fin_income", "Doanh thu tài chính"),
              ("fin_expense", "Chi phí tài chính"), ("other_profit", "Lợi nhuận khác"),
              ("pbt", "Lợi nhuận trước thuế"), ("tax", "Thuế TNDN"), ("net_profit", "Lợi nhuận sau thuế"))

    def build(self, lines: pd.DataFrame) -> dict[str, float]:
        pl = lines[~lines["kc"]]  # bỏ bút toán kết chuyển (nếu không, TK loại 5–8 bằng 0)
        net = (pl["co"] - pl["no"]).groupby(pl["tk"]).sum()  # số ròng theo Có: doanh thu dương, chi phí âm
        inc = self._cfg["income"]
        sums = sum_items(net, {k: v["prefixes"] for k, v in inc.items()})
        # bên Có giữ nguyên dấu; bên Nợ (chi phí) đổi dấu cho thành số dương
        v = {k: s if inc[k]["side"] == "credit" else -s for k, s in sums.items()}
        interest = -sum_items(net, {"i": self._cfg["interest_prefixes"]})["i"]  # chi phí lãi vay
        v["net_revenue"] = v["revenue_gross"] - v["deductions"]
        v["gross_profit"] = v["net_revenue"] - v["cogs"]
        v["other_profit"] = v["other_income"] - v["other_expense"]
        v["pbt"] = (v["gross_profit"] - v["selling"] - v["admin"] + v["fin_income"] - v["fin_expense"]
                    + v["other_profit"])
        v["net_profit"] = v["pbt"] - v["tax"]
        v["interest"] = interest
        v["ebit"] = v["pbt"] + interest  # EBIT = lợi nhuận trước thuế + lãi vay
        v["depreciation"] = sum_items(net, {"d": self._cfg["depreciation_prefixes"]})["d"]  # phát sinh Có TK 214
        return v


@dataclass(frozen=True)
class Statements:
    """Gói kết quả Module 3: BCĐKT cuối kỳ, BCĐKT đầu kỳ, BCKQKD, bảng số liệu theo tháng."""
    bs: BalanceSheet
    bs_open: BalanceSheet
    income: IncomeStatement
    monthly: pd.DataFrame


def monthly_table(lines: pd.DataFrame, cash_open: float, cfg: Mapping, months: pd.PeriodIndex) -> pd.DataFrame:
    """Bảng theo tháng: doanh thu, giá vốn, lợi nhuận gộp, chi phí, biên gộp, tiền cuối tháng
    (đã loại chứng từ kết chuyển). Dùng cho thủ tục phân tích xu hướng."""
    pl = lines[~lines["kc"]]
    items = {k: v["prefixes"] for k, v in cfg["income"].items()}
    keys = pd.Series(tag(list(pl["tk"]), items), index=pl.index)  # chỉ tiêu của từng dòng
    # bảng: dòng = tháng, cột = chỉ tiêu; tháng không có dữ liệu thì bằng 0
    net = ((pl["co"] - pl["no"]).groupby([pl["ngay_ghi_so"].dt.to_period("M"), keys]).sum()
           .unstack(fill_value=0).reindex(index=months, columns=list(items), fill_value=0))
    cash = lines[lines["tk"].str.startswith(tuple(cfg["cash_prefixes"]))]
    flow = (cash["no"] - cash["co"]).groupby(cash["ngay_ghi_so"].dt.to_period("M")).sum()  # dòng tiền ròng mỗi tháng
    flow = flow.reindex(months, fill_value=0)
    revenue = net["revenue_gross"] + net["deductions"]
    cogs = -net["cogs"]
    out = pd.DataFrame({"revenue": revenue, "cogs": cogs, "gross_profit": revenue - cogs,
                        "opex": -(net["selling"] + net["admin"]),
                        # accumulate: tiền cuối tháng = tiền đầu kỳ + cộng dồn dòng tiền; [1:] bỏ giá trị đầu (chính là tiền đầu kỳ)
                        "cash_end": list(accumulate(flow, initial=cash_open))[1:]})
    out["gross_margin"] = out["gross_profit"] / out["revenue"].where(out["revenue"] != 0)  # tháng doanh thu 0 -> NaN
    out.index = months.astype(str)
    return out


def build_statements(ledger: GeneralLedger, tb: TrialBalance, cfg: Mapping,
                     start: str, end: str) -> Statements:
    """Lập đủ bộ: BCĐKT đầu kỳ, BCĐKT cuối kỳ, BCKQKD và bảng theo tháng."""
    lines = ledger.data
    bs_open = BalanceSheet(cfg, tb.net_debit("dau"))
    months = pd.period_range(start, end, freq="M")
    return Statements(BalanceSheet(cfg, tb.net_debit("cuoi")), bs_open, IncomeStatement(cfg, lines),
                      monthly_table(lines, bs_open["cash"], cfg, months))
