"""作者：Wangyuan；日期：2026-10-29；职责：精确数值、采购核算、积分和多源统计。"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import sqlite3
from contextlib import closing
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


def decimal(value: Any, *, nonnegative: bool = False) -> Decimal:
    """使用十进制文本解释数值；布尔、缺失、NaN、无穷明确拒绝。"""
    if isinstance(value, bool) or value is None: raise ValueError("数值类型无效")
    try: result = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc: raise ValueError("数值格式无效") from exc
    if not result.is_finite() or nonnegative and result < 0: raise ValueError("数值范围无效")
    return result


def count(value: Any) -> int:
    """保留大整数精度；有小数或大浮点数时拒绝。"""
    result = decimal(value, nonnegative=True)
    if result != result.to_integral_value() or isinstance(value, float) and value > 2**53: raise ValueError("计数须为精确非负整数")
    return int(result)


def procurement(catalog: list[dict], requests: list[dict], *, price_caps: dict[str, str],
                rounding: str = "0.01") -> dict:
    """按显式目录核对规格、数量、参考单价和金额，不含任何采购制度。"""
    lookup = {x["id"]: x for x in catalog}
    if len(lookup) != len(catalog): raise ValueError("目录身份重复")
    quantum = decimal(rounding, nonnegative=True)
    if quantum <= 0: raise ValueError("精度须为正")
    seen = set(); lines = []; total = Decimal(0)
    for request in requests:
        key = request["id"]
        if key not in lookup or key in seen: raise ValueError("申请物品未知或重复")
        seen.add(key); item = lookup[key]; packs = count(request["packs"]); units = count(item["units_per_pack"])
        if not units: raise ValueError("包装数量不能为零")
        price = decimal(item["package_price"], nonnegative=True); unit = price / units
        issues = []
        if not str(item.get("specification", "")).strip(): issues.append("missing_specification")
        cap = price_caps.get(item.get("category", ""))
        if cap is not None and unit > decimal(cap, nonnegative=True): issues.append("unit_price_above_configured_cap")
        if packs == 0: issues.append("zero_quantity")
        amount = (packs * price).quantize(quantum); total += amount
        received = count(request["received"]) if request.get("received") is not None else None
        if received is not None and received != packs: issues.append("received_quantity_mismatch")
        lines.append({"id": key, "packs": packs, "received": received, "unit_price": str(unit.quantize(quantum)),
                      "amount": str(amount), "issues": issues})
    return {"lines": lines, "total": str(total), "ready": all(not x["issues"] for x in lines)}


def ratio(sold: Any, capacity: Any) -> dict:
    """保留未知和零分母；不设销售阈值。"""
    if sold is None or capacity is None: return {"state": "missing", "ratio": None}
    numerator, denominator = count(sold), count(capacity)
    if numerator > denominator: raise ValueError("分子超过容量")
    return {"state": "not_applicable", "ratio": None} if denominator == 0 else {"state": "available", "ratio": str(Decimal(numerator) / denominator)}


def join_scores(roster: list[dict], sources: list[dict], weights: dict[str, str],
                base: str, expected_month: str) -> dict:
    """按稳定身份连接多源分值，来源键去重，缺项保留并阻断完整总分。"""
    date.fromisoformat(expected_month + "-01")
    ids = {x["id"] for x in roster}
    if len(ids) != len(roster): raise ValueError("人员身份重复")
    totals = {pid: {} for pid in ids}; seen = {}; unknown = []
    for row in sources:
        if row["month"] != expected_month: raise ValueError("统计月份不匹配")
        key = row["source_id"]
        encoded = json.dumps(row, sort_keys=True, allow_nan=False)
        if key in seen:
            if seen[key] != encoded: raise ValueError("来源记录冲突")
            continue
        seen[key] = encoded
        if row["person"] not in ids: unknown.append(row["source_id"]); continue
        if row["metric"] not in weights: raise ValueError("统计指标未配置")
        values = totals[row["person"]]
        values[row["metric"]] = values.get(row["metric"], Decimal(0)) + decimal(row["score"])
    rows = []
    for person in roster:
        values = totals[person["id"]]; missing = sorted(set(weights) - set(values))
        score = decimal(base) + sum((values.get(k, Decimal(0)) * decimal(weight) for k, weight in weights.items()), Decimal(0))
        rows.append({"id": person["id"], "metrics": {k: str(v) for k, v in values.items()}, "missing": missing,
                     "known_subtotal": str(score), "total": None if missing else str(score)})
    return {"rows": rows, "unknown_source_ids": unknown, "month": expected_month}


def rank_scores(rows: list[dict], tiers: list[dict]) -> list[dict]:
    """确定性并列排名与调用方给定分段，缺失分值不参与排名。"""
    if len({x["id"] for x in rows}) != len(rows): raise ValueError("排名身份重复")
    thresholds = [(decimal(x["minimum"]), x["name"]) for x in tiers]
    if len({v for v, _ in thresholds}) != len(thresholds): raise ValueError("等级门槛重复")
    known = sorted([x for x in rows if x.get("score") is not None], key=lambda x: (-decimal(x["score"]), x["id"]))
    result = []; previous = None; rank = 0
    for position, row in enumerate(known, 1):
        value = decimal(row["score"])
        if previous != value: rank = position
        previous = value
        choices = sorted([(minimum, name) for minimum, name in thresholds if value >= minimum])
        result.append({**row, "rank": rank, "tier": choices[-1][1] if choices else None})
    return result + [{**x, "rank": None, "tier": None} for x in rows if x.get("score") is None]


class PointLedger:
    """按来源去重、修订留审计的通用积分账本。"""

    def __init__(self, path: str | Path) -> None:
        """只创建显式本地数据库。"""
        self.path = str(path)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.executescript("CREATE TABLE IF NOT EXISTS points(source TEXT PRIMARY KEY,person TEXT,month TEXT,score TEXT,version INTEGER);CREATE TABLE IF NOT EXISTS audit(source TEXT,version INTEGER,actor TEXT,score TEXT);CREATE TABLE IF NOT EXISTS audit_changes(source TEXT,version INTEGER,old_person TEXT,old_month TEXT,old_score TEXT,new_person TEXT,new_month TEXT,new_score TEXT,actor TEXT);")

    def record(self, source: str, person: str, month: str, score: str, actor: str,
               *, expected_version: int = 0, confirmed: bool = False) -> dict:
        """人工确认后写入，同内容幂等，不同内容必须传当前版本。"""
        if confirmed is not True or not source or not person or not actor: raise ValueError("身份或人工确认缺失")
        date.fromisoformat(month + "-01"); value = str(decimal(score))
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT person,month,score,version FROM points WHERE source=?", (source,)).fetchone()
            if row and tuple(row[:3]) == (person, month, value): return {"source": source, "version": row[3], "reused": True}
            current = row[3] if row else 0
            if current != expected_version: raise ValueError("积分版本冲突")
            db.execute("INSERT OR REPLACE INTO points VALUES(?,?,?,?,?)", (source, person, month, value, current + 1))
            db.execute("INSERT INTO audit VALUES(?,?,?,?)", (source, current + 1, actor, value))
            old=tuple(row[:3]) if row else (None,None,None)
            db.execute("INSERT INTO audit_changes VALUES(?,?,?,?,?,?,?,?,?)", (source,current+1,*old,person,month,value,actor))
            return {"source": source, "version": current + 1, "reused": False}

    def monthly(self, month: str, expected_people: list[str]) -> dict:
        """按月汇总，未出现的人员标记缺失，不以零补齐。"""
        date.fromisoformat(month + "-01"); result = {}
        with closing(sqlite3.connect(self.path)) as db, db:
            for person, score in db.execute("SELECT person,score FROM points WHERE month=?", (month,)):
                result[person] = result.get(person, Decimal(0)) + decimal(score)
        return {"month": month, "rows": [{"id": key, "score": str(value)} for key, value in sorted(result.items())],
                "missing_people": sorted(set(expected_people) - set(result))}


def compare_prices(before: dict, after: dict, cutoff: str) -> dict:
    """比较有效证据价格；结果为候选，不能表示采购决定。"""
    now = datetime.fromisoformat(cutoff)
    if now.tzinfo is None: raise ValueError("截止缺少时区")
    if before["item"] != after["item"] or before["unit"] != after["unit"]: raise ValueError("物品或单位不一致")
    for row in [before, after]:
        captured, valid = datetime.fromisoformat(row["captured_at"]), datetime.fromisoformat(row["valid_until"])
        if captured.tzinfo is None or valid.tzinfo is None or not captured <= now <= valid or not row.get("evidence"): raise ValueError("价格证据过期、未来或不完整")
    a, b = decimal(before["price"], nonnegative=True), decimal(after["price"], nonnegative=True)
    return {"item": before["item"], "delta": str(b - a), "relative_delta": str((b - a) / a) if a else None,
            "state": "candidate", "evidence": [before["evidence"], after["evidence"]]}


def export_csv(rows: list[dict], fields: list[str]) -> str:
    """按显式列导出，防止公式文本被电子表格直接执行。"""
    stream = io.StringIO(); writer = csv.DictWriter(stream, fieldnames=fields); writer.writerow({key:"'"+key if key.startswith(("=","+","-","@","\t","\r")) else key for key in fields})
    for row in rows:
        cleaned = {}
        for key in fields:
            value = row.get(key)
            if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")): value = "'" + value
            cleaned[key] = value
        writer.writerow(cleaned)
    return stream.getvalue()
