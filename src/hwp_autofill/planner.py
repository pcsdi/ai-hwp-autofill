from __future__ import annotations
from typing import Any
import re

ALIASES = {
    "프로그램명": ["프로그램명","교육명","강의명","과정명","사업명","행사명","주제","프로그램명(주제)"],
    "일시": ["일시","교육일","교육일시","강의일","강의일시","날짜","운영일","일자"],
    "장소": ["장소","교육장소","강의장소","위치","개최장소"],
    "대상": ["대상","교육대상","참여대상","참가대상","수강대상"],
    "인원": ["인원","교육인원","참여인원","참가자수","참석자수","수강인원"],
    "내용": ["내용","강의내용","교육내용","주요내용","세부내용","활동내용","주요활동","프로그램내용"],
    "목표": ["목표","교육목표","운영목표","학습목표"],
    "강사명": ["강사명","강사","성명","담당강사","강사성명"],
    "연락처": ["연락처","전화번호","휴대전화","휴대폰","연락처(휴대전화)"],
    "준비물": ["준비물","재료","준비사항","준비 사항"],
    "기관명": ["기관명","학교명","기관","소속기관"],
    "담당자": ["담당자","담당","담당자명"],
}

def normalize(s: str) -> str:
    return re.sub(r"[\s:：()（）\[\]{}\-_/.,·]+", "", s or "").lower()

def canonical(label: str) -> str | None:
    n = normalize(label)
    if not n:
        return None
    for key, vals in ALIASES.items():
        for v in vals:
            nv = normalize(v)
            if n == nv or (len(n) >= 2 and len(nv) >= 2 and (n in nv or nv in n)):
                return key
    return None

def compare_values(current: str, proposed: str) -> str:
    c, p = (current or "").strip(), (proposed or "").strip()
    if not p:
        return "review"
    if not c:
        return "fill"
    if normalize(c) == normalize(p):
        return "keep"
    return "replace"

def resolve_fact(facts: dict[str, Any], key: str | None):
    if not key:
        return "", None, 0.0
    raw = facts.get(key)
    if raw is None:
        return "", None, 0.0
    if isinstance(raw, dict):
        value = str(raw.get("value", "") or "")
        return value, raw.get("source") or "conversation", float(raw.get("confidence", 1.0 if value else 0.0))
    return str(raw), "conversation", 1.0

def make_proposal(field: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    label = field.get("label", "")
    key = canonical(label)
    proposed, source, confidence = resolve_fact(facts, key)
    current = str(field.get("current_value", "") or "")
    return {
        "field_id": field.get("field_id"),
        "label": label,
        "canonical": key,
        "current_value": current,
        "proposed_value": proposed,
        "source": source,
        "confidence": confidence,
        "action": compare_values(current, proposed),
        "locator": field.get("locator"),
        "field_name": field.get("field_name"),
    }

def build_proposals(fields, facts):
    proposals = [make_proposal(f, facts) for f in fields]
    return {
        "proposals": proposals,
        "missing": [p["label"] for p in proposals if p["action"] == "review"],
        "replacements": [p for p in proposals if p["action"] == "replace"],
        "fills": [p for p in proposals if p["action"] == "fill"],
        "keeps": [p for p in proposals if p["action"] == "keep"],
    }

def proposals_to_plan(bundle):
    edits = []
    for p in bundle.get("proposals", []):
        if p.get("action") not in {"fill","replace"} or not p.get("proposed_value"):
            continue
        if p.get("field_name"):
            edits.append({"action":"set_field","field":p["field_name"],"value":p["proposed_value"],"label":p.get("label")})
        elif p.get("locator"):
            edits.append({"action":"set_cell","locator":p["locator"],"value":p["proposed_value"],"label":p.get("label")})
        elif p.get("current_value"):
            edits.append({"action":"replace","find":p["current_value"],"value":p["proposed_value"],"label":p.get("label")})
    return {"edits": edits, "photos": [], "verify": True}
