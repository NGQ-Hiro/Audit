"""Preliminary materiality (VSA 320)."""
from __future__ import annotations

import logging
from typing import Mapping

import pandas as pd

log = logging.getLogger("audit")


class Materiality:
    def __init__(self, bases: Mapping[str, float], cfg: Mapping):
        self._cfg = cfg
        self.candidates = {k: self.round_amount(bases[k] * p) for k, p in cfg["pct"].items()}
        wanted = cfg["benchmark"]
        self.benchmark = wanted if bases[wanted] > 0 else "revenue"  # loss-making -> fall back to revenue
        if self.benchmark != wanted:
            log.warning("Benchmark %s is not positive, using %s", wanted, self.benchmark)
        self._bases = dict(bases)

    @classmethod
    def from_statements(cls, income, bs, cfg: Mapping) -> "Materiality":
        return cls({"pbt": income["pbt"], "revenue": income["net_revenue"], "assets": bs["total_assets"]}, cfg)

    @staticmethod
    def round_amount(x: float) -> float:
        """Round to 2 significant digits (materiality is a judgement, not a precise figure)."""
        return float(f"{x:.2g}")

    @property
    def overall(self) -> float:
        return self.candidates[self.benchmark]

    @property
    def performance(self) -> float:
        return self.round_amount(self.overall * self._cfg["performance_factor"])

    @property
    def trivial(self) -> float:
        return self.round_amount(self.overall * self._cfg["trivial_factor"])

    @property
    def reason(self) -> str:
        note = "" if self.benchmark == self._cfg["benchmark"] else f" (đã chuyển sang {self.benchmark} vì tiêu chí gốc không dương)"
        return self._cfg["reason"] + note

    def to_frame(self) -> pd.DataFrame:
        rows = [(k, self._bases[k], self._cfg["pct"][k], v, "x" if k == self.benchmark else "")
                for k, v in self.candidates.items()]
        rows += [("Mức trọng yếu thực hiện", "", self._cfg["performance_factor"], self.performance, ""),
                 ("Ngưỡng sai sót không đáng kể", "", self._cfg["trivial_factor"], self.trivial, "")]
        return pd.DataFrame(rows, columns=["tieu_chi", "co_so", "ty_le", "so_tien", "duoc_chon"])
