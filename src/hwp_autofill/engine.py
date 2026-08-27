from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

class EngineError(RuntimeError):
    pass

def _run(args: list[str], *, capture=True) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            args,
            check=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE if capture else None,
        )
    except FileNotFoundError as e:
        raise EngineError(
            "hwp 실행파일을 찾지 못했습니다. hwp-cli를 설치한 뒤 PATH에 추가하세요."
        ) from e
    except subprocess.CalledProcessError as e:
        raise EngineError(
            f"명령 실행 실패: {' '.join(args)}\nSTDOUT: {e.stdout}\nSTDERR: {e.stderr}"
        ) from e

def find_hwp_binary() -> str:
    configured = os.environ.get("HWP_CLI")
    if configured and Path(configured).exists():
        return configured
    found = shutil.which("hwp")
    if found:
        return found
    raise EngineError("hwp-cli가 설치되어 있지 않습니다.")

def hwp_version() -> str:
    exe = find_hwp_binary()
    for args in ([exe, "--version"], [exe, "info", "--help"]):
        try:
            p = _run(list(args))
            text = (p.stdout or p.stderr or "").strip()
            if text:
                return text.splitlines()[0]
        except Exception:
            pass
    return "설치됨"

def analyze_document(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if path.suffix.lower() not in {".hwp", ".hwpx"}:
        raise EngineError("HWP 또는 HWPX 파일만 지원합니다.")
    if not path.exists():
        raise EngineError(f"파일이 없습니다: {path}")

    exe = find_hwp_binary()
    info_raw = _run([exe, "info", str(path), "--json"]).stdout
    ir_raw = _run([exe, "cat", str(path), "--format", "json"]).stdout
    fields_raw = _run([exe, "fields", str(path), "--json"]).stdout

    def loads_or_text(s: str):
        try:
            return json.loads(s)
        except Exception:
            return {"raw": s}

    ir = loads_or_text(ir_raw)
    return {
        "input": str(path.resolve()),
        "format": path.suffix.lower().lstrip("."),
        "info": loads_or_text(info_raw),
        "fields": loads_or_text(fields_raw),
        "ir": ir,
        "text_candidates": _collect_strings(ir),
        "engine": hwp_version(),
    }

def _collect_strings(obj: Any, limit: int = 5000) -> list[str]:
    out: list[str] = []
    def walk(x: Any):
        if len(out) >= limit:
            return
        if isinstance(x, str):
            s = x.strip()
            if s and s not in out:
                out.append(s)
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(obj)
    return out

def build_edit_command(
    input_path: str | Path,
    output_path: str | Path,
    plan: dict[str, Any],
) -> list[str]:
    exe = find_hwp_binary()
    cmd = [exe, "edit", str(input_path), "-o", str(output_path)]

    for item in plan.get("edits", []):
        action = item.get("action")
        value = str(item.get("value", ""))
        if action == "set_cell":
            locator = item["locator"]
            cmd += ["--set-cell", f"{locator}={value}"]
        elif action == "set_field":
            cmd += ["--set-field", f'{item["field"]}={value}']
        elif action == "replace":
            cmd += ["--replace", f'{item["find"]}=>{value}']
        elif action == "insert_paragraph":
            cmd += ["--insert-para", f'{item["anchor"]}=>{value}']
        else:
            raise EngineError(f"알 수 없는 edit action: {action}")

    for photo in plan.get("photos", []):
        anchor = photo["anchor"]
        image_path = photo["path"]
        size = photo.get("size_mm")
        spec = f"{anchor}=>{image_path}"
        if size:
            spec += f"@{size}"
        cmd += ["--insert-image", spec]

    cmd.append("--verify")
    return cmd

def apply_plan(
    input_path: str | Path,
    output_path: str | Path,
    plan: dict[str, Any],
) -> dict[str, Any]:
    input_path = Path(input_path)
    output_path = Path(output_path)
    if input_path.resolve() == output_path.resolve():
        raise EngineError("원본 파일과 결과 파일 경로는 달라야 합니다.")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = build_edit_command(input_path, output_path, plan)
    p = _run(cmd)
    validation = validate_document(output_path)
    return {
        "output": str(output_path.resolve()),
        "command": cmd,
        "stdout": p.stdout,
        "validation": validation,
    }

def validate_document(path: str | Path) -> dict[str, Any]:
    exe = find_hwp_binary()
    p = _run([exe, "validate", str(path), "--json"])
    try:
        return json.loads(p.stdout)
    except Exception:
        return {"raw": p.stdout, "valid": True}

def render_preview(path: str | Path, output_png: str | Path, page: int = 1, dpi: int = 120):
    exe = find_hwp_binary()
    cmd = [
        exe, "render", str(path), "-o", str(output_png),
        "--pages", str(page), "--dpi", str(dpi), "--format", "png"
    ]
    _run(cmd)
    return str(Path(output_png).resolve())
