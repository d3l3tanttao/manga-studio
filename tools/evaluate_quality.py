"""Local evaluation on supplied pages. Images never leave the machine."""
import argparse
import json
from pathlib import Path
import sys
from time import perf_counter

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image

from studio.engine import Engine,Settings,open_page
from studio.materials import MaterialLayer,audit
from studio.regions import pack
from studio.segmentation import Segmenter


def evaluate(paths,destination,selection=None,points=(),backend='sam2'):
    destination.mkdir(parents=True,exist_ok=True)
    engine=Engine();report=[]
    try:
        for index,path in enumerate(paths,1):
            original=open_page(path)
            settings=Settings(device='cuda')
            started=perf_counter();engine.prepare(settings)
            pred=engine.predict(original,settings,[])
            colored=pred
            output=destination/f'{index:04d}.png';colored.save(output)
            report.append({'source':path.name,'dimensions':original.size,'seconds':perf_counter()-started,
                           'render_report':engine.last_report,'output':output.name})
            print(json.dumps(report[-1],ensure_ascii=False),flush=True)
    finally:
        engine.release_ai()
    if selection:
        original=open_page(selection)
        segmenter=Segmenter()
        started=perf_counter();masks,scores,info=segmenter.predict(original,points,device='cuda',backend=backend)
        mask=masks[0]
        layer=MaterialLayer(pack(mask),'Skin',(241,198,170),prompts=points,backend=info['engine'])
        # Deliberately contaminate the input. All owned pixels must discard the old color.
        red=np.full((original.height,original.width,3),(200,40,40),np.uint8)
        from studio.materials import compose_layers
        a=compose_layers(original,red,[layer]);b=compose_layers(original,np.asarray(original),[layer])
        assert np.array_equal(a[mask>0],b[mask>0])
        assert np.array_equal(b[mask==0],np.asarray(original)[mask==0])
        Image.fromarray(b).save(destination/'object-skin.png')
        Image.fromarray(mask).save(destination/'object-skin-mask.png')
        print(json.dumps({'selection_seconds':perf_counter()-started,'scores':scores,'audit':audit(original,b,[layer])}),flush=True)
        report.append({'selection':selection.name,'backend':info,'clicks':len(points),
                       'outside_changed_pixels':0,'old_chroma_pixels_in_mask':0,
                       'note':'Coverage is a model proposal, not a ground-truth accuracy measurement.'})
    (destination/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('pages',nargs='+',type=Path)
    parser.add_argument('--output',required=True,type=Path);parser.add_argument('--selection',type=Path)
    parser.add_argument('--points',type=Path,help='JSON array of [normalized x, normalized y, positive]')
    parser.add_argument('--backend',choices=('sam2','sam2-large','sam2-parts','sam2-large-parts'),default='sam2')
    args=parser.parse_args()
    if args.selection and not args.points:parser.error('--selection requires --points')
    points=json.loads(args.points.read_text()) if args.points else []
    evaluate(args.pages,args.output,args.selection,points,args.backend)
