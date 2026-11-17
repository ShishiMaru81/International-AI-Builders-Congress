"""Download a small, declared-label, official-leaf-grouped research subset.
Only official original color images are used. No random image-level split.
"""
import csv,hashlib,io,json,random,re,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from urllib.parse import quote
import httpx
from PIL import Image

OUT=Path('data/plantvillage');OUT.mkdir(parents=True,exist_ok=True)
client=httpx.Client(timeout=45,follow_redirects=True,limits=httpx.Limits(max_connections=10))
def get(url):
    for attempt in range(3):
        try:r=client.get(url);r.raise_for_status();return r
        except httpx.HTTPError:
            if attempt==2:raise
            time.sleep(1)
hf= get('https://huggingface.co/api/datasets/mohanty/PlantVillage').json()['sha']
gh= get('https://api.github.com/repos/spMohanty/PlantVillage-Dataset/commits/master').json()['sha']
base=f'https://huggingface.co/datasets/mohanty/PlantVillage/resolve/{hf}/'
card=get(base+'README.md').text
if 'license: cc-by-sa-3.0' not in card:raise RuntimeError('Dataset license declaration changed; review required')
(OUT/'source-card.md').write_text(card,encoding='utf-8')
leaf_raw=get(base+'leaf_grouping/leaf-map.json').content
(OUT/'leaf-map.json').write_bytes(leaf_raw);leaf_map=json.loads(leaf_raw)
splits={}
for split in ('train','test'):
    text=get(base+f'splits/color_{split}.txt').text
    (OUT/f'original_{split}.txt').write_text(text,encoding='utf-8');splits[split]=text.splitlines()
available=sorted({p.split('/')[2] for paths in splits.values() for p in paths if p.startswith('raw/color/Tomato')})
labels=[x for x in available if x in ('Tomato___healthy','Tomato___Early_blight','Tomato___Late_blight')]
if len(labels)!=3:raise RuntimeError(f'Expected selected labels not found in actual split: {available}')
def group(path):
    name=Path(path).name.split('___')[-1].split('copy')[0]
    key=re.sub(r'\.(jpg|png)$','',name,flags=re.I).strip().lower()
    matches=[x for x in leaf_map.get(key,[]) if path.split('/')[2]+':::' in x]
    return matches[0] if len(matches)==1 else None
seen={};candidates=[];rng=random.Random(42)
for label in labels:
    for original in ('train','test'):
        paths=[p for p in splits[original] if p.split('/')[2]==label];rng.shuffle(paths);groups={}
        for path in paths:
            g=group(path)
            if g:
                if g in seen and seen[g]!=original:raise RuntimeError('Official grouping crosses original split')
                seen[g]=original;groups.setdefault(g,path)
        selected=list(groups.items())[:150 if original=='train' else 40]
        print(f'{label} {original}: {len(groups)} verified groups; selecting {len(selected)}',flush=True)
        if len(selected)<(100 if original=='train' else 25):raise RuntimeError('Insufficient verified leaf groups')
        for i,(g,path) in enumerate(selected):candidates.append(dict(path=path,label=label,group_id=g,split='test' if original=='test' else ('val' if i<30 else 'train')))
def fetch(row):
    path=OUT/'images'/row['path'];path.parent.mkdir(parents=True,exist_ok=True)
    url=f'https://raw.githubusercontent.com/spMohanty/PlantVillage-Dataset/{gh}/'+quote(row['path'],safe='/')
    if not path.exists():path.write_bytes(get(url).content)
    with Image.open(path) as im:
        gray=im.convert('L').resize((9,8));pixels=list(gray.getdata());bits=[pixels[y*9+x]>pixels[y*9+x+1] for y in range(8) for x in range(8)];dh=sum(int(v)<<i for i,v in enumerate(bits))
    return row,hashlib.sha256(path.read_bytes()).hexdigest(),dh,url
results=[]
with ThreadPoolExecutor(max_workers=8) as pool:
    futures=[pool.submit(fetch,row) for row in candidates]
    for future in as_completed(futures):
        results.append(future.result())
        if len(results)%50==0:print(f'Downloaded {len(results)}/{len(candidates)}',flush=True)
# Conservative perceptual duplicate exclusion. Keep train first, then validation,
# then holdout; never move an original test group into training.
priority={'train':0,'val':1,'test':2};kept=[];digests=set();hashes=[];removed=[]
for row,digest,dh,url in sorted(results,key=lambda r:(priority[r[0]['split']],r[0]['path'])):
    if digest in digests or any((dh^h).bit_count()<=4 for h in hashes):removed.append(row['path']);continue
    digests.add(digest);hashes.append(dh);kept.append({**row,'sha256':digest,'source_url':url})
with (OUT/'manifest.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=['path','label','group_id','split','sha256','source_url']);w.writeheader();w.writerows(kept)
meta=dict(name='PlantVillage selected tomato color subset',version=hf,url='https://huggingface.co/datasets/mohanty/PlantVillage',license='CC BY-SA 3.0 (dataset card declaration)',attribution='Mohanty, Hughes and Salathe (2016), Digital Epidemiology Lab, EPFL. DOI:10.3389/fpls.2016.01419',permission_verified=True,permission_basis='Original author dataset card declares CC BY-SA 3.0; source retained, attribution provided. No independent legal review.',grouping_method='One image per unambiguous official physical-leaf ID. Original test split preserved; 30 training groups per class reserved for validation. Conservative dHash distance <=4 exclusion across all selected images.',downloaded_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),github_commit=gh,leaf_map_sha256=hashlib.sha256(leaf_raw).hexdigest(),labels=labels,removed_near_duplicates=len(removed),field_validated=False)
(OUT/'dataset.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
(OUT/'excluded.json').write_text(json.dumps(removed,indent=2))
print(json.dumps({'selected':len(kept),'labels':labels,'removed':len(removed),'counts':{label:{s:sum(r['label']==label and r['split']==s for r in kept) for s in ('train','val','test')} for label in labels}},indent=2))
