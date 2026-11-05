"""Reproducible local GPU comparison. User images are never bundled or uploaded."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from studio.generation import Renderer, image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--models', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    renderer = Renderer(args.models, lambda stage, **kw: print(stage, kw, flush=True))
    source = image(args.source)
    cases = [('auto', {}), ('strict', {'fidelity':'strict'}),
             ('reference', {'generation':'reference','reference':str(args.reference),'reference_role':'all'}),
             ('palette', {'generation':'reference','reference':str(args.reference),'reference_role':'palette'}),
             ('skin', {'correction':'skin','base':str(args.output/'reference.png')}),
             ('face', {'correction':'face','base':str(args.output/'reference.png')})]
    try:
        for name, changes in cases:
            output = args.output/(name+'.png')
            if output.exists():
                continue
            result, meta = renderer.render(source, {'generation':'color','precision':'bf16', **changes})
            result.save(output)
            output.with_suffix('.json').write_text(json.dumps(meta, indent=2), 'utf8')
            print('SAVED', name, meta['seconds_total'], flush=True)
    finally:
        renderer.release()


if __name__ == '__main__':
    main()
