import argparse, json
from pathlib import Path
from .engine import analyze_document, apply_plan, validate_document, EngineError
from .bridge import build_autofill_bundle

def load(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def emit(obj, out=None):
    t=json.dumps(obj, ensure_ascii=False, indent=2)
    Path(out).write_text(t, encoding="utf-8") if out else print(t)

def main():
    ap=argparse.ArgumentParser(prog="한글자동작성")
    sp=ap.add_subparsers(dest="cmd", required=True)
    a=sp.add_parser("분석"); a.add_argument("문서"); a.add_argument("-o","--출력")
    p=sp.add_parser("제안"); p.add_argument("분석JSON"); p.add_argument("대화정보JSON"); p.add_argument("-o","--출력")
    e=sp.add_parser("작성"); e.add_argument("문서"); e.add_argument("계획JSON"); e.add_argument("-o","--출력",required=True)
    v=sp.add_parser("검증"); v.add_argument("문서")
    ns=ap.parse_args()
    try:
        if ns.cmd=="분석": emit(analyze_document(ns.문서), ns.출력)
        elif ns.cmd=="제안": emit(build_autofill_bundle(load(ns.분석JSON), load(ns.대화정보JSON)), ns.출력)
        elif ns.cmd=="작성": emit(apply_plan(ns.문서, ns.출력, load(ns.계획JSON)))
        elif ns.cmd=="검증": emit(validate_document(ns.문서))
    except EngineError as e:
        ap.error(str(e))
