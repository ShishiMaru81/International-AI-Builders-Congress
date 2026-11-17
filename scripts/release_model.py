"""Review reproducibility gates and export holdout failures before local prototype release."""
import csv,hashlib,json
from pathlib import Path
import torch
from PIL import Image
from torchvision import transforms
root=Path(__file__).resolve().parents[1]
out=root/'ml/artifacts';card=json.loads((out/'model.json').read_text());evaluation=json.loads((out/'evaluation.json').read_text())
assert card['field_validated'] is False
manifest=root/'data/plantvillage/manifest.csv'
assert hashlib.sha256(manifest.read_bytes()).hexdigest()==card['manifest_sha256']
rows=list(csv.DictReader(manifest.open(encoding='utf-8')))
assert len({r['group_id'] for r in rows})==len(rows)
assert evaluation['split_counts']=={'train':360,'val':90,'test':120}
torch.set_num_threads(2)
model=torch.jit.load(str(out/'model.pt')).eval()
transform=transforms.Compose([transforms.Resize((224,224)),transforms.ToTensor(),transforms.Normalize([.485,.456,.406],[.229,.224,.225])])
failures=[];correct=0
for row in [r for r in rows if r['split']=='test']:
    path=root/'data/plantvillage/images'/row['path']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']
    with Image.open(path) as im:
        with torch.inference_mode():prob=model(transform(im.convert('RGB')).unsqueeze(0)).softmax(1)[0]
    predicted=card['labels'][int(prob.argmax())]
    if predicted==row['label']:correct+=1
    else:failures.append({'path':row['path'],'expected':row['label'],'predicted':predicted,'score':float(prob.max())})
assert abs(correct/120-evaluation['metrics']['accuracy'])<1e-8
(out/'failures.json').write_text(json.dumps(failures,indent=2))
card.update(release_approved=True,release_scope='local research prototype only; controlled images; not field-validated',artifact_sha256=hashlib.sha256((out/'model.pt').read_bytes()).hexdigest(),release_checks=['official leaf-group disjointness','exact checksums','conservative dHash screening','holdout export parity','failure records retained'])
(out/'model.json').write_text(json.dumps(card,indent=2))
print(json.dumps({'exported_holdout_correct':correct,'holdout_count':120,'failures':len(failures),'release_scope':card['release_scope']}))
