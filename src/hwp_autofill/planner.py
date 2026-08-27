from __future__ import annotations
from typing import Any
import re

ALIASES = {
    "프로그램명": ["프로그램명","교육명","강의명","과정명","사업명","행사명","주제"],
    "일시": ["일시","교육일","강의일","날짜","운영일","일자"],
    "장소": ["장소","교육장소","강의장소","위치","개최장소"],
    "대상": ["대상","교육대상","참여대상","참가대상"],
    "인원": ["인원","교육인원","참여인원","참가자수","참석자수"],
    "내용": ["내용","강의내용","교육내용","주요내용","세부내용","활동내용","주요 활동"],
    "목표": ["목표","교육목표","운영목표"],
    "강사명": ["강사명","강사","성명","담당강사"],
    "연락처": ["연락처","전화번호","휴대전화","휴대폰"],
    "준비물": ["준비물","재료","준비 사항"],
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
            if n == nv or (len(nv) >= 2 and (n in nv or nv in n)):
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

def make_proposal(field: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    label = field.get("label", "")
    key = canonical(label)
    proposed = facts.get(key, "") if key else ""
    current = str(field.get("current_value", "") or "")
    return {
        "field_id": field.get("field_id"),
        "label": label,
        "canonical": key,
        "current_value": current,
        "proposed_value": proposed,
        "source": "conversation" if proposed else None,
        "confidence": 1.0 if proposed and key else 0.0,
        "action": compare_values(current, str(proposed)),
        "locator": field.get("locator"),
    }
