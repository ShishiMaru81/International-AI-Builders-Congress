"""Fetch the public release model and verify its recorded digest during image build."""
import hashlib,json,os
from pathlib import Path
from urllib.request import urlopen

model_dir=Path(os.getenv('MODEL_DIR','/models'))
card=json.loads((model_dir/'model.json').read_text(encoding='utf-8'))
url='https://github.com/Nabib-Azad-Jisan/zyntrix-agrosphere-ai/releases/download/v0.1.0/model.pt'
with urlopen(url,timeout=90) as response:
    payload=response.read(25*1024*1024)
if hashlib.sha256(payload).hexdigest()!=card['artifact_sha256']:
    raise RuntimeError('Model release checksum mismatch; refusing to build an unverified artifact')
(model_dir/'model.pt').write_bytes(payload)
print('Verified research model release downloaded.')
