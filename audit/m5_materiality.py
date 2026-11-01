"""Module 5: mức trọng yếu sơ bộ (VSA 320).

Ba con số:
  - Mức trọng yếu tổng thể  = tỷ lệ % x một cơ sở (lợi nhuận trước thuế, doanh thu hoặc tổng tài sản)
  - Mức trọng yếu thực hiện = một phần của mức tổng thể (50%–75%); dùng làm ngưỡng lọc ở Module 2
  - Ngưỡng sai sót không đáng kể = phần nhỏ của mức tổng thể (3%–5%)
"""
from __future__ import annotations

import logging
from typing import Mapping

import pandas as pd

log = logging.getLogger("audit")


class Materiality:
    def __init__(self, bases: Mapping[str, float], cfg: Mapping):
        """bases: các cơ sở tính (pbt, revenue, assets). cfg: cấu hình (tỷ lệ %, tiêu chí chọn, hệ số)."""
        self._cfg = cfg
        # Số tiền ứng viên theo từng tiêu chí = cơ sở x tỷ lệ, làm tròn 2 chữ số có nghĩa
        self.candidates = {k: self.round_amount(bases[k] * p) for k, p in cfg["pct"].items()}
        wanted = cfg["benchmark"]  # tiêu chí được chọn trong config
        self.benchmark = wanted if bases[wanted] > 0 else "revenue"  # nếu lỗ (cơ sở không dương) thì chuyển sang doanh thu
        if self.benchmark != wanted:
            log.warning("Benchmark %s is not positive, using %s", wanted, self.benchmark)
        self._bases = dict(bases)

    @classmethod
    def from_statements(cls, income, bs, cfg: Mapping) -> "Materiality":
        """Tạo từ BCKQKD và BCĐKT đã lập ở Module 3."""
        return cls({"pbt": income["pbt"], "revenue": income["net_revenue"], "assets": bs["total_assets"]}, cfg)

    @staticmethod
    def round_amount(x: float) -> float:
        """Làm tròn còn 2 chữ số có nghĩa (mức trọng yếu là xét đoán, không cần chính xác từng đồng)."""
        return float(f"{x:.2g}")

    @property
    def overall(self) -> float:
        """Mức trọng yếu tổng thể (theo tiêu chí được chọn)."""
        return self.candidates[self.benchmark]

    @property
    def performance(self) -> float:
        """Mức trọng yếu thực hiện = tổng thể x performance_factor."""
        return self.round_amount(self.overall * self._cfg["performance_factor"])

    @property
    def trivial(self) -> float:
        """Ngưỡng sai sót không đáng kể = tổng thể x trivial_factor."""
        return self.round_amount(self.overall * self._cfg["trivial_factor"])

    @property
    def reason(self) -> str:
        """Lý do chọn tiêu chí (từ config), kèm ghi chú nếu phải đổi tiêu chí."""
        note = "" if self.benchmark == self._cfg["benchmark"] else f" (đã chuyển sang {self.benchmark} vì tiêu chí gốc không dương)"
        return self._cfg["reason"] + note

    def to_frame(self) -> pd.DataFrame:
        """Bảng để ghi ra Excel: các tiêu chí ứng viên (đánh dấu x ở tiêu chí được chọn) và 2 mức còn lại."""
        rows = [(k, self._bases[k], self._cfg["pct"][k], v, "x" if k == self.benchmark else "")
                for k, v in self.candidates.items()]
        rows += [("Mức trọng yếu thực hiện", "", self._cfg["performance_factor"], self.performance, ""),
                 ("Ngưỡng sai sót không đáng kể", "", self._cfg["trivial_factor"], self.trivial, "")]
        return pd.DataFrame(rows, columns=["tieu_chi", "co_so", "ty_le", "so_tien", "duoc_chon"])
