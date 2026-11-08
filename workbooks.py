"""作者：Wangyuan；日期：2026-10-29；职责：显式表头导入与保持公式样式的中性表格回填。"""
from __future__ import annotations

import zipfile
from datetime import date,datetime,time
from pathlib import Path
from typing import Any


def check_workbook(path: str | Path) -> None:
    """限制XLSX包预算并拒绝外部链接和宏。"""
    target = Path(path)
    if target.suffix.lower() != ".xlsx" or target.stat().st_size > 20_000_000: raise ValueError("仅接受预算内XLSX")
    with zipfile.ZipFile(target) as archive:
        entries = archive.infolist()
        if len(entries) > 3000 or sum(x.file_size for x in entries) > 100_000_000: raise ValueError("工作簿展开预算超限")
        for item in entries:
            if ".." in item.filename.replace("\\", "/").split("/") or item.filename.startswith("/") or "vbaproject" in item.filename.lower() or "externallinks" in item.filename.lower(): raise ValueError("不接受外部链接、宏或异常路径")
            if item.file_size > 200 * max(1, item.compress_size): raise ValueError("压缩比超限")


def header_map(worksheet: Any, columns: dict[str, str], header_row: int | None = None) -> tuple[int, dict[str, int]]:
    """按调用方明确列名匹配表头；重名列或缺列拒绝。"""
    if not columns or len(set(columns.values())) != len(columns): raise ValueError("列合同为空或重复")
    rows = [header_row] if header_row is not None else range(1, min(worksheet.max_row, 10) + 1)
    for index in rows:
        if type(index) is not int or not 1 <= index <= worksheet.max_row: raise ValueError("表头行无效")
        values = [str(cell.value).strip() if cell.value is not None else "" for cell in worksheet[index]]
        if set(columns.values()) <= set(values):
            if any(values.count(label) != 1 for label in columns.values()): raise ValueError("表头重名")
            return index, {key: values.index(label) + 1 for key, label in columns.items()}
    raise ValueError("没有匹配完整列合同的表头")


def read_xlsx(path: str | Path, sheet: str, columns: dict[str, str], header_row: int | None = None) -> list[dict]:
    """导入用户指定的多源表格，缺值保持None，不猜姓名或业务口径。"""
    from openpyxl import load_workbook
    check_workbook(path); workbook = load_workbook(path, read_only=True, data_only=True, keep_links=False)
    try:
        if sheet not in workbook.sheetnames: raise ValueError("工作表不存在")
        worksheet = workbook[sheet]
        if worksheet.max_row > 100_000 or worksheet.max_column > 200: raise ValueError("工作表规模超限")
        row_number, mapping = header_map(worksheet, columns, header_row); output = []
        for index, values in enumerate(worksheet.iter_rows(min_row=row_number + 1, values_only=True), row_number + 1):
            if not any(value is not None for value in values): continue
            output.append({**{key: values[col - 1].isoformat() if isinstance(values[col - 1],(date,datetime,time)) else values[col - 1] for key, col in mapping.items()}, "_source_row": index})
        return output
    finally:
        workbook.close()


def fill_template(template: str | Path, output: str | Path, sheet: str, rows: list[dict],
                  identity_header: str, destinations: dict[str, str], header_row: int | None = None) -> dict:
    """按稳定身份回填指定列，其他公式/样式保留，禁止覆盖输入模板。"""
    from openpyxl import load_workbook
    if Path(template).resolve() == Path(output).resolve() or Path(output).exists() and Path(template).samefile(output): raise ValueError("不能覆盖输入")
    check_workbook(template)
    if not destinations or "id" in destinations: raise ValueError("回填列合同无效")
    index = {}
    for row in rows:
        identifier = str(row["id"]).strip()
        if not identifier or identifier in index: raise ValueError("回填身份缺失或重复")
        index[identifier] = row
    workbook = load_workbook(template, keep_links=False)
    try:
        if sheet not in workbook.sheetnames: raise ValueError("工作表不存在")
        worksheet = workbook[sheet]
        head, mapping = header_map(worksheet, {"id": identity_header, **destinations}, header_row)
        seen = set(); written = []
        for number in range(head + 1, worksheet.max_row + 1):
            raw = worksheet.cell(number, mapping["id"]).value
            if raw is None: continue
            identifier = str(raw).strip()
            if identifier in seen: raise ValueError("模板身份重复")
            seen.add(identifier)
            if identifier not in index: continue
            for field in destinations:
                value = index[identifier].get(field)
                if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
                    value = "'" + value
                worksheet.cell(number, mapping[field]).value = value
            written.append(identifier)
        missing = sorted(set(index) - seen)
        if missing: raise ValueError("模板缺少部分身份，未保存")
        workbook.save(output)
        return {"output": Path(output).name, "updated": sorted(written)}
    finally:
        workbook.close()


def export_xlsx(rows: list[dict], fields: list[str], output: str | Path) -> dict:
    """从零输出可筛选的中性Excel表，转义公式文本。"""
    from openpyxl import Workbook
    if not fields or len(set(fields)) != len(fields): raise ValueError("导出列无效")
    workbook = Workbook(); worksheet = workbook.active; worksheet.title = "结果"; worksheet.append(["\'" + value if value.startswith(("=", "+", "-", "@", "\t", "\r")) else value for value in fields])
    for row in rows:
        values = [row.get(key) for key in fields]
        worksheet.append(["'" + value if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")) else value for value in values])
    worksheet.freeze_panes = "A2"; worksheet.auto_filter.ref = worksheet.dimensions
    workbook.save(output); workbook.close()
    return {"output": Path(output).name, "rows": len(rows)}
