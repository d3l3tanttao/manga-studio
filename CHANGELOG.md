# 2.2.0

- FLUX.2 klein 4B is the only rendering engine. Removed classic inference, the hint tool, old processing controls, upstream cloning and old weight downloads.
- Preserved old PNG history and projects; a new render upgrades its request to FLUX without modifying previous versions.
- Added drawing fidelity presets, separate rendering/palette/lighting reference roles, and optional exterior-paper protection.
- Palette-only references contain color swatches, with the source person and pose removed.
- Added brushless skin and clothing edits, and Florence-grounded face/hand context passes through FLUX. These are editable proposals, not guaranteed anatomy restoration.
- Kept fixed chapter guidance with explicit anchor selection, rejection of contour-warning automatic anchors, and character color notes.
- New generation does not reapply historical brush/material fills. A manual trial can still be saved from its existing cache.
- Added NF4 retry after an automatic-mode CUDA memory failure; fixed worker model-directory switching.
- Added portable correction assets, 25 translated control sets, missing-original image viewing, and updated regression tests.
- Fixed manual edits on an uncolored original replacing pixels outside the selection, and preserved numeric layer values across load/save so accepted versions remain recognized as saved.
- Reference influence and character identity remain imperfect. See docs/QUALITY-2.2.md.

# 2.1 development checkpoint

- Introduced the isolated local FLUX worker, source/reference/redraw workspace, text/paper protection, chapter references, cancellation, runtime setup and generation provenance.
- Compared SDXL line-conditioning and simple ink reconstruction; neither became the default.

# 2.0.0

- Added native Windows SAM 2.1 Small/Large selection, automatic proposals, positive/negative points, independent-part inference and persistent manual boundary corrections.
- Added source-bound material layers, exact pixel protection, HEX-matched base colors, reference sampling, linked palettes and object undo/redo.
- Added bounded lightness, scan-guided upsampling, native-scale denoising and local detail passes.
- Added 25 localized object workspaces, legacy project copying and CPU/GPU regression checks.
- Automatic anatomical labels and character identity matching remain research tasks.

# 1.2.0

- Set Color brings together presets, HEX input and a named chapter palette. Swatches can be renamed or removed. The active name and color stay in sync.
- AI hints use a trial workflow with a hint count, clean comparison, acceptance and discard. Applying hints computes a preview without creating a working PNG version.
- Local brush and freehand lasso recolor the selected pixels while preserving scan detail. Stroke endpoints and the first crossing of the page border are captured.
- The eyedropper has explicit original/result sources. Alt samples temporarily. Brackets change the diameter. Color and diameter persist between sessions.
- The comparison view can show the page immediately before the trial. Working versions carry edit labels. Original 1.1 projects open as separate 1.2 projects.
- 25 offline catalogs, RTL panel layout, translated editor actions, model setup and credits.
- Original demonstration art, Windows setup and build scripts, split project/engine credits and automated release verification.
