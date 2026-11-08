"""作者：Wangyuan；日期：2026-10-29；职责：独立离线JSON命令行入口。"""
from __future__ import annotations
import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any
from metrics import procurement, ratio, join_scores, rank_scores, PointLedger, compare_prices, export_csv
from workbooks import read_xlsx, fill_template, export_xlsx
def run(payload: dict, output: Path) -> Any:
    """运行采购、比率、积分、多源汇总或价格证据比较。"""
    action = payload["action"]; args = payload.get("args", {})
    if action == "read_xlsx": return read_xlsx(**args)
    if action == "fill_template": return fill_template(output=output / "filled.xlsx", **args)
    if action == "export_xlsx": return export_xlsx(output=output / "result.xlsx", **args)
    actions = {"procurement": procurement, "ratio": ratio, "join": join_scores, "rank": rank_scores, "prices": compare_prices}
    if action in actions: return actions[action](**args)
    ledger = PointLedger(output / "points.sqlite")
    if action == "record": return ledger.record(**args)
    if action == "monthly": return ledger.monthly(**args)
    raise ValueError("未知动作")

def demo(output: Path) -> dict:
    """演示精确金额、积分去重及未知分母。"""
    ledger = PointLedger(output / "points.sqlite"); ledger.record("source-1", "person-1", "2030-01", "2.5", "reviewer-1", confirmed=True)
    result = procurement([{"id": "item-1", "units_per_pack": 4, "package_price": "10.00", "category": "generic", "specification": "4件/包"}], [{"id": "item-1", "packs": 3}], price_caps={"generic": "3.00"})
    (output / "procurement.csv").write_text(export_csv(result["lines"], ["id", "packs", "amount"]), encoding="utf-8")
    return {"procurement": result, "monthly": ledger.monthly("2030-01", ["person-1", "person-2"]), "missing_ratio": ratio(None, 10)}

def main() -> int:
    """运行合成演示或显式输入；错误返回非零，不访问外部服务。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["demo", "run"])
    parser.add_argument("input", nargs="?")
    parser.add_argument("--output", help="显式输出目录；默认临时目录")
    args = parser.parse_args()
    try:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(args.output or temporary)
            output.mkdir(parents=True, exist_ok=True)
            if args.command == "demo":
                result = demo(output)
            else:
                if not args.input:
                    raise ValueError("run必须提供JSON文件")
                source = Path(args.input)
                if source.stat().st_size > 10_000_000:
                    raise ValueError("JSON文件超出预算")
                result = run(json.loads(source.read_text(encoding="utf-8")), output)
            print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (ValueError, TypeError, KeyError, OSError) as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
if __name__ == "__main__":
    raise SystemExit(main())
