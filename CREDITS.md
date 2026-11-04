# Contributions and provenance

| Contributor | Contribution |
|---|---|
| **d3l3tanttao** | Product direction, requirements, priorities, feedback on the brush workflow and release approval. |
| **OpenAI Codex (AI assistant)** | Implementation of the Windows/PySide6 desktop application, interface and interaction design, GPU/CPU adapter, original-resolution tint and luma modes, local brush and lasso, hint authoring, palettes, trial comparison, version acceptance, project migration, chapter persistence and export, automated tests, packaging, localization integration, documentation and original vector demonstration art. |
| **qweasdd and contributors to manga-colorization-v2** | External neural colorization pipeline. The application uses the generator architecture, pretrained checkpoints linked by the upstream project, input preparation and guidance mask interface. The upstream model performs inference. |
| **Matias Tassano / FFDNet implementation** | Denoising component integrated by the upstream project. Its source headers credit Matias Tassano and specify GPL version 3 or later. |

The pinned engine revision is `a0d0e4482e5e86ddbd49958475f3e95f282a1915`. Studio rasterizes the user's normalized strokes and sends the color and mask to the upstream `update_hint` method. For local color, Studio applies a separate full-resolution mask directly to the scan. [Upstream repository](https://github.com/qweasdd/manga-colorization-v2) · [Upstream hint implementation](https://github.com/qweasdd/manga-colorization-v2/blob/a0d0e4482e5e86ddbd49958475f3e95f282a1915/colorizator.py) · [FFDNet notice](https://github.com/qweasdd/manga-colorization-v2/blob/a0d0e4482e5e86ddbd49958475f3e95f282a1915/denoising/denoiser.py)

The upstream generator explicitly references AlacGAN, and its feature extractor references Tag2Pix. Those references are retained here for provenance. [AlacGAN](https://github.com/orashi/AlacGAN) · [Tag2Pix](https://github.com/blandocs/Tag2Pix)

PySide6/Qt provides the desktop toolkit. PyTorch and torchvision support inference. Pillow, NumPy and OpenCV handle image input, geometry and composition. The original demonstration assets are in `studio/assets`. Repository screenshots show this drawing. The project uses system fonts.

The interface catalogs were prepared with Codex and local translation assistance from Meta's NLLB-200 distilled 600M. Codex edited the brush terminology across languages. The application contains the finished catalogs and runs without a translation model. [Translation model card](https://huggingface.co/facebook/nllb-200-distilled-600M) · [Review status](docs/LOCALIZATION.md)
