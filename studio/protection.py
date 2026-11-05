"""Offline text-region protection and conservative page-layout checks."""
from pathlib import Path
import cv2
import numpy as np
from PIL import Image


class TextProtector:
    def __init__(self, models):
        self.models = Path(models)
        self.reader = None

    def regions(self, source):
        if self.reader is None:
            import easyocr
            self.reader = easyocr.Reader(["en"], gpu=False, recognizer=False, download_enabled=False,
                model_storage_directory=str(self.models/"ocr"),
                user_network_directory=str(self.models/"ocr"/"user"), verbose=False)
        rgb = np.asarray(source.convert("RGB"))
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        h,w = gray.shape
        horizontal, free = self.reader.detect(rgb, min_size=10, canvas_size=2048,
            text_threshold=.8, low_text=.4, link_threshold=.4, add_margin=.15)
        mask = np.zeros((h,w),np.uint8)
        boxes = []
        for x0,x1,y0,y1 in horizontal[0]:
            x0,x1 = max(0,int(x0)-2),min(w,int(x1)+2)
            y0,y1 = max(0,int(y0)-2),min(h,int(y1)+2)
            if x1>x0 and y1>y0 and (x1-x0)*(y1-y0)<h*w*.2:
                mask[y0:y1,x0:x1] = 255
                boxes.append([x0,y0,x1,y1])
        for polygon in free[0]:
            points = np.rint(polygon).astype(np.int32)
            cv2.fillPoly(mask,[points],255)
            x,y,rw,rh = cv2.boundingRect(points)
            boxes.append([max(0,x),max(0,y),min(w,x+rw),min(h,y+rh)])
        # Preserve the interior of a closed white speech bubble if detected text
        # lies within it. Large border-connected paper/white clothes are excluded.
        count, labels, stats, _ = cv2.connectedComponentsWithStats(np.uint8(gray>=238),8)
        for x0,y0,x1,y1 in boxes:
            values, counts = np.unique(labels[y0:y1,x0:x1],return_counts=True)
            candidates = [(int(n),int(v)) for v,n in zip(values,counts) if v]
            if not candidates:
                continue
            label = max(candidates)[1]
            x,y,rw,rh,area = stats[label]
            if area < h*w*.13 and x>0 and y>0 and x+rw<w and y+rh<h and area>(x1-x0)*(y1-y0)*.7:
                region = np.uint8(labels==label)*255
                contours,_ = cv2.findContours(region,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
                cv2.drawContours(mask,contours,-1,255,cv2.FILLED)
        if boxes:
            mask = cv2.dilate(mask,np.ones((3,3),np.uint8))
        return mask, boxes


def finish(source, generated, text_mask=None, preserve_gutters=True, preserve_paper=True):
    original = np.asarray(source.convert("RGB"))
    result = np.asarray(generated.convert("RGB")).copy()
    gray = cv2.cvtColor(original,cv2.COLOR_RGB2GRAY)
    layout_mask = np.zeros(gray.shape,np.uint8)
    # On isolated illustrations, keep the connected paper outside the drawing.
    # Closing tiny ink gaps prevents the mask from leaking into clothes/skin.
    # This is a paper mask, not a semantic body/garment segmentation claim.
    white = cv2.morphologyEx(np.uint8(gray>=248),cv2.MORPH_OPEN,np.ones((3,3),np.uint8))
    _, labels = cv2.connectedComponents(white,8)
    border_ids = np.unique(np.concatenate((labels[0],labels[-1],labels[:,0],labels[:,-1])))
    paper = np.isin(labels,border_ids[border_ids>0])
    # Multi-panel pages generally have much less connected exterior paper.
    paper_mask = paper if preserve_paper and np.mean(paper)>.20 else np.zeros(gray.shape,bool)
    np.copyto(result,original,where=paper_mask[:,:,None])
    if preserve_gutters:
        for axis in (0,1):
            empty = np.mean(gray>=248,axis=axis)>.998
            # Require adjacent clear scan lines, avoiding isolated highlight pixels.
            clear = np.convolve(empty.astype(np.uint8),np.ones(3,dtype=np.uint8),mode="same")>=3
            # Only interior gutters. Restoring outer blank scan lines would make
            # conspicuous white stripes on an intentionally colored background.
            occupied = np.flatnonzero(~empty)
            if occupied.size:
                clear[:occupied[0]+1] = False
                clear[occupied[-1]:] = False
            else:
                clear[:] = False
            if axis==0:
                layout_mask[:,clear] = 255
            else:
                layout_mask[clear,:] = 255
        np.copyto(result,original,where=(layout_mask>0)[:,:,None])
    if text_mask is not None:
        np.copyto(result,original,where=(text_mask>0)[:,:,None])
    small_shape = (max(1,round(gray.shape[1]*min(1,1000/max(gray.shape)))),
                   max(1,round(gray.shape[0]*min(1,1000/max(gray.shape)))))
    before = cv2.resize(gray,small_shape,interpolation=cv2.INTER_AREA)
    after = cv2.resize(cv2.cvtColor(result,cv2.COLOR_RGB2GRAY),small_shape,interpolation=cv2.INTER_AREA)
    a,b = cv2.Canny(before,80,180),cv2.Canny(after,80,180)
    near_b = cv2.dilate(b,np.ones((5,5),np.uint8))
    coverage = float(np.count_nonzero((a>0)&(near_b>0))/max(1,np.count_nonzero(a)))
    metadata = {"source_edge_coverage":round(coverage,4),
                "protected_text_pixels":int(np.count_nonzero(text_mask)) if text_mask is not None else 0,
                "protected_text_changed_pixels":int(np.count_nonzero(np.any(result!=original,axis=2)&(text_mask>0))) if text_mask is not None else 0,
                "protected_gutter_pixels":int(np.count_nonzero(layout_mask)),
                "protected_paper_pixels":int(np.count_nonzero(paper_mask)),
                "warnings":["source_contours_changed"] if coverage<.8 else []}
    return Image.fromarray(result), metadata
