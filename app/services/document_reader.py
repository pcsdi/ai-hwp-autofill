from __future__ import annotations
from pathlib import Path
from typing import Any


def read_document(path: str) -> dict[str, Any]:
    """HWP/HWPX 문서에서 텍스트/표 정보를 최대한 추출한다."""
    p = Path(path)
    ext = p.suffix.lower()
    result: dict[str, Any] = {"file_name": p.name, "ext": ext, "text": "", "tables": [], "errors": []}

    try:
        from hwp_hwpx_parser import HWPParser, HWPXParser  # type: ignore
        parser = HWPXParser(str(p)) if ext == ".hwpx" else HWPParser(str(p))
        if hasattr(parser, "extract_text"):
            result["text"] = parser.extract_text() or ""
        elif hasattr(parser, "get_text"):
            result["text"] = parser.get_text() or ""
        if hasattr(parser, "extract_tables"):
            result["tables"] = _normalize_tables(parser.extract_tables() or [])
        elif hasattr(parser, "get_tables"):
            result["tables"] = _normalize_tables(parser.get_tables() or [])
        return result
    except Exception as e:
        result["errors"].append(f"parser: {e}")

    if ext == ".hwpx":
        try:
            import zipfile
            from lxml import etree
            texts: list[str] = []
            tables: list[list[list[str]]] = []
            with zipfile.ZipFile(p, "r") as z:
                sections = sorted(n for n in z.namelist() if n.startswith("Contents/section") and n.endswith(".xml"))
                for name in sections:
                    root = etree.fromstring(z.read(name))
                    for node in root.xpath('//*[local-name()="t"]'):
                        if node.text:
                            texts.append(node.text)
                    for tbl in root.xpath('//*[local-name()="tbl"]'):
                        rows = []
                        for tr in tbl.xpath('.//*[local-name()="tr"]'):
                            row = []
                            for tc in tr.xpath('./*[local-name()="tc"]'):
                                cell_text = "".join(tc.xpath('.//*[local-name()="t"]/text()')).strip()
                                row.append(cell_text)
                            if row:
                                rows.append(row)
                        if rows:
                            tables.append(rows)
            result["text"] = "\n".join(texts)
            result["tables"] = tables
        except Exception as e:
            result["errors"].append(f"hwpx_fallback: {e}")
    return result


def _normalize_tables(tables: Any) -> list:
    normalized = []
    for table in tables:
        if isinstance(table, list):
            normalized.append(table)
        elif hasattr(table, "to_list"):
            normalized.append(table.to_list())
        else:
            normalized.append(str(table))
    return normalized
