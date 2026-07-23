#!/usr/bin/env python3
"""Validate an editable Open Slide PPTX package."""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NOTES_REL_TYPE = f"{OFFICE_REL_NS}/notesSlide"
SLIDE_REL_TYPE = f"{OFFICE_REL_NS}/slide"
NOTES_MASTER_REL_TYPE = f"{OFFICE_REL_NS}/notesMaster"
THEME_REL_TYPE = f"{OFFICE_REL_NS}/theme"
NS = {"p": P_NS, "a": A_NS, "r": REL_NS}


def numeric_parts(names: list[str], pattern: str) -> list[str]:
    regex = re.compile(pattern)
    matches = [name for name in names if regex.fullmatch(name)]
    return sorted(matches, key=lambda name: int(re.search(r"\d+", name.rsplit("/", 1)[-1]).group()))


def part_number(name: str) -> int:
    match = re.search(r"(\d+)\.xml$", name)
    if match is None:
        raise ValueError(f"Part has no numeric suffix: {name}")
    return int(match.group(1))


def relationships_part(source_part: str) -> str:
    directory, filename = posixpath.split(source_part)
    return posixpath.join(directory, "_rels", f"{filename}.rels")


def resolve_target(source_part: str, target: str) -> str:
    if target.startswith("/"):
        return posixpath.normpath(target.lstrip("/"))
    return posixpath.normpath(posixpath.join(posixpath.dirname(source_part), target))


def validate(
    path: Path,
    require_notes: bool,
    reject_image_only: bool,
    expected_slides: int | None,
) -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []
    slides_report: list[dict[str, object]] = []

    if not path.is_file():
        return {"ok": False, "errors": [f"File not found: {path}"], "warnings": []}

    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as error:
        return {"ok": False, "errors": [f"Invalid ZIP package: {error}"], "warnings": []}

    with archive:
        bad = archive.testzip()
        if bad:
            errors.append(f"Corrupt ZIP member: {bad}")

        names = archive.namelist()
        slides = numeric_parts(names, r"ppt/slides/slide\d+\.xml")
        notes = numeric_parts(names, r"ppt/notesSlides/notesSlide\d+\.xml")
        if not slides:
            errors.append("No slide XML parts found")
        if expected_slides is not None and len(slides) != expected_slides:
            errors.append(f"Expected {expected_slides} slides, found {len(slides)}")

        ratio = None
        notes_master_id = None
        if "ppt/presentation.xml" not in names:
            errors.append("Missing ppt/presentation.xml")
        else:
            presentation = ET.fromstring(archive.read("ppt/presentation.xml"))
            size = presentation.find("p:sldSz", NS)
            if size is None:
                errors.append("Presentation has no slide-size declaration")
            else:
                width = int(size.get("cx", "0"))
                height = int(size.get("cy", "0"))
                ratio = width / height if height else None
                if ratio is None or abs(ratio - (16 / 9)) > 0.01:
                    errors.append(f"Slide canvas is not 16:9: {width}x{height}")
            notes_master = presentation.find("p:notesMasterIdLst/p:notesMasterId", NS)
            if notes_master is not None:
                notes_master_id = notes_master.get(f"{{{OFFICE_REL_NS}}}id")

        notes_master_relationship = False
        notes_master_part = None
        presentation_rels_name = "ppt/_rels/presentation.xml.rels"
        if presentation_rels_name not in names:
            errors.append(f"Missing {presentation_rels_name}")
        else:
            presentation_rels = ET.fromstring(archive.read(presentation_rels_name))
            matching_master_rels = [
                rel
                for rel in presentation_rels
                if rel.get("Type") == NOTES_MASTER_REL_TYPE
                and (notes_master_id is None or rel.get("Id") == notes_master_id)
            ]
            if len(matching_master_rels) > 1:
                errors.append("Presentation has multiple matching notes-master relationships")
            if matching_master_rels:
                master_target = matching_master_rels[0].get("Target", "")
                notes_master_part = resolve_target("ppt/presentation.xml", master_target)
                notes_master_relationship = notes_master_part in names
                if not notes_master_relationship:
                    errors.append(
                        f"Presentation notes-master target does not resolve: {master_target}"
                    )

        image_only_pages: list[int] = []
        notes_relationships = 0
        slide_note_targets: dict[int, str] = {}
        for slide_name in slides:
            index = part_number(slide_name)
            root = ET.fromstring(archive.read(slide_name))
            shapes = len(root.findall(".//p:sp", NS))
            pictures = len(root.findall(".//p:pic", NS))
            graphics = len(root.findall(".//p:graphicFrame", NS))
            connectors = len(root.findall(".//p:cxnSp", NS))
            groups = len(root.findall(".//p:grpSp", NS))
            text_chars = sum(len(node.text or "") for node in root.findall(".//a:t", NS))
            editable_objects = shapes + pictures + graphics + connectors + groups
            image_only = pictures > 0 and text_chars == 0 and graphics == 0
            if image_only:
                image_only_pages.append(index)
            if editable_objects == 0:
                errors.append(f"Slide {index} has no editable objects")

            rels_name = relationships_part(slide_name)
            has_notes_rel = False
            if rels_name not in names:
                errors.append(f"Slide {index} is missing its relationships file")
            else:
                rels_root = ET.fromstring(archive.read(rels_name))
                note_rels = [rel for rel in rels_root if rel.get("Type") == NOTES_REL_TYPE]
                if len(note_rels) > 1:
                    errors.append(f"Slide {index} has multiple notes relationships")
                if note_rels:
                    target = note_rels[0].get("Target", "")
                    resolved = resolve_target(slide_name, target)
                    expected_note = f"ppt/notesSlides/notesSlide{index}.xml"
                    if resolved not in names:
                        errors.append(
                            f"Slide {index} notes target does not resolve: {target}"
                        )
                    elif resolved != expected_note:
                        errors.append(
                            f"Slide {index} points to {resolved}, expected {expected_note}"
                        )
                    else:
                        has_notes_rel = True
                        slide_note_targets[index] = resolved
                if has_notes_rel:
                    notes_relationships += 1

            slides_report.append(
                {
                    "page": index,
                    "shapes": shapes,
                    "pictures": pictures,
                    "graphics": graphics,
                    "connectors": connectors,
                    "groups": groups,
                    "text_chars": text_chars,
                    "notes_relationship": has_notes_rel,
                    "image_only": image_only,
                }
            )

        valid_note_relationships = 0
        for note_name in notes:
            index = part_number(note_name)
            rels_name = relationships_part(note_name)
            if rels_name not in names:
                errors.append(f"Note {index} is missing its relationships file")
                continue

            rels_root = ET.fromstring(archive.read(rels_name))
            slide_rels = [rel for rel in rels_root if rel.get("Type") == SLIDE_REL_TYPE]
            master_rels = [
                rel for rel in rels_root if rel.get("Type") == NOTES_MASTER_REL_TYPE
            ]
            if len(slide_rels) != 1:
                errors.append(
                    f"Note {index} must have exactly one slide relationship, found {len(slide_rels)}"
                )
            if len(master_rels) != 1:
                errors.append(
                    f"Note {index} must have exactly one notes-master relationship, found {len(master_rels)}"
                )

            relationships_valid = True
            if slide_rels:
                target = slide_rels[0].get("Target", "")
                resolved = resolve_target(note_name, target)
                expected_slide = f"ppt/slides/slide{index}.xml"
                if resolved not in names:
                    errors.append(f"Note {index} slide target does not resolve: {target}")
                    relationships_valid = False
                elif resolved != expected_slide:
                    errors.append(
                        f"Note {index} points to {resolved}, expected {expected_slide}"
                    )
                    relationships_valid = False
            else:
                relationships_valid = False

            if master_rels:
                target = master_rels[0].get("Target", "")
                resolved = resolve_target(note_name, target)
                if resolved not in names:
                    errors.append(
                        f"Note {index} notes-master target does not resolve: {target}"
                    )
                    relationships_valid = False
                elif notes_master_part is not None and resolved != notes_master_part:
                    errors.append(
                        f"Note {index} points to notes master {resolved}, "
                        f"expected {notes_master_part}"
                    )
                    relationships_valid = False
            else:
                relationships_valid = False

            if slide_note_targets.get(index) != note_name:
                errors.append(
                    f"Note {index} is not the resolved notes target of slide {index}"
                )
                relationships_valid = False
            if relationships_valid:
                valid_note_relationships += 1

        notes_master_theme_relationship = False
        if notes_master_part is not None and notes_master_part in names:
            master_rels_name = relationships_part(notes_master_part)
            if master_rels_name not in names:
                errors.append("Notes master is missing its relationships file")
            else:
                master_rels = ET.fromstring(archive.read(master_rels_name))
                theme_rels = [rel for rel in master_rels if rel.get("Type") == THEME_REL_TYPE]
                if len(theme_rels) != 1:
                    errors.append(
                        "Notes master must have exactly one theme relationship, "
                        f"found {len(theme_rels)}"
                    )
                elif theme_rels[0].get("Target"):
                    theme_target = theme_rels[0].get("Target", "")
                    theme_part = resolve_target(notes_master_part, theme_target)
                    notes_master_theme_relationship = theme_part in names
                    if not notes_master_theme_relationship:
                        errors.append(
                            f"Notes-master theme target does not resolve: {theme_target}"
                        )

        if require_notes:
            if len(notes) != len(slides):
                errors.append(f"Expected {len(slides)} note parts, found {len(notes)}")
            if notes_relationships != len(slides):
                errors.append(
                    f"Expected {len(slides)} slide-to-note relationships, found {notes_relationships}"
                )
            if notes_master_id is None:
                errors.append("Presentation has no notesMasterIdLst")
            if not notes_master_relationship:
                errors.append("Presentation has no matching notes-master relationship")
            if not notes_master_theme_relationship:
                errors.append("Presentation has no valid notes-master theme relationship")
            if valid_note_relationships != len(slides):
                errors.append(
                    f"Expected {len(slides)} valid note relationship sets, "
                    f"found {valid_note_relationships}"
                )
        elif notes and len(notes) != len(slides):
            warnings.append(f"Partial notes: {len(notes)} notes for {len(slides)} slides")

        if image_only_pages:
            message = f"Image-only slides detected: {image_only_pages}"
            if reject_image_only:
                errors.append(message)
            else:
                warnings.append(message)

        return {
            "ok": not errors,
            "file": str(path),
            "bytes": path.stat().st_size,
            "slides": len(slides),
            "expected_slides": expected_slides,
            "notes": len(notes),
            "notes_relationships": notes_relationships,
            "valid_note_relationships": valid_note_relationships,
            "notes_master_id": notes_master_id,
            "notes_master_relationship": notes_master_relationship,
            "notes_master_theme_relationship": notes_master_theme_relationship,
            "aspect_ratio": ratio,
            "image_only_pages": image_only_pages,
            "errors": errors,
            "warnings": warnings,
            "pages": slides_report,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pptx", type=Path)
    parser.add_argument("--expected-slides", type=int)
    parser.add_argument("--require-notes", action="store_true")
    parser.add_argument("--reject-image-only", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.expected_slides is not None and args.expected_slides <= 0:
        parser.error("--expected-slides must be a positive integer")

    result = validate(
        args.pptx,
        args.require_notes,
        args.reject_image_only,
        args.expected_slides,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        status = "PASS" if result["ok"] else "FAIL"
        print(f"{status}: {result['file']}")
        print(
            f"slides={result['slides']} notes={result['notes']} "
            f"notes_relationships={result['notes_relationships']}"
        )
        for warning in result["warnings"]:
            print(f"WARNING: {warning}")
        for error in result["errors"]:
            print(f"ERROR: {error}")

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
