from .i18n import tr
import cv2
import numpy as np
from PIL import Image


def guided_resize(prediction,gray):
    """Upsample color using the scan as an edge guide, at bounded working resolution."""
    h,w=prediction.shape[:2]
    guide=cv2.resize(gray,(w,h),interpolation=cv2.INTER_AREA).astype(np.float32)/255
    color=prediction.astype(np.float32)/255
    mean_g=cv2.boxFilter(guide,-1,(7,7))
    mean_p=cv2.boxFilter(color,-1,(7,7))
    variance=cv2.boxFilter(guide*guide,-1,(7,7))-mean_g*mean_g
    covariance=cv2.boxFilter(guide[:,:,None]*color,-1,(7,7))-mean_g[:,:,None]*mean_p
    a=covariance/(variance[:,:,None]+.008)
    b=mean_p-a*mean_g[:,:,None]
    size=(gray.shape[1],gray.shape[0])
    a=cv2.resize(cv2.boxFilter(a,-1,(7,7)),size,interpolation=cv2.INTER_LINEAR)
    b=cv2.resize(cv2.boxFilter(b,-1,(7,7)),size,interpolation=cv2.INTER_LINEAR)
    return np.rint(np.clip(a*(gray.astype(np.float32)/255)[:,:,None]+b,0,1)*255).astype(np.uint8)


def transfer(gray, prediction, mode, intensity=100):
    """Transfer model color while keeping the scan on its native pixel grid."""
    if mode not in ("tint", "luma", "balanced", "generated"):
        raise ValueError(tr("Неизвестный режим цвета: {0}", mode))
    if mode == "generated":
        result = cv2.resize(prediction, (gray.shape[1],gray.shape[0]), interpolation=cv2.INTER_CUBIC)
        if intensity != 100:
            base = np.repeat(gray[:,:,None],3,axis=2)
            result = np.rint(base*(1-intensity/100)+result*(intensity/100)).clip(0,255).astype(np.uint8)
        return result
    height, width = gray.shape
    result = (guided_resize(prediction,gray) if mode=='balanced' and min(prediction.shape[:2])>1 else
              cv2.resize(prediction, (width, height), interpolation=cv2.INTER_CUBIC))
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
        elif mode == "balanced":
            gray3=np.repeat(scan[:,:,None],3,axis=2).astype(np.float32)/255
            source_l=cv2.cvtColor(gray3,cv2.COLOR_RGB2LAB)[:,:,0]
            lab=cv2.cvtColor(rgb/255,cv2.COLOR_RGB2LAB)
            # At most 18 L* of model shading; color cannot darken skin without limit.
            lab[:,:,0]=np.clip(source_l+np.clip(lab[:,:,0]-source_l,-18,12)*(intensity/100),0,100)
            lab[:,:,1:]*=intensity/100
            mapped=cv2.cvtColor(lab,cv2.COLOR_LAB2RGB)
            result[start:end]=np.rint(mapped*255).clip(0,255)
            result[start:end][scan==0]=0
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
