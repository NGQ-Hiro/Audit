"""Audit.py - client acceptance assessment. Usage: python main.py [config/client.json] [out_dir]"""
import logging
import sys
from pathlib import Path

from audit.engagement import AuditEngagement
from audit.m1_integrity import check_integrity
from audit.m3_ledger import GeneralLedger
from audit.m1_loaders import drop_invalid, fill_opening, load_client_tb, load_opening, make_loader
from audit.models import ROOT, Client, read_json
from audit.report import export_all


def main(config=ROOT / "config" / "client_2024.json", out=ROOT / "outputs"):
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    client = Client.from_config(config)
    acct_map = read_json(client.account_map_path())
    params, risk_cfg = read_json(ROOT / "config" / "params.json"), read_json(ROOT / "config" / "risk_weights.json")
    benchmarks = read_json(ROOT / "config" / "benchmarks.json")

    gl_path = ROOT / client.files["gl"]
    loader = make_loader(gl_path)
    raw = loader.load(gl_path)  # Factory picks the loader from the header
    tb_file = client.files.get("client_tb")
    client_tb = load_client_tb(ROOT / tb_file) if tb_file and (ROOT / tb_file).exists() else None
    integrity = check_integrity(raw, client, set(acct_map["catalog"]), params, client_tb)
    ledger = GeneralLedger(drop_invalid(raw), tuple(acct_map["closing_accounts"]))
    opening_file = client.files.get("opening")  # null -> opening balances come from the GL itself
    opening = load_opening(ROOT / opening_file) if opening_file else loader.opening

    opening = fill_opening(opening, client_tb)
    result = AuditEngagement(client, ledger, opening, integrity, acct_map, params, risk_cfg, benchmarks).run()
    export_all(result, ledger.data, Path(out))
    a = result.assessment
    print(f"Điểm rủi ro: {a.total:.1f}/100 -> {a.decision.vi}")
    print(f"Quy tắc chặn: {', '.join(a.knocked) or 'không'} | Output: {out}")
    return result


if __name__ == "__main__":
    main(*(Path(p) for p in sys.argv[1:3]))
