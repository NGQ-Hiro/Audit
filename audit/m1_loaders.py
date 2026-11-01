"""Module 1 (phần đọc file): đọc file khách hàng về một bảng chuẩn, mỗi dòng là một dòng tài khoản.
Dùng mẫu Factory (chọn loader theo file) và Strategy (mỗi định dạng một lớp loader).

Luồng:  file CSV/Excel -> make_loader (chọn loader) -> chunks (đọc từng khối) -> to_lines -> clean -> bảng chuẩn
"""
from __future__ import annotations

import re
import unicodedata
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterator

import pandas as pd

from .fp import pipe
from .models import ROOT, SchemaError, read_json

# Các cột chuẩn của bảng đầu ra
COLUMNS = ("so_ct", "ngay_ct", "ngay_ghi_so", "dien_giai", "tk", "no", "co",
           "ma_doi_tuong", "nguoi_lap", "gio")
# Từ điển đổi tên cột: tên khách hàng hay dùng ("Số CT", "So chung tu"...) -> tên chuẩn ("so_ct").
# Đọc từ config/columns.json nên thêm tên mới không cần sửa code.
_ALIASES = {norm: canon for canon, names in read_json(ROOT / "config" / "columns.json").items()
            for norm in names}


def norm_header(h: str) -> str:
    """Chuẩn hóa tên cột: 'Số CT' -> 'so_ct' (chữ thường, bỏ dấu, ký tự lạ -> '_')."""
    s = unicodedata.normalize("NFD", str(h).lower().replace("đ", "d"))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")  # bỏ dấu
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def _is_excel(path) -> bool:
    return Path(path).suffix.lower() in (".xlsx", ".xls")


# Dòng tổng hợp trong sổ xuất ra từ phần mềm kế toán: không phải bút toán thật
MARKERS = {"so_du_dau_ky", "cong", "so_du_cuoi_ky"}


def _blank(s: pd.Series) -> pd.Series:
    """True ở những ô trống (NaN hoặc chỉ có khoảng trắng)."""
    return s.fillna("").astype(str).str.strip() == ""


def _opening(rows: pd.DataFrame) -> pd.DataFrame:
    """Bảng số dư đầu kỳ (tk, du_no, du_co) từ các dòng 'Số dư đầu kỳ' của sổ."""
    return pd.DataFrame({"tk": list(map(normalize_tk, rows["tk"])),
                         "du_no": _num(rows["du_no"]).fillna(0).values, "du_co": _num(rows["du_co"]).fillna(0).values})


def _rename(df: pd.DataFrame) -> pd.DataFrame:
    """Đổi tên cột về tên chuẩn bằng _ALIASES."""
    return df.rename(columns=lambda h: _ALIASES.get(norm_header(h), norm_header(h)))


# ---------- Các bước làm sạch (hàm thuần, nối với nhau bằng pipe) ----------
def normalize_tk(code) -> str:
    """Chuẩn hóa mã tài khoản thành chuỗi: bỏ khoảng trắng, giữ số 0 đầu, 'nan' -> ''."""
    s = str(code).strip().replace(" ", "")
    if s.lower() in ("nan", "none"):
        return ""
    return s[:-2] if s.endswith(".0") else s  # Excel hay thêm ".0" vào số; số 0 đầu được giữ vì đọc dạng chữ


def _num(s: pd.Series) -> pd.Series:
    """Đổi chữ thành số. Bỏ dấu phẩy ngăn cách nghìn; '1.234.567' (kiểu Việt) -> 1234567.
    Giá trị không đọc được thành NaN (không báo lỗi)."""
    s = s.astype("string").str.strip().str.replace(",", "", regex=False)
    s = s.str.replace(r"^(\d{1,3}(\.\d{3})+)$", lambda m: m.group(1).replace(".", ""), regex=True)  # 1.234.567
    return pd.to_numeric(s, errors="coerce")


def _date(s: pd.Series) -> pd.Series:
    """Đọc ngày: thử dạng ISO (yyyy-mm-dd) trước; chữ khác đọc theo kiểu Việt (dd/mm/yyyy)."""
    if pd.api.types.is_datetime64_any_dtype(s):
        return s
    s = s.astype("string").str.strip()
    iso = pd.to_datetime(s.str.extract(r"^(\d{4}-\d{2}-\d{2})")[0], format="%Y-%m-%d", errors="coerce")  # cả 'yyyy-mm-dd 00:00:00'
    return iso.fillna(pd.to_datetime(s.where(iso.isna()), errors="coerce", dayfirst=True, format="mixed"))


def parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Bước 1: đổi 2 cột ngày thành kiểu ngày."""
    return df.assign(**{c: _date(df[c]) for c in ("ngay_ct", "ngay_ghi_so")})


def parse_numbers(df: pd.DataFrame) -> pd.DataFrame:
    """Bước 2: đổi Nợ, Có thành số; lấy giờ nhập (số nguyên) từ chữ dạng 'hh:mm'."""
    hour = df["gio"].astype("string").str.extract(r"(\d{1,2}):\d{2}")[0]
    return df.assign(no=_num(df["no"]), co=_num(df["co"]), gio=pd.to_numeric(hour, errors="coerce"))


def normalize_accounts(df: pd.DataFrame) -> pd.DataFrame:
    """Bước 3: chuẩn hóa mã tài khoản."""
    return df.assign(tk=list(map(normalize_tk, df["tk"].fillna(""))))


def fill_text(df: pd.DataFrame) -> pd.DataFrame:
    """Bước 4: cột chữ bị thiếu -> chuỗi rỗng, cắt khoảng trắng hai đầu."""
    cols = ["so_ct", "dien_giai", "ma_doi_tuong", "nguoi_lap"]
    return df.assign(**{c: df[c].astype("string").fillna("").str.strip().astype(object) for c in cols})


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Chạy 4 bước làm sạch theo thứ tự. df gốc không bị sửa (mỗi bước trả về bảng mới)."""
    return pipe(df, parse_dates, parse_numbers, normalize_accounts, fill_text).reset_index(drop=True)


def drop_invalid(df: pd.DataFrame) -> pd.DataFrame:
    """Giữ các dòng dùng được làm bằng chứng: có ngày, có tài khoản, có ít nhất một số tiền.
    Bên Nợ hoặc Có bị thiếu thì coi là 0."""
    ok = df["ngay_ghi_so"].notna() & (df["tk"] != "") & (df["no"].notna() | df["co"].notna())
    return df[ok].assign(no=df["no"].fillna(0.0), co=df["co"].fillna(0.0)).reset_index(drop=True)


# ---------- Các loader ----------
class BaseLoader(ABC):
    """Lớp cha trừu tượng. Lớp con chỉ cần định nghĩa 'required' và 'to_lines'."""
    required: tuple[str, ...]  # các cột bắt buộc phải có

    def __init__(self, chunksize: int = 50_000):
        self.chunksize = chunksize  # số dòng mỗi khối khi đọc file CSV lớn

    def chunks(self, path) -> Iterator[pd.DataFrame]:
        """Generator: file CSV lớn được đọc từng khối, không nạp hết vào bộ nhớ một lần."""
        if _is_excel(path):
            yield _rename(pd.read_excel(path, dtype=str))
        else:
            for chunk in pd.read_csv(path, dtype=str, chunksize=self.chunksize, encoding="utf-8-sig"):
                yield _rename(chunk)

    def _check(self, raw: pd.DataFrame) -> pd.DataFrame:
        """Báo SchemaError nếu thiếu cột bắt buộc."""
        missing = set(self.required) - set(raw.columns)
        if missing:
            raise SchemaError(f"Thiếu cột bắt buộc: {sorted(missing)}")
        return raw

    @abstractmethod
    def to_lines(self, raw: pd.DataFrame) -> pd.DataFrame:
        """Đổi một khối dữ liệu thành bảng mỗi dòng một tài khoản."""

    def load(self, path) -> pd.DataFrame:
        """Đọc toàn bộ file. Bỏ các dòng tổng ('Số dư đầu kỳ', 'Cộng', tổng cuối);
        riêng số dư đầu kỳ được lưu lại trong self.opening."""
        lines, openings = [], []
        for c in map(self._check, self.chunks(path)):
            # dòng "rác" = không có số chứng từ và diễn giải trống hoặc là dòng tổng
            junk = _blank(c["so_ct"]) & (_blank(c["dien_giai"]) | c["dien_giai"].map(norm_header).isin(MARKERS))
            acct = c["tk"] if "tk" in c else c["tk_no"]
            # trong số dòng rác, giữ lại dòng "Số dư đầu kỳ" có tài khoản
            openings.append(c[junk & (c["dien_giai"].map(norm_header) == "so_du_dau_ky") & ~_blank(acct)])
            lines.append(self.to_lines(c[~junk]))
        self.opening = _opening(pd.concat(openings)) if "du_no" in openings[0].columns else None
        lines = pd.concat(lines, ignore_index=True)
        return clean(lines.rename(columns={"gio_nhap": "gio"}).reindex(columns=COLUMNS))


class LineFormatLoader(BaseLoader):
    """Định dạng A: mỗi dòng là một dòng tài khoản (cột tk, no, co). Đã đúng dạng chuẩn."""
    required = ("so_ct", "ngay_ghi_so", "tk", "no", "co")

    def to_lines(self, raw):
        return raw


class PairFormatLoader(BaseLoader):
    """Định dạng B: mỗi dòng là một cặp Nợ/Có (cột tk_no, tk_co, so_tien).
    Tách mỗi cặp thành 2 dòng: một dòng Nợ và một dòng Có."""
    required = ("so_ct", "ngay_ghi_so", "tk_no", "tk_co", "so_tien")

    def to_lines(self, raw):
        common = [c for c in raw.columns if c not in ("tk_no", "tk_co", "so_tien")]
        debit = raw[common].assign(tk=raw["tk_no"], no=raw["so_tien"], co="0")
        credit = raw[common].assign(tk=raw["tk_co"], no="0", co=raw["so_tien"])
        return pd.concat([debit, credit]).sort_index(kind="stable")  # giữ dòng Nợ ngay trước dòng Có


LOADERS = {"line": LineFormatLoader, "pair": PairFormatLoader}


def detect_format(path) -> str:
    """Nhìn tên cột để đoán định dạng: có tk_no + tk_co -> 'pair'; có tk -> 'line'."""
    head = _rename(pd.read_excel(path, nrows=0) if _is_excel(path) else pd.read_csv(path, nrows=0))
    cols = set(head.columns)
    if {"tk_no", "tk_co"} <= cols:
        return "pair"
    if "tk" in cols:
        return "line"
    raise SchemaError("Không nhận diện được định dạng file (cần cột tk hoặc tk_no/tk_co)")


def make_loader(path, fmt: str | None = None) -> BaseLoader:
    """Factory: chọn loader phù hợp từ tên cột của file (hoặc từ fmt nếu truyền vào)."""
    return LOADERS[fmt or detect_format(path)]()


def load_opening(path) -> pd.DataFrame:
    """Đọc file số dư đầu kỳ riêng (CSV): cột tk, du_no, du_co."""
    df = _rename(pd.read_csv(path, dtype=str))
    return pd.DataFrame({"tk": list(map(normalize_tk, df["tk"])),
                         "du_no": _num(df["du_no"]).fillna(0), "du_co": _num(df["du_co"]).fillna(0)})


def load_client_tb(path) -> pd.DataFrame:
    """Đọc Bảng cân đối phát sinh (CĐPS) do khách hàng gửi, để đối chiếu với sổ."""
    if _is_excel(path):  # shortcut: bố cục cố định (cột A tài khoản, E Nợ, F Có); nếu mẫu đổi thì phải sửa
        raw = pd.read_excel(path, header=None, dtype=str)
        body = raw[raw[0].fillna("").str.strip().str.fullmatch(r"\d+")]  # chỉ lấy dòng có cột A là mã tài khoản
        tb = pd.DataFrame({"tk": list(map(normalize_tk, body[0])), "ps_no": _num(body[4]).fillna(0).values,
                           "ps_co": _num(body[5]).fillna(0).values,
                           "du_no": _num(body[2]).fillna(0).values, "du_co": _num(body[3]).fillna(0).values}).drop_duplicates("tk")
        # chỉ giữ tài khoản chi tiết (lá): tài khoản cha (111, 112...) lặp lại tổng của các tài khoản con
        return tb[[not tb["tk"].str.startswith(a).sum() > 1 for a in tb["tk"]]].reset_index(drop=True)
    df = _rename(pd.read_csv(path, dtype=str))
    return pd.DataFrame({"tk": list(map(normalize_tk, df["tk"])),
                         "ps_no": _num(df["no"]).fillna(0), "ps_co": _num(df["co"]).fillna(0)})


def fill_opening(opening: pd.DataFrame, client_tb: pd.DataFrame | None) -> pd.DataFrame:
    """Sổ chi tiết chỉ liệt kê tài khoản có phát sinh. Với tài khoản còn lại,
    lấy số dư đầu kỳ từ bảng CĐPS của khách hàng."""
    if client_tb is None or "du_no" not in client_tb:
        return opening
    extra = client_tb.loc[~client_tb["tk"].isin(opening["tk"]) & ((client_tb["du_no"] != 0) | (client_tb["du_co"] != 0)),
                          ["tk", "du_no", "du_co"]]
    return pd.concat([opening, extra], ignore_index=True)
