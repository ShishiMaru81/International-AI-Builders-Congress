'use client';
import Link from 'next/link';
import {useEffect,useRef,useState} from 'react';
import {useQuery,useQueryClient} from '@tanstack/react-query';
import {ArrowRight,Camera,CheckCircle2,Download,ImagePlus,Leaf,LoaderCircle,ScanLine,Trash2} from 'lucide-react';
import {API,download,formatTime,getSessionToken,request} from '@/lib/api';
import type {Case,DoctorCapabilities,Farm,Plot} from '@/lib/types';

type Locale='en'|'bn';
type Perform=(fn:()=>Promise<unknown>,message?:string)=>Promise<void>;
export function conditionName(label:string){return label.split('___').pop()!.replaceAll('_',' ').replace(/\s+/g,' ').trim()}
export function cropName(id:string,capabilities?:DoctorCapabilities,locale:Locale='en'){
 const crop=capabilities?.crops.find(c=>c.id===id);
 return crop?(locale==='bn'?crop.name_bn:crop.name_en):id.replaceAll('_',' ');
}
export function useDoctorCapabilities(){return useQuery({queryKey:['doctor-capabilities'],queryFn:()=>request<DoctorCapabilities>('/doctor/capabilities'),staleTime:60000,retry:1})}

// The parent keys this component by plot identity. A context change unmounts it,
// aborts the request and discards all local photo/result state together.
export function DoctorStudio({plot,plots,farms,onSelectPlot,cases,casesTotal,casesHasMore,casesFetching,casesError,onLoadMore,locale}: {
 plot?:Plot;plots:Plot[];farms:Farm[];onSelectPlot:(id:string)=>void;cases:Case[];casesTotal:number;
 casesHasMore:boolean;casesFetching:boolean;casesError?:string;onLoadMore:()=>void;locale:Locale;
}){
 const {data:capabilities,error:catalogError,isFetching:catalogFetching,refetch}=useDoctorCapabilities();
 const qc=useQueryClient();const t=(en:string,bn:string)=>locale==='bn'?bn:en;
 const [crop,setCrop]=useState(plot?.crop||'tomato');const [file,setFile]=useState<File>();
 const [symptoms,setSymptoms]=useState('');const [result,setResult]=useState<Case>();
 const [error,setError]=useState('');const [pending,setPending]=useState(false);
 const [plotName,setPlotName]=useState('');const [farmId,setFarmId]=useState(farms[0]?.id||'');
 const [area,setArea]=useState('1');const [creating,setCreating]=useState(false);const [preview,setPreview]=useState('');
 const input=useRef<HTMLInputElement>(null);const camera=useRef<HTMLInputElement>(null);
 const flight=useRef<AbortController|null>(null);const generation=useRef(0);const locked=useRef(false);
 const capability=capabilities?.crops.find(c=>c.id===crop);
 const matching=plots.filter(p=>p.crop===crop);const matches=plot?.crop===crop;
 const canChoose=!!plot&&matches&&!!capability?.available;
 useEffect(()=>()=>{generation.current++;flight.current?.abort()},[]);
 useEffect(()=>{
  if(!file)return;
  const url=URL.createObjectURL(file);setPreview(url);
  return ()=>URL.revokeObjectURL(url);
 },[file]);
 function clearPhoto(){setFile(undefined);setPreview('');setResult(undefined);setError('');if(input.current)input.current.value='';if(camera.current)camera.current.value=''}
 function changeCrop(value:string){generation.current++;flight.current?.abort();clearPhoto();setCrop(value)}
 function choose(value?:File){
  if(locked.current||!canChoose||!value)return;
  if(!value.size||value.size>8*1024*1024||!['image/jpeg','image/png','image/webp'].includes(value.type)){
   clearPhoto();setError(t('Choose a non-empty JPG, PNG or WebP photo up to 8 MB.','৮ মেগাবাইটের মধ্যে JPG, PNG বা WebP ছবি দিন।'));return;
  }
  setError('');setResult(undefined);setFile(value);
 }
 async function screen(){
  if(locked.current||!file||!plot||!matches||!capability?.available)return;
  locked.current=true;setPending(true);setError('');setResult(undefined);
  const current=++generation.current;const controller=new AbortController();flight.current=controller;
  const form=new FormData();form.append('image',file);form.append('plot_id',plot.id);form.append('crop',crop);form.append('symptoms',symptoms);
  try{
   const response=await request<Case>('/doctor/cases',{method:'POST',body:form,signal:controller.signal});
   if(current===generation.current&&!controller.signal.aborted){setResult(response);await qc.invalidateQueries({queryKey:['cases']});await qc.invalidateQueries({queryKey:['actions']})}
  }catch(e){if(current===generation.current&&!controller.signal.aborted)setError((e as Error).message)}
  finally{if(current===generation.current){locked.current=false;setPending(false)}}
 }
 async function createPlot(){
  if(creating||!plotName.trim()||!(farmId||farms[0]?.id))return;
  setCreating(true);setError('');
  const current=++generation.current;
  try{
   const created=await request<Plot>('/plots',{method:'POST',body:JSON.stringify({farm_id:farmId||farms[0].id,name:plotName.trim(),crop,area_acres:area,stage:'Vegetative'})});
   await qc.invalidateQueries({queryKey:['plots']});
   if(current===generation.current)onSelectPlot(created.id);
  }catch(e){if(current===generation.current)setError((e as Error).message)}finally{if(current===generation.current)setCreating(false)}
 }
 return <><div className="studio-grid"><section className="panel upload-panel">
  <div className="section-heading"><div><span className="eyebrow">CROP HEALTH STUDIO</span><h2>{t('Give your leaf a closer look.','পাতার ছবি আপলোড করুন')}</h2></div><span className="badge">{capabilities?`${capabilities.crops.length} ${t('crop groups','ফসল')}`:t('Loading crops…','ফসল লোড হচ্ছে…')}</span></div>
  <div className="form-grid"><label>{t('Crop','ফসল')}<select aria-label="Screening crop" value={crop} disabled={pending||creating||!capabilities} onChange={e=>changeCrop(e.target.value)}>
   {capabilities?.crops.map(c=><option key={c.id} value={c.id}>{c.name_en} · {c.name_bn}{c.available?'':` (${t('unavailable','অনুপলব্ধ')})`}</option>)}
  </select></label><label>{t('Selected plot','নির্বাচিত জমি')}<select aria-label="Screening plot" disabled={pending||creating} value={matches?plot?.id:''} onChange={e=>{if(e.target.value)onSelectPlot(e.target.value)}}><option value="">{t('Choose a matching plot','মিল থাকা জমি বেছে নিন')}</option>{matching.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></label></div>
  {!matches&&<div className="notice"><div><strong>{t('Select or create a plot for this crop.','এই ফসলের জমি বেছে নিন বা তৈরি করুন।')}</strong><p>{t('An observation must use the same crop as its plot.','পর্যবেক্ষণ ও জমির ফসল একই হতে হবে।')}</p>{!matching.length&&<form onSubmit={e=>{e.preventDefault();void createPlot()}}><label>{t('Farm','খামার')}<select aria-label="New crop plot farm" value={farmId||farms[0]?.id||''} onChange={e=>setFarmId(e.target.value)}>{farms.map(f=><option key={f.id} value={f.id}>{f.name}</option>)}</select></label><label>{t('Plot name','জমির নাম')}<input aria-label="New crop plot name" required maxLength={100} value={plotName} onChange={e=>setPlotName(e.target.value)}/></label><label>{t('Area (acres)','ক্ষেত্রফল (একর)')}<input aria-label="New crop plot area" type="number" required min="0.01" max="10000" step="0.01" value={area} onChange={e=>setArea(e.target.value)}/></label><button className="btn secondary" disabled={creating||!farms.length||!plotName.trim()}>{creating?t('Creating…','তৈরি হচ্ছে…'):t('Create crop plot','ফসলের জমি তৈরি করুন')}</button></form>}</div></div>}
  {catalogError&&<div className="error" role="alert">{t('Could not load crop capabilities.','ফসলের তালিকা লোড হয়নি।')} <button onClick={()=>void refetch()}>{t('Retry','আবার চেষ্টা')}</button></div>}
  {capability&&!capability.available&&<p className="error" role="alert">{t('Model unavailable for this crop.','এই ফসলের মডেল অনুপলব্ধ।')} {t('Install and verify its pinned model bundle before screening.','পরীক্ষার আগে মডেল ইনস্টল ও যাচাই করুন।')}</p>}
  <div className={`dropzone ${preview?'has-image':''}`} aria-busy={pending} onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();if(!locked.current)choose(e.dataTransfer.files[0])}}>
   {preview?<img src={preview} alt={t('Selected leaf for screening','পরীক্ষার জন্য নির্বাচিত পাতার ছবি')}/>:<><div className="upload-symbol"><ImagePlus size={35}/></div><h3>{t('A clear photo is a good beginning.','পরিষ্কার ছবি দিয়ে শুরু করুন।')}</h3><p>{t('Drop one leaf photo here, or choose from your device.','পাতার একটি ছবি দিন অথবা ডিভাইস থেকে বেছে নিন।')}</p></>}
   <div className="row"><button className="btn primary" disabled={pending||!canChoose} onClick={()=>input.current?.click()}><ImagePlus size={16}/>{t(preview?'Change photo':'Choose a photo',preview?'ছবি পরিবর্তন':'ছবি বেছে নিন')}</button><button className="btn secondary" disabled={pending||!canChoose} onClick={()=>camera.current?.click()}><Camera size={16}/>{t('Camera','ক্যামেরা')}</button>{file&&<button className="text-link" disabled={pending} onClick={clearPhoto}>{t('Remove','সরান')}</button>}</div>
   <input ref={input} aria-label="Upload leaf photo" type="file" accept="image/jpeg,image/png,image/webp" hidden disabled={pending||!canChoose} onChange={e=>{choose(e.target.files?.[0]);e.target.value=''}}/>
   <input ref={camera} aria-label="Take a leaf photo" type="file" accept="image/jpeg,image/png,image/webp" capture="environment" hidden disabled={pending||!canChoose} onChange={e=>{choose(e.target.files?.[0]);e.target.value=''}}/>
   <small>{t('JPG, PNG or WebP · Up to 8 MB · Private storage','JPG, PNG বা WebP · সর্বোচ্চ ৮ মেগাবাইট · ব্যক্তিগত সংরক্ষণ')}</small>
  </div>
  <label>{t('What have you noticed? (Optional)','কী লক্ষণ দেখেছেন? (ঐচ্ছিক)')}<textarea maxLength={2000} disabled={pending} value={symptoms} onChange={e=>setSymptoms(e.target.value)} placeholder={t('Spots, yellowing, when symptoms began…','দাগ, হলুদ পাতা, লক্ষণ শুরুর সময়…')}/></label>
  {error&&<p className="error" role="alert">{error}</p>}
  <button className="btn primary full" disabled={!file||!matches||!capability?.available||pending||creating||catalogFetching&&!capabilities} onClick={()=>void screen()}>{pending?<LoaderCircle size={18} className="spin"/>:<ScanLine size={18}/>} {pending?t('Checking image & saving…','পরীক্ষা ও সংরক্ষণ হচ্ছে…'):t('Screen & save observation','পরীক্ষা করুন ও সংরক্ষণ করুন')}<ArrowRight size={17}/></button>
  <p className="helper">{t('Research screening only. Confirm the crop yourself. Unknown diseases and non-leaf images may receive high scores; this is not a diagnosis.','এটি গবেষণা পর্যায়ের সহায়তা। ফসল নিজে নিশ্চিত করুন। অজানা রোগ বা পাতাবিহীন ছবিতেও বেশি স্কোর আসতে পারে; এটি নিশ্চিত রোগ নির্ণয় নয়।')}</p>
  {capability&&<details><summary>{t('Supported conditions & limits','সমর্থিত অবস্থা ও সীমাবদ্ধতা')} ({capability.labels.length})</summary><p>{capability.labels.map(conditionName).join(' · ')}</p>{!capability.has_healthy_class&&<p className="error">{t('This crop has no healthy reference class. A healthy leaf cannot be ruled in or out.','এই ফসলের সুস্থ পাতার শ্রেণি নেই। সুস্থ কি না নিশ্চিত করা যায় না।')}</p>}<small>{capability.model_version} · {t('Not field-validated','মাঠ পর্যায়ে যাচাই করা হয়নি')}</small></details>}
 </section><div className="stack">{result?<DoctorResult result={result} locale={locale}/>:<section className="panel result-placeholder"><ScanLine size={38}/><h3>{t('Room for understanding.','ফসলকে বোঝার সুযোগ।')}</h3><p>{t('Your screening, possible conditions, model evidence and next steps will appear here.','পরীক্ষার ফল, সম্ভাব্য অবস্থা ও পরবর্তী করণীয় এখানে দেখুন।')}</p><span className="badge amber">{t('Uncertainty is part of the result','ফলাফলে অনিশ্চয়তা থাকে')}</span></section>}<section className="panel"><h3>{t('Let the leaf be the focus.','পাতা স্পষ্টভাবে দেখান।')}</h3>{[t('Use natural, even light.','প্রাকৃতিক ও সমান আলো ব্যবহার করুন।'),t('Get close and keep the camera steady.','কাছ থেকে স্থির ক্যামেরায় ছবি নিন।'),t('Photograph both sides of several leaves.','কয়েকটি পাতার দুই পাশের ছবি নিন।'),t('Avoid filters and distracting backgrounds.','ফিল্টার ও জটিল পটভূমি এড়িয়ে চলুন।')].map((tip,i)=><div className="tip" key={tip}><span>{i+1}</span>{tip}</div>)}</section></div></div>
 <section className="panel"><h2>{t('Recent screenings','সাম্প্রতিক পরীক্ষা')} · {casesTotal}</h2>{casesError&&<p className="error" role="alert">{casesError}</p>}{casesFetching&&!cases.length?<p role="status">{t('Loading screenings…','পরীক্ষা লোড হচ্ছে…')}</p>:<CaseList cases={cases} locale={locale}/>}<CasePagination total={casesTotal} shown={cases.length} hasMore={casesHasMore} pending={casesFetching} onLoadMore={onLoadMore}/></section></>;
}

export function DoctorResult({result,locale='en',imgUrl,imgError}:{result:Case;locale?:Locale;imgUrl?:string;imgError?:string}){
 const t=(en:string,bn:string)=>locale==='bn'?bn:en;const {data:capabilities}=useDoctorCapabilities();
 const reasons:Record<string,string>={crop_mismatch:t('The highest model score belongs to a different crop. Check the selected crop and take another photo.','সর্বোচ্চ স্কোর অন্য ফসলের জন্য এসেছে। ফসল যাচাই করে নতুন ছবি নিন।'),low_confidence:t('The model score did not meet the research screening threshold.','মডেলের স্কোর পরীক্ষার সীমা পূরণ করেনি।'),image_quality:t('The photo quality checks did not pass. Take a clearer photo.','ছবির মান যথেষ্ট নয়। আরও পরিষ্কার ছবি নিন।')};
 return <section className="panel result" aria-label="Screening result">
  {imgUrl&&<img src={imgUrl} alt={t('Submitted leaf photo','জমা দেওয়া পাতার ছবি')} style={{width:'100%',maxHeight:260,objectFit:'contain'}}/>}{imgError&&<p role="status">{imgError}</p>}
  <span className="badge amber">{result.meta.mode} · {cropName(result.crop||'tomato',capabilities,locale)}</span><p>{result.plot_name||result.plot_id}</p>
  <h2>{result.classification.abstained?t('Unable to classify reliably','নির্ভরযোগ্যভাবে শ্রেণিবিন্যাস করা যায়নি'):`${t('Possible','সম্ভাব্য')}: ${conditionName(result.classification.top_label)}`}</h2>
  <p>{reasons[result.classification.rejection_reason||'']||t('Screening support only. Ask a qualified agronomist to review symptoms.','এটি প্রাথমিক সহায়তা। কৃষিবিদের পরামর্শ নিন।')}</p>
  {result.classification.score!=null&&<p>{t('Uncalibrated model score','অক্যালিব্রেটেড মডেল স্কোর')}: {(result.classification.score*100).toFixed(1)}% · {t('Not diagnostic certainty','নিশ্চিত রোগ নির্ণয় নয়')}</p>}
  {result.quality_flags.map(flag=><span className="badge amber" key={flag}>{flag.replaceAll('_',' ')}</span>)}
  {result.classification.alternatives.length>0&&<details><summary>{t('Raw model alternatives','মডেলের বিকল্প স্কোর')}</summary>{result.classification.alternatives.map(a=><p key={a.label}>{a.label.split('___')[0].replaceAll('_',' ')} · {conditionName(a.label)}: {(a.score*100).toFixed(1)}%</p>)}</details>}
  <h4>{t('Next steps','পরবর্তী করণীয়')}</h4>{result.advice.map(advice=><div className="advice" key={advice}><CheckCircle2 size={16}/><span>{advice}</span></div>)}
  <div className="model-evidence"><small>{t('MODEL EVIDENCE','মডেলের তথ্য')}</small><strong>{result.model.version}</strong><p>{t('Not field-validated','মাঠ পর্যায়ে যাচাই করা হয়নি')} · {result.model.available?t('Verified artifact installed','যাচাইকৃত মডেল ইনস্টল আছে'):t('Artifact unavailable','মডেল অনুপলব্ধ')}</p>{result.model.source_url&&<a href={result.model.source_url} target="_blank" rel="noreferrer">{t('Upstream model & limitations','মূল মডেল ও সীমাবদ্ধতা')}</a>}<p>{result.disclaimer}</p></div>
 </section>;
}
export function CaseList({cases,locale}:{cases:Case[];locale:Locale}){
 const {data:capabilities}=useDoctorCapabilities();
 return cases.length?<div className="table-wrap"><table><thead><tr><th>{locale==='bn'?'ফসল ও জমি':'Crop & plot'}</th><th>{locale==='bn'?'ফলাফল':'Result'}</th><th>Model</th><th>{locale==='bn'?'সময়':'Bangladesh time'}</th><th/></tr></thead><tbody>{cases.map(c=><tr key={c.id}><td><Leaf size={16}/> {cropName(c.crop||'tomato',capabilities,locale)}<small>{c.plot_name||c.plot_id}</small></td><td>{c.classification.abstained?(locale==='bn'?'অনিশ্চিত':'Uncertain'):conditionName(c.classification.top_label)}</td><td>{c.model.version}</td><td>{formatTime(c.created_at,locale)}</td><td><Link className="text-link" href={`/${locale}/agrodoctor/${c.id}`}>{locale==='bn'?'খুলুন':'Open'}</Link></td></tr>)}</tbody></table></div>:<p>{locale==='bn'?'এই জমির কোনো পর্যবেক্ষণ নেই।':'No observations for this plot yet.'}</p>;
}
export function CasePagination({total,shown,hasMore,pending,onLoadMore}:{total:number;shown:number;hasMore:boolean;pending:boolean;onLoadMore:()=>void}){
 return <><p className="helper">Showing {shown} of {total} saved screenings for this plot.</p>{hasMore&&<button className="btn secondary full" disabled={pending} onClick={onLoadMore}>{pending?'Loading…':'Load older screenings'}</button>}</>;
}
export function CaseDetail({id,perform,locale}:{id:string;perform:Perform;locale:Locale}){
 const {data,error,isPending}=useQuery({queryKey:['case',id],queryFn:()=>request<Case>(`/doctor/cases/${id}`)});
 const [note,setNote]=useState('');const [imgUrl,setImgUrl]=useState('');const [imgError,setImgError]=useState('');
 useEffect(()=>{
  const controller=new AbortController();let url='';let disposed=false;
  async function load(){try{
   const response=await fetch(`${API}/doctor/cases/${id}/image`,{headers:{Authorization:`Bearer ${getSessionToken()}`},signal:controller.signal});
   if(!response.ok)throw new Error(response.status===410?'Photo no longer available. Case metadata is preserved.':'Photo could not be loaded.');
   const blob=await response.blob();if(disposed)return;url=URL.createObjectURL(blob);setImgUrl(url);
  }catch(e){if(!disposed&&!controller.signal.aborted)setImgError((e as Error).message)}}
  void load();return()=>{disposed=true;controller.abort();if(url)URL.revokeObjectURL(url)};
 },[id]);
 if(isPending)return <section className="panel" role="status">Loading case…</section>;
 if(error)return <section className="panel error" role="alert">{error.message}</section>;
 return <div className="two-grid"><DoctorResult result={data} locale={locale} imgUrl={imgUrl} imgError={imgError}/><section className="panel"><h2>{locale==='bn'?'পর্যবেক্ষণের নোট':'Observation notes'}</h2><p>{data.symptoms||'No symptoms recorded.'}</p><label>{locale==='bn'?'নতুন নোট':'New note'}<textarea maxLength={2000} value={note} onChange={e=>setNote(e.target.value)}/></label><button className="btn primary" disabled={!note.trim()} onClick={()=>void perform(async()=>{await request(`/doctor/cases/${id}/feedback`,{method:'POST',body:JSON.stringify({note:note.trim(),request_review:false})});setNote('')},'Note saved')}>Save note</button><button className="btn secondary" disabled={!note.trim()} onClick={()=>void perform(async()=>{await request(`/doctor/cases/${id}/feedback`,{method:'POST',body:JSON.stringify({note:note.trim(),request_review:true})});setNote('')},'Review request recorded locally')}>Record review request</button><p className="helper">Private notes only. No advisor has been contacted.</p>{data.feedback?.map(feedback=><div className="timeline-row" key={feedback.id}><div><strong>{feedback.request_review?'Local review request':'Note'}</strong><p>{feedback.note}</p><small>{formatTime(feedback.created_at,locale)}</small></div></div>)}<div className="row wrap"><button className="btn secondary" onClick={()=>void perform(()=>download(`/doctor/cases/${id}/report`,'agrodoctor-case.csv'),'Report downloaded')}><Download size={16}/>Export CSV</button><button className="btn secondary" disabled={!imgUrl} onClick={()=>void perform(()=>download(`/doctor/cases/${id}/image`,`${data.crop||'tomato'}-leaf.jpg`),'Photo downloaded')}><Download size={16}/>Download photo</button><button className="btn danger" onClick={()=>void perform(async()=>{await request(`/doctor/cases/${id}`,{method:'DELETE'});location.href=`/${locale}/agrodoctor`},'Case deleted')}><Trash2 size={16}/>Delete observation</button></div></section></div>;
}
