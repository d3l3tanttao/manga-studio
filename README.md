# Manga Studio 2.2

Local Windows manga coloring and redrawing with **Black Forest Labs FLUX.2 klein 4B** as the only rendering engine. Automatic coloring is a complete workflow without a reference or brush. [Русский](README.ru.md)

Direction: **d3l3tanttao**. Application implementation: **OpenAI Codex (AI assistant)**. Model authorship is credited separately in [CREDITS.md](CREDITS.md). The original qweasdd/FFDNet contributions remain in project history, with their inference and installation paths retired.

## Workflow

1. Add PNG/JPEG images or a chapter folder.
2. Choose automatic coloring, reference coloring, or redraw. A reference is optional for redraw.
3. Choose drawing fidelity (strict by default). Redraw has a separate latent transformation slider. These reduce changes; they do not guarantee identical lines or anatomy.
4. Choose a reference role: rendering style, palette, lighting, or all. Palette mode strips the reference to swatches; lighting mode converts it to grayscale. Style and combined roles are model instructions, not perfect disentanglement.
5. Generate and compare. Export numbered PNGs at original dimensions. Each result has its own immutable history entry.
6. Correct skin, face, hands or clothing boundaries without painting a mask. Skin/clothing commands use whole-page context. Florence-2 locates faces/hands; FLUX processes enlarged contextual crops against the original and existing colors. Review the proposal and return to an earlier version if needed.

New generation does not reapply old brush fills/material layers. Existing manual trials can still be saved from their cached result. Historical layers remain in prior versions.

## Chapter guidance and limitations

The chapter uses a fixed color guide. An automatic first result becomes the guide only if it passes the contour check. This is not an anatomy or aesthetic assessment. You can explicitly choose an approved version as the guide, remove it, and describe character colors in advanced settings. Cross-pose character identity and color consistency remain imperfect.

Detected text is restored from the original. Exterior white-paper protection is a heuristic and can be disabled for open contours or a deliberate background change. Detectors can miss or misidentify regions. Faces, fingers, skin and material boundaries still require visual review.

Older projects open as separate 2.2 copies, preserving saved PNGs and history. Recoloring uses FLUX. References and correction inputs are copied inside the project and serialized with relative paths. The bundled demonstration is a historical cached result; its next generation uses FLUX.

## Install

Version 2.2 is published as source. No new packaged Windows release accompanies this update; older release downloads belong to their stated versions. Setup builds the current launcher locally.

Windows x64, Python 3.10 x64 with `py`, and NVIDIA CUDA are required for generation. Tested on RTX 5080 Laptop GPU, 16 GB VRAM. CPU installations can view, manually edit cached results and export.

```powershell
.\setup.ps1
& '.\Manga Studio 2.2.exe'
```

Default setup installs the CUDA GUI runtime, isolated AI runtime, FLUX, CRAFT text detection and Florence-2 grounding. Weights occupy about 15.3 GiB; libraries need additional space. Inference is local and offline.

For an existing CUDA runtime use `setup-ai.ps1`. `setup.ps1 -SkipDownload` skips models, `setup.ps1 -Device CPU` installs a viewer, and `setup.ps1 -InstallSelection` adds optional SAM manual tools. Source archives exclude runtimes, weights, user images, projects and the local `.runtime-path` pointer.

## Validation

```powershell
.\.venv\Scripts\python.exe tests\check_release.py
.\.venv\Scripts\python.exe tests\check_ai_ui.py
.\.venv\Scripts\python.exe tests\check_flux_contract.py
.\.venv\Scripts\python.exe tests\check_ai_desktop.py --output results\workflow --source source.jpg --reference style.jpg --chapter page1.jpg page2.jpg page3.jpg
```

The last command runs real GPU inference. Shared-runtime installations must use their runtime Python and set `MANGA_STUDIO_HOME` to its directory. [Quality evidence](docs/QUALITY-2.2.md). All 25 UI catalogs include the new controls; native-speaker review remains pending.

Application code is MIT licensed. External models and libraries retain their own terms. [LICENSE](LICENSE), [LICENSING.md](LICENSING.md).
