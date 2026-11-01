"""Hàm tiện ích kiểu lập trình hàm (FP): compose/pipe, closure, decorator ghi dấu vết kiểm toán."""
from __future__ import annotations

import logging
import time
from functools import reduce, wraps

import pandas as pd

log = logging.getLogger("audit")
TRAIL: list[dict] = []  # dấu vết kiểm toán (audit trail): mỗi bước được kiểm toán thêm 1 bản ghi vào đây


def compose(*fns):
    """Ghép nhiều hàm thành một hàm, chạy từ trái sang phải.
    compose(f, g, h)(x) = h(g(f(x)))"""
    return lambda x: reduce(lambda acc, f: f(acc), fns, x)


def pipe(x, *fns):
    """Đưa x qua lần lượt các hàm. pipe(df, f1, f2) = f2(f1(df))."""
    return compose(*fns)(x)


def make_threshold_test(threshold: float, lo: float = 0.95):
    """Closure: tạo hàm kiểm tra "số tiền nằm ngay dưới ngưỡng phê duyệt".
    Ví dụ ngưỡng 500 triệu, lo=0.95 -> True nếu số tiền trong khoảng [475 triệu, 500 triệu)."""
    return lambda amount: lo * threshold <= amount < threshold


def make_account_filter(*prefixes: str):
    """Closure: tạo hàm kiểm tra tài khoản có bắt đầu bằng một trong các tiền tố.
    Ví dụ make_account_filter("5") -> chọn mọi TK doanh thu (loại 5)."""
    return lambda tk: tk.startswith(prefixes)


def is_round_amount(amount: float, base: float) -> bool:
    """Số tiền 'tròn': lớn hơn hoặc bằng base và chia hết cho base (ví dụ base = 1 triệu)."""
    return amount >= base and amount % base == 0


def _rows(obj):
    """Số dòng của obj (nếu có độ dài), ngược lại None."""
    return len(obj) if hasattr(obj, "__len__") else None


def audit_log(fn):
    """Decorator: ghi vào TRAIL tên bước, số dòng vào, số dòng ra và thời gian chạy.
    Dùng để có dấu vết kiểm toán mà không phải sửa hàm gốc."""
    @wraps(fn)  # giữ tên và docstring của hàm gốc
    def wrapper(*args, **kw):
        # lấy DataFrame đầu tiên trong tham số làm "dữ liệu vào"
        frame = next((a for a in args if isinstance(a, pd.DataFrame)), None)
        t0 = time.perf_counter()
        out = fn(*args, **kw)  # chạy hàm gốc
        rec = {"thu_tuc": fn.__qualname__, "so_dong_vao": _rows(frame), "so_dong_ra": _rows(out),
               "giay": round(time.perf_counter() - t0, 3)}
        TRAIL.append(rec)
        log.info("%s", rec)
        return out
    return wrapper
