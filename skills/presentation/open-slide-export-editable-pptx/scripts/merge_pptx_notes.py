#!/usr/bin/env python3
"""Merge approved speaker notes into a newer PPTX without replacing current slides."""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
NOTES_REL_TYPE = f"{OFFICE_REL_NS}/notesSlide"
NOTES_MASTER_REL_TYPE = f"{OFFICE_REL_NS}/notesMaster"
THEME_REL_TYPE = f"{OFFICE_REL_NS}/theme"

ET.register_namespace("", CT_NS)
ET.register_namespace("", REL_NS)
ET.register_namespace("p", P_NS)
ET.register_namespace("r", OFFICE_REL_NS)


def numeric_parts(names: list[str], pattern: str) -> list[str]:
    regex = re.compile(pattern)
    matches = [name for name in names if regex.fullmatch(name)]
    return sorted(matches, key=lambda name: int(re.search(r"\d+", name.rsplit("/", 1)[-1]).group()))


def next_rid(root: ET.Element) -> str:
    values = []
    for rel in root:
        match = re.fullmatch(r"rId(\d+)", rel.get("Id", ""))
        if match:
            values.append(int(match.group(1)))
    return f"rId{max(values, default=0) + 1}"


def xml_bytes(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def remove_relationships(root: ET.Element, relation_type: str) -> None:
    for rel in list(root):
        if rel.get("Type") == relation_type:
            root.remove(rel)


def add_relationship(root: ET.Element, relation_type: str, target: str) -> str:
    relation_id = next_rid(root)
    ET.SubElement(
        root,
        f"{{{REL_NS}}}Relationship",
        {"Id": relation_id, "Type": relation_type, "Target": target},
    )
    return relation_id


def merge_content_types(current: bytes, notes_source: bytes) -> bytes:
    current_root = ET.fromstring(current)
    source_root = ET.fromstring(notes_source)
    existing = {
        (child.tag, child.get("PartName"), child.get("Extension"))
        for child in current_root
    }
    for child in source_root:
        part_name = child.get("PartName", "")
        if not (
            part_name.startswith("/ppt/notesSlides/")
            or part_name.startswith("/ppt/notesMasters/")
        ):
            continue
        key = (child.tag, child.get("PartName"), child.get("Extension"))
        if key not in existing:
            current_root.append(ET.fromstring(ET.tostring(child)))
            existing.add(key)
    return xml_bytes(current_root)


def build_output(
    input_path: Path,
    notes_source_path: Path,
    output_path: Path,
    *,
    allow_partial: bool,
    force: bool,
    replace_existing_notes: bool,
) -> dict[str, object]:
    if output_path.exists() and not force:
        raise FileExistsError(f"Output already exists: {output_path}. Use --force to replace it.")
    if input_path.resolve() == output_path.resolve():
        raise ValueError("--input and --output must be different files")

    with zipfile.ZipFile(input_path) as current, zipfile.ZipFile(notes_source_path) as source:
        if current.testzip():
            raise ValueError(f"Input PPTX is corrupt: {current.testzip()}")
        if source.testzip():
            raise ValueError(f"Notes source PPTX is corrupt: {source.testzip()}")

        current_names = current.namelist()
        source_names = source.namelist()
        slides = numeric_parts(current_names, r"ppt/slides/slide\d+\.xml")
        current_notes = numeric_parts(current_names, r"ppt/notesSlides/notesSlide\d+\.xml")
        notes = numeric_parts(source_names, r"ppt/notesSlides/notesSlide\d+\.xml")
        if not slides:
            raise ValueError("Input PPTX contains no slides")
        if current_notes and not replace_existing_notes:
            raise ValueError(
                "Input PPTX already contains speaker notes. "
                "Use --replace-existing-notes only after confirming replacement is intended."
            )
        if not notes:
            raise ValueError("Notes source contains no speaker-note parts")
        if not allow_partial and len(slides) != len(notes):
            raise ValueError(
                f"Slide/note count mismatch: input has {len(slides)} slides, notes source has {len(notes)} notes"
            )

        note_count = min(len(slides), len(notes))
        required = {
            "[Content_Types].xml",
            "ppt/notesMasters/notesMaster1.xml",
            "ppt/notesMasters/_rels/notesMaster1.xml.rels",
        }
        missing = sorted(required - set(source_names))
        if missing:
            raise ValueError(f"Notes source is missing required parts: {missing}")
        notes_master_rels = ET.fromstring(
            source.read("ppt/notesMasters/_rels/notesMaster1.xml.rels")
        )
        theme_relationship = next(
            (rel for rel in notes_master_rels if rel.get("Type") == THEME_REL_TYPE),
            None,
        )
        if theme_relationship is None or not theme_relationship.get("Target"):
            raise ValueError("Notes source has no notes-master theme relationship")
        theme_part = posixpath.normpath(
            posixpath.join("ppt/notesMasters", theme_relationship.get("Target", ""))
        )
        if theme_part not in source_names:
            raise ValueError(f"Notes source is missing its notes theme: {theme_part}")
        if theme_part in current_names and current.read(theme_part) != source.read(theme_part):
            raise ValueError(
                f"Input already contains a different {theme_part}; "
                "refusing to overwrite a potentially unrelated theme."
            )

        replacements: dict[str, bytes] = {}
        replacements["[Content_Types].xml"] = merge_content_types(
            current.read("[Content_Types].xml"), source.read("[Content_Types].xml")
        )

        presentation_rels = ET.fromstring(current.read("ppt/_rels/presentation.xml.rels"))
        remove_relationships(presentation_rels, NOTES_MASTER_REL_TYPE)
        notes_master_rid = add_relationship(
            presentation_rels,
            NOTES_MASTER_REL_TYPE,
            "notesMasters/notesMaster1.xml",
        )
        replacements["ppt/_rels/presentation.xml.rels"] = xml_bytes(presentation_rels)

        presentation = ET.fromstring(current.read("ppt/presentation.xml"))
        for existing_list in list(presentation.findall(f"{{{P_NS}}}notesMasterIdLst")):
            presentation.remove(existing_list)
        notes_master_list = ET.Element(f"{{{P_NS}}}notesMasterIdLst")
        ET.SubElement(
            notes_master_list,
            f"{{{P_NS}}}notesMasterId",
            {f"{{{OFFICE_REL_NS}}}id": notes_master_rid},
        )
        slide_master_list = presentation.find(f"{{{P_NS}}}sldMasterIdLst")
        insert_at = list(presentation).index(slide_master_list) + 1 if slide_master_list is not None else 0
        presentation.insert(insert_at, notes_master_list)
        replacements["ppt/presentation.xml"] = xml_bytes(presentation)

        note_parts = {
            name
            for name in source_names
            if name.startswith("ppt/notesSlides/")
            or name.startswith("ppt/notesMasters/")
        }
        if theme_part not in current_names:
            note_parts.add(theme_part)

        for index in range(1, note_count + 1):
            rels_name = f"ppt/slides/_rels/slide{index}.xml.rels"
            if rels_name not in current_names:
                raise ValueError(f"Input PPTX is missing slide relationships: {rels_name}")
            rels_root = ET.fromstring(current.read(rels_name))
            remove_relationships(rels_root, NOTES_REL_TYPE)
            add_relationship(
                rels_root,
                NOTES_REL_TYPE,
                f"../notesSlides/notesSlide{index}.xml",
            )
            replacements[rels_name] = xml_bytes(rels_root)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as output:
            for info in current.infolist():
                if info.filename in note_parts:
                    continue
                output.writestr(info, replacements.get(info.filename, current.read(info.filename)))
            for name in sorted(note_parts):
                match = re.fullmatch(r"ppt/notesSlides(?:/_rels)?/notesSlide(\d+)\.xml(?:\.rels)?", name)
                if match and int(match.group(1)) > note_count:
                    continue
                output.writestr(source.getinfo(name), source.read(name))

    with zipfile.ZipFile(output_path) as check:
        bad = check.testzip()
        if bad:
            raise ValueError(f"Output PPTX is corrupt at {bad}")

    return {
        "ok": True,
        "input": str(input_path),
        "notes_source": str(notes_source_path),
        "output": str(output_path),
        "slides": len(slides),
        "notes": note_count,
        "partial": note_count != len(slides),
        "bytes": output_path.stat().st_size,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--notes-source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--replace-existing-notes", action="store_true")
    args = parser.parse_args()

    try:
        result = build_output(
            args.input,
            args.notes_source,
            args.output,
            allow_partial=args.allow_partial,
            force=args.force,
            replace_existing_notes=args.replace_existing_notes,
        )
    except Exception as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
