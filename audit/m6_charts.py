"""Module 6: biểu đồ. Mỗi hàm vẽ được bọc bởi decorator @chart (hàm bậc cao) để dùng chung phần dựng và lưu hình."""
from __future__ import annotations

from functools import wraps
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # backend không cần màn hình: chỉ lưu ra file PNG
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from matplotlib.ticker import FuncFormatter  # noqa: E402

plt.style.use("seaborn-v0_8-whitegrid")
# Bảng màu dùng chung cho mọi biểu đồ
PAL = ["#2E86AB", "#F6AE2D", "#2F9E6E", "#E4572E", "#8E6C8A", "#17BEBB", "#F26419", "#6C757D", "#B5179E", "#3A0CA3", "#80B918"]
plt.rcParams.update({"axes.prop_cycle": plt.cycler(color=PAL), "axes.titleweight": "bold", "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False, "grid.alpha": 0.35})
thousands = FuncFormatter(lambda v, _: f"{v:,.0f}")  # định dạng trục: 1,234,567

M = 1e6  # số tiền vẽ theo đơn vị triệu đồng
DAYS = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "CN"]


def chart(filename: str, title: str, xlabel: str = "", ylabel: str = "", ncols: int = 1,
          polar: bool = False, figsize=(10, 5.5)):
    """Decorator dùng chung: tạo hình -> gọi hàm vẽ -> đặt tiêu đề -> lưu file -> đóng hình.
    Hàm vẽ chỉ cần lo phần vẽ; nó nhận `ax` (hoặc danh sách `ax` nếu ncols > 1). Hàm trả về đường dẫn file PNG."""
    def deco(draw):
        @wraps(draw)
        def wrapper(self, *args):
            fig, ax = plt.subplots(1, ncols, figsize=figsize, subplot_kw={"projection": "polar"} if polar else {})
            if ncols == 1 and not polar:  # đặt nhãn trước khi vẽ để hàm vẽ có thể ghi đè
                ax.set_xlabel(xlabel)
                ax.set_ylabel(ylabel)
            draw(self, ax, *args)
            fig.suptitle(title, fontweight="bold", fontsize=14)
            fig.tight_layout()
            path = self.out / filename
            fig.savefig(path, dpi=130)
            plt.close(fig)  # giải phóng bộ nhớ
            return path
        return wrapper
    return deco


class ChartBuilder:
    def __init__(self, out_dir):
        self.out = Path(out_dir)
        self.out.mkdir(parents=True, exist_ok=True)

    @chart("01_doanh_thu_gia_von.png", "Doanh thu - Giá vốn - Lợi nhuận gộp theo tháng", "Tháng", "Triệu đồng")
    def revenue_cogs_profit(self, ax, monthly: pd.DataFrame):
        """Cột: doanh thu và giá vốn. Đường: lợi nhuận gộp, có số ghi trên mỗi điểm."""
        x = np.arange(len(monthly))
        ax.bar(x - 0.2, monthly["revenue"] / M, 0.4, color=PAL[0], label="Doanh thu thuần")
        ax.bar(x + 0.2, monthly["cogs"] / M, 0.4, color=PAL[1], label="Giá vốn")
        gp = monthly["gross_profit"] / M
        ax.plot(x, gp, color="#C1121F", marker="o", ms=9, mec="white", mew=2, lw=3.5, zorder=5, label="Lợi nhuận gộp")
        for xi, v in zip(x, gp):  # ghi số trên mỗi điểm, nền trắng để dễ đọc trên cột
            ax.annotate(f"{v:,.0f}", (xi, v), textcoords="offset points", xytext=(0, 11), ha="center", fontsize=8,
                        fontweight="bold", color="#C1121F", zorder=6,
                        bbox={"boxstyle": "round,pad=0.15", "fc": "white", "ec": "none", "alpha": 0.85})
        ax.yaxis.set_major_formatter(thousands)
        ax.set_xticks(x, monthly.index, rotation=45)
        ax.legend()

    @chart("02_bien_loi_nhuan_gop.png", "Biên lợi nhuận gộp theo tháng", "Tháng", "Biên lợi nhuận gộp (%)")
    def gross_margin(self, ax, flags: pd.DataFrame):
        """Đường biên gộp theo tháng; tháng bất thường (lệch quá ±2 độ lệch chuẩn) tô điểm đỏ."""
        m = flags["bien_loi_nhuan_gop"] * 100
        ax.plot(m.index, m, marker="o", lw=2.5, color=PAL[0], label="Biên gộp")
        ax.fill_between(m.index, m, m.min() - 1, alpha=0.12, color=PAL[0])
        bad = flags["bat_thuong"]
        ax.scatter(m.index[bad], m[bad], color=PAL[3], s=140, zorder=3, edgecolor="white", label="Tháng bất thường (±2σ)")
        for i in m.index[bad]:
            ax.annotate(f"{m[i]:.1f}%", (i, m[i]), textcoords="offset points", xytext=(0, 10), ha="center", color=PAL[3], fontweight="bold")
        ax.axhline(m.mean(), ls="--", color="gray", label="Trung bình")  # đường trung bình để so sánh
        ax.tick_params(axis="x", rotation=45)
        ax.legend()

    @chart("03_benford.png", "Kiểm định Benford: tần suất chữ số đầu", "Chữ số đầu", "Tần suất (%)")
    def benford(self, ax, result: dict):
        """Cột: tần suất chữ số đầu thực tế. Đường đỏ: tần suất kỳ vọng theo Benford."""
        t = result["table"] * 100
        ax.bar(t.index, t["thuc_te"], color=PAL[0], label="Thực tế")
        ax.plot(t.index, t["ky_vong"], color=PAL[3], marker="o", lw=2.5, label="Kỳ vọng Benford")
        top = max(t["thuc_te"].max(), t["ky_vong"].max())
        for d, a_, e_ in zip(t.index, t["thuc_te"], t["ky_vong"]):  # ghi số trên giá trị cao hơn, không đè lên đường
            ax.text(d, max(a_, e_) + top * 0.03, f"{a_:.1f}%", ha="center", fontsize=9, fontweight="bold", color=PAL[0])
        ax.set_ylim(0, top * 1.25)
        ax.set_xticks(t.index)
        ax.set_title(f"MAD={result['mad']:.4f} ({result['level']}), n={result['n']:,}", fontsize=9)
        ax.legend()

    @chart("04_heatmap_gio_thu.png", "Số bút toán theo thứ trong tuần và giờ nhập liệu", "Giờ nhập", "Thứ")
    def heatmap(self, ax, ents: pd.DataFrame):
        """Bản đồ nhiệt: thứ trong tuần x giờ nhập. Ô càng đậm càng nhiều bút toán (phát hiện nhập liệu ngoài giờ)."""
        e = ents[ents["gio"].notna()]
        if e.empty:  # file không có cột giờ nhập: dùng tháng ghi sổ thay cho giờ
            grid = pd.crosstab(ents["ngay"].dt.dayofweek, ents["ngay"].dt.month).reindex(index=range(7), columns=range(1, 13), fill_value=0)
            ax.set_title("Số bút toán theo thứ và tháng ghi sổ (dữ liệu không có giờ nhập)", fontsize=10)
            ax.set_xlabel("Tháng ghi sổ")
        else:
            grid = pd.crosstab(e["ngay"].dt.dayofweek, e["gio"].astype(int)).reindex(index=range(7), columns=range(24),
                                                                                      fill_value=0)
        im = ax.imshow(grid.to_numpy(), aspect="auto", cmap="YlOrRd")
        ax.grid(False)
        if grid.shape[1] <= 12:  # ít cột thì ghi số vào từng ô
            top = grid.to_numpy().max() or 1
            for (i, j), v in np.ndenumerate(grid.to_numpy()):
                ax.text(j, i, f"{v:,}", ha="center", va="center", fontsize=8, color="white" if v > top / 2 else "black")
        ax.set_xticks(range(grid.shape[1]), grid.columns)
        ax.set_yticks(range(7), DAYS)
        ax.figure.colorbar(im, ax=ax, label="Số bút toán")

    @chart("05_theo_nguoi_lap.png", "Số lượng và giá trị bút toán theo người lập", "Người lập", "Số bút toán")
    def by_user(self, ax, ents: pd.DataFrame):
        """Cột: số bút toán theo người lập. Đường: tổng giá trị (trục phải)."""
        if (ents["nguoi_lap"].fillna("") == "").all():  # không có cột người lập: nhóm theo tiền tố số chứng từ
            ents = ents.assign(nguoi_lap=ents["so_ct"].str.extract(r"^([A-Za-z]+)")[0].fillna("(trống)"))
            ax.set_title("Theo loại chứng từ (tiền tố số CT; dữ liệu không có người lập)", fontsize=10)
            ax.set_xlabel("Tiền tố số chứng từ")
        g = ents.assign(nguoi_lap=ents["nguoi_lap"].replace("", "(trống)")).groupby("nguoi_lap").agg(
            n=("so_ct", "count"), amount=("amount", "sum"))
        g = g.sort_values("n", ascending=False).head(15)  # chỉ lấy 15 nhóm đầu cho dễ đọc
        ax.bar(g.index, g["n"], color=PAL[0], label="Số bút toán")
        ax.tick_params(axis="x", rotation=45)
        ax2 = ax.twinx()  # trục y thứ hai cho giá trị tiền
        ax2.grid(False)
        ax2.yaxis.set_major_formatter(thousands)
        ax2.plot(g.index, g["amount"] / M, color=PAL[3], marker="o", lw=2, label="Giá trị (triệu đồng)")
        ax2.set_ylabel("Giá trị (triệu đồng)")
        ax.set_ylim(0, g["n"].max() * 1.2)  # chừa chỗ trống để chú thích không che cột
        ax2.set_ylim(0, g["amount"].max() / M * 1.2)
        ax.legend(loc="upper right")
        ax2.legend(loc="center right")

    @chart("06_phan_phoi_so_tien.png", "Phân phối số tiền giao dịch", ncols=2, figsize=(12, 5.5))
    def distribution(self, axes, lines: pd.DataFrame):
        """Hai hình: histogram số tiền (thang log) và boxplot theo nhóm tài khoản. Dùng để thấy giá trị ngoại lai."""
        d = lines[~lines["kc"]].assign(amt=lambda x: x["no"] + x["co"])  # bỏ dòng kết chuyển
        d = d[d["amt"] > 0]  # log không tính được với số <= 0
        axes[0].hist(np.log10(d["amt"] / M), bins=40, color=PAL[0], edgecolor="white")
        axes[0].set(xlabel="log10(số tiền, triệu đồng)", ylabel="Số dòng", title="Histogram (thang log)")
        groups = d.groupby(d["tk"].str[:1])["amt"]  # nhóm theo loại tài khoản (chữ số đầu)
        bp = axes[1].boxplot([np.log10(v / M) for _, v in groups], tick_labels=[f"Loại {k}" for k, _ in groups],
                             patch_artist=True, medianprops={"color": "black"})
        for patch, c in zip(bp["boxes"], PAL * 2):
            patch.set(facecolor=c, alpha=0.7)
        axes[1].set(xlabel="Nhóm tài khoản", ylabel="log10(số tiền, triệu đồng)", title="Boxplot theo nhóm TK")

    @chart("07_co_cau_tai_san_nguon_von.png", "Cơ cấu tài sản và nguồn vốn", "", "Triệu đồng")
    def structure(self, ax, bs):
        """Hai cột chồng: cơ cấu tài sản và cơ cấu nguồn vốn, ghi số tiền và tỷ trọng trong từng phần."""
        cols = {"Tài sản": [("Tiền", "cash"), ("Phải thu", "receivables"), ("Hàng tồn kho", "inventory"),
                            ("TSNH khác", "other_current_assets"), ("TSCĐ", "fixed_assets"),
                            ("TSDH khác", "other_noncurrent_assets")],
                "Nguồn vốn": [("Nợ ngắn hạn", "current_liabilities"), ("Nợ dài hạn", "long_term_debt"),
                              ("Vốn chủ sở hữu", "equity")]}
        total = {n: sum(max(bs[k], 0) for _, k in p) / M or 1 for n, p in cols.items()}  # "or 1" tránh chia cho 0
        ax.yaxis.set_major_formatter(thousands)
        colors = iter(PAL + ["#B5179E", "#3A0CA3", "#80B918"])
        for i, (name, parts) in enumerate(cols.items()):
            bottom = 0.0  # đáy của phần đang vẽ (xếp chồng lên nhau)
            for label, key in parts:
                v = max(bs[key], 0) / M  # số âm không vẽ
                b = ax.bar(name, v, bottom=bottom, label=label, color=next(colors), edgecolor="white")
                if v > 0.04 * total[name]:  # phần quá nhỏ (<4%) thì không ghi số cho khỏi rối
                    ax.text(name, bottom + v / 2, f"{v:,.0f}\n({v / total[name]:.0%})", ha="center", va="center",
                            fontsize=8, color="white", fontweight="bold")
                bottom += v
        ax.legend(fontsize=8, bbox_to_anchor=(1.01, 1), loc="upper left")

    @chart("08_radar_chi_so.png", "Điểm các nhóm chỉ số tài chính (100 = tốt)", polar=True, figsize=(7.5, 7))
    def radar(self, ax, group_scores: dict[str, float], good: float = 100 * 2 / 3):
        """Biểu đồ radar: điểm từng nhóm chỉ số so với đường ngưỡng tốt (mặc định 66.7)."""
        names = list(group_scores)
        ang = np.linspace(0, 2 * np.pi, len(names), endpoint=False).tolist()  # góc của từng nhóm
        vals = [group_scores[n] for n in names]
        ax.plot(ang + ang[:1], vals + vals[:1], color=PAL[0], lw=2.5, label="Thực tế")  # thêm điểm đầu vào cuối để khép kín
        ax.fill(ang + ang[:1], vals + vals[:1], alpha=0.3, color=PAL[0])
        for a_, v_ in zip(ang, vals):
            ax.text(a_, v_ + 6, f"{v_:.0f}", ha="center", fontweight="bold", color=PAL[0])
        ax.plot(ang + ang[:1], [good] * (len(ang) + 1), ls="--", color=PAL[2], lw=2, label="Ngưỡng tốt")
        ax.set_xticks(ang, names)
        ax.set_ylim(0, 100)
        ax.legend(loc="lower right", bbox_to_anchor=(1.2, -0.05))

    @chart("09_diem_rui_ro.png", "Điểm rủi ro khách hàng và vùng quyết định", "Điểm rủi ro (0-100)", "", figsize=(10, 3))
    def gauge(self, ax, score: float, cutoffs: dict):
        """Thanh đo: 3 vùng màu (chấp nhận / có điều kiện / từ chối) và vạch đen chỉ điểm rủi ro của khách hàng."""
        a, r = cutoffs["accept"], cutoffs["reject"]
        for lo, hi, color, label in ((0, a, PAL[2], "Chấp nhận"), (a, r, PAL[1], "Có điều kiện"),
                                     (r, 100, PAL[3], "Từ chối")):
            ax.barh(0, hi - lo, left=lo, color=color, alpha=0.7)
            ax.text((lo + hi) / 2, -0.62, f"{label} ({lo}-{hi})", ha="center", fontweight="bold", color=color)
        ax.grid(False)
        ax.vlines(score, -0.4, 0.4, color="black", lw=4)  # vạch chỉ điểm
        ax.scatter([score], [0.45], marker="v", s=250, color="black", zorder=4)
        ax.text(score, 0.6, f"{score:.1f}", ha="center", fontweight="bold", fontsize=16)
        ax.set_xlim(0, 100)
        ax.set_yticks([])
        ax.set_ylim(-0.75, 1)
