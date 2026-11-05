# FLUX workflow validation in 2.2

This is a source update with tested local workflows, not a claim that anatomy or character consistency is solved. A new packaged Windows release has not been published. The launcher compiled locally; the final interactive launcher check was interrupted and is not counted as passed.

## Reproducible checks

- `tests/check_release.py`: all 25 catalogs, 289 messages each, placeholders, available Windows glyphs, RTL layout, historical sample editing, version acceptance, export and project migration.
- `tests/check_ai_ui.py`: all 25 primary workspaces at 940x610, optional reference controls, manual-tool switching and access to advanced settings without horizontal clipping.
- `tests/check_flux_contract.py`: old settings round-trip, unchanged historical PNG/version data, FLUX-only requests for recoloring, portable correction inputs and viewing a result when its source is missing. This test uses a stub renderer to isolate persistence and routing; it does not evaluate model quality.
- `tests/check_ai_desktop.py`: real FLUX inference and Qt integration. A mixed three-page chapter without a reference or brush, PNG export, reference coloring, redraw, exact history restoration, cancellation during generation, a successful next variant, brushless skin/face corrections, project relocation, and unchanged input files all passed.
- `tests/check_objects.py` without `--sam`: passed material boundaries, original-pixel preservation, undo/redo, acceptance, reload, linked palette changes and migration. It caught and verified fixes for original-base composition and numeric layer round-trip stability. This rerun does not claim a new SAM benchmark.
- AI-runtime `pip check`: passed. The Windows launcher build completed successfully.

The GPU workflow used NVIDIA GeForce RTX 5080 Laptop GPU with 16 GB VRAM, FLUX.2 klein 4B at revision `e7b7dc27f91deacad38e78976d1f2b499d76a294`, and contract `manga-studio/generation-2.2-v2`. The three chapter pages used strict fidelity, BF16 and four generation steps.

| Page | Source dimensions | Working dimensions | Render time | Peak allocated CUDA | Detected text regions | Changed protected text pixels |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 1218x1874 | 816x1264 | 54.166 s | 9.315 GiB | 57 | 0 |
| 2 | 746x1080 | 736x1072 | 26.158 s | 9.127 GiB | 1 | 0 |
| 3 | 751x1080 | 736x1072 | 11.314 s | 9.127 GiB | 28 | 0 |

These are single-run development observations, not latency guarantees. Loading, prompt caching and other applications affect timings. Tensor allocation is not total GPU usage. Final PNGs retain source dimensions; inference is performed at the working resolution, so source-size export does not imply native-resolution reconstruction of every detail.

The face correction in the same workflow used one automatically located contextual crop, took 50.173 seconds including model setup, and retained its predecessor as a separate version. Florence-2-base at revision `5ca5edf5bd017b9919c05d08aebef5e4c7ac3bac` supplies region coordinates; FLUX remains the renderer. The result carries a review warning. The hand-context path was also exercised on the supplied single-character illustration during local development, separately from the complete desktop workflow.

## Visual findings and boundaries

- Strict source initialization at 0.75 was selected after a 0.65 trial left parts of the test figure uncolored. Greater source retention is not automatically better coloring.
- A whole-page instruction to restore a face made little useful correction on the test illustration. Enlarged, automatically located context gave a more noticeable correction, but eyes, irises, smiles and finger shapes can still change.
- Palette-only input contains color swatches instead of the reference person. This removes reference pose/garment pixels from that input; it does not guarantee correct assignment of those colors to materials.
- Skin and clothing corrections see the whole page. They can change unrelated details or interpret a material incorrectly. Face/hand crops use surrounding context and feathered application, but detection and boundaries can be wrong.
- Text and exterior-paper protections are heuristics. Zero changed protected pixels proves copying inside detected regions, not that every text region was found.
- Source-edge coverage is only a contour diagnostic. A high value does not establish correct anatomy, identity, color or artistic quality.
- The chapter consisted of three different regression pages, not a continuous story with independently verified character identities. Fixed chapter guides and color notes do not establish reliable character tracking across poses or pages.
- Native-speaker translation review and a clean-machine installation test remain outstanding. Automated layout checks do not replace either.

## Local evidence and public files

The complete local report, renders and screenshots are retained in the developer workspace. User images, reference art, chapter files, absolute local paths, and raw reports containing those paths are not published. The public repository contains the original bundled demonstration artwork and this aggregate report.

Run the checks in [README.md](../README.md#validation) with your own source, reference and three chapter images. Model revisions, seed, precision, working resolution, reference hashes and protection diagnostics are stored with generated versions. Keep the full project directory to preserve history and imported correction inputs.
