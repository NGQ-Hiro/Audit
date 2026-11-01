"""Module 3 (phần 1): Sổ cái (GeneralLedger, chỉ đọc) và Bảng cân đối số phát sinh (TrialBalance)."""
from __future__ import annotations

import operator
from functools import reduce
from itertools import groupby
from typing import Iterator

import pandas as pd

from .models import JournalLine, UnbalancedEntryError


def flag_closing(df: pd.DataFrame, accounts: tuple[str, ...]) -> pd.Series:
    """Đánh dấu bút toán KẾT CHUYỂN cuối kỳ: chứng từ có BẤT KỲ dòng nào ghi vào TK kết chuyển (911).

    Vì sao: cuối năm kế toán chuyển 5xx/6xx/7xx/8xx -> 911 -> 421, nên bút toán nào cũng đi qua 911.
    Ta loại cả chứng từ đó khi tính doanh thu, chi phí. Nếu không loại, TK loại 5–8 sẽ có số dư bằng 0.
    """
    hit = df["tk"].str.startswith(accounts)           # dòng nào ghi vào TK kết chuyển
    return hit.groupby(df["so_ct"]).transform("any")  # nếu một dòng trúng thì cả chứng từ là kết chuyển


class GeneralLedger:
    """Các dòng bút toán. Dữ liệu gốc là private; thuộc tính `data` chỉ trả về BẢN SAO,
    nên không ai sửa được bằng chứng gốc."""

    def __init__(self, df: pd.DataFrame, closing_accounts: tuple[str, ...]):
        df = df.reset_index(drop=True)
        # thêm cột kc (True = bút toán kết chuyển)
        self.__df = df.assign(kc=flag_closing(df, tuple(closing_accounts)))

    @property
    def data(self) -> pd.DataFrame:
        return self.__df.copy()

    def __len__(self) -> int:
        """len(ledger) = số dòng."""
        return len(self.__df)

    def __repr__(self) -> str:
        return f"GeneralLedger(lines={len(self)}, vouchers={self.__df['so_ct'].nunique()})"

    def __iter__(self) -> Iterator[JournalLine]:
        """for line in ledger: duyệt từng dòng, mỗi dòng là một JournalLine (không sửa được)."""
        return (JournalLine(r.so_ct, r.ngay_ghi_so, r.tk, r.no, r.co, r.dien_giai, r.ma_doi_tuong, r.nguoi_lap)
                for r in self.__df.itertuples())

    def __getitem__(self, prefix: str) -> pd.DataFrame:
        """ledger["511"]: Sổ cái của một tài khoản (khớp theo tiền tố), sắp theo ngày."""
        sub = self.__df[self.__df["tk"].str.startswith(prefix)]
        return sub.sort_values("ngay_ghi_so", kind="stable").reset_index(drop=True)

    def entries(self) -> Iterator[tuple[str, tuple[JournalLine, ...]]]:
        """Generator: trả về từng chứng từ (nhóm theo số CT) cùng các dòng của nó."""
        for so_ct, lines in groupby(sorted(self, key=lambda l: l.so_ct), key=lambda l: l.so_ct):
            yield so_ct, tuple(lines)

    def assert_balanced(self, tol: float = 1.0) -> None:
        """Báo UnbalancedEntryError ở chứng từ đầu tiên có Nợ khác Có quá sai số tol."""
        for so_ct, lines in self.entries():
            diff = sum(l.no for l in lines) - sum(l.co for l in lines)
            if abs(diff) > tol:
                raise UnbalancedEntryError(so_ct, diff)


def _sums(df: pd.DataFrame) -> pd.DataFrame:
    """Tổng phát sinh Nợ, Có theo tài khoản; số dư đầu = 0 (số đầu kỳ được cộng vào sau)."""
    return df.groupby("tk")[["no", "co"]].sum().rename(columns={"no": "ps_no", "co": "ps_co"}).assign(dau=0.0)


class TrialBalance:
    """Bảng cân đối số phát sinh. Số dư tính theo Nợ ròng (Nợ là số dương, Có là số âm).
    Cột: dau = số dư đầu kỳ, ps_no / ps_co = phát sinh Nợ / Có, cuoi = số dư cuối kỳ."""

    def __init__(self, table: pd.DataFrame):
        self.__t = table[["dau", "ps_no", "ps_co"]].astype(float)

    @classmethod
    def from_ledger(cls, ledger: GeneralLedger, opening: pd.DataFrame) -> "TrialBalance":
        """Lập một TrialBalance cho mỗi tháng, rồi cộng tất cả lên số dư đầu kỳ bằng reduce."""
        lines = ledger.data
        start = pd.DataFrame({"dau": (opening["du_no"] - opening["du_co"]).values,
                              "ps_no": 0.0, "ps_co": 0.0}, index=opening["tk"].values)
        months = [cls(_sums(g)) for _, g in lines.groupby(lines["ngay_ghi_so"].dt.to_period("M"))]
        return reduce(operator.add, months, cls(start))

    def __add__(self, other: "TrialBalance") -> "TrialBalance":
        """tb1 + tb2: cộng từng tài khoản; tài khoản chỉ có ở một bên được coi là 0 ở bên kia."""
        return TrialBalance(self.__t.add(other.__t, fill_value=0.0))

    def __repr__(self) -> str:
        return f"TrialBalance(accounts={len(self.__t)}, debit={self.total_debit:,.0f}, credit={self.total_credit:,.0f})"

    # Các thuộc tính chỉ đọc (@property, không có setter nên không gán được)
    @property
    def total_debit(self) -> float:
        """Tổng phát sinh Nợ."""
        return float(self.__t["ps_no"].sum())

    @property
    def total_credit(self) -> float:
        """Tổng phát sinh Có."""
        return float(self.__t["ps_co"].sum())

    @property
    def table(self) -> pd.DataFrame:
        """Bảng đầy đủ, thêm cột cuoi = dau + ps_no - ps_co. Trả về bản sao."""
        t = self.__t.copy()
        return t.assign(cuoi=t["dau"] + t["ps_no"] - t["ps_co"]).sort_index()

    def net_debit(self, column: str = "cuoi") -> pd.Series:
        """Số dư Nợ ròng theo tài khoản (mặc định là cuối kỳ)."""
        return self.table[column]
