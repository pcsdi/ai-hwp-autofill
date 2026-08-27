from __future__ import annotations
import argparse, json
from pathlib import Path
from .engine import analyze_document, apply_plan, validate_document, render_preview, EngineError

def _load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def main():
    ap = argparse.ArgumentParser(prog="한글자동작성", description="HWP/HWPX 대화형 자동작성 엔진")
    sp = ap.add_subparsers(dest="cmd", required=True)

    a = sp.add_parser("분석")
    a.add_argument("문서")
    a.add_argument("-o", "--출력")

    e = sp.add_parser("작성")
    e.add_argument("문서")
    e.add_argument("계획")
    e.add_argument("-o", "--출력", required=True)

    v = sp.add_parser("검증")
    v.add_argument("문서")

    r = sp.add_parser("미리보기")
    r.add_argument("문서")
    r.add_argument("-o", "--출력", required=True)
    r.add_argument("--페이지", type=int, default=1)

    ns = ap.parse_args()
    try:
        if ns.cmd == "분석":
            result = analyze_document(ns.문서)
            text = json.dumps(result, ensure_ascii=False, indent=2)
            if ns.출력:
                Path(ns.출력).write_text(text, encoding="utf-8")
            else:
                print(text)
        elif ns.cmd == "작성":
            plan = _load_json(ns.계획)
            print(json.dumps(apply_plan(ns.문서, ns.출력, plan), ensure_ascii=False, indent=2))
        elif ns.cmd == "검증":
            print(json.dumps(validate_document(ns.문서), ensure_ascii=False, indent=2))
        elif ns.cmd == "미리보기":
            print(render_preview(ns.문서, ns.출력, ns.페이지))
    except EngineError as ex:
        ap.error(str(ex))

if __name__ == "__main__":
    main()
