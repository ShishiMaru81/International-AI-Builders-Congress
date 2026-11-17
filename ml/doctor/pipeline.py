"""Train/evaluate a tomato classifier from an explicitly permitted grouped manifest.

No dataset is downloaded or randomly split here. Review the dataset and assign
leaf/plant/near-duplicate groups before building the manifest described in README.
"""
import argparse,csv,hashlib,json,random,time
from pathlib import Path

def validate_manifest(manifest,root,license_file):
    license=json.loads(Path(license_file).read_text(encoding='utf-8'))
    for key in ('name','version','url','license','attribution','permission_verified','grouping_method'):
        if not license.get(key):raise ValueError(f'Missing verified dataset field: {key}')
    rows=list(csv.DictReader(Path(manifest).open(encoding='utf-8')))
    groups={};hashes={};labels={};base=Path(root).resolve()
    for row in rows:
        if row['split'] not in ('train','val','test') or not row['group_id']:raise ValueError('Invalid split/group')
        if 'tomato' not in row['label'].lower():raise ValueError('Tomato labels only; discover labels from actual data')
        p=(base/row['path']).resolve()
        if not p.is_relative_to(base):raise ValueError('Image path escapes dataset directory')
        digest=hashlib.sha256(p.read_bytes()).hexdigest()
        for lookup,key in [(groups,row['group_id']),(hashes,digest)]:
            if key in lookup and lookup[key]!=row['split']:raise ValueError('Group or exact duplicate leakage across splits')
            lookup[key]=row['split']
        labels.setdefault(row['split'],set()).add(row['label'])
    if set(labels)!= {'train','val','test'} or len(labels['train'])<2 or any(labels[s]!=labels['train'] for s in labels):raise ValueError('Each split must contain all actual selected classes (at least two)')
    return rows,license,sorted(labels['train'])

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--root',required=True);p.add_argument('--license',required=True);p.add_argument('--output',default='ml/artifacts');p.add_argument('--epochs',type=int,default=8);p.add_argument('--seed',type=int,default=42);p.add_argument('--validate-only',action='store_true');args=p.parse_args()
    rows,dataset,labels=validate_manifest(args.manifest,args.root,args.license)
    if args.validate_only:print(json.dumps({'labels':labels,'images':len(rows),'status':'manifest_valid; near-duplicate grouping still requires documented review'}));return
    import numpy as np
    import torch
    from torch import nn
    from torch.utils.data import Dataset,DataLoader
    from torchvision import transforms,models
    from PIL import Image
    from sklearn.metrics import accuracy_score,f1_score,classification_report,confusion_matrix
    random.seed(args.seed);np.random.seed(args.seed);torch.manual_seed(args.seed)
    torch.set_num_threads(min(4,torch.get_num_threads()))
    device=torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    normal=transforms.Normalize([.485,.456,.406],[.229,.224,.225])
    eval_transform=transforms.Compose([transforms.Resize((224,224)),transforms.ToTensor(),normal])
    train_transform=transforms.Compose([transforms.Resize((256,256)),transforms.RandomResizedCrop(224,scale=(.75,1)),transforms.RandomHorizontalFlip(),transforms.ToTensor(),normal])
    class Images(Dataset):
        def __init__(self,split):self.rows=[r for r in rows if r['split']==split];self.transform=train_transform if split=='train' else eval_transform
        def __len__(self):return len(self.rows)
        def __getitem__(self,i):
            row=self.rows[i]
            with Image.open(Path(args.root)/row['path']) as im:x=self.transform(im.convert('RGB'))
            return x,labels.index(row['label'])
    loaders={s:DataLoader(Images(s),batch_size=24,shuffle=s=='train',num_workers=0) for s in ('train','val','test')}
    model=models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.DEFAULT)
    for param in model.features.parameters():param.requires_grad=False
    model.classifier[-1]=nn.Linear(model.classifier[-1].in_features,len(labels));model.to(device)
    opt=torch.optim.AdamW(filter(lambda p:p.requires_grad,model.parameters()),lr=.001);loss_fn=nn.CrossEntropyLoss()
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True);best=-1
    def predict(split):
        model.eval();ys=[];ps=[]
        with torch.inference_mode():
            for x,y in loaders[split]:ys.extend(y.tolist());ps.extend(model(x.to(device)).softmax(1).cpu().tolist())
        return np.array(ys),np.array(ps)
    for epoch in range(args.epochs):
        model.train();model.features.eval()
        for x,y in loaders['train']:
            opt.zero_grad();loss=loss_fn(model(x.to(device)),y.to(device));loss.backward();opt.step()
        y,prob=predict('val');score=f1_score(y,prob.argmax(1),average='macro')
        print(json.dumps({'epoch':epoch+1,'validation_macro_f1':score}),flush=True)
        if score>best:best=score;torch.save(model.state_dict(),out/'checkpoint.pt')
    model.load_state_dict(torch.load(out/'checkpoint.pt',map_location=device,weights_only=True))
    vy,vp=predict('val');confidence=vp.max(1);correct=vp.argmax(1)==vy
    # Select on validation only; target accepted precision >=90%, minimum five accepted.
    candidates=[float(t) for t in np.arange(.5,.96,.025) if (confidence>=t).sum()>=5 and correct[confidence>=t].mean()>=.9]
    threshold=min(candidates) if candidates else 1.0
    start=time.perf_counter();y,prob=predict('test');elapsed=time.perf_counter()-start;pred=prob.argmax(1);conf=prob.max(1)
    ece=0.
    for low in np.arange(0,1,.1):
        mask=(conf>low)&(conf<=low+.1)
        if mask.any():ece+=float(mask.mean()*abs((pred[mask]==y[mask]).mean()-conf[mask].mean()))
    metrics={'accuracy':float(accuracy_score(y,pred)),'macro_f1':float(f1_score(y,pred,average='macro')),'ece':ece,'abstention_rate':float((conf<threshold).mean()),'seconds_per_image':elapsed/len(y)}
    report={'metrics':metrics,'per_class':classification_report(y,pred,target_names=labels,output_dict=True,zero_division=0),'confusion_matrix':confusion_matrix(y,pred).tolist(),'split_counts':{s:len(loaders[s].dataset) for s in loaders},'seed':args.seed,'field_metrics':None}
    report['model_bytes']=sum(p.numel()*p.element_size() for p in model.parameters())
    (out/'evaluation.json').write_text(json.dumps(report,indent=2))
    traced=torch.jit.trace(model.cpu().eval(),torch.zeros(1,3,224,224));traced.save(str(out/'model.pt'))
    card={'version':'mobilenetv3-tomato-'+hashlib.sha256(Path(args.manifest).read_bytes()).hexdigest()[:10],'available':True,'release_approved':False,'field_validated':False,'labels':labels,'metrics':metrics,'dataset':dataset,'manifest_sha256':hashlib.sha256(Path(args.manifest).read_bytes()).hexdigest(),'threshold':threshold,'score_type':'uncalibrated_model_score','limitations':['Controlled-image results only. Not field-validated.','Softmax scores are not calibrated diagnostic probabilities.','Out-of-distribution rejection is not validated.']}
    (out/'model.json').write_text(json.dumps(card,indent=2));print('Artifacts written. Review grouping, metrics and failures before setting release_approved=true. No automatic release.')
if __name__=='__main__':main()
