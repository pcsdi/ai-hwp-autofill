from __future__ import annotations
import json, os, shutil, subprocess
from pathlib import Path
from typing import Any
from .extractor import infer_fields_from_ir, infer_fields_from_text

class EngineError(RuntimeError):
    pass

def _run(args):
    try:
        return subprocess.run(args, check=True, text=True, encoding="utf-8", errors="replace",
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError as e:
        raise EngineError("hwp 실행파일을 찾지 못했습니다. HWP_CLI 또는 PATH를 확인하세요.") from e
    except subprocess.CalledProcessError as e:
        raise EngineError(f"명령 실행 실패: {' '.join(args)}\nSTDOUT: {e.stdout}\nSTDERR: {e.stderr}") from e

def find_hwp_binary():
    configured = os.environ.get("HWP_CLI")
    if configured and Path(configured).exists():
        return configured
    for name in ("hwp","hwp.exe"):
        found = shutil.which(name)
        if found:
            return found
    raise EngineError("hwp-cli가 설치되어 있지 않거나 PATH/HWP_CLI 설정이 없습니다.")

def hwp_version():
    p = _run([find_hwp_binary(), "--version"])
    return (p.stdout or p.stderr or "").strip()

def _loads_or_text(s):
    try:
        return json.loads(s)
    except Exception:
        return {"raw": s}

def _collect_strings(obj: Any, limit=5000):
    out = []
    def walk(x):
        if len(out) >= limit: return
        if isinstance(x, str):
            s=x.strip()
            if s and s not in out: out.append(s)
        elif isinstance(x, dict):
            for v in x.values(): walk(v)
        elif isinstance(x, list):
            for v in x: walk(v)
    walk(obj); return out

def analyze_document(path):
    path = Path(path)
    if path.suffix.lower() not in {".hwp",".hwpx"}:
        raise EngineError("HWP 또는 HWPX 파일만 지원합니다.")
    exe = find_hwp_binary()
    info_text = _run([exe,"info",str(path)]).stdout
    try:
        ir = _loads_or_text(_run([exe,"cat",str(path),"--format","json"]).stdout)
    except EngineError:
        ir = {"raw_text": _run([exe,"cat",str(path)]).stdout}
    try:
        native_fields = _loads_or_text(_run([exe,"fields",str(path),"--json"]).stdout)
    except EngineError:
        native_fields = {}
    text_candidates = _collect_strings(ir)
    if "raw_text" in ir:
        text_candidates = [x.strip() for x in ir["raw_text"].splitlines() if x.strip()]
    fields = infer_fields_from_ir(ir) or infer_fields_from_text(text_candidates)
    return {
        "input": str(path.resolve()),
        "format": path.suffix.lower().lstrip("."),
        "engine": hwp_version(),
        "info_text": info_text,
        "native_fields": native_fields,
        "fields": fields,
        "text_candidates": text_candidates[:1000],
    }

def build_edit_command(input_path, output_path, plan):
    exe = find_hwp_binary()
    cmd = [exe,"edit",str(input_path),"-o",str(output_path)]
    for item in plan.get("edits", []):
        action=item.get("action"); value=str(item.get("value",""))
        if action=="set_cell":
            cmd += ["--set-cell", f'{item["locator"]}={value}']
        elif action=="set_field":
            cmd += ["--set-field", f'{item["field"]}={value}']
        elif action=="replace":
            cmd += ["--replace", f'{item["find"]}=>{value}']
        elif action=="insert_paragraph":
            cmd += ["--insert-para", f'{item["anchor"]}=>{value}']
        else:
            raise EngineError(f"알 수 없는 edit action: {action}")
    for photo in plan.get("photos", []):
        spec = f'{photo["anchor"]}=>{photo["path"]}'
        if photo.get("size_mm"): spec += f'@{photo["size_mm"]}'
        cmd += ["--insert-image", spec]
    if plan.get("verify", True): cmd.append("--verify")
    return cmd

def apply_plan(input_path, output_path, plan):
    input_path, output_path = Path(input_path), Path(output_path)
    if input_path.resolve()==output_path.resolve():
        raise EngineError("원본 파일과 결과 파일 경로는 달라야 합니다.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    p=_run(build_edit_command(input_path,output_path,plan))
    return {"output":str(output_path.resolve()),"stdout":p.stdout,"stderr":p.stderr,
            "validation": validate_document(output_path)}

def validate_document(path):
    exe=find_hwp_binary()
    try:
        return _loads_or_text(_run([exe,"validate",str(path),"--json"]).stdout)
    except EngineError:
        info=_run([exe,"info",str(path)]).stdout
        _run([exe,"cat",str(path)])
        return {"available":True,"valid":True,"method":"reopen","info":info}
