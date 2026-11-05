# Object editing and quality in 2.0

SAM predicts regions, qweasdd predicts color, and the application renders editable materials from the scan. Neural outputs remain editable proposals.

| Approved area | Implementation | Boundary |
| --- | --- | --- |
| Scene structure | Object and rectangular panel proposals, manual scopes | No automatic text transcription or reliable anatomical labels |
| Object recoloring | Positive/negative points and mask variants | Human review remains necessary |
| Disconnected parts | Independent per-part inference, positive/negative points and persistent manual additions/exclusions | No hidden-surface reconstruction |
| Native edges | Scan-guided closed regions, thin-edge detection and conservative pinhole repair | Small ambiguous holes can still need correction; negative points protect them |
| Protection | Exact original/current-pixel locks and paper proposals | Paper may connect to white clothing |
| Object layers | Versioned masks bound to source-pixel hashes, colors, materials and locks | Larger manifests than 1.2 |
| Lightness | Bounded LAB mode and material controls | Gamut still limits saturated highlights |
| Black materials | Optional broad-fill lift | Broad ink strokes can be mistaken for fill |
| Global/local processing | Overlapping local passes with global hints | Slower and not always preferable |
| Scan preparation | Native-scale denoising tiles | Denoising can affect interpretation |
| Color instructions | Deterministic materials and separate legacy hints | Material base color differs from shaded pixels |
| Chapter palettes | User-confirmed character/material links | No automatic identity matching |
| Reference | Median material sampling by lasso | No learned reference alignment |
| Diagnostics | Locks, owned pixels, fragments and palettes | No calibrated semantic confidence |
| Interface | Dedicated workspace and persistent Apply button | Advanced controls remain in Settings |
| Runtime | Cached embeddings, serialized GPU access and stale-result rejection | Running forward passes finish before cancellation |
| Engine boundary | Separate adapters and pinned manifests | SAM 2.1 Small/Large and qweasdd v2 are the installed baselines |
| Regression checks | Mask, material, UI, migration, locale and chapter tests | Synthetic checks do not replace varied-artwork review |

## Verification

Object tests check replacement of deliberately contaminated old colors, including soft boundaries, exact outside-mask and locked-pixel preservation, black-fill lifting, thin ink, mask dimensions, serialization, undo/redo, trial acceptance/discard and legacy copying. The optional SAM check invokes the real model.

Release checks cover all 25 catalogs and deep workflows in Russian, English, German, Arabic and Simplified Chinese. Desktop checks preserve the existing chapter, brush, export and CPU workflows.

The local evaluation script writes dimensions, settings, timings and outputs. Zero old chroma inside a proposed mask is not proof of complete semantic coverage. Coverage must be reviewed separately.

On the development RTX 5080 Laptop GPU, the first isolated selection took roughly 18 seconds including startup. Repeated selection took about 0.20 seconds on the synthetic page and 0.46 seconds on the supplied screenshot. The isolated SAM test reported approximately 623 MiB peak allocated CUDA memory. These are machine-specific observations, not latency guarantees or total application VRAM requirements.

## Research boundaries

Automatic anatomical/material labels, automatic character identity matching, learned reference alignment and trained defect detection need separate evaluation. SAM 3 and MangaNinja are not shipped. This release exposes editable proposals and explicit material links instead of claiming those research problems are solved.

## Release validation on the development machine

- A three-page local chapter (918x1145, 2771x3464 and 1235x1734) completed GPU colorization, version acceptance and PNG export at source dimensions.
- An actual 1.2 chapter opened as a separate project; its original manifest stayed byte-identical and its selected PNG remained saved.
- Object checks covered soft-edge replacement, outside-region preservation, exact locks, HEX on white, source replacement, small-hole protection, persistent manual corrections, undo/redo, reference sampling and two-page linked palette updates.
- Native Windows object workflows and both real SAM variants passed on the RTX 5080 Laptop GPU. The tested isolated models peaked at about 623 MiB (Small) and 1453 MiB (Large) allocated CUDA memory. The application and colorization model need additional memory.
- All 25 catalogs were checked for matching keys, placeholders and font glyphs. This does not constitute native-speaker review.

On the supplied character screenshot, Small left fragmented skin regions. Large improved coverage but sometimes selected stockings. Independent-part inference improved the arm coverage; negative points and manual correction remain necessary. Model score alone did not reliably rank the best region, so point agreement now takes priority. None of these observations establish universal anatomical accuracy.

Local example images and chapters are excluded from the repository and release archive. The public screenshots use only the bundled original demonstration artwork.

The detailed-processing check used a 2771x3464 scan, 20 native denoising tiles (largest edge 864), a 1638x2048 color proposal and a 2771x3464 final PNG. Source bytes and black scan pixels remained unchanged. Cancellation between tiles passed.
