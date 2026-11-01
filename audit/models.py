"""Các kiểu dữ liệu dùng chung: Enum, bản ghi bằng chứng (không đổi được), lỗi tự định nghĩa, Client.

File này không có logic xử lý. Nó chỉ định nghĩa "hình dạng" dữ liệu để các module khác dùng lại.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from enum import IntEnum
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

# Thư mục gốc của dự án (cha của thư mục audit/). Dùng để tìm thư mục config/.
ROOT = Path(__file__).resolve().parent.parent


def read_json(path) -> dict:
    """Đọc file JSON (UTF-8) và trả về dict."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ---------- Ngoại lệ tự định nghĩa ----------
# Cây kế thừa:  Exception -> AuditError -> SchemaError / UnbalancedEntryError
class AuditError(Exception):
    """Lớp lỗi gốc của chương trình. Bắt AuditError là bắt được mọi lỗi của dự án."""


class SchemaError(AuditError):
    """File đầu vào thiếu cột bắt buộc (hoặc không nhận ra định dạng)."""


class UnbalancedEntryError(AuditError):
    """Chứng từ không cân Nợ/Có. Lưu lại số chứng từ và số chênh lệch để báo cáo."""
    def __init__(self, so_ct: str, diff: float):
        super().__init__(f"Chứng từ {so_ct} không cân Nợ/Có, chênh lệch {diff:,.0f}")
        self.so_ct, self.diff = so_ct, diff


# ---------- Enum ----------
# Dùng IntEnum để so sánh và sắp xếp được: HIGH (3) > MEDIUM (2) > LOW (1).
class RiskLevel(IntEnum):
    """Mức độ rủi ro của một phát hiện."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3

    @property
    def vi(self) -> str:
        """Tên tiếng Việt, dùng khi in ra Excel/báo cáo."""
        return {1: "Thấp", 2: "Trung bình", 3: "Cao"}[self]


class Decision(IntEnum):
    """Kết luận cuối cùng về việc chấp nhận khách hàng."""
    ACCEPT = 1
    CONDITIONAL = 2
    REJECT = 3

    @property
    def vi(self) -> str:
        return {1: "Chấp nhận", 2: "Chấp nhận có điều kiện", 3: "Từ chối"}[self]


# ---------- Bản ghi bằng chứng ----------
# frozen=True: tạo xong thì không sửa được. Bằng chứng kiểm toán không được thay đổi.
@dataclass(frozen=True)
class JournalLine:
    """Một dòng bút toán (một tài khoản trong một chứng từ)."""
    so_ct: str          # số chứng từ
    ngay_ghi_so: object  # ngày ghi sổ
    tk: str             # tài khoản
    no: float           # số tiền ghi Nợ
    co: float           # số tiền ghi Có
    dien_giai: str      # diễn giải
    ma_doi_tuong: str   # mã khách hàng / nhà cung cấp
    nguoi_lap: str      # người lập


@dataclass(frozen=True)
class Finding:
    """Một phát hiện bất thường do một thủ tục kiểm tra bút toán (JE01–JE14) tạo ra."""
    ma_thu_tuc: str   # mã thủ tục, ví dụ "JE03"
    so_ct: str
    ngay: str
    tk: str
    so_tien: float
    mo_ta: str        # mô tả ngắn vì sao bị đánh dấu
    muc_do: RiskLevel

    def __lt__(self, other: "Finding") -> bool:
        """So sánh để sắp xếp: mức rủi ro trước, rồi đến số tiền.
        Dùng sorted(findings, reverse=True) để có phát hiện nặng nhất lên đầu."""
        return (self.muc_do, self.so_tien) < (other.muc_do, other.so_tien)

    def row(self) -> dict:
        """Chuyển thành dict để đưa vào bảng Excel."""
        return {"ma_thu_tuc": self.ma_thu_tuc, "so_ct": self.so_ct, "ngay": self.ngay, "tk": self.tk,
                "so_tien": self.so_tien, "mo_ta": self.mo_ta, "muc_do": self.muc_do.vi}


@dataclass(frozen=True)
class RatioResult:
    """Kết quả một chỉ số tài chính (ví dụ hệ số thanh toán hiện hành)."""
    key: str                # mã chỉ số, ví dụ "current_ratio"
    name: str               # tên tiếng Việt
    group: str              # nhóm: Thanh khoản, Cơ cấu vốn, ...
    value: float | None     # giá trị; None nếu không tính được (ví dụ chia cho 0)
    label: str              # nhãn: Tốt / Cần chú ý / Rủi ro
    note: str = ""          # ghi chú, ví dụ cảnh báo chia cho 0


@dataclass(frozen=True)
class Client:
    """Thông tin khách hàng, đọc từ file config/client*.json."""
    name: str
    industry: str
    period_start: date                 # ngày đầu kỳ kế toán
    period_end: date                   # ngày cuối kỳ kế toán
    account_maps: Mapping[str, str]    # năm -> file ánh xạ tài khoản (TT200 hoặc TT99)
    files: Mapping[str, str]           # đường dẫn các file dữ liệu
    qualitative: Mapping[str, float]   # điểm định tính (ngành, quản trị, chính trực)

    @classmethod
    def from_config(cls, path) -> "Client":
        """Tạo Client từ file JSON. MappingProxyType làm dict chỉ đọc (không sửa được)."""
        raw = read_json(path)
        return cls(raw["name"], raw["industry"], date.fromisoformat(raw["period_start"]),
                   date.fromisoformat(raw["period_end"]), MappingProxyType(raw["account_maps"]),
                   MappingProxyType(raw["files"]), MappingProxyType(raw["qualitative"]))

    def account_map_path(self) -> Path:
        """Chọn file ánh xạ tài khoản theo năm tài chính (TT99 áp dụng từ năm 2026).
        Lấy năm lớn nhất mà vẫn <= năm bắt đầu kỳ. Ví dụ kỳ 2024 -> dùng bản của năm 2024 hoặc cũ hơn."""
        years = sorted(int(y) for y in self.account_maps)
        year = max((y for y in years if y <= self.period_start.year), default=years[0])
        return ROOT / self.account_maps[str(year)]
