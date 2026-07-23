#!/usr/bin/env python3
"""Deterministic tests for the PPTX notes merger and OOXML validator."""

from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import merge_pptx_notes
import validate_pptx

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"


def relationships(*items: tuple[str, str, str]) -> bytes:
    root = ET.Element(f"{{{REL_NS}}}Relationships")
    for relation_id, relation_type, target in items:
        ET.SubElement(
            root,
            f"{{{REL_NS}}}Relationship",
            {"Id": relation_id, "Type": relation_type, "Target": target},
        )
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def content_types(*overrides: tuple[str, str]) -> bytes:
    root = ET.Element(f"{{{CT_NS}}}Types")
    ET.SubElement(
        root,
        f"{{{CT_NS}}}Default",
        {"Extension": "xml", "ContentType": "application/xml"},
    )
    for part_name, content_type in overrides:
        ET.SubElement(
            root,
            f"{{{CT_NS}}}Override",
            {"PartName": part_name, "ContentType": content_type},
        )
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def presentation_xml() -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<p:presentation xmlns:p="{P_NS}" xmlns:r="{R_NS}">
  <p:sldMasterIdLst/>
  <p:sldSz cx="12192000" cy="6858000"/>
</p:presentation>
""".encode()


def slide_xml(*, image_only: bool = False) -> bytes:
    if image_only:
        body = "<p:pic/>"
    else:
        body = (
            "<p:sp><p:txBody><a:p><a:r><a:t>Editable text</a:t>"
            "</a:r></a:p></p:txBody></p:sp>"
        )
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<p:sld xmlns:p="{P_NS}" xmlns:a="{A_NS}">'
        f"<p:cSld><p:spTree>{body}</p:spTree></p:cSld>"
        f"</p:sld>"
    ).encode()


def write_current(path: Path, *, image_only: bool = False) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            content_types(
                (
                    "/ppt/presentation.xml",
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml",
                ),
                (
                    "/ppt/slides/slide1.xml",
                    "application/vnd.openxmlformats-officedocument.presentationml.slide+xml",
                ),
            ),
        )
        archive.writestr("ppt/presentation.xml", presentation_xml())
        archive.writestr("ppt/_rels/presentation.xml.rels", relationships())
        archive.writestr("ppt/slides/slide1.xml", slide_xml(image_only=image_only))
        archive.writestr("ppt/slides/_rels/slide1.xml.rels", relationships())


def write_notes_source(path: Path, *, theme_number: int = 2) -> None:
    notes_master_type = (
        "application/vnd.openxmlformats-officedocument.presentationml.notesMaster+xml"
    )
    notes_slide_type = (
        "application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml"
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            content_types(
                ("/ppt/notesMasters/notesMaster1.xml", notes_master_type),
                ("/ppt/notesSlides/notesSlide1.xml", notes_slide_type),
            ),
        )
        archive.writestr(
            "ppt/notesMasters/notesMaster1.xml",
            f'<p:notesMaster xmlns:p="{P_NS}"/>',
        )
        archive.writestr(
            "ppt/notesMasters/_rels/notesMaster1.xml.rels",
            relationships(
                (
                    "rId1",
                    f"{R_NS}/theme",
                    f"../theme/theme{theme_number}.xml",
                )
            ),
        )
        archive.writestr(
            f"ppt/theme/theme{theme_number}.xml",
            f'<a:theme xmlns:a="{A_NS}" name="Notes Theme"/>',
        )
        archive.writestr(
            "ppt/notesSlides/notesSlide1.xml",
            f'<p:notes xmlns:p="{P_NS}" xmlns:a="{A_NS}"/>',
        )
        archive.writestr(
            "ppt/notesSlides/_rels/notesSlide1.xml.rels",
            relationships(
                ("rId1", f"{R_NS}/slide", "../slides/slide1.xml"),
                ("rId2", f"{R_NS}/notesMaster", "../notesMasters/notesMaster1.xml"),
            ),
        )


def rewrite_member(source: Path, output: Path, member: str, payload: bytes) -> None:
    with zipfile.ZipFile(source) as current, zipfile.ZipFile(
        output, "w", zipfile.ZIP_DEFLATED
    ) as changed:
        for info in current.infolist():
            changed.writestr(info, payload if info.filename == member else current.read(info.filename))


class PptxToolsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.current = self.root / "current.pptx"
        self.notes_source = self.root / "notes-source.pptx"
        self.merged = self.root / "merged.pptx"
        write_current(self.current)
        write_notes_source(self.notes_source, theme_number=2)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def merge(self) -> dict[str, object]:
        return merge_pptx_notes.build_output(
            self.current,
            self.notes_source,
            self.merged,
            allow_partial=False,
            force=False,
            replace_existing_notes=False,
        )

    def test_merge_uses_source_theme_and_builds_valid_note_graph(self) -> None:
        result = self.merge()
        self.assertEqual(result["notes"], 1)

        with zipfile.ZipFile(self.merged) as archive:
            self.assertIn("ppt/theme/theme2.xml", archive.namelist())
            presentation = ET.fromstring(archive.read("ppt/presentation.xml"))
            notes_master = presentation.find(f"{{{P_NS}}}notesMasterIdLst")
            self.assertIsNotNone(notes_master)

        validation = validate_pptx.validate(
            self.merged,
            require_notes=True,
            reject_image_only=True,
            expected_slides=1,
        )
        self.assertTrue(validation["ok"], validation["errors"])
        self.assertEqual(validation["valid_note_relationships"], 1)

    def test_merge_refuses_to_replace_existing_notes_without_flag(self) -> None:
        self.merge()
        second_output = self.root / "second.pptx"
        with self.assertRaisesRegex(ValueError, "already contains speaker notes"):
            merge_pptx_notes.build_output(
                self.merged,
                self.notes_source,
                second_output,
                allow_partial=False,
                force=False,
                replace_existing_notes=False,
            )

    def test_validator_rejects_expected_slide_count_mismatch(self) -> None:
        result = validate_pptx.validate(
            self.current,
            require_notes=False,
            reject_image_only=False,
            expected_slides=2,
        )
        self.assertFalse(result["ok"])
        self.assertIn("Expected 2 slides, found 1", result["errors"])

    def test_validator_rejects_dangling_slide_to_note_target(self) -> None:
        self.merge()
        broken = self.root / "broken.pptx"
        rewrite_member(
            self.merged,
            broken,
            "ppt/slides/_rels/slide1.xml.rels",
            relationships(
                ("rId1", f"{R_NS}/notesSlide", "../notesSlides/missing.xml")
            ),
        )
        result = validate_pptx.validate(
            broken,
            require_notes=True,
            reject_image_only=True,
            expected_slides=1,
        )
        self.assertFalse(result["ok"])
        self.assertTrue(
            any("notes target does not resolve" in error for error in result["errors"])
        )

    def test_validator_rejects_image_only_slide(self) -> None:
        image_only = self.root / "image-only.pptx"
        write_current(image_only, image_only=True)
        result = validate_pptx.validate(
            image_only,
            require_notes=False,
            reject_image_only=True,
            expected_slides=1,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["image_only_pages"], [1])


if __name__ == "__main__":
    unittest.main()
