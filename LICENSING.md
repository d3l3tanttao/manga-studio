# Licensing and release boundary

This is a local release candidate for public distribution. The project owner will select a license for the application's original material before publishing. This document records provenance and the pending decision. It does not grant an application-wide redistribution license.

The repository contains desktop application source, UI catalogs, scripts, tests and the original jacket illustration. The illustration and its derived PNGs were created for this application and are included for the sample and tests. It contains no upstream manga-page examples or derivatives of those examples.

The pinned manga-colorization-v2 tree has no repository-wide license file in its root. Its README provides links to pretrained weights. Treat the code, weights and independently licensed components separately. The optional setup steps obtain the upstream checkout and checkpoints directly for the local installation. The public source archive excludes both. [Upstream tree](https://github.com/qweasdd/manga-colorization-v2/tree/a0d0e4482e5e86ddbd49958475f3e95f282a1915) · [Upstream instructions](https://github.com/qweasdd/manga-colorization-v2)

The FFDNet source used upstream has GPL-3.0-or-later notices. PySide6/Qt and the other installed dependencies retain their own licenses. Review applicable obligations before distributing a combined runtime or an installer containing dependencies. The setup script retrieves runtime packages from their original indexes. The launcher contains no Python, Qt, PyTorch or model data. [FFDNet source notice](https://github.com/qweasdd/manga-colorization-v2/blob/a0d0e4482e5e86ddbd49958475f3e95f282a1915/denoising/denoiser.py) · [Qt for Python licensing](https://doc.qt.io/qtforpython-6/licenses.html)

NLLB was used as a development-time translation aid. Its model card identifies CC-BY-NC-4.0. Its weights and translation tooling are excluded from the release. Publication review should include the intended use of the generated catalogs. [Model card](https://huggingface.co/facebook/nllb-200-distilled-600M)

Before publication, confirm the application license and intended distribution scope, review the external integration and notices, and approve the repository and release assets. [Project credits](CREDITS.md)
