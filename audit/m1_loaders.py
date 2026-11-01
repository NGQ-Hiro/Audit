"""Read client files into one standard line-per-account layout (Factory + Strategy)."""
from __future__ import annotations

import re
import unicodedata
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterator

import pandas as pd

from .fp import pipe
from .models import ROOT, SchemaError, read_json

COLUMNS = ("so_ct", "ngay_ct", "ngay_ghi_so", "dien_giai", "tk", "no", "co",
           "ma_doi_tuong", "nguoi_lap", "gio")
_ALIASES = {norm: canon for canon, names in read_json(ROOT / "config" / "columns.json").items()
            for norm in names}


def norm_header(h: str) -> str:
    """'Số CT' -> 'so_ct': lower case, no accents, non-alphanumeric -> '_'."""
    s = unicodedata.normalize("NFD", str(h).lower().replace("đ", "d"))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def _is_excel(path) -> bool:
    return Path(path).suffix.lower() in (".xlsx", ".xls")


MARKERS = {"so_du_dau_ky", "cong", "so_du_cuoi_ky"}  # subtotal rows of a ledger export


def _blank(s: pd.Series) -> pd.Series:
    return s.fillna("").astype(str).str.strip() == ""


def _opening(rows: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({"tk": list(map(normalize_tk, rows["tk"])),
                         "du_no": _num(rows["du_no"]).fillna(0).values, "du_co": _num(rows["du_co"]).fillna(0).values})


def _rename(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns=lambda h: _ALIASES.get(norm_header(h), norm_header(h)))


# ---------- cleaning steps (pure, chained with DataFrame.pipe) ----------
def normalize_tk(code) -> str:
    s = str(code).strip().replace(" ", "")
    if s.lower() in ("nan", "none"):
        return ""
    return s[:-2] if s.endswith(".0") else s  # Excel float artefact; leading zeros are kept (text)


def _num(s: pd.Series) -> pd.Series:
    s = s.astype("string").str.strip().str.replace(",", "", regex=False)
    s = s.str.replace(r"^(\d{1,3}(\.\d{3})+)$", lambda m: m.group(1).replace(".", ""), regex=True)  # 1.234.567
    return pd.to_numeric(s, errors="coerce")


def _date(s: pd.Series) -> pd.Series:
    """ISO (yyyy-mm-dd) first; other text is read day-first (Vietnamese dd/mm/yyyy)."""
    if pd.api.types.is_datetime64_any_dtype(s):
        return s
    s = s.astype("string").str.strip()
    iso = pd.to_datetime(s.str.extract(r"^(\d{4}-\d{2}-\d{2})")[0], format="%Y-%m-%d", errors="coerce")  # also 'yyyy-mm-dd 00:00:00' 
    return iso.fillna(pd.to_datetime(s.where(iso.isna()), errors="coerce", dayfirst=True, format="mixed"))


def parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    return df.assign(**{c: _date(df[c]) for c in ("ngay_ct", "ngay_ghi_so")})


def parse_numbers(df: pd.DataFrame) -> pd.DataFrame:
    hour = df["gio"].astype("string").str.extract(r"(\d{1,2}):\d{2}")[0]
    return df.assign(no=_num(df["no"]), co=_num(df["co"]), gio=pd.to_numeric(hour, errors="coerce"))


def normalize_accounts(df: pd.DataFrame) -> pd.DataFrame:
    return df.assign(tk=list(map(normalize_tk, df["tk"].fillna(""))))


def fill_text(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["so_ct", "dien_giai", "ma_doi_tuong", "nguoi_lap"]
    return df.assign(**{c: df[c].astype("string").fillna("").str.strip().astype(object) for c in cols})


def clean(df: pd.DataFrame) -> pd.DataFrame:
    return pipe(df, parse_dates, parse_numbers, normalize_accounts, fill_text).reset_index(drop=True)


def drop_invalid(df: pd.DataFrame) -> pd.DataFrame:
    """Keep rows usable as evidence (date, account, amount present); missing side -> 0."""
    ok = df["ngay_ghi_so"].notna() & (df["tk"] != "") & (df["no"].notna() | df["co"].notna())
    return df[ok].assign(no=df["no"].fillna(0.0), co=df["co"].fillna(0.0)).reset_index(drop=True)


# ---------- loaders ----------
class BaseLoader(ABC):
    required: tuple[str, ...]

    def __init__(self, chunksize: int = 50_000):
        self.chunksize = chunksize

    def chunks(self, path) -> Iterator[pd.DataFrame]:
        """Generator: big CSV files are read block by block."""
        if _is_excel(path):
            yield _rename(pd.read_excel(path, dtype=str))
        else:
            for chunk in pd.read_csv(path, dtype=str, chunksize=self.chunksize, encoding="utf-8-sig"):
                yield _rename(chunk)

    def _check(self, raw: pd.DataFrame) -> pd.DataFrame:
        missing = set(self.required) - set(raw.columns)
        if missing:
            raise SchemaError(f"Thiếu cột bắt buộc: {sorted(missing)}")
        return raw

    @abstractmethod
    def to_lines(self, raw: pd.DataFrame) -> pd.DataFrame:
        """Convert one chunk to one row per account line."""

    def load(self, path) -> pd.DataFrame:
        """Skip ledger subtotal rows ('Số dư đầu kỳ', 'Cộng', grand total); keep opening balances in self.opening."""
        lines, openings = [], []
        for c in map(self._check, self.chunks(path)):
            junk = _blank(c["so_ct"]) & (_blank(c["dien_giai"]) | c["dien_giai"].map(norm_header).isin(MARKERS))
            acct = c["tk"] if "tk" in c else c["tk_no"]
            openings.append(c[junk & (c["dien_giai"].map(norm_header) == "so_du_dau_ky") & ~_blank(acct)])
            lines.append(self.to_lines(c[~junk]))
        self.opening = _opening(pd.concat(openings)) if "du_no" in openings[0].columns else None
        lines = pd.concat(lines, ignore_index=True)
        return clean(lines.rename(columns={"gio_nhap": "gio"}).reindex(columns=COLUMNS))


class LineFormatLoader(BaseLoader):
    """Format A: one row per account line (tk, no, co)."""
    required = ("so_ct", "ngay_ghi_so", "tk", "no", "co")

    def to_lines(self, raw):
        return raw


class PairFormatLoader(BaseLoader):
    """Format B: one row per debit/credit pair (tk_no, tk_co, so_tien)."""
    required = ("so_ct", "ngay_ghi_so", "tk_no", "tk_co", "so_tien")

    def to_lines(self, raw):
        common = [c for c in raw.columns if c not in ("tk_no", "tk_co", "so_tien")]
        debit = raw[common].assign(tk=raw["tk_no"], no=raw["so_tien"], co="0")
        credit = raw[common].assign(tk=raw["tk_co"], no="0", co=raw["so_tien"])
        return pd.concat([debit, credit]).sort_index(kind="stable")


LOADERS = {"line": LineFormatLoader, "pair": PairFormatLoader}


def detect_format(path) -> str:
    head = _rename(pd.read_excel(path, nrows=0) if _is_excel(path) else pd.read_csv(path, nrows=0))
    cols = set(head.columns)
    if {"tk_no", "tk_co"} <= cols:
        return "pair"
    if "tk" in cols:
        return "line"
    raise SchemaError("Không nhận diện được định dạng file (cần cột tk hoặc tk_no/tk_co)")


def make_loader(path, fmt: str | None = None) -> BaseLoader:
    """Factory: choose the loader from the file header."""
    return LOADERS[fmt or detect_format(path)]()


def load_opening(path) -> pd.DataFrame:
    df = _rename(pd.read_csv(path, dtype=str))
    return pd.DataFrame({"tk": list(map(normalize_tk, df["tk"])),
                         "du_no": _num(df["du_no"]).fillna(0), "du_co": _num(df["du_co"]).fillna(0)})


def load_client_tb(path) -> pd.DataFrame:
    if _is_excel(path):  # shortcut: fixed layout (col A account, E debit, F credit), upgrade if the template changes
        raw = pd.read_excel(path, header=None, dtype=str)
        body = raw[raw[0].fillna("").str.strip().str.fullmatch(r"\d+")]
        tb = pd.DataFrame({"tk": list(map(normalize_tk, body[0])), "ps_no": _num(body[4]).fillna(0).values,
                           "ps_co": _num(body[5]).fillna(0).values,
                           "du_no": _num(body[2]).fillna(0).values, "du_co": _num(body[3]).fillna(0).values}).drop_duplicates("tk")
        # keep leaf accounts only: parents (111, 112...) repeat the sum of their children
        return tb[[not tb["tk"].str.startswith(a).sum() > 1 for a in tb["tk"]]].reset_index(drop=True)
    df = _rename(pd.read_csv(path, dtype=str))
    return pd.DataFrame({"tk": list(map(normalize_tk, df["tk"])),
                         "ps_no": _num(df["no"]).fillna(0), "ps_co": _num(df["co"]).fillna(0)})


def fill_opening(opening: pd.DataFrame, client_tb: pd.DataFrame | None) -> pd.DataFrame:
    """A detail ledger lists only accounts with movement; take opening balances of the rest from the client TB."""
    if client_tb is None or "du_no" not in client_tb:
        return opening
    extra = client_tb.loc[~client_tb["tk"].isin(opening["tk"]) & ((client_tb["du_no"] != 0) | (client_tb["du_co"] != 0)),
                          ["tk", "du_no", "du_co"]]
    return pd.concat([opening, extra], ignore_index=True)
