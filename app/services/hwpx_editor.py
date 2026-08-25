from __future__ import annotations
import copy
import mimetypes
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any
from lxml import etree


def apply_text_matches(src: str, dst: str, matches: list[dict[str, Any]]) -> dict[str, Any]:
    """HWPX 표에서 라벨 다음 빈 셀을 찾아 값을 삽입한다. 실패 시 원본 유지."""
    src_p, dst_p = Path(src), Path(dst)
    if src_p.suffix.lower() != ".hwpx":
        raise ValueError("현재 자동 편집 출력은 HWPX만 지원합니다.")
    shutil.copy2(src_p, dst_p)
    report = {"applied": [], "skipped": []}

    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        with zipfile.ZipFile(dst_p, "r") as zin:
            zin.extractall(work)
        section_files = sorted((work / "Contents").glob("section*.xml"))
        for match in matches:
            done = False
            for sec in section_files:
                parser = etree.XMLParser(remove_blank_text=False, recover=True)
                root = etree.parse(str(sec), parser)
                if _fill_label_adjacent_cell(root, match["document_label"], match["value"]):
                    root.write(str(sec), encoding="UTF-8", xml_declaration=True, pretty_print=False)
                    report["applied"].append(match)
                    done = True
                    break
            if not done:
                report["skipped"].append(match)
        _repack(work, dst_p)
    return report


def _fill_label_adjacent_cell(tree: etree._ElementTree, label: str, value: str) -> bool:
    root = tree.getroot()
    for t in root.xpath('//*[local-name()="t"]'):
        if (t.text or "").strip() != label.strip():
            continue
        tc = _ancestor_local(t, "tc")
        if tc is None:
            continue
        tr = _ancestor_local(tc, "tr")
        if tr is None:
            continue
        cells = [c for c in tr if etree.QName(c).localname == "tc"]
        try:
            idx = cells.index(tc)
        except ValueError:
            continue
        for target in cells[idx + 1:]:
            texts = target.xpath('.//*[local-name()="t"]')
            current = "".join((x.text or "") for x in texts).strip()
            if current == "":
                if texts:
                    texts[0].text = value
                else:
                    _append_text_run(target, value)
                return True
    return False


def _ancestor_local(node: etree._Element, local: str):
    p = node.getparent()
    while p is not None:
        if etree.QName(p).localname == local:
            return p
        p = p.getparent()
    return None


def _append_text_run(tc: etree._Element, value: str):
    p = next(iter(tc.xpath('.//*[local-name()="p"]')), None)
    if p is not None:
        run = next(iter(p.xpath('./*[local-name()="run"]')), None)
        if run is not None:
            new_run = copy.deepcopy(run)
            for child in list(new_run):
                if etree.QName(child).localname == "t":
                    child.text = value
            p.append(new_run)


def insert_images_near_photo_labels(src: str, dst: str, image_paths: list[str]) -> dict[str, Any]:
    """사진을 HWPX 패키지에 등록하고 기존 그림 문단 형식을 복제해 문서 끝에 삽입하는 v1 기능."""
    if not image_paths:
        shutil.copy2(src, dst)
        return {"inserted": 0, "mode": "none"}
    shutil.copy2(src, dst)
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        with zipfile.ZipFile(dst, "r") as zin:
            zin.extractall(work)
        bindata = work / "BinData"
        bindata.mkdir(exist_ok=True)
        manifest = work / "Contents" / "content.hpf"
        sections = sorted((work / "Contents").glob("section*.xml"))
        if not manifest.exists() or not sections:
            _repack(work, Path(dst))
            return {"inserted": 0, "mode": "unsupported_structure"}
        section = sections[0]
        m_tree = etree.parse(str(manifest))
        s_tree = etree.parse(str(section))
        s_root = s_tree.getroot()
        inserted = 0
        for image_path in image_paths:
            src_img = Path(image_path)
            ext = src_img.suffix.lower() or ".png"
            item_id = _next_image_id(m_tree)
            file_name = f"{item_id}{ext}"
            shutil.copy2(src_img, bindata / file_name)
            _append_manifest_item(m_tree, item_id, f"BinData/{file_name}", mimetypes.guess_type(file_name)[0] or "image/png")
            para = _make_image_para(s_root, item_id)
            if para is not None:
                s_root.append(para)
                inserted += 1
        m_tree.write(str(manifest), encoding="UTF-8", xml_declaration=True, pretty_print=False)
        s_tree.write(str(section), encoding="UTF-8", xml_declaration=True, pretty_print=False)
        _repack(work, Path(dst))
    return {"inserted": inserted, "mode": "append_end_v1"}


def _next_image_id(tree: etree._ElementTree) -> str:
    ids = set(tree.xpath('//@id'))
    n = 1
    while f"image{n}" in ids:
        n += 1
    return f"image{n}"


def _append_manifest_item(tree: etree._ElementTree, item_id: str, href: str, media_type: str):
    root = tree.getroot()
    manifest = next(iter(root.xpath('//*[local-name()="manifest"]')), None)
    if manifest is None:
        return
    ns = etree.QName(manifest).namespace
    tag = f"{{{ns}}}item" if ns else "item"
    item = etree.Element(tag)
    item.set("id", item_id)
    item.set("href", href)
    item.set("media-type", media_type)
    manifest.append(item)


def _make_image_para(root: etree._Element, item_id: str):
    pics = root.xpath('//*[local-name()="pic"]')
    if not pics:
        return None
    pic = copy.deepcopy(pics[0])
    for el in pic.iter():
        for attr in list(el.attrib):
            if attr.endswith("binaryItemIDRef") or attr == "binaryItemIDRef":
                el.set(attr, item_id)
    p = _ancestor_local(pics[0], "p")
    if p is None:
        return None
    p_copy = copy.deepcopy(p)
    old_pics = p_copy.xpath('.//*[local-name()="pic"]')
    if old_pics:
        old = old_pics[0]
        old.getparent().replace(old, pic)
    return p_copy


def _repack(work: Path, dst: Path):
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        mimetype = work / "mimetype"
        if mimetype.exists():
            zout.write(mimetype, "mimetype", compress_type=zipfile.ZIP_STORED)
        for f in work.rglob("*"):
            if f.is_file() and f.name != "mimetype":
                zout.write(f, f.relative_to(work).as_posix())
    tmp.replace(dst)
