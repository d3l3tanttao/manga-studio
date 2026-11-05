"""Native-resolution region masks. No model weights or scene pixels in global state."""
import base64
import io

import cv2
import numpy as np
from PIL import Image


MAX_PIXELS = 80_000_000


def pack(array):
    stream = io.BytesIO()
    Image.fromarray(np.asarray(array, dtype=np.uint8)).save(stream, format="PNG")
    return base64.b64encode(stream.getvalue()).decode("ascii")


def unpack(value, size=None, mode="L"):
    with Image.open(io.BytesIO(base64.b64decode(value, validate=True))) as image:
        if image.width * image.height > MAX_PIXELS or image.format != "PNG":
            raise ValueError("Invalid region image")
        if size is not None and image.size != tuple(size):
            raise ValueError("Region dimensions differ from the original")
        return np.array(image.convert(mode))


def snap_regions(gray,binary,points=()):
    """Use confident semantic coverage to complete closed light cells of the scan.

    Open/ambiguous cells retain the neural proposal. Ink itself is never synthesized.
    """
    barrier=np.uint8(cv2.GaussianBlur(gray,(3,3),0)<150)
    # Include thin diagonal contours which a darkness threshold can miss.
    barrier |= np.uint8(cv2.Canny(gray,40,100)>0)
    barrier=cv2.morphologyEx(barrier,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
    count,labels,stats,_=cv2.connectedComponentsWithStats(1-barrier,8)
    areas=stats[:,cv2.CC_STAT_AREA]
    covered=np.bincount(labels.ravel(),weights=(binary.ravel()>0),minlength=count)
    fraction=covered/np.maximum(areas,1)
    positive=set();negative=set()
    h,w=gray.shape
    for x,y,inside in points:
        index=int(labels[min(h-1,round(y*(h-1))),min(w-1,round(x*(w-1)))])
        if index:(positive if inside else negative).add(index)
    choices=np.full(count,-1,np.int8)
    eligible=(areas>=12)&(areas<=gray.size*.28)
    choices[eligible&(fraction>=.55)]=1
    choices[(areas>=12)&(fraction<=.15)]=0
    for index in positive-negative:
        if eligible[index]:choices[index]=1
    for index in negative-positive:
        choices[index]=0
    for index in positive&negative:
        choices[index]=-1
    choices[0]=-1
    result=binary.copy();classification=choices[labels]
    result[classification==1]=255;result[classification==0]=0
    return repair_pinholes(gray,result,points)


def repair_pinholes(gray,binary,points=()):
    """Fill small enclosed mask defects only where the scan has no supporting edge."""
    count,labels,stats,_=cv2.connectedComponentsWithStats(np.uint8(binary==0),8)
    h,w=gray.shape
    protected={int(labels[round(y*(h-1)),round(x*(w-1))]) for x,y,inside in points if not inside}
    result=binary.copy();limit=max(16,min(256,gray.size//3000))
    for index in range(1,count):
        x,y,rw,rh,area=stats[index]
        if index in protected or area>limit or x==0 or y==0 or x+rw==w or y+rh==h:continue
        region=np.s_[y-1:y+rh+1,x-1:x+rw+1]
        hole=labels[region]==index
        patch=gray[region];values=patch[hole]
        if values.min()<200 or values.std()>12:continue
        ring=(cv2.dilate(np.uint8(hole),np.ones((3,3),np.uint8))>0)&~hole
        boundary=patch[ring]
        if not len(boundary) or np.mean(boundary<180)>.05 or abs(float(np.median(boundary))-float(np.median(values)))>12:continue
        result[region][hole]=255
    return result


def refine_mask(gray, mask, radius=2, points=()):
    """Refine only an uncertain boundary band. Preserve real holes and components."""
    height, width = gray.shape
    mask = cv2.resize(np.asarray(mask, np.uint8), (width, height), interpolation=cv2.INTER_LINEAR)
    binary = np.uint8(mask >= 128) * 255
    if not np.any(binary) or np.all(binary):
        return binary
    binary=snap_regions(gray,binary,points)
    radius = min(8, max(1, int(radius)))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius*2+1, radius*2+1))
    interior = cv2.erode(binary, kernel)
    exterior = cv2.dilate(binary, kernel)
    # A joint bilateral update respects scan edges without filling every tiny hole.
    guide = gray.astype(np.float32) / 255
    alpha = binary.astype(np.float32) / 255
    numerator = np.zeros_like(guide)
    denominator = np.zeros_like(guide)
    for dy, dx in ((0,0),(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(1,1),(-1,1),(1,-1)):
        shifted_g = cv2.copyMakeBorder(guide,1,1,1,1,cv2.BORDER_REFLECT)[1+dy:1+dy+height,1+dx:1+dx+width]
        shifted_a = cv2.copyMakeBorder(alpha,1,1,1,1,cv2.BORDER_REFLECT)[1+dy:1+dy+height,1+dx:1+dx+width]
        weight = np.exp(-((guide-shifted_g)/0.08)**2) * (1 if dx==dy==0 else .65)
        numerator += weight*shifted_a
        denominator += weight
    alpha = np.rint(numerator/denominator*255).astype(np.uint8)
    alpha[interior==255] = 255
    alpha[exterior==0] = 0
    return alpha


def paint_mask(mask, points, width, add=True, polygon=False):
    result = mask.copy()
    h,w = result.shape
    pts = np.int32([(round(x*(w-1)), round(y*(h-1))) for x,y in points])
    if not len(pts):
        return result
    value = 255 if add else 0
    diameter = max(1, round(width*w))
    if polygon and len(pts)>=3:
        cv2.fillPoly(result,[pts],value)
    else:
        cv2.circle(result,tuple(pts[0]),diameter//2,value,-1)
        cv2.polylines(result,[pts],False,value,diameter)
    return result


def region_outline(mask):
    binary = np.uint8(mask>=128)
    return (cv2.dilate(binary,np.ones((3,3),np.uint8))-cv2.erode(binary,np.ones((3,3),np.uint8)))*255


def component_mask(gray, points, box=None):
    """Explicit contour fallback, never presented as semantic AI selection."""
    h,w = gray.shape
    scale = min(1,1600/max(h,w))
    small = cv2.resize(gray,(max(1,round(w*scale)),max(1,round(h*scale))))
    barrier = np.uint8(small<125)
    barrier = cv2.morphologyEx(barrier,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
    if box:
        x0,y0,x1,y1 = box
        scope=np.zeros_like(barrier);scope[round(y0*small.shape[0]):round(y1*small.shape[0]),round(x0*small.shape[1]):round(x1*small.shape[1])]=1
        barrier[scope==0]=1
    _, labels = cv2.connectedComponents(1-barrier,8)
    keep=set(); remove=set()
    for x,y,positive in points:
        label=int(labels[min(labels.shape[0]-1,round(y*(labels.shape[0]-1))),min(labels.shape[1]-1,round(x*(labels.shape[1]-1)))])
        if label:
            (keep if positive else remove).add(label)
    mask=np.uint8(np.isin(labels,list(keep-remove)))*255
    return refine_mask(gray,mask)


def background_mask(gray):
    """Suggest paper connected to the image border, not every white pixel."""
    white=np.uint8(gray>=245)
    count,labels,stats,_=cv2.connectedComponentsWithStats(white,8)
    border=set(np.unique(np.concatenate((labels[0],labels[-1],labels[:,0],labels[:,-1]))))-{0}
    return np.uint8(np.isin(labels,list(border)))*255


def scene_regions(gray):
    """Conservative frame proposals; editable, with full-page context retained."""
    h,w=gray.shape
    scale=min(1,1000/max(h,w))
    small=cv2.resize(gray,(round(w*scale),round(h*scale)))
    edges=cv2.Canny(small,70,160)
    contours,_=cv2.findContours(edges,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
    regions=[]
    for contour in contours:
        perimeter=cv2.arcLength(contour,True)
        poly=cv2.approxPolyDP(contour,.025*perimeter,True)
        x,y,rw,rh=cv2.boundingRect(poly)
        ratio=rw*rh/(small.shape[0]*small.shape[1])
        if len(poly)==4 and cv2.isContourConvex(poly) and .04<ratio<.92 and min(rw,rh)>60:
            rect=[x/small.shape[1],y/small.shape[0],(x+rw)/small.shape[1],(y+rh)/small.shape[0]]
            if not any(sum(abs(a-b) for a,b in zip(rect,r))<.06 for r in regions):
                regions.append(rect)
    return sorted(regions,key=lambda b:(b[1],b[0]))[:24]
