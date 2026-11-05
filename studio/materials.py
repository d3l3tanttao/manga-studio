"""Object colors are evaluated from the original, never painted onto previous hues."""
from dataclasses import asdict, dataclass, field
import hashlib
from uuid import uuid4

import cv2
import numpy as np

from .regions import pack, unpack


@dataclass
class MaterialLayer:
    mask: str
    name: str = ""
    color: tuple = (40,127,232)
    uid: str = field(default_factory=lambda:uuid4().hex)
    material: str = ""
    character: str = ""
    saturation: float = 1.0
    lightness: float = 0.0
    dark_lift: float = 0.0
    visible: bool = True
    locked: bool = False
    original: bool = False
    frozen: str = ""
    prompts: list = field(default_factory=list)
    scope: list | None = None
    backend: str = "manual"
    manual_add: str = ""
    manual_remove: str = ""
    source_digest: str = ""

    def serialize(self):
        return asdict(self)

    @classmethod
    def load(cls,data):
        values={key:value for key,value in data.items() if key in cls.__dataclass_fields__}
        values['color']=tuple(values.get('color',(40,127,232)))
        if len(values['color'])!=3 or any(not 0<=v<=255 for v in values['color']):
            raise ValueError("Invalid material color")
        for key,low,high in (('saturation',0,2),('lightness',-.5,.5),('dark_lift',0,.6)):
            raw=values.get(key,0.0 if key!='saturation' else 1.0)
            bounded=max(float(low),min(float(high),float(raw)))
            # Keep valid historical JSON numbers stable (0 and 0.0 hash differently).
            values[key]=raw if type(raw) in (int,float) and low<=raw<=high else bounded
        return cls(**values)


def image_digest(image):
    return hashlib.sha256(image.convert('RGB').tobytes()).hexdigest()


def material_color(gray,color,saturation=1.0,lightness=0.0,dark_lift=0.0):
    """Bounded LAB tone mapping; the swatch is the material's lit base color."""
    scan=gray.astype(np.float32)/255
    swatch=np.array([[color]],np.float32)/255
    lab=cv2.cvtColor(swatch,cv2.COLOR_RGB2LAB)[0,0]
    original_l=cv2.cvtColor(np.repeat(scan[:,:,None],3,2),cv2.COLOR_RGB2LAB)[:,:,0]
    # Preserve relative ink/texture contrast. At white paper, use material lightness.
    tone=original_l/100
    base_l=np.clip(lab[0]+lightness*100,0,100)
    target_l=original_l*base_l/100
    # Optional lifting affects broad black fills, not thin dark lines.
    if dark_lift>0:
        dark=np.uint8(gray<32)
        distance=cv2.distanceTransform(dark,cv2.DIST_L2,3)
        broad=np.clip((distance-2)/8,0,1)
        target_l+=dark_lift*70*broad*(1-tone)
    result=np.zeros((*gray.shape,3),np.float32)
    result[:,:,0]=np.clip(target_l,0,100)
    fade=np.clip(original_l/18,0,1)
    result[:,:,1]=lab[1]*saturation*fade
    result[:,:,2]=lab[2]*saturation*fade
    rgb=cv2.cvtColor(result,cv2.COLOR_LAB2RGB)
    return np.rint(rgb*255).clip(0,255).astype(np.uint8)


def compose_layers(original,base,layers):
    if any(layer.source_digest for layer in layers):
        actual=image_digest(original)
        if any(layer.source_digest and layer.source_digest!=actual for layer in layers):
            from .i18n import tr
            raise ValueError(tr('Исходный файл изменился во время обработки. Повторите страницу.'))
    gray=np.asarray(original.convert('L'))
    original_rgb=np.asarray(original.convert('RGB'))
    result=np.asarray(base).copy()
    masks=[]
    for layer in layers:
        if not layer.visible:
            continue
        mask=unpack(layer.mask,original.size)
        masks.append((layer,mask))
        if layer.locked:
            continue
        target=original_rgb if layer.original else material_color(gray,layer.color,layer.saturation,layer.lightness,layer.dark_lift)
        alpha=mask.astype(np.float32)[:,:,None]/255
        inside=mask>0
        # Rebuild the transition from the scan too. Old chroma must not survive at a soft edge.
        result[inside]=np.rint(target[inside]*alpha[inside]+original_rgb[inside]*(1-alpha[inside])).clip(0,255).astype(np.uint8)
    # Locks are composited last, so global recoloring cannot overwrite their pixels.
    for layer,mask in masks:
        if layer.locked:
            target=unpack(layer.frozen,original.size,'RGB') if layer.frozen else original_rgb
            np.copyto(result,target,where=(mask>0)[:,:,None])
    return result


def audit(original,result,layers):
    """Diagnostics describe measured conditions, not a calibrated AI confidence."""
    rgb=np.asarray(result.convert('RGB') if hasattr(result,'convert') else result)
    original_rgb=np.asarray(original.convert('RGB'))
    gray=np.asarray(original.convert('L'))
    findings=[]
    for layer in layers:
        if not layer.visible:
            continue
        mask=unpack(layer.mask,original.size)
        inside=mask==255
        if layer.locked:
            target=unpack(layer.frozen,original.size,'RGB') if layer.frozen else original_rgb
            wrong=int(np.any(rgb[mask>0]!=target[mask>0],axis=1).sum())
            findings.append({'kind':'protected','object':layer.name,'pixels':wrong})
        elif inside.any() and not layer.original:
            target=material_color(gray,layer.color,layer.saturation,layer.lightness,layer.dark_lift)
            # Other visible layers may legitimately overlap; check only owned pixels.
            own=inside.copy()
            index=layers.index(layer)
            for other in layers[index+1:]:
                if other.visible:
                    own[unpack(other.mask,original.size)>0]=False
            for other in layers:
                if other.visible and other.locked:
                    own[unpack(other.mask,original.size)>0]=False
            residual=int(np.any(rgb[own]!=target[own],axis=1).sum())
            findings.append({'kind':'material','object':layer.name,'pixels':residual})
        count,_,stats,_=cv2.connectedComponentsWithStats(np.uint8(mask>=128),8)
        small=int(sum(1 for area in stats[1:,cv2.CC_STAT_AREA] if area<16))
        if small:
            findings.append({'kind':'fragments','object':layer.name,'pixels':small})
    return findings
