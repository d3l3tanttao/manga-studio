"""Download pinned model assets. Never uploads user images."""
import argparse
import hashlib
import json
import os
from pathlib import Path

os.environ.update(HF_HUB_DISABLE_TELEMETRY='1',HF_HUB_DISABLE_XET='1',HF_HUB_DOWNLOAD_TIMEOUT='120')
from huggingface_hub import snapshot_download

MODEL='black-forest-labs/FLUX.2-klein-4B'
REVISION='e7b7dc27f91deacad38e78976d1f2b499d76a294'

def main(models):
    dest=models/'flux2-klein-4b'
    snapshot_download(MODEL,revision=REVISION,local_dir=dest,max_workers=2,
        allow_patterns=['model_index.json','LICENSE.md','README.md','scheduler/*',
                        'text_encoder/*','tokenizer/*','transformer/*','vae/*'])
    (dest/'PROVENANCE.json').write_text(json.dumps(dict(repo_id=MODEL,revision=REVISION,
        license='Apache-2.0',source_url=f'https://huggingface.co/{MODEL}'),indent=2),encoding='utf8')
    auxiliary = models/'florence2-base'
    snapshot_download('microsoft/Florence-2-base',revision='5ca5edf5bd017b9919c05d08aebef5e4c7ac3bac',
        local_dir=auxiliary,max_workers=2,allow_patterns=['*.json','*.safetensors','*.py','LICENSE'])
    (auxiliary/'PROVENANCE.json').write_text(json.dumps(dict(repo_id='microsoft/Florence-2-base',
        revision='5ca5edf5bd017b9919c05d08aebef5e4c7ac3bac',license='MIT',purpose='face/hand phrase grounding'),indent=2),'utf8')
    import easyocr
    easyocr.Reader(['en'],gpu=False,recognizer=False,model_storage_directory=str(models/'ocr'),
                   user_network_directory=str(models/'ocr/user'),verbose=False)
    detector=models/'ocr/craft_mlt_25k.pth'
    checksum=hashlib.md5(detector.read_bytes()).hexdigest()
    if checksum!='2f8227d2def4037cdb3b34389dcf9ec1':
        raise RuntimeError('Unexpected CRAFT detector checkpoint')
    (models/'ocr/PROVENANCE.json').write_text(json.dumps(dict(
        source_url='https://github.com/JaidedAI/EasyOCR/releases/download/pre-v1.1.6/craft_mlt_25k.zip',
        md5=checksum,sha256=hashlib.sha256(detector.read_bytes()).hexdigest(),loader='easyocr==1.7.2'),indent=2),encoding='utf8')
    print('Models ready. Inference runs offline.')

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--models',type=Path,required=True)
    main(parser.parse_args().models)
