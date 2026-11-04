from .i18n import tr
import cv2
import numpy as np
from PIL import Image


def transfer(gray, prediction, mode, intensity=100):
    """Transfer model color while keeping the scan on its native pixel grid."""
    if mode not in ("tint", "luma"):
        raise ValueError(tr("Неизвестный режим цвета: {0}", mode))
    height, width = gray.shape
    result = cv2.resize(prediction, (width, height), interpolation=cv2.INTER_CUBIC)
    # Keep float buffers bounded even for large scans.
    for start in range(0, height, max(1, 524288 // width)):
        end = start + max(1, 524288 // width)
        scan = gray[start:end]
        rgb = result[start:end].astype(np.float32)
        if mode == "tint":
            peak = rgb.max(axis=2, keepdims=True)
            tint = 1 - (peak - rgb) / np.maximum(peak, 64)
            if intensity != 100:
                tint = 1 + (tint - 1) * (intensity / 100)
            result[start:end] = np.rint(scan[:, :, None] * tint).clip(0, 255)
        else:
            chroma = rgb - cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)[:, :, None]
            limit = np.minimum((255 - scan) / np.maximum(chroma.max(2), 1e-6),
                               scan / np.maximum(-chroma.min(2), 1e-6))
            strict = scan[:, :, None] + chroma * (np.minimum(limit, 1) * (intensity / 100))[:, :, None]
            strict = np.rint(strict).clip(0, 255).astype(np.uint8)
            measured = np.asarray(Image.fromarray(strict).convert("L"))
            while np.any(mismatch := (measured != scan)):
                step = np.sign(scan[mismatch].astype(np.int16) - measured[mismatch])
                strict[mismatch] = (strict[mismatch] + step[:, None]).clip(0, 255)
                measured = np.asarray(Image.fromarray(strict).convert("L"))
            result[start:end] = strict
    return result
