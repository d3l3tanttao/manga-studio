"""Optional native Windows SAM 2 adapter and an explicit non-AI contour tool."""
import hashlib
from pathlib import Path
import sys
import threading

import numpy as np

from .engine import ROOT
from .regions import component_mask, refine_mask


GPU_LOCK = threading.RLock()
SAM_REVISION = "2b90b9f5ceec907a1c18123530e92e794ad901a4"


class Segmenter:
    def __init__(self):
        self.predictor = None
        self.key = None
        self.device = "cpu"
        self.image_key = None

    @staticmethod
    def checkpoint(variant='small'):
        return ROOT / '.models' / f'sam2.1_hiera_{variant}.pt'

    @staticmethod
    def available(variant='small'):
        return Segmenter.checkpoint(variant).is_file() and any((ROOT/p/'sam2').is_dir() for p in ('.sam2','.sam2-src'))

    def release(self):
        self.predictor = self.key = self.image_key = None

    def prepare(self,device='auto',variant='small'):
        import torch
        for folder in ('.sam2','.sam2-src'):
            root=ROOT/folder
            if (root/'sam2').is_dir():
                if str(root) not in sys.path:
                    sys.path.insert(0,str(root))
                break
        from sam2.build_sam import build_sam2
        from sam2.sam2_image_predictor import SAM2ImagePredictor
        device=('cuda' if torch.cuda.is_available() else 'cpu') if device=='auto' else device
        weight=self.checkpoint(variant)
        stat=weight.stat()
        key=(device,str(weight),stat.st_size,stat.st_mtime_ns)
        if self.key!=key:
            self.release()
            config='l' if variant=='large' else 's'
            model=build_sam2(f'configs/sam2.1/sam2.1_hiera_{config}.yaml',str(weight),device=device,apply_postprocessing=False)
            self.predictor=SAM2ImagePredictor(model,max_hole_area=0,max_sprinkle_area=0)
            self.key,self.device=key,device

    def predict(self,image,points,box=None,device='auto',backend='sam2',cancelled=lambda:False):
        gray=np.asarray(image.convert('L'))
        if backend=='contour':
            return [component_mask(gray,points,box)],[],{'engine':'contour','revision':1}
        variant='large' if 'large' in backend else 'small'
        if not self.available(variant):
            raise FileNotFoundError('SAM 2.1 is not installed. Run setup.ps1 -InstallSelection or use the contour tool.')
        import torch
        rgb=np.array(image.convert('RGB'))
        image_key=hashlib.sha256(rgb.tobytes()).hexdigest()
        with GPU_LOCK,torch.inference_mode():
            self.prepare(device,variant)
            if cancelled():
                return [],[],{}
            if image_key!=self.image_key:
                self.predictor.set_image(rgb)
                self.image_key=image_key
            if cancelled():
                return [],[],{}
            coords=np.float32([(x*(image.width-1),y*(image.height-1)) for x,y,_ in points])
            labels=np.int32([bool(positive) for _,_,positive in points])
            bounds=np.float32([box[0]*image.width,box[1]*image.height,box[2]*image.width,box[3]*image.height]) if box else None
            if backend.endswith('-parts') and np.count_nonzero(labels)>1:
                # Distinct body/clothing parts need independent region hypotheses.
                # Treating all positive points as one SAM instance can fragment them.
                unions=[np.zeros(gray.shape,bool) for _ in range(3)];part_scores=[]
                negative=coords[labels==0]
                for positive in coords[labels==1]:
                    if cancelled():return [],[],{}
                    prompts=np.concatenate((positive[None],negative))
                    target=np.array([1]+[0]*len(negative),np.int32)
                    parts,quality,_=self.predictor.predict(point_coords=prompts,point_labels=target,
                                                           box=bounds,multimask_output=True)
                    def errors(mask):
                        return sum(bool(mask[round(y),round(x)])!=bool(label) for (x,y),label in zip(prompts,target))
                    ranked=sorted(range(len(parts)),key=lambda i:(errors(parts[i]),-float(quality[i])))
                    for i,index in enumerate(ranked):unions[i]|=parts[index]>0
                    part_scores.append([quality[index] for index in ranked])
                masks=np.asarray(unions);scores=np.mean(part_scores,axis=0)
            else:
                masks,scores,_=self.predictor.predict(point_coords=coords if len(coords) else None,
                                                     point_labels=labels if len(coords) else None,
                                                     box=bounds,multimask_output=True)
        output=[]
        for mask in masks:
            mask=np.uint8(mask)*255
            if box:
                scope=np.zeros_like(mask);x0,y0,x1,y1=map(int,bounds)
                scope[max(0,y0):min(image.height,y1),max(0,x0):min(image.width,x1)]=1
                mask[scope==0]=0
            refined=refine_mask(gray,mask,points=points)
            if box:
                refined[scope==0]=0
            output.append(refined)
        def disagreements(mask):
            return sum(bool(mask[round(y*(image.height-1)),round(x*(image.width-1))]>=128)!=bool(positive)
                       for x,y,positive in points)
        # A model's predicted IoU must never outrank explicit correction points.
        order=sorted(range(len(output)),key=lambda i:(disagreements(output[i]),-float(scores[i])))
        suffix='-parts' if backend.endswith('-parts') else ''
        return [output[i] for i in order],[float(scores[i]) for i in order],{'engine':f'sam2.1-{variant}{suffix}','revision':SAM_REVISION}

    def propose(self,image,device='auto',cancelled=lambda:False,variant='small'):
        import torch
        with GPU_LOCK,torch.inference_mode():
            self.prepare(device,variant)
            from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator
            if cancelled():return [],[],{}
            generator=SAM2AutomaticMaskGenerator(self.predictor.model,points_per_side=12,points_per_batch=16,
                                                pred_iou_thresh=.82,stability_score_thresh=.94,
                                                min_mask_region_area=0)
            proposals=generator.generate(np.array(image.convert('RGB')))
            # The generator has its own predictor; invalidate our cached image conservatively.
            self.image_key=None
        area=image.width*image.height
        proposals=[p for p in proposals if .002*area<p['area']<.85*area]
        proposals=sorted(proposals,key=lambda p:p['predicted_iou'],reverse=True)[:24]
        gray=np.asarray(image.convert('L'))
        masks=[refine_mask(gray,np.uint8(p['segmentation'])*255) for p in proposals]
        return masks,[float(p['predicted_iou']) for p in proposals],{'engine':'sam2.1-proposals','revision':SAM_REVISION}
