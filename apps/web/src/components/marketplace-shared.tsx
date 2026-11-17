'use client';
import {cloneElement,createContext,isValidElement,useContext,useEffect,useId,useRef,useState,type ReactElement,type ReactNode} from 'react';
import {useQuery} from '@tanstack/react-query';
import {API,getSessionToken,request} from '@/lib/api';
import type {Product,PageOf,MarketRole} from '@/lib/marketplace-types';
import {cropImageFor} from '@/lib/crop-images';

export type MarketContextValue = {locale:'en'|'bn';t:(en:string,bn:string)=>string;role:MarketRole|null;userId:string;busy:boolean;perform:(fn:()=>Promise<unknown>,success?:string)=>Promise<boolean>;go:(path:string)=>void};
export const MarketContext=createContext<MarketContextValue|null>(null);
export function useMarket(){const c=useContext(MarketContext);if(!c)throw Error('Marketplace context missing');return c;}
export const send=<T,>(path:string,body:unknown,method='POST',headers?:HeadersInit)=>request<T>(path,{method,body:JSON.stringify(body),headers});
export function useMarketQuery<T>(path:string,enabled=true,interval?:number){const {userId}=useMarket();return useQuery({queryKey:['market',userId,path],queryFn:()=>request<T>(path),enabled,refetchInterval:interval,retry:false});}
export function rows<T>(value:T[]|PageOf<T>|undefined):T[]{return Array.isArray(value)?value:value?.items||[];}
export function cash(value:string|number|undefined){return `৳${Number(value||0).toLocaleString('en-BD',{minimumFractionDigits:2,maximumFractionDigits:2})}`;}
export function Field({label,children}:{label:string;children:ReactNode}){const id=useId();return <div className="mk-field"><label htmlFor={id}>{label}</label>{isValidElement(children)?cloneElement(children as ReactElement<{id:string}>,{id}):children}</div>;}
export function Panel({title,children}:{title?:string;children:ReactNode}){return <section className="mk-panel">{title&&<h2>{title}</h2>}{children}</section>;}
export function DataState({query}:{query:{isPending:boolean;error:Error|null;refetch:()=>unknown}}){const {t}=useMarket();return query.isPending?<p role="status">{t('Loading…','লোড হচ্ছে…')}</p>:query.error?<div role="alert" className="mk-error">{query.error.message} <button onClick={()=>void query.refetch()}>{t('Retry','আবার চেষ্টা করুন')}</button></div>:null;}
export function Empty({children}:{children:ReactNode}){return <p className="mk-empty">{children}</p>;}
export function useIdempotency(){const keys=useRef(new Map<string,string>());return (signature:string)=>{let value=keys.current.get(signature);if(!value){value=crypto.randomUUID();keys.current.set(signature,value);}return {'Idempotency-Key':value};};}
export function ProductImage({product,index=0}:{product:Product;index?:number}){
 const image=product.images[index];
 const source=image?.url?.startsWith('/api/v1/')?API.replace(/\/api\/v1\/?$/,'')+image.url:image?.url?.startsWith('/market/')?API+image.url:image?.url;
 const privateImage=!['published','out_of_stock'].includes(product.status)||product.moderation_status==='hidden';
 const {userId}=useMarket();
 // A changed account, thumbnail, source or visibility cannot reuse an old blob/error,
 // even during the render before an effect would otherwise clear the previous state.
 const key=JSON.stringify([product.id,image?.id,source,privateImage,userId]);
 return <ProductPhoto key={key} source={source} privateImage={privateImage} name={product.name} index={index}/>;
}
function ProductPhoto({source,privateImage,name,index}:{source?:string;privateImage:boolean;name:string;index:number}){
 const {t}=useMarket();const [blob,setBlob]=useState('');const [failed,setFailed]=useState(false);
 useEffect(()=>{
  if(!source||!privateImage)return;
  const controller=new AbortController();let objectUrl='';
  void fetch(source,{headers:{Authorization:`Bearer ${getSessionToken()||''}`},signal:controller.signal})
   .then(async response=>{
    if(!response.ok)throw Error('Image unavailable');
    const file=await response.blob();
    if(controller.signal.aborted)return;
    objectUrl=URL.createObjectURL(file);setBlob(objectUrl);
   }).catch(()=>{if(!controller.signal.aborted)setFailed(true);});
  return()=>{controller.abort();if(objectUrl)URL.revokeObjectURL(objectUrl);};
 },[source,privateImage]);
 if(!source||failed)return <IllustrativeCropImage key={name} name={name}/>;
 const src=privateImage?blob:source;
 // Uploaded marketplace images require native img because owners need authenticated blob URLs.
 // eslint-disable-next-line @next/next/no-img-element
 return src?<img className="mk-product-image" src={src} alt={`${name} ${index+1}`} onLoad={event=>{
  // Existing pixel/test uploads contain no usable produce detail. Keep the upload
  // untouched, but display the same labelled fallback as an unavailable photo.
  const image=event.currentTarget;if(image.naturalWidth<32||image.naturalHeight<32)setFailed(true);
 }} onError={()=>setFailed(true)}/>:<p>{t('Loading photo…','ছবি লোড হচ্ছে…')}</p>;
}
function IllustrativeCropImage({name}:{name:string}){
 const {t}=useMarket();const image=cropImageFor(name);const [failed,setFailed]=useState(false);
 if(!image||failed)return <span className="mk-image-placeholder" aria-label={t('No product photo','পণ্যের ছবি নেই')}>❧<span>{t('Farm produce','খামারের পণ্য')}</span></span>;
 return <span className="mk-illustrative-photo">
  {/* These public local photos need no image authentication or external network. */}
  {/* eslint-disable-next-line @next/next/no-img-element */}
  <img className="mk-product-image" src={image.src} alt={t(`Illustrative ${name} crop image`,`ফসলের উদাহরণ ছবি: ${name}`)} onError={()=>setFailed(true)}/>
  <span className="mk-illustrative-label">{t('Illustrative crop image','ফসলের উদাহরণ ছবি')}</span>
  <span className="mk-crop-credit" title={`${image.author} · ${image.license} · ${image.sourceUrl} · ${image.licenseUrl}`}>{image.author} · {image.license}</span>
 </span>;
}
