"""Module 7: risk score, decision, knock-out rules, sensitivity."""
from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Mapping

import pandas as pd

from .models import Decision, RiskLevel

FULL_KEYS = ("missing_months_full", "unknown_ratio_full", "missing_ratio_full", "out_period_ratio_full",
             "high_entries_share_full", "revenue_spike_full")


def _clip(x: float) -> float:
    return max(0.0, min(1.0, x))


# ---- factor scores 0-100; c = context dict, s = signal thresholds from risk_weights.json
def score_data(c, s):
    m, pm = c["integrity"], c["pm"]
    unbal = 1.0 if m["unbalanced_amount"] >= pm else s["unbalanced_partial"] if m["unbalanced_amount"] > 0 else 0.0
    tb = 1.0 if m["tb_mismatch_amount"] >= pm else s["unbalanced_partial"] if m["tb_mismatch_amount"] > 0 else 0.0
    parts = [unbal, tb, _clip(m["missing_months"] / s["missing_months_full"]),
             _clip(m["unknown_ratio"] / s["unknown_ratio_full"]), _clip(m["missing_ratio"] / s["missing_ratio_full"]),
             _clip(m["out_period_ratio"] / s["out_period_ratio_full"])]
    return 100 * mean(parts)


def score_fraud(c, s):
    high = {f.so_ct for f in c["findings"] if f.muc_do == RiskLevel.HIGH and f.ma_thu_tuc != "JE14"}
    share = len(high) / max(c["n_entries"], 1)
    benford = [s["benford_level_score"][r["level"]] for r in c["benford"].values()]
    w_high, w_ben = s["fraud_mix"]
    return 100 * (w_high * _clip(share / s["high_entries_share_full"]) + w_ben * (mean(benford) if benford else 0))


def _label_score(c, s, key):
    r = c["ratios"].get(key)
    return s["label_score"].get(r.label, s["neutral_score"]) if r else s["neutral_score"]


def score_financial(c, s):
    return 100 * mean(_label_score(c, s, k) for k in s["financial_ratios"])


def score_reporting(c, s):
    rev = c["monthly"]["revenue"]
    base = rev.iloc[:-1].mean()
    spike = _clip((rev.iloc[-1] / base - 1) / (s["revenue_spike_full"] - 1)) if base > 0 else s["neutral_score"]
    cutoff = [f for f in c["findings"] if f.ma_thu_tuc == "JE08"]
    cut = 1.0 if any(f.muc_do == RiskLevel.HIGH for f in cutoff) else 0.5 if cutoff else 0.0
    return 100 * mean([spike, _label_score(c, s, "dso"), cut])


def score_qualitative(c, s):
    return float(mean(c["qual"].values()))


SCORERS = {"data_quality": score_data, "fraud": score_fraud, "financial": score_financial,
           "reporting": score_reporting, "qualitative": score_qualitative}

# ---- knock-out rules: name -> (description, predicate)
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
    total: float
    decision: Decision
    score_decision: Decision  # decision from the score alone
    scores: Mapping[str, float]
    weights: Mapping[str, float]
    knocked: tuple[str, ...]


class AcceptanceEngine:
    def __init__(self, cfg: Mapping):
        self.cfg = cfg

    def factor_scores(self, ctx: Mapping, signals: Mapping | None = None) -> dict[str, float]:
        s = signals or self.cfg["signals"]
        return {k: fn(ctx, s) for k, fn in SCORERS.items()}

    def knocked(self, ctx: Mapping) -> tuple[str, ...]:
        return tuple(KNOCKOUTS[k][0] for k in self.cfg["knockout"] if KNOCKOUTS[k][1](ctx))

    @staticmethod
    def assess(scores: Mapping, weights: Mapping, cutoffs: Mapping, knocked=()) -> Assessment:
        total_w = sum(weights.values())
        w = {k: v / total_w for k, v in weights.items()}
        total = sum(w[k] * scores[k] for k in w)
        by_score = (Decision.ACCEPT if total < cutoffs["accept"]
                    else Decision.REJECT if total >= cutoffs["reject"] else Decision.CONDITIONAL)
        final = max(by_score, Decision.CONDITIONAL) if knocked else by_score
        return Assessment(total, final, by_score, dict(scores), w, tuple(knocked))

    def run(self, ctx: Mapping) -> Assessment:
        return self.assess(self.factor_scores(ctx), self.cfg["weights"], self.cfg["cutoffs"], self.knocked(ctx))

    def sensitivity(self, ctx: Mapping, base: Assessment) -> pd.DataFrame:
        """Vary weights, signal thresholds and cutoffs by -20% / +20%."""
        cfg, rows = self.cfg, []

        def add(name, scores, weights, cutoffs):
            a = self.assess(scores, weights, cutoffs, base.knocked)
            rows.append({"kich_ban": name, "diem": round(a.total, 1), "ket_luan": a.decision.vi,
                         "doi_ket_luan": a.decision != base.decision,
                         "ket_luan_theo_diem": a.score_decision.vi,
                         "doi_theo_diem": a.score_decision != base.score_decision})

        add("Cơ sở", base.scores, cfg["weights"], cfg["cutoffs"])
        for k in cfg["weights"]:
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
        """Actions for each factor scoring at or above the threshold, worst first."""
        low = self.cfg["signals"]["condition_min_score"]
        worst = sorted(a.scores.items(), key=lambda kv: -kv[1])
        return [f"{self.cfg['factor_names'][k]} ({v:.0f}/100): {self.cfg['conditions'][k]}" for k, v in worst if v >= low]

    def reasons(self, a: Assessment, n: int = 3) -> list[str]:
        top = sorted(a.scores, key=lambda k: -a.weights[k] * a.scores[k])[:n]
        return [f"{self.cfg['factor_names'][k]}: {a.scores[k]:.0f}/100 (đóng góp {a.weights[k] * a.scores[k]:.1f} điểm)"
                for k in top]
