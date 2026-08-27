from __future__ import annotations
from typing import Any
from .planner import canonical

def _iter_nodes(x: Any):
    if isinstance(x, dict):
        yield x
        for v in x.values():
            yield from _iter_nodes(v)
    elif isinstance(x, list):
        for v in x:
            yield from _iter_nodes(v)

def infer_fields_from_ir(ir: Any):
    fields, seen = [], set()
    for node in _iter_nodes(ir):
        label = None
        for k in ("label","name","title","text","caption"):
            v = node.get(k)
            if isinstance(v, str) and canonical(v):
                label = v.strip()
                break
        if not label:
            continue
        current, locator, field_name = "", None, None
        for k in ("value","current_value","content","text_value"):
            v = node.get(k)
            if isinstance(v, str) and v.strip() != label:
                current = v.strip(); break
        if all(k in node for k in ("table_index","row","col")):
            locator = f'{node["table_index"]}:{node["row"]}:{node["col"]}'
        elif isinstance(node.get("locator"), str):
            locator = node["locator"]
        if isinstance(node.get("field_name"), str):
            field_name = node["field_name"]
        elif isinstance(node.get("field"), str):
            field_name = node["field"]
        sig = (label, locator, field_name)
        if sig in seen:
            continue
        seen.add(sig)
        fields.append({
            "field_id": f"f{len(fields)+1}",
            "label": label,
            "current_value": current,
            "locator": locator,
            "field_name": field_name,
            "confidence": 0.9 if (locator or field_name) else 0.6
        })
    return fields

def infer_fields_from_text(text_candidates):
    fields, seen = [], set()
    for s in text_candidates:
        t = s.strip()
        if len(t) <= 20 and canonical(t) and t not in seen:
            seen.add(t)
            fields.append({
                "field_id": f"t{len(fields)+1}",
                "label": t,
                "current_value": "",
                "locator": None,
                "field_name": None,
                "confidence": 0.4,
                "note": "텍스트 기반 후보 — 자동쓰기 전 사용자 확인 필요"
            })
    return fields
