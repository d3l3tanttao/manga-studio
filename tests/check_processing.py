"""One actual FLUX worker request, with source immutability and provenance checks."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from studio.engine import Engine,Settings,open_page
from studio.chapter import source_hash
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();before=source_hash(a.source);original=open_page(a.source);engine=Engine();settings=Settings()
try:
    engine.prepare(settings);result=engine.predict(original,settings)
    assert result.size==original.size and source_hash(a.source)==before
    assert engine.last_report['backend']=='flux'
    a.output.parent.mkdir(parents=True,exist_ok=True);result.save(a.output)
    a.output.with_suffix('.json').write_text(json.dumps(engine.last_report,indent=2),'utf8')
finally:
    engine.release_ai()
print('PASS FLUX worker, source dimensions, unchanged input, provenance')
