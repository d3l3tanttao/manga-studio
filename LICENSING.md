# Licensing and release boundary

## Current rendering in 2.2

The application remains MIT. FLUX.2 klein **4B** is downloaded at a pinned revision and retains Apache-2.0. Neither 9B nor FLUX dev is used by this release. [Official model and license](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B/tree/e7b7dc27f91deacad38e78976d1f2b499d76a294).

Historical 2.1 experiments compared SDXL/MistoLine/IP-Adapter; they are removed from the active application. SDXL and MistoLine weights have their own OpenRAIL terms; MistoLine additionally requires the attribution preserved in CREDITS.md. They are neither bundled nor downloaded by the standard AI installer. [SDXL](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0), [MistoLine](https://huggingface.co/TheMistoAI/MistoLine), [IP-Adapter](https://huggingface.co/h94/IP-Adapter), [VAE fix](https://huggingface.co/madebyollin/sdxl-vae-fp16-fix).

EasyOCR, CRAFT, Diffusers, Transformers and other dependencies retain their upstream licenses. The source ZIP contains no third-party runtime or weights. New 2.1 translations were drafted by Codex without an additional translation service or model.

Manga Studio's original application code, scripts, tests, documentation, UI catalogs and demonstration artwork are available under the MIT License. Keep the copyright and permission notices when distributing copies or substantial portions. [MIT License](LICENSE)

The repository contains desktop application source, UI catalogs, scripts, tests and the original jacket illustration. The illustration and its derived PNGs were created for this application and are included for the sample and tests. It contains no upstream manga-page examples or derivatives of those examples.

The pinned manga-colorization-v2 tree has no repository-wide license file in its root. Its README provides links to pretrained weights. Treat the code, weights and independently licensed components separately. Versions through 2.1 offered setup steps to obtain that checkout and checkpoints. Version 2.2 no longer installs or invokes them. The public source archive excludes both. [Upstream tree](https://github.com/qweasdd/manga-colorization-v2/tree/a0d0e4482e5e86ddbd49958475f3e95f282a1915) · [Upstream instructions](https://github.com/qweasdd/manga-colorization-v2)

The FFDNet source used upstream has GPL-3.0-or-later notices. PySide6/Qt and the other installed dependencies retain their own licenses. Review applicable obligations before distributing a combined runtime or an installer containing dependencies. The setup script retrieves runtime packages from their original indexes. The launcher contains no Python, Qt, PyTorch or model data. [FFDNet source notice](https://github.com/qweasdd/manga-colorization-v2/blob/a0d0e4482e5e86ddbd49958475f3e95f282a1915/denoising/denoiser.py) · [Qt for Python licensing](https://doc.qt.io/qtforpython-6/licenses.html)

NLLB was used as a development-time translation aid. Its model card identifies CC-BY-NC-4.0 for the model. The application ships the finished UI catalogs and runs offline. [Model card](https://huggingface.co/facebook/nllb-200-distilled-600M)

The credits distinguish product direction, application implementation and upstream contributions. [Project credits](CREDITS.md)

## SAM 2.1 integration in 2.0

Optional SAM 2.1 source and checkpoints are obtained from Meta's official repository and checkpoint host. They retain Apache-2.0 and are excluded from the application's source archive. Our refinement does not use the optional CUDA connected-components extension. [SAM 2 license](https://github.com/facebookresearch/sam2/blob/main/LICENSE).

`studio/backends.json` records the revision and checkpoint hash. SAM 3 and MangaNinja are not installed or shipped. The application's MIT license does not replace external model terms.

## Region grounding in 2.2

Microsoft Florence-2-base is downloaded separately at a pinned revision under MIT, with its LICENSE file. The reviewed model implementation runs locally with no network access during inference. The public application archive contains neither its code nor weights. [Official source and license](https://huggingface.co/microsoft/Florence-2-base/tree/5ca5edf5bd017b9919c05d08aebef5e4c7ac3bac).
