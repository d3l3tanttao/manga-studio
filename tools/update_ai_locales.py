"""Merge the reviewed-order AI strings into the existing 25 catalogs."""
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
rows=json.loads(Path(__file__).with_name('ai_locales.json').read_text('utf8'))
keys=rows['ru'].split('|')
assert len(keys)==30 and len(rows)==25
for code, text in rows.items():
    values=text.split('|')
    assert len(values)==len(keys),(code,len(values))
    path=root/'studio/locales'/f'{code}.json'
    catalog=json.loads(path.read_text('utf8'))
    catalog.update(zip(keys,values))
    path.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
