"""Core types: enums, frozen evidence records, custom errors, Client."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from enum import IntEnum
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

ROOT = Path(__file__).resolve().parent.parent


def read_json(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


class AuditError(Exception):
    """Base class for all audit program errors."""


class SchemaError(AuditError):
    """Input file misses required columns."""


class UnbalancedEntryError(AuditError):
    def __init__(self, so_ct: str, diff: float):
        super().__init__(f"Chứng từ {so_ct} không cân Nợ/Có, chênh lệch {diff:,.0f}")
        self.so_ct, self.diff = so_ct, diff


class RiskLevel(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3

    @property
    def vi(self) -> str:
        return {1: "Thấp", 2: "Trung bình", 3: "Cao"}[self]


class Decision(IntEnum):
    ACCEPT = 1
    CONDITIONAL = 2
    REJECT = 3

    @property
    def vi(self) -> str:
        return {1: "Chấp nhận", 2: "Chấp nhận có điều kiện", 3: "Từ chối"}[self]


@dataclass(frozen=True)
class JournalLine:
    so_ct: str
    ngay_ghi_so: object
    tk: str
    no: float
    co: float
    dien_giai: str
    ma_doi_tuong: str
    nguoi_lap: str


@dataclass(frozen=True)
class Finding:
    ma_thu_tuc: str
    so_ct: str
    ngay: str
    tk: str
    so_tien: float
    mo_ta: str
    muc_do: RiskLevel

    def __lt__(self, other: "Finding") -> bool:
        """Order by risk, then amount. Use sorted(findings, reverse=True) for worst first."""
        return (self.muc_do, self.so_tien) < (other.muc_do, other.so_tien)

    def row(self) -> dict:
        return {"ma_thu_tuc": self.ma_thu_tuc, "so_ct": self.so_ct, "ngay": self.ngay, "tk": self.tk,
                "so_tien": self.so_tien, "mo_ta": self.mo_ta, "muc_do": self.muc_do.vi}


@dataclass(frozen=True)
class RatioResult:
    key: str
    name: str
    group: str
    value: float | None
    label: str
    note: str = ""


@dataclass(frozen=True)
class Client:
    name: str
    industry: str
    period_start: date
    period_end: date
    account_maps: Mapping[str, str]
    files: Mapping[str, str]
    qualitative: Mapping[str, float]

    @classmethod
    def from_config(cls, path) -> "Client":
        raw = read_json(path)
        return cls(raw["name"], raw["industry"], date.fromisoformat(raw["period_start"]),
                   date.fromisoformat(raw["period_end"]), MappingProxyType(raw["account_maps"]),
                   MappingProxyType(raw["files"]), MappingProxyType(raw["qualitative"]))

    def account_map_path(self) -> Path:
        """Pick the chart-of-accounts map by fiscal year (TT99 applies from FY2026)."""
        years = sorted(int(y) for y in self.account_maps)
        year = max((y for y in years if y <= self.period_start.year), default=years[0])
        return ROOT / self.account_maps[str(year)]
