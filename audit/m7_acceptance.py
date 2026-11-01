"""Module 7: điểm rủi ro, kết luận chấp nhận khách hàng, quy tắc chặn (knock-out), phân tích độ nhạy.

Cách tính:
  5 nhóm yếu tố, mỗi nhóm chấm 0–100  ->  nhân trọng số  ->  điểm tổng 0–100  ->  so với ngưỡng ra kết luận.
  Nếu dính quy tắc chặn thì kết luận ít nhất là "Chấp nhận có điều kiện", bất kể điểm.
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Mapping

import pandas as pd

from .models import Decision, RiskLevel

# Các ngưỡng tín hiệu "mức đầy" (đạt mức này là 100% rủi ro). Độ nhạy sẽ đổi ±20% các ngưỡng này.
FULL_KEYS = ("missing_months_full", "unknown_ratio_full", "missing_ratio_full", "out_period_ratio_full",
             "high_entries_share_full", "revenue_spike_full")


def _clip(x: float) -> float:
    """Kẹp giá trị vào khoảng [0, 1]."""
    return max(0.0, min(1.0, x))


# ---- Điểm từng nhóm (0–100). c = context (dict kết quả các module), s = ngưỡng tín hiệu từ risk_weights.json
def score_data(c, s):
    """Nhóm 1: chất lượng dữ liệu. Trung bình của 6 tín hiệu (mỗi tín hiệu 0–1):
    sổ không cân, lệch CĐPS khách hàng, thiếu tháng, TK lạ, dòng thiếu thông tin, dòng ngoài kỳ."""
    m, pm = c["integrity"], c["pm"]
    # >= mức trọng yếu: điểm tối đa (1.0); có lệch nhỏ: điểm một phần; không lệch: 0
    unbal = 1.0 if m["unbalanced_amount"] >= pm else s["unbalanced_partial"] if m["unbalanced_amount"] > 0 else 0.0
    tb = 1.0 if m["tb_mismatch_amount"] >= pm else s["unbalanced_partial"] if m["tb_mismatch_amount"] > 0 else 0.0
    parts = [unbal, tb, _clip(m["missing_months"] / s["missing_months_full"]),
             _clip(m["unknown_ratio"] / s["unknown_ratio_full"]), _clip(m["missing_ratio"] / s["missing_ratio_full"]),
             _clip(m["out_period_ratio"] / s["out_period_ratio_full"])]
    return 100 * mean(parts)


def score_fraud(c, s):
    """Nhóm 2: rủi ro gian lận từ kiểm tra bút toán = tỷ lệ chứng từ rủi ro cao (trừ Benford) và mức Benford, có trọng số."""
    high = {f.so_ct for f in c["findings"] if f.muc_do == RiskLevel.HIGH and f.ma_thu_tuc != "JE14"}
    share = len(high) / max(c["n_entries"], 1)  # tỷ lệ chứng từ rủi ro cao
    benford = [s["benford_level_score"][r["level"]] for r in c["benford"].values()]
    w_high, w_ben = s["fraud_mix"]  # trọng số của hai phần
    return 100 * (w_high * _clip(share / s["high_entries_share_full"]) + w_ben * (mean(benford) if benford else 0))


def _label_score(c, s, key):
    """Đổi nhãn của một chỉ số (Tốt / Cần chú ý / Rủi ro) thành điểm 0–1. Thiếu chỉ số thì dùng điểm trung lập."""
    r = c["ratios"].get(key)
    return s["label_score"].get(r.label, s["neutral_score"]) if r else s["neutral_score"]


def score_financial(c, s):
    """Nhóm 3: sức khỏe tài chính = trung bình điểm các chỉ số trong danh sách financial_ratios."""
    return 100 * mean(_label_score(c, s, k) for k in s["financial_ratios"])


def score_reporting(c, s):
    """Nhóm 4: rủi ro báo cáo = trung bình của 3 tín hiệu: doanh thu tháng cuối tăng đột biến, DSO, cut-off (JE08)."""
    rev = c["monthly"]["revenue"]
    base = rev.iloc[:-1].mean()  # doanh thu trung bình các tháng trước tháng cuối
    spike = _clip((rev.iloc[-1] / base - 1) / (s["revenue_spike_full"] - 1)) if base > 0 else s["neutral_score"]
    cutoff = [f for f in c["findings"] if f.ma_thu_tuc == "JE08"]
    cut = 1.0 if any(f.muc_do == RiskLevel.HIGH for f in cutoff) else 0.5 if cutoff else 0.0
    return 100 * mean([spike, _label_score(c, s, "dso"), cut])


def score_qualitative(c, s):
    """Nhóm 5: yếu tố định tính (ngành, quản trị, chính trực) = trung bình điểm nhóm tự đánh giá trong config."""
    return float(mean(c["qual"].values()))


# Registry các hàm chấm điểm: tên nhóm -> hàm. Tên phải khớp khóa trọng số trong risk_weights.json.
SCORERS = {"data_quality": score_data, "fraud": score_fraud, "financial": score_financial,
           "reporting": score_reporting, "qualitative": score_qualitative}

# ---- Quy tắc chặn (knock-out): tên -> (mô tả, hàm điều kiện). Điều kiện đúng thì kết luận >= "Có điều kiện".
KNOCKOUTS = {
    "unbalanced_over_pm": ("Sổ không cân với giá trị vượt mức trọng yếu thực hiện",
                           lambda c: c["integrity"]["unbalanced_amount"] >= c["pm"]),
    "revenue_high_finding": ("Bút toán doanh thu bất thường vượt mức trọng yếu thực hiện",
                             lambda c: any(f.muc_do == RiskLevel.HIGH and f.ma_thu_tuc in ("JE09", "JE12")
                                           and "511" in f.tk and f.so_tien >= c["pm"] for f in c["findings"])),
    "tb_mismatch_over_pm": ("Sổ lệch bảng cân đối số phát sinh khách hàng vượt mức trọng yếu",
                            lambda c: c["integrity"]["tb_mismatch_amount"] >= c["pm"]),
}


@dataclass(frozen=True)
class Assessment:
    """Kết quả đánh giá cuối cùng."""
    total: float                    # điểm rủi ro tổng 0–100
    decision: Decision              # kết luận cuối (đã tính quy tắc chặn)
    score_decision: Decision        # kết luận nếu chỉ dựa vào điểm
    scores: Mapping[str, float]     # điểm từng nhóm
    weights: Mapping[str, float]    # trọng số từng nhóm (đã chuẩn hóa, tổng = 1)
    knocked: tuple[str, ...]        # các quy tắc chặn bị kích hoạt


class AcceptanceEngine:
    def __init__(self, cfg: Mapping):
        self.cfg = cfg  # nội dung config/risk_weights.json

    def factor_scores(self, ctx: Mapping, signals: Mapping | None = None) -> dict[str, float]:
        """Điểm từng nhóm. signals có thể truyền ngưỡng khác (dùng cho độ nhạy)."""
        s = signals or self.cfg["signals"]
        return {k: fn(ctx, s) for k, fn in SCORERS.items()}

    def knocked(self, ctx: Mapping) -> tuple[str, ...]:
        """Danh sách mô tả các quy tắc chặn đang bị kích hoạt (chỉ xét các quy tắc bật trong config)."""
        return tuple(KNOCKOUTS[k][0] for k in self.cfg["knockout"] if KNOCKOUTS[k][1](ctx))

    @staticmethod
    def assess(scores: Mapping, weights: Mapping, cutoffs: Mapping, knocked=()) -> Assessment:
        """Điểm tổng = tổng (trọng số x điểm nhóm). So với cutoff: dưới 'accept' chấp nhận,
        từ 'reject' trở lên từ chối, ở giữa chấp nhận có điều kiện. Dính knock-out thì tối thiểu 'có điều kiện'."""
        total_w = sum(weights.values())
        w = {k: v / total_w for k, v in weights.items()}  # chuẩn hóa để tổng trọng số = 1 (cần khi độ nhạy đổi trọng số)
        total = sum(w[k] * scores[k] for k in w)
        by_score = (Decision.ACCEPT if total < cutoffs["accept"]
                    else Decision.REJECT if total >= cutoffs["reject"] else Decision.CONDITIONAL)
        final = max(by_score, Decision.CONDITIONAL) if knocked else by_score  # max: lấy kết luận nặng hơn
        return Assessment(total, final, by_score, dict(scores), w, tuple(knocked))

    def run(self, ctx: Mapping) -> Assessment:
        """Chạy đủ: chấm điểm, kiểm tra knock-out, ra kết luận."""
        return self.assess(self.factor_scores(ctx), self.cfg["weights"], self.cfg["cutoffs"], self.knocked(ctx))

    def sensitivity(self, ctx: Mapping, base: Assessment) -> pd.DataFrame:
        """Phân tích độ nhạy: đổi trọng số, ngưỡng tín hiệu, ngưỡng kết luận ±20%, xem kết luận có đổi không."""
        cfg, rows = self.cfg, []

        def add(name, scores, weights, cutoffs):
            """Chạy một kịch bản và thêm một dòng kết quả."""
            a = self.assess(scores, weights, cutoffs, base.knocked)
            rows.append({"kich_ban": name, "diem": round(a.total, 1), "ket_luan": a.decision.vi,
                         "doi_ket_luan": a.decision != base.decision,
                         "ket_luan_theo_diem": a.score_decision.vi,
                         "doi_theo_diem": a.score_decision != base.score_decision})

        add("Cơ sở", base.scores, cfg["weights"], cfg["cutoffs"])  # kịch bản gốc để so sánh
        for k in cfg["weights"]:                                    # đổi từng trọng số -20% và +20%
            for pct in (-0.2, 0.2):
                add(f"Trọng số {k} {pct:+.0%}", base.scores, {**cfg["weights"], k: cfg["weights"][k] * (1 + pct)},
                    cfg["cutoffs"])
        for pct in (-0.2, 0.2):
            sig = {**cfg["signals"], **{k: cfg["signals"][k] * (1 + pct) for k in FULL_KEYS}}
            add(f"Ngưỡng tín hiệu {pct:+.0%}", self.factor_scores(ctx, sig), cfg["weights"], cfg["cutoffs"])
            add(f"Ngưỡng kết luận {pct:+.0%}", base.scores, cfg["weights"],
                {k: v * (1 + pct) for k, v in cfg["cutoffs"].items()})
        return pd.DataFrame(rows)

    def conditions(self, a: Assessment) -> list[str]:
        """Hành động đề xuất cho mỗi nhóm có điểm >= ngưỡng condition_min_score, nhóm nặng nhất trước."""
        low = self.cfg["signals"]["condition_min_score"]
        worst = sorted(a.scores.items(), key=lambda kv: -kv[1])
        return [f"{self.cfg['factor_names'][k]} ({v:.0f}/100): {self.cfg['conditions'][k]}" for k, v in worst if v >= low]

    def reasons(self, a: Assessment, n: int = 3) -> list[str]:
        """n nhóm đóng góp nhiều điểm nhất vào điểm tổng (đóng góp = trọng số x điểm nhóm). Dùng làm lý do chính."""
        top = sorted(a.scores, key=lambda k: -a.weights[k] * a.scores[k])[:n]
        return [f"{self.cfg['factor_names'][k]}: {a.scores[k]:.0f}/100 (đóng góp {a.weights[k] * a.scores[k]:.1f} điểm)"
                for k in top]
