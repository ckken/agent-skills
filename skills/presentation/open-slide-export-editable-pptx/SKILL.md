---
name: open-slide-export-editable-pptx
description: Export Open Slide React decks as high-fidelity editable PowerPoint files, preserve or restore speaker notes, and verify the result with OOXML checks plus a real Microsoft PowerPoint render. Use when a user asks to export an Open Slide deck to editable .pptx, improve PPTX fidelity, keep presentation notes, diagnose Web-versus-PowerPoint layout drift, or validate that text, shapes, images, page counts, notes, and selected slides survive export.
---

# Export editable Open Slide PPTX

Produce a PowerPoint file that opens without repair prompts, keeps text and shapes editable, includes the expected speaker notes, and matches the Web deck closely enough to present.

## Establish the contract

Record before exporting:

- deck checkout and slide id;
- editable-PPTX exporter checkout and branch;
- output path and overwrite policy;
- expected slide count;
- whether speaker notes are required;
- high-risk pages to compare after export.

Resolve `<skill-dir>` to the directory containing this `SKILL.md`. Invoke bundled scripts through `<skill-dir>/scripts/...`; the current working directory may be the deck checkout and does not contain these scripts.

Preserve unrelated dirty changes. Do not edit the deck's `package.json` or lockfile merely to load a newer exporter. Run the exporter CLI from its own checkout while using the deck directory as the current working directory.

## Select the exporter

Use the deck's current runtime only when its Download menu already exposes `Export as PPTX`.

Otherwise:

1. Locate an Open Slide checkout that contains `packages/core/src/app/lib/export-pptx-editable.ts`.
2. Verify the current branch and local changes live; never infer them from old notes.
3. Prefer the user-selected branch. For the established fork workflow, use `ckken/open-slide` branch `codex/editable-pptx-export`.
4. Build only the core package:

```bash
pnpm --filter @open-slide/core build
```

5. Start its CLI from the deck checkout on an unused loopback port:

```bash
node <open-slide-checkout>/packages/core/bin.js dev \
  --host 127.0.0.1 --port <port>
```

Decline any prompt to synchronize project skills unless the user also asked for that change.

## Export the editable file

Use the bundled browser exporter after the page is reachable:

```bash
node <skill-dir>/scripts/export_editable_pptx.mjs \
  --url "http://127.0.0.1:<port>/s/<slide-id>?p=1" \
  --output "/absolute/path/deck-editable-raw.pptx"
```

The script requires Playwright. In Codex Desktop, call `codex_app.load_workspace_dependencies` first, then use the returned Node executable and Node modules path:

```bash
NODE_PATH="<returned-node-modules>" "<returned-node-executable>" \
  <skill-dir>/scripts/export_editable_pptx.mjs \
  --url "http://127.0.0.1:<port>/s/<slide-id>?p=1" \
  --output "/absolute/path/deck-editable-raw.pptx"
```

Outside Codex Desktop, use a project/runtime that already provides Playwright. Do not hard-code one machine's bundled runtime paths into the Skill.

Treat the download as successful only when:

- the browser reports no export error;
- the download has no failure reason;
- the output exists and is non-empty.

Stop the temporary exporter after the download.

## Preserve speaker notes

Prefer source-controlled notes:

```tsx
export const notes = [
  'Speaker notes for page 1',
  'Speaker notes for page 2',
];
```

Keep the array index-aligned with the default page export.

When the current source lacks notes but a previously verified PPTX contains the approved notes, merge them into the new export:

```bash
python3 <skill-dir>/scripts/merge_pptx_notes.py \
  --input deck-editable-raw.pptx \
  --notes-source deck-with-approved-notes.pptx \
  --output deck-editable-final.pptx
```

The merger preserves the new slide XML and image relationships while adding note parts and relationships. Require equal slide and note counts by default. Use `--allow-partial` only when the user explicitly accepts partial notes.

Never copy an older PPTX wholesale as the final artifact: that silently loses recent slide edits.

## Validate the OOXML package

Run deterministic validation:

```bash
python3 <skill-dir>/scripts/validate_pptx.py deck-editable-final.pptx \
  --expected-slides <count> \
  --require-notes \
  --json
```

Require:

- a valid ZIP package;
- the expected slide count;
- one note part and note relationship per slide when notes are required;
- a 16:9 presentation canvas;
- editable slide objects, not only a full-canvas screenshot;
- no missing slide relationship files.
- every slide-to-note target and note-to-slide/master target resolves when notes are required.

Use `--reject-image-only` when every page is expected to remain editable.

## Verify with Microsoft PowerPoint

On macOS with PowerPoint installed, open and render the actual PPTX. This is the fidelity gate; a successful Web screenshot is insufficient.

```applescript
tell application "Microsoft PowerPoint"
  set pptFile to POSIX file "/absolute/path/deck-editable-final.pptx"
  set pdfFile to POSIX file "/tmp/deck-editable-final.pdf"
  open pptFile
  delay 3
  save active presentation in pdfFile as save as PDF
  close active presentation saving no
end tell
```

Render the high-risk pages from the PDF and inspect them:

```bash
pdftoppm -f <page> -singlefile -png -r 120 \
  /tmp/deck-editable-final.pdf /tmp/deck-page-<page>
```

Check at least:

- one text-heavy page;
- one page with circular badges or centered numbers;
- one page with project imagery;
- the page changed most recently;
- one page with speaker notes in PowerPoint's Notes pane.

Use LibreOffice only as a fallback. If its bundled fontconfig cannot resolve `PingFang SC` or `SF Pro Text`, missing CJK glyphs are a renderer limitation, not proof that the PPTX is corrupt. Confirm the OOXML typefaces and validate in Microsoft PowerPoint before changing the deck.

## Completion gate

Finish only after all applicable checks pass:

- slide count matches the deck;
- note count matches the requirement;
- PowerPoint opens the file without repair;
- selected PowerPoint-rendered pages preserve hierarchy, alignment, and imagery;
- centered numbers remain centered after export;
- text, shapes, and images remain editable objects;
- the final filename is distinct from the raw export;
- the delivered link points to the verified final PPTX.

Report the final path, file size, slide count, note count, pages inspected, exporter branch, and any known fidelity limitations.

## Bundled scripts

- `scripts/export_editable_pptx.mjs`: trigger the editable PPTX download through the Open Slide UI.
- `scripts/merge_pptx_notes.py`: add approved notes from an earlier PPTX without replacing current slides.
- `scripts/validate_pptx.py`: validate archive integrity, slide/note relationships, aspect ratio, and editable-object presence.
