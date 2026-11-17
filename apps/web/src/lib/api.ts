export const API=process.env.NEXT_PUBLIC_API_URL||'http://127.0.0.1:8000/api/v1';
export async function request<T=unknown>(path:string,options:RequestInit={}):Promise<T>{
 const headers=new Headers(options.headers);const token=typeof window!=='undefined'?localStorage.getItem('agrosphere-token'):null;
 if(token)headers.set('Authorization',`Bearer ${token}`);
 if(options.body&&!(options.body instanceof FormData))headers.set('Content-Type','application/json');
 const response=await fetch(API+path,{...options,headers});
 if(!response.ok){const e=await response.json().catch(()=>({message:'Connection failed'}));throw new Error(e.message||JSON.stringify(e.detail)||`Request failed (${response.status})`)}
 return response.json() as Promise<T>;
}
export async function download(path:string,name:string){const r=await fetch(API+path,{headers:{Authorization:`Bearer ${localStorage.getItem('agrosphere-token')}`}});if(!r.ok)throw new Error('Export failed');const blob=await r.blob();const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;a.click();URL.revokeObjectURL(url)}
export function formatTime(value:string){return new Intl.DateTimeFormat('en-BD',{dateStyle:'medium',timeStyle:'short',timeZone:'Asia/Dhaka'}).format(new Date(value))+' BST'}
export function netReturn(price:number,quantity:number,loss:number,costs:number){return quantity*(1-loss)*price-costs}
