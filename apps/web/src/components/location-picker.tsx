'use client';
import dynamic from 'next/dynamic';
import {useId,useState} from 'react';
import {useQueryClient} from '@tanstack/react-query';
import {LoaderCircle,MapPin,Search,Check,Plus} from 'lucide-react';
import {request} from '@/lib/api';
import type {Farm} from '@/lib/types';

const FarmMap=dynamic(()=>import('./farm-map'),{ssr:false,loading:()=> <div className="skeleton map"/>});
export type AreaSelection={latitude:number;longitude:number;label:string;district:string;country:string};
type Place=AreaSelection&{id:string;name:string};
type SearchResult={results:Place[];source_name:string};
type Perform=(fn:()=>Promise<unknown>,message?:string)=>Promise<void>;

export function LocationPicker({value,onChange,locale='en'}:{value:AreaSelection|null;onChange:(area:AreaSelection|null)=>void;locale?:string}){
 const id=useId();const bn=locale==='bn';const t=(en:string,bnText:string)=>bn?bnText:en;
 const [query,setQuery]=useState('');const [result,setResult]=useState<SearchResult>();
 const [searching,setSearching]=useState(false);const [error,setError]=useState('');
 const [latitude,setLatitude]=useState(value?.latitude.toString()??'');
 const [longitude,setLongitude]=useState(value?.longitude.toString()??'');
 const valid=latitude.trim()!==''&&longitude.trim()!==''&&Number.isFinite(Number(latitude))&&Number.isFinite(Number(longitude))&&Math.abs(Number(latitude))<=90&&Math.abs(Number(longitude))<=180;
 function choose(area:AreaSelection){onChange(area);setLatitude(String(area.latitude));setLongitude(String(area.longitude))}
 function point(lat:number,lon:number){choose({latitude:lat,longitude:lon,label:`Map point ${lat.toFixed(5)}, ${lon.toFixed(5)}`,district:'Selected area',country:''})}
 async function search(){
  if(query.trim().length<2)return;setSearching(true);setError('');setResult(undefined);
  try{setResult(await request<SearchResult>(`/locations/search?q=${encodeURIComponent(query.trim())}&language=${bn?'bn':'en'}`))}
  catch(e){setError((e as Error).message)}finally{setSearching(false)}
 }
 return <div className="location-picker">
  <label htmlFor={`${id}-search`}>{t('Search any area','যেকোনো এলাকা খুঁজুন')}</label>
  <div className="area-search-row"><input id={`${id}-search`} placeholder={t('Town, district or village, e.g. Sylhet','শহর, জেলা বা গ্রামের নাম লিখুন')} value={query} disabled={searching} maxLength={100} onChange={e=>{setQuery(e.target.value);setResult(undefined)}} onKeyDown={e=>{if(e.key==='Enter'){e.preventDefault();void search()}}}/><button type="button" className="btn secondary" disabled={searching||query.trim().length<2} onClick={search}>{searching?<LoaderCircle className="spin" size={16}/>:<Search size={16}/>} {t('Search','খুঁজুন')}</button></div>
  {error&&<div className="error" role="alert">{error}</div>}
  {result&&<div className="area-results" aria-label={t('Area search results','অনুসন্ধানের ফলাফল')}>
   {result.results.length?result.results.map(area=><button type="button" className="area-result" key={area.id} onClick={()=>{choose(area);setResult(undefined);setQuery(area.name)}}><MapPin size={16}/><span><strong>{area.label}</strong><small>{area.latitude.toFixed(5)}, {area.longitude.toFixed(5)}</small></span></button>):<p className="helper">{t('No places found. Try a nearby town or select a point on the map.','কোনো এলাকা পাওয়া যায়নি। কাছাকাছি শহর খুঁজুন অথবা মানচিত্রে স্থান নির্বাচন করুন।')}</p>}
   <small className="helper">{result.source_name}</small>
  </div>}
  <FarmMap lat={value?.latitude??24.0023} lon={value?.longitude??90.4264} demo={!value} onSelect={point}/>
  <p className="helper">{t('Search worldwide, click anywhere on the map, or drag the pin. A selected point is not a surveyed farm boundary.','নাম দিয়ে খুঁজুন, মানচিত্রে ক্লিক করুন অথবা পিন সরান। নির্বাচিত বিন্দু জমির জরিপকৃত সীমানা নয়।')}</p>
  <div className="form-grid area-coordinates"><label htmlFor={`${id}-lat`}>{t('Latitude','অক্ষাংশ')}<input id={`${id}-lat`} inputMode="decimal" type="number" min="-90" max="90" step="any" value={latitude} onChange={e=>setLatitude(e.target.value)}/></label><label htmlFor={`${id}-lon`}>{t('Longitude','দ্রাঘিমাংশ')}<input id={`${id}-lon`} inputMode="decimal" type="number" min="-180" max="180" step="any" value={longitude} onChange={e=>setLongitude(e.target.value)}/></label></div>
  <div className="row wrap"><button type="button" className="btn secondary" disabled={!valid} onClick={()=>point(Number(latitude),Number(longitude))}>{t('Use coordinates','স্থানাঙ্ক ব্যবহার করুন')}</button>{value&&<button type="button" className="text-link" onClick={()=>{onChange(null);setLatitude('');setLongitude('')}}>{t('Clear selection','নির্বাচন মুছুন')}</button>}</div>
  {value&&<div className="selected-area" role="status"><MapPin size={18}/><div><strong>{value.label}</strong><small>{value.latitude.toFixed(5)}, {value.longitude.toFixed(5)} · {t('Preview — save below to apply','প্রাকদর্শন — প্রয়োগ করতে সংরক্ষণ করুন')}</small></div></div>}
 </div>;
}

export function FarmLocationEditor({farm,perform,onSaved,locale='en'}:{farm:Farm;perform:Perform;onSaved:()=>void;locale?:string}){
 const qc=useQueryClient();const bn=locale==='bn';const t=(en:string,bnText:string)=>bn?bnText:en;
 const [selection,setSelection]=useState<AreaSelection|null>(()=>farm.latitude!=null&&farm.longitude!=null?{latitude:farm.latitude,longitude:farm.longitude,label:farm.location_name||farm.district,district:farm.district,country:farm.country||''}:null);
 const [consent,setConsent]=useState(false);const [saving,setSaving]=useState(false);
 return <div className="farm-location-editor"><h3>{t('Choose your farm area','আপনার খামারের এলাকা নির্বাচন করুন')}</h3>
  <LocationPicker value={selection} onChange={setSelection} locale={locale}/>
  <label className="checkbox-label"><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)}/>{t('Save this location for my farm and use it for live Open-Meteo weather.','এই অবস্থান খামারের জন্য সংরক্ষণ করুন এবং সরাসরি আবহাওয়ার তথ্যের জন্য Open-Meteo-তে ব্যবহার করুন।')}</label>
  <button type="button" className="btn primary full" disabled={!selection||!consent||saving} onClick={async()=>{setSaving(true);try{await perform(async()=>{
   const saved=await request<Farm>(`/farms/${farm.id}/location`,{method:'PATCH',body:JSON.stringify({latitude:selection!.latitude,longitude:selection!.longitude,location_name:selection!.label,district:selection!.district,country:selection!.country,location_consent:true})});
   qc.setQueryData<Farm[]>(['farms'],previous=>previous?.map(item=>item.id===saved.id?saved:item));onSaved();
  },t('Area saved. Live weather now uses your selected location.','এলাকা সংরক্ষিত হয়েছে। নির্বাচিত অবস্থানের আবহাওয়া দেখানো হচ্ছে।'))}finally{setSaving(false)}}}>{saving?<LoaderCircle className="spin" size={16}/>:<Check size={16}/>} {t('Save area & use live weather','এলাকা সংরক্ষণ ও আবহাওয়া দেখুন')}</button>
 </div>;
}

export function FarmCreateForm({perform,locale='en'}:{perform:Perform;locale?:string}){
 const [name,setName]=useState('');const [district,setDistrict]=useState('');const [selection,setSelection]=useState<AreaSelection|null>(null);const [consent,setConsent]=useState(false);const [saving,setSaving]=useState(false);
 return <form onSubmit={async e=>{e.preventDefault();setSaving(true);try{await perform(async()=>{
  await request('/farms',{method:'POST',body:JSON.stringify({name,district,latitude:selection?.latitude??null,longitude:selection?.longitude??null,location_name:selection?.label??null,country:selection?.country??null,location_consent:selection?consent:false})});setName('');setDistrict('');setSelection(null);setConsent(false);
 },'Farm saved')}finally{setSaving(false)}}}>
  <label>Farm name<input required maxLength={100} value={name} onChange={e=>setName(e.target.value)}/></label>
  <LocationPicker key={selection?'selected':'unselected'} value={selection} onChange={area=>{setSelection(area);if(area)setDistrict(area.district)}} locale={locale}/>
  <label>District / area name<input required maxLength={80} value={district} onChange={e=>setDistrict(e.target.value)}/></label>
  <label className="checkbox-label"><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)}/>I consent to storing the selected coordinates for weather lookup. Clear the selection to save a district-only farm.</label>
  <button type="submit" className="btn primary" disabled={saving||Boolean(selection&&!consent)}><Plus size={17}/>Create farm</button>
 </form>;
}
