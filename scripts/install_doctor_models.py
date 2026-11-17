"""Download pinned SafeTensors and export known architectures; never runs Hub code."""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT/'apps/api/app/doctor_catalog.json').read_text(encoding='utf-8'))


def fetch(repo: str, revision: str, filename: str, destination: Path, digest: str | None = None):
    url = f'https://huggingface.co/{repo}/resolve/{revision}/{filename}'
    payload = urllib.request.urlopen(url, timeout=90).read(32*1024*1024+1)
    if len(payload)>32*1024*1024: raise RuntimeError('Artifact exceeds download size limit')
    actual = hashlib.sha256(payload).hexdigest()
    if digest and actual != digest: raise RuntimeError('Pinned source artifact SHA-256 mismatch')
    destination.write_bytes(payload)
    return actual


def install(model_id: str, target: Path):
    import torch
    from safetensors.torch import load_file
    torch.set_num_threads(2)
    spec = CATALOG['models'][model_id]
    target.mkdir(parents=True, exist_ok=True)
    # Source files/failed exports are kept outside the published bundle until verification.
    with tempfile.TemporaryDirectory(prefix=f'doctor-{model_id}-') as temp:
        work = Path(temp)
        source_sha = fetch(spec['source_repo'],spec['revision'],'model.safetensors',work/'model.safetensors',spec['source_sha256'])
        config_sha = fetch(spec['source_repo'],spec['revision'],'config.json',work/'config.json')
        config = json.loads((work/'config.json').read_bytes())
        fetch(spec['source_repo'],spec['revision'],'README.md',work/'SOURCE_README.md')
        state = load_file(str(work/'model.safetensors'), device='cpu')
        if model_id=='plantvillage':
            from transformers import MobileNetV2Config, MobileNetV2ForImageClassification
            labels = [config['id2label'][str(i)] for i in range(38)]
            if labels != spec['labels']: raise RuntimeError('Source label order changed')
            native = MobileNetV2ForImageClassification(MobileNetV2Config.from_dict(config))
            native.load_state_dict(state, strict=True)
            class Logits(torch.nn.Module):
                def __init__(self, model): super().__init__(); self.model=model
                def forward(self, x): return self.model(pixel_values=x).logits
            native = Logits(native).eval()
        else:
            import timm
            labels = ['Rice___'+label.replace(' ','_') for label in config['label_names']]
            if labels != spec['labels'] or config['architecture']!='efficientnet_b0':
                raise RuntimeError('Rice source architecture/labels changed')
            native = timm.create_model('efficientnet_b0', pretrained=False, num_classes=len(labels)).eval()
            native.load_state_dict(state, strict=True)
        sample = torch.zeros(1,3,224,224)
        with torch.inference_mode(): exported = torch.jit.trace(native,sample,check_trace=True).eval()
        max_error = 0.
        for seed in [0,7,42]:
            torch.manual_seed(seed); sample = torch.randn(1,3,224,224)
            with torch.inference_mode(): a,b = native(sample),exported(sample)
            if tuple(b.shape)!=(1,len(labels)) or not torch.isfinite(b).all():
                raise RuntimeError('Invalid model output')
            error = float((a-b).abs().max()); max_error=max(max_error,error)
            if not torch.allclose(a,b,atol=1e-5,rtol=1e-5):raise RuntimeError('Native/export parity failed')
        exported.save(str(work/'model.pt'))
        # Reload the exact bytes being installed, not merely the in-memory trace.
        reloaded=torch.jit.load(str(work/'model.pt'),map_location='cpu').eval()
        with torch.inference_mode():
            if not torch.allclose(reloaded(sample),native(sample),atol=1e-5,rtol=1e-5):
                raise RuntimeError('Saved artifact parity failed')
        card={**spec,'version':f'{model_id}-{spec["revision"][:12]}',
            'artifact_sha256':hashlib.sha256((work/'model.pt').read_bytes()).hexdigest(),
            'source_sha256_verified':source_sha,'source_config_sha256':config_sha,
            'reported_metrics':None,'metrics':None,'independent_accuracy_evaluation':False,
            'integration_checks':{'native_export_tensor_controls':3,'max_absolute_logit_error':max_error,
                'saved_artifact_reload':True,'remote_code_executed':False},
            'conversion_versions':{p:importlib.metadata.version(p) for p in ['torch','torchvision','transformers','timm','safetensors']},
            'limitations':['Not field-validated by AgroSphere.',
                'Closed-set research classifier; arbitrary images or unknown diseases can receive high scores.',
                'Publisher metrics and limitations: '+spec['source_url']],
            'dataset':{'source':'See pinned upstream model card; PlantVillage/PlantDoc or Rice Leaf Disease Images.',
                'independently_reaudited':False,'model_license_declared':spec['license']}}
        (work/'model.json').write_text(json.dumps(card,indent=2),encoding='utf-8')
        # os.replace makes each published file complete; registry rejects mixed-version pairs.
        for filename in ['model.pt','model.json','SOURCE_README.md']:
            staging=target/(filename+'.tmp'); staging.write_bytes((work/filename).read_bytes()); os.replace(staging,target/filename)
        print(json.dumps({'model_id':model_id,'classes':len(labels),'artifact_sha256':card['artifact_sha256'],
            'parity_max_abs':max_error,'target':str(target)},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models',nargs='+',choices=list(CATALOG['models']),default=list(CATALOG['models']))
    parser.add_argument('--output',type=Path,default=ROOT/'ml/artifacts/multicrop')
    args=parser.parse_args()
    for model_id in args.models: install(model_id,args.output/model_id)
