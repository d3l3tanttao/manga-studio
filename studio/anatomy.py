"""Local phrase grounding for contextual FLUX edits, not a color-fill mask."""
import gc
import os
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


class RegionLocator:
    def __init__(self, models):
        self.folder = Path(models)/'florence2-base'
        self.cache = {}

    def find(self, image, kind):
        import hashlib
        key = (hashlib.sha256(image.tobytes()).hexdigest(),kind)
        if key in self.cache:
            return self.cache[key]
        # Pin and download the reviewed Microsoft implementation during setup.
        # Runtime never fetches code or model files from the network.
        os.environ['HF_MODULES_CACHE'] = str(self.folder.parent/'.modules')
        import torch
        from transformers import AutoModelForCausalLM, AutoProcessor
        import transformers.dynamic_module_utils as dynamic
        dynamic.HF_MODULES_CACHE = os.environ['HF_MODULES_CACHE']
        model = AutoModelForCausalLM.from_pretrained(self.folder, local_files_only=True,
            trust_remote_code=True, torch_dtype=torch.float32, attn_implementation='eager').eval()
        processor = AutoProcessor.from_pretrained(self.folder, local_files_only=True, trust_remote_code=True)
        task = '<CAPTION_TO_PHRASE_GROUNDING>'
        text = 'The face of a person.' if kind == 'face' else 'The hands of a person.'
        inputs = processor(text=task+text, images=image, return_tensors='pt')
        with torch.inference_mode():
            ids = model.generate(input_ids=inputs['input_ids'], pixel_values=inputs['pixel_values'],
                max_new_tokens=256, num_beams=1, do_sample=False, use_cache=False)
        text = processor.batch_decode(ids,skip_special_tokens=False)[0]
        data = processor.post_process_generation(text,task=task,image_size=image.size)[task]
        boxes = []
        for box, label in zip(data['bboxes'],data['labels']):
            if ('face' if kind=='face' else 'hand') not in label.lower():
                continue
            x0,y0,x1,y1 = [round(v) for v in box]
            x0,y0,x1,y1 = max(0,x0),max(0,y0),min(image.width,x1),min(image.height,y1)
            if min(x1-x0,y1-y0)<24 or (x1-x0)*(y1-y0)>image.width*image.height*.4:
                continue
            boxes.append([x0,y0,x1,y1])
        # Grounding may return overlapping copies of the same hand.
        unique = []
        for box in sorted(boxes,key=lambda b:(b[2]-b[0])*(b[3]-b[1]),reverse=True):
            if any(overlap(box, other)>.45 for other in unique):
                continue
            unique.append(box)
        del model, processor, inputs, ids
        gc.collect()
        if len(self.cache)>16:
            self.cache.clear()
        self.cache[key] = unique[:8]
        return self.cache[key]


def overlap(a,b):
    area = max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    return area/max(1,min((a[2]-a[0])*(a[3]-a[1]),(b[2]-b[0])*(b[3]-b[1])))


def context_box(box, size):
    x0,y0,x1,y1 = box
    dx,dy = max(24,round((x1-x0)*.4)),max(24,round((y1-y0)*.3))
    return [max(0,x0-dx),max(0,y0-dy),min(size[0],x1+dx),min(size[1],y1+dy)]


def composite_context(base, patch, original, box, context, kind):
    """Use the whole context to reason; feather changes around the target part.

    Broad source-black hair connected to the crop edge retains its existing color.
    This protection is conservative and is not a semantic hair segmentation claim.
    """
    x0,y0,x1,y1 = context
    size = (x1-x0,y1-y0)
    patch = patch.resize(size,Image.Resampling.LANCZOS)
    yy,xx = np.mgrid[y0:y1,x0:x1]
    pad = max(8,min(box[2]-box[0],box[3]-box[1])*.18)
    distance = np.minimum.reduce([xx-box[0],box[2]-1-xx,yy-box[1],box[3]-1-yy])
    alpha = np.clip((distance+pad)/pad,0,1).astype(np.float32)
    if kind == 'face':
        gray = np.asarray(original.crop(context).convert('L'))
        dark = cv2.erode(np.uint8(gray<40),np.ones((3,3),np.uint8))
        _,labels = cv2.connectedComponents(dark,8)
        edges = np.unique(np.concatenate([labels[0],labels[-1],labels[:,0],labels[:,-1]]))
        hair = np.isin(labels,edges[edges>0]).astype(np.uint8)
        hair = cv2.dilate(hair,np.ones((5,5),np.uint8)).astype(np.float32)
        alpha *= 1-cv2.GaussianBlur(hair,(0,0),1)
    before = np.asarray(base.crop(context)).astype(np.float32)
    rgb = np.rint(before*(1-alpha[:,:,None])+np.asarray(patch)*alpha[:,:,None]).clip(0,255).astype(np.uint8)
    result = base.copy()
    result.paste(Image.fromarray(rgb),(x0,y0))
    return result
