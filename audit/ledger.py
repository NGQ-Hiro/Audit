"""GeneralLedger (read-only evidence) and TrialBalance."""
from __future__ import annotations

import operator
from functools import reduce
from itertools import groupby
from typing import Iterator

import pandas as pd

from .models import JournalLine, UnbalancedEntryError


def flag_closing(df: pd.DataFrame, accounts: tuple[str, ...]) -> pd.Series:
    """A voucher is a closing entry when any of its lines touches a closing account (911).

    Why: year-end transfers 5xx/6xx/7xx/8xx -> 911 -> 421 always pass through 911, so the
    whole voucher is excluded when we measure revenue and cost (else classes 5-8 sum to 0).
    """
    hit = df["tk"].str.startswith(accounts)
    return hit.groupby(df["so_ct"]).transform("any")


class GeneralLedger:
    """Journal lines. The original data is private; `data` returns a copy."""

    def __init__(self, df: pd.DataFrame, closing_accounts: tuple[str, ...]):
        df = df.reset_index(drop=True)
        self.__df = df.assign(kc=flag_closing(df, tuple(closing_accounts)))

    @property
    def data(self) -> pd.DataFrame:
        return self.__df.copy()

    def __len__(self) -> int:
        return len(self.__df)

    def __repr__(self) -> str:
        return f"GeneralLedger(lines={len(self)}, vouchers={self.__df['so_ct'].nunique()})"

    def __iter__(self) -> Iterator[JournalLine]:
        return (JournalLine(r.so_ct, r.ngay_ghi_so, r.tk, r.no, r.co, r.dien_giai, r.ma_doi_tuong, r.nguoi_lap)
                for r in self.__df.itertuples())

    def __getitem__(self, prefix: str) -> pd.DataFrame:
        """Sổ cái of one account (prefix match), in date order."""
        sub = self.__df[self.__df["tk"].str.startswith(prefix)]
        return sub.sort_values("ngay_ghi_so", kind="stable").reset_index(drop=True)

    def entries(self) -> Iterator[tuple[str, tuple[JournalLine, ...]]]:
        """Generator: vouchers (grouped by so_ct) with their lines."""
        for so_ct, lines in groupby(sorted(self, key=lambda l: l.so_ct), key=lambda l: l.so_ct):
            yield so_ct, tuple(lines)

    def assert_balanced(self, tol: float = 1.0) -> None:
        for so_ct, lines in self.entries():
            diff = sum(l.no for l in lines) - sum(l.co for l in lines)
            if abs(diff) > tol:
                raise UnbalancedEntryError(so_ct, diff)


def _sums(df: pd.DataFrame) -> pd.DataFrame:
    return df.groupby("tk")[["no", "co"]].sum().rename(columns={"no": "ps_no", "co": "ps_co"}).assign(dau=0.0)


class TrialBalance:
    """Bảng cân đối số phát sinh. Balances are net debit (debit +, credit -)."""

    def __init__(self, table: pd.DataFrame):
        self.__t = table[["dau", "ps_no", "ps_co"]].astype(float)

    @classmethod
    def from_ledger(cls, ledger: GeneralLedger, opening: pd.DataFrame) -> "TrialBalance":
        """Build one TrialBalance per month, then add them all onto the opening balances."""
        lines = ledger.data
        start = pd.DataFrame({"dau": (opening["du_no"] - opening["du_co"]).values,
                              "ps_no": 0.0, "ps_co": 0.0}, index=opening["tk"].values)
        months = [cls(_sums(g)) for _, g in lines.groupby(lines["ngay_ghi_so"].dt.to_period("M"))]
        return reduce(operator.add, months, cls(start))

    def __add__(self, other: "TrialBalance") -> "TrialBalance":
        return TrialBalance(self.__t.add(other.__t, fill_value=0.0))

    def __repr__(self) -> str:
        return f"TrialBalance(accounts={len(self.__t)}, debit={self.total_debit:,.0f}, credit={self.total_credit:,.0f})"

    @property
    def total_debit(self) -> float:
        return float(self.__t["ps_no"].sum())

    @property
    def total_credit(self) -> float:
        return float(self.__t["ps_co"].sum())

    @property
    def table(self) -> pd.DataFrame:
        t = self.__t.copy()
        return t.assign(cuoi=t["dau"] + t["ps_no"] - t["ps_co"]).sort_index()

    def net_debit(self, column: str = "cuoi") -> pd.Series:
        return self.table[column]
