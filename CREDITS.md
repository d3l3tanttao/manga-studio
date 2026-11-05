# Contributions and provenance

## Additions in 2.2

- **d3l3tanttao** set the FLUX-only direction and priorities for fidelity, skin consistency, references, chapter colors and brushless editing.
- **OpenAI Codex (AI assistant)** implemented removal of the old inference path, historical project compatibility, reference roles, source-fidelity settings, contextual face/hand corrections, automatic memory retry, tests, translation drafts and release preparation.
- **Microsoft** created Florence-2-base, used only for local phrase grounding of faces and hands at revision `5ca5edf5bd017b9919c05d08aebef5e4c7ac3bac` (MIT). It does not color images. [Official model](https://huggingface.co/microsoft/Florence-2-base).
- **Black Forest Labs** remains the author of the sole rendering model, FLUX.2 klein 4B.

Earlier contributions below describe their respective versions. qweasdd/FFDNet and SDXL comparison models are no longer processing or installation options in 2.2. Original-author credit is retained as project history.


## Additions in 2.1

- **d3l3tanttao** defined the automatic source/reference workflow and supplied quality feedback.
- **OpenAI Codex (AI assistant)** implemented the local worker protocol, source-initialized coloring, redraw controls, optional reference UI, chapter guidance, text/paper protection, version provenance, runtime integration, tests, translation drafts and packaging. These are application contributions, not training or authorship of external models.
- **Black Forest Labs** created FLUX.2 klein 4B and its weights, used at revision `e7b7dc27f91deacad38e78976d1f2b499d76a294`. [Official model](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B), Apache-2.0.
- **Qwen team** created the Qwen3 encoder family in the official FLUX package. **Hugging Face and contributors** provide Diffusers, Transformers and Accelerate; **bitsandbytes contributors** provide NF4 quantization.
- **Jaided AI / EasyOCR** and **Clova AI / CRAFT** provide text detection. Studio restores original pixels; it does not translate or regenerate text. [EasyOCR](https://github.com/JaidedAI/EasyOCR), [CRAFT](https://github.com/clovaai/CRAFT-pytorch).
- Experimental comparisons used **Stability AI SDXL 1.0**, **TheMisto.ai MistoLine**, **Tencent AI Lab IP-Adapter**, and **madebyollin's SDXL VAE fix**. They were not selected for the automatic UI path. **This product uses the MistoLine-SDXL-ControlNet developed by TheMisto.ai.** Their authors retain all model credit.

The historical engine and optional SAM credits below are retained. User illustrations, references and manga test pages are excluded from the public source package.

| Contributor | Contribution |
|---|---|
| **d3l3tanttao** | Product direction, requirements, priorities, feedback on the brush workflow and release approval. |
| **OpenAI Codex (AI assistant)** | Implementation of the Windows/PySide6 desktop application, interface and interaction design, GPU/CPU adapter, original-resolution tint and luma modes, local brush and lasso, hint authoring, palettes, trial comparison, version acceptance, project migration, chapter persistence and export, automated tests, packaging, localization integration, documentation and original vector demonstration art. |
| **qweasdd and contributors to manga-colorization-v2** | External neural colorization pipeline. Versions 1.x and 2.0 used the generator architecture, pretrained checkpoints linked by the upstream project, input preparation and guidance mask interface. The upstream model performed inference in those versions. |
| **Matias Tassano / FFDNet implementation** | Denoising component integrated by the upstream project. Its source headers credit Matias Tassano and specify GPL version 3 or later. |

The pinned engine revision is `a0d0e4482e5e86ddbd49958475f3e95f282a1915`. Earlier Studio versions rasterized the user's normalized strokes and sent the color and mask to the upstream `update_hint` method. For local color, Studio applies a separate full-resolution mask directly to the scan. [Upstream repository](https://github.com/qweasdd/manga-colorization-v2) · [Upstream hint implementation](https://github.com/qweasdd/manga-colorization-v2/blob/a0d0e4482e5e86ddbd49958475f3e95f282a1915/colorizator.py) · [FFDNet notice](https://github.com/qweasdd/manga-colorization-v2/blob/a0d0e4482e5e86ddbd49958475f3e95f282a1915/denoising/denoiser.py)

The upstream generator explicitly references AlacGAN, and its feature extractor references Tag2Pix. Those references are retained here for provenance. [AlacGAN](https://github.com/orashi/AlacGAN) · [Tag2Pix](https://github.com/blandocs/Tag2Pix)

PySide6/Qt provides the desktop toolkit. PyTorch and torchvision support inference. Pillow, NumPy and OpenCV handle image input, geometry and composition. The original demonstration assets are in `studio/assets`. Repository screenshots show this drawing. The project uses system fonts.

The interface catalogs were prepared with Codex and local translation assistance from Meta's NLLB-200 distilled 600M. Codex edited the brush terminology across languages. The application contains the finished catalogs and runs without a translation model. [Translation model card](https://huggingface.co/facebook/nllb-200-distilled-600M) · [Review status](docs/LOCALIZATION.md)

## Additions in 2.0

- **d3l3tanttao** supplied direction, approved priorities and identified color leakage and incomplete edits through examples.
- **OpenAI Codex**, an AI assistant, implemented the object workspace, masks, scan-guided refinement, materials, protection, reference sampling, linked palettes, preprocessing, local refinement, adapters, tests, localization drafts and documentation.
- **Meta and the SAM 2 contributors** created SAM 2 and its checkpoints. This application uses SAM 2.1 Small and Large at revision `2b90b9f5ceec907a1c18123530e92e794ad901a4`. [Official project](https://github.com/facebookresearch/sam2). Code and weights retain Apache-2.0.
- In 2.0 the colorization network was **qweasdd/manga-colorization-v2**. Existing FFDNet attribution to **Matias Tassano** remains applicable. The application claims no authorship of these networks or weights.
- New translation drafts were authored by Codex. Native-speaker review remains pending. The application sends no images or chapters to translation services.
