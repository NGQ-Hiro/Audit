"""Module 2: kiểm tra bút toán (Journal Entry Testing), 14 thủ tục JE01–JE14.

Mẫu Strategy: mỗi thủ tục là một lớp con của JournalEntryTest, có hàm run(df) trả về danh sách Finding.
Engine chỉ cần gọi test.run(df) cho từng thủ tục, không cần biết thủ tục đó làm gì (đa hình).
Lớp nào gắn @register_test thì tự được thêm vào danh sách TESTS (mẫu Registry).
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from functools import partial
from itertools import groupby, pairwise
from typing import Callable, Mapping

import numpy as np
import pandas as pd

from .fp import is_round_amount, make_account_filter, make_threshold_test
from .models import Finding, RiskLevel

TESTS: list[type] = []  # danh sách các lớp test (registry), được điền bởi @register_test
CHI2_CRIT_8DF_5PCT = 15.507  # giá trị tới hạn Chi-bình phương: 8 bậc tự do, mức ý nghĩa 5%
# Ngưỡng MAD của Nigrini: dưới 0.006 phù hợp chặt, dưới 0.012 chấp nhận, dưới 0.015 biên; còn lại không phù hợp
NIGRINI_MAD = ((0.006, "close"), (0.012, "acceptable"), (0.015, "marginal"))


def register_test(cls):
    """Decorator: đăng ký lớp test vào danh sách TESTS."""
    TESTS.append(cls)
    return cls


def entries(df: pd.DataFrame, include_closing: bool = False) -> pd.DataFrame:
    """Gộp các dòng thành MỘT DÒNG MỖI CHỨNG TỪ: tổng Nợ, tổng Có, ngày đầu tiên, người lập,
    diễn giải, đối tượng, danh sách tài khoản. Mặc định bỏ chứng từ kết chuyển (cột kc)."""
    d = df if include_closing else df[~df["kc"]]
    return (d.groupby("so_ct", sort=False)
            .agg(ngay=("ngay_ghi_so", "min"), amount=("no", "sum"), credit=("co", "sum"),
                 nguoi_lap=("nguoi_lap", "first"), gio=("gio", "min"), dien_giai=("dien_giai", "first"),
                 ma_doi_tuong=("ma_doi_tuong", "first"), tk=("tk", lambda s: ",".join(sorted(set(s))[:6])))
            .reset_index())


def _has_data(s: pd.Series) -> bool:
    """Cột có ít nhất một giá trị thật (không rỗng) không?"""
    return bool(s.notna().any() and (s.astype(str) != "").any())


class JournalEntryTest(ABC):
    """Lớp cha của mọi thủ tục. Lớp con phải có code, name và hàm run."""
    code: str   # mã thủ tục, ví dụ "JE01"
    name: str   # tên tiếng Việt

    def __init__(self, params: Mapping):
        self._p = params                 # tham số lấy từ config/params.json
        self._pm = params["pm"]          # mức trọng yếu thực hiện (Module 5)
        self.skipped = ""                # lý do bị bỏ qua khi thiếu dữ liệu cần thiết

    @abstractmethod
    def run(self, df: pd.DataFrame) -> list[Finding]: ...

    def _finding(self, so_ct, ngay, tk, amount, desc, base=RiskLevel.MEDIUM, escalate=True) -> Finding:
        """Tạo một Finding. Nếu số tiền >= mức trọng yếu thực hiện thì nâng lên rủi ro CAO
        (đây là chỗ Module 5 làm ngưỡng lọc cho Module 2)."""
        risk = RiskLevel.HIGH if escalate and amount >= self._pm else base
        day = "" if pd.isna(ngay) or ngay == "" else pd.Timestamp(ngay).date().isoformat()
        return Finding(self.code, str(so_ct), day, str(tk), float(amount), desc, risk)

    def _flag(self, ents: pd.DataFrame, mask, describe: Callable, base=RiskLevel.MEDIUM) -> list[Finding]:
        """Với mỗi chứng từ thỏa mask (True), tạo một Finding. describe(r) viết phần mô tả."""
        return [self._finding(r.so_ct, r.ngay, r.tk, r.amount, describe(r), base) for r in ents[mask].itertuples()]


@register_test
class UnbalancedTest(JournalEntryTest):
    """JE01: chứng từ có tổng Nợ khác tổng Có (vượt sai số cho phép)."""
    code, name = "JE01", "Chứng từ không cân Nợ/Có"

    def run(self, df):
        e = entries(df, include_closing=True)
        diff = (e["amount"] - e["credit"]).abs()  # số chênh lệch Nợ - Có
        return self._flag(e.assign(amount=diff), diff > self._p["balance_tolerance"],
                          lambda r: f"Lệch Nợ/Có {r.amount:,.0f}", RiskLevel.HIGH)


@register_test
class DuplicateTest(JournalEntryTest):
    """JE02: dòng trùng hoàn toàn (cùng số CT, ngày, TK, Nợ, Có). Giữ dòng đầu, đánh dấu các dòng sau."""
    code, name = "JE02", "Chứng từ trùng lặp"

    def run(self, df):
        d = df[df.duplicated(["so_ct", "ngay_ghi_so", "tk", "no", "co"], keep="first")]
        return [self._finding(r.so_ct, r.ngay_ghi_so, r.tk, r.no + r.co, "Dòng trùng số CT, ngày, TK, số tiền")
                for r in d.itertuples()]


@register_test
class GapTest(JournalEntryTest):
    """JE03: số chứng từ bị nhảy (ví dụ có AC2403001 và AC2403004, thiếu 002 và 003)."""
    code, name = "JE03", "Khoảng trống/nhảy số chứng từ"

    # Số chứng từ = chuỗi đầu + YYMM + số thứ tự (ví dụ AC24030033, T54942408002); mỗi tháng đánh số lại từ đầu
    # shortcut: regex đoán vị trí YYMM; định dạng lạ thì bị bỏ qua (không kiểm tra)
    _ID = re.compile(r"^(\D*\d*?2[3-6](?:0[1-9]|1[0-2]))(\d{3,6})$")

    def run(self, df):
        # Tách mỗi số chứng từ thành (chuỗi đầu+YYMM, số thứ tự, độ dài), rồi sắp xếp
        ids = sorted((m.group(1), int(m.group(2)), len(m.group(2))) for s in df["so_ct"].unique() if (m := self._ID.match(s)))
        out = []
        for series, grp in groupby(ids, key=lambda x: x[0]):      # nhóm theo từng dãy (series + tháng)
            for (_, a, w), (_, b, _) in pairwise(grp):            # so từng cặp số liền kề
                if b - a > 1:                                     # nhảy số: giữa a và b còn thiếu số
                    f = lambda n: f"{series}{n:0{w}d}"            # ghép lại thành số chứng từ đầy đủ
                    out.append(self._finding(f"{f(a + 1)}..{f(b - 1)}", "", "", 0,
                                             f"Thiếu {b - a - 1} số chứng từ giữa {f(a)} và {f(b)}"))
        return out


@register_test
class WeekendHolidayTest(JournalEntryTest):
    """JE04: chứng từ ghi sổ vào thứ Bảy, Chủ nhật hoặc ngày lễ."""
    code, name = "JE04", "Bút toán vào cuối tuần / ngày lễ"

    def run(self, df):
        e = entries(df)
        holidays = pd.to_datetime(list(self._p["holidays"]))   # danh sách ngày lễ trong config
        mask = (e["ngay"].dt.dayofweek >= 5) | e["ngay"].isin(holidays)  # dayofweek: 5 = thứ Bảy, 6 = Chủ nhật
        return self._flag(e, mask, lambda r: f"Ghi sổ ngày {r.ngay:%d/%m/%Y} ({'cuối tuần' if r.ngay.dayofweek >= 5 else 'ngày lễ'})",
                          RiskLevel.LOW)


@register_test
class AfterHoursTest(JournalEntryTest):
    """JE05: nhập liệu ngoài giờ làm việc. Bỏ qua nếu file không có cột giờ nhập."""
    code, name = "JE05", "Nhập liệu ngoài giờ làm việc"

    def run(self, df):
        e = entries(df)
        if not _has_data(e["gio"]):
            self.skipped = "không có dữ liệu giờ nhập"
            return []
        # ngoài giờ = từ after_hour trở đi (ví dụ 20h) hoặc trước before_hour (ví dụ 6h sáng)
        mask = e["gio"].notna() & ((e["gio"] >= self._p["after_hour"]) | (e["gio"] < self._p["before_hour"]))
        return self._flag(e, mask, lambda r: f"Nhập lúc {int(r.gio)}h", RiskLevel.LOW)


@register_test
class RoundAmountTest(JournalEntryTest):
    """JE06: số tiền tròn (chia hết cho round_base, ví dụ 1 triệu). Dấu hiệu ước tính hoặc điều chỉnh tay."""
    code, name = "JE06", "Số tiền tròn"

    def run(self, df):
        e = entries(df)
        test_round = partial(is_round_amount, base=self._p["round_base"])  # partial: cố định tham số base
        return self._flag(e, e["amount"].map(test_round), lambda r: f"Số tiền tròn {r.amount:,.0f}", RiskLevel.LOW)


@register_test
class JustBelowThresholdTest(JournalEntryTest):
    """JE07: số tiền nằm ngay dưới ngưỡng phê duyệt (95%–100%). Dấu hiệu né kiểm soát phê duyệt."""
    code, name = "JE07", "Số tiền ngay dưới ngưỡng phê duyệt"

    def run(self, df):
        e = entries(df)
        # mỗi ngưỡng phê duyệt có một hàm kiểm tra riêng (closure)
        tests = [make_threshold_test(t, self._p["threshold_lo"]) for t in self._p["approval_thresholds"]]
        return self._flag(e, e["amount"].map(lambda a: any(t(a) for t in tests)),
                          lambda r: f"Số tiền {r.amount:,.0f} sát dưới ngưỡng phê duyệt")


@register_test
class CutoffTest(JournalEntryTest):
    """JE08: bút toán LỚN gần ngày khóa sổ (± cutoff_days ngày). Rủi ro cut-off, thổi phồng doanh thu."""
    code, name = "JE08", "Bút toán lớn sát ngày khóa sổ"

    def run(self, df):
        e = entries(df)
        gap = (e["ngay"] - pd.Timestamp(self._p["period_end"])).abs().dt.days  # cách ngày khóa sổ bao nhiêu ngày
        # "lớn" = từ large_factor lần mức trọng yếu thực hiện trở lên
        mask = (gap <= self._p["cutoff_days"]) & (e["amount"] >= self._p["large_factor"] * self._pm)
        return self._flag(e, mask, lambda r: f"Bút toán lớn {r.amount:,.0f} ngày {r.ngay:%d/%m/%Y} gần khóa sổ")


@register_test
class UnusualPairTest(JournalEntryTest):
    """JE09: cặp tài khoản Nợ/Có bất thường (ví dụ Nợ 211 / Có 511). Các cặp khai báo trong config.
    Không cần cột TK đối ứng: chỉ cần chứng từ vừa có dòng Nợ TK này vừa có dòng Có TK kia."""
    code, name = "JE09", "Cặp tài khoản đối ứng bất thường"

    def run(self, df):
        d, e, out = df[~df["kc"]], entries(df), []
        for rule in self._p["unusual_pairs"]:
            dr = set(d.loc[(d["no"] > 0) & d["tk"].str.startswith(rule["no"]), "so_ct"])  # CT có dòng Nợ khớp
            cr = set(d.loc[(d["co"] > 0) & d["tk"].str.startswith(rule["co"]), "so_ct"])  # CT có dòng Có khớp
            hit = e[e["so_ct"].isin(dr & cr) & (e["amount"] >= rule["min"])]               # cả hai + đủ lớn
            out += [self._finding(r.so_ct, r.ngay, f"{rule['no']}/{rule['co']}", r.amount,
                                  f"Nợ {rule['no']} / Có {rule['co']} bất thường") for r in hit.itertuples()]
        return out


@register_test
class UserTest(JournalEntryTest):
    """JE10: người lập lạ (không có trong danh sách biết trước) hoặc có rất ít bút toán. Bỏ qua nếu không có cột người lập."""
    code, name = "JE10", "Người lập lạ hoặc rất ít bút toán"

    def run(self, df):
        e = entries(df)
        if not _has_data(e["nguoi_lap"]):
            self.skipped = "không có dữ liệu người lập"
            return []
        counts = e["nguoi_lap"].map(e["nguoi_lap"].value_counts())  # số chứng từ của người lập đó
        known = set(self._p["known_users"])
        mask = (e["nguoi_lap"] == "") | (counts < self._p["min_user_entries"])
        if known:  # nếu có danh sách người lập hợp lệ thì ai ngoài danh sách cũng bị đánh dấu
            mask |= ~e["nguoi_lap"].isin(known)
        return self._flag(e, mask, lambda r: f"Người lập '{r.nguoi_lap or 'trống'}' ít/lạ")


@register_test
class VagueDescriptionTest(JournalEntryTest):
    """JE11: diễn giải trống hoặc mơ hồ ("điều chỉnh", "khác", "xử lý"...). Thiếu căn cứ."""
    code, name = "JE11", "Diễn giải trống hoặc mơ hồ"

    def run(self, df):
        e = entries(df)
        norm = e["dien_giai"].str.lower().str.strip(" .")  # chữ thường, bỏ khoảng trắng và dấu chấm hai đầu
        mask = (norm == "") | norm.isin({w.lower() for w in self._p["vague_words"]})
        return self._flag(e, mask, lambda r: f"Diễn giải '{r.dien_giai}' trống/mơ hồ", RiskLevel.LOW)


@register_test
class OneTimePartyTest(JournalEntryTest):
    """JE12: đối tượng (khách hàng/NCC) chỉ xuất hiện 1 lần với giá trị lớn. Dấu hiệu khách hàng ảo."""
    code, name = "JE12", "Đối tượng chỉ phát sinh 1 lần, giá trị lớn"

    def run(self, df):
        e = entries(df)
        e = e[e["ma_doi_tuong"] != ""]
        if e.empty:
            self.skipped = "không có dữ liệu mã đối tượng"
            return []
        once = e["ma_doi_tuong"].map(e["ma_doi_tuong"].value_counts()) == 1  # đối tượng chỉ có đúng 1 chứng từ
        return self._flag(e, once & (e["amount"] >= self._p["large_factor"] * self._pm),
                          lambda r: f"Đối tượng {r.ma_doi_tuong} chỉ phát sinh 1 lần, {r.amount:,.0f}")


@register_test
class OutlierTest(JournalEntryTest):
    """JE13: ngoại lệ thống kê theo từng tài khoản, dùng IQR trên log10 của số tiền.
    Dùng log vì số tiền kế toán lệch phải rất mạnh. Giá trị > Q3 + k*IQR bị đánh dấu."""
    code, name = "JE13", "Ngoại lệ thống kê (IQR trên log, theo TK)"

    def run(self, df):
        d = df[~df["kc"]]
        d = d[(d["no"] + d["co"]) > 0]            # log chỉ tính được với số dương
        amt = d["no"] + d["co"]
        logs = np.log10(amt)
        q = logs.groupby(d["tk"]).quantile([0.25, 0.75]).unstack()   # Q1 và Q3 của từng tài khoản
        upper = q[0.75] + self._p["iqr_k"] * (q[0.75] - q[0.25])     # ngưỡng trên của từng tài khoản
        size = d["tk"].map(d["tk"].value_counts())                    # số dòng của tài khoản
        # chỉ xét tài khoản có đủ dòng (iqr_min_group) để thống kê có ý nghĩa
        hit = d[(logs > d["tk"].map(upper)) & (size >= self._p["iqr_min_group"])]
        return [self._finding(r.so_ct, r.ngay_ghi_so, r.tk, r.no + r.co, "Giá trị vượt ngoại lệ IQR của TK")
                for r in hit.itertuples()]


def first_digits(amounts: pd.Series) -> pd.Series:
    """Chữ số đầu tiên của mỗi số dương. Ví dụ 4523 -> 4, 0.37 -> 3."""
    a = amounts[amounts > 0]
    return np.floor(a / 10 ** np.floor(np.log10(a))).astype(int)


def benford_table(amounts: pd.Series) -> dict:
    """Tính kiểm định Benford: tần suất thực tế và kỳ vọng của chữ số đầu 1–9, Chi-bình phương, MAD (Nigrini).
    Kỳ vọng P(d) = log10(1 + 1/d). MAD = trung bình |thực tế - kỳ vọng|."""
    digits = first_digits(amounts)
    n = len(digits)
    idx = pd.Index(range(1, 10), name="chu_so")
    actual = digits.value_counts().reindex(idx, fill_value=0) / max(n, 1)   # tần suất thực tế
    expected = pd.Series(np.log10(1 + 1 / idx.to_numpy()), index=idx)       # tần suất kỳ vọng theo Benford
    mad = float((actual - expected).abs().mean())
    chi2 = float(n * ((actual - expected) ** 2 / expected).sum())
    level = next((name for limit, name in NIGRINI_MAD if mad < limit), "nonconforming")
    return {"n": n, "mad": mad, "chi2": chi2, "level": level,
            "table": pd.DataFrame({"thuc_te": actual, "ky_vong": expected})}


@register_test
class BenfordTest(JournalEntryTest):
    """JE14: kiểm định Benford chữ số đầu, chạy cho 3 nhóm: toàn sổ, doanh thu, chi phí.
    Chỉ tạo Finding khi mức phù hợp là 'biên' (MEDIUM) hoặc 'không phù hợp' (HIGH)."""
    code, name = "JE14", "Kiểm định Benford chữ số đầu"
    LEVEL_RISK = {"marginal": RiskLevel.MEDIUM, "nonconforming": RiskLevel.HIGH}

    def __init__(self, params):
        super().__init__(params)
        self.results: dict[str, dict] = {}  # lưu kết quả từng nhóm để vẽ biểu đồ Benford

    def run(self, df):
        d = df[~df["kc"]]
        amt = d["no"] + d["co"]
        # hai hàm lọc tài khoản doanh thu / chi phí, tiền tố lấy từ config
        is_revenue, is_expense = (make_account_filter(*self._p[k]) for k in ("revenue_prefixes", "expense_prefixes"))
        groups = {"Toàn sổ": amt, "Doanh thu": amt[d["tk"].map(is_revenue)], "Chi phí": amt[d["tk"].map(is_expense)]}
        out = []
        for name, series in groups.items():
            res = benford_table(series)
            if res["n"] < self._p["benford_min_n"]:  # quá ít dữ liệu thì kiểm định không đáng tin
                continue
            self.results[name] = res
            risk = self.LEVEL_RISK.get(res["level"])
            if risk:
                out.append(self._finding("—", "", name, series.sum(),
                                         f"Benford {name}: MAD={res['mad']:.4f} ({res['level']}), "
                                         f"chi2={res['chi2']:.1f} (tới hạn {CHI2_CRIT_8DF_5PCT})",
                                         risk, escalate=False))
        return out


def build_tests(params: Mapping) -> list[JournalEntryTest]:
    """Tạo đối tượng cho mọi thủ tục đã đăng ký, sắp theo mã (JE01, JE02, ...)."""
    return [cls(params) for cls in sorted(TESTS, key=lambda c: c.code)]


def summarize(findings_by_code: Mapping[str, list[Finding]], tests: list[JournalEntryTest]) -> pd.DataFrame:
    """Bảng tổng hợp: với mỗi thủ tục, số phát hiện, tổng giá trị, số phát hiện rủi ro cao, ghi chú bỏ qua."""
    rows = [{"ma_thu_tuc": t.code, "thu_tuc": t.name, "so_luong": len(findings_by_code[t.code]),
             "gia_tri": sum(f.so_tien for f in findings_by_code[t.code]),
             "so_rui_ro_cao": sum(f.muc_do == RiskLevel.HIGH for f in findings_by_code[t.code]),
             "ghi_chu": t.skipped} for t in tests]
    return pd.DataFrame(rows)
