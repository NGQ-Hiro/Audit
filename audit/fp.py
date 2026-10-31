"""Small functional helpers: compose/pipe, closures, audit-trail decorator."""
from __future__ import annotations

import logging
import time
from functools import reduce, wraps

import pandas as pd

log = logging.getLogger("audit")
TRAIL: list[dict] = []  # audit trail: one record per audited step


def compose(*fns):
    return lambda x: reduce(lambda acc, f: f(acc), fns, x)


def pipe(x, *fns):
    return compose(*fns)(x)


def make_threshold_test(threshold: float, lo: float = 0.95):
    """Closure: True when amount is just below the approval threshold."""
    return lambda amount: lo * threshold <= amount < threshold


def make_account_filter(*prefixes: str):
    return lambda tk: tk.startswith(prefixes)


def is_round_amount(amount: float, base: float) -> bool:
    return amount >= base and amount % base == 0


def _rows(obj):
    return len(obj) if hasattr(obj, "__len__") else None


def audit_log(fn):
    """Record step name, input rows, output rows and run time in TRAIL."""
    @wraps(fn)
    def wrapper(*args, **kw):
        frame = next((a for a in args if isinstance(a, pd.DataFrame)), None)
        t0 = time.perf_counter()
        out = fn(*args, **kw)
        rec = {"thu_tuc": fn.__qualname__, "so_dong_vao": _rows(frame), "so_dong_ra": _rows(out),
               "giay": round(time.perf_counter() - t0, 3)}
        TRAIL.append(rec)
        log.info("%s", rec)
        return out
    return wrapper
