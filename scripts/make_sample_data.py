"""Generate synthetic sample data (trading company, FY2025) with injected anomalies.

Writes data/sample_gl.csv (line format), data/sample_gl_pair.csv (pair format),
data/opening_balances.csv and data/client_tb.csv.  Run: python scripts/make_sample_data.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
rng = np.random.default_rng(42)
HOLIDAYS = {pd.Timestamp(d) for d in json.loads((ROOT / "config/params.json").read_text())["holidays"]}
DAYS = [d for d in pd.date_range("2025-01-01", "2025-12-31") if d.day_of_week < 5 and d not in HOLIDAYS]
USERS, USER_P = ["ketoan1", "ketoan2", "ketoan3"], [0.5, 0.3, 0.2]
VOUCHERS = []  # dicts: prefix, date, desc, pairs[(no, co, amount)], kh, user, hour, ngay_ct


def lognorm(mu, sigma, n):
    return np.round(rng.lognormal(np.log(mu), sigma, n), -3)


def business_day(d):
    while d.day_of_week >= 5 or d in HOLIDAYS:
        d += pd.Timedelta(days=1)
    return d


def add(prefix, date, desc, pairs, kh="", user=None, hour=None, lag=0):
    VOUCHERS.append({"prefix": prefix, "date": date, "desc": desc, "pairs": pairs, "kh": kh,
                     "user": rng.choice(USERS, p=USER_P) if user is None else user,
                     "hour": int(rng.integers(8, 18)) if hour is None else hour,
                     "ngay_ct": date - pd.Timedelta(days=lag)})


customers, suppliers = [f"KH{i:03d}" for i in range(1, 61)], [f"NCC{i:02d}" for i in range(1, 21)]
cogs_total = 0.0
for month in range(1, 13):
    month_days = [d for d in DAYS if d.month == month]
    n_sales = 168 if month == 12 else 120
    for amt in lognorm(30e6, 0.9, n_sales):
        d, kh = rng.choice(month_days), rng.choice(customers)
        d = pd.Timestamp(d)
        vat = round(amt * 0.1, -3)
        add("BH", d, f"Bán hàng {kh}", [("131", "511", amt), ("131", "3331", vat)], kh,
            lag=int(rng.choice([0, 0, 0, 0, 1, 3])) if rng.random() < 0.04 else 0)
        cost = round(amt * 0.84, -3)
        cogs_total += cost
        add("XK", d, f"Xuất kho giá vốn {kh}", [("632", "156", cost)], kh)
        if rng.random() < 0.85:
            rd = business_day(d + pd.Timedelta(days=int(rng.integers(5, 45))))
            if rd.year == 2025:
                add("PT", rd, f"Thu tiền {kh}", [("112", "131", amt + vat)], kh)
    for label, pairs in (("Thuê văn phòng", ("642", "112", 80_123_000)), ("Lương nhân viên", ("642", "334", lognorm(380e6, 0.03, 1)[0])),
                         ("Lãi vay ngân hàng", ("635", "112", 12_345_000)), ("Khấu hao TSCĐ", ("642", "214", 8_000_000))):
        d = business_day(pd.Timestamp(2025, month, 25))
        add("PKT", d, label, [pairs])
    add("PC", business_day(pd.Timestamp(2025, month, 28)), "Chi lương", [("334", "112", 380_000_000)])
    for amt in lognorm(4e6, 0.8, 15):
        add("PC", pd.Timestamp(rng.choice(month_days)), "Chi phí văn phòng phẩm, tiếp khách", [("642", "111", amt)])
    for amt in lognorm(8e6, 0.8, 12):
        add("PC", pd.Timestamp(rng.choice(month_days)), "Chi phí vận chuyển, quảng cáo", [("641", "112", amt)])

# purchases: scaled so that purchases ~ 1.03 x cost of goods sold
raw = lognorm(37e6, 0.8, 1080)
scale = 1.03 * cogs_total / raw.sum()
for amt in raw:
    amt = round(amt * scale, -3)
    d, ncc = pd.Timestamp(rng.choice(DAYS)), rng.choice(suppliers)
    vat = round(amt * 0.1, -3)
    add("NK", d, f"Mua hàng {ncc}", [("156", "331", amt), ("133", "331", vat)], ncc)
    if rng.random() < 0.85:
        pd_ = business_day(d + pd.Timedelta(days=int(rng.integers(10, 50))))
        if pd_.year == 2025:
            add("TT", pd_, f"Trả tiền {ncc}", [("331", "112", amt + vat)], ncc)

# ---- injected anomalies
sat, sun, holiday = pd.Timestamp("2025-03-15"), pd.Timestamp("2025-06-08"), pd.Timestamp("2025-09-02")
add("PKT", sat, "Chi phí tư vấn", [("642", "112", 63_450_000)], user="ketoan2")
add("PKT", sun, "Chi phí tiếp khách", [("642", "111", 190_700_000)], user="ketoan2")
add("PKT", holiday, "Điều chỉnh", [("642", "112", 120_300_000)], user="ketoan1")
for i, h in enumerate((22, 23, 21)):
    add("PKT", pd.Timestamp(2025, 7, 10 + i), "Chi phí khác", [("642", "112", 55_000_000 + i * 1_234_000)], hour=h, user="ketoan3")
add("PKT", pd.Timestamp("2025-05-20"), "Chi phí dịch vụ", [("642", "112", 500_000_000)], user="ketoan2")
add("PKT", pd.Timestamp("2025-10-21"), "Chi phí sửa chữa", [("642", "112", 1_000_000_000)], user="ketoan2")
add("PKT", pd.Timestamp("2025-08-12"), "Thanh toán dịch vụ", [("642", "112", 489_900_000)], user="ketoan1")
add("PKT", pd.Timestamp("2025-11-18"), "Thanh toán dịch vụ", [("642", "112", 198_000_000)], user="ketoan1")
add("PKT", pd.Timestamp("2025-06-30"), "Ghi nhận doanh thu", [("211", "511", 300_000_000)], user="ketoan2")
add("PKT", pd.Timestamp("2025-10-15"), "Ghi nhận doanh thu tiền mặt", [("111", "511", 450_000_000)], user="ketoan1")
add("PKT", pd.Timestamp("2025-04-22"), "Chi tiền mặt", [("642", "111", 250_000_000)], user="ketoan3")
add("BH", pd.Timestamp("2025-12-30"), "Bán hàng lô lớn cuối năm", [("131", "511", 750_000_000), ("131", "3331", 75_000_000)], kh="KH999", user="ketoan1", hour=19)
add("BH", pd.Timestamp("2025-12-31"), "Bán hàng lô lớn cuối năm", [("131", "511", 620_000_000), ("131", "3331", 62_000_000)], kh="KH998", user="ketoan1", hour=20)
add("PKT", pd.Timestamp("2025-02-14"), "Xử lý", [("642", "112", 15_000_000)], user="ketoan9")
add("PKT", pd.Timestamp("2025-02-18"), "", [("642", "112", 9_000_000)], user="")
add("PKT", pd.Timestamp("2025-03-05"), "Khác", [("642", "112", 7_500_000)], user="ketoan9")
add("PKT", pd.Timestamp("2025-09-10"), "Chi phí tư vấn", [("642", "112", 40_000_000)], lag=75)

# ---- number vouchers in date order, build pairs
VOUCHERS.sort(key=lambda v: v["date"])
counters, pairs = {}, []
for v in VOUCHERS:
    counters[v["prefix"]] = counters.get(v["prefix"], 0) + 1
    v["so_ct"] = f"{v['prefix']}{counters[v['prefix']]:05d}"
    hh = f"{v['hour']:02d}:{int(rng.integers(0, 60)):02d}"
    for no, co, amt in v["pairs"]:
        pairs.append({"so_ct": v["so_ct"], "ngay_ct": v["ngay_ct"], "ngay_ghi_so": v["date"], "dien_giai": v["desc"],
                      "tk_no": no, "tk_co": co, "so_tien": float(amt), "ma_doi_tuong": v["kh"],
                      "nguoi_lap": v["user"], "gio_nhap": hh})
P = pd.DataFrame(pairs)

# ---- tax and closing vouchers (so the books are closed at 31/12)
def totals(df):
    s = pd.concat([df.groupby("tk_no")["so_tien"].sum(), -df.groupby("tk_co")["so_tien"].sum()]).groupby(level=0).sum()
    return s  # net debit by account

nd = totals(P)
pbt = -sum(v for k, v in nd.items() if k[0] in "5678")
tax = round(max(0, 0.2 * pbt), -3)
end = pd.Timestamp("2025-12-31")
extra = [("THUE0001", "Trích thuế TNDN", [("821", "3334", tax)])]
nd = nd.add(pd.Series({"821": tax, "3334": -tax}), fill_value=0)
close_pairs = [(tk, "911", -v) if v < 0 else ("911", tk, v) for tk, v in sorted(nd.items()) if tk[0] in "5678" and v != 0]
profit = -sum(v for k, v in nd.items() if k[0] in "5678")
close_pairs.append(("911", "421", profit))
rows = [{"so_ct": s, "ngay_ct": end, "ngay_ghi_so": end, "dien_giai": d, "tk_no": a, "tk_co": b, "so_tien": float(x),
         "ma_doi_tuong": "", "nguoi_lap": "ketoan1", "gio_nhap": "17:00"} for s, d, ps in extra for a, b, x in ps]
rows += [{"so_ct": "KC00001", "ngay_ct": end, "ngay_ghi_so": end, "dien_giai": "Kết chuyển cuối kỳ", "tk_no": a,
          "tk_co": b, "so_tien": float(x), "ma_doi_tuong": "", "nguoi_lap": "ketoan1", "gio_nhap": "17:30"}
         for a, b, x in close_pairs]
P = pd.concat([P, pd.DataFrame(rows)], ignore_index=True)

# ---- client trial balance (before we damage the ledger)
tb = pd.concat([P.groupby("tk_no")["so_tien"].sum().rename("ps_no"), P.groupby("tk_co")["so_tien"].sum().rename("ps_co")],
               axis=1).fillna(0).rename_axis("tk").reset_index()

# ---- damage the ledger: delete 3 vouchers (number gaps), duplicate 2 vouchers
drop = [v["so_ct"] for v in VOUCHERS if v["prefix"] == "BH"][200:203:2] + [VOUCHERS[400]["so_ct"]]
ledger = P[~P["so_ct"].isin(drop)]
dups = ledger[ledger["so_ct"].isin([v["so_ct"] for v in VOUCHERS if v["prefix"] == "PC"][50:52])]
ledger = pd.concat([ledger, dups], ignore_index=True)

fmt = lambda d: d.assign(ngay_ct=d["ngay_ct"].dt.strftime("%Y-%m-%d"), ngay_ghi_so=d["ngay_ghi_so"].dt.strftime("%Y-%m-%d"))
(ROOT / "data").mkdir(exist_ok=True)
fmt(ledger).to_csv(ROOT / "data/sample_gl_pair.csv", index=False)
lines = pd.concat([ledger.assign(tk=ledger["tk_no"], no=ledger["so_tien"], co=0.0),
                   ledger.assign(tk=ledger["tk_co"], no=0.0, co=ledger["so_tien"])]).sort_index(kind="stable")
lines = lines.drop(columns=["tk_no", "tk_co", "so_tien"])[["so_ct", "ngay_ct", "ngay_ghi_so", "dien_giai", "tk", "no", "co",
                                                           "ma_doi_tuong", "nguoi_lap", "gio_nhap"]]
# one unbalanced voucher: +2.5M on one credit line, in the line-format file only
lines = fmt(lines).reset_index(drop=True)
lines.loc[lines.index[(lines["so_ct"] == "PKT00010") & (lines["co"] > 0)][0], "co"] += 2_500_000
lines.to_csv(ROOT / "data/sample_gl.csv", index=False)
tb.to_csv(ROOT / "data/client_tb.csv", index=False)
pd.DataFrame([("112", 2e9, 0), ("131", 3e9, 0), ("156", 6e9, 0), ("211", 5e9, 0), ("214", 0, 1e9),
              ("331", 0, 2.5e9), ("3411", 0, 0.5e9), ("4111", 0, 12e9)], columns=["tk", "du_no", "du_co"]
             ).to_csv(ROOT / "data/opening_balances.csv", index=False)
print("vouchers:", len(set(P["so_ct"])), "lines:", len(lines), "PBT:", round(pbt))
